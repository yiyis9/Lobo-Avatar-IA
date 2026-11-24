using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace LoboUPVT
{
    [Serializable] public sealed class ChatRequest { public string mensaje; }
    [Serializable] public sealed class ChatResponse { public string respuesta; public string animacion; public string emocion; public int consultaId; }
    [Serializable] public sealed class HealthResponse { public string api; public string mysql; }
    [Serializable] public sealed class VoiceTranscriptionResponse { public string transcripcion; }
    [Serializable] public sealed class VoiceSynthesisRequest { public string texto; }

    public sealed class LoboChatClient : MonoBehaviour
    {
        [SerializeField] private string apiBaseUrl = "http://127.0.0.1:8000";
        public event Action<ChatResponse> OnResponse;
        public event Action<string> OnTranscription;
        public event Action<string> OnError;
        public event Action<string> OnSpeechError;
        public event Action<bool> OnConnectionChanged;
        private Coroutine connectionMonitor;

        private string ApiBaseUrl
        {
            get
            {
                var configured = Environment.GetEnvironmentVariable("LOBO_API_BASE_URL");
                if (string.IsNullOrWhiteSpace(configured)) configured = PlayerPrefs.GetString("LoboApiBaseUrl", apiBaseUrl);
                return configured.TrimEnd('/');
            }
        }

        public void StartConnectionMonitor()
        {
            if (connectionMonitor == null) connectionMonitor = StartCoroutine(MonitorConnection());
        }

        private IEnumerator MonitorConnection()
        {
            while (true)
            {
                yield return StartCoroutine(CheckHealth());
                yield return new WaitForSecondsRealtime(10f);
            }
        }

        public void Send(string message)
        {
            if (string.IsNullOrWhiteSpace(message)) { OnError?.Invoke("Escribe una pregunta."); return; }
            StartCoroutine(PostQuestion(message.Trim()));
        }

        public void Transcribe(byte[] wavAudio)
        {
            if (wavAudio == null || wavAudio.Length == 0) { OnError?.Invoke("No se capturó audio."); return; }
            StartCoroutine(PostVoice(wavAudio));
        }

        public void Speak(string text, AudioSource audioSource)
        {
            if (!string.IsNullOrWhiteSpace(text) && audioSource != null)
                StartCoroutine(PostSpeech(text.Trim(), audioSource));
        }

        private IEnumerator CheckHealth()
        {
            using (var request = UnityWebRequest.Get(ApiBaseUrl + "/health"))
            {
                request.timeout = 5;
                yield return request.SendWebRequest();
                var healthy = request.result == UnityWebRequest.Result.Success;
                if (healthy)
                {
                    var health = JsonUtility.FromJson<HealthResponse>(request.downloadHandler.text);
                    healthy = health != null && health.api == "operativa" && health.mysql == "conectado";
                }
                OnConnectionChanged?.Invoke(healthy);
            }
        }

        private IEnumerator PostQuestion(string message)
        {
            var payload = JsonUtility.ToJson(new ChatRequest { mensaje = message });
            const int maxAttempts = 3;
            for (var attempt = 1; attempt <= maxAttempts; attempt++)
            {
                using (var request = new UnityWebRequest(ApiBaseUrl + "/api/v1/chat", "POST"))
                {
                    request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(payload));
                    request.downloadHandler = new DownloadHandlerBuffer();
                    request.SetRequestHeader("Content-Type", "application/json");
                    request.timeout = 15;
                    yield return request.SendWebRequest();
                    if (request.result == UnityWebRequest.Result.Success)
                    {
                        OnConnectionChanged?.Invoke(true);
                        OnResponse?.Invoke(JsonUtility.FromJson<ChatResponse>(request.downloadHandler.text));
                        yield break;
                    }

                    var retryable = request.result == UnityWebRequest.Result.ConnectionError ||
                                    (long)request.responseCode >= 500;
                    if (!retryable || attempt == maxAttempts)
                    {
                        OnConnectionChanged?.Invoke(false);
                        OnError?.Invoke(request.error ?? "No se pudo conectar con Lobo UPVT.");
                        yield break;
                    }
                }
                yield return new WaitForSecondsRealtime(attempt);
            }
        }

        private IEnumerator PostVoice(byte[] wavAudio)
        {
            using (var request = new UnityWebRequest(ApiBaseUrl + "/api/v1/voz/transcribir", "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(wavAudio);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.SetRequestHeader("Content-Type", "audio/wav");
                request.timeout = 45;
                yield return request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success)
                {
                    OnError?.Invoke("No se pudo reconocer la voz. Intenta de nuevo o escribe tu pregunta.");
                    yield break;
                }
                var result = JsonUtility.FromJson<VoiceTranscriptionResponse>(request.downloadHandler.text);
                if (result == null || string.IsNullOrWhiteSpace(result.transcripcion))
                {
                    OnError?.Invoke("No se reconoció una pregunta. Intenta de nuevo.");
                    yield break;
                }
                OnTranscription?.Invoke(result.transcripcion.Trim());
            }
        }

        private IEnumerator PostSpeech(string text, AudioSource audioSource)
        {
            var payload = JsonUtility.ToJson(new VoiceSynthesisRequest { texto = text });
            using (var request = new UnityWebRequest(ApiBaseUrl + "/api/v1/voz/sintetizar", "POST"))
            {
                request.uploadHandler = new UploadHandlerRaw(Encoding.UTF8.GetBytes(payload));
                request.downloadHandler = new DownloadHandlerAudioClip(ApiBaseUrl + "/api/v1/voz/sintetizar", AudioType.WAV);
                request.SetRequestHeader("Content-Type", "application/json");
                request.timeout = 60;
                yield return request.SendWebRequest();
                if (request.result != UnityWebRequest.Result.Success)
                {
                    OnSpeechError?.Invoke(request.error ?? "No se pudo reproducir la respuesta.");
                    yield break;
                }
                var clip = DownloadHandlerAudioClip.GetContent(request);
                if (clip == null)
                {
                    OnSpeechError?.Invoke("No se recibió audio compatible.");
                    yield break;
                }
                audioSource.Stop();
                var previousClip = audioSource.clip;
                audioSource.clip = clip;
                audioSource.Play();
                if (previousClip != null && previousClip != clip) UnityEngine.Object.Destroy(previousClip);
            }
        }
    }
}

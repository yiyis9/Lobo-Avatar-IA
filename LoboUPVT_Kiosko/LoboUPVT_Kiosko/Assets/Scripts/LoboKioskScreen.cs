using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;
using System.Collections;
using System.IO;
using System.Text;

namespace LoboUPVT
{
    public sealed class LoboKioskScreen : MonoBehaviour
    {
        private static readonly Color Guinda = Hex("B70D30");
        private static readonly Color Verde = Hex("1E6F14");
        private static readonly Color Carbon = Hex("404648");
        private static readonly Color Gris = Hex("7A7980");

        private Text responseText;
        private InputField questionInput;
        private Button sendButton;
        private Button voiceButton;
        private Text voiceStatus;
        private LoboChatClient client;
        private AudioSource speechSource;
        private Animator avatarAnimator;
        private AudioClip microphoneClip;
        private string microphoneDevice;
        private bool waiting;
        private bool recordingVoice;
        private float lastInteractionTime;
        private float idleTimeoutSeconds = 120f;
        private bool idlePromptShown;
        private const int MaxRecordingSeconds = 12;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void CreateKiosk()
        {
            if (FindAnyObjectByType<LoboKioskScreen>() != null) return;
            var kiosk = new GameObject("Lobo UPVT Public Kiosk");
            kiosk.AddComponent<LoboKioskScreen>();
        }

        private void Awake()
        {
            idleTimeoutSeconds = Mathf.Max(15f, PlayerPrefs.GetFloat("LoboKioskIdleTimeoutSeconds", 120f));
            lastInteractionTime = Time.unscaledTime;
            BuildInterface();
            BindAvatar(FindAnyObjectByType<Animator>(), null);
            client = gameObject.AddComponent<LoboChatClient>();
            client.OnResponse += ShowResponse;
            client.OnTranscription += ShowTranscription;
            client.OnError += ShowError;
            client.OnSpeechError += ShowSpeechError;
            client.OnConnectionChanged += UpdateConnectionStatus;
            client.StartConnectionMonitor();
            questionInput.onValueChanged.AddListener(_ => RegisterInteraction());
        }

        private void Update()
        {
            if (waiting || recordingVoice || speechSource != null && speechSource.isPlaying)
            {
                lastInteractionTime = Time.unscaledTime;
                return;
            }
            if (!idlePromptShown && Time.unscaledTime - lastInteractionTime >= idleTimeoutSeconds)
                ShowIdlePrompt();
        }

        private void OnDestroy()
        {
            if (client == null) return;
            client.OnResponse -= ShowResponse;
            client.OnTranscription -= ShowTranscription;
            client.OnError -= ShowError;
            client.OnSpeechError -= ShowSpeechError;
            client.OnConnectionChanged -= UpdateConnectionStatus;
            if (recordingVoice && !string.IsNullOrEmpty(microphoneDevice)) Microphone.End(microphoneDevice);
            if (microphoneClip != null) Destroy(microphoneClip);
        }

        private void BuildInterface()
        {
            if (FindAnyObjectByType<EventSystem>() == null)
            {
                var eventSystem = new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
                eventSystem.GetComponent<InputSystemUIInputModule>().AssignDefaultActions();
                DontDestroyOnLoad(eventSystem);
            }

            var canvasObject = new GameObject("Kiosk Canvas", typeof(Canvas), typeof(CanvasScaler), typeof(GraphicRaycaster));
            var canvas = canvasObject.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            var scaler = canvasObject.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920, 1080);
            scaler.matchWidthOrHeight = 0.5f;
            canvasObject.transform.SetParent(transform, false);

            var root = Rect(canvasObject.transform, "Background", Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            root.gameObject.AddComponent<Image>().color = Color.white;
            AddHeader(root);
            AddPrompt(root);
            AddResponse(root);
            AddComposer(root);
        }

        private void AddHeader(RectTransform root)
        {
            var header = Rect(root, "Header", new Vector2(0.14f, 0.84f), new Vector2(0.86f, 0.94f), Vector2.zero, Vector2.zero);
            AddText(header, "Lobo UPVT", 30, Guinda, TextAnchor.MiddleCenter, FontStyle.Bold);
        }

        private void AddPrompt(RectTransform root)
        {
            var prompt = Rect(root, "Prompt", new Vector2(0.14f, 0.72f), new Vector2(0.86f, 0.81f), Vector2.zero, Vector2.zero);
            AddText(prompt, "¿Qué te gustaría saber?", 25, Carbon, TextAnchor.MiddleCenter, FontStyle.Normal);
        }

        private void AddResponse(RectTransform root)
        {
            var responsePanel = Rect(root, "Response area", new Vector2(0.14f, 0.34f), new Vector2(0.86f, 0.68f), Vector2.zero, Vector2.zero);
            responsePanel.gameObject.AddComponent<Image>().color = new Color(0.96f, 0.97f, 0.96f);
            var response = Rect(responsePanel, "Response text", new Vector2(0.04f, 0.08f), new Vector2(0.96f, 0.92f), Vector2.zero, Vector2.zero);
            responseText = AddText(response, "La respuesta aparecerá aquí.", 22, Gris, TextAnchor.MiddleCenter, FontStyle.Normal);
            responseText.horizontalOverflow = HorizontalWrapMode.Wrap;
            responseText.verticalOverflow = VerticalWrapMode.Overflow;
        }

        private void AddComposer(RectTransform root)
        {
            var composer = Rect(root, "Question composer", new Vector2(0.14f, 0.19f), new Vector2(0.86f, 0.29f), Vector2.zero, Vector2.zero);
            var inputRect = Rect(composer, "Question input", Vector2.zero, new Vector2(0.61f, 1f), Vector2.zero, Vector2.zero);
            inputRect.gameObject.AddComponent<Image>().color = Color.white;
            questionInput = inputRect.gameObject.AddComponent<InputField>();
            questionInput.characterLimit = 1000;
            questionInput.lineType = InputField.LineType.SingleLine;
            questionInput.targetGraphic = inputRect.GetComponent<Image>();
            var textRect = Rect(inputRect, "Input text", new Vector2(0.025f, 0.08f), new Vector2(0.975f, 0.92f), Vector2.zero, Vector2.zero);
            var inputText = AddText(textRect, "", 20, Carbon, TextAnchor.MiddleLeft, FontStyle.Normal);
            questionInput.textComponent = inputText;
            var placeholder = AddText(textRect, "Escribe aquí tu pregunta...", 20, Gris, TextAnchor.MiddleLeft, FontStyle.Italic);
            questionInput.placeholder = placeholder;

            var buttonRect = Rect(composer, "Send button", new Vector2(0.64f, 0f), new Vector2(0.80f, 1f), Vector2.zero, Vector2.zero);
            var buttonImage = buttonRect.gameObject.AddComponent<Image>();
            buttonImage.color = Verde;
            sendButton = buttonRect.gameObject.AddComponent<Button>();
            sendButton.targetGraphic = buttonImage;
            sendButton.onClick.AddListener(SendQuestion);
            AddText(buttonRect, "Enviar", 18, Color.white, TextAnchor.MiddleCenter, FontStyle.Bold);
            questionInput.onSubmit.AddListener(_ => SendQuestion());

            var voiceRect = Rect(composer, "Voice button", new Vector2(0.83f, 0f), Vector2.one, Vector2.zero, Vector2.zero);
            var voiceImage = voiceRect.gameObject.AddComponent<Image>();
            voiceImage.color = Guinda;
            voiceButton = voiceRect.gameObject.AddComponent<Button>();
            voiceButton.targetGraphic = voiceImage;
            voiceButton.onClick.AddListener(ToggleVoiceCapture);
            AddText(voiceRect, "Hablar", 18, Color.white, TextAnchor.MiddleCenter, FontStyle.Bold);

            var statusRect = Rect(root, "Voice status", new Vector2(0.14f, 0.12f), new Vector2(0.86f, 0.17f), Vector2.zero, Vector2.zero);
            voiceStatus = AddText(statusRect, "Pulsa Hablar para dictar. El audio se envía a Gemini para transcribirlo; evita decir datos personales.", 13, Gris, TextAnchor.MiddleLeft, FontStyle.Normal);
        }

        private void SendQuestion()
        {
            if (waiting || string.IsNullOrWhiteSpace(questionInput.text)) return;
            RegisterInteraction();
            speechSource.Stop();
            waiting = true;
            SetBusy(true);
            responseText.text = "Buscando información institucional...";
            responseText.color = Gris;
            client.Send(questionInput.text);
        }

        private void ShowResponse(ChatResponse response)
        {
            RegisterInteraction();
            waiting = false;
            SetBusy(false);
            responseText.text = response != null && !string.IsNullOrWhiteSpace(response.respuesta)
                ? response.respuesta
                : "No se recibió una respuesta válida. Inténtalo de nuevo.";
            responseText.color = Carbon;
            voiceStatus.text = "Lobo está preparando la respuesta en voz...";
            PlayAvatarAnimation(response != null ? response.animacion : null);
            client.Speak(responseText.text, speechSource);
            questionInput.ActivateInputField();
        }

        public void BindAvatar(Animator animator, AudioSource speaker)
        {
            avatarAnimator = animator;
            if (speaker == null && avatarAnimator != null)
            {
                var avatarRoot = avatarAnimator.transform.root.gameObject;
                speaker = avatarRoot.GetComponent<AudioSource>();
                if (speaker == null) speaker = avatarRoot.AddComponent<AudioSource>();
            }
            if (speaker == null)
            {
                speaker = gameObject.GetComponent<AudioSource>();
                if (speaker == null) speaker = gameObject.AddComponent<AudioSource>();
            }
            speaker.playOnAwake = false;
            speechSource = speaker;
        }

        private void PlayAvatarAnimation(string animationName)
        {
            if (avatarAnimator == null || string.IsNullOrWhiteSpace(animationName)) return;
            foreach (var parameter in avatarAnimator.parameters)
            {
                if (parameter.type != AnimatorControllerParameterType.Trigger || parameter.name != animationName) continue;
                avatarAnimator.SetTrigger(parameter.name);
                return;
            }
        }

        private void ToggleVoiceCapture()
        {
            RegisterInteraction();
            if (recordingVoice) StopVoiceCapture();
            else if (!waiting) StartCoroutine(BeginVoiceCapture());
        }

        private IEnumerator BeginVoiceCapture()
        {
            if (Microphone.devices.Length == 0)
            {
                voiceStatus.text = "No se encontró un micrófono. Puedes escribir tu pregunta.";
                yield break;
            }

#if UNITY_WEBGL || UNITY_ANDROID || UNITY_IOS
            yield return Application.RequestUserAuthorization(UserAuthorization.Microphone);
            if (!Application.HasUserAuthorization(UserAuthorization.Microphone))
            {
                voiceStatus.text = "Permite el acceso al micrófono para dictar una pregunta.";
                yield break;
            }
#endif
            microphoneDevice = Microphone.devices[0];
            microphoneClip = Microphone.Start(microphoneDevice, false, MaxRecordingSeconds, 16000);
            if (microphoneClip == null)
            {
                voiceStatus.text = "No se pudo iniciar el micrófono. Puedes escribir tu pregunta.";
                yield break;
            }
            recordingVoice = true;
            voiceButton.GetComponentInChildren<Text>().text = "Terminar";
            voiceButton.GetComponent<Image>().color = Verde;
            voiceStatus.text = "Escuchando... pulsa Terminar al acabar (máximo 12 segundos).";
            StartCoroutine(StopVoiceAfterLimit());
        }

        private IEnumerator StopVoiceAfterLimit()
        {
            yield return new WaitForSeconds(MaxRecordingSeconds);
            if (recordingVoice) StopVoiceCapture();
        }

        private void StopVoiceCapture()
        {
            var samplePosition = Microphone.GetPosition(microphoneDevice);
            Microphone.End(microphoneDevice);
            recordingVoice = false;
            voiceButton.GetComponentInChildren<Text>().text = "Hablar";
            voiceButton.GetComponent<Image>().color = Guinda;

            if (microphoneClip == null || samplePosition <= 0)
            {
                if (microphoneClip != null) Destroy(microphoneClip);
                microphoneClip = null;
                voiceStatus.text = "No se captó voz. Intenta de nuevo o escribe tu pregunta.";
                return;
            }

            var audio = EncodeWav(microphoneClip, samplePosition);
            Destroy(microphoneClip);
            microphoneClip = null;
            if (audio == null || audio.Length == 0)
            {
                voiceStatus.text = "No se pudo preparar el audio. Intenta escribir tu pregunta.";
                return;
            }
            waiting = true;
            SetBusy(true);
            voiceStatus.text = "Transcribiendo la pregunta...";
            client.Transcribe(audio);
        }

        private void ShowTranscription(string transcript)
        {
            RegisterInteraction();
            waiting = false;
            SetBusy(false);
            questionInput.text = transcript;
            responseText.text = "Revisa la pregunta reconocida y pulsa Enviar para consultarla.";
            responseText.color = Carbon;
            voiceStatus.text = "Pregunta reconocida. Puedes corregirla antes de enviarla.";
            questionInput.ActivateInputField();
        }

        private static byte[] EncodeWav(AudioClip clip, int recordedFrames)
        {
            var channels = Mathf.Max(1, clip.channels);
            var frames = Mathf.Clamp(recordedFrames, 0, clip.samples);
            var samples = new float[clip.samples * channels];
            if (frames == 0 || !clip.GetData(samples, 0)) return null;

            using (var stream = new MemoryStream())
            using (var writer = new BinaryWriter(stream))
            {
                var dataLength = frames * 2;
                writer.Write(Encoding.ASCII.GetBytes("RIFF"));
                writer.Write(36 + dataLength);
                writer.Write(Encoding.ASCII.GetBytes("WAVEfmt "));
                writer.Write(16);
                writer.Write((short)1);
                writer.Write((short)1);
                writer.Write(clip.frequency);
                writer.Write(clip.frequency * 2);
                writer.Write((short)2);
                writer.Write((short)16);
                writer.Write(Encoding.ASCII.GetBytes("data"));
                writer.Write(dataLength);
                for (var frame = 0; frame < frames; frame++)
                {
                    var mono = 0f;
                    for (var channel = 0; channel < channels; channel++) mono += samples[frame * channels + channel];
                    mono /= channels;
                    var value = (short)Mathf.RoundToInt(Mathf.Clamp(mono, -1f, 1f) * (mono < 0 ? 32768f : 32767f));
                    writer.Write(value);
                }
                return stream.ToArray();
            }
        }

        private void ShowError(string error)
        {
            RegisterInteraction();
            waiting = false;
            SetBusy(false);
            responseText.text = "No pudimos completar la consulta. Revisa la conexión con el servicio e inténtalo nuevamente.";
            responseText.color = Guinda;
            Debug.LogWarning("Lobo UPVT kiosk request failed: " + error);
            voiceStatus.text = "No se completó la consulta. Intenta de nuevo o escribe tu pregunta.";
        }

        private void ShowSpeechError(string error)
        {
            voiceStatus.text = "La respuesta escrita está lista, pero no se pudo reproducir la voz.";
            Debug.LogWarning("Lobo UPVT speech playback failed: " + error);
        }

        private void RegisterInteraction()
        {
            lastInteractionTime = Time.unscaledTime;
            idlePromptShown = false;
        }

        private void ShowIdlePrompt()
        {
            idlePromptShown = true;
            questionInput.text = string.Empty;
            responseText.text = "¡Hola! Soy Lobo UPVT. Escribe o dicta tu pregunta para comenzar.";
            responseText.color = Gris;
            voiceStatus.text = "Kiosko listo para una nueva consulta.";
            if (speechSource != null) speechSource.Stop();
            PlayAvatarAnimation("idle");
        }

        private void UpdateConnectionStatus(bool connected)
        {
            if (waiting || recordingVoice) return;
            voiceStatus.text = connected
                ? "Conexión con FastAPI y MySQL disponible."
                : "Sin conexión con el servicio. Se reintentará automáticamente.";
        }

        private void SetBusy(bool busy)
        {
            sendButton.interactable = !busy;
            sendButton.GetComponent<Image>().color = busy ? Gris : Verde;
        }

        private static RectTransform Rect(Transform parent, string name, Vector2 anchorMin, Vector2 anchorMax, Vector2 offsetMin, Vector2 offsetMax)
        {
            var child = new GameObject(name, typeof(RectTransform));
            child.transform.SetParent(parent, false);
            var rect = child.GetComponent<RectTransform>();
            rect.anchorMin = anchorMin;
            rect.anchorMax = anchorMax;
            rect.offsetMin = offsetMin;
            rect.offsetMax = offsetMax;
            return rect;
        }

        private static Text AddText(RectTransform parent, string value, int size, Color color, TextAnchor alignment, FontStyle style)
        {
            var textRect = parent.GetComponent<Text>() == null ? parent : Rect(parent, "Label", Vector2.zero, Vector2.one, Vector2.zero, Vector2.zero);
            var text = textRect.gameObject.AddComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            text.text = value;
            text.fontSize = size;
            text.color = color;
            text.alignment = alignment;
            text.fontStyle = style;
            text.horizontalOverflow = HorizontalWrapMode.Wrap;
            text.verticalOverflow = VerticalWrapMode.Truncate;
            text.raycastTarget = false;
            return text;
        }

        private static Color Hex(string value)
        {
            ColorUtility.TryParseHtmlString("#" + value, out var color);
            return color;
        }
    }
}

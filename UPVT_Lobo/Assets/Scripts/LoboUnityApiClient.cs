using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

[Serializable]
public sealed class LoboChatTurn
{
    public string role;
    public string content;
}

[Serializable]
public sealed class LoboChatRequest
{
    public string mensaje;
    public LoboChatTurn[] contexto = Array.Empty<LoboChatTurn>();
    public string request_id;
}

[Serializable]
public sealed class LoboChatReply
{
    public string respuesta;
    public string accion_avatar;
    public string animacion;
    public string emocion;
    public int consultaId;
}

/// <summary>Cliente Unity del mismo endpoint que usa el kiosco web.</summary>
public sealed class LoboUnityApiClient : MonoBehaviour
{
    [SerializeField] private string apiBaseUrl = "http://127.0.0.1:8000";
    public string ApiBaseUrl { get => apiBaseUrl; set => apiBaseUrl = value?.TrimEnd('/'); }

    private void Awake()
    {
        var configuredUrl = Environment.GetEnvironmentVariable("LOBO_API_BASE_URL");
        if (!string.IsNullOrWhiteSpace(configuredUrl)) ApiBaseUrl = configuredUrl;
    }

    public void Ask(string message, Action<LoboChatReply> onSuccess, Action<string> onError = null)
    {
        StartCoroutine(PostQuestion(message, onSuccess, onError));
    }

    private IEnumerator PostQuestion(string message, Action<LoboChatReply> onSuccess, Action<string> onError)
    {
        var requestId = Guid.NewGuid().ToString("N");
        var body = JsonUtility.ToJson(new LoboChatRequest { mensaje = message, request_id = requestId });
        var bytes = Encoding.UTF8.GetBytes(body);
        string lastError = "No se pudo conectar con el servicio de consultas.";

        for (var attempt = 0; attempt < 3; attempt++)
        {
            using (var request = new UnityWebRequest(ApiBaseUrl + "/api/v1/chat", UnityWebRequest.kHttpVerbPOST))
            {
                request.uploadHandler = new UploadHandlerRaw(bytes);
                request.downloadHandler = new DownloadHandlerBuffer();
                request.timeout = 10;
                request.SetRequestHeader("Content-Type", "application/json");
                yield return request.SendWebRequest();

                if (request.result == UnityWebRequest.Result.Success)
                {
                    LoboChatReply reply = null;
                    try { reply = JsonUtility.FromJson<LoboChatReply>(request.downloadHandler.text); }
                    catch (Exception exception) { lastError = "La respuesta del servicio no se pudo interpretar: " + exception.Message; }
                    if (reply != null && !string.IsNullOrWhiteSpace(reply.respuesta))
                    {
                        onSuccess?.Invoke(reply);
                        yield break;
                    }
                    onError?.Invoke(lastError);
                    yield break;
                }

                lastError = string.IsNullOrWhiteSpace(request.error)
                    ? "El servicio de consultas respondió con un error."
                    : request.error;
                var transient = request.result == UnityWebRequest.Result.ConnectionError
                    || request.result == UnityWebRequest.Result.DataProcessingError
                    || request.responseCode >= 500;
                if (!transient || attempt == 2)
                {
                    onError?.Invoke(lastError);
                    yield break;
                }
            }

            yield return new WaitForSecondsRealtime(0.5f * Mathf.Pow(2, attempt));
        }

        onError?.Invoke(lastError);
    }
}

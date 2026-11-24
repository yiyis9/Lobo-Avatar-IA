using UnityEngine;

/// <summary>Interfaz táctil básica para probar las consultas en la escena Unity.</summary>
public sealed class LoboUnityKioskView : MonoBehaviour
{
    [SerializeField] private LoboUnityApiClient api;
    [SerializeField] private LoboAvatarAnimator avatar;
    private string question = "";
    private string answer = "Hola, soy Lobo. Escribe una pregunta sobre la UPVT.";
    private string status = "Servicio de consultas";
    private bool busy;
    private GUIStyle panelStyle;
    private GUIStyle answerStyle;
    private GUIStyle fieldStyle;
    private GUIStyle buttonStyle;
    private Vector2 answerScroll;
    private TouchScreenKeyboard touchKeyboard;

    public void Initialize(LoboUnityApiClient apiClient, LoboAvatarAnimator avatarAnimator)
    {
        api = apiClient;
        avatar = avatarAnimator;
    }

    private void OnGUI()
    {
        EnsureStyles();
        var scale = Mathf.Clamp(Screen.width / 1280f, 0.8f, 1.35f);
        var width = Mathf.Min(Screen.width - 32f, 520f * scale);
        var height = Mathf.Min(Screen.height - 32f, 330f * scale);
        var rect = new Rect(16, 16, width, height);
        GUI.Box(rect, GUIContent.none, panelStyle);
        GUILayout.BeginArea(new Rect(rect.x + 18, rect.y + 14, rect.width - 36, rect.height - 28));
        GUILayout.Label("LOBO UPVT  ·  ASISTENTE INSTITUCIONAL", buttonStyle);
        GUILayout.Space(10);
        answerScroll = GUILayout.BeginScrollView(answerScroll, GUILayout.ExpandHeight(true));
        GUILayout.Label(answer, answerStyle, GUILayout.ExpandHeight(true));
        GUILayout.EndScrollView();
        GUILayout.Space(10);
        GUI.SetNextControlName("lobo-question");
        var inputRect = GUILayoutUtility.GetRect(0, 52 * scale, GUILayout.ExpandWidth(true));
        question = GUI.TextField(inputRect, question, fieldStyle);
        if (Event.current.type == EventType.MouseDown && inputRect.Contains(Event.current.mousePosition) && TouchScreenKeyboard.isSupported)
        {
            touchKeyboard = TouchScreenKeyboard.Open(question, TouchScreenKeyboardType.Default, true, false, false, false, "Escribe tu pregunta");
            Event.current.Use();
        }
        GUILayout.Space(8);
        GUILayout.BeginHorizontal();
        GUILayout.Label(status, answerStyle, GUILayout.ExpandWidth(true));
        GUI.enabled = !busy && !string.IsNullOrWhiteSpace(question);
        if (GUILayout.Button(busy ? "Consultando…" : "Enviar pregunta", buttonStyle, GUILayout.Width(185 * scale), GUILayout.Height(48 * scale))) Submit();
        GUI.enabled = true;
        GUILayout.EndHorizontal();
        GUILayout.EndArea();
    }

    private void Update()
    {
        if (touchKeyboard == null) return;
        question = touchKeyboard.text;
        if (touchKeyboard.status == TouchScreenKeyboard.Status.Done
            || touchKeyboard.status == TouchScreenKeyboard.Status.Canceled
            || touchKeyboard.status == TouchScreenKeyboard.Status.LostFocus)
            touchKeyboard = null;
    }

    private void EnsureStyles()
    {
        if (panelStyle != null) return;
        panelStyle = new GUIStyle(GUI.skin.box) { normal = { background = MakeTexture(new Color(1f, 1f, 1f, 0.96f)) } };
        answerStyle = new GUIStyle(GUI.skin.label) { fontSize = 19, wordWrap = true, normal = { textColor = new Color(0.13f, 0.16f, 0.16f) } };
        fieldStyle = new GUIStyle(GUI.skin.textField) { fontSize = 20, padding = new RectOffset(12, 12, 10, 10) };
        buttonStyle = new GUIStyle(GUI.skin.button) { fontSize = 16, fontStyle = FontStyle.Bold, wordWrap = true };
    }

    private static Texture2D MakeTexture(Color color)
    {
        var texture = new Texture2D(1, 1);
        texture.SetPixel(0, 0, color);
        texture.Apply();
        return texture;
    }

    private void Submit()
    {
        var text = question.Trim();
        if (text.Length < 2 || api == null) return;
        busy = true;
        status = "Buscando información…";
        api.Ask(text, reply =>
        {
            answer = reply.respuesta;
            status = "Respuesta lista";
            avatar?.PlayReply(reply);
            question = "";
            busy = false;
        }, error =>
        {
            status = "No se pudo conectar. Intenta de nuevo.";
            answer = error;
            busy = false;
        });
    }
}

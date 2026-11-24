using UnityEngine;
using UnityEngine.SceneManagement;

/// <summary>Agrega el modelo articulado y la interfaz a escenas del proyecto al iniciar.</summary>
public static class LoboUnityBootstrap
{
    private const string RuntimeName = "LoboUPVT_KioskRuntime";
    private const string ModelName = "LoboUPVT_Rigged";
    private static bool initializing;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void InstallIntoLoadedScene()
    {
        SceneManager.sceneLoaded -= OnSceneLoaded;
        SceneManager.sceneLoaded += OnSceneLoaded;
        Install();
    }

    private static void OnSceneLoaded(Scene scene, LoadSceneMode mode) => Install();

    private static void Install()
    {
        if (initializing || GameObject.Find(RuntimeName) != null) return;
        initializing = true;
        try
        {
            var prefab = Resources.Load<GameObject>(ModelName);
            if (prefab == null)
            {
                Debug.LogError("No se pudo cargar Assets/Resources/" + ModelName + ".glb. Espera a que Unity termine de importar el modelo.");
                return;
            }

            var avatar = Object.Instantiate(prefab);
            avatar.name = "LoboUPVT_Articulado";
            avatar.transform.position = Vector3.zero;
            avatar.transform.rotation = Quaternion.Euler(0f, 180f, 0f);

            var animator = avatar.GetComponentInChildren<Animator>(true);
            var legacyAnimation = avatar.GetComponentInChildren<Animation>(true);
            var avatarAnimation = avatar.GetComponent<LoboAvatarAnimator>() ?? avatar.AddComponent<LoboAvatarAnimator>();
            avatarAnimation.SetAnimator(animator);
            avatarAnimation.SetLegacyAnimation(legacyAnimation);

            var camera = Camera.main;
            if (camera != null)
            {
                camera.transform.position = new Vector3(0f, 0.1f, -2.5f);
                camera.transform.rotation = Quaternion.identity;
                camera.clearFlags = CameraClearFlags.SolidColor;
                camera.backgroundColor = new Color(0.94f, 0.96f, 0.95f);
            }

            var runtime = new GameObject(RuntimeName);
            var api = runtime.AddComponent<LoboUnityApiClient>();
            var view = runtime.AddComponent<LoboUnityKioskView>();
            view.Initialize(api, avatarAnimation);
            Debug.Log("Kiosko Unity de Lobo UPVT listo: avatar articulado, preguntas a la API y consultas registradas en el historial.");
        }
        finally
        {
            initializing = false;
        }
    }
}

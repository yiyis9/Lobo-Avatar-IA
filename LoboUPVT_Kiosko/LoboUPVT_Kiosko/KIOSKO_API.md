# Kiosko Unity y API FastAPI

El kiosko Unity es la interfaz pública. Se comunica solo con FastAPI; no se conecta directamente con MySQL ni con el panel administrativo. El visitante no necesita iniciar sesión.

## Ejecutar localmente

1. Inicia FastAPI desde `backend`:

   ```powershell
   uvicorn main:app --reload --host 127.0.0.1 --port 8000
   ```

2. Confirma `http://127.0.0.1:8000/health`; debe informar que API y MySQL están operativas.
3. Abre `LoboUPVT_Kiosko/LoboUPVT_Kiosko` en Unity y ejecuta `Assets/Scenes/SampleScene.unity`.
4. El cliente C# llama `POST /api/v1/chat`; FastAPI busca en MySQL y registra cada consulta.

## Servicios utilizados por Unity

- `GET /health`: disponibilidad de FastAPI y MySQL.
- `POST /api/v1/chat`: búsqueda institucional y registro de la consulta.
- `POST /api/v1/voz/transcribir`: transcribe audio español enviado como WAV.
- `POST /api/v1/voz/sintetizar`: devuelve voz generada para la respuesta.

La URL predeterminada es `http://127.0.0.1:8000`. Para cambiarla, configura `LOBO_API_BASE_URL` en el entorno del proceso de Unity o `LoboApiBaseUrl` en PlayerPrefs. En otra computadora de la misma red, configura la IP local del servidor y permite el puerto de FastAPI en el firewall de la red privada.

El panel administrativo es otra interfaz web, servida por el mismo backend en `/panel/`. Requiere autenticación y permisos. El kiosko permanece público. Laravel no forma parte de la arquitectura actual.

## Estado de integración

El proyecto incluye el cliente API C#, una pantalla Unity provisional, entrada de voz por micrófono y reproducción de voz. El avatar GLB está integrado en el kiosko web, pero no está importado ni enlazado al `Animator` de la escena Unity. Kinect/MediaPipe y la detección automática de presencia todavía no están integrados. La escena actual genera la interfaz durante la ejecución.

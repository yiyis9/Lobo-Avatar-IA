# Lobo UPVT · Avatar digital 3D con IA

Sistema interactivo con un avatar 3D (el Lobo Blanco de la UPVT) que funciona como kiosko virtual. Responde preguntas frecuentes y orienta a los visitantes de la **Universidad Politécnica del Valle de Toluca**, y cuenta con un panel web para que el personal administre el contenido.

## ¿Qué hace?

- **Kiosko público** (`/kiosko/`): el visitante escribe o habla su pregunta y el Lobo responde con voz y gestos (saludo, hablar, pensar, celebrar, explicar). No pide cuenta.
- **Detección con cámara (opcional)**: MediaPipe Tasks Vision, en el navegador, detecta la presencia de un visitante y gestos de mano. No identifica personas ni guarda ni envía imágenes.
- **Respuestas con IA**: el backend busca en MySQL las fuentes más relevantes y Gemini redacta la respuesta. Si Gemini no está configurado o falla, se usa la respuesta guardada más relevante.
- **Panel administrativo** (`/panel/`): preguntas frecuentes, información institucional, carga de PDF/imágenes con indexado, historial de consultas, mensajes de contacto, usuarios, métricas, respaldos y papelera con retención de 30 días.
- **Roles**: administrador general y administrador de contenido.

## Arquitectura

| Capa | Tecnología |
| --- | --- |
| Backend / API | FastAPI (Python 3.10+), SQLAlchemy 2, PyMySQL |
| Base de datos | MySQL (`lobo_upvt_db`) con migraciones SQL numeradas |
| Kiosko y panel | HTML, CSS y JavaScript servidos por FastAPI; `model-viewer` para el `.glb` |
| Visión por computadora | MediaPipe Tasks Vision (en el navegador) |
| IA y voz | Gemini (chat, transcripción, TTS e indexado de documentos) |
| Modelo 3D | Blender, exportado a GLB con rig de 26 huesos y clips de animación |
| Seguridad | Argon2 (pwdlib), tokens JWT, HTTPS forzable con `FORCE_HTTPS` |

## Estructura del repositorio

```
backend/            API FastAPI (routers/, services/, tests/, migrations/, static/)
  static/kiosk/     Kiosko público y modelos GLB
  static/admin/     Panel administrativo
  static/home/      Página de inicio
tools/              Scripts de Blender para construir y animar el avatar
lobo_upvt_db.sql    Esquema para una instalación nueva
DICCIONARIO_DE_DATOS.md
legacy/             (recomendado) código histórico: admin-panel (Laravel) y backend/LoboUPVT.Api (.NET)
```

> `admin-panel/` (Laravel) y `backend/LoboUPVT.Api/` (ASP.NET Core) son versiones anteriores que ya no forman parte de la ejecución actual.

## Instalación local (Windows PowerShell)

Requisitos: Python 3.10+ y MySQL 8.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

1. Crea la base y el usuario de servicio en MySQL (permisos `SELECT, INSERT, UPDATE, DELETE`) y ejecuta `lobo_upvt_db.sql` desde la raíz.
2. Edita `.env` con las credenciales de MySQL, una `ADMIN_TOKEN_SECRET` aleatoria de al menos 32 caracteres y, si quieres IA, tu `GEMINI_API_KEY`.
3. Crea el administrador inicial:
   ```powershell
   python cli.py create-admin
   ```
4. Arranca el servidor:
   ```powershell
   uvicorn main:app --host 127.0.0.1 --port 8000 --reload
   ```

| Ruta | Descripción |
| --- | --- |
| `http://127.0.0.1:8000/kiosko/` | Kiosko público |
| `http://127.0.0.1:8000/panel/` | Panel administrativo |
| `http://127.0.0.1:8000/docs` | Documentación OpenAPI |
| `http://127.0.0.1:8000/health` | Estado de la API y de MySQL |

Si la base ya existía, aplica las migraciones de `backend/migrations/` en orden (hasta la `018`) antes de arrancar.

## Variables de entorno

Todas están documentadas en `backend/.env.example`. **Nunca subas tu `.env` al repositorio.**

Las principales son `DB_*`, `ADMIN_TOKEN_SECRET`, `REGISTRATION_AUTHORIZATION_KEY`, `SMTP_*` (recuperación de contraseña), `GEMINI_*` y `CORS_ORIGINS`.

## Pruebas

```powershell
cd backend
python -m pip install pytest
python -m pytest tests
```

## Documentación adicional

- [`backend/README.md`](backend/README.md): operación detallada del backend, migraciones y roles.
- [`backend/API.md`](backend/API.md): referencia de la API.
- [`DICCIONARIO_DE_DATOS.md`](DICCIONARIO_DE_DATOS.md): tablas y relaciones.
- [`backend/DEPLOY_RAILWAY.md`](backend/DEPLOY_RAILWAY.md): despliegue público en Railway.

## Notas de privacidad

- El kiosko no pide cuenta; cada consulta se registra de forma anónima para métricas.
- Las preguntas pueden enviarse a Gemini junto con contenido público de MySQL. No cargues datos personales ni información confidencial.
- La cámara solo se activa con permiso explícito y se detiene al salir de la pestaña.

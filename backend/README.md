# Backend FastAPI

FastAPI es el backend central. Requiere Python 3.10 o superior. Unity consume rutas públicas sin iniciar sesión; el panel administrativo web (HTML, CSS y JavaScript) se sirve desde `/panel/` y consume las rutas administrativas con bearer token. La lógica de datos permanece en este backend y MySQL.

## Preparación en Windows PowerShell

El directorio `venv` que ya existe apunta a una ruta antigua de OneDrive; se conservó. Para este proyecto se creó y preparó `.venv` en la carpeta `backend`.

```powershell
cd C:\Users\irisg\Documents\LoboUPVT\backend
.\.venv\Scripts\Activate.ps1
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Edita `.env` con el usuario/contraseña MySQL, una `ADMIN_TOKEN_SECRET` aleatoria de al menos 32 caracteres y la clave de registro administrativo. El backend no usa una cuenta `root` ni contraseña vacía por defecto. No publiques `.env` ni copies secretos al kiosco. Crea previamente el usuario de servicio en MySQL con permisos `SELECT`, `INSERT`, `UPDATE` y `DELETE` sobre `lobo_upvt_db`; aplica la migración con una cuenta DBA.

Ejemplo de creación del usuario de servicio en MySQL (cambia la contraseña y el host según tu instalación):

```sql
CREATE USER 'lobo_api'@'localhost' IDENTIFIED BY 'reemplaza-por-una-clave-segura';
GRANT SELECT, INSERT, UPDATE, DELETE ON lobo_upvt_db.* TO 'lobo_api'@'localhost';
```

Para una base existente, respalda primero la base y ejecuta una vez `migrations/001_fastapi_alignment.sql` sobre MySQL. El script añade las columnas, índices y relación faltantes, además de la tabla de información institucional; conserva filas existentes. Para una instalación nueva, ejecuta `lobo_upvt_db.sql` desde la raíz del proyecto. No uses el SQL de instalación nueva sobre una base productiva sin revisar las sentencias de datos semilla.

Si el SQL conserva el administrador semilla `admin@upvt.edu.mx` con contraseña marcador, inicializa/activa esa cuenta desde esta terminal:

```powershell
python cli.py create-admin
```

El comando pide correo, nombre y contraseña sin mostrarla en pantalla. No restablece cuentas que ya tienen un hash real.

Arranque del servicio:

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

La documentación OpenAPI queda disponible en `http://127.0.0.1:8000/docs`; el estado y la conexión MySQL en `/health`. Para Unity WebGL configura `CORS_ORIGINS` con el origen exacto del kiosco; Unity nativo no utiliza CORS del navegador.

El kiosko público de navegador está disponible en `http://127.0.0.1:8000/kiosko/`. Es independiente del panel privado, no solicita cuenta y envía las preguntas a `POST /api/v1/chat`; cada consulta se busca en MySQL y se registra en el historial. El icono de teléfono abre el formulario **Contáctanos**. Los mensajes se guardan en `mensajes_contacto` y el administrador general los revisa en **Mensajes de contacto** del panel; puede responder desde su aplicación de correo. Para una base existente, ejecuta la migración aditiva `migrations/010_mensajes_contacto.sql`. El sistema no envía correos automáticamente. Con `GEMINI_API_KEY` configurada, FastAPI envía la pregunta y hasta tres fuentes relevantes de MySQL a Gemini para redactar una respuesta en español. No envía datos si no encuentra fuentes; si Gemini no está configurado o falla, usa la respuesta guardada más relevante. El kiosko reproduce la voz masculina mexicana cálida generada por Gemini TTS; si falla, utiliza la voz española instalada en Edge/Windows. El kiosko carga `static/kiosk/models/lobo-upvt-rigged.glb`. El avatar actual del kiosko se actualizó desde `ahora si lobo.glb`, conservando su textura y agregando un rig de 26 huesos con los clips `Idle`, `Saludo`, `Hablar`, `Pensar` y `Celebrar`; el archivo editable es `ahora_si_lobo_articulado.blend`. La versión que estaba en uso se conserva como `lobo-upvt-rigged-pre-2026-11-17.glb`. El kiosko activa el gesto configurado en la respuesta; también reconoce instrucciones directas cortas como “Lobo, saluda” y ejecuta el gesto localmente. El botón **Activar cámara** solicita permiso explícito y usa MediaPipe Tasks Vision en el navegador para detectar presencia facial y gestos de mano: al reconocer a un visitante el avatar saluda; una palma en movimiento activa otro saludo y el pulgar arriba activa celebración. No se reconoce la identidad, no se graban ni envían imágenes y se detiene la cámara al salir de la pestaña. La primera activación requiere Internet para cargar MediaPipe y sus modelos. El componente visor `model-viewer` también se carga desde Google.

El panel web está disponible en `http://127.0.0.1:8000/panel/`. Al servirse desde FastAPI comparte el origen de la API y no necesita configuración CORS adicional. Su inicio de sesión utiliza `POST /api/v1/auth/login`; las solicitudes de registro administrativo usan la clave ingresada en el formulario y quedan pendientes de aprobación. El token se conserva solo durante la sesión actual del navegador.

El relevo de emergencia del administrador general se realiza desde el mismo formulario de registro, seleccionando **Administrador general** y proporcionando `PRINCIPAL_ADMIN_RECOVERY_KEY`. Solo funciona si el administrador principal configurado ya no está activo, aprobado y fuera de la papelera. La clave omite la aprobación, aprueba la cuenta nueva y cambia `PRINCIPAL_ADMIN_EMAIL` al nuevo administrador. Se consume una sola vez y su consumo queda registrado en `estado_relevo_admin`. Genera una clave larga con `python -c "import secrets; print(secrets.token_urlsafe(48))"`, guárdala únicamente en `backend/.env` y entrégala solo a la persona responsable de continuidad. No la guardes en el repositorio ni la compartas por canales públicos. Para una base existente, aplica `migrations/014_relevo_emergencia_admin.sql` después de la 013. Para habilitar un relevo futuro adicional, primero rota `PRINCIPAL_ADMIN_RECOVERY_KEY` por una clave nueva y luego, con una cuenta DBA, ejecuta `UPDATE estado_relevo_admin SET usada_en = NULL, usada_por_id = NULL WHERE id = 1;`; después reinicia FastAPI.

El registro administrativo acepta nombres con letras, espacios, guiones o apóstrofos. Las contraseñas deben tener al menos 12 caracteres, mayúscula, minúscula, número y símbolo, sin espacios. La recuperación envía un código de 6 dígitos válido durante 10 minutos al correo de una cuenta administrativa activa y aprobada. Para habilitar el correo, configura `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` y opcionalmente `SMTP_FROM`/`SMTP_STARTTLS` en `backend/.env`. Para Gmail se requiere una contraseña de aplicación; no uses la contraseña normal de tu cuenta. Reinicia FastAPI después de configurar SMTP. Aplica la migración aditiva `migrations/011_recuperacion_contrasena.sql` con una cuenta DBA antes de usar la recuperación.

En **Información institucional**, un administrador puede seleccionar un PDF de hasta 10 MB o un `.txt`/`.md` de hasta 2 MB y pedir a Gemini que complete el formulario como borrador, incluida la animación. El análisis no guarda el documento ni crea la ficha; para guardar el contenido y adjuntar el PDF, se debe pulsar **Guardar información**. Gemini prepara las respuestas a partir de un máximo de 50,000 caracteres. Para habilitarlo, instala las dependencias y agrega `GEMINI_API_KEY` en el `.env` local; opcionalmente configura `GEMINI_MODEL` (por defecto `gemini-3.8-flash`). No pegues la clave en el código, el repositorio ni este chat. Después reinicia FastAPI. La clave se mantiene solo en el backend.

El texto extraído del documento se envía a Gemini para generar sugerencias; el archivo y las sugerencias no se guardan automáticamente. Revisa cada borrador y pulsa **Guardar** para persistirlo en `informacion_institucional`. Usa solo documentos públicos: no cargues datos personales, contraseñas, información confidencial ni material que no tengas autorización para compartir. La confirmación en pantalla no sustituye esa revisión. Las preguntas del kiosko también pueden enviarse a Gemini junto con el contenido público relevante de MySQL; no ingreses datos personales. La solicitud de chat usa `store=False`.

También puedes escribir información directamente desde esa pantalla y adjuntar hasta 20 archivos públicos (PDF, PNG, JPG o WEBP), con máximo 10 MB por archivo y 20 MB en total por ficha. El texto admite hasta 1 millón de caracteres. El texto seleccionable de los PDF se extrae y se guarda junto con el archivo; Gemini analiza el PDF en segundo plano, recibe el título/categoría o la pregunta a la que está adjunto y agrega al índice palabras clave basadas en el documento y esa ficha. El chat puede encontrar un PDF por esos términos incluso si la pregunta o título del registro no repite la frase exacta. Las palabras clave sirven para recuperar el archivo; la respuesta se redacta usando fragmentos de contenido, no mostrando la lista de palabras clave como respuesta. Si Gemini no está configurado o falla, el PDF conserva su texto seleccionable para la búsqueda. Las imágenes se conservan para consulta desde el kiosko. Las preguntas frecuentes también admiten varios adjuntos; al enviarlas a la papelera, conservan sus archivos durante 30 días y pueden restaurarse desde el panel. Para una base existente, aplica en orden las migraciones aditivas `migrations/002_documentos_institucionales.sql`, `003_documentos_texto_busqueda.sql`, `004_papelera_retencion_30_dias.sql`, `005_document_index_status.sql`, `006_adjuntos_preguntas_y_papelera.sql`, `007_administrador_contenido.sql`, `008_contenido_extenso.sql`, `009_busqueda_fulltext.sql`, `010_mensajes_contacto.sql`, `011_recuperacion_contrasena.sql`, `012_papelera_usuarios.sql`, `013_modulo_historial.sql`, `014_relevo_emergencia_admin.sql`, `015_accion_avatar.sql`, `016_historial_respuestas_contacto.sql` y `017_chat_idempotency_avatar_metadata.sql`, `018_animacion_info_institucional.sql` y `019_papelera_mensajes_contacto.sql`. La 012 añade la papelera de usuarios, la 013 añade el módulo al historial, la 014 registra el canje único de la clave de relevo, la 015 añade acciones del avatar, la 016 registra respuestas a mensajes de contacto y la 017 agrega metadatos e idempotencia al historial, la 018 incorpora animación en información institucional y la 019 añade la papelera de mensajes de contacto con retención de 30 días. Ejecuta las migraciones pendientes en orden; conservan los registros existentes. El historial incluye todas las consultas guardadas y muestra si la fuente fue Preguntas y respuestas, Información institucional, una aclaración o si no se encontró coincidencia. Los registros anteriores a la 013 aparecen como consultas anteriores porque no conservaban ese dato. Los archivos se almacenan en `backend/uploads/institutional/`, fuera de Git; incluye esa carpeta en los respaldos del servidor.

Para volver a analizar con Gemini un PDF que ya estaba cargado antes de esta mejora, usa `python cli.py analyze-document ID`, reemplazando `ID` por el identificador del documento. Ese comando actualiza su texto indexado; no modifica el archivo original ni otros registros.

Instalación/actualización de dependencias e inicio local:

Para una base existente, aplica también `migrations/007_administrador_contenido.sql` después de las migraciones anteriores. Esta migración amplía de forma aditiva el ENUM de `usuarios.rol` con `admin_contenido`; conserva los roles y registros existentes. El administrador de contenido gestiona preguntas, respuestas, información, adjuntos y papelera. El administrador general conserva las funciones de usuarios, solicitudes, métricas y respaldos. Los mensajes de contacto se pueden mover a la papelera y restaurar durante 30 días.

```powershell
python -m pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Para designar una cuenta existente como administrador principal, configura temporalmente `PRINCIPAL_ADMIN_SETUP_KEY` en `backend/.env` y ejecuta `python cli.py assign-principal-admin`. El comando solicita la clave sin mostrarla y solo acepta una cuenta administradora activa y aprobada. Al terminar, guarda `PRINCIPAL_ADMIN_EMAIL` en `.env` y elimina la clave de inicialización. Reinicia FastAPI. La base de datos no requiere cambios de esquema.

La migración `007_administrador_contenido.sql` amplía de forma aditiva el ENUM `usuarios.rol`; conserva los registros existentes. El administrador de contenido gestiona preguntas, respuestas, información, adjuntos y papelera. El administrador general conserva usuarios, solicitudes, métricas y respaldos.

El panel permite actualizar el nombre y cambiar la contraseña desde **Mi perfil**; el cambio de contraseña requiere verificar la contraseña actual.

## Contrato de base de datos

Los modelos SQLAlchemy reflejan los nombres SQL existentes: `usuarios.email`, `usuarios.creado_en`, `historial_consultas.pregunta_usuario`, `respuesta_bot`, `pregunta_frecuente_id` y `fecha_consulta`. No se ejecuta `create_all()` al arrancar: cambios de esquema se aplican mediante los scripts SQL versionados.

Las preguntas y respuestas siguen juntas en `preguntas_frecuentes`. `categoria` permanece como campo de esa tabla; no se crea una tabla duplicada de respuestas ni un catálogo de categorías aparte. `informacion_institucional` almacena contenido institucional general que no es una FAQ. Cada llamada a `/api/v1/chat` registra una interacción anónima para métricas, sin pedir cuenta al visitante.

## Límites de esta fase

Gemini se usa como asistente de importación del panel y como redactor acotado para el chat público. MySQL sigue siendo la fuente institucional; Gemini no puede contestar sin fuentes relevantes recuperadas de la base. Los PDF se publican únicamente cuando su información institucional está activa. La detección actual por cámara se ejecuta en el kiosko web; la integración de cámara dentro de Unity se desarrollará por separado.

# API REST Lobo UPVT

Base URL: `http://127.0.0.1:8000`. JSON utiliza nombres `snake_case`, salvo `consultaId` para conservar compatibilidad con el cliente Unity existente. Errores estándar: `{"detail":"..."}`. Paginación/listas limitadas mediante `limite` donde se indica.

## Kiosco público

Estas rutas no requieren registro ni bearer token.

| Método y ruta | Parámetros/entrada | Respuesta |
| --- | --- | --- |
| `GET /api/v1/informacion` | `q` opcional | `200`: lista de información institucional activa. |
| `GET /api/v1/preguntas` | `q` opcional | `200`: preguntas FAQ activas dirigidas a `todos`. |
| `GET /api/v1/documentos?q=...` | consulta de 2 a 100 caracteres | Devuelve únicamente documentos que coinciden con la consulta; no ofrece un listado general. El kiosko normalmente obtiene el PDF relevante como cita de `POST /chat`. |
| `GET /api/v1/documentos/{id}/archivo` | ninguno | PDF inline; solo si el documento y su información están activos. |
| `POST /api/v1/chat` | `{"mensaje":"¿Cuándo son las inscripciones?","request_id":"uuid-opcional"}` | `200`: respuesta, animación, emoción, `accion_avatar` y `consultaId`; también incluye `mapaUrl` o `videoUrl` cuando la fuente seleccionada tenga un enlace validado de Google Maps o YouTube. Registra la interacción y hace idempotente el reintento con el mismo `request_id` (migración 017). |
| `POST /api/v1/contacto` | `nombre`, `correo`, `asunto`, `mensaje` | Guarda en MySQL un mensaje enviado desde el formulario público del kiosko. El panel separa mensajes pendientes e historial respondido; al completar una respuesta SMTP, el mensaje queda marcado como leído y respondido (migración 016). |
| `POST /api/v1/voz/transcribir` | Cuerpo WAV (`audio/wav`), máximo 1 MB | `200`: `{"transcripcion":"..."}` en español; el audio temporal se elimina del servicio de archivos de Gemini después del proceso. |
| `POST /api/v1/voz/sintetizar` | `{"texto":"..."}`, máximo 2000 caracteres | `200`: audio WAV para reproducir en Unity; no se almacena en el servidor. |
| `GET /health` | ninguno | `200`: API y MySQL operativos; `503` si la base no responde. |

`POST /api/v1/chat` busca primero fuentes relevantes publicadas en MySQL. Los saludos y órdenes breves del avatar se resuelven en el backend y también se registran. Si hay una `GEMINI_API_KEY`, envía la pregunta y solo esas fuentes a Gemini para redactar una respuesta en español; se usa `store=false` y un tiempo de espera de hasta 1.5 segundos. Si no hay fuentes, no se llama al modelo. Si Gemini no está configurado o falla, se devuelve la respuesta almacenada más relevante. Cada consulta y respuesta se registra anónimamente, incluyendo la FAQ relacionada cuando se encontró una. No requiere `usuario_id`. No enviar datos personales en las preguntas.

### Cliente Unity

El proyecto `UPVT_Lobo` agrega el GLB articulado desde `Assets/Resources`, y al iniciar la escena instala la interfaz de consulta, el cliente de esta API y el controlador de animaciones. El endpoint predeterminado es `http://127.0.0.1:8000`; se puede cambiar en el proceso Unity mediante `LOBO_API_BASE_URL` (en despliegue, usar la URL HTTPS del backend). La importación del GLB está configurada en modo de animación Legacy para conservar los clips `Idle`, `Hablar`, `Pensar`, `Saludo` y `Celebrar`.

## Autenticación del panel web

| Método y ruta | Entrada | Acceso y respuesta |
| --- | --- | --- |
| `POST /api/v1/auth/register` | `nombre`, `correo`, `contrasena`, `rol`; `clave_autorizacion` para registro ordinario o `clave_relevo` para emergencia | Nombre de letras, espacios, guiones o apóstrofos; contraseña segura de 12 caracteres o más. El registro ordinario queda pendiente (`202`). La clave de relevo solo se acepta si el principal configurado no está activo y aprobado; se consume una vez, aprueba y designa al nuevo principal, actualizando `PRINCIPAL_ADMIN_EMAIL`. Requiere migración 014. |
| `POST /api/v1/auth/login` | `{"correo":"admin@upvt.edu.mx","contrasena":"..."}` | `200` devuelve `access_token`, `token_type` y `expires_in`; `401` credenciales incorrectas. Solo administradores activos aprobados inician sesión. |
| `POST /api/v1/auth/forgot-password` | `{"correo":"admin@upvt.edu.mx"}` | `202` muestra una respuesta genérica; si el correo pertenece a una cuenta administrativa activa y aprobada, envía un código de seis dígitos válido por 10 minutos. Requiere SMTP configurado y migración 011. |
| `POST /api/v1/auth/reset-password` | `correo`, `codigo`, `contrasena_nueva` | Verifica el código de un solo uso, permite hasta cinco intentos y actualiza el hash de contraseña. La contraseña nueva debe cumplir los requisitos de seguridad. |
| `GET /api/v1/auth/me` | ninguno | Bearer token; `200` perfil actual e indicador `es_admin_principal`. |
| `PATCH /api/v1/auth/me` | `nombre` y, opcionalmente, `contrasena_actual` + `contrasena_nueva` | Bearer de administrador general o de contenido; actualiza el perfil y requiere validar la contraseña actual para cambiarla. |

Las rutas `/api/v1/admin/*` requieren `Authorization: Bearer <access_token>`. El rol `admin_contenido` puede administrar preguntas, información institucional y documentos; consultar historial y métricas; y atender mensajes de contacto (leer, marcar como leído y responder). No puede gestionar usuarios, solicitudes, respaldos, borrar mensajes ni marcar mensajes como nuevos. La depuración del historial y las demás funciones generales quedan reservadas al rol `admin`. Aprobación de solicitudes y cambios de estado de cuentas requieren administrador principal. El token expira según `ACCESS_TOKEN_MINUTES` y se firma con `ADMIN_TOKEN_SECRET`.

## Administración

| Método y ruta | Entrada/parámetros | Descripción |
| --- | --- | --- |
| `GET /api/v1/admin/dashboard` | Bearer | Administrador general: resumen completo. Administrador de contenido: respuestas activas, consultas totales y preguntas más consultadas. |
| `GET /api/v1/admin/metricas?dias=30` | `dias`: 1–365 | Administrador general o de contenido: total de atenciones y serie diaria. |
| `GET /api/v1/admin/usuarios?estado=pendiente&limite=100` | filtros opcionales | Usuarios y estados de solicitud. |
| `GET /api/v1/admin/solicitudes` | Bearer | Solicitudes pendientes. |
| `GET /api/v1/admin/mensajes-contacto` | Bearer de administrador general o de contenido | Lista hasta 500 mensajes recientes enviados desde el kiosko. |
| `PATCH /api/v1/admin/mensajes-contacto/{id}/leido` | `{"leido":true}` | Admin general puede marcar leído/nuevo; administrador de contenido solo puede marcar leído. |
| `GET /api/v1/admin/mensajes-contacto/eventos` | Bearer de administrador general o de contenido | Notificaciones en tiempo real de nuevos mensajes. |
| `POST /api/v1/admin/mensajes-contacto/{id}/responder` | Mensaje y adjuntos opcionales | Envía respuesta por correo y marca leído/respondido. Disponible para ambos roles administrativos. |
| `POST /api/v1/admin/mensajes-contacto/{id}/papelera` | ninguno | Retira el mensaje durante 30 días; luego se elimina automáticamente. |
| `POST /api/v1/admin/mensajes-contacto/{id}/restaurar` | ninguno | Restaura el mensaje desde la papelera. |
| `PUT /api/v1/admin/solicitudes/{id}` | `{"decision":"aprobar"}` o `{"decision":"rechazar"}` | Solo administrador principal; actualiza estado; `404` si no hay solicitud pendiente. |
| `PATCH /api/v1/admin/usuarios/{id}/estado` | `{"activo":true}` | Solo administrador principal; activa/desactiva usuario. |
| `PATCH /api/v1/admin/usuarios/{id}/rol` | `{"rol":"admin_contenido"}` | Solo administrador principal; asigna rol y protege al único administrador activo. |
| `POST /api/v1/admin/usuarios/{id}/papelera` | Bearer de administrador principal | Bloquea la cuenta y la conserva durante 30 días; protege la cuenta principal, la sesión actual y al último administrador general activo. |
| `POST /api/v1/admin/usuarios/{id}/restaurar` | Bearer de administrador principal | Restaura la cuenta con su estado de acceso previo. |
| `GET /api/v1/admin/preguntas?q=...` | búsqueda opcional | Lista FAQs, incluidas archivadas. |
| `GET /api/v1/admin/preguntas/paginadas?q=...&categoria=...&pagina=1&por_pagina=25` | filtros y paginación | Devuelve elementos, total, páginas y categorías disponibles. |
| `GET /api/v1/admin/categorias` | Bearer | Categorías existentes deduplicadas desde FAQs. |
| `POST /api/v1/admin/avatar/accion/generar` | Bearer; `tipo`, `titulo`, `categoria`, `contenido`, palabras clave opcionales y nombres de adjuntos | Gemini propone descripción y clip compatible; no crea ni modifica registros. |
| `POST /api/v1/admin/preguntas` | categoría, pregunta, respuesta, palabras_clave, dirigido_a, accion_avatar, activo | `201` FAQ creada. |
| `PUT /api/v1/admin/preguntas/{id}` | mismos campos que POST | `200` FAQ actualizada; `404` si no existe. |
| `DELETE /api/v1/admin/preguntas/{id}` | Bearer | Archiva sin borrar historial; `204`. |
| `GET /api/v1/admin/informacion` | Bearer | Información institucional, activa y archivada. |
| `POST /api/v1/admin/informacion/analizar` | Bearer; `nombre_archivo`, contenido de archivo y `contenido_publico_confirmado: true` | Analiza el documento con Gemini y devuelve borradores con categoría y animación sin guardar datos ni archivos. PDF máximo 10 MB; TXT/MD máximo 2 MB. |
| `POST /api/v1/admin/informacion/importar` | Bearer; `nombre_archivo`, contenido de archivo y `contenido_publico_confirmado: true` | Ruta de importación anterior que conserva la fuente completa para consultas y prepara borradores opcionales. PDF máximo 10 MB; TXT/MD máximo 2 MB. |
| `POST /api/v1/admin/informacion/con-documento` | Bearer; JSON de información y hasta 20 adjuntos opcionales (`archivos_nombres` + `archivos_base64`) | Crea contenido escrito manualmente y adjunta PDFs o imágenes (máximo 10 MB por archivo y 20 MB en total por ficha); los PDF se indexan para consultas. Se conserva el formato escalar anterior por compatibilidad. |
| `DELETE /api/v1/admin/documentos/{id}` | Bearer | Archiva el adjunto sin borrar su archivo. |
| `POST /api/v1/admin/informacion` | clave, titulo, contenido, categoria, activo | `201` registro creado. |
| `PUT /api/v1/admin/informacion/{id}` | mismos campos que POST | Actualiza registro; `404` si no existe. |
| `DELETE /api/v1/admin/informacion/{id}` | Bearer | Archiva sin borrar; `204`. |
| `GET /api/v1/admin/papelera` | Bearer | Lista preguntas, información, documentos y mensajes; también usuarios para la cuenta de administrador principal. |
| `GET /api/v1/admin/historial?limite=100` | 1–500 | Historial reciente del kiosco. |
| `GET /api/v1/admin/historial?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` | Fechas opcionales | Administrador general o de contenido; filtra consultas del kiosko por intervalo. |
| `DELETE /api/v1/admin/historial?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` | Ambas fechas obligatorias | Solo administrador general; borra las consultas del intervalo elegido. |

Respuestas comunes: `401` sin token válido, `403` clave de registro inválida, `404` recurso ausente, `409` correo duplicado, `422` entrada que no cumple el esquema y `503` servicio/base no disponible.

La importación y el chat requieren `GEMINI_API_KEY` y pueden usar `GEMINI_MODEL` en `backend/.env`. Para importación, solo usar información institucional pública. El texto extraído se envía a Gemini; los archivos originales y borradores no se guardan hasta que el administrador confirma cada ficha. En el chat se envían la pregunta pública y las fuentes relevantes recuperadas de MySQL. La clave se mantiene en el backend y no se entrega al navegador. Los PDF públicos no se envían a Gemini al adjuntarlos.

Los PDFs adjuntos a información institucional o preguntas frecuentes se analizan en segundo plano con Gemini, incluyendo como contexto el título/categoría o pregunta asociada. El resultado indexado incluye palabras clave respaldadas por el PDF y su ficha; el chat puede recuperar el adjunto por ellas aunque la pregunta del registro use otra redacción. Las palabras clave apoyan la búsqueda, pero no se devuelven como contenido de respuesta. Si Gemini no está disponible, se conserva el texto nativo extraído y la búsqueda sigue funcionando sobre ese contenido. Para reanalizar un PDF previo con su ficha asociada, ejecuta desde `backend` `python cli.py analyze-document ID` con el ID del documento. No hay cambios de esquema ni se modifica el archivo original.

La voz del kiosko también requiere `GEMINI_API_KEY`. Unity graba hasta 12 segundos, envía el WAV a FastAPI para transcripción (`GEMINI_TRANSCRIBE_MODEL`) y muestra el texto para revisión antes de consultar. La respuesta se sintetiza con `GEMINI_TTS_MODEL` y `GEMINI_TTS_VOICE` (por defecto, `es-419-concierge-8`, voz masculina mexicana de guía, cálida y conversacional); si la voz falla, el texto sigue disponible. La grabación solo se conserva en un archivo temporal durante la transcripción, se solicita eliminar el archivo cargado a Gemini y no se guarda audio en MySQL. El audio se procesa mediante Gemini; evita dictar datos personales o confidenciales.

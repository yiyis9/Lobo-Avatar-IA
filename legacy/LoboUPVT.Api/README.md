# Lobo UPVT API y panel

Servicio ASP.NET Core 9 para el panel administrativo y el kiosco Unity. La API usa el esquema `lobo_upvt_db` del archivo `lobo_upvt_db.sql`.

## Configuración

Configura estas variables de entorno antes de ejecutar:

- `ConnectionStrings__LoboUpvt`: conexión MySQL.
- `Admin__ApiKey`: secreto aleatorio largo para proteger `/api/v1/admin/*`.
- `Registration__AuthorizationKey`: clave que se distribuye a usuarios para solicitar una cuenta.
- `Admin__BootstrapKey`: secreto temporal para activar la cuenta administradora de semilla.
- `Cors__Origins__0`: origen autorizado del panel, por ejemplo `http://localhost:5000`; añade índices si hay más orígenes.
- `ASPNETCORE_URLS`: dirección de escucha; por ejemplo `http://0.0.0.0:5000` para el kiosco de la red local.

El SQL incluye `admin@upvt.edu.mx` con un hash marcador que no permite iniciar sesión. Tras aplicar el SQL y configurar `Admin__BootstrapKey`, envía una sola vez `POST /api/v1/setup/admin` con `{"correo":"admin@upvt.edu.mx","contrasena":"<secreto de al menos 10 caracteres>","claveConfiguracion":"<Admin__BootstrapKey>"}`. El servicio genera el hash PBKDF2-SHA256 y activa la cuenta; después elimina `Admin__BootstrapKey` de la configuración. No hay contraseña por defecto.

Aplica el SQL actualizado y ejecuta desde esta carpeta con `dotnet run`. El panel está en `/`. En producción, usa HTTPS y limita CORS a los orígenes del kiosco y del panel.

## Rutas

| Método | Ruta | Acceso |
| --- | --- | --- |
| POST | `/api/v1/chat` | Unity |
| POST | `/api/v1/registro` | Público, requiere clave de autorización |
| POST | `/api/v1/setup/admin` | Configuración inicial protegida con clave temporal |
| GET | `/api/v1/health` | Estado de API y MySQL |
| POST | `/api/v1/admin/login` | Validación de administrador |
| GET | `/api/v1/admin/dashboard` | Administrador |
| GET | `/api/v1/admin/metricas?dias=30` | Administrador |
| GET, POST, PUT, DELETE | `/api/v1/admin/respuestas` | Administrador |
| GET | `/api/v1/admin/autorizaciones` | Administrador |
| POST | `/api/v1/admin/autorizaciones/{id}/aprobar` | Administrador |
| POST | `/api/v1/admin/autorizaciones/{id}/rechazar` | Administrador |
| GET, PATCH | `/api/v1/admin/usuarios` | Administrador |

Las rutas bajo `/admin` usan `Authorization: Bearer <Admin__ApiKey>`. El inicio de sesión devuelve ese token para el panel; cambia el secreto periódicamente y no lo distribuyas en el cliente Unity.

### Ejemplo Unity

Solicitud: `{"mensaje":"¿Dónde se ubica la universidad?","usuario_id":null}`

Respuesta: `{"respuesta":"...","animacion":"idle","emocion":"neutral","consultaId":1}`

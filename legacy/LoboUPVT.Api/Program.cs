using System.Security.Cryptography;
using System.Text;
using LoboUPVT.Api;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddSingleton<UpvtRepository>();
var allowedOrigins = builder.Configuration.GetSection("Cors:Origins").Get<string[]>() ?? ["http://localhost:5000"];
builder.Services.AddCors(options => options.AddDefaultPolicy(policy =>
    policy.WithOrigins(allowedOrigins).AllowAnyHeader().AllowAnyMethod()));
var app = builder.Build();
app.UseCors();
app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/api/v1/health", async (UpvtRepository db) => Results.Ok(new { status = "ok", database = await db.IsAvailableAsync() ? "connected" : "unavailable" }));

app.MapPost("/api/v1/chat", async (ChatRequest request, UpvtRepository db) =>
{
    if (string.IsNullOrWhiteSpace(request.Mensaje) || request.Mensaje.Length > 1000)
        return Results.BadRequest(new { error = "Escribe una pregunta de hasta 1000 caracteres." });
    var answer = await db.FindAnswerAsync(request.Mensaje, request.UsuarioId);
    return Results.Ok(answer);
});

app.MapPost("/api/v1/registro", async (RegistrationRequest request, UpvtRepository db, IConfiguration config) =>
{
    if (string.IsNullOrWhiteSpace(request.Nombre) || string.IsNullOrWhiteSpace(request.Correo) || request.Contrasena.Length < 10)
        return Results.BadRequest(new { error = "Nombre y correo son obligatorios; la contraseña requiere al menos 10 caracteres." });
    var expectedKey = config["Registration:AuthorizationKey"];
    if (string.IsNullOrWhiteSpace(expectedKey) || !CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(request.ClaveAutorizacion ?? ""), Encoding.UTF8.GetBytes(expectedKey)))
        return Results.BadRequest(new { error = "La clave de autorización no es válida." });
    try { await db.RegisterAsync(request); }
    catch (MySqlConnector.MySqlException ex) when (ex.Number == 1062) { return Results.Conflict(new { error = "Ya existe una cuenta con ese correo." }); }
    return Results.Accepted("/api/v1/admin/autorizaciones", new { status = "pending", mensaje = "Solicitud enviada para autorización." });
});

app.MapPost("/api/v1/setup/admin", async (BootstrapAdminRequest request, UpvtRepository db, IConfiguration config) =>
{
    var expectedKey = config["Admin:BootstrapKey"];
    if (string.IsNullOrWhiteSpace(expectedKey) || !CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(request.ClaveConfiguracion ?? ""), Encoding.UTF8.GetBytes(expectedKey))) return Results.Unauthorized();
    if (request.Contrasena.Length < 10) return Results.BadRequest(new { error = "La contraseña requiere al menos 10 caracteres." });
    return await db.ProvisionSeedAdminAsync(request.Correo, request.Contrasena)
        ? Results.Ok(new { mensaje = "Administrador inicial configurado. Elimine Admin:BootstrapKey de la configuración." })
        : Results.Conflict(new { error = "No se encontró la cuenta de semilla pendiente o ya fue configurada." });
});

app.MapPost("/api/v1/admin/login", async (LoginRequest request, UpvtRepository db, IConfiguration config) =>
{
    var user = await db.ValidateAdminAsync(request.Correo, request.Contrasena);
    if (user is null) return Results.Unauthorized();
    var key = config["Admin:ApiKey"];
    if (string.IsNullOrWhiteSpace(key)) return Results.Problem("Configure Admin:ApiKey en variables de entorno antes de iniciar el panel.", statusCode: 503);
    return Results.Ok(new { token = key, user });
});

var admin = app.MapGroup("/api/v1/admin").AddEndpointFilter(async (context, next) =>
{
    var config = context.HttpContext.RequestServices.GetRequiredService<IConfiguration>();
    var expected = config["Admin:ApiKey"];
    var supplied = context.HttpContext.Request.Headers.Authorization.ToString();
    if (string.IsNullOrWhiteSpace(expected) || !CryptographicOperations.FixedTimeEquals(Encoding.UTF8.GetBytes(supplied), Encoding.UTF8.GetBytes($"Bearer {expected}")))
        return Results.Unauthorized();
    return await next(context);
});

admin.MapGet("/dashboard", async (UpvtRepository db) => Results.Ok(await db.GetDashboardAsync()));
admin.MapGet("/metricas", async (UpvtRepository db, int dias = 30) => Results.Ok(await db.GetMetricsAsync(Math.Clamp(dias, 1, 365))));
admin.MapGet("/autorizaciones", async (UpvtRepository db) => Results.Ok(await db.GetPendingUsersAsync()));
admin.MapPost("/autorizaciones/{id:int}/aprobar", async (int id, UpvtRepository db) => await db.ApproveUserAsync(id) ? Results.NoContent() : Results.NotFound());
admin.MapPost("/autorizaciones/{id:int}/rechazar", async (int id, UpvtRepository db) => await db.RejectUserAsync(id) ? Results.NoContent() : Results.NotFound());
admin.MapGet("/usuarios", async (UpvtRepository db) => Results.Ok(await db.GetUsersAsync()));
admin.MapPatch("/usuarios/{id:int}/estado", async (int id, UserStatusRequest request, UpvtRepository db) => await db.SetUserStatusAsync(id, request.Activo) ? Results.NoContent() : Results.NotFound());
admin.MapGet("/respuestas", async (UpvtRepository db) => Results.Ok(await db.GetAnswersAsync()));
admin.MapPost("/respuestas", async (FaqRequest request, UpvtRepository db) => Results.Created("/api/v1/admin/respuestas", await db.SaveAnswerAsync(request)));
admin.MapPut("/respuestas/{id:int}", async (int id, FaqRequest request, UpvtRepository db) => await db.SaveAnswerAsync(request, id) is { } item ? Results.Ok(item) : Results.NotFound());
admin.MapDelete("/respuestas/{id:int}", async (int id, UpvtRepository db) => await db.DeleteAnswerAsync(id) ? Results.NoContent() : Results.NotFound());
admin.MapGet("/perfil", (HttpContext context) => Results.Ok(new { api = "Lobo UPVT", role = "admin" }));

app.Run();

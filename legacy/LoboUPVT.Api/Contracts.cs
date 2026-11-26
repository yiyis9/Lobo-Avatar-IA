using System.Text.Json.Serialization;

namespace LoboUPVT.Api;

public sealed record ChatRequest([property: JsonPropertyName("mensaje")] string Mensaje, [property: JsonPropertyName("usuario_id")] int? UsuarioId = null);
public sealed record ChatResponse(string Respuesta, string Animacion, string Emocion, int? ConsultaId = null);
public sealed record RegistrationRequest(string Nombre, string Correo, string Contrasena, string? ClaveAutorizacion);
public sealed record BootstrapAdminRequest(string Correo, string Contrasena, string? ClaveConfiguracion);
public sealed record LoginRequest(string Correo, string Contrasena);
public sealed record UserStatusRequest(bool Activo);
public sealed record FaqRequest(string Categoria, string Pregunta, string Respuesta, string? PalabrasClave = null, string DirigidoA = "todos", string Animacion = "idle", string Emocion = "neutral");
public sealed record UserDto(int Id, string Nombre, string Correo, string Rol, string? Departamento, bool Activo, DateTime CreadoEn);
public sealed record FaqDto(int Id, string Categoria, string Pregunta, string Respuesta, string? PalabrasClave, string DirigidoA, string Animacion, string Emocion, bool Activo);
public sealed record DashboardDto(int RespuestasRegistradas, int AlumnosAtendidos, int SolicitudesPendientes, int ConsultasHoy, bool ServidorConectado, IReadOnlyList<FrequentQuestionDto> PreguntasFrecuentes);
public sealed record FrequentQuestionDto(string Pregunta, int Consultas);

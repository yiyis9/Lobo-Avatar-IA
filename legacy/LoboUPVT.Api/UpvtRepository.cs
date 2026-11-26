using System.Security.Cryptography;
using System.Text;
using MySqlConnector;

namespace LoboUPVT.Api;

public sealed class UpvtRepository(IConfiguration configuration)
{
    private string ConnectionString => configuration.GetConnectionString("LoboUpvt")
        ?? Environment.GetEnvironmentVariable("LOBOUPVT_DB")
        ?? "Server=localhost;Port=3306;Database=lobo_upvt_db;User ID=root;Password=;Character Set=utf8mb4;";

    private MySqlConnection Connect() => new(ConnectionString);

    public async Task<bool> IsAvailableAsync()
    {
        try { await using var c = Connect(); await c.OpenAsync(); return true; }
        catch (MySqlException) { return false; }
    }

    public async Task<ChatResponse> FindAnswerAsync(string message, int? userId)
    {
        const string sql = "SELECT id,respuesta,animacion,emocion FROM preguntas_frecuentes WHERE activo=1 AND (pregunta LIKE @q OR palabras_clave LIKE @q OR categoria LIKE @q) ORDER BY CASE WHEN pregunta LIKE @exact THEN 0 ELSE 1 END,id LIMIT 1";
        await using var c = Connect(); await c.OpenAsync();
        await using var cmd = new MySqlCommand(sql, c);
        cmd.Parameters.AddWithValue("@q", $"%{message.Trim()}%"); cmd.Parameters.AddWithValue("@exact", $"%{message.Trim()}%");
        string response = "No encontré una respuesta. Puedes reformular la pregunta o contactar a Servicios Escolares.";
        string animation = "thinking", emotion = "duda"; int? faqId = null;
        await using (var r = await cmd.ExecuteReaderAsync())
            if (await r.ReadAsync()) { faqId = r.GetInt32("id"); response = r.GetString("respuesta"); animation = r.GetString("animacion"); emotion = r.GetString("emocion"); }
        await using var log = new MySqlCommand("INSERT INTO historial_consultas(usuario_id,pregunta_usuario,respuesta_bot,origen,pregunta_frecuente_id) VALUES(@uid,@q,@a,'kiosko_kinect',@faq)", c);
        log.Parameters.AddWithValue("@uid", (object?)userId ?? DBNull.Value); log.Parameters.AddWithValue("@q", message.Trim()); log.Parameters.AddWithValue("@a", response); log.Parameters.AddWithValue("@faq", (object?)faqId ?? DBNull.Value);
        await log.ExecuteNonQueryAsync();
        return new ChatResponse(response, animation, emotion, (int)log.LastInsertedId);
    }

    public async Task RegisterAsync(RegistrationRequest request)
    {
        await using var c = Connect(); await c.OpenAsync();
        await using var cmd = new MySqlCommand("INSERT INTO usuarios(nombre,email,password_hash,rol,activo,estado_solicitud) VALUES(@n,@e,@p,'alumno',0,'pendiente')", c);
        cmd.Parameters.AddWithValue("@n", request.Nombre.Trim()); cmd.Parameters.AddWithValue("@e", request.Correo.Trim().ToLowerInvariant()); cmd.Parameters.AddWithValue("@p", HashPassword(request.Contrasena)); await cmd.ExecuteNonQueryAsync();
    }

    public async Task<bool> ProvisionSeedAdminAsync(string email, string password)
    {
        await using var c = Connect(); await c.OpenAsync();
        await using var cmd = new MySqlCommand("UPDATE usuarios SET password_hash=@p,activo=1,estado_solicitud='aprobada' WHERE email=@e AND rol='admin' AND password_hash='hash_secret_admin'", c);
        cmd.Parameters.AddWithValue("@p", HashPassword(password)); cmd.Parameters.AddWithValue("@e", email.Trim().ToLowerInvariant()); return await cmd.ExecuteNonQueryAsync() == 1;
    }

    public async Task<UserDto?> ValidateAdminAsync(string email, string password)
    {
        await using var c = Connect(); await c.OpenAsync();
        await using var cmd = new MySqlCommand("SELECT id,nombre,email,rol,carrera,activo,creado_en,password_hash FROM usuarios WHERE email=@e AND activo=1 LIMIT 1", c);
        cmd.Parameters.AddWithValue("@e", email.Trim().ToLowerInvariant()); await using var r = await cmd.ExecuteReaderAsync();
        if (!await r.ReadAsync() || r.GetString("rol") != "admin" || !VerifyPassword(password, r.GetString("password_hash"))) return null;
        return ReadUser(r);
    }

    public async Task<DashboardDto> GetDashboardAsync()
    {
        await using var c = Connect(); await c.OpenAsync();
        var answers = await Scalar(c, "SELECT COUNT(*) FROM preguntas_frecuentes WHERE activo=1");
        var users = await Scalar(c, "SELECT COUNT(DISTINCT usuario_id) FROM historial_consultas WHERE usuario_id IS NOT NULL");
        var pending = await Scalar(c, "SELECT COUNT(*) FROM usuarios WHERE estado_solicitud='pendiente'");
        var today = await Scalar(c, "SELECT COUNT(*) FROM historial_consultas WHERE fecha_consulta >= CURRENT_DATE()");
        var popular = new List<FrequentQuestionDto>();
        await using var cmd = new MySqlCommand("SELECT pf.pregunta,COUNT(h.id) consultas FROM preguntas_frecuentes pf LEFT JOIN historial_consultas h ON h.pregunta_frecuente_id=pf.id GROUP BY pf.id,pf.pregunta ORDER BY consultas DESC LIMIT 5", c);
        await using var r = await cmd.ExecuteReaderAsync(); while (await r.ReadAsync()) popular.Add(new(r.GetString("pregunta"), r.GetInt32("consultas")));
        return new((int)answers, (int)users, (int)pending, (int)today, true, popular);
    }

    public async Task<object> GetMetricsAsync(int days)
    {
        await using var c = Connect(); await c.OpenAsync();
        await using var cmd = new MySqlCommand("SELECT DATE(fecha_consulta) fecha,COUNT(*) consultas,COUNT(DISTINCT usuario_id) usuarios FROM historial_consultas WHERE fecha_consulta >= DATE_SUB(CURRENT_DATE(),INTERVAL @days DAY) GROUP BY DATE(fecha_consulta) ORDER BY fecha", c);
        cmd.Parameters.AddWithValue("@days", days); var rows = new List<object>(); await using var r = await cmd.ExecuteReaderAsync();
        while (await r.ReadAsync()) rows.Add(new { fecha = r.GetDateTime("fecha"), consultas = r.GetInt32("consultas"), usuarios = r.GetInt32("usuarios") });
        return new { dias = days, series = rows };
    }

    public Task<List<UserDto>> GetPendingUsersAsync() => GetUsersAsync("estado_solicitud='pendiente'");
    public Task<List<UserDto>> GetUsersAsync(string? where = null) => ReadUsersAsync(where);

    private async Task<List<UserDto>> ReadUsersAsync(string? where)
    {
        await using var c = Connect(); await c.OpenAsync();
        var sql = "SELECT id,nombre,email,rol,carrera,activo,creado_en FROM usuarios" + (where is null ? "" : " WHERE " + where) + " ORDER BY creado_en DESC LIMIT 500";
        await using var cmd = new MySqlCommand(sql, c); await using var r = await cmd.ExecuteReaderAsync(); var list = new List<UserDto>();
        while (await r.ReadAsync()) list.Add(ReadUser(r)); return list;
    }

    public async Task<bool> ApproveUserAsync(int id)
    {
        await using var c = Connect(); await c.OpenAsync(); await using var cmd = new MySqlCommand("UPDATE usuarios SET activo=1,estado_solicitud='aprobada' WHERE id=@id AND estado_solicitud='pendiente'", c); cmd.Parameters.AddWithValue("@id", id); return await cmd.ExecuteNonQueryAsync() > 0;
    }

    public async Task<bool> RejectUserAsync(int id)
    {
        await using var c = Connect(); await c.OpenAsync(); await using var cmd = new MySqlCommand("UPDATE usuarios SET activo=0,estado_solicitud='rechazada' WHERE id=@id AND estado_solicitud='pendiente'", c); cmd.Parameters.AddWithValue("@id", id); return await cmd.ExecuteNonQueryAsync() > 0;
    }

    public async Task<bool> SetUserStatusAsync(int id, bool active)
    {
        await using var c = Connect(); await c.OpenAsync(); await using var cmd = new MySqlCommand("UPDATE usuarios SET activo=@active WHERE id=@id", c); cmd.Parameters.AddWithValue("@active", active); cmd.Parameters.AddWithValue("@id", id); return await cmd.ExecuteNonQueryAsync() > 0;
    }

    public async Task<List<FaqDto>> GetAnswersAsync()
    {
        await using var c = Connect(); await c.OpenAsync(); await using var cmd = new MySqlCommand("SELECT id,categoria,pregunta,respuesta,palabras_clave,dirigido_a,animacion,emocion,activo FROM preguntas_frecuentes ORDER BY id DESC LIMIT 500", c);
        await using var r = await cmd.ExecuteReaderAsync(); var list = new List<FaqDto>(); while (await r.ReadAsync()) list.Add(ReadFaq(r)); return list;
    }

    public async Task<FaqDto?> SaveAnswerAsync(FaqRequest item, int? id = null)
    {
        await using var c = Connect(); await c.OpenAsync();
        var sql = id is null ? "INSERT INTO preguntas_frecuentes(categoria,pregunta,respuesta,palabras_clave,dirigido_a,animacion,emocion) VALUES(@cat,@q,@a,@keys,@to,@anim,@emo)" : "UPDATE preguntas_frecuentes SET categoria=@cat,pregunta=@q,respuesta=@a,palabras_clave=@keys,dirigido_a=@to,animacion=@anim,emocion=@emo WHERE id=@id";
        await using var cmd = new MySqlCommand(sql, c); BindFaq(cmd, item); if (id.HasValue) cmd.Parameters.AddWithValue("@id", id); await cmd.ExecuteNonQueryAsync();
        var saved = id ?? (int)cmd.LastInsertedId; await using var read = new MySqlCommand("SELECT id,categoria,pregunta,respuesta,palabras_clave,dirigido_a,animacion,emocion,activo FROM preguntas_frecuentes WHERE id=@id", c); read.Parameters.AddWithValue("@id", saved); await using var r = await read.ExecuteReaderAsync(); return await r.ReadAsync() ? ReadFaq(r) : null;
    }

    public async Task<bool> DeleteAnswerAsync(int id)
    {
        await using var c = Connect(); await c.OpenAsync(); await using var cmd = new MySqlCommand("UPDATE preguntas_frecuentes SET activo=0 WHERE id=@id AND activo=1", c); cmd.Parameters.AddWithValue("@id", id); return await cmd.ExecuteNonQueryAsync() > 0;
    }

    private static async Task<long> Scalar(MySqlConnection c, string sql) { await using var cmd = new MySqlCommand(sql, c); return Convert.ToInt64(await cmd.ExecuteScalarAsync()); }
    private static UserDto ReadUser(MySqlDataReader r) => new(r.GetInt32("id"), r.GetString("nombre"), r.GetString("email"), r.GetString("rol"), r.IsDBNull(r.GetOrdinal("carrera")) ? null : r.GetString("carrera"), r.GetBoolean("activo"), r.GetDateTime("creado_en"));
    private static FaqDto ReadFaq(MySqlDataReader r) => new(r.GetInt32("id"), r.GetString("categoria"), r.GetString("pregunta"), r.GetString("respuesta"), r.IsDBNull(r.GetOrdinal("palabras_clave")) ? null : r.GetString("palabras_clave"), r.GetString("dirigido_a"), r.GetString("animacion"), r.GetString("emocion"), r.GetBoolean("activo"));
    private static void BindFaq(MySqlCommand c, FaqRequest f) { c.Parameters.AddWithValue("@cat", f.Categoria.Trim()); c.Parameters.AddWithValue("@q", f.Pregunta.Trim()); c.Parameters.AddWithValue("@a", f.Respuesta.Trim()); c.Parameters.AddWithValue("@keys", (object?)f.PalabrasClave ?? DBNull.Value); c.Parameters.AddWithValue("@to", f.DirigidoA); c.Parameters.AddWithValue("@anim", f.Animacion); c.Parameters.AddWithValue("@emo", f.Emocion); }
    private static string HashPassword(string value) { var salt = RandomNumberGenerator.GetBytes(16); var hash = Rfc2898DeriveBytes.Pbkdf2(value, salt, 210_000, HashAlgorithmName.SHA256, 32); return $"pbkdf2-sha256${Convert.ToBase64String(salt)}${Convert.ToBase64String(hash)}"; }
    private static bool VerifyPassword(string value, string encoded) { try { var parts = encoded.Split('$'); if (parts.Length != 3 || parts[0] != "pbkdf2-sha256") return false; var hash = Rfc2898DeriveBytes.Pbkdf2(value, Convert.FromBase64String(parts[1]), 210_000, HashAlgorithmName.SHA256, 32); return CryptographicOperations.FixedTimeEquals(hash, Convert.FromBase64String(parts[2])); } catch (FormatException) { return false; } }
}

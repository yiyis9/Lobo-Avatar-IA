<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ExampleTest extends TestCase
{
    public function test_admin_access_login_and_registration_pages_are_exposed(): void
    {
        $this->assertFalse(config('services.fastapi.demo_access'));
        $this->get('/')->assertRedirect('/acceso');
        $this->get('/acceso')->assertOk()->assertSee('Iniciar sesión')->assertSee('Solicitar registro')->assertDontSee('alumno');
        $this->get('/login')->assertOk()->assertSee('Acceso de administrador')->assertSee('Correo')->assertSee('Regresar')->assertDontSee('demo');
        $this->get('/registro')->assertOk()->assertSee('Solicitar registro')->assertSee('Clave de autorización')->assertSee('Regresar');
    }

    public function test_registration_submits_an_admin_request_to_fastapi(): void
    {
        Http::fake(['*api/v1/auth/register' => Http::response(['id' => 9, 'estado' => 'pendiente'], 202)]);

        $this->post('/registro', [
            'nombre' => 'Admin de prueba',
            'correo' => 'nuevo@example.test',
            'contrasena' => 'Clave-Prueba-2026',
            'contrasena_confirmation' => 'Clave-Prueba-2026',
            'clave_autorizacion' => 'invitacion-valida',
        ])->assertRedirect('/registro')->assertSessionHas('request_sent', true);

        Http::assertSent(fn ($request) => $request->url() === 'http://127.0.0.1:8000/api/v1/auth/register'
            && $request['rol'] === 'admin');
    }

    public function test_private_routes_require_an_admin_session(): void
    {
        $this->get('/dashboard')->assertRedirect('/login');
        $this->get('/preguntas')->assertRedirect('/login');
    }

    public function test_local_demo_login_opens_read_only_prototype_pages(): void
    {
        config(['app.env' => 'local']);
        config(['services.fastapi.demo_access' => true]);
        Http::fake(['*' => Http::response([], 401)]);

        $this->post('/login', ['correo' => 'demo@example.test', 'contrasena' => 'cualquier-clave'])
            ->assertRedirect('/dashboard')
            ->assertSessionHas('demo_admin', true);

        $this->get('/dashboard')->assertOk()->assertSee('Panel administrativo')->assertSee('—')->assertDontSee('demo');
        $this->get('/preguntas')->assertOk()->assertSee('Preguntas y respuestas');
        $this->get('/preguntas/nueva')->assertOk()->assertSee('Registrar nueva respuesta')->assertSee('Edición no disponible');
        $this->get('/solicitudes')->assertOk()->assertSee('Autorizaciones');
        $this->get('/usuarios')->assertOk()->assertSee('Usuarios');
        $this->get('/reportes')->assertOk()->assertSee('Métricas');
        $this->get('/perfil')->assertOk()->assertSee('Perfil');
        $this->get('/configuracion')->assertOk()->assertSee('Sistema');
        $this->get('/mantenimiento')->assertOk()->assertSee('Mantenimiento');
        $this->post('/preguntas', [])->assertForbidden();
    }

    public function test_login_is_delegated_to_fastapi_and_stored_in_session(): void
    {
        Http::fake([
            '*api/v1/auth/login' => Http::response([
                'access_token' => 'test-only-token',
                'token_type' => 'bearer',
                'expires_in' => 1800,
            ], 200),
        ]);

        $this->post('/login', ['correo' => 'admin@upvt.edu.mx', 'contrasena' => 'not-saved'])
            ->assertRedirect('/dashboard')
            ->assertSessionHas('fastapi_token', 'test-only-token');
    }
}

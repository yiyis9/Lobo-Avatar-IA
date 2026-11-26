<?php

namespace Tests\Feature;

use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class PanelViewsTest extends TestCase
{
    protected function setUp(): void
    {
        parent::setUp();
        Http::fake([
            '*api/v1/auth/me' => Http::response([
                'id' => 1,
                'nombre' => 'Administración de prueba',
                'correo' => 'admin@example.test',
                'rol' => 'admin',
                'activo' => true,
                'estado_solicitud' => 'aprobada',
            ]),
            '*api/v1/admin/dashboard' => Http::response([
                'respuestas_registradas' => 6,
                'solicitudes_pendientes' => 0,
                'consultas_hoy' => 0,
                'atenciones_totales' => 1,
                'preguntas_frecuentes' => [],
            ]),
            '*api/v1/admin/usuarios*' => Http::response([]),
            '*api/v1/admin/historial*' => Http::response([]),
            '*api/v1/admin/solicitudes' => Http::response([]),
            '*api/v1/admin/preguntas*' => Http::response([]),
            '*api/v1/admin/categorias' => Http::response([]),
            '*api/v1/admin/metricas*' => Http::response([
                'desde' => '2026-09-01',
                'dias' => 30,
                'atenciones' => 0,
                'series' => [],
            ]),
            '*health' => Http::response(['api' => 'operativa', 'mysql' => 'conectado']),
        ]);
        $this->withSession(['fastapi_token' => 'test-session-token']);
    }

    public function test_dashboard_and_management_views_render(): void
    {
        $this->get('/dashboard')->assertOk()->assertSee('Panel administrativo')->assertSee('Respuestas activas');
        $this->get('/preguntas')->assertOk()->assertSee('Gestor de preguntas');
        $this->get('/preguntas/nueva')->assertOk()->assertSee('Registrar nueva respuesta');
        $this->get('/solicitudes')->assertOk()->assertSee('Solicitudes pendientes');
        $this->get('/usuarios')->assertOk()->assertSee('Usuarios');
    }

    public function test_profile_system_and_reporting_views_render(): void
    {
        $this->get('/perfil')->assertOk()->assertSee('Administración de prueba');
        $this->get('/configuracion')->assertOk()->assertSee('Sistema');
        $this->get('/mantenimiento')->assertOk()->assertSee('Mantenimiento');
        $this->get('/reportes')->assertOk()->assertSee('Reportes y métricas');
    }
}

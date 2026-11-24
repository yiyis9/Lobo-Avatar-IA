<?php

namespace App\Http\Controllers;

use App\Exceptions\FastApiUnavailable;
use App\Services\FastApiClient;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;
use Symfony\Component\HttpFoundation\Response;

class AdminPanelController extends Controller
{
    public function __construct(private readonly FastApiClient $api) {}

    public function dashboard(Request $request): View
    {
        if ((bool) $request->session()->get('demo_admin', false)) {
            return view('admin.dashboard', [
                'summary' => [
                    'respuestas_registradas' => '—',
                    'atenciones_totales' => '—',
                    'solicitudes_pendientes' => '—',
                ],
                'warning' => null,
            ]);
        }

        $warning = null;
        $summary = $this->read('/api/v1/admin/dashboard', $request, $warning);
        $users = $this->read('/api/v1/admin/usuarios?limite=500', $request, $warning);
        $history = $this->read('/api/v1/admin/historial?limite=6', $request, $warning);
        $requests = $this->read('/api/v1/admin/solicitudes', $request, $warning);

        return view('admin.dashboard', [
            'summary' => $summary,
            'userCount' => count($users),
            'history' => $history,
            'requests' => $requests,
            'warning' => $warning,
        ]);
    }

    public function questions(Request $request): View
    {
        $warning = null;
        $items = $this->read('/api/v1/admin/preguntas?q='.rawurlencode((string) $request->query('q', '')), $request, $warning);

        return view('admin.questions.index', ['items' => $items, 'warning' => $warning, 'search' => (string) $request->query('q', '')]);
    }

    public function createQuestion(Request $request): View
    {
        $warning = null;
        $categories = $this->read('/api/v1/admin/categorias', $request, $warning);

        return view('admin.questions.form', ['item' => null, 'categories' => $categories, 'warning' => $warning]);
    }

    public function storeQuestion(Request $request): RedirectResponse
    {
        return $this->saveQuestion($request, '/api/v1/admin/preguntas', 'POST');
    }

    public function editQuestion(int $id, Request $request): View|RedirectResponse
    {
        $warning = null;
        $items = $this->read('/api/v1/admin/preguntas', $request, $warning);
        $item = collect($items)->firstWhere('id', $id);
        if ($item === null) {
            return redirect()->route('admin.questions')->withErrors(['pregunta' => 'No se encontró la pregunta solicitada.']);
        }
        $categories = $this->read('/api/v1/admin/categorias', $request, $warning);

        return view('admin.questions.form', ['item' => $item, 'categories' => $categories, 'warning' => $warning]);
    }

    public function updateQuestion(int $id, Request $request): RedirectResponse
    {
        return $this->saveQuestion($request, "/api/v1/admin/preguntas/{$id}", 'PUT');
    }

    public function archiveQuestion(int $id, Request $request): RedirectResponse
    {
        try {
            $response = $this->api->request('DELETE', "/api/v1/admin/preguntas/{$id}", token: $this->token($request));
        } catch (FastApiUnavailable) {
            return back()->withErrors(['api' => 'FastAPI no está disponible; no se archivó ningún registro.']);
        }

        return $response->successful()
            ? back()->with('status', 'La respuesta se archivó sin borrar su historial.')
            : back()->withErrors(['api' => $response->json('detail', 'No se pudo archivar la respuesta.')]);
    }

    public function requests(Request $request): View
    {
        $warning = null;

        return view('admin.requests', ['items' => $this->read('/api/v1/admin/solicitudes', $request, $warning), 'warning' => $warning]);
    }

    public function decideRequest(int $id, Request $request): RedirectResponse
    {
        $data = $request->validate(['decision' => ['required', 'in:aprobar,rechazar']]);
        try {
            $response = $this->api->request('PUT', "/api/v1/admin/solicitudes/{$id}", $data, $this->token($request));
        } catch (FastApiUnavailable) {
            return back()->withErrors(['api' => 'FastAPI no está disponible; la solicitud no cambió.']);
        }

        return $response->successful()
            ? back()->with('status', $data['decision'] === 'aprobar' ? 'Solicitud aprobada.' : 'Solicitud rechazada.')
            : back()->withErrors(['api' => $response->json('detail', 'No se pudo actualizar la solicitud.')]);
    }

    public function users(Request $request): View
    {
        $warning = null;
        $query = http_build_query(array_filter([
            'estado' => $request->query('estado'),
            'limite' => 500,
        ], fn ($value) => $value !== null && $value !== ''));

        return view('admin.users', [
            'items' => $this->read('/api/v1/admin/usuarios?'.$query, $request, $warning),
            'warning' => $warning,
            'state' => (string) $request->query('estado', ''),
        ]);
    }

    public function setUserState(int $id, Request $request): RedirectResponse
    {
        $data = $request->validate(['activo' => ['required', 'boolean']]);
        try {
            $response = $this->api->request('PATCH', "/api/v1/admin/usuarios/{$id}/estado", $data, $this->token($request));
        } catch (FastApiUnavailable) {
            return back()->withErrors(['api' => 'FastAPI no está disponible; el estado de cuenta no cambió.']);
        }

        return $response->successful()
            ? back()->with('status', 'Estado de la cuenta actualizado.')
            : back()->withErrors(['api' => $response->json('detail', 'No se pudo actualizar el estado.')]);
    }

    public function profile(Request $request): View
    {
        return view('admin.profile', ['admin' => $request->attributes->get('panel_admin', [])]);
    }

    public function settings(): View
    {
        return view('admin.settings');
    }

    public function maintenance(Request $request): View
    {
        $health = null;
        $message = null;
        try {
            $response = $this->api->request('GET', '/health');
            $health = $response->successful() ? $response->json() : null;
            if (! $response->successful()) {
                $message = 'La API respondió con estado HTTP '.$response->status().'.';
            }
        } catch (FastApiUnavailable $exception) {
            $message = $exception->getMessage();
        }

        return view('admin.maintenance', ['health' => $health, 'message' => $message]);
    }

    public function reports(Request $request): View
    {
        $days = max(1, min(365, (int) $request->query('dias', 30)));
        $warning = null;
        $metrics = $this->read("/api/v1/admin/metricas?dias={$days}", $request, $warning);

        return view('admin.reports', ['metrics' => $metrics, 'days' => $days, 'warning' => $warning]);
    }

    public function downloadReport(Request $request): Response|RedirectResponse
    {
        $days = max(1, min(365, (int) $request->query('dias', 30)));
        try {
            $response = $this->api->request('GET', "/api/v1/admin/metricas?dias={$days}", token: $this->token($request));
        } catch (FastApiUnavailable) {
            return back()->withErrors(['api' => 'No se pudo generar el reporte porque FastAPI no está disponible.']);
        }
        if (! $response->successful()) {
            return back()->withErrors(['api' => $response->json('detail', 'No se pudo generar el reporte.')]);
        }

        $metrics = $response->json();
        $filename = 'lobo-upvt-metricas-'.now()->format('Ymd-His').'.csv';

        return response()->streamDownload(function () use ($metrics): void {
            $stream = fopen('php://output', 'w');
            fputcsv($stream, ['Fecha', 'Consultas']);
            foreach ($metrics['series'] ?? [] as $row) {
                fputcsv($stream, [$row['fecha'] ?? '', $row['consultas'] ?? 0]);
            }
            fclose($stream);
        }, $filename, ['Content-Type' => 'text/csv; charset=UTF-8']);
    }

    private function saveQuestion(Request $request, string $path, string $method): RedirectResponse
    {
        $data = $request->validate([
            'categoria' => ['required', 'string', 'max:50'],
            'pregunta' => ['required', 'string', 'min:3', 'max:255'],
            'respuesta' => ['required', 'string', 'min:1'],
            'palabras_clave' => ['nullable', 'string', 'max:255'],
            'dirigido_a' => ['required', 'in:todos,alumnos,profesores,directivos'],
            'animacion' => ['required', 'string', 'max:80'],
            'emocion' => ['required', 'string', 'max:80'],
            'activo' => ['nullable', 'boolean'],
        ]);
        $data['activo'] = (bool) ($data['activo'] ?? false);
        $data['palabras_clave'] = $data['palabras_clave'] ?: null;

        try {
            $response = $this->api->request($method, $path, $data, $this->token($request));
        } catch (FastApiUnavailable) {
            return back()->withInput()->withErrors(['api' => 'FastAPI no está disponible; los cambios no se guardaron.']);
        }

        if (! $response->successful()) {
            $detail = $response->json('detail', 'No se pudo guardar la respuesta.');

            return back()->withInput()->withErrors(is_array($detail) ? ['api' => 'Revisa los campos e inténtalo de nuevo.'] : ['api' => $detail]);
        }

        return redirect()->route('admin.questions')->with('status', $method === 'POST' ? 'Respuesta registrada.' : 'Respuesta actualizada.');
    }

    private function read(string $path, Request $request, ?string &$warning): array
    {
        if ((bool) $request->session()->get('demo_admin', false)) {
            return [];
        }

        try {
            $response = $this->api->request('GET', $path, token: $this->token($request));
            if ($response->successful()) {
                return $response->json() ?? [];
            }
            $warning ??= 'FastAPI respondió con estado HTTP '.$response->status().'.';
        } catch (FastApiUnavailable $exception) {
            $warning ??= $exception->getMessage();
        }

        return [];
    }

    private function token(Request $request): string
    {
        return (string) $request->session()->get('fastapi_token', '');
    }
}

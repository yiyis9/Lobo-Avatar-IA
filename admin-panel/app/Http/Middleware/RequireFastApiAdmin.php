<?php

namespace App\Http\Middleware;

use App\Exceptions\FastApiUnavailable;
use App\Services\FastApiClient;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class RequireFastApiAdmin
{
    public function handle(Request $request, Closure $next): Response
    {
        if ((bool) $request->session()->get('demo_admin', false)) {
            $isLocalDemo = config('services.fastapi.demo_access')
                && config('app.env') === 'local'
                && in_array($request->ip(), ['127.0.0.1', '::1'], true);
            if (! $isLocalDemo || ! $request->routeIs('admin.*') || $request->routeIs('admin.reports.download') || ! $request->isMethod('GET')) {
                abort(403);
            }

            $request->attributes->set('panel_admin', [
                'nombre' => 'Administrador',
                'correo' => $request->session()->get('demo_email', 'demo@local'),
                'rol' => 'admin',
            ]);

            return $next($request);
        }

        $token = $request->session()->get('fastapi_token');
        if (! is_string($token) || $token === '') {
            return redirect()->route('login');
        }

        try {
            $response = app(FastApiClient::class)->request('GET', '/api/v1/auth/me', token: $token);
        } catch (FastApiUnavailable) {
            return response()->view('errors.fastapi-unavailable', status: 503);
        }

        if (! $response->successful()) {
            $request->session()->forget(['fastapi_token', 'fastapi_admin']);
            $request->session()->regenerate();

            return redirect()->route('login')->withErrors(['correo' => 'Tu sesión expiró. Inicia sesión de nuevo.']);
        }

        $admin = $response->json();
        if (($admin['rol'] ?? null) !== 'admin') {
            $request->session()->invalidate();
            $request->session()->regenerateToken();

            return redirect()->route('login')->withErrors(['correo' => 'La cuenta no tiene permisos administrativos.']);
        }

        $request->attributes->set('panel_admin', $admin);

        return $next($request);
    }
}

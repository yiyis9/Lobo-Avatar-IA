<?php

namespace App\Http\Controllers;

use App\Exceptions\FastApiUnavailable;
use App\Services\FastApiClient;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Illuminate\View\View;

class AuthenticationController extends Controller
{
    public function showLogin(Request $request): View|RedirectResponse
    {
        if ($request->session()->has('fastapi_token') || (bool) $request->session()->get('demo_admin', false)) {
            return redirect()->route('admin.dashboard');
        }

        return view('auth.login');
    }

    public function login(Request $request, FastApiClient $api): RedirectResponse
    {
        $credentials = $request->validate([
            'correo' => ['required', 'email', 'max:100'],
            'contrasena' => ['required', 'string', 'max:256'],
        ]);

        if (config('services.fastapi.demo_access')
            && config('app.env') === 'local'
            && in_array($request->ip(), ['127.0.0.1', '::1'], true)) {
            $request->session()->regenerate();
            $request->session()->put('demo_admin', true);
            $request->session()->put('demo_email', $credentials['correo']);

            return redirect()->route('admin.dashboard');
        }

        try {
            $response = $api->request('POST', '/api/v1/auth/login', $credentials);
        } catch (FastApiUnavailable) {
            return back()->withInput($request->only('correo'))->withErrors(['correo' => 'No se pudo conectar con el servicio de autenticación.']);
        }

        if ($response->status() === 401) {
            return back()->withInput($request->only('correo'))->withErrors(['correo' => 'Correo o contraseña incorrectos.']);
        }

        if (! $response->successful() || ! is_string($response->json('access_token'))) {
            return back()->withInput($request->only('correo'))->withErrors(['correo' => $response->json('detail', 'No fue posible iniciar sesión.')]);
        }

        $request->session()->regenerate();
        $request->session()->put('fastapi_token', $response->json('access_token'));

        return redirect()->intended(route('admin.dashboard'));
    }

    public function showRegistration(Request $request): View|RedirectResponse
    {
        if ($request->session()->has('fastapi_token') || (bool) $request->session()->get('demo_admin', false)) {
            return redirect()->route('admin.dashboard');
        }

        return view('auth.register');
    }

    public function register(Request $request, FastApiClient $api): RedirectResponse
    {
        $data = $request->validate([
            'nombre' => ['required', 'string', 'min:2', 'max:100'],
            'correo' => ['required', 'email', 'max:100'],
            'contrasena' => ['required', 'string', 'min:10', 'max:256', 'confirmed'],
            'clave_autorizacion' => ['required', 'string', 'max:256'],
        ]);
        $data['rol'] = 'admin';

        try {
            $response = $api->request('POST', '/api/v1/auth/register', $data);
        } catch (FastApiUnavailable) {
            return back()->withInput($request->except(['contrasena', 'contrasena_confirmation', 'clave_autorizacion']))
                ->withErrors(['correo' => 'No se pudo conectar con el servicio de solicitudes.']);
        }

        if ($response->status() === 202) {
            return redirect()->route('register')->with('request_sent', true);
        }

        if ($response->status() === 422) {
            return back()->withInput($request->except(['contrasena', 'contrasena_confirmation', 'clave_autorizacion']))
                ->withErrors($response->json('detail', ['registro' => 'Verifica los datos ingresados.']));
        }

        return back()->withInput($request->except(['contrasena', 'contrasena_confirmation', 'clave_autorizacion']))
            ->withErrors(['registro' => $response->json('detail', 'No se pudo enviar la solicitud.')]);
    }

    public function logout(Request $request): RedirectResponse
    {
        $request->session()->invalidate();
        $request->session()->regenerateToken();

        return redirect()->route('login')->with('status', 'La sesión se cerró correctamente.');
    }
}

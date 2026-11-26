<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'Acceso') | Lobo UPVT</title>
    @vite(['resources/js/app.js'])
</head>
<body class="login-page">
    <a class="skip-link" href="#contenido">Saltar al contenido</a>
    <div class="institutional-stripe" aria-hidden="true"><span></span><span></span><span></span></div>
    <header class="login-top">
        <a class="brand" href="{{ route('login') }}">
            <span class="brand-copy"><strong>Lobo UPVT</strong><small>Acceso de administrador</small></span>
        </a>
        <span class="text-secondary small">Acceso privado</span>
    </header>
    <main class="login-main" id="contenido">
        @include('partials.flash')
        @yield('content')
        <p class="login-footer">Universidad Politécnica del Valle de Toluca</p>
    </main>
</body>
</html>

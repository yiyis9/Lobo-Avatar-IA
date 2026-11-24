<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>@yield('title', 'Panel') | Lobo UPVT</title>
    @vite(['resources/js/app.js'])
</head>
<body>
    <a class="skip-link" href="#contenido">Saltar al contenido</a>
    <div class="institutional-stripe" aria-hidden="true"><span></span><span></span><span></span></div>
    <header class="topbar">
        <div class="d-flex align-items-center gap-2">
            <button class="menu-button mobile-menu-button" type="button" data-sidebar-toggle aria-expanded="false" aria-controls="panel-sidebar">Menú</button>
            <a class="brand" href="{{ route('admin.dashboard') }}" aria-label="Lobo UPVT, resumen general">
                <img class="brand-logo" src="{{ asset('images/upvt-logo.png') }}" alt="Universidad Politécnica del Valle de Toluca">
                <span class="brand-copy"><strong>Lobo UPVT</strong><small>Panel administrativo</small></span>
            </a>
        </div>
        <div class="topbar-tools">
            <span class="system-pill">Panel privado</span>
        </div>
    </header>
    <div class="sidebar-scrim" data-sidebar-scrim aria-hidden="true"></div>
    <div class="app-shell">
        @include('partials.sidebar')
        <main class="main-content" id="contenido">
            <div class="content-wrap">
                @include('partials.flash')
                @yield('content')
                <footer class="content-footer">Universidad Politécnica del Valle de Toluca <span aria-hidden="true">·</span> Lobo UPVT</footer>
            </div>
        </main>
    </div>
</body>
</html>

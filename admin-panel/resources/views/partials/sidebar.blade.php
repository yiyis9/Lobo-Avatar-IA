@php($admin = request()->attributes->get('panel_admin', []))
<aside class="sidebar" id="panel-sidebar" data-sidebar aria-label="Navegación del panel">
    <div class="sidebar-heading">Administración</div>
    <nav class="sidebar-nav">
        <a class="sidebar-link {{ request()->routeIs('admin.dashboard') ? 'active' : '' }}" href="{{ route('admin.dashboard') }}" @if(request()->routeIs('admin.dashboard')) aria-current="page" @endif>
            <span>Resumen general</span>
        </a>
        <a class="sidebar-link {{ request()->routeIs('admin.questions*') ? 'active' : '' }}" href="{{ route('admin.questions') }}" @if(request()->routeIs('admin.questions*')) aria-current="page" @endif>
            <span>Preguntas y respuestas</span>
        </a>
        <a class="sidebar-link {{ request()->routeIs('admin.requests') ? 'active' : '' }}" href="{{ route('admin.requests') }}" @if(request()->routeIs('admin.requests')) aria-current="page" @endif>
            <span>Autorizaciones</span>
        </a>
        <a class="sidebar-link {{ request()->routeIs('admin.users') ? 'active' : '' }}" href="{{ route('admin.users') }}" @if(request()->routeIs('admin.users')) aria-current="page" @endif>
            <span>Usuarios</span>
        </a>
        <a class="sidebar-link {{ request()->routeIs('admin.reports') ? 'active' : '' }}" href="{{ route('admin.reports') }}" @if(request()->routeIs('admin.reports')) aria-current="page" @endif>
            <span>Métricas</span>
        </a>
        <a class="sidebar-link {{ request()->routeIs('admin.settings', 'admin.maintenance') ? 'active' : '' }}" href="{{ route('admin.settings') }}" @if(request()->routeIs('admin.settings', 'admin.maintenance')) aria-current="page" @endif>
            <span>Sistema</span>
        </a>
    </nav>
    <div class="sidebar-bottom">
        <div class="sidebar-identity">
            <span class="identity-avatar" aria-hidden="true">{{ mb_substr($admin['nombre'] ?? 'A', 0, 1) }}</span>
            <span class="identity-text"><strong>{{ $admin['nombre'] ?? 'Administrador' }}</strong><small>Administrador</small></span>
        </div>
        <form method="post" action="{{ route('logout') }}">
            @csrf
            <button class="logout-link" type="submit"><span>Cerrar sesión</span></button>
        </form>
    </div>
</aside>

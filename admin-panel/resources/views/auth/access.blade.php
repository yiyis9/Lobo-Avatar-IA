@extends('layouts.guest')
@section('title', 'Acceso administrativo')
@section('content')
<section class="login-panel access-panel" aria-labelledby="access-title">
    <img class="login-institutional-logo" src="{{ asset('images/upvt-logo.png') }}" alt="Universidad Politécnica del Valle de Toluca">
    <div class="eyebrow">Área administrativa privada</div>
    <h1 id="access-title">Acceso Lobo UPVT</h1>
    <p>Elige cómo deseas continuar.</p>
    <nav class="access-options" aria-label="Opciones de acceso">
        <a class="btn access-option access-option-primary" href="{{ route('login') }}">
            <span><strong>Iniciar sesión</strong><small>Ya cuento con una cuenta autorizada</small></span>
        </a>
        <a class="btn access-option" href="{{ route('register') }}">
            <span><strong>Solicitar registro</strong><small>Enviar mis datos para revisión administrativa</small></span>
        </a>
    </nav>
    <p class="access-note">El acceso al panel requiere autorización.</p>
</section>
@endsection

@extends('layouts.guest')
@section('title', 'Inicio de sesión')
@section('content')
<section class="login-panel" aria-labelledby="login-title">
    <img class="login-institutional-logo" src="{{ asset('images/upvt-logo.png') }}" alt="Universidad Politécnica del Valle de Toluca">
    <div class="eyebrow">Acceso privado</div>
    <h1 id="login-title">Acceso de administrador</h1>
    <p>Ingresa con tu cuenta administrativa autorizada.</p>
    <form method="post" action="{{ route('login.submit') }}">
        @csrf
        <div class="mb-3">
            <label class="form-label" for="correo">Correo</label>
            <input class="form-control" id="correo" name="correo" type="email" value="{{ old('correo') }}" autocomplete="username" maxlength="100" required autofocus>
            @error('correo')<div class="field-error">{{ $message }}</div>@enderror
        </div>
        <div class="mb-3">
            <label class="form-label" for="contrasena">Contraseña</label>
            <input class="form-control" id="contrasena" name="contrasena" type="password" autocomplete="current-password" maxlength="256" required>
            @error('contrasena')<div class="field-error">{{ $message }}</div>@enderror
        </div>
        <button class="btn btn-primary w-100 py-2" type="submit">Ingresar</button>
    </form>
    <a class="btn btn-outline-secondary w-100 mt-3" href="{{ route('access') }}">Regresar</a>
</section>
@endsection

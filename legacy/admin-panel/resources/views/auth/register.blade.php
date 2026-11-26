@extends('layouts.guest')
@section('title', 'Solicitud de cuenta')
@section('content')
<section class="login-panel" aria-labelledby="register-title">
    <img class="login-institutional-logo" src="{{ asset('images/upvt-logo.png') }}" alt="Universidad Politécnica del Valle de Toluca">
    @if (session('request_sent'))
        <div class="request-success" role="status">
            <h1 id="register-title">Solicitud enviada</h1>
            <p>La cuenta queda pendiente de autorización. El acceso administrativo solo se habilita para una cuenta aprobada con rol administrador.</p>
            <a class="btn btn-primary mt-3" href="{{ route('login') }}">Ir al inicio de sesión</a>
            <a class="btn btn-outline-secondary mt-3" href="{{ route('access') }}">Regresar</a>
        </div>
    @else
        <div class="eyebrow">Área administrativa</div>
        <h1 id="register-title">Solicitar registro</h1>
        <p>La cuenta se habilitará cuando el administrador principal apruebe la solicitud.</p>
        <form method="post" action="{{ route('register.submit') }}">
            @csrf
            <div class="mb-3"><label class="form-label" for="nombre">Nombre completo</label><input class="form-control" id="nombre" name="nombre" value="{{ old('nombre') }}" maxlength="100" autocomplete="name" required>@error('nombre')<div class="field-error">{{ $message }}</div>@enderror</div>
            <div class="mb-3"><label class="form-label" for="correo">Correo</label><input class="form-control" id="correo" name="correo" type="email" value="{{ old('correo') }}" maxlength="100" autocomplete="email" required>@error('correo')<div class="field-error">{{ $message }}</div>@enderror</div>
            <div class="mb-3"><label class="form-label" for="clave_autorizacion">Clave de autorización</label><input class="form-control" id="clave_autorizacion" name="clave_autorizacion" type="password" autocomplete="off" maxlength="256" required>@error('clave_autorizacion')<div class="field-error">{{ $message }}</div>@enderror</div>
            <div class="mb-3"><label class="form-label" for="contrasena">Contraseña</label><input class="form-control" id="contrasena" name="contrasena" type="password" autocomplete="new-password" minlength="10" maxlength="256" required>@error('contrasena')<div class="field-error">{{ $message }}</div>@enderror</div>
            <div class="mb-3"><label class="form-label" for="contrasena_confirmation">Confirmar contraseña</label><input class="form-control" id="contrasena_confirmation" name="contrasena_confirmation" type="password" autocomplete="new-password" minlength="10" maxlength="256" required></div>
            <button class="btn btn-primary w-100 py-2" type="submit">Solicitar autorización</button>
        </form>
        <div class="auth-links"><span>¿Ya tienes cuenta?</span><a href="{{ route('login') }}">Regresar al inicio de sesión</a></div>
        <a class="btn btn-outline-secondary w-100 mt-3" href="{{ route('access') }}">Volver</a>
    @endif
</section>
@endsection

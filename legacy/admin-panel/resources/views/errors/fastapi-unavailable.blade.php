@extends('layouts.guest')
@section('title', 'Servicio no disponible')
@section('content')
<section class="login-panel text-center" aria-labelledby="service-title">
    <div class="eyebrow">Lobo UPVT</div>
    <h1 id="service-title">Servicio temporalmente no disponible</h1>
    <p class="mt-2">El panel no pudo validar tu sesión con FastAPI. Comprueba que el backend esté activo y vuelve a intentarlo.</p>
    <a class="btn btn-primary" href="{{ route('login') }}">Volver al acceso</a>
</section>
@endsection

@extends('layouts.admin')
@section('title', 'Sistema')
@section('content')
<div class="page-heading"><div><div class="eyebrow">Configuración</div><h1>Sistema</h1></div></div>
<section class="panel-surface panel-padding" aria-label="Configuración del servicio">
    <div class="profile-field"><small>API central</small><strong>{{ config('services.fastapi.base_url') }}</strong></div>
    <p class="text-secondary mb-0">La conexión a MySQL se realiza desde FastAPI.</p>
</section>
@endsection

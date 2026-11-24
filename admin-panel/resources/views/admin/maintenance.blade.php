@extends('layouts.admin')
@section('title', 'Mantenimiento')
@section('content')
<div class="page-heading"><div><div class="eyebrow">Sistema</div><h1>Mantenimiento</h1></div></div>
<section class="panel-surface panel-padding" aria-label="Estado de servicios">
    <div class="profile-field"><small>FastAPI</small><strong>{{ $health['api'] ?? 'Sin conexión' }}</strong></div>
    <div class="profile-field"><small>MySQL</small><strong>{{ $health['mysql'] ?? 'No verificado' }}</strong></div>
    @if($message)<p class="text-secondary mb-0">{{ $message }}</p>@endif
</section>
@endsection

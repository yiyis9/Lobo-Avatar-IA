@extends('layouts.admin')
@section('title', 'Solicitudes pendientes')
@section('content')
<div class="page-heading"><div><div class="eyebrow">Accesos</div><h1>Solicitudes pendientes</h1></div></div>
@if($warning)<div class="alert alert-warning" role="status">{{ $warning }}</div>@endif
<section class="panel-surface panel-padding" aria-label="Solicitudes">
    @forelse($items as $item)
        <div class="profile-field"><strong>{{ $item['nombre'] ?? '—' }}</strong><div class="text-secondary">{{ $item['correo'] ?? '—' }} · {{ ucfirst($item['rol'] ?? '—') }}</div></div>
    @empty
        <p class="text-secondary mb-0">No hay solicitudes para mostrar.</p>
    @endforelse
</section>
@endsection

@extends('layouts.admin')
@section('title', 'Panel administrativo')
@section('content')
@php($questions = $summary['preguntas_frecuentes'] ?? [])
@php($requests = $requests ?? [])
<div class="page-heading">
    <div>
        <div class="eyebrow">Panel administrativo</div>
        <h1>Resumen general</h1>
        <p>Resumen básico del kiosko y su contenido.</p>
    </div>
</div>

@if($warning)
    <div class="alert alert-warning" role="status">{{ $warning }} Los indicadores no disponibles aparecen como “—”.</div>
@endif

<section class="metric-grid" aria-label="Indicadores básicos">
    <div class="metric-tile guinda">
        <div class="metric-copy"><span class="metric-label">Respuestas activas</span><strong class="metric-value">{{ $summary['respuestas_registradas'] ?? '—' }}</strong></div>
    </div>
    <div class="metric-tile verde">
        <div class="metric-copy"><span class="metric-label">Consultas atendidas</span><strong class="metric-value">{{ $summary['atenciones_totales'] ?? '—' }}</strong></div>
    </div>
    <div class="metric-tile lima">
        <div class="metric-copy"><span class="metric-label">Solicitudes pendientes</span><strong class="metric-value">{{ $summary['solicitudes_pendientes'] ?? '—' }}</strong></div>
    </div>
</section>

<section aria-labelledby="quick-actions-title">
    <div class="section-heading"><h2 id="quick-actions-title">Acciones rápidas</h2></div>
    <div class="quick-actions">
        <a class="quick-action" href="{{ route('admin.questions.create') }}">
            <span>Registrar respuesta</span>
        </a>
        <a class="quick-action" href="{{ route('admin.requests') }}">
            <span>Revisar autorizaciones</span>
        </a>
        @unless(session('demo_admin'))
            <a class="quick-action" href="{{ route('admin.reports.download') }}">
                <span>Descargar reporte</span>
            </a>
        @endunless
    </div>
</section>

<div class="dashboard-columns mt-4">
    <section class="panel-surface" aria-labelledby="popular-questions-title">
        <div class="panel-head"><h2 id="popular-questions-title">Preguntas frecuentes</h2></div>
        <div class="panel-body rank-list">
            @forelse($questions as $question)
                <div class="rank-row">
                    <span>{{ $question['pregunta'] ?? 'Pregunta' }}</span>
                    <strong>{{ $question['consultas'] ?? 0 }}</strong>
                </div>
            @empty
                <p class="text-secondary small mb-0">Aún no hay consultas registradas.</p>
            @endforelse
        </div>
    </section>

    <section class="panel-surface" aria-labelledby="pending-requests-title">
        <div class="panel-head">
            <h2 id="pending-requests-title">Solicitudes pendientes</h2>
            <a class="small" href="{{ route('admin.requests') }}">Ver todas</a>
        </div>
        <div class="panel-body">
            @forelse($requests as $requestItem)
                <div class="activity-row">
                    <span class="activity-message">{{ $requestItem['nombre'] ?? 'Solicitud de acceso' }}</span>
                    <span class="activity-time">{{ ucfirst($requestItem['rol'] ?? 'pendiente') }}</span>
                </div>
            @empty
                <p class="text-secondary small mb-0">No hay solicitudes pendientes.</p>
            @endforelse
        </div>
    </section>
</div>

@endsection

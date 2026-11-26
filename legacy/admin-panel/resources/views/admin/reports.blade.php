@extends('layouts.admin')
@section('title', 'Reportes y métricas')
@section('content')
<div class="page-heading"><div><div class="eyebrow">Kiosko</div><h1>Reportes y métricas</h1></div></div>
@if($warning)<div class="alert alert-warning" role="status">{{ $warning }}</div>@endif
<section class="metric-grid" aria-label="Métricas">
    <div class="metric-tile guinda"><div class="metric-copy"><span class="metric-label">Atenciones</span><strong class="metric-value">{{ $metrics['atenciones'] ?? '—' }}</strong></div></div>
    <div class="metric-tile verde"><div class="metric-copy"><span class="metric-label">Días consultados</span><strong class="metric-value">{{ $metrics['dias'] ?? '—' }}</strong></div></div>
    <div class="metric-tile lima"><div class="metric-copy"><span class="metric-label">Periodo</span><strong class="metric-value" style="font-size:19px">{{ $days }} días</strong></div></div>
</section>
@endsection

@extends('layouts.admin')
@section('title', 'Gestor de preguntas')
@section('content')
<div class="page-heading">
    <div><div class="eyebrow">Contenido del kiosko</div><h1>Gestor de preguntas</h1><p>Preguntas y respuestas institucionales.</p></div>
    <a class="btn btn-primary" href="{{ route('admin.questions.create') }}">Nueva respuesta</a>
</div>
@if($warning)<div class="alert alert-warning" role="status">{{ $warning }}</div>@endif
<section class="panel-surface panel-padding" aria-label="Preguntas y respuestas">
    <form class="d-flex gap-2 mb-3" method="get" action="{{ route('admin.questions') }}">
        <input class="form-control" name="q" value="{{ $search }}" placeholder="Buscar pregunta" aria-label="Buscar pregunta">
        <button class="btn btn-outline-primary" type="submit">Buscar</button>
    </form>
    @forelse($items as $item)
        <div class="profile-field"><strong>{{ $item['pregunta'] ?? '—' }}</strong><div class="text-secondary mt-1">{{ \Illuminate\Support\Str::limit($item['respuesta'] ?? '', 140) }}</div></div>
    @empty
        <p class="text-secondary mb-0">Aún no hay respuestas para mostrar.</p>
    @endforelse
</section>
@endsection

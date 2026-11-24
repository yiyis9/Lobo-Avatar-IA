@extends('layouts.admin')
@section('title', $item ? 'Editar respuesta' : 'Nueva respuesta')
@section('content')
<div class="page-heading"><div><div class="eyebrow">Contenido del kiosko</div><h1>{{ $item ? 'Editar respuesta' : 'Registrar nueva respuesta' }}</h1></div></div>
@if($warning)<div class="alert alert-warning" role="status">{{ $warning }}</div>@endif
<form class="panel-surface panel-padding" method="post" action="{{ $item ? route('admin.questions.update', $item['id']) : route('admin.questions.store') }}">
    @csrf @if($item) @method('PUT') @endif
    <input type="hidden" name="palabras_clave" value="{{ old('palabras_clave', $item['palabras_clave'] ?? '') }}">
    <input type="hidden" name="dirigido_a" value="{{ old('dirigido_a', $item['dirigido_a'] ?? 'todos') }}">
    <input type="hidden" name="animacion" value="{{ old('animacion', $item['animacion'] ?? 'idle') }}">
    <input type="hidden" name="emocion" value="{{ old('emocion', $item['emocion'] ?? 'neutral') }}">
    <input type="hidden" name="activo" value="1">
    <div class="mb-3"><label class="form-label" for="pregunta">Pregunta</label><input class="form-control" id="pregunta" name="pregunta" maxlength="255" value="{{ old('pregunta', $item['pregunta'] ?? '') }}" required></div>
    <div class="mb-3"><label class="form-label" for="categoria">Categoría</label><input class="form-control" id="categoria" name="categoria" maxlength="50" value="{{ old('categoria', $item['categoria'] ?? '') }}" required></div>
    <div class="mb-3"><label class="form-label" for="respuesta">Respuesta</label><textarea class="form-control" id="respuesta" name="respuesta" rows="3" required>{{ old('respuesta', $item['respuesta'] ?? '') }}</textarea></div>
    <a class="btn btn-outline-secondary" href="{{ route('admin.questions') }}">Volver</a>
    @if(session('demo_admin'))
        <span class="text-secondary small ms-2">Edición no disponible en esta sesión.</span>
    @else
        <button class="btn btn-primary ms-2" type="submit">Guardar</button>
    @endif
</form>
@endsection

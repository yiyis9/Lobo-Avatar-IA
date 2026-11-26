@extends('layouts.admin')
@section('title', 'Perfil')
@section('content')
<div class="page-heading"><div><div class="eyebrow">Cuenta</div><h1>Perfil</h1></div></div>
<section class="panel-surface panel-padding" aria-label="Perfil administrativo">
    <div class="profile-field"><small>Nombre</small><strong>{{ $admin['nombre'] ?? '—' }}</strong></div>
    <div class="profile-field"><small>Correo</small><strong>{{ $admin['correo'] ?? '—' }}</strong></div>
    <div class="profile-field"><small>Rol</small><strong>{{ ucfirst($admin['rol'] ?? 'admin') }}</strong></div>
</section>
@endsection

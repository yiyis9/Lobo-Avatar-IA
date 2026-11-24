@if (session('status'))
    <div class="alert alert-success" role="status">{{ session('status') }}</div>
@endif
@if ($errors->any())
    <div class="alert alert-danger" role="alert">
        {{ $errors->first() }}
    </div>
@endif
@if (isset($warning) && $warning)
    <div class="alert alert-warning" role="status">{{ $warning }} Los datos no disponibles se muestran sin sustituirlos por cifras de demostración.</div>
@endif

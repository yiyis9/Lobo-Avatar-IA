$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $project
$portablePhp = Join-Path $root '.tools\php84\php.exe'

if (Test-Path -LiteralPath $portablePhp) {
    $php = $portablePhp
} else {
    $command = Get-Command php -ErrorAction SilentlyContinue
    if (-not $command) { throw 'Instala PHP 8.3 o superior y vuelve a iniciar el panel.' }
    $php = $command.Source
    $version = & $php -r 'echo PHP_VERSION_ID;'
    if ([int]$version -lt 80300) { throw 'El panel requiere PHP 8.3 o superior. La versión detectada no es compatible.' }
}

Push-Location $project
try {
    if (-not (Test-Path -LiteralPath '.env')) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        & $php artisan key:generate
    }
    if (-not (Test-Path -LiteralPath 'public\build\manifest.json')) {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron compilar los recursos del panel.' }
    }
    & $php artisan serve --host=127.0.0.1 --port=8002
} finally {
    Pop-Location
}

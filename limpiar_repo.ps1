# Limpia del índice de Git los archivos que no deben versionarse.
# NO borra nada de tu disco: solo deja de rastrearlos (git rm --cached).
# Úsalo en la raíz del repositorio, DESPUÉS de reemplazar .gitignore y agregar README.md.

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".git")) { Write-Error "Ejecuta este script en la raíz del repositorio."; exit 1 }

$rutas = @(
  ".tools",
  "_backups",
  "_working",
  ".nuget-profile",
  "Untitled.blend",
  "Untitled.blend1",
  "lobo_upvt_nuevo.blend1",
  "backend/uvicorn-check.err.log",
  "backend/uvicorn-check.out.log",
  "backend/static/kiosk/models/lobo-upvt-rigged.glb.pre-explicar-20261118-215749"
)

foreach ($r in $rutas) {
  git rm -r --cached --ignore-unmatch -- $r | Out-Null
  Write-Host "Dejado de rastrear: $r"
}

# Organización opcional: mover los proyectos obsoletos a legacy/
# (descomenta si quieres hacerlo)
# New-Item -ItemType Directory -Force legacy | Out-Null
# git mv admin-panel legacy/admin-panel
# git mv backend/LoboUPVT.Api legacy/LoboUPVT.Api

git add .gitignore README.md
git status --short
Write-Host "`nRevisa el resultado y luego:"
Write-Host '  git commit -m "Limpieza del repo, README raiz y .gitignore"'
Write-Host "  git push"

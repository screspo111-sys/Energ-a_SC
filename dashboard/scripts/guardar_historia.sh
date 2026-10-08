#!/usr/bin/env bash
# Sube al repositorio solo la historia de datos. No sube la página en claro,
# el HTML cifrado ni contraseñas.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add data dashboard
# raw/, site/ y public/ están en .gitignore; por si acaso, no se indexan.
git reset -q -- site public raw dashboard/raw .staticrypt.json 2>/dev/null || true
if git diff --cached --quiet; then
  echo "Sin cambios de datos para guardar."
  exit 0
fi
git commit -m "datos: actualización automática del tablero"
git push

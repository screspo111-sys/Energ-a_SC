#!/usr/bin/env bash
# Rutina del tablero (se puede repetir: no duplica filas).
# Una fuente que no responda no borra los CSV ni impide armar la página.
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
mkdir -p "$ROOT/dashboard/raw" "$ROOT/raw"
LOG="$ROOT/dashboard/raw/ultima_corrida.log"
{
  echo "== corrida $(TZ=America/Guayaquil date '+%Y-%m-%d %H:%M %Z')"
  "${PYTHON:-python3}" "$ROOT/dashboard/scripts/correr.py" "$@"
  echo "== fin $(TZ=America/Guayaquil date '+%H:%M')"
} 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"

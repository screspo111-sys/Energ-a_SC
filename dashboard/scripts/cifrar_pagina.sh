#!/usr/bin/env bash
# Cifra site/index.html con StatiCrypt (AES-256 en el navegador).
# Lee la contraseña de DASHBOARD_PASSWORD. Si falta, termina con error
# y no deja una página legible en public/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

python3 - << 'PY'
import os, sys
pw = os.environ.get("DASHBOARD_PASSWORD", "")
if not isinstance(pw, str) or pw.strip() == "":
    print(
        "FALTA el secreto DASHBOARD_PASSWORD. No se cifra y no se publica nada legible.",
        file=sys.stderr,
    )
    sys.exit(1)
print("Secreto DASHBOARD_PASSWORD presente. Se cifra la página; la contraseña no se imprime.")
PY

if [[ ! -f site/index.html ]]; then
  echo "No existe site/index.html. Hay que armar la página antes de cifrar." >&2
  exit 1
fi

rm -rf public
mkdir -p public
# STATICRYPT_PASSWORD la lee el programa; no va en la línea de comandos.
export STATICRYPT_PASSWORD="$DASHBOARD_PASSWORD"
npx --yes staticrypt@3.5.4 site/index.html \
  -c false \
  -d public \
  --short \
  --remember false \
  --template-title "Tablero de electricidad — Ecuador" \
  --template-instructions "Página cifrada. Solo quien tiene la contraseña puede leer el tablero." \
  --template-placeholder "Contraseña" \
  --template-button "Entrar" \
  --template-error "Contraseña incorrecta" \
  --template-color-primary "#0f6f6a" \
  --template-color-secondary "#f6f3ec"
estado=$?
unset STATICRYPT_PASSWORD
unset DASHBOARD_PASSWORD
if [[ $estado -ne 0 ]]; then
  rm -rf public
  echo "Falló el cifrado. No se deja una copia legible." >&2
  exit "$estado"
fi

if ! python3 - << 'PY'
import sys
from pathlib import Path
html = Path("public/index.html").read_text(encoding="utf-8", errors="replace")
prohibido = ["Estimación propia, no oficial", "Margen de reserva", "semaforo", "probabilidad_apagones"]
for marca in prohibido:
    if marca in html:
        print(f"La página cifrada todavía contiene texto legible ({marca!r}). No se publica.", file=sys.stderr)
        sys.exit(1)
if "Entrar" not in html and "DECRYPT" not in html:
    print("La página cifrada no muestra el formulario de contraseña.", file=sys.stderr)
    sys.exit(1)
otros = [p for p in Path("public").rglob("*") if p.is_file() and p.suffix.lower() in {".csv", ".json", ".parquet", ".md"}]
if otros:
    print("public/ contiene datos sin cifrar:", ", ".join(str(p) for p in otros), file=sys.stderr)
    sys.exit(1)
print("Cifrado comprobado: el HTML público no contiene las cifras en claro.")
PY
then
  rm -rf public
  echo "Se borró public/ porque el cifrado no quedó ilegible." >&2
  exit 1
fi
echo > public/.nojekyll
rm -f .staticrypt.json public/.staticrypt.json
exit 0

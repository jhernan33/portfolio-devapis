#!/bin/bash
# Sirve src/ bajo /cv/, que es la ruta real del sitio.
set -euo pipefail
cd "$(dirname "$0")"
RAIZ=$(mktemp -d)
ln -sfn "$(cd ../../src && pwd)" "$RAIZ/cv"
cd "$RAIZ"
exec python3 -m http.server 8123 --bind 127.0.0.1

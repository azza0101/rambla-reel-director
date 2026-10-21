#!/bin/sh
set -eu
APP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ ! -x "$APP_ROOT/.venv/bin/python" ]; then
  echo "Runtime Python RMBL non disponibile: questa prima versione richiede il motore installato."
  exit 1
fi
exec "$APP_ROOT/.venv/bin/python" "$APP_ROOT/tools/install_autocut_integration.py" --app-root "$APP_ROOT"

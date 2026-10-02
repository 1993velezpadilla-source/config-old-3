#!/usr/bin/env bash
set -euo pipefail

ROOT="${XZIEL_TOOLS_ROOT:-.xziel-tools}"
VENV="$ROOT/reference-match-venv"
GEOCALIB_SHA="97b8968e7798a66bf04fcf791fb535624241bda7"
LIGHTGLUE_SHA="eb42fee2d71449efb0aa5c10549752b5d75384d8"

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip wheel setuptools
"$VENV/bin/python" -m pip install   "git+https://github.com/cvg/GeoCalib.git@$GEOCALIB_SHA"   "git+https://github.com/cvg/LightGlue.git@$LIGHTGLUE_SHA"

"$VENV/bin/python" - <<'PY'
import importlib
for name in ("geocalib","lightglue"):
    importlib.import_module(name)
print("XZIEL_REFERENCE_MATCH_BOOTSTRAP_GREEN")
PY

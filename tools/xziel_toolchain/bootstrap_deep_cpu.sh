#!/usr/bin/env bash
set -euo pipefail
ROOT="${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
VENV="$ROOT/deep-venv"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip wheel setuptools
"$VENV/bin/python" -m pip install \
  "open3d-cpu==0.20.0" \
  "pycolmap==4.2.1" \
  "numpy>=2.0" \
  "pillow>=10" \
  "opencv-python-headless>=4.10"
"$VENV/bin/python" - <<'PY'
import open3d as o3d
import pycolmap
print("OPEN3D_VERSION", o3d.__version__)
print("PYCOLMAP_VERSION", pycolmap.__version__)
print("XZIEL_DEEP_CPU_TOOLCHAIN_READY")
PY

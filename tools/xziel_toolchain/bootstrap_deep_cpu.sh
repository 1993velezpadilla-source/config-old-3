#!/usr/bin/env bash
set -euo pipefail
ROOT="${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
VENV="$ROOT/deep-venv"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip wheel setuptools
"$VENV/bin/python" -m pip install \
  "open3d-cpu==0.20.0" \
  "pycolmap==4.2.1" \
  "manifold3d==3.5.4" \
  "coacd==1.0.14" \
  "numpy>=2.0" \
  "pillow>=10" \
  "opencv-python-headless>=4.10"
"$VENV/bin/python" - <<'PY'
import open3d as o3d
import pycolmap
import manifold3d
import coacd
print("OPEN3D_VERSION", o3d.__version__)
print("PYCOLMAP_VERSION", pycolmap.__version__)
print("MANIFOLD3D_READY", manifold3d.Manifold.cube((1,1,1)).volume())
print("COACD_READY", coacd.__version__ if hasattr(coacd, "__version__") else "imported")
print("XZIEL_DEEP_CPU_TOOLCHAIN_READY")
PY

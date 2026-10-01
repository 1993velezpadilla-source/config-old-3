#!/usr/bin/env bash
set -euo pipefail

ROOT="\${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
VENV="$ROOT/geometry-venv"

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --upgrade pip wheel setuptools
"$VENV/bin/python" -m pip install \
  "numpy>=2.0" \
  "trimesh==5.1.0" \
  "manifold3d==3.5.4" \
  "coacd==1.0.14"

"$VENV/bin/python" - <<'PY'
import coacd
import manifold3d
import trimesh

box=trimesh.creation.box()
assert len(box.vertices)==8
assert len(box.faces)==12
assert manifold3d.Manifold.cube((1,1,1)).volume() > 0
print("TRIMESH_VERSION", trimesh.__version__)
print("COACD_READY", hasattr(coacd, "run_coacd"))
print("MANIFOLD_READY")
print("XZIEL_GEOMETRY_CPU_READY")
PY

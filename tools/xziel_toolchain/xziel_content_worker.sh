#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'EOF'
XZIEL content worker
usage:
  xziel_content_worker.sh asset INPUT.glb OUTPUT_DIR [NAME]
  xziel_content_worker.sh map INPUT.glb OUTPUT_DIR [NAME]
  xziel_content_worker.sh references IMAGE_DIR OUTPUT_DIR

Modes:
  asset       optimize + inspect + official glTF validation + KTX2 mobile variant
  map         asset pipeline + runtime geometry + Recast/Detour navmesh + CoACD collision
  references  pyCOLMAP + Open3D camera/sparse reconstruction
EOF
  exit 2
}

[[ $# -ge 3 ]] || usage
MODE="$1"
INPUT="$2"
OUT="$3"
NAME="${4:-$(basename "${INPUT%.*}")}"
ROOT="${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
mkdir -p "$OUT"

case "$MODE" in
  asset)
    bash tools/xziel_toolchain/bootstrap_asset_cli.sh
    bash tools/xziel_toolchain/process_glb.sh "$INPUT" "$OUT/optimized" "$NAME"
    bash tools/xziel_toolchain/process_glb_mobile.sh "$INPUT" "$OUT/mobile" "$NAME"
    echo "XZIEL_CONTENT_WORKER_ASSET_PASS"
    ;;

  map)
    bash tools/xziel_toolchain/bootstrap_asset_cli.sh
    bash tools/xziel_toolchain/process_glb.sh "$INPUT" "$OUT/optimized" "$NAME"
    bash tools/xziel_toolchain/process_glb_mobile.sh "$INPUT" "$OUT/mobile" "$NAME"

    bash tools/xziel_toolchain/bootstrap_fast.sh
    bash tools/xziel_toolchain/bootstrap_geometry_cpu.sh

    "$ROOT/geometry-venv/bin/python"       tools/xziel_toolchain/extract_runtime_geometry.py       --input "$INPUT"       --out "$OUT/runtime"

    "$ROOT/bin/xziel-navmesh-bake"       "$OUT/runtime/sanctum-nav-source.obj"       "$OUT/runtime/$NAME.navbin"       "$OUT/runtime/$NAME.navmesh.json"

    "$ROOT/geometry-venv/bin/python"       tools/xziel_toolchain/generate_collision_hulls.py       --input "$OUT/runtime/sanctum-collision-source.glb"       --output "$OUT/runtime/$NAME.collision-hulls.glb"       --report "$OUT/runtime/$NAME.collision.json"       --threshold 0.08       --max-hulls 128       --max-hull-vertices 64

    python3 - "$OUT/runtime/$NAME.navmesh.json" "$OUT/runtime/$NAME.collision.json" <<'PY'
import json,sys
nav=json.load(open(sys.argv[1],encoding="utf-8"))
col=json.load(open(sys.argv[2],encoding="utf-8"))
assert nav["status"]=="PASS" and nav["nav_polygons"]>0 and nav["nearest_poly_ref"]!=0,nav
assert col["status"]=="PASS" and 0<col["hull_count"]<=128,col
print("XZIEL_CONTENT_WORKER_MAP_GREEN",{
    "nav_polygons":nav["nav_polygons"],
    "navdata_bytes":nav["navdata_bytes"],
    "collision_hulls":col["hull_count"],
})
PY
    echo "XZIEL_CONTENT_WORKER_MAP_PASS"
    ;;

  references)
    [[ -d "$INPUT" ]] || { echo "reference input must be a directory" >&2; exit 2; }
    bash tools/xziel_toolchain/bootstrap_deep_cpu.sh
    "$ROOT/deep-venv/bin/python"       tools/xziel_toolchain/reconstruct_references.py       --images "$INPUT"       --out "$OUT"
    echo "XZIEL_CONTENT_WORKER_REFERENCES_PASS"
    ;;

  *)
    usage
    ;;
esac

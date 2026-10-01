#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 2 ]]; then
  echo "usage: $0 INPUT.glb OUTPUT.glb" >&2
  exit 2
fi
INPUT="$1"
OUTPUT="$2"
ROOT="${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
GLTFPACK="$ROOT/bin/gltfpack"
test -x "$GLTFPACK"
test -s "$INPUT"
mkdir -p "$(dirname "$OUTPUT")"
"$GLTFPACK" -i "$INPUT" -o "$OUTPUT"
test -s "$OUTPUT"
python3 - "$INPUT" "$OUTPUT" <<'PY'
from pathlib import Path
import json,sys
a,b=map(Path,sys.argv[1:3])
r={"input":str(a),"input_bytes":a.stat().st_size,"output":str(b),"output_bytes":b.stat().st_size}
r["ratio"]=r["output_bytes"]/r["input_bytes"] if r["input_bytes"] else None
print(json.dumps(r,indent=2))
PY
echo "XZIEL_GLTFPACK_PASS"

#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: $0 INPUT.glb OUTPUT_DIR [NAME]" >&2
  exit 2
fi

INPUT="$1"
OUT="$2"
NAME="${3:-$(basename "${INPUT%.*}")}"
ROOT="${XZIEL_TOOL_ROOT:-$PWD/.xziel-tools}"
BIN="$ROOT/bin"

test -s "$INPUT"
test -x "$BIN/gltfpack"
test -x "$BIN/gltf-transform"
mkdir -p "$OUT"

OPT="$OUT/$NAME.optimized.glb"
VALIDATION="$OUT/$NAME.validation.json"
INSPECT="$OUT/$NAME.inspect.txt"
REPORT="$OUT/$NAME.pipeline.json"

"$BIN/gltfpack" -i "$INPUT" -o "$OPT"
test -s "$OPT"

"$BIN/gltf-transform" inspect "$OPT" > "$INSPECT"

XZIEL_TOOL_ROOT="$ROOT" node tools/xziel_toolchain/validate_glb.cjs "$OPT" "$VALIDATION"

python3 - "$INPUT" "$OPT" "$VALIDATION" "$REPORT" <<'PY'
from pathlib import Path
import hashlib, json, sys
raw,opt,val,report=map(Path,sys.argv[1:5])
validation=json.loads(val.read_text(encoding="utf-8"))
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()
out={
    "status":"PASS",
    "input":str(raw),
    "input_bytes":raw.stat().st_size,
    "input_sha256":sha(raw),
    "optimized":str(opt),
    "optimized_bytes":opt.stat().st_size,
    "optimized_sha256":sha(opt),
    "size_ratio":opt.stat().st_size/raw.stat().st_size if raw.stat().st_size else None,
    "validator":{
        "errors":validation.get("issues",{}).get("numErrors",0),
        "warnings":validation.get("issues",{}).get("numWarnings",0),
        "infos":validation.get("issues",{}).get("numInfos",0),
        "hints":validation.get("issues",{}).get("numHints",0),
    }
}
if out["validator"]["errors"] != 0:
    raise SystemExit("validator errors")
report.write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps(out,indent=2))
PY

echo "XZIEL_ASSET_PIPELINE_PASS"

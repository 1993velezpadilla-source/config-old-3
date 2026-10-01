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

MOBILE="$OUT/$NAME.mobile-ktx2.glb"
VALIDATION="$OUT/$NAME.mobile-ktx2.validation.json"
INSPECT="$OUT/$NAME.mobile-ktx2.inspect.txt"
REPORT="$OUT/$NAME.mobile-ktx2.pipeline.json"

# Keep all authored vertex attributes. Color/attribute textures use ETC1S,
# while normal maps use UASTC to avoid excessive normal-map artifacts.
"$BIN/gltfpack" \
  -kv \
  -tc color,attrib \
  -tu normal \
  -tq 9 \
  -i "$INPUT" \
  -o "$MOBILE"

test -s "$MOBILE"
"$BIN/gltf-transform" inspect "$MOBILE" > "$INSPECT"
XZIEL_TOOL_ROOT="$ROOT" node tools/xziel_toolchain/validate_glb.cjs \
  "$MOBILE" "$VALIDATION"

python3 - "$INPUT" "$MOBILE" "$VALIDATION" "$REPORT" <<'PY'
from pathlib import Path
import hashlib,json,sys

raw,mobile,val,report=map(Path,sys.argv[1:5])
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
    "mobile":str(mobile),
    "mobile_bytes":mobile.stat().st_size,
    "mobile_sha256":sha(mobile),
    "size_ratio":mobile.stat().st_size/raw.stat().st_size if raw.stat().st_size else None,
    "texture_policy":{
        "color_and_attribute":"KTX2 BasisU ETC1S",
        "normal":"KTX2 BasisU UASTC",
        "quality":9,
        "vertex_attributes":"preserved"
    },
    "validator":{
        "errors":validation.get("issues",{}).get("numErrors",0),
        "warnings":validation.get("issues",{}).get("numWarnings",0),
        "infos":validation.get("issues",{}).get("numInfos",0),
        "hints":validation.get("issues",{}).get("numHints",0),
    }
}
if out["validator"]["errors"] != 0:
    raise SystemExit("mobile KTX2 validator errors")
report.write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps(out,indent=2))
PY

echo "XZIEL_MOBILE_KTX2_PIPELINE_PASS"

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

"$BIN/gltfpack" -kv -i "$INPUT" -o "$OPT"
test -s "$OPT"

"$BIN/gltf-transform" inspect "$OPT" > "$INSPECT"

XZIEL_TOOL_ROOT="$ROOT" node tools/xziel_toolchain/validate_glb.cjs "$OPT" "$VALIDATION"

UASTC=""
UASTC_VALIDATION=""
UASTC_INSPECT=""
if [[ "${XZIEL_KTX2_UASTC:-0}" == "1" ]]; then
  UASTC="$OUT/$NAME.uastc-ktx2.glb"
  UASTC_VALIDATION="$OUT/$NAME.uastc-ktx2.validation.json"
  UASTC_INSPECT="$OUT/$NAME.uastc-ktx2.inspect.txt"

  # Maximum-quality mobile texture variant. No -ts/-tl/-tp flags are used:
  # texture dimensions are preserved; only representation changes to UASTC KTX2.
  "$BIN/gltfpack" -kv -tu -tq 10 -i "$INPUT" -o "$UASTC"
  test -s "$UASTC"
  "$BIN/gltf-transform" inspect "$UASTC" > "$UASTC_INSPECT"
  XZIEL_TOOL_ROOT="$ROOT" node tools/xziel_toolchain/validate_glb.cjs     "$UASTC" "$UASTC_VALIDATION"
fi

python3 - "$INPUT" "$OPT" "$VALIDATION" "$REPORT" "$UASTC" "$UASTC_VALIDATION" <<'PY'
from pathlib import Path
import hashlib, json, sys
raw,opt,val,report=map(Path,sys.argv[1:5])
uastc_arg=sys.argv[5] if len(sys.argv) > 5 else ""
uastc_val_arg=sys.argv[6] if len(sys.argv) > 6 else ""
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

if uastc_arg:
    uastc=Path(uastc_arg)
    uastc_val=Path(uastc_val_arg)
    uv=json.loads(uastc_val.read_text(encoding="utf-8"))
    out["uastc_ktx2"]={
        "path":str(uastc),
        "bytes":uastc.stat().st_size,
        "sha256":sha(uastc),
        "size_ratio":uastc.stat().st_size/raw.stat().st_size if raw.stat().st_size else None,
        "texture_dimensions_policy":"preserved-no-resize-flags",
        "gltfpack_flags":["-kv","-tu","-tq","10"],
        "validator":{
            "errors":uv.get("issues",{}).get("numErrors",0),
            "warnings":uv.get("issues",{}).get("numWarnings",0),
            "infos":uv.get("issues",{}).get("numInfos",0),
            "hints":uv.get("issues",{}).get("numHints",0),
        },
    }
    if out["uastc_ktx2"]["validator"]["errors"] != 0:
        raise SystemExit("UASTC KTX2 validator errors")

report.write_text(json.dumps(out,indent=2),encoding="utf-8")
print(json.dumps(out,indent=2))
PY

echo "XZIEL_ASSET_PIPELINE_PASS"

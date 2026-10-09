#!/usr/bin/env python3
import argparse, base64, io, json, struct
from pathlib import Path
from PIL import Image

JSON_CHUNK=0x4E4F534A
BIN_CHUNK=0x004E4942

def read_glb(path: Path):
    data=path.read_bytes()
    if len(data)<12:
        raise SystemExit("GLB too small")
    magic,version,total=struct.unpack_from("<4sII",data,0)
    if magic!=b"glTF" or version!=2:
        raise SystemExit(f"unsupported GLB header {magic!r} v{version}")
    if total>len(data):
        raise SystemExit("truncated GLB")
    off=12; doc=None; bin_blob=b""
    while off+8<=total:
        clen,ctype=struct.unpack_from("<II",data,off); off+=8
        chunk=data[off:off+clen]; off+=clen
        if ctype==JSON_CHUNK:
            doc=json.loads(chunk.rstrip(b" \t\r\n\x00").decode("utf-8"))
        elif ctype==BIN_CHUNK:
            bin_blob=chunk
    if doc is None:
        raise SystemExit("GLB missing JSON chunk")
    return doc,bin_blob

def image_bytes(doc,bin_blob,index):
    im=doc["images"][index]
    if "bufferView" in im:
        bv=doc["bufferViews"][im["bufferView"]]
        if bv.get("buffer",0)!=0:
            raise SystemExit("external GLB buffer not supported")
        start=bv.get("byteOffset",0)
        end=start+bv["byteLength"]
        return bin_blob[start:end], im.get("mimeType","")
    uri=im.get("uri","")
    if uri.startswith("data:"):
        head,payload=uri.split(",",1)
        return base64.b64decode(payload), head.split(";")[0].split(":",1)[1]
    raise SystemExit(f"external image URI unsupported: {uri[:80]}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--glb",required=True)
    ap.add_argument("--report",required=True)
    ap.add_argument("--root",required=True)
    ap.add_argument("--max-dim",type=int,default=4096)
    args=ap.parse_args()

    glb=Path(args.glb); report_path=Path(args.report); root=Path(args.root)
    doc,bin_blob=read_glb(glb)
    report=json.loads(report_path.read_text(encoding="utf-8"))
    targets=report.get("textures",{})
    textures=doc.get("textures",[])
    materials=doc.get("materials",[])

    replaced=[]
    source_dims=[]
    unmatched=[]
    for mat in materials:
        name=mat.get("name") or ""
        target=targets.get(name)
        pbr=mat.get("pbrMetallicRoughness") or {}
        bc=pbr.get("baseColorTexture")
        if not target or not bc:
            continue
        ti=bc.get("index")
        if ti is None or ti>=len(textures):
            continue
        source=textures[ti].get("source")
        if source is None:
            continue
        raw,mime=image_bytes(doc,bin_blob,source)
        with Image.open(io.BytesIO(raw)) as src:
            im=src.convert("RGB")
            sw,sh=im.size
            source_dims.append((name,sw,sh))
            scale=min(1.0,args.max_dim/max(sw,sh))
            nw=max(1,int(round(sw*scale))); nh=max(1,int(round(sh*scale)))
            if (nw,nh)!=(sw,sh):
                im=im.resize((nw,nh),Image.Resampling.LANCZOS)
            rel=target["path"]
            dst=root/rel
            dst.parent.mkdir(parents=True,exist_ok=True)
            im.save(dst,format="PNG",optimize=True)
            replaced.append((name,sw,sh,nw,nh,str(dst)))

    if not replaced:
        raise SystemExit("No architectural textures matched original GLB materials")
    hi=[r for r in replaced if max(r[1],r[2])>1024]
    if not hi:
        raise SystemExit(f"Original GLB did not expose >1K base-color textures: {source_dims}")
    if len(replaced)<8:
        raise SystemExit(f"Too few original architectural textures matched: {len(replaced)}")

    print("XZIEL_ORIGINAL_TEXTURE_INJECT_OK")
    print(json.dumps({
        "matched":len(replaced),
        "sourceAbove1K":len(hi),
        "maxSourceDimension":max(max(r[1],r[2]) for r in replaced),
        "maxOutputDimension":max(max(r[3],r[4]) for r in replaced),
        "samples":[
            {"material":r[0],"source":[r[1],r[2]],"output":[r[3],r[4]],"path":r[5]}
            for r in replaced[:6]
        ]
    },indent=2))

if __name__=="__main__":
    main()

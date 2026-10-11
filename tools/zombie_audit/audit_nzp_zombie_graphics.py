#!/usr/bin/env python3
"""Read-only audit of the NZ:P runtime PC asset archive and pinned QuakeC."""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re
import struct
import zipfile

BODY=["zfull.mdl","zb%.mdl","zh^.mdl","zal(.mdl","zar(.mdl","zcfull.mdl","zbc%.mdl","zhc^.mdl","zalc(.mdl","zarc(.mdl"]
DOG=["dog.mdl","dog_lightning.mdl"]
FILES={"zombie":"source/server/ai/zombie_core.qc","crawler":"source/server/ai/crawler_core.qc",
       "hellhound":"source/server/ai/dog_core.qc","client_skins":"source/client/zombie.qc",
       "navigation":"source/server/ai/ai_core.qc",
       "pathfinding":"source/server/ai/pathfind_code.qc","zones":"source/server/ai/zoning_core.qc"}
def mdl(raw):
    out={"bytes":len(raw),"format":raw[:4].decode("ascii","replace"),
         "version":struct.unpack_from("<i",raw,4)[0] if len(raw)>=8 else None}
    if out["format"]!="IDPO" or out["version"]!=6 or len(raw)<84:
        out["warning"]="Not standard Quake IDPO version 6"
        return out
    ns,w,h,nv,nt,nf,sy,flags=struct.unpack_from("<8i",raw,48)
    out.update(skins=ns,width=w,height=h,vertices=nv,triangles=nt,
               frames=nf,synctype=sy,flags=flags)
    if min(ns,w,h,nv,nt,nf)<=0:out["warning"]="Invalid or zero MDL metadata"
    return out
def tex(raw,name):
    out={"bytes":len(raw)}
    if name.lower().endswith(".pcx") and len(raw)>=128 and raw[0]==10:
        mnx,mny,mxx,mxy=struct.unpack_from("<4H",raw,4)
        out.update(format="PCX",width=mxx-mnx+1,height=mxy-mny+1,depth=raw[3])
    elif name.lower().endswith(".png") and raw.startswith(b"\x89PNG\r\n\x1a\n"):
        w,h=struct.unpack_from(">II",raw,16)
        out.update(format="PNG",width=w,height=h,depth=raw[24])
    else:out["format"]="unknown"
    return out
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pack",type=Path,required=True)
    ap.add_argument("--quakec",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    dest=a.out
    dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.pack) as z:
        names=z.namelist()
        data={"archive_sha256":hashlib.sha256(a.pack.read_bytes()).hexdigest(),
              "archive_entries":len(names),"model":{},"skin_images":{},"sounds":{},
              "quakec":{},"warnings":[]}
        for basename in BODY+DOG:
            matches=[p for p in names if p.endswith("models/ai/"+basename)]
            if not matches:
                data["warnings"].append("MISSING ENEMY MODEL "+basename)
                continue
            path=matches[0]
            data["model"][basename]={"path":path,**mdl(z.read(path))}
        for p in names:
            norm="/"+p
            if "/models/ai/" in norm and p.lower().endswith((".pcx",".png",".tga",".palhint")):
                data["skin_images"][p]=tex(z.read(p),p)
        ss=[p for p in names if p.endswith(".wav") and
            ("/sounds/zombie/" in "/"+p or "/sounds/hound/" in "/"+p)]
        data["sounds"]={"zombie":sum("/sounds/zombie/" in p for p in ss),
                        "hound":sum("/sounds/hound/" in p for p in ss),
                        "files":ss}
    for category,path in FILES.items():
        src=(a.quakec/path).read_text(encoding="utf8",errors="replace")
        frames=[int(v) for v in re.findall(r"\bself\.frame\s*=\s*(\d+)\s*;",src)]
        setmodel=[{"line":i+1,"text":l.strip()} for i,l in enumerate(src.splitlines())
                  if ("setmodel" in l and "models/ai/" in l and not l.lstrip().startswith("//"))]
        data["quakec"][category]={
            "file":path,"lines":len(src.splitlines()),
            "frame_statements":len(frames),"max_direct_frame_index":max(frames,default=None),
            "model_references":sorted(set(re.findall(r"models/ai/[^\"\s]+\.mdl",src))),
            "model_assignments":setmodel}
    data["index_checks"]={}
    for model,kind in [("zb%.mdl","zombie"),("zbc%.mdl","crawler"),("dog.mdl","hellhound")]:
        n=data["model"].get(model,{}).get("frames")
        hi=data["quakec"][kind]["max_direct_frame_index"]
        data["index_checks"][model]={"model_frames":n,"highest_explicit_frame":hi,
                                      "in_range":n is not None and hi is not None and hi<n}
    data["summary"]={"models_expected":len(BODY+DOG),"models_found":len(data["model"]),
                     "skins_files":len(data["skin_images"]),
                     "skin_dimensions":sorted(set(str(x.get("width"))+"x"+str(x.get("height")) for x in data["skin_images"].values() if x.get("width"))),
                     "zombie_sounds":data["sounds"]["zombie"],
                     "hound_sounds":data["sounds"]["hound"],
                     "runtime_checks":data["index_checks"]}
    (dest/"nzp-zombie-graphics.json").write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n")
    md=["# NZ:P Zombie Graphics Full Asset/QuakeC Audit",
        "Scope: pinned XZIEL QuakeC revision 8a77f1ce + runtime PC assets release newest.",
        "This is a READ-ONLY source/binary metadata inspection, not a phone visual test.","",
        "Asset SHA256: "+data["archive_sha256"],"",
        "## Model files",
        "| Model | Tris | Vertices | Animation frames | Embedded skins | Skin resolution | Format |",
        "|---|---:|---:|---:|---:|---|---|"]
    for name in BODY+DOG:
        m=data["model"].get(name,{})
        md.append("| {} | {} | {} | {} | {} | {}x{} | {} v{} |".format(
            name,m.get("triangles","?"),m.get("vertices","?"),m.get("frames","?"),
            m.get("skins","?"),m.get("width","?"),m.get("height","?"),
            m.get("format","MISSING"),m.get("version","?")))
    md+=["","## External skin files","| Path | Dimensions | Bytes |","|---|---|---:|"]
    for path,t in data["skin_images"].items():
        md.append("| {} | {}x{} | {} |".format(path,t.get("width","?"),t.get("height","?"),t["bytes"]))
    md+=["","## Gameplay animation and AI source files",
         "| Type | QuakeC lines | Explicit frame assignments | Largest direct frame index |",
         "|---|---:|---:|---:|"]
    for name,t in data["quakec"].items():
        md.append("| {} | {} | {} | {} |".format(name,t["lines"],t["frame_statements"],t["max_direct_frame_index"]))
    md+=["","## QuakeC vs binary animation frame range","| Model | Frames | Largest index | In range? |","|---|---:|---:|---|"]
    for name,t in data["index_checks"].items():
        md.append("| {} | {} | {} | {} |".format(name,t["model_frames"],t["highest_explicit_frame"],t["in_range"]))
    md+=["","## Audio","Zombies: {} WAV; Hellhounds: {} WAV".format(data["sounds"]["zombie"],data["sounds"]["hound"]),
          "","## Structural observations",
          "- Quake alias IDPO v6 models are frame-animated meshes, not skinned skeletal rigs.",
          "- In source QuakeC, stock zombie body, head, left and right arm are separate detachable entities.",
          "- Stock zombie appearance randomly chooses skin index 0, 1, 2, 3, not four different skeletons.",
          "- Crawler conversion switches to separate crawler-form body/head/arm meshes.",
          "- Hellhound uses a separate model, lightning spawn effect and model animation.",
          "- Rendering throughput, lighting and interpolation require live Android visual and FPS tests.",
          "- Mutable release tag newest is fingerprinted with SHA256, not guaranteed identical forever.",
          "","## Warnings"]+[("- "+w) for w in data["warnings"]]
    (dest/"nzp-zombie-graphics.md").write_text("\n".join(md)+"\n")
    print("NZP_ZOMBIE_GRAPHICS_SUMMARY",json.dumps(data["summary"],sort_keys=True))
    for key,m in data["model"].items():
        print("NZP_ZOMBIE_MDL",key,"tris",m.get("triangles"),
              "verts",m.get("vertices"),"frames",m.get("frames"),
              "skins",m.get("skins"),"pixels",str(m.get("width"))+"x"+str(m.get("height")))
    print("NZP_ZOMBIE_GRAPHICS_READONLY_AUDIT_DONE")
if __name__=="__main__":main()

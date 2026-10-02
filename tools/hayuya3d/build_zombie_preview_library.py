#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def run(cmd:list[str])->None:
    print("HAYUYA_RUN",json.dumps(cmd))
    subprocess.run(cmd,check=True)


def blender_export(blend:Path,out:Path)->None:
    out.parent.mkdir(parents=True,exist_ok=True)
    expr=(
        "import bpy, pathlib;"
        f"out=pathlib.Path({str(out)!r}).resolve();"
        "bpy.ops.export_scene.gltf("
        "filepath=str(out),export_format='GLB',export_animations=True,"
        "export_skins=True,export_nla_strips=True,export_yup=True);"
        "print('HAYUYA_PREVIEW_EXPORT',out)"
    )
    run(["blender","-b",str(blend),"--python-expr",expr])


def inspect_model(model:Path,report:Path,inspector:Path)->dict:
    report.parent.mkdir(parents=True,exist_ok=True)
    run([
        "blender","-b","--python",str(inspector),"--",
        "--input",str(model),"--json",str(report),
    ])
    return json.loads(report.read_text(encoding="utf-8"))


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--characters",type=Path,required=True)
    p.add_argument("--monsters",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--inspector",type=Path,default=Path("tools/hayuya3d/blender_asset_inspector.py"))
    a=p.parse_args()

    if not a.characters.exists() or not a.monsters.exists():
        raise SystemExit("required CC0 archives are missing")

    if a.out.exists():
        shutil.rmtree(a.out)
    (a.out/"models").mkdir(parents=True)
    (a.out/"reports").mkdir(parents=True)

    with tempfile.TemporaryDirectory(prefix="hayuya-zpreview-") as td:
        tmp=Path(td)
        chars=tmp/"chars"; monsters=tmp/"monsters"
        chars.mkdir(); monsters.mkdir()
        with zipfile.ZipFile(a.characters) as z:z.extractall(chars)
        with zipfile.ZipFile(a.monsters) as z:z.extractall(monsters)

        selected=[]
        for name in ("Zombie_Male.blend","Zombie_Female.blend"):
            hit=next(chars.rglob(name),None)
            if hit:selected.append((hit,Path(name).stem,"quaternius_animated_characters"))
        skel=next(monsters.rglob("Skeleton.blend"),None)
        if skel:selected.append((skel,"Skeleton","quaternius_animated_monsters"))
        if len(selected)<2:
            raise SystemExit(f"not enough preview sources found: {selected}")

        assets=[]
        for blend,label,pack in selected:
            glb=a.out/"models"/f"{label}.glb"
            report=a.out/"reports"/f"{label}.json"
            blender_export(blend,glb)
            d=inspect_model(glb,report,a.inspector)
            assets.append({
                "id":label.lower(),
                "label":label.replace("_"," "),
                "preview_model":str(glb).replace("\\","/"),
                "actions":d.get("actions",[]),
                "action_count":d.get("action_count",0),
                "armature_count":d.get("armature_count",0),
                "animation_capable":bool(d.get("animation_capable",False)),
                "license":"CC0",
                "availability":"local",
                "source_pack":pack,
            })

    inv={"schema":1,"id":"hayuya_zombie_preview_models_v1","assets":assets}
    (a.out/"inventory.json").write_text(json.dumps(inv,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_ZOMBIE_PREVIEW_COUNT",len(assets))
    print(json.dumps(inv,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

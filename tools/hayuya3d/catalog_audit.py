#!/usr/bin/env python3
from __future__ import annotations
import json, re, struct, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
AUDIO=ROOT/"hayuya/library/zombie_audio.json"
ANIMS=ROOT/"hayuya/library/zombie_animations.json"
MOTION=ROOT/"hayuya/library/procedural_motion.json"
ADDONS=ROOT/"hayuya/library/character_addons.json"
BANKS={
    "quaternius-uam1":ROOT/"hayuya/animation_library/quaternius-uam1/library.glb",
    "quaternius-uam2":ROOT/"hayuya/animation_library/quaternius-uam2/library.glb",
}
AUDIO_EXT={".wav",".ogg",".mp3",".flac",".m4a",".aac"}

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def glb_animation_names(path):
    blob=path.read_bytes()
    if len(blob)<20 or blob[:4]!=b"glTF":
        raise ValueError(f"invalid GLB:{path}")
    version,total=struct.unpack_from("<II",blob,4)
    if version!=2 or total>len(blob):
        raise ValueError(f"invalid GLB header:{path}")
    off=12
    while off+8<=total:
        ln,typ=struct.unpack_from("<II",blob,off);off+=8
        data=blob[off:off+ln];off+=ln
        if typ==0x4E4F534A:
            doc=json.loads(data.rstrip(b"\x00 \t\r\n").decode("utf-8"))
            return {str(a.get("name") or f"clip_{i}") for i,a in enumerate(doc.get("animations",[]) or [])}
    raise ValueError(f"GLB JSON missing:{path}")

def clean_label(label):
    return bool(label and label.strip() and "_" not in label and not re.search(r"\.(wav|ogg|mp3|flac|glb|fbx)$",label,re.I))

def require(ok,msg,errors):
    if not ok: errors.append(msg)

def audit():
    errors=[]; warnings=[]; summary={}
    audio=load_json(AUDIO)
    audio_ids=set(); audio_files=set(); audio_count=0; pools=0
    for cat in audio.get("categories",[]):
        require(clean_label(cat.get("label")),"audio category label is not human-readable:"+str(cat.get("label")),errors)
        for pool in cat.get("subcategories",[]):
            pools+=1
            pid=str(pool.get("id") or "")
            require(pid and pid not in audio_ids,f"duplicate/empty audio id:{pid}",errors);audio_ids.add(pid)
            require(clean_label(pool.get("label")),f"audio pool label is not human-readable:{pid}:{pool.get('label')}",errors)
            files=list(pool.get("files") or [])
            require(files,f"audio pool has no files:{pid}",errors)
            require(int(pool.get("count",len(files)))==len(files),f"audio count mismatch:{pid}",errors)
            for rel in files:
                audio_count+=1
                p=ROOT/rel
                require(rel not in audio_files,f"duplicate audio file reference:{rel}",errors);audio_files.add(rel)
                require(p.is_file(),f"missing audio file:{rel}",errors)
                if p.is_file():
                    require(p.stat().st_size>=1024,f"audio file too small:{rel}:{p.stat().st_size}",errors)
                require(p.suffix.lower() in AUDIO_EXT,f"unsupported audio extension:{rel}",errors)
    summary["audio"]={"pools":pools,"files":audio_count,"errors":len(errors)}

    anim=load_json(ANIMS)
    bank_names={k:glb_animation_names(v) for k,v in BANKS.items()}
    anim_ids=set(); clips=0; local_clips=0
    for group in anim.get("groups",[]):
        for cat in group.get("categories",[]):
            for item in cat.get("items",[]):
                iid=str(item.get("id") or "")
                require(iid and iid not in anim_ids,f"duplicate/empty animation id:{iid}",errors);anim_ids.add(iid)
                require(clean_label(item.get("label")),f"animation label is not human-readable:{iid}:{item.get('label')}",errors)
                clip=item.get("clip")
                if clip:
                    clips+=1
                    source=str(item.get("source") or "").lower()
                    if item.get("availability")=="local":
                        local_clips+=1
                        if source in bank_names:
                            require(clip in bank_names[source],f"animation clip missing from {source}:{iid}:{clip}",errors)
                        elif item.get("local_path"):
                            require((ROOT/item["local_path"]).is_file(),f"local animation path missing:{iid}:{item['local_path']}",errors)
                        else:
                            warnings.append(f"local animation has no known bank/path:{iid}")
                lp=item.get("local_path")
                if lp: require((ROOT/lp).is_file(),f"missing local animation file:{iid}:{lp}",errors)
                la=item.get("local_archive_path")
                if la: require((ROOT/la).exists(),f"missing local source archive:{iid}:{la}",errors)
    summary["animations"]={"items":len(anim_ids),"clips":clips,"local_clips":local_clips,
                           "uam1_bank_clips":len(bank_names["quaternius-uam1"]),
                           "uam2_bank_clips":len(bank_names["quaternius-uam2"])}

    motion=load_json(MOTION)
    motion_ids=set(); motion_items=0
    allowed_systems={"vertex_wind","transform_channels","mechanical_skeleton"}
    for cat in motion.get("categories",[]):
        for item in cat.get("items",[]):
            motion_items+=1
            iid=str(item.get("id") or "")
            require(iid and iid not in motion_ids,f"duplicate/empty motion id:{iid}",errors);motion_ids.add(iid)
            require(clean_label(item.get("label")),f"motion label is not human-readable:{iid}:{item.get('label')}",errors)
            require(item.get("system") in allowed_systems,f"unsupported motion system:{iid}:{item.get('system')}",errors)
            require(bool(item.get("profiles")),f"motion has no compatible profiles:{iid}",errors)
            require(isinstance(item.get("params"),dict),f"motion params missing:{iid}",errors)
    summary["motion"]={"items":motion_items}

    addons=load_json(ADDONS)
    addon_ids=set(); addon_items=0
    for cat in addons.get("categories",[]):
        for item in cat.get("items",[]):
            addon_items+=1
            iid=str(item.get("id") or "")
            require(iid and iid not in addon_ids,f"duplicate/empty addon id:{iid}",errors);addon_ids.add(iid)
            require(clean_label(item.get("label")),f"addon label is not human-readable:{iid}:{item.get('label')}",errors)
            require(bool(item.get("type")),f"addon type missing:{iid}",errors)
    summary["addons"]={"items":addon_items}

    # Pipeline regression contracts. These protect failures that can otherwise
    # look visually catastrophic while a Blender workflow still appears green.
    autorig_path=ROOT/"tools/hayuya3d/blender_autorig.py"
    autorig_source=autorig_path.read_text(encoding="utf-8")
    retarget_init=autorig_source.find('animation_retarget={')
    retarget_report=autorig_source.find('"animation_retarget":animation_retarget')
    require(retarget_init>=0,"autorig rotation-only animation_retarget initialization missing",errors)
    require(retarget_report>=0,"autorig animation_retarget report field missing",errors)
    require(retarget_init>=0 and retarget_report>retarget_init,
            "autorig animation_retarget used before initialization",errors)
    require("rotation_only_on_fitted_rest" in autorig_source,
            "autorig no longer declares fitted-rest rotation-only retarget",errors)

    protected_workflows=[
        ".github/workflows/hayuya-rig-request.yml",
        ".github/workflows/hayuya-queue.yml",
        ".github/workflows/hayuya-autorig-prototype.yml",
        ".github/workflows/hayuya-character-package.yml",
    ]
    blender_contract={}
    for rel in protected_workflows:
        wf=(ROOT/rel).read_text(encoding="utf-8")
        guarded=sum(
            wf.count("blender --python-exit-code 1 -b --python "+script)
            for script in (
                "tools/hayuya3d/blender_autorig.py",
                "tools/hayuya3d/blender_animation_gate.py",
            )
        )
        unsafe=sum(
            wf.count("blender -b --python "+script)
            for script in (
                "tools/hayuya3d/blender_autorig.py",
                "tools/hayuya3d/blender_animation_gate.py",
            )
        )
        require(guarded>0,f"no fail-fast Blender Python calls found:{rel}",errors)
        require(unsafe==0,f"unsafe Blender Python call can hide traceback:{rel}",errors)
        blender_contract[rel]={"guarded_calls":guarded,"unsafe_calls":unsafe}
    summary["pipeline_contract"]={
        "rotation_only_retarget":retarget_init>=0 and retarget_report>retarget_init,
        "blender_fail_fast":blender_contract,
    }

    summary["warnings"]=warnings
    summary["error_count"]=len(errors)
    summary["errors"]=errors
    print(json.dumps(summary,indent=2))
    return 1 if errors else 0

if __name__=="__main__":
    raise SystemExit(audit())

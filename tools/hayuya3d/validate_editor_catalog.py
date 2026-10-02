#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT=Path(".")
ANIM=ROOT/"hayuya/library/zombie_animations.json"
AUDIO=ROOT/"hayuya/library/zombie_audio.json"
ADDONS=ROOT/"hayuya/library/character_addons.json"

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def main() -> int:
    errors=[]
    warnings=[]

    anim=load(ANIM)
    audio=load(AUDIO)
    addons=load(ADDONS)

    sources={}
    for source,path in {
        "quaternius-uam1":ROOT/"hayuya/animation_library/quaternius-uam1/rig_gate.json",
        "quaternius-uam2":ROOT/"hayuya/animation_library/quaternius-uam2/rig_gate.json",
        "quaternius-human-rigged":ROOT/"hayuya/models/hayuya-rig-test/manifest.json",
    }.items():
        if not path.exists():
            warnings.append(f"missing_optional_source_manifest:{source}:{path}")
            continue
        data=load(path)
        if source=="quaternius-human-rigged":
            clips=set((data.get("character") or {}).get("animation_clips",[]))
        else:
            clips=set(data.get("animation_clips",[]))
        sources[source]=clips

    seen_ids=set()
    local_anim=0
    pending_anim=0
    external_anim=0
    for group in anim.get("groups",[]):
        for cat in group.get("categories",[]):
            for item in cat.get("items",[]):
                iid=item.get("id")
                if not iid:
                    errors.append(f"animation_missing_id:{group.get('id')}:{cat.get('id')}")
                    continue
                if iid in seen_ids:
                    errors.append(f"duplicate_animation_id:{iid}")
                seen_ids.add(iid)
                availability=item.get("availability","local")
                clip=item.get("clip")
                source=item.get("source")
                if availability=="local":
                    local_anim+=1
                    if not clip:
                        # Library-level pack cards are allowed to be local without one clip.
                        if item.get("one_tap_ready"):
                            errors.append(f"one_tap_animation_missing_clip:{iid}")
                    elif source in sources and clip not in sources[source]:
                        errors.append(f"local_clip_missing_from_source:{iid}:{source}:{clip}")
                elif availability=="local_mapping_pending":
                    pending_anim+=1
                    if clip and source in sources and clip not in sources[source]:
                        errors.append(f"pending_clip_missing_from_source:{iid}:{source}:{clip}")
                else:
                    external_anim+=1
                    if item.get("one_tap_ready"):
                        errors.append(f"external_marked_one_tap:{iid}:{availability}")

    audio_files=0
    audio_pools=0
    seen_audio_ids=set()
    for cat in audio.get("categories",[]):
        for pool in cat.get("subcategories",[]):
            audio_pools+=1
            pid=pool.get("id")
            if not pid:
                errors.append(f"audio_pool_missing_id:{cat.get('id')}")
                continue
            if pid in seen_audio_ids:
                errors.append(f"duplicate_audio_pool_id:{pid}")
            seen_audio_ids.add(pid)
            files=pool.get("files") or []
            if not files:
                errors.append(f"audio_pool_empty:{pid}")
            if "count" in pool and int(pool["count"])!=len(files):
                errors.append(f"audio_count_mismatch:{pid}:{pool.get('count')}!={len(files)}")
            for raw in files:
                audio_files+=1
                p=ROOT/raw
                if not p.is_file():
                    errors.append(f"audio_missing:{pid}:{raw}")

    addon_ids=set()
    for cat in addons.get("categories",[]):
        for item in cat.get("items",[]):
            iid=item.get("id")
            if not iid:
                errors.append(f"addon_missing_id:{cat.get('id')}")
            elif iid in addon_ids:
                errors.append(f"duplicate_addon_id:{iid}")
            else:
                addon_ids.add(iid)

    report={
        "passed":not errors,
        "animation_items":len(seen_ids),
        "local_animation_items":local_anim,
        "retarget_pending_animation_items":pending_anim,
        "external_animation_items":external_anim,
        "audio_pools":audio_pools,
        "audio_file_references":audio_files,
        "addon_items":len(addon_ids),
        "errors":errors,
        "warnings":warnings,
    }
    print(json.dumps(report,indent=2))
    if errors:
        raise SystemExit(2)
    print("HAYUYA_EDITOR_CATALOG_PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())

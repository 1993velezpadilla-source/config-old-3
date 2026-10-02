#!/usr/bin/env python3
from __future__ import annotations

import shutil
import tempfile
from dataclasses import asdict,dataclass
from pathlib import Path


@dataclass
class RigPreservingRebakeResult:
    source_mesh:str
    target_mesh:str
    output_glb:str
    requested_channels:list[str]
    resolved_channels:list[str]
    remaining_channels:list[str]
    skin_payload_preserved:bool
    rig_preserved:bool
    skin_weights_ready:bool
    ready:bool
    blender_report:str|None=None
    error:str|None=None
    method:str="hayuya-rig-preserving-material-rebake-v1"


_ROLE_BY_CHANNEL={
    "normal":"normal",
    "occlusion":"occlusion",
}


def _role_images(path:Path,role:str)->list[tuple[int,str,bytes]]:
    from texture_gate import embedded_images
    out=[]
    for index,mime,data,roles in embedded_images(path):
        if role in set(roles or []):
            out.append((int(index),str(mime),data))
    return sorted(out,key=lambda item:item[0])


def rebake_material_channels_preserve_rig(
    source_mesh:Path,
    target_mesh:Path,
    output_glb:Path,
    *,
    required:list[str]|tuple[str,...]|set[str],
    max_texture_size:int,
    blender:str|Path|None=None,
)->RigPreservingRebakeResult:
    requested=sorted({
        str(channel)
        for channel in required
        if str(channel) in _ROLE_BY_CHANNEL
    })
    if not requested:
        output_glb.parent.mkdir(parents=True,exist_ok=True)
        if target_mesh.resolve()!=output_glb.resolve():
            shutil.copy2(target_mesh,output_glb)
        return RigPreservingRebakeResult(
            source_mesh=str(source_mesh),
            target_mesh=str(target_mesh),
            output_glb=str(output_glb),
            requested_channels=[],
            resolved_channels=[],
            remaining_channels=[],
            skin_payload_preserved=True,
            rig_preserved=True,
            skin_weights_ready=True,
            ready=True,
        )

    try:
        from gltf_audit import audit_glb
        from gltf_position_patch import skin_payload_signature
        from skin_weight_qa import audit_skin_weights

        before_rig=audit_glb(target_mesh)
        before_skin=audit_skin_weights(target_mesh)
        before_signature=skin_payload_signature(target_mesh)
        if before_rig.skin_count<=0 or not before_rig.rig_ready:
            raise RuntimeError("target is not a validated rigged GLB")
        if not before_skin.applicable or not before_skin.ready:
            raise RuntimeError("target skin weights are not valid before rebake")

        with tempfile.TemporaryDirectory(prefix="hayuya-rig-rebake-") as tmp:
            root=Path(tmp)
            baked=root/"blender_rebaked.glb"

            from material_rebake import rebake_material_channels
            rebake=rebake_material_channels(
                source_mesh,
                target_mesh,
                baked,
                required=requested,
                max_texture_size=max_texture_size,
                blender=blender,
            )
            unresolved=sorted(set(requested)-set(rebake.resolved_channels))
            if unresolved:
                raise RuntimeError(
                    "Blender rebake did not resolve: "+",".join(unresolved)
                )

            replacements={}
            for channel in requested:
                role=_ROLE_BY_CHANNEL[channel]
                target_images=_role_images(target_mesh,role)
                baked_images=_role_images(baked,role)
                if not target_images:
                    raise RuntimeError(
                        f"target has no embedded {role} image to replace"
                    )
                if len(target_images)!=len(baked_images):
                    raise RuntimeError(
                        f"{role} image cardinality changed during rebake: "
                        f"{len(target_images)}->{len(baked_images)}"
                    )
                for target_item,baked_item in zip(target_images,baked_images):
                    target_index=target_item[0]
                    _,mime,data=baked_item
                    replacements[target_index]=(mime,data)

            from glb_images import replace_embedded_images
            replace_embedded_images(
                target_mesh,
                output_glb,
                replacements,
            )

        after_signature=skin_payload_signature(output_glb)
        skin_preserved=before_signature==after_signature
        after_rig=audit_glb(output_glb)
        after_skin=audit_skin_weights(output_glb)
        rig_preserved=bool(
            after_rig.rig_ready
            and before_rig.skin_count==after_rig.skin_count
            and before_rig.skinned_mesh_nodes==after_rig.skinned_mesh_nodes
            and before_rig.joint_count==after_rig.joint_count
            and before_rig.animation_count==after_rig.animation_count
        )
        skin_ready=bool(after_skin.applicable and after_skin.ready)

        from qa import inspect_mesh
        inspected=inspect_mesh(
            output_glb,
            backend="rig_preserving_rebake_verify",
            mode="character",
            target_faces=1,
        )
        channels=set(inspected.pbr_channels or [])
        remaining=[
            channel
            for channel in requested
            if channel not in channels
        ]
        ready=bool(
            not remaining
            and skin_preserved
            and rig_preserved
            and skin_ready
        )
        error=None
        if not ready:
            reasons=[]
            if remaining:
                reasons.append("missing_channels:"+",".join(remaining))
            if not skin_preserved:
                reasons.append("skin_payload_changed")
            if not rig_preserved:
                reasons.append("rig_structure_changed")
            if not skin_ready:
                reasons.append("skin_weight_audit_failed")
            error=";".join(reasons)

        return RigPreservingRebakeResult(
            source_mesh=str(source_mesh),
            target_mesh=str(target_mesh),
            output_glb=str(output_glb),
            requested_channels=requested,
            resolved_channels=sorted(set(requested)-set(remaining)),
            remaining_channels=remaining,
            skin_payload_preserved=skin_preserved,
            rig_preserved=rig_preserved,
            skin_weights_ready=skin_ready,
            ready=ready,
            blender_report=rebake.report,
            error=error,
        )
    except Exception as exc:
        if target_mesh.resolve()!=output_glb.resolve():
            output_glb.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target_mesh,output_glb)
        return RigPreservingRebakeResult(
            source_mesh=str(source_mesh),
            target_mesh=str(target_mesh),
            output_glb=str(output_glb),
            requested_channels=requested,
            resolved_channels=[],
            remaining_channels=requested,
            skin_payload_preserved=False,
            rig_preserved=False,
            skin_weights_ready=False,
            ready=False,
            error=f"{type(exc).__name__}:{exc}",
        )

#!/usr/bin/env python3
"""HAYUYA Blender AutoRig prototype.

Run with:
  blender -b --python tools/hayuya3d/blender_autorig.py -- \
    --target static.glb --donor donor.glb --output rigged.glb --report report.json

P0 strategy:
- import the generated static humanoid
- import the CC0 Quaternius animated donor
- fit the donor armature to the target's overall height/center
- discard donor render meshes
- bind target meshes to the armature with Blender automatic weights
- preserve donor animation actions and export a skinned/animated GLB

This is intentionally a first-pass autorig stage. Later revisions can replace
bounds fitting with landmark/body-part fitting without changing the pipeline API.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Quaternion
from mathutils.kdtree import KDTree


def parse_args():
    argv=sys.argv
    if "--" in argv:
        argv=argv[argv.index("--")+1:]
    else:
        argv=[]
    p=argparse.ArgumentParser()
    p.add_argument("--target",required=True,type=Path)
    p.add_argument("--donor",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    return p.parse_args(argv)


def world_bbox(objects):
    pts=[]
    for obj in objects:
        if obj.type!="MESH":
            continue
        for corner in obj.bound_box:
            pts.append(obj.matrix_world @ Vector(corner))
    if not pts:
        raise RuntimeError("no mesh bounds")
    mins=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    maxs=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return mins,maxs


def height_axis(ext):
    vals=[abs(ext.x),abs(ext.y),abs(ext.z)]
    return max(range(3),key=lambda i:vals[i])


def axis_value(v,axis):
    return (v.x,v.y,v.z)[axis]


def import_glb(path):
    before=set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path.resolve()))
    return [o for o in bpy.data.objects if o not in before]


def select_only(*objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    if objects:
        bpy.context.view_layer.objects.active=objects[-1]


def main():
    args=parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)

    target_objs=import_glb(args.target)
    target_meshes=[o for o in target_objs if o.type=="MESH"]
    if not target_meshes:
        raise RuntimeError("target GLB has no meshes")

    target_min,target_max=world_bbox(target_meshes)
    target_ext=target_max-target_min
    target_axis=height_axis(target_ext)
    target_height=axis_value(target_ext,target_axis)
    if target_height<=1e-6:
        raise RuntimeError("target height is degenerate")

    donor_objs=import_glb(args.donor)
    donor_object_names={o.name for o in donor_objs}
    donor_meshes=[o for o in donor_objs if o.type=="MESH"]
    donor_arms=[o for o in donor_objs if o.type=="ARMATURE"]
    if len(donor_arms)!=1:
        raise RuntimeError(f"expected one donor armature, got {len(donor_arms)}")
    arm=donor_arms[0]

    # Donor rigs may carry Blender-only controller/custom-shape objects such as
    # "Icosphere". glTF can follow those armature dependencies even when the
    # render mesh selection contains only the generated target. That was the
    # hidden second mesh behind the giant sphere/slab-looking preview. Remove
    # every pose-bone custom-shape reference before export.
    custom_shape_names=set()
    if arm.pose:
        for pbone in arm.pose.bones:
            shape=getattr(pbone,"custom_shape",None)
            if shape is not None:
                custom_shape_names.add(shape.name)
                pbone.custom_shape=None

    # Controller/custom-shape meshes are NOT body geometry. They must be
    # excluded before calculating donor proportions and before sampling donor
    # skin data. Including Rigify's Icosphere made the donor look ~2.83m tall
    # and ~2m wide, compressing the fitted skeleton into the target's legs.
    donor_meshes_all=list(donor_meshes)
    donor_meshes=[o for o in donor_meshes if o.name not in custom_shape_names]
    if not donor_meshes:
        raise RuntimeError("donor_has_no_render_mesh_after_control_shape_filter")
    excluded_donor_meshes=sorted(o.name for o in donor_meshes_all if o not in donor_meshes)

    donor_set=set(donor_objs)
    donor_roots=[o for o in donor_objs if o.parent not in donor_set]
    if not donor_roots:
        donor_roots=[arm]
    donor_root_names=[o.name for o in donor_roots]

    # HUMANOID ORIENTATION AUTHORITY: anatomy, never bounding-box major axis.
    # A T-pose can be wider than it is tall, so "longest bbox axis == up" is
    # invalid. Head - pelvis defines the anatomical up vector.
    head_bone=next((b for b in arm.data.bones if "head" in b.name.lower()),None)
    pelvis_bone=next((b for b in arm.data.bones if any(k in b.name.lower() for k in ("pelvis","hips"))),None)
    if head_bone is None or pelvis_bone is None:
        raise RuntimeError("cannot_determine_anatomical_up:missing_head_or_pelvis")

    def bone_mid_world(bone):
        return arm.matrix_world @ ((bone.head_local+bone.tail_local)*0.5)

    head_world_before=bone_mid_world(head_bone)
    pelvis_world_before=bone_mid_world(pelvis_bone)
    anatomical_up=head_world_before-pelvis_world_before
    if anatomical_up.length<=1e-6:
        raise RuntimeError("cannot_determine_anatomical_up:degenerate_head_pelvis_vector")
    anatomical_up.normalize()

    target_up=Vector((0.0,0.0,0.0))
    target_up[target_axis]=1.0
    alignment_before=float(anatomical_up.dot(target_up))
    rotation=anatomical_up.rotation_difference(target_up).to_matrix().to_4x4()

    # Rotate each top-level donor root exactly once so armature and any donor
    # render geometry keep the same spatial relationship.
    if alignment_before < 0.999:
        for root in donor_roots:
            root.matrix_world=rotation @ root.matrix_world
        bpy.context.view_layer.update()

    head_world_after=bone_mid_world(head_bone)
    pelvis_world_after=bone_mid_world(pelvis_bone)
    anatomical_after=head_world_after-pelvis_world_after
    if anatomical_after.length<=1e-6:
        raise RuntimeError("anatomical_up_degenerate_after_rotation")
    anatomical_after.normalize()
    alignment_after=float(anatomical_after.dot(target_up))
    if alignment_after < 0.985:
        raise RuntimeError(
            f"anatomical_orientation_failed:alignment={alignment_after:.6f}"
        )

    donor_min,donor_max=world_bbox(donor_meshes)
    donor_ext=donor_max-donor_min
    # Height means extent along the TARGET anatomical up axis. It does not
    # matter if arm span is larger than body height.
    donor_height=axis_value(donor_ext,target_axis)
    if donor_height<=1e-6:
        raise RuntimeError("donor height is degenerate after anatomical orientation")

    orientation_fix={
        "method":"head_minus_pelvis",
        "applied":alignment_before < 0.999,
        "target_axis":target_axis,
        "alignment_before":alignment_before,
        "alignment_after":alignment_after,
        "head_before":[float(x) for x in head_world_before],
        "pelvis_before":[float(x) for x in pelvis_world_before],
        "head_after":[float(x) for x in head_world_after],
        "pelvis_after":[float(x) for x in pelvis_world_after],
        "bbox_major_axis_after":height_axis(donor_ext),
        "body_height_on_target_axis":donor_height,
    }

    scale=target_height/donor_height
    target_ext_values=(abs(target_ext.x),abs(target_ext.y),abs(target_ext.z))
    donor_ext_values=(abs(donor_ext.x),abs(donor_ext.y),abs(donor_ext.z))
    requested_axis_scales=[]
    for axis in range(3):
        if axis==target_axis:
            value=scale
        else:
            raw=target_ext_values[axis]/max(1e-8,donor_ext_values[axis])
            value=max(scale*0.55,min(scale*1.80,raw))
        requested_axis_scales.append(value)

    # Never apply anisotropic object scale to an animated armature. A fitted
    # skeleton with X/Y/Z scales such as 0.30/0.91/0.54 can create shear when
    # donor rotations are evaluated, even after transform_apply(). Fit the
    # skeleton uniformly by anatomical height; surface proportions are handled
    # by the skin-weight solver, not by distorting the armature basis.
    axis_scales=[scale,scale,scale]
    fit_scale=Vector((scale,scale,scale))

    for root in donor_roots:
        root.scale=Vector((
            root.scale.x*fit_scale.x,
            root.scale.y*fit_scale.y,
            root.scale.z*fit_scale.z,
        ))
    bpy.context.view_layer.update()

    dmin2,dmax2=world_bbox(donor_meshes)
    target_center=(target_min+target_max)*0.5
    donor_center=(dmin2+dmax2)*0.5
    offset=target_center-donor_center

    # Preserve horizontal centering but align the feet/floor on the vertical
    # axis.  This is much safer than center-only fitting for robes, long hair
    # and other asymmetric silhouettes.
    desired_floor=axis_value(target_min,target_axis)
    current_floor=axis_value(dmin2,target_axis)
    # Center on the two horizontal axes; on the height axis, align floors.
    if target_axis==0:
        offset.x = desired_floor-current_floor
    elif target_axis==1:
        offset.y = desired_floor-current_floor
    else:
        offset.z = desired_floor-current_floor

    for root in donor_roots:
        root.location += offset
    bpy.context.view_layer.update()

    arm.name="HAYUYA_Armature"

    # Build a spatial weight donor from the already-rigged CC0 character.
    # Use blended nearest-neighbour weights (instead of ONE nearest donor
    # vertex), preserve left/right body side, and cap at four influences.
    # This keeps shoulders, arms, neck and face from inheriting torso weights.
    arm_bones={b.name for b in arm.data.bones}
    samples=[]
    donor_min_fit,donor_max_fit=world_bbox(donor_meshes)
    donor_center_fit=(donor_min_fit+donor_max_fit)*0.5
    target_center_fit=(target_min+target_max)*0.5
    non_height=[i for i in range(3) if i!=target_axis]

    def explicit_side_tag(name):
        n=str(name or "").lower()
        if n.endswith(".l") or n.endswith("_l") or ".l." in n or "_left" in n or n.startswith("left"):
            return -1
        if n.endswith(".r") or n.endswith("_r") or ".r." in n or "_right" in n or n.startswith("right"):
            return 1
        return 0

    # Anatomical lateral-axis authority: derive left/right from the skeleton,
    # never from whichever horizontal bbox extent happens to be larger. V24/25
    # picked target Y as "width" for Zombitest1 because its depth slightly
    # exceeded X, turning front/back into left/right and poisoning side filters.
    left_midpoints=[]
    right_midpoints=[]
    for bone in arm.data.bones:
        tag=explicit_side_tag(bone.name)
        if not tag:
            continue
        mid=arm.matrix_world @ ((bone.head_local+bone.tail_local)*0.5)
        (left_midpoints if tag<0 else right_midpoints).append(mid)
    if not left_midpoints or not right_midpoints:
        raise RuntimeError(
            f"cannot_determine_anatomical_lateral_axis:left={len(left_midpoints)},right={len(right_midpoints)}"
        )
    left_center=sum(left_midpoints,Vector((0.0,0.0,0.0)))/len(left_midpoints)
    right_center=sum(right_midpoints,Vector((0.0,0.0,0.0)))/len(right_midpoints)
    lateral_vector=right_center-left_center
    width_axis=max(non_height,key=lambda i:abs((lateral_vector.x,lateral_vector.y,lateral_vector.z)[i]))
    lateral_component=abs((lateral_vector.x,lateral_vector.y,lateral_vector.z)[width_axis])
    if lateral_component <= max(1e-6,target_height*0.01):
        raise RuntimeError(
            "anatomical_lateral_axis_degenerate:"
            +json.dumps({"vector":list(lateral_vector),"axis":width_axis})
        )
    lateral_axis_telemetry={
        "method":"named_lr_bone_centroids_v27",
        "axis":width_axis,
        "vector":[float(x) for x in lateral_vector],
        "left_samples":len(left_midpoints),
        "right_samples":len(right_midpoints),
        "target_horizontal_extents":[float((target_ext.x,target_ext.y,target_ext.z)[i]) for i in non_height],
    }

    def coord_axis(v,axis):
        return (v.x,v.y,v.z)[axis]

    def side_of(co,center,axis):
        delta=coord_axis(co,axis)-coord_axis(center,axis)
        width=max(1e-8,abs((target_ext.x,target_ext.y,target_ext.z)[axis]))
        if abs(delta)/width < 0.04:
            return 0
        return -1 if delta < 0 else 1

    def remap_target_to_donor_space(world):
        # Map the generated target into the donor's normalized body envelope.
        # This is deliberately independent of the donor's absolute world
        # placement. A nearest-neighbour lookup in raw world space can collapse
        # most target vertices onto feet/calves when a generated silhouette has
        # very different robe/hair proportions.
        tv=(world.x,world.y,world.z)
        tmin=(target_min.x,target_min.y,target_min.z)
        text=(target_ext.x,target_ext.y,target_ext.z)
        dmin=(donor_min_fit.x,donor_min_fit.y,donor_min_fit.z)
        dext=((donor_max_fit-donor_min_fit).x,(donor_max_fit-donor_min_fit).y,(donor_max_fit-donor_min_fit).z)
        vals=[]
        for axis in range(3):
            n=(tv[axis]-tmin[axis])/max(1e-8,text[axis])
            n=max(0.0,min(1.0,n))
            vals.append(dmin[axis]+n*dext[axis])
        return Vector(tuple(vals))

    for donor in donor_meshes:
        for v in donor.data.vertices:
            weights=[]
            for g in v.groups:
                if g.group < len(donor.vertex_groups):
                    name=donor.vertex_groups[g.group].name
                    if name in arm_bones and g.weight > 1e-8:
                        weights.append((name,float(g.weight)))
            if not weights:
                continue
            weights.sort(key=lambda x:x[1],reverse=True)
            world=donor.matrix_world @ v.co
            samples.append((world,weights[:4],side_of(world,donor_center_fit,width_axis)))
    if not samples:
        raise RuntimeError("donor rig has no transferable vertex weights")

    kd=KDTree(len(samples))
    for i,(co,_,__) in enumerate(samples):
        kd.insert(co,i)
    kd.balance()

    # Bake the fitted armature OBJECT transform into its rest skeleton before
    # binding the generated target. Leaving a non-identity armature scale/location
    # makes glTF inverse-bind matrices reconstruct the target in donor space on
    # re-import, even though Blender looks correct before export.
    arm_world_before=[list(row) for row in arm.matrix_world]
    select_only(arm)
    bpy.context.view_layer.objects.active=arm
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.context.view_layer.update()
    arm_world_after=[list(row) for row in arm.matrix_world]

    # POSE-AWARE ARM REST FIT.
    #
    # Height-only uniform fitting is correct for the animated armature basis, but
    # a T-pose donor can still place wrists/hands far outside a generated
    # standing character whose source pose has the arms down. Do NOT solve that
    # by anisotropically scaling the armature (that reintroduces shear). Instead,
    # when the target silhouette is narrow AND the fitted donor hand is clearly
    # outside the target lateral envelope, rigidly rotate the entire arm subtree
    # around the upper-arm head. Bone lengths, child offsets and hierarchy remain
    # intact. Existing animation translation/scale curves are removed below, so
    # rotation animation continues to operate on this fitted rest pose.
    arm_rest_fit={
        "schema":1,
        "method":"rigid_arm_subtree_lateral_projection_v2_rest_compensated",
        "applied":False,
        "target_width_height_ratio":0.0,
        "trigger_width_height_ratio_max":0.68,
        "trigger_hand_overhang_min_normalized":0.10,
        "chains":[],
    }
    target_lateral_min=coord_axis(target_min,width_axis)
    target_lateral_max=coord_axis(target_max,width_axis)
    target_lateral_span=max(1e-8,target_lateral_max-target_lateral_min)
    target_width_height_ratio=target_lateral_span/max(1e-8,target_height)
    arm_rest_fit["target_width_height_ratio"]=float(target_width_height_ratio)

    def _find_side_bone_name(side_tag,tokens,exclude=()):
        candidates=[]
        for bone in arm.data.bones:
            n=bone.name.lower()
            if explicit_side_tag(bone.name)!=side_tag:
                continue
            if any(x in n for x in exclude):
                continue
            if any(x in n for x in tokens):
                candidates.append(bone.name)
        if not candidates:
            return None
        # Prefer the shortest canonical-looking name rather than a helper copy.
        return sorted(candidates,key=lambda x:(len(x),x.lower()))[0]

    # For a rigid subtree rotation, every descendant keeps the same local rest
    # transform. Only the upper-arm local rest orientation changes relative to
    # its unchanged parent, so animation compensation belongs on that one bone.
    # Mapping: bone name -> quaternion C where B_new = C * B_old.
    arm_animation_rest_compensation={}

    arm_chain_names=[]
    for side_tag,side_label in ((-1,"left"),(1,"right")):
        upper_name=_find_side_bone_name(
            side_tag,("upper_arm","upperarm"),("twist","helper","ctrl","control","ik")
        )
        hand_name=_find_side_bone_name(
            side_tag,("hand",),("finger","thumb","index","middle","pinky","ring","twist","helper","ctrl","control","ik")
        )
        if upper_name and hand_name:
            arm_chain_names.append((side_tag,side_label,upper_name,hand_name))

    if target_width_height_ratio<=arm_rest_fit["trigger_width_height_ratio_max"] and arm_chain_names:
        select_only(arm)
        bpy.context.view_layer.objects.active=arm
        bpy.ops.object.mode_set(mode="EDIT")
        edit_bones=arm.data.edit_bones
        try:
            for side_tag,side_label,upper_name,hand_name in arm_chain_names:
                upper=edit_bones.get(upper_name)
                hand=edit_bones.get(hand_name)
                if upper is None or hand is None:
                    continue
                pivot=upper.head.copy()
                upper_parent=upper.parent
                old_upper_local=(
                    upper_parent.matrix.inverted() @ upper.matrix
                    if upper_parent is not None
                    else upper.matrix.copy()
                )
                original_endpoint=hand.tail.copy()
                original_vector=original_endpoint-pivot
                original_length=original_vector.length
                if original_length<=1e-6:
                    continue

                shoulder_lateral=coord_axis(pivot,width_axis)
                hand_lateral=coord_axis(original_endpoint,width_axis)
                center_lateral=(target_lateral_min+target_lateral_max)*0.5
                geometric_sign=1.0 if shoulder_lateral>=center_lateral else -1.0
                overhang=max(
                    0.0,
                    hand_lateral-target_lateral_max,
                    target_lateral_min-hand_lateral,
                )
                overhang_norm=overhang/target_lateral_span
                chain_info={
                    "side":side_label,
                    "upper":upper_name,
                    "hand":hand_name,
                    "applied":False,
                    "original_hand_lateral":float(hand_lateral),
                    "original_hand_overhang":float(overhang),
                    "original_hand_overhang_normalized":float(overhang_norm),
                    "shoulder":[float(x) for x in pivot],
                    "original_endpoint":[float(x) for x in original_endpoint],
                }
                if overhang_norm<=arm_rest_fit["trigger_hand_overhang_min_normalized"]:
                    arm_rest_fit["chains"].append(chain_info)
                    continue

                # Keep the terminal hand just inside the observed character
                # envelope. The arm keeps its original total shoulder->hand
                # length; only its rest orientation changes.
                inset=target_lateral_span*0.04
                target_hand_lateral=(
                    target_lateral_max-inset
                    if geometric_sign>0.0
                    else target_lateral_min+inset
                )
                desired_lateral=abs(target_hand_lateral-shoulder_lateral)
                desired_lateral=max(
                    original_length*0.15,
                    min(original_length*0.95,desired_lateral),
                )

                depth_axis=next(
                    axis for axis in range(3)
                    if axis not in (target_axis,width_axis)
                )
                original_depth=coord_axis(original_vector,depth_axis)
                max_depth=math.sqrt(max(0.0,original_length*original_length-desired_lateral*desired_lateral))*0.35
                desired_depth=max(-max_depth,min(max_depth,original_depth))
                vertical_sq=max(
                    1e-10,
                    original_length*original_length
                    - desired_lateral*desired_lateral
                    - desired_depth*desired_depth,
                )
                vertical_drop=math.sqrt(vertical_sq)
                target_vector=Vector((0.0,0.0,0.0))
                target_vector[width_axis]=geometric_sign*desired_lateral
                target_vector[depth_axis]=desired_depth
                target_vector[target_axis]=-vertical_drop

                rotation_delta=original_vector.rotation_difference(target_vector)
                subtree=[]
                stack=[upper]
                seen=set()
                while stack:
                    bone=stack.pop()
                    if bone.name in seen:
                        continue
                    seen.add(bone.name)
                    subtree.append(bone)
                    stack.extend(list(bone.children))

                for bone in subtree:
                    bone.head=pivot+(rotation_delta @ (bone.head-pivot))
                    bone.tail=pivot+(rotation_delta @ (bone.tail-pivot))

                new_upper_local=(
                    upper_parent.matrix.inverted() @ upper.matrix
                    if upper_parent is not None
                    else upper.matrix.copy()
                )
                # Want: Rest_new * Basis_new == Rest_old * Basis_old
                # therefore Basis_new = inverse(Rest_new) * Rest_old * Basis_old.
                compensation_matrix=new_upper_local.inverted() @ old_upper_local
                compensation_quat=compensation_matrix.to_quaternion()
                compensation_quat.normalize()
                arm_animation_rest_compensation[upper_name]=compensation_quat.copy()

                new_endpoint=pivot+target_vector
                chain_info.update({
                    "applied":True,
                    "target_hand_lateral":float(target_hand_lateral),
                    "desired_lateral_reach":float(desired_lateral),
                    "vertical_drop":float(vertical_drop),
                    "rotated_bone_count":len(subtree),
                    "rest_compensation_quaternion":[float(x) for x in compensation_quat],
                    "new_endpoint":[float(x) for x in new_endpoint],
                })
                arm_rest_fit["chains"].append(chain_info)
                arm_rest_fit["applied"]=True
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
            bpy.context.view_layer.update()

    # Retarget donor motion onto the FITTED rest skeleton. Imported glTF
    # animations frequently key local translation/scale on many bones. Once
    # the rest skeleton is resized/repositioned for a generated character,
    # replaying those donor-space offsets pulls joints back toward donor
    # proportions and stretches the skin. Keep rotations only. Locomotion/root
    # translation is owned by the game/clip controller, not by deform bones.
    animation_retarget={
        "method":"rotation_only_on_fitted_rest_v29_rest_compensated",
        "actions":0,
        "removed_location_curves":0,
        "removed_scale_curves":0,
        "kept_rotation_curves":0,
        "kept_other_curves":0,
        "rest_compensated_bones":sorted(arm_animation_rest_compensation),
        "rest_compensated_actions":0,
        "rest_compensated_keyframes":0,
        "rest_compensation_missing_quaternion_channels":[],
    }

    def compensate_quaternion_fcurves(action,bone_name,compensation):
        path=f'pose.bones["{bone_name}"].rotation_quaternion'
        curves={fc.array_index:fc for fc in action.fcurves if fc.data_path==path and 0<=fc.array_index<=3}
        if len(curves)!=4:
            return 0,False
        times=sorted({
            float(kp.co.x)
            for fc in curves.values()
            for kp in fc.keyframe_points
        })
        if not times:
            return 0,True

        # Snapshot before mutating because fcurve.evaluate() reads live points.
        samples=[]
        previous=None
        for frame in times:
            q_old=Quaternion(tuple(float(curves[i].evaluate(frame)) for i in range(4)))
            q_norm_sq=sum(float(v)*float(v) for v in q_old)
            if q_norm_sq<=1e-24:
                q_old=Quaternion((1.0,0.0,0.0,0.0))
            else:
                q_old.normalize()
            q_new=compensation @ q_old
            q_new.normalize()
            # Quaternion q and -q are equivalent, but sign flips between adjacent
            # keys make interpolation take the long path.
            if previous is not None and q_new.dot(previous)<0.0:
                q_new=Quaternion(tuple(-float(v) for v in q_new))
            previous=q_new.copy()
            samples.append((frame,tuple(float(v) for v in q_new)))

        def set_component(fc,frame,value):
            for kp in fc.keyframe_points:
                if abs(float(kp.co.x)-frame)<=1e-6:
                    kp.co.y=value
                    kp.handle_left.y=value
                    kp.handle_right.y=value
                    return
            fc.keyframe_points.insert(frame,value,options={"FAST"})

        for frame,values in samples:
            for index,value in enumerate(values):
                set_component(curves[index],frame,value)
        for fc in curves.values():
            fc.update()
        return len(samples),True

    for action in bpy.data.actions:
        compensated_this_action=False
        for bone_name,compensation in arm_animation_rest_compensation.items():
            count,found=compensate_quaternion_fcurves(action,bone_name,compensation)
            if not found:
                # Only report actions which actually address this bone by another
                # rotation representation. A clip with no channel for the bone is
                # valid and needs no compensation.
                prefix=f'pose.bones["{bone_name}"].'
                has_bone_rotation=any(
                    fc.data_path.startswith(prefix) and "rotation_" in fc.data_path
                    for fc in action.fcurves
                )
                if has_bone_rotation:
                    animation_retarget["rest_compensation_missing_quaternion_channels"].append(
                        f"{action.name}:{bone_name}"
                    )
            elif count:
                compensated_this_action=True
                animation_retarget["rest_compensated_keyframes"]+=count
        if compensated_this_action:
            animation_retarget["rest_compensated_actions"]+=1

    if animation_retarget["rest_compensation_missing_quaternion_channels"]:
        raise RuntimeError(
            "arm_rest_compensation_requires_quaternion_channels:"
            + ",".join(animation_retarget["rest_compensation_missing_quaternion_channels"][:16])
        )

    for action in bpy.data.actions:
        animation_retarget["actions"]+=1
        for fcurve in list(action.fcurves):
            path=str(getattr(fcurve,"data_path","") or "")
            is_location=(path=="location" or path.endswith(".location"))
            is_scale=(path=="scale" or path.endswith(".scale"))
            is_rotation=(
                "rotation_quaternion" in path
                or "rotation_euler" in path
                or "rotation_axis_angle" in path
            )
            if is_location:
                action.fcurves.remove(fcurve)
                animation_retarget["removed_location_curves"]+=1
            elif is_scale:
                action.fcurves.remove(fcurve)
                animation_retarget["removed_scale_curves"]+=1
            elif is_rotation:
                animation_retarget["kept_rotation_curves"]+=1
            else:
                animation_retarget["kept_other_curves"]+=1
    bpy.context.view_layer.update()

    # Production skinning: use the fitted skeleton itself as the weighting
    # field. AI-generated meshes may contain hundreds/thousands of disconnected
    # islands, so donor-mesh nearest-neighbour weights can jump abruptly across
    # adjacent target vertices. A bone-envelope field stays spatially smooth
    # regardless of mesh fragmentation.
    def bone_side(name):
        return explicit_side_tag(name)

    def is_major_deform_bone(name):
        n=name.lower()
        if any(token in n for token in ("finger","thumb","index","middle","pinky","ring","twist","helper","ctrl","control","ik","pole")):
            return False
        return any(token in n for token in (
            "hips","pelvis","spine","chest","neck","head","shoulder","clav",
            "upper_arm","upperarm","arm.","arm_","forearm","lower_arm","lowerarm",
            "hand","thigh","upper_leg","upperleg","shin","calf","lower_leg",
            "lowerleg","foot","toe"
        ))

    def point_segment_distance(point,a,b):
        ab=b-a
        denom=ab.length_squared
        if denom<=1e-12:
            return (point-a).length
        t=max(0.0,min(1.0,(point-a).dot(ab)/denom))
        nearest=a+ab*t
        return (point-nearest).length

    bone_segments=[]
    for bone in arm.data.bones:
        if not is_major_deform_bone(bone.name):
            continue
        a=arm.matrix_world @ bone.head_local
        b=arm.matrix_world @ bone.tail_local
        length=max((b-a).length,1e-5)
        midpoint=(a+b)*0.5
        geometric_side=side_of(midpoint,target_center_fit,width_axis)
        bone_segments.append({
            "name":bone.name,
            "a":a,
            "b":b,
            "length":length,
            # Geometry decides left/right. Bone naming conventions disagree
            # across Mixamo/Rigify/UAM sources, so name suffixes are telemetry,
            # never the source of truth for side filtering.
            "side":geometric_side,
            "name_side":bone_side(bone.name),
        })
    if len(bone_segments)<12:
        raise RuntimeError(f"insufficient_major_bone_segments:{len(bone_segments)}<12")

    head_segment=next((seg for seg in bone_segments if seg["name"].lower()=="head" or "head" in seg["name"].lower()),None)
    neck_segment=next((seg for seg in bone_segments if "neck" in seg["name"].lower()),None)
    if head_segment is None:
        raise RuntimeError("major_head_bone_missing")

    segment_by_name={seg["name"]:seg for seg in bone_segments}
    major_names=set(segment_by_name)
    bone_neighbors={name:set() for name in major_names}
    for bone in arm.data.bones:
        if bone.name not in major_names:
            continue
        parent=bone.parent
        while parent is not None and parent.name not in major_names:
            parent=parent.parent
        if parent is not None and parent.name in major_names:
            bone_neighbors[bone.name].add(parent.name)
            bone_neighbors[parent.name].add(bone.name)

    # Some rigs insert non-deform helper chains between anatomically adjacent
    # DEF bones. The nearest-major-ancestor pass above recovers those links.
    # Keep support local: one dominant bone plus immediate anatomical neighbors.
    if not any(bone_neighbors.values()):
        raise RuntimeError("major_bone_adjacency_empty")

    bind_results=[]
    all_weighted_groups=set()
    bone_top1_counts={}
    for mesh in target_meshes:
        for mod in list(mesh.modifiers):
            if mod.type=="ARMATURE":
                mesh.modifiers.remove(mod)
        mesh.parent=None
        mesh.vertex_groups.clear()

        transferred=0
        fallback_count=0
        group_cache={}
        mesh_groups=set()
        # Preserve the per-vertex anatomical support mask through every later
        # smoothing pass. V24 constrained the initial solve correctly, but the
        # adjacency smoother could re-introduce unrelated bone names from a
        # neighboring vertex, defeating that guarantee.
        allowed_groups_by_vertex=[set() for _ in mesh.data.vertices]
        for v in mesh.data.vertices:
            world=mesh.matrix_world @ v.co
            target_side=side_of(world,target_center_fit,width_axis)
            height_norm=(
                (axis_value(world,target_axis)-axis_value(target_min,target_axis))
                / max(1e-8,target_height)
            )

            # Face/head safety zone. This model class currently has no facial
            # rig, so allowing the visible face surface to interpolate between
            # neck/clavicle/spine bones can only create distortion. Above 76%
            # of body height, make Head authoritative. This matches the
            # deformation gate's top-body face region without freezing shoulder
            # or arm articulation.
            semantic_head_zone=height_norm>=0.76
            if semantic_head_zone:
                scored=[(1.0e12,head_segment["name"],0.0)]
            else:
                scored=[]
                for seg in bone_segments:
                    if target_side and seg["side"] and target_side!=seg["side"]:
                        continue
                    dist=point_segment_distance(world,seg["a"],seg["b"])
                    radius=max(target_height*0.035,seg["length"]*0.42)
                    score=1.0/((dist+radius*0.35)**2)
                    scored.append((score,seg["name"],dist))
                if not scored:
                    for seg in bone_segments:
                        dist=point_segment_distance(world,seg["a"],seg["b"])
                        radius=max(target_height*0.035,seg["length"]*0.42)
                        scored.append((1.0/((dist+radius*0.35)**2),seg["name"],dist))
                scored.sort(reverse=True,key=lambda x:x[0])
            dominant=scored[0][1]
            bone_top1_counts[dominant]=bone_top1_counts.get(dominant,0)+1

            # Critical deformation rule: never mix unrelated bones merely
            # because their envelope happens to be nearby in a robe/hair/face
            # silhouette. Blend only the dominant bone and its immediate
            # skeletal neighbours. This preserves rigid facial/head surfaces
            # while retaining smooth elbow/knee/shoulder transitions.
            allowed=({head_segment["name"]} if semantic_head_zone else ({dominant}|bone_neighbors.get(dominant,set())))
            allowed_groups_by_vertex[v.index]=set(allowed)
            local=[]
            for score,name,dist in scored:
                if name in allowed:
                    local.append((score,name,dist))
            if not local:
                local=[scored[0]]

            accum={}
            for score,name,_ in local[:4]:
                accum[name]=accum.get(name,0.0)+score
            ranked=sorted(accum.items(),key=lambda x:x[1],reverse=True)[:4]
            total=sum(w for _,w in ranked)
            if total <= 1e-8:
                ranked=[("pelvis" if "pelvis" in arm_bones else "Hips",1.0)]
                total=1.0
                fallback_count += 1

            for name,weight in ranked:
                if name not in arm_bones:
                    continue
                group=group_cache.get(name)
                if group is None:
                    group=mesh.vertex_groups.get(name) or mesh.vertex_groups.new(name=name)
                    group_cache[name]=group
                group.add([v.index],float(weight/total),"REPLACE")
                mesh_groups.add(name)
                all_weighted_groups.add(name)
            transferred += 1

        # Smooth the transferred skin field across actual mesh adjacency without
        # context-sensitive bpy operators. This works headless in GitHub Actions
        # and prevents abrupt bone-weight jumps across face/clothing surfaces.
        smoothing={
            "attempted":True,
            "passed":False,
            "groups":len(mesh.vertex_groups),
            "method":"adjacency_python_anatomical_mask_v2",
            "anatomical_mask_enforced":True,
            "semantic_head_zone":{"min_height_norm":0.76,"bone":head_segment["name"]},
        }
        try:
            adjacency=[set() for _ in mesh.data.vertices]
            for edge in mesh.data.edges:
                a,b=edge.vertices
                adjacency[a].add(b)
                adjacency[b].add(a)

            # Snapshot sparse weights by bone name.
            weights_by_vertex=[]
            for v in mesh.data.vertices:
                row={}
                for g in v.groups:
                    if g.group < len(mesh.vertex_groups):
                        name=mesh.vertex_groups[g.group].name
                        if name in arm_bones and g.weight>1e-8:
                            row[name]=float(g.weight)
                weights_by_vertex.append(row)

            factor=0.28
            for _pass in range(2):
                next_rows=[]
                for vi,row in enumerate(weights_by_vertex):
                    neighbors=adjacency[vi]
                    if not neighbors:
                        next_rows.append(dict(row))
                        continue
                    allowed_names=allowed_groups_by_vertex[vi] or set(row)
                    names=set(row)
                    for ni in neighbors:
                        names.update(weights_by_vertex[ni])
                    # Never let topology smoothing widen a vertex's anatomical
                    # bone support. Neighbor weights may influence only bones
                    # that V25's local solver already declared valid here.
                    names.intersection_update(allowed_names)
                    merged={}
                    denom=float(len(neighbors))
                    for name in names:
                        own=row.get(name,0.0)
                        avg=sum(weights_by_vertex[ni].get(name,0.0) for ni in neighbors)/denom
                        value=(1.0-factor)*own+factor*avg
                        if value>1e-6:
                            merged[name]=value
                    ranked=sorted(merged.items(),key=lambda x:x[1],reverse=True)[:4]
                    total=sum(w for _,w in ranked)
                    if total>1e-8:
                        next_rows.append({name:w/total for name,w in ranked})
                    else:
                        fallback={name:w for name,w in row.items() if name in allowed_names}
                        fallback_total=sum(fallback.values())
                        next_rows.append(
                            {name:w/fallback_total for name,w in fallback.items()}
                            if fallback_total>1e-8 else dict(row)
                        )
                weights_by_vertex=next_rows

            # AI image-to-3D surfaces can contain hundreds/thousands of tiny
            # disconnected islands. Per-vertex blend differences inside a tiny
            # island visibly stretch faces, teeth, hair cards and clothing
            # patches when bones rotate. For small local islands, use one
            # coherent dominant bone for the entire connected component. Large
            # surfaces keep normal blended skinning for joint flexibility.
            visited=set()
            rigidized_components=0
            rigidized_vertices=0
            component_count=0
            # Fragmented generative meshes need component-level coherence.
            # A disconnected island cannot benefit from smooth weights across
            # topology that simply does not exist. Allow medium islands to move
            # as one anatomical piece; truly large/body-spanning surfaces keep
            # blended weights for joint articulation.
            max_rigid_vertices=max(96,min(2048,int(len(mesh.data.vertices)*0.08)))
            max_rigid_span=max(target_height*0.28,1e-5)
            for seed in range(len(mesh.data.vertices)):
                if seed in visited:
                    continue
                stack=[seed]
                visited.add(seed)
                component=[]
                while stack:
                    vi=stack.pop()
                    component.append(vi)
                    for ni in adjacency[vi]:
                        if ni not in visited:
                            visited.add(ni)
                            stack.append(ni)
                component_count+=1
                if not component:
                    continue

                coords=[mesh.matrix_world @ mesh.data.vertices[vi].co for vi in component]
                cmin=Vector((
                    min(p.x for p in coords),
                    min(p.y for p in coords),
                    min(p.z for p in coords),
                ))
                cmax=Vector((
                    max(p.x for p in coords),
                    max(p.y for p in coords),
                    max(p.z for p in coords),
                ))
                span=(cmax-cmin).length
                if len(component)>max_rigid_vertices or span>max_rigid_span:
                    continue

                totals={}
                for vi in component:
                    for name,weight in weights_by_vertex[vi].items():
                        totals[name]=totals.get(name,0.0)+float(weight)
                if not totals:
                    continue
                dominant=max(totals.items(),key=lambda x:x[1])[0]
                for vi in component:
                    weights_by_vertex[vi]={dominant:1.0}
                rigidized_components+=1
                rigidized_vertices+=len(component)

            smoothing["connected_components"]=component_count
            smoothing["rigidized_small_components"]=rigidized_components
            smoothing["rigidized_vertices"]=rigidized_vertices
            smoothing["rigidize_max_vertices"]=max_rigid_vertices
            smoothing["rigidize_max_span"]=float(max_rigid_span)

            # Rewrite groups from the smoothed field.
            for group in list(mesh.vertex_groups):
                mesh.vertex_groups.remove(group)
            group_cache={}
            smoothed_group_names=set()
            for vi,row in enumerate(weights_by_vertex):
                for name,weight in row.items():
                    group=group_cache.get(name)
                    if group is None:
                        group=mesh.vertex_groups.new(name=name)
                        group_cache[name]=group
                    group.add([vi],float(weight),"REPLACE")
                    smoothed_group_names.add(name)
            smoothing["passed"]=True
            smoothing["groups"]=len(smoothed_group_names)
            mesh_groups=set(smoothed_group_names)
        except Exception as exc:
            smoothing["error"]=f"{type(exc).__name__}:{exc}"

        # glTF skin export expects the armature to be the mesh parent. Preserve
        # the target mesh WORLD transform while parenting so the fitted
        # armature transform is not applied twice. This gives the exporter the
        # hierarchy it expects without moving/scaling the generated character.
        world_before=mesh.matrix_world.copy()
        mesh.parent=arm
        mesh.matrix_parent_inverse=arm.matrix_world.inverted()
        mesh.matrix_world=world_before
        mod=mesh.modifiers.new(name="HAYUYA_Armature",type="ARMATURE")
        mod.object=arm
        mod.use_vertex_groups=True
        bind_results.append({
            "mesh":mesh.name,
            "ok":True,
            "groups":len(mesh_groups),
            "weighted_group_names":sorted(mesh_groups),
            "spatial_weight_vertices":transferred,
            "fallback_weighted_vertices":fallback_count,
            "donor_samples":len(samples),
            "bone_envelope_segments":len(bone_segments),
            "anatomical_neighbor_graph":{k:sorted(v) for k,v in bone_neighbors.items()},
            "blend_neighbours":4,
            "query_space":"fitted_skeleton_bone_envelopes",
            "weight_smoothing":smoothing,
        })

    segment_debug=[
        {
            "name":seg["name"],
            "a":[round(float(x),5) for x in seg["a"]],
            "b":[round(float(x),5) for x in seg["b"]],
            "length":round(float(seg["length"]),5),
            "side":seg["side"],
            "name_side":seg["name_side"],
        }
        for seg in bone_segments
    ]

    # Persist rest-fit coverage telemetry instead of keeping it only in CI logs.
    # This is deliberately observational: it does not alter weights, skeleton
    # transforms, animation curves, or QA thresholds. It lets later solvers
    # distinguish "weighting missed the hand" from "the fitted hand bone is not
    # spatially inside the generated character's rest-pose envelope".
    lateral_min=coord_axis(target_min,width_axis)
    lateral_max=coord_axis(target_max,width_axis)
    lateral_span=max(1e-8,lateral_max-lateral_min)
    terminal_major_fit=[]
    for seg in bone_segments:
        n=seg["name"].lower()
        kind=None
        if "hand" in n:
            kind="hand"
        elif "foot" in n or "toe" in n:
            kind="foot"
        if kind is None:
            continue
        pa=coord_axis(seg["a"],width_axis)
        pb=coord_axis(seg["b"],width_axis)
        seg_min=min(pa,pb)
        seg_max=max(pa,pb)
        outside=max(0.0,lateral_min-seg_min,seg_max-lateral_max)
        terminal_major_fit.append({
            "name":seg["name"],
            "kind":kind,
            "top1_vertices":int(bone_top1_counts.get(seg["name"],0)),
            "weighted":seg["name"] in all_weighted_groups,
            "lateral_range":[round(float(seg_min),6),round(float(seg_max),6)],
            "target_lateral_range":[round(float(lateral_min),6),round(float(lateral_max),6)],
            "lateral_overhang":round(float(outside),6),
            "lateral_overhang_normalized":round(float(outside/lateral_span),6),
        })
    hand_fit=[x for x in terminal_major_fit if x["kind"]=="hand"]
    suspected_rest_pose_mismatch=bool(
        hand_fit
        and all(x["top1_vertices"]==0 for x in hand_fit)
        and any(x["lateral_overhang_normalized"]>0.10 for x in hand_fit)
    )
    rest_pose_fit_telemetry={
        "schema":1,
        "method":"terminal_major_bone_bbox_overlap_v1",
        "lateral_axis":width_axis,
        "top1_counts":dict(sorted(bone_top1_counts.items(),key=lambda x:x[1],reverse=True)),
        "terminal_major_fit":terminal_major_fit,
        "suspected_rest_pose_mismatch":suspected_rest_pose_mismatch,
    }

    print("HAYUYA_BONE_ENVELOPE",json.dumps({
        "target_bounds":{"min":list(target_min),"max":list(target_max)},
        "segments":segment_debug,
        "top1_counts":rest_pose_fit_telemetry["top1_counts"],
        "terminal_major_fit":terminal_major_fit,
        "suspected_rest_pose_mismatch":suspected_rest_pose_mismatch,
        "weighted_groups":sorted(all_weighted_groups),
    },separators=(",",":")))

    # A technically valid skin with only a few weighted bones is NOT a usable
    # humanoid rig. Fail here so the Studio keeps the clean static model rather
    # than publishing a melted/stretched animated preview.
    if len(all_weighted_groups) < 12:
        raise RuntimeError(
            f"insufficient_weighted_bone_coverage:{len(all_weighted_groups)}<12:"
            + ",".join(sorted(all_weighted_groups))
        )

    # Donor render meshes/helpers are no longer needed after weight transfer.
    # Fail closed and remove every non-target mesh in the scene. Some donor GLBs
    # contain an unparented Icosphere/root mesh which glTF export can otherwise
    # pull back in through armature dependencies even with use_selection=True.
    target_mesh_names={m.name for m in target_meshes}
    for obj in list(bpy.data.objects):
        if obj.type=="MESH" and obj.name not in target_mesh_names:
            bpy.data.objects.remove(obj,do_unlink=True)
    for name in list(custom_shape_names):
        obj=bpy.data.objects.get(name)
        if obj is not None and obj.name not in target_mesh_names:
            bpy.data.objects.remove(obj,do_unlink=True)
    # Remove remaining donor helpers by NAME, not by stale Blender object
    # references. Mesh objects above may already have been unlinked and a stale
    # StructRNA raises ReferenceError when its .name is accessed.
    for obj in list(bpy.data.objects):
        if obj.name in donor_object_names and obj != arm and obj.name not in target_mesh_names:
            bpy.data.objects.remove(obj,do_unlink=True)

    bpy.context.view_layer.update()
    remaining_meshes=[o.name for o in bpy.context.scene.objects if o.type=="MESH"]
    unexpected=[name for name in remaining_meshes if name not in target_mesh_names]
    if unexpected:
        raise RuntimeError("unexpected_meshes_before_export:"+",".join(unexpected))
    if sorted(remaining_meshes)!=sorted(target_mesh_names):
        raise RuntimeError(
            "target_mesh_set_changed_before_export:"
            +json.dumps({"expected":sorted(target_mesh_names),"actual":sorted(remaining_meshes)})
        )

    # Make a sensible default preview action if imported animations exist.
    actions=sorted(bpy.data.actions,key=lambda a:a.name.lower())
    idle=next((a for a in actions if "idle" in a.name.lower()), actions[0] if actions else None)
    if idle:
        if arm.animation_data is None:
            arm.animation_data_create()
        arm.animation_data.action=idle

    args.output.unlink(missing_ok=True)

    # Export from a sterile scene containing ONLY the generated target meshes
    # and fitted armature. glTF exporters may follow dependencies outside the
    # selected object list (custom shapes / helper roots / donor controls), so
    # use_selection alone is not a sufficient containment boundary.
    export_scene=bpy.data.scenes.new("HAYUYA_EXPORT_SCENE")
    for obj in [arm,*target_meshes]:
        if obj.name not in export_scene.collection.objects:
            export_scene.collection.objects.link(obj)
    if bpy.context.window is not None:
        bpy.context.window.scene=export_scene
    bpy.context.view_layer.update()
    export_scene_meshes=sorted(o.name for o in export_scene.objects if o.type=="MESH")
    if export_scene_meshes!=sorted(target_mesh_names):
        raise RuntimeError(
            "sterile_export_scene_mesh_mismatch:"
            +json.dumps({"expected":sorted(target_mesh_names),"actual":export_scene_meshes})
        )
    extra_scene_objects=[
        o.name for o in export_scene.objects
        if o not in target_meshes and o != arm
    ]
    if extra_scene_objects:
        raise RuntimeError("sterile_export_scene_extra_objects:"+",".join(sorted(extra_scene_objects)))

    select_only(*target_meshes,arm)
    bpy.ops.export_scene.gltf(
        filepath=str(args.output.resolve()),
        export_format="GLB",
        use_selection=True,
        export_animations=True,
        export_skins=True,
        export_def_bones=True,
        export_all_influences=True,
        export_nla_strips=True,
        export_yup=True,
    )

    report={
        "schema":1,
        "target":str(args.target),
        "donor":str(args.donor),
        "output":str(args.output),
        "target_meshes":[m.name for m in target_meshes],
        "target_bounds":{"min":list(target_min),"max":list(target_max),"height":target_height,"axis":target_axis},
        "donor_bounds":{
            "min":list(donor_min),
            "max":list(donor_max),
            "height":donor_height,
            "height_axis":target_axis,
            "bbox_major_axis":height_axis(donor_ext)
        },
        "scale":scale,
        "axis_scales":axis_scales,
        "requested_axis_scales":requested_axis_scales,
        "armature_fit_mode":"uniform_height_plus_pose_aware_arms_v32_rest_compensated",
        "orientation_fix":orientation_fix,
        "lateral_axis":lateral_axis_telemetry,
        "arm_rest_fit":arm_rest_fit,
        "armature":arm.name,
        "bones":[b.name for b in arm.data.bones],
        "actions":[a.name for a in actions],
        "weighted_bones":sorted(all_weighted_groups),
        "weighted_bone_count":len(all_weighted_groups),
        "donor_root_objects":donor_root_names,
        "cleared_custom_shape_objects":sorted(custom_shape_names),
        "excluded_donor_meshes_from_fit":excluded_donor_meshes,
        "armature_object_transform_baked":True,
        "armature_world_before":arm_world_before,
        "armature_world_after":arm_world_after,
        "animation_retarget":animation_retarget,
        "export_meshes":remaining_meshes,
        "sterile_export_scene_meshes":export_scene_meshes,
        "binding_method":"expanded_component_consensus_pose_aware_arms_v35",
        "bind_results":bind_results,
        "rest_pose_fit_telemetry":rest_pose_fit_telemetry,
        "output_bytes":args.output.stat().st_size if args.output.exists() else 0,
    }
    args.report.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("HAYUYA_AUTORIG_PASS")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main()

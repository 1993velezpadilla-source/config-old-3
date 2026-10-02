#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

def load(path:Path|None)->dict:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def choose_weapon_family(explicit:str,research:dict)->tuple[str,str,float]:
    if explicit and explicit!="auto":
        return explicit,"explicit",1.0
    fam=str(research.get("inferred_weapon_family") or "auto")
    conf=float(research.get("confidence") or 0.0)
    if fam!="auto" and conf>=0.72:
        return fam,"internet_research",conf
    return "auto","unresolved",conf

def plan(profile:str,animation_requested:bool,motion_profile:str,weapon_family:str,research:dict,learned:dict|None=None)->dict:
    result={
        "schema":1,
        "engine":"HAYUYA Auto",
        "enabled":bool(animation_requested and motion_profile in {"auto","hayuya_auto"}),
        "asset_profile":profile,
        "motion_profile":"hayuya_auto" if motion_profile in {"auto","hayuya_auto"} else motion_profile,
        "status":"disabled",
        "motion_system":None,
        "weapon_family":"auto",
        "family_source":None,
        "family_confidence":0.0,
        "preview_set":[],
        "required_components":[],
        "synthesis_operations":[],
        "requires":["mesh_gate","texture_gate"],
        "warnings":[],
        "research_sources":research.get("sources",[]),
        "editor_override_allowed":True,
        "motion_strategy":None,
        "learned_examples":[],
    }
    if not result["enabled"]:
        result["warnings"].append("auto_motion_not_requested")
        return result

    if profile=="character.humanoid":
        result.update(
            status="plan_ready",
            motion_system="skeletal",
            preview_set=["idle","walk","run","attack","hit","death"],
            requires=result["requires"]+["humanoid_autorig","rig_gate","animation_deformation_gate"],
            synthesis_operations=["fit_hayuya_humanoid_v1","retarget_local_animation_library","facial_idle_if_controls_exist","secondary_motion_if_controls_exist"]
        )
        return result

    if profile=="character.creature":
        result.update(
            status="needs_creature_rig",
            motion_system="skeletal",
            preview_set=["idle","locomotion","attack","hit","death"],
            requires=result["requires"]+["creature_skeleton_fit","rig_gate","animation_deformation_gate"],
            synthesis_operations=["infer_joint_chain","fit_creature_skeleton","retarget_only_compatible_creature_motion"]
        )
        return result

    if profile=="weapon.firearm":
        fam,source,conf=choose_weapon_family(weapon_family,research)
        result["weapon_family"]=fam
        result["family_source"]=source
        result["family_confidence"]=conf
        result["motion_system"]="mechanical_skeleton"
        result["requires"]+=["part_segmentation","weapon_component_gate","weapon_animation_matcher","mechanical_motion_gate"]
        if fam=="auto":
            result["status"]="needs_family_confirmation"
            result["warnings"].append("firearm_mechanism_unresolved")
            return result
        family_rules={
            "handgun_semiauto":{
                "preview":["idle","fire","slide_cycle","reload_mag","inspect"],
                "parts":["trigger","slide","magazine"],
                "ops":["slide_reciprocate","magazine_detach_insert","optional_trigger_pull"]
            },
            "revolver":{
                "preview":["idle","fire","reload_cylinder","inspect"],
                "parts":["trigger","cylinder"],
                "ops":["cylinder_rotate","cylinder_open_close","optional_hammer_cock","rounds_extract_insert"]
            },
            "shotgun_pump_tube":{
                "preview":["idle","fire","pump_cycle","reload_shell","inspect"],
                "parts":["trigger","pump","tube"],
                "ops":["pump_reciprocate","shell_insert_to_tube","optional_shell_eject"]
            },
            "shotgun_semiauto_tube":{
                "preview":["idle","fire","bolt_cycle","reload_shell","inspect"],
                "parts":["trigger","bolt","tube"],
                "ops":["bolt_reciprocate","shell_insert_to_tube","optional_shell_eject"]
            },
            "shotgun_break_open":{
                "preview":["idle","fire","break_open","reload_shell_pair","break_close","inspect"],
                "parts":["trigger","break_hinge","barrel_group"],
                "ops":["break_hinge_rotate","shell_pair_extract_insert"]
            },
            "rifle_magazine":{
                "preview":["idle","fire","bolt_cycle","reload_mag","inspect"],
                "parts":["trigger","bolt_or_slide","magazine"],
                "ops":["bolt_reciprocate","magazine_detach_insert","optional_charge_handle"]
            },
            "rifle_bolt_action":{
                "preview":["idle","fire","bolt_cycle","reload","inspect"],
                "parts":["trigger","bolt_handle","magazine_or_internal_mag"],
                "ops":["bolt_unlock_rotate","bolt_pull_push","bolt_lock_rotate","reload_mag_or_single_round"]
            },
            "lmg_beltfed":{
                "preview":["idle","fire","reload_belt","inspect"],
                "parts":["trigger","bolt_or_slide","feed_cover","belt_or_box"],
                "ops":["feed_cover_open_close","belt_or_box_replace","bolt_cycle"]
            },
            "launcher":{
                "preview":["idle","fire","reload_round","inspect"],
                "parts":["trigger"],
                "ops":["family_specific_breech_or_tube_reload"]
            }
        }
        rules=family_rules[fam]
        result["preview_set"]=rules["preview"]
        result["required_components"]=rules["parts"]
        result["synthesis_operations"]=rules["ops"]

        learned=learned or {}
        examples=[]
        for asset in learned.get("assets",[]) or []:
            if asset.get("family")==fam:
                examples.append({
                    "source_file":asset.get("source_file"),
                    "actions":[x.get("name") for x in asset.get("actions",[]) if x.get("name")],
                    "moving_parts":sorted({
                        bone
                        for action in asset.get("actions",[])
                        for bone in action.get("animated_bones",[])
                    })
                })
        result["learned_examples"]=examples
        result["motion_strategy"]="retarget_learned_then_synthesize_missing" if examples else "synthesize_from_semantic_recipe"
        result["status"]="needs_component_fit"
        return result

    if profile=="weapon.melee":
        result.update(
            status="plan_ready",
            motion_system="transform_channels",
            preview_set=["idle","inspect","display_spin"],
            requires=result["requires"]+["pivot_socket_gate"],
            synthesis_operations=["pivot_setup","grip_socket_setup","optional_display_motion"]
        )
        return result

    if profile=="prop.mechanical":
        result.update(
            status="needs_part_fit",
            motion_system="transform_channels",
            preview_set=["idle","open_close_or_rotate"],
            requires=result["requires"]+["part_segmentation","pivot_detection","mechanical_motion_gate"],
            synthesis_operations=["detect_hinge_or_rotation_axis","generate_bounded_transform_animation"]
        )
        return result

    if profile=="vehicle":
        result.update(
            status="needs_part_fit",
            motion_system="mechanical_skeleton",
            preview_set=["idle","wheel_spin","steer","suspension"],
            requires=result["requires"]+["wheel_axis_detection","mechanical_motion_gate"],
            synthesis_operations=["detect_wheels","generate_axle_rotation","generate_steering","optional_suspension"]
        )
        return result

    if profile=="foliage.grass":
        result.update(
            status="plan_ready",
            motion_system="vertex_wind",
            preview_set=["soft_breeze","windy"],
            requires=result["requires"]+["wind_bounds_gate"],
            synthesis_operations=["root_lock_weight_map","height_gradient_wind_weights","procedural_wind_profile"]
        )
        return result

    if profile=="foliage.tree":
        result.update(
            status="plan_ready",
            motion_system="vertex_wind",
            preview_set=["branch_leaf_breeze","heavy_wind"],
            requires=result["requires"]+["wind_bounds_gate"],
            synthesis_operations=["trunk_branch_leaf_weight_layers","procedural_wind_profile"]
        )
        return result

    result.update(
        status="static_default",
        motion_system="optional_transform_channels",
        preview_set=["static"],
        synthesis_operations=[]
    )
    return result

def main()->int:
    p=argparse.ArgumentParser(description="Plan self-evaluating HAYUYA Auto motion.")
    p.add_argument("--asset-profile",required=True)
    p.add_argument("--weapon-family",default="auto")
    p.add_argument("--motion-profile",default="hayuya_auto")
    p.add_argument("--animation-requested",default="true")
    p.add_argument("--research",type=Path)
    p.add_argument("--learned-motion",type=Path,default=Path("hayuya/weapon_library/quaternius-animated-guns/learned_motion.json"))
    p.add_argument("--json",type=Path,required=True)
    a=p.parse_args()
    requested=str(a.animation_requested).lower() in {"1","true","yes","on"}
    learned=load(a.learned_motion) if a.learned_motion and a.learned_motion.exists() else {}
    out=plan(a.asset_profile,requested,a.motion_profile,a.weapon_family,load(a.research),learned)
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_AUTO_MOTION",json.dumps({
        "enabled":out["enabled"],
        "profile":out["asset_profile"],
        "status":out["status"],
        "system":out["motion_system"],
        "weapon_family":out["weapon_family"],
        "preview_set":out["preview_set"]
    },separators=(",",":")))
    return 0

if __name__=="__main__":
    raise SystemExit(main())

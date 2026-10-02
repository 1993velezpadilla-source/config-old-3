#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

PROFILE_PARTS={
    "character.humanoid":{
        "required":[
            "body","head",
            "upper_arm_left","upper_arm_right",
            "forearm_left","forearm_right",
            "thigh_left","thigh_right",
            "calf_left","calf_right"
        ],
        "optional":[
            "jaw","left_eye","right_eye","mouth","teeth",
            "left_hand","right_hand","left_ear","right_ear",
            "hair","wounds","loose_clothing","feet"
        ],
        "prompts":{
            "body":["human body","torso"],
            "head":["head","face"],
            "upper_arm_left":["left upper arm"],
            "upper_arm_right":["right upper arm"],
            "forearm_left":["left forearm"],
            "forearm_right":["right forearm"],
            "thigh_left":["left thigh","left upper leg"],
            "thigh_right":["right thigh","right upper leg"],
            "calf_left":["left calf","left lower leg"],
            "calf_right":["right calf","right lower leg"],
            "jaw":["jaw","lower face"],
            "left_eye":["left eye"],
            "right_eye":["right eye"],
            "mouth":["mouth","lips"],
            "teeth":["teeth","visible teeth"],
            "left_hand":["left hand","left fingers"],
            "right_hand":["right hand","right fingers"],
            "left_ear":["left ear"],
            "right_ear":["right ear"],
            "hair":["hair","hairline","ponytail","braid"],
            "wounds":["wound","scar","skin lesion"],
            "loose_clothing":["coat","skirt","dress","cape","loose sleeve","tie"],
            "feet":["feet","shoes"]
        }
    },
    "vehicle":{
        "required":["body","wheel_front_left","wheel_front_right","wheel_rear_left","wheel_rear_right"],
        "optional":["door_left","door_right","steering","hood","trunk"],
        "prompts":{
            "wheel_front_left":["front left wheel","front wheel"],
            "wheel_front_right":["front right wheel","front wheel"],
            "wheel_rear_left":["rear left wheel","rear wheel"],
            "wheel_rear_right":["rear right wheel","rear wheel"],
            "door_left":["left door","driver door"],
            "door_right":["right door","passenger door"]
        }
    },
    "foliage.grass":{
        "required":["root_region","blade_region"],
        "optional":["tip_region"],
        "prompts":{
            "root_region":["grass roots","bottom of grass blades"],
            "blade_region":["grass blades"],
            "tip_region":["tips of grass blades"]
        }
    },
    "foliage.tree":{
        "required":["trunk","branches","leaves"],
        "optional":["small_twigs"],
        "prompts":{
            "trunk":["tree trunk"],
            "branches":["tree branches"],
            "leaves":["leaves","foliage canopy"],
            "small_twigs":["small branches","twigs"]
        }
    },
}

CRITICAL_CHARACTER_TARGETS={
    "eyes":["left_eye","right_eye"],
    "mouth":["mouth"],
    "teeth":["teeth"],
    "hands":["left_hand","right_hand"],
    "hair":["hair"],
    "ears":["left_ear","right_ear"],
    "wounds":["wounds"],
}

WEAPON_PARTS={
    "handgun_semiauto":{
        "required":["trigger","slide","magazine"],
        "optional":["magazine_release","hammer","safety","slide_stop","ejection_port"],
        "prompts":{
            "trigger":["trigger"],
            "slide":["pistol slide","upper slide"],
            "magazine":["removable pistol magazine","magazine"],
            "magazine_release":["magazine release button"],
            "hammer":["hammer"],
            "safety":["safety lever"],
            "slide_stop":["slide stop lever"]
        }
    },
    "revolver":{
        "required":["trigger","cylinder"],
        "optional":["hammer","ejector_rod","cylinder_release","rounds"],
        "prompts":{
            "trigger":["trigger"],
            "cylinder":["revolver cylinder","rotating cylinder","drum"],
            "hammer":["hammer"],
            "ejector_rod":["ejector rod"],
            "cylinder_release":["cylinder release"]
        }
    },
    "shotgun_pump_tube":{
        "required":["trigger","pump","tube"],
        "optional":["loading_gate","shell_lifter","ejection_port","bolt","shell"],
        "prompts":{
            "trigger":["trigger"],
            "pump":["pump fore-end","sliding fore-end","pump handle"],
            "tube":["tubular magazine under barrel","magazine tube"],
            "loading_gate":["shotgun loading gate","loading port"],
            "ejection_port":["ejection port"],
            "bolt":["shotgun bolt"]
        }
    },
    "shotgun_semiauto_tube":{
        "required":["trigger","bolt","tube"],
        "optional":["charging_handle","loading_gate","ejection_port","shell"],
        "prompts":{
            "trigger":["trigger"],
            "bolt":["shotgun bolt"],
            "tube":["tubular magazine under barrel","magazine tube"],
            "charging_handle":["charging handle"],
            "loading_gate":["loading gate","loading port"]
        }
    },
    "shotgun_break_open":{
        "required":["trigger","barrel_group","break_hinge"],
        "optional":["extractor","hammer","shell_pair"],
        "prompts":{
            "trigger":["trigger"],
            "barrel_group":["shotgun barrels","barrel group"],
            "break_hinge":["break action hinge","receiver hinge"],
            "extractor":["shell extractor","ejector"]
        }
    },
    "rifle_magazine":{
        "required":["trigger","bolt_or_slide","magazine"],
        "optional":["charging_handle","selector","safety","bolt_release","ejection_port"],
        "prompts":{
            "trigger":["trigger"],
            "bolt_or_slide":["rifle bolt","bolt carrier","moving bolt"],
            "magazine":["detachable rifle magazine","magazine"],
            "charging_handle":["charging handle"],
            "selector":["fire selector","selector lever"],
            "bolt_release":["bolt release"]
        }
    },
    "rifle_bolt_action":{
        "required":["trigger","bolt_handle","magazine_or_internal_mag"],
        "optional":["safety","ejection_port","round"],
        "prompts":{
            "trigger":["trigger"],
            "bolt_handle":["bolt handle","bolt knob"],
            "magazine_or_internal_mag":["magazine","internal magazine","floorplate"]
        }
    },
    "lmg_beltfed":{
        "required":["trigger","bolt_or_slide","feed_cover","belt_or_box"],
        "optional":["charging_handle","bipod","ejection_port"],
        "prompts":{
            "trigger":["trigger"],
            "bolt_or_slide":["bolt","bolt carrier"],
            "feed_cover":["feed cover","top cover"],
            "belt_or_box":["ammunition belt","ammo box","belt box"],
            "charging_handle":["charging handle"]
        }
    },
    "launcher":{
        "required":["trigger"],
        "optional":["breech","tube","cylinder","safety"],
        "prompts":{
            "trigger":["trigger"],
            "breech":["breech","breech block"],
            "tube":["launcher tube"],
            "cylinder":["launcher cylinder"]
        }
    }
}

def build(
    profile:str,
    family:str,
    critical_targets:list[str]|None=None,
)->dict:
    requested=[
        str(x).strip().lower()
        for x in (critical_targets or [])
        if str(x).strip()
    ]
    if profile=="weapon.firearm":
        data=WEAPON_PARTS.get(family)
        if not data:
            return {
                "schema":1,"asset_profile":profile,"weapon_family":family,
                "status":"needs_family_confirmation","required":[],"optional":[],
                "prompts":{},"projection":"multi_view_preferred",
                "warnings":["weapon_family_unresolved"]
            }
    else:
        source=PROFILE_PARTS.get(profile,{
            "required":[],
            "optional":[],
            "prompts":{}
        })
        data={
            "required":list(source.get("required",[])),
            "optional":list(source.get("optional",[])),
            "prompts":{
                str(key):list(value)
                for key,value in (source.get("prompts",{}) or {}).items()
            },
        }
        if profile=="character.humanoid":
            promoted=[]
            unknown=[]
            for target in requested:
                parts=CRITICAL_CHARACTER_TARGETS.get(target)
                if not parts:
                    unknown.append(target)
                    continue
                for part in parts:
                    if part not in data["required"]:
                        data["required"].append(part)
                    if part in data["optional"]:
                        data["optional"].remove(part)
                    promoted.append(part)
            data["promoted_critical_parts"]=sorted(set(promoted))
            data["unknown_critical_targets"]=sorted(set(unknown))
    return {
        "schema":1,
        "asset_profile":profile,
        "weapon_family":family if profile=="weapon.firearm" else "auto",
        "status":"ready" if data.get("required") else "not_required",
        "required":data.get("required",[]),
        "optional":data.get("optional",[]),
        "prompts":data.get("prompts",{}),
        "detectors":["groundingdino","sam2"] if data.get("required") else [],
        "projection":"multi_view_preferred",
        "fusion_rule":"a 3D component is accepted only when masks from available views agree spatially or later 3D geometry evidence confirms it",
        "confidence_gate":0.72,
        "critical_targets_requested":requested,
        "promoted_critical_parts":data.get("promoted_critical_parts",[]),
        "warnings":[
            *(
                ["unknown_critical_targets:"+",".join(data.get("unknown_critical_targets",[]))]
                if data.get("unknown_critical_targets") else []
            ),
            *[
                "required_part_missing_prompt:"+part
                for part in data.get("required",[])
                if part not in (data.get("prompts") or {})
            ],
        ]
    }

def main()->int:
    p=argparse.ArgumentParser(description="Create HAYUYA semantic part segmentation prompts.")
    p.add_argument("--asset-profile",required=True)
    p.add_argument("--weapon-family",default="auto")
    p.add_argument(
        "--critical-target",
        action="append",
        default=[],
        choices=sorted(CRITICAL_CHARACTER_TARGETS),
        help="Promote an explicitly referenced critical anatomy target to required semantic evidence.",
    )
    p.add_argument("--json",required=True,type=Path)
    a=p.parse_args()
    out=build(
        a.asset_profile,
        a.weapon_family,
        critical_targets=a.critical_target,
    )
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("HAYUYA_PART_SEGMENTATION_PLAN",json.dumps({
        "status":out["status"],"required":out["required"],"detectors":out["detectors"]
    },separators=(",",":")))
    return 0

if __name__=="__main__":
    raise SystemExit(main())

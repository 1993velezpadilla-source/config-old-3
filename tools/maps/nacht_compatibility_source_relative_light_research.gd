extends RefCounted
## Research-only original Unreal light photometry -> Godot Compatibility
## RELATIVE energy mapping. Physical lumens/lux are ignored by Compatibility.
## Preserve all original source light positions, colors, zero intensities,
## ranges, shadow states and original material files. NOT lumen equivalence.
var _original_energy: Array[Dictionary]=[]
var _running: bool=false

static func _source_candela_equivalent(light: Light3D) -> float:
    var source: float=float(light.get_meta("source_intensity",-1.0))
    var units: String=str(light.get_meta("source_intensity_units",""))
    if source<=0.0:
        return source
    if units=="Candelas":
        return source
    if units=="Lumens":
        if light is SpotLight3D:
            var angle: float=deg_to_rad((light as SpotLight3D).spot_angle)
            var solid_angle: float=2.0*PI*(1.0-cos(angle))
            if solid_angle<=0.000001:
                return -1.0
            return source/solid_angle
        return source/(4.0*PI)
    return -1.0

func apply_original_source_light_ratios_research(
        light_root: Node3D, source_actors: int, max_relative_energy: float=4.0) -> Dictionary:
    if _running or not _original_energy.is_empty():
        return {"errors":["source light ratio controller is already active"]}
    if light_root==null or source_actors!=10793 or max_relative_energy<1.0 or max_relative_energy>8.0:
        return {"errors":["original actor authority/light root/source ratio cap missing"]}
    var children: Array[Node]=light_root.find_children("*","Light3D",true,false)
    var list: Array[Light3D]=[]
    var positive: Array[float]=[]
    var original_zero: int=0
    for n: Node in children:
        var light: Light3D=n as Light3D
        if light==null:
            continue
        list.append(light)
        if not light.has_meta("source_intensity") or not light.has_meta("source_intensity_units"):
            return {"errors":["non-source light in original source positional set"]}
        var source: float=float(light.get_meta("source_intensity",-1.0))
        if not is_finite(source) or source<0.0:
            return {"errors":["invalid authored source light intensity"]}
        if source==0.0:
            original_zero+=1
        if light is OmniLight3D or light is SpotLight3D:
            var candela: float=_source_candela_equivalent(light)
            if candela<0.0 or not is_finite(candela):
                return {"errors":["unsupported or incomplete original UE4 point/spot source units "+str(light.get_meta("source_intensity_units",""))]}
            if candela>0.0:
                positive.append(candela)
    if list.size()!=165 or positive.size()<20:
        return {"errors":["missing exact 165 original 3D source light components or positive point/spot photometry"],
                "lightsFound":list.size(),"sourceLitPointSpotCount":positive.size()}
    positive.sort()
    var mid: int=positive.size()/2
    var median: float=positive[mid] if positive.size()%2==1 else (
        (positive[mid-1]+positive[mid])*0.5)
    if not is_finite(median) or median<=0.0:
        return {"errors":["original source candela median is not finite positive"]}
    var proposed: Array[Dictionary]=[]
    var clipped: int=0
    var min_ratio: float=1.0e30
    var max_ratio: float=0.0
    for l: Light3D in list:
        var energy: float=l.light_energy
        if (l is OmniLight3D or l is SpotLight3D) and energy>0.0:
            var orig_cd: float=_source_candela_equivalent(l)
            var uncapped: float=orig_cd/median
            # Research-only sane display cap; does NOT certify UE irradiance.
            var ratio: float=clampf(uncapped,0.10,max_relative_energy)
            if not is_finite(ratio) or ratio<=0.0:
                return {"errors":["relative calibrated light energy not finite"]}
            clipped+=1 if not is_equal_approx(uncapped,ratio) else 0
            min_ratio=minf(min_ratio,ratio)
            max_ratio=maxf(max_ratio,ratio)
            proposed.append({"light":l,"before":energy,"after":ratio})
        else:
            proposed.append({"light":l,"before":energy,"after":energy})
    for row: Dictionary in proposed:
        _original_energy.append({"light":row["light"],"energy":row["before"]})
        (row["light"] as Light3D).light_energy=float(row["after"])
    _running=true
    return {
        "errors":[],
        "originalSourceActorsRetained":source_actors,
        "sourceLightNodeCountIncludingDirectional":list.size(),
        "sourceLightCountExcludingSky":165,
        "positiveOriginalPhotometricPointSpotLights":positive.size(),
        "originalZeroIntensityCount":original_zero,
        "sourceCandelaEquivalentMedian":median,
        "clippedRatioCandidates":clipped,
        "minimumRelativeEnergyAssigned":min_ratio,
        "maximumRelativeEnergyAssigned":max_ratio,
        "absoluteUEPhotometricEquivalenceNotProven":true,
        "lightTransformColorRadiusAndMasksUnchanged":true,
        "normalAndMaterialDDSUnchanged":true,
        "shippingAllowed":false
    }

func restore_source_light_energy() -> Dictionary:
    if not _running or _original_energy.size()!=165:
        return {"errors":["no complete active source-light ratio diagnostic"]}
    for original: Dictionary in _original_energy:
        var light: Light3D=original["light"] as Light3D
        light.light_energy=float(original["energy"])
        if not is_equal_approx(light.light_energy,float(original["energy"])):
            return {"errors":["failed restoring exact original source light energy"]}
    _running=false
    _original_energy.clear()
    return {"errors":[],"originalSourceLightEnergyResourcesRestored":165,
            "noOriginalSourceNodesAddedOrDeleted":true}

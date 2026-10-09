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


static func _median_positive(values: Array[float]) -> float:
    if values.is_empty():
        return 0.0
    var count: int=values.size()
    var middle: int=count/2
    return values[middle] if count%2==1 else (
        0.5*(values[middle-1]+values[middle]))

func apply_original_source_light_ratios_research(
        light_root: Node3D, source_actors: int, max_relative_energy: float=4.0) -> Dictionary:
    if _running or not _original_energy.is_empty():
        return {"errors":["source light ratio controller is already active"]}
    if light_root==null or source_actors!=10793 or max_relative_energy<1.0 or max_relative_energy>8.0:
        return {"errors":["original actor authority/light root/source ratio cap missing"]}
    var children: Array[Node]=light_root.find_children("*","Light3D",true,false)
    var list: Array[Light3D]=[]
    var photometric_positive: Array[float]=[]
    var unitless_positive: Array[float]=[]
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
            var units: String=str(light.get_meta("source_intensity_units",""))
            # UE source Unitless intensities are NOT candelas. Preserve their
            # ratios as an entirely separate cohort: never mix their numeric
            # values with genuine Lumens / Candelas.
            if units=="Unitless":
                if source>0.0:
                    unitless_positive.append(source)
            else:
                var candela: float=_source_candela_equivalent(light)
                if candela<0.0 or not is_finite(candela):
                    return {"errors":["unsupported original UE4 source light units "+units]}
                if candela>0.0:
                    photometric_positive.append(candela)
    if list.size()!=165 or photometric_positive.size()+unitless_positive.size()<20:
        return {"errors":["missing 165 source lights or insufficient positive source-authored point/spot ratios"],
                "lightsFound":list.size(),"photometricCount":photometric_positive.size(),
                "unitlessCount":unitless_positive.size()}
    photometric_positive.sort()
    unitless_positive.sort()
    var median_photo: float=_median_positive(photometric_positive)
    var median_unitless: float=_median_positive(unitless_positive)
    if (not photometric_positive.is_empty() and median_photo<=0.0) or (
        not unitless_positive.is_empty() and median_unitless<=0.0):
        return {"errors":["source authored intensity cohort median invalid"]}
    var proposed: Array[Dictionary]=[]
    var clipped: int=0
    var min_ratio: float=1.0e30
    var max_ratio: float=0.0
    for l: Light3D in list:
        var energy: float=l.light_energy
        if (l is OmniLight3D or l is SpotLight3D) and energy>0.0:
            var is_unitless: bool=str(l.get_meta("source_intensity_units",""))=="Unitless"
            var value: float=(
                float(l.get_meta("source_intensity",0.0))
                if is_unitless else _source_candela_equivalent(l))
            var baseline: float=median_unitless if is_unitless else median_photo
            if baseline<=0.0 or not is_finite(value) or value<0.0:
                return {"errors":["invalid separately-normalized original light source cohort"]}
            var uncapped: float=value/baseline
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
        "positiveOriginalPhotometricPointSpotLights":photometric_positive.size(),
        "positiveOriginalUnitlessPointSpotLights":unitless_positive.size(),
        "positiveOriginalPointSpotLights":photometric_positive.size()+unitless_positive.size(),
        "originalZeroIntensityCount":original_zero,
        "sourceCandelaEquivalentMedian":median_photo,
        "sourceUnitlessMedian":median_unitless,
        "unitlessValuesNeverMixedWithCandelaLumens":true,
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

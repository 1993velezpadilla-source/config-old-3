extends SceneTree
func _initialize() -> void:
    call_deferred("_run")
func _run() -> void:
    var cls: Script=load("res://nacht_compatibility_source_relative_light_research.gd") as Script
    if cls==null or not cls.can_instantiate():
        push_error("XZOGOT_NACHT_COMPAT_ORIGINAL_RELATIVE_LIGHT_PARSER_RED")
        quit(2)
        return
    var root3d: Node3D=Node3D.new()
    root.add_child(root3d)
    var lights: Array[Light3D]=[]
    for i: int in range(165):
        var light: Light3D=null
        if i<144:
            light=OmniLight3D.new()
        elif i<163:
            light=SpotLight3D.new()
        else:
            light=DirectionalLight3D.new()
        light.light_energy=1.0 if i!=164 else 0.0
        light.set_meta("source_intensity",float((i%7+1)*150) if i<163 else (0.0 if i==164 else 0.2))
        light.set_meta("source_intensity_units","Candelas" if i<163 else "Lux")
        root3d.add_child(light)
        lights.append(light)
    var control: RefCounted=cls.new() as RefCounted
    var invalid: Dictionary=control.call(
        "apply_original_source_light_ratios_research",root3d,100,4.0) as Dictionary
    if (invalid.get("errors",[]) as Array).is_empty():
        push_error("XZOGOT_NACHT_COMPAT_SOURCE_LIGHT_INVALID_ACTOR_CENSUS_ACCEPTED_RED")
        quit(3)
        return
    var result: Dictionary=control.call(
        "apply_original_source_light_ratios_research",root3d,10793,4.0) as Dictionary
    if (not (result.get("errors",[]) as Array).is_empty()
        or int(result.get("sourceLightNodeCountIncludingDirectional",0))!=165
        or int(result.get("positiveOriginalPhotometricPointSpotLights",0))!=163
        or not result.get("absoluteUEPhotometricEquivalenceNotProven",false)):
        push_error("XZOGOT_NACHT_COMPAT_ORIGINAL_LIGHT_RELATIVE_AUDIT_RED "+JSON.stringify(result))
        quit(4)
        return
    if is_equal_approx(lights[0].light_energy,lights[6].light_energy):
        push_error("XZOGOT_NACHT_COMPAT_SOURCE_ORIGINAL_CD_RATIO_NOT_APPLIED_RED")
        quit(5)
        return
    if lights[164].light_energy!=0.0 or lights[163].light_energy!=1.0:
        push_error("XZOGOT_NACHT_COMPAT_ORIGINAL_ZERO_AND_DIRECTIONAL_LOST_RED")
        quit(6)
        return
    var rollback: Dictionary=control.call("restore_source_light_energy") as Dictionary
    if (not (rollback.get("errors",[]) as Array).is_empty()
        or int(rollback.get("originalSourceLightEnergyResourcesRestored",0))!=165):
        push_error("XZOGOT_NACHT_COMPAT_SOURCE_LIGHT_RESTORE_RED "+JSON.stringify(rollback))
        quit(7)
        return
    for i: int in range(lights.size()):
        var expected: float=0.0 if i==164 else 1.0
        if not is_equal_approx(lights[i].light_energy,expected):
            push_error("XZOGOT_NACHT_COMPAT_LIGHT_RESTORATION_WRONG "+str(i))
            quit(8)
            return
    var twice: Dictionary=control.call("restore_source_light_energy") as Dictionary
    if (twice.get("errors",[]) as Array).is_empty():
        push_error("XZOGOT_NACHT_COMPAT_LIGHT_CONTROLLER_ACCEPTED_DUPLICATE_RESTORE_RED")
        quit(9)
        return
    print("XZOGOT_NACHT_COMPAT_165_LIGHT_AUTHORED_INTENSITY_RATIOS_GODOT461_PROBE_GREEN "+
        JSON.stringify(result))
    quit(0)

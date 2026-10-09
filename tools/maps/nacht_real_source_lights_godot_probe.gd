extends SceneTree
## Independent TRUE source-light placement audit in real Godot 4.6.1.
## Uses existing xziel_benchmark_loader.gd to mount CUE4Parse UE4.21 xzen lights
## onto the independently verified 10,793-actor Meridian source scene.
## Not a per-pixel lighting parity test; not official Black Ops III T7.

func _initialize() -> void:
    call_deferred("_audit")

func _audit() -> void:
    var source: Variant = JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-authority/xzen-report.json")
    )
    if not (source is Dictionary):
        push_error("XZOGOT_NACHT_REAL_LIGHT_SOURCE_REPORT_MISSING_RED")
        quit(2)
        return
    var records: Array = source.get("lights", [])
    if records.size() != 166:
        push_error("XZOGOT_NACHT_SOURCE_LIGHT_COUNT_RED count=" + str(records.size()))
        quit(3)
        return
    var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if packed == null:
        push_error("XZOGOT_NACHT_MERIDIAN_SOURCE_SCENE_MISSING_RED")
        quit(4)
        return
    var world: Node = packed.instantiate()
    get_root().add_child(world)
    var meshes: Array[Node] = world.find_children("*","MeshInstance3D",true,false)
    if meshes.size()!=10793:
        push_error("XZOGOT_NACHT_WORLD_MESHES_LOST_RED")
        quit(5)
        return

    var loader_script: Script = load("res://scripts/xziel_benchmark_loader.gd") as Script
    if loader_script == null:
        push_error("XZOGOT_NACHT_SHIPPING_SOURCE_LIGHT_BINDER_MISSING_RED")
        quit(6)
        return
    var binder: Node3D = loader_script.new() as Node3D
    binder.set("load_on_ready",false)
    binder.set("build_materials",false)
    binder.set("build_lights",true)
    binder.set("build_skeletal_actors",false)
    binder.set("source_root","res://nacht-authority")
    binder.set("light_report_file","xzen-report.json")
    binder.set("source_environment_truth_file","res://nacht-authority/source-environment-truth.json")
    get_root().add_child(binder)
    var root: Node3D = Node3D.new()
    root.name = "NativeUE421SourceLighting"
    root.basis = Basis(
        Vector3(0.0,0.0,-1.0),
        Vector3(-1.0,0.0,0.0),
        Vector3(0.0,1.0,0.0)
    )
    binder.add_child(root)
    binder.set("_runtime_root", root)
    binder.call("_build_source_lights")

    var originals: Dictionary = {}
    var unsupported: Array[String] = []
    for raw: Variant in records:
        var row: Dictionary = raw as Dictionary
        var id: String = str(row.get("id",""))
        if id.is_empty() or originals.has(id):
            push_error("XZOGOT_NACHT_SOURCE_LIGHT_IDENTITIES_NOT_UNIQUE_RED")
            quit(7)
            return
        originals[id] = row
        if not str(row.get("componentType","")) in ["point","spot","directional","sky"]:
            unsupported.append(id)
    if not unsupported.is_empty():
        push_error("XZOGOT_NACHT_SOURCE_LIGHT_UNSUPPORTED_RED "+str(unsupported.slice(0,12)))
        quit(8)
        return

    var accepted: int = 0
    var worst_position_m: float = 0.0
    var zero_intensity_proven: int = 0
    var sky_count: int = 0
    var errors: Array[String] = []
    for raw: Variant in records:
        var row: Dictionary = raw as Dictionary
        var id: String = str(row["id"])
        var source_type: String = str(row["componentType"])
        if source_type=="sky":
            sky_count += 1
            continue
        var found: Node = root.get_node_or_null(NodePath(id))
        if not (found is Light3D):
            errors.append(id+" source light not instantiated")
            continue
        var light: Light3D = found as Light3D
        accepted += 1
        var loc: Array = row.get("worldPositionMeters",[])
        if loc.size()!=3:
            errors.append(id+" missing source location")
            continue
        var expected: Vector3 = Vector3(-float(loc[1]),float(loc[2]),-float(loc[0]))
        var err_m: float = light.global_position.distance_to(expected)
        worst_position_m = maxf(worst_position_m, err_m)
        if err_m > 0.001:
            errors.append(id+" source light world transform err_m="+str(err_m))
        var intensity: float = float(row.get("intensity",1.0))
        if is_zero_approx(intensity):
            zero_intensity_proven += 1
            if not is_zero_approx(light.light_energy):
                errors.append(id+" source zero intensity was invented as lit")
        if absf(float(light.get_meta("source_intensity",-9999.0))-intensity)>0.00001:
            errors.append(id+" authored source intensity metadata mismatch")
    var sky_nodes: Array[Node] = root.find_children("*","WorldEnvironment",true,false)
    if sky_count>0 and sky_nodes.is_empty():
        errors.append("source sky light not mounted as WorldEnvironment")
    var total: int = int(binder.get_meta("xziel_benchmark_light_count",-1))
    if total!=records.size():
        errors.append("source light count mismatch "+str(total)+"/"+str(records.size()))
    var result: Dictionary = {
        "source": "archived Pavlov UE4.21, not original BO3 T7",
        "original_source_mesh_instances": meshes.size(),
        "native_source_light_records":records.size(),
        "godot_registered_source_lights":total,
        "positional_source_lights":accepted,
        "sky_components":sky_count,
        "maximum_source_light_world_position_error_m":worst_position_m,
        "source_zero_intensity_lights_kept_dark":zero_intensity_proven,
        "errors_first_30":errors.slice(0,30),
        "lighting_pixel_equivalence_proven":false,
        "materials_textures_loaded_by_this_light_gate":false,
        "android_performance_proven":false
    }
    var out: FileAccess = FileAccess.open("res://native-source-light-audit.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(result,"\t"))
    out.close()
    binder.queue_free()
    world.queue_free()
    if not errors.is_empty() or worst_position_m>0.001:
        push_error("XZOGOT_NACHT_REAL_UE421_LIGHTS_GODOT_RED "+JSON.stringify(result))
        quit(9)
        return
    print("XZOGOT_NACHT_166_REAL_UE421_LIGHTS_GODOT_SOURCE_PLACEMENT_GREEN",
        " source_lights=",total,
        " world_positional_lights=",accepted,
        " sky_components=",sky_count,
        " max_position_error_m=",worst_position_m,
        " zero_source_intensity_lights=",zero_intensity_proven)
    quit(0)

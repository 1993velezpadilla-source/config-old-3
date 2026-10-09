extends SceneTree
## FULL original source UE4.21 actor/material DDS parity in actual Godot 4.6.1
## Metadata bridge: 10793 actors, 574 XZMI effective materials, 16595 surfaces.
## Uses original in-repo XzielBenchmarkLoader for SOURCE-authored material logic.
## No BO3 T7 attribution or pixel/render/Android performance claim.

func _initialize() -> void:
    call_deferred("_run")

func _run() -> void:
    var raw: String = FileAccess.get_file_as_string("res://nacht-actor-material-authority.json")
    var report: Variant = JSON.parse_string(raw)
    if not (report is Dictionary):
        push_error("XZOGOT_NACHT_NATIVE_MATERIAL_BRIDGE_ABSENT_RED")
        quit(3)
        return
    var bridge: Dictionary = report as Dictionary
    if (int(bridge.get("sourceActorCount",0)) != 10793 or
        int(bridge.get("originalSourceSurfaceBindings",0)) != 16595 or
        int(bridge.get("distinctSourceEffectiveMaterials",0)) != 574):
        push_error("XZOGOT_NACHT_SOURCE_MATERIAL_BRIDGE_INCOMPLETE_RED")
        quit(4)
        return

    var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if packed == null:
        push_error("XZOGOT_NACHT_LOSSLESS_MERIDIAN_SCENE_RED")
        quit(5)
        return
    var world: Node = packed.instantiate()
    get_root().add_child(world)
    var nodes: Array[Node] = world.find_children("*", "MeshInstance3D", true, false)
    if nodes.size() != 10793:
        push_error("XZOGOT_NACHT_LOSSLESS_FULL_MESH_NODE_LOSS_RED")
        quit(6)
        return
    var mesh_by_actor: Dictionary = {}
    for raw_node: Node in nodes:
        var mi: MeshInstance3D = raw_node as MeshInstance3D
        var name_text: String = str(mi.name)
        var at: int = name_text.find("_native_exact_")
        if at < 0:
            push_error("XZOGOT_NACHT_MISSING_REAL_GLTF_ACTOR_NODE_RED " + name_text)
            quit(7)
            return
        var actor: String = name_text.substr(0,at)
        if mesh_by_actor.has(actor):
            push_error("XZOGOT_NACHT_MULTIPLE_NATIVE_NODE_UNSUPPORTED_RED " + actor)
            quit(8)
            return
        mesh_by_actor[actor] = mi
    if mesh_by_actor.size() != 10793:
        push_error("XZOGOT_NACHT_SOURCE_ACTOR_COUNT_RED")
        quit(9)
        return

    var loader_script: Script = load("res://scripts/xziel_benchmark_loader.gd") as Script
    if loader_script == null:
        push_error("XZOGOT_NACHT_REUSE_PRODUCTION_SOURCE_BINDER_MISSING_RED")
        quit(10)
        return
    var binder: Node3D = loader_script.new() as Node3D
    binder.set("load_on_ready", false)
    binder.set("build_materials", true)
    binder.set("build_lights", false)
    binder.set("build_skeletal_actors", false)
    binder.set("source_root", "res://nacht-authority")
    binder.set("vfs_map_root", "vfs/xziel/maps/xziel_nacht_chronicles")
    get_root().add_child(binder)
    binder.call("_prepare_material_authority")

    var errors: Array[String] = []
    var bound: int = 0
    var textured: int = 0
    var actor_count: int = 0
    var textured_materials: Dictionary = {}
    var unique_paths: Dictionary = {}
    for row_var: Variant in bridge["actors"]:
        var row: Dictionary = row_var as Dictionary
        var iid: String = str(row["actorId"])
        var mesh_index: int = int(row["meshIndex"])
        if not mesh_by_actor.has(iid):
            errors.append(iid + " native GLB actor absent")
            continue
        var mesh_node: MeshInstance3D = mesh_by_actor[iid]
        var slots: Array = row["sourceMaterialPaths"]
        if mesh_node.mesh.get_surface_count() != slots.size():
            errors.append(iid + " surface count mismatch " +
                str(mesh_node.mesh.get_surface_count()) + "/" + str(slots.size()))
            continue
        binder.call("_apply_instance_materials",mesh_node,iid,mesh_index,0)
        actor_count += 1
        for i in range(slots.size()):
            var effective: String = str(slots[i])
            unique_paths[effective] = true
            var mat: Material = mesh_node.get_surface_override_material(i)
            if mat == null:
                errors.append(iid + " surface=" + str(i) + " missing original bound material")
                continue
            bound += 1
            var std: StandardMaterial3D = mat as StandardMaterial3D
            if std != null and std.albedo_texture != null:
                textured += 1
                textured_materials[effective] = true
    var tex_hits: int = int(binder.get("_source_texture_resource_hits"))
    var result: Dictionary = {
        "source":"actual archived Pavlov UE4.21 XZMI/XZML original DDS, NOT BO3 T7",
        "source_actors":10793,
        "actual_godot_actors":actor_count,
        "actual_godot_source_surface_bindings":bound,
        "expected_original_source_surface_bindings":16595,
        "unique_original_effective_material_paths":unique_paths.size(),
        "unique_original_effective_materials_with_loaded_albedo":textured_materials.size(),
        "actual_godot_textured_surfaces":textured,
        "original_DDS_resource_hits":tex_hits,
        "original_look_identical_to_BO3_T7":false,
        "full_pixel_render_parity_proven":false,
        "android_fps_tested":false,
        "errors_count":errors.size(),
        "errors_first_40":errors.slice(0,40)
    }
    var file: FileAccess = FileAccess.open("res://nacht-full-original-material-godot-report.json",FileAccess.WRITE)
    file.store_string(JSON.stringify(result,"\t"))
    file.close()
    binder.queue_free()
    world.queue_free()
    if (not errors.is_empty() or actor_count!=10793 or bound!=16595
            or unique_paths.size()!=574 or textured_materials.size()<500
            or tex_hits<500):
        push_error("XZOGOT_NACHT_ALL_ORIGINAL_SOURCE_MATERIALS_GODOT_RED " +
            JSON.stringify(result))
        quit(11)
        return
    print("XZOGOT_NACHT_ALL_10793_SOURCE_574_MATERIALS_GODOT_GREEN",
          " actors=",actor_count," authoritative_surfaces=",bound,
          " distinct_original_materials=",unique_paths.size(),
          " textured_materials=",textured_materials.size(),
          " textured_surfaces=",textured,
          " actual_source_DDS_resource_hits=",tex_hits)
    quit(0)

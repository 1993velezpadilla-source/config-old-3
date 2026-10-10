extends SceneTree
## Independent authored Pavlov UE4.21 material binding proof on lossless Meridian GLB.
## Uses existing shipping XzielBenchmarkLoader material/texture resolver.
## Samples distinct real material types. No gameplay, screenshots or BO3 T7 claims.

func _initialize() -> void:
    call_deferred("_probe")

func _probe() -> void:
    var raw: String = FileAccess.get_file_as_string(
        "res://nacht-authority/material-preview-samples.json"
    )
    var manifest: Variant = JSON.parse_string(raw)
    if not (manifest is Dictionary):
        push_error("XZOGOT_NACHT_AUTHORED_SAMPLE_MANIFEST_RED")
        quit(2)
        return
    var samples: Array = manifest["samples"]
    if samples.size() < 8:
        push_error("XZOGOT_NACHT_ORIGINAL_DIFFUSE_SAMPLES_TOO_FEW_RED")
        quit(3)
        return
    var scene: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if scene == null:
        push_error("XZOGOT_NACHT_MERIDIAN_FULL_SCENE_MISSING_RED")
        quit(4)
        return
    var world: Node = scene.instantiate()
    get_root().add_child(world)
    var nodes: Array[Node] = world.find_children("*", "MeshInstance3D", true, false)
    if nodes.size() != 10793:
        push_error("XZOGOT_NACHT_MERIDIAN_FULL_NODE_LOSS_RED " + str(nodes.size()))
        quit(5)
        return

    var by_actor: Dictionary = {}
    for raw_node: Node in nodes:
        var node: MeshInstance3D = raw_node as MeshInstance3D
        var strname: String = str(node.name)
        var marker: String = "_native_exact_"
        var at: int = strname.find(marker)
        if at < 0:
            push_error("XZOGOT_NACHT_SOURCE_ACTOR_ID_LOST_RED name=" + strname)
            quit(6)
            return
        var actor: String = strname.substr(0,at)
        if not by_actor.has(actor):
            by_actor[actor] = []
        by_actor[actor].append(node)
    if by_actor.size() != 10793:
        push_error("XZOGOT_NACHT_ORIGINAL_ACTOR_NODE_ID_LOSS_RED " + str(by_actor.size()))
        quit(7)
        return

    var loader_script: Script = load("res://scripts/xziel_benchmark_loader.gd") as Script
    if loader_script == null:
        push_error("XZOGOT_NACHT_EXISTING_MATERIAL_LOADER_MISSING_RED")
        quit(8)
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
    var material_bound: int = 0
    var sourced_albedo: int = 0
    var checked_actors: int = 0
    var unique_paths: Dictionary = {}
    for raw_sample: Variant in samples:
        var sample: Dictionary = raw_sample as Dictionary
        var iid: String = str(sample["actorId"])
        var idx: int = int(sample["meshIndex"])
        var target: int = int(sample["targetSurface"])
        var material_path: String = str(sample["sourceMaterialPath"])
        if not by_actor.has(iid):
            errors.append(iid + ": imported source node missing")
            continue
        var chunks: Array = by_actor[iid]
        chunks.sort_custom(func(a: MeshInstance3D, b: MeshInstance3D) -> bool:
            return str(a.name) < str(b.name))
        var surface_offset: int = 0
        var target_surface: Material = null
        for item: Variant in chunks:
            var mesh_node: MeshInstance3D = item as MeshInstance3D
            var count: int = mesh_node.mesh.get_surface_count()
            binder.call("_apply_instance_materials",
                mesh_node, iid, idx, surface_offset)
            for s in range(count):
                var bound: Material = mesh_node.get_surface_override_material(s)
                if bound != null:
                    material_bound += 1
                if surface_offset + s == target:
                    target_surface = bound
            surface_offset += count
        if surface_offset != int(sample["sourceSurfaceCount"]):
            errors.append(iid + ": authored primitive count differs")
        if target_surface == null:
            errors.append(iid + ": original selected surface not material-bound")
            continue
        var std: StandardMaterial3D = target_surface as StandardMaterial3D
        if std == null or std.albedo_texture == null:
            errors.append(iid + ": original DDS albedo not loaded")
            continue
        sourced_albedo += 1
        checked_actors += 1
        unique_paths[material_path] = true
    var report: Dictionary = {
        "authority": "genuine archived Pavlov UE4.21 surface/material + original DDS - NOT BO3 T7",
        "godot_engine": Engine.get_version_info().get("string", ""),
        "scene_actors": by_actor.size(),
        "scene_mesh_nodes": nodes.size(),
        "sampled_original_actors": samples.size(),
        "verified_source_DDS_albedo_textures": sourced_albedo,
        "bound_source_surface_materials": material_bound,
        "verified_unique_authored_material_paths": unique_paths.size(),
        "errors": errors,
        "all_10793_actors_material_rendered": false,
        "identical_source_pixel_render_proven": false,
        "original_BO3_T7_proven": false
    }
    var out: FileAccess = FileAccess.open(
        "res://nacht-authored-material-godot-probe.json", FileAccess.WRITE
    )
    out.store_string(JSON.stringify(report, "\t"))
    out.close()
    binder.queue_free()
    world.queue_free()
    if not errors.is_empty():
        push_error("XZOGOT_NACHT_AUTHORED_GODOT_MATERIAL_SAMPLE_RED " +
            str(errors.slice(0,12)))
        quit(9)
        return
    print("XZOGOT_NACHT_REAL_SOURCE_DDS_AND_AUTHORED_MATERIAL_IN_GODOT_GREEN",
        " source_actors=", checked_actors,
        " unique_materials=", unique_paths.size(),
        " original_DDS_albedos=", sourced_albedo,
        " source_material_surface_bindings=", material_bound)
    quit(0)

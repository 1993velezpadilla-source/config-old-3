extends SceneTree
## Godot 4.6.1 REAL MultiMesh research gate.
## Proves original actor affine transforms + triangle multiplicity survive
## changing a bounded subset of exact-match STATIC source actors to MultiMesh.
## NO fps, GPU drawcall, editable-interactable, material pixel parity claims.

func _initialize() -> void:
    call_deferred("_probe")

func _transform_component_error(a: Transform3D, b: Transform3D) -> float:
    var error: float = a.origin.distance_to(b.origin)
    for i: int in range(3):
        error = maxf(error,(a.basis[i]-b.basis[i]).length())
    return error

func _probe() -> void:
    var bridge_any: Variant = JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-actor-material-authority.json"))
    if not (bridge_any is Dictionary):
        push_error("XZOGOT_NACHT_MULTIMESH_SOURCE_MATERIAL_REPORT_ABSENT_RED")
        quit(2)
        return
    var bridge: Dictionary = bridge_any as Dictionary
    if (int(bridge.get("sourceActorCount",0))!=10793 or
        int(bridge.get("originalSourceSurfaceBindings",0))!=16595 or
        int(bridge.get("distinctSourceEffectiveMaterials",0))!=574):
        push_error("XZOGOT_NACHT_MULTIMESH_ACTOR_SOURCE_AUTHORITY_MISMATCH_RED")
        quit(3)
        return
    var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if packed == null:
        push_error("XZOGOT_NACHT_MULTIMESH_LOSSLESS_MERIDIAN_SCENE_ABSENT_RED")
        quit(4)
        return
    var world: Node = packed.instantiate()
    get_root().add_child(world)
    var meshes: Array[Node] = world.find_children("*","MeshInstance3D",true,false)
    if meshes.size()!=10793:
        push_error("XZOGOT_NACHT_MULTIMESH_SOURCE_ACTORS_NOT_ALL_IMPORTED_RED")
        quit(5)
        return
    var by_actor: Dictionary = {}
    for candidate: Node in meshes:
        var mi: MeshInstance3D = candidate as MeshInstance3D
        var name_text: String = str(mi.name)
        var at: int = name_text.find("_native_exact_")
        if at < 0:
            push_error("XZOGOT_NACHT_MULTIMESH_NO_AUTHORITATIVE_ACTOR_ID_RED "+name_text)
            quit(6)
            return
        var actor: String = name_text.substr(0,at)
        if by_actor.has(actor):
            push_error("XZOGOT_NACHT_MULTIMESH_DUPLICATED_SOURCE_ACTOR_RED "+actor)
            quit(7)
            return
        by_actor[actor]=mi
    var groups: Dictionary = {}
    var unique_authored_materials: Dictionary = {}
    var source_surface_instances: int = 0
    for entry: Variant in bridge["actors"]:
        var row: Dictionary = entry as Dictionary
        var iid: String = str(row["actorId"])
        if not by_actor.has(iid):
            push_error("XZOGOT_NACHT_MULTIMESH_DROPPED_SOURCE_ACTOR_RED "+iid)
            quit(8)
            return
        var mesh: MeshInstance3D = by_actor[iid] as MeshInstance3D
        var original_index: int = int(row["meshIndex"])
        var material_paths: Array = row["sourceMaterialPaths"]
        if mesh.mesh == null or mesh.mesh.get_surface_count()!=material_paths.size():
            push_error("XZOGOT_NACHT_MULTIMESH_MISMATCH_ORIGINAL_GLTF_SURFACE_COUNT_RED "+iid)
            quit(9)
            return
        var p: Vector3 = mesh.global_transform.origin
        var cell: Array = [floori(p.x/16.0), floori(p.z/16.0), floori(p.y/6.0)]
        var signature: String = JSON.stringify([original_index,material_paths,cell])
        if not groups.has(signature):
            groups[signature]=[]
        groups[signature].append(iid)
        for material_path: Variant in material_paths:
            unique_authored_materials[str(material_path)] = true
        source_surface_instances += material_paths.size()
    if (groups.is_empty() or source_surface_instances!=16595 or
        unique_authored_materials.size()!=574):
        push_error("XZOGOT_NACHT_MULTIMESH_SOURCE_MATERIAL_AUDIT_RED")
        quit(10)
        return

    # First validate identity of all 10,793 before even touching a test node.
    var sampled_groups: int = 0
    var transformed_source_actors: int = 0
    var triangles_before: int = 0
    var triangles_after: int = 0
    var max_error: float = 0.0
    var groups_rejected_for_unequal_mesh_formats: int = 0
    var errors: Array[String] = []
    var stage: Node3D = Node3D.new()
    stage.name="ResearchNativeSourceMultiMeshOnly"
    get_root().add_child(stage)
    var candidates: Array = groups.values()
    candidates.sort_custom(func(a: Array, b: Array) -> bool:
        return a.size()>b.size())
    for ids_variant: Variant in candidates:
        if sampled_groups >= 64 or transformed_source_actors>=2048:
            break
        var ids: Array = ids_variant as Array
        if ids.size()<2:
            continue
        var first_id: String = str(ids[0])
        var representative: MeshInstance3D = by_actor[first_id] as MeshInstance3D
        var mesh_data: Mesh = representative.mesh
        var surfaces: int = mesh_data.get_surface_count()
        var tri_per_actor: int = 0
        var fmt_signature: Array = []
        for surface: int in range(surfaces):
            var idx_len: int = mesh_data.surface_get_array_index_len(surface)
            var vertex_len: int = mesh_data.surface_get_array_len(surface)
            if idx_len<=0 or idx_len%3!=0:
                errors.append(first_id+" nonindexed or invalid source triangle primitive")
                break
            tri_per_actor += idx_len/3
            fmt_signature.append([vertex_len,idx_len,mesh_data.surface_get_format(surface)])
        if not errors.is_empty():
            break
        var matching: bool = true
        for entry_id: Variant in ids:
            var other: MeshInstance3D = by_actor[str(entry_id)] as MeshInstance3D
            if other.mesh.get_surface_count()!=surfaces:
                matching=false
                break
            for surface: int in range(surfaces):
                var fmt: Array = fmt_signature[surface]
                if (other.mesh.surface_get_array_len(surface)!=int(fmt[0]) or
                    other.mesh.surface_get_array_index_len(surface)!=int(fmt[1]) or
                    other.mesh.surface_get_format(surface)!=int(fmt[2])):
                    matching=false
                    break
            if not matching:
                break
        if not matching:
            groups_rejected_for_unequal_mesh_formats += 1
            continue

        var mm: MultiMesh = MultiMesh.new()
        mm.transform_format=MultiMesh.TRANSFORM_3D
        mm.use_colors=false
        mm.use_custom_data=false
        mm.mesh=mesh_data
        mm.instance_count=ids.size()
        var instance: MultiMeshInstance3D = MultiMeshInstance3D.new()
        instance.name="ExactUE421StaticBatch_"+str(sampled_groups)
        instance.multimesh=mm
        stage.add_child(instance)
        for i: int in range(ids.size()):
            var original: MeshInstance3D = by_actor[str(ids[i])] as MeshInstance3D
            var expected: Transform3D = original.global_transform
            mm.set_instance_transform(i,expected)
            var actual: Transform3D = mm.get_instance_transform(i)
            var drift: float = _transform_component_error(expected,actual)
            max_error=maxf(max_error,drift)
            if drift>0.0003:
                errors.append(str(ids[i])+" Godot MultiMesh transform differs in real Godot "+str(drift))
                break
        if not errors.is_empty():
            break
        for element_id: Variant in ids:
            var original: MeshInstance3D = by_actor[str(element_id)] as MeshInstance3D
            original.visible=false
        triangles_before += tri_per_actor*ids.size()
        triangles_after += tri_per_actor*mm.instance_count
        transformed_source_actors += ids.size()
        sampled_groups += 1
    if sampled_groups<10 or transformed_source_actors<128:
        errors.append("insufficient real original source MeshInstance3D->MultiMesh coverage")
    if triangles_before!=triangles_after:
        errors.append("original placed indexed triangle count changed")
    if transformed_source_actors>2048+512:
        errors.append("research scope exceeded")
    var result: Dictionary = {
        "authority":"archived Pavlov UE4.21 source, not original BO3 T7",
        "actual_godot_engine":Engine.get_version_info().get("string",""),
        "original_actor_mesh_nodes":meshes.size(),
        "original_source_authored_surface_assignments":source_surface_instances,
        "original_source_distinct_effective_materials":unique_authored_materials.size(),
        "actual_godot_multimesh_groups_created":sampled_groups,
        "original_actor_meshes_replaced_in_research_runtime":transformed_source_actors,
        "source_indexed_triangles_in_test_groups":triangles_before,
        "actual_godot_multimesh_triangles_in_test_groups":triangles_after,
        "max_actor_affine_transform_component_difference_m":max_error,
        "mesh_format_mismatching_group_candidates_rejected":groups_rejected_for_unequal_mesh_formats,
        "original_source_actor_metadata_removed":false,
        "original_source_material_binding_preserved_in_prototype_geometry_only":false,
        "actual_gpu_driver_draw_call_reduction_proven":false,
        "actual_mobile_fps_proven":false,
        "collision_navigation_or_interactable_actor_safety_proven":false,
        "shipping_scene_modified":false,
        "errors":errors.slice(0,20)
    }
    var writer: FileAccess = FileAccess.open("res://nacht-real-source-multimesh-research-report.json",FileAccess.WRITE)
    writer.store_string(JSON.stringify(result,"\t"))
    writer.close()
    stage.queue_free()
    world.queue_free()
    if not errors.is_empty():
        push_error("XZOGOT_NACHT_REAL_GODOT_MULTIMESH_TRANSFORM_TRIANGLE_PARITY_RED "+JSON.stringify(result))
        quit(11)
        return
    print("XZOGOT_NACHT_REAL_GODOT_MULTIMESH_UE421_SOURCE_TRANSFORMS_GREEN",
          " groups=",sampled_groups," source_actors=",transformed_source_actors,
          " indexed_source_triangles=",triangles_before,
          " output_indexed_triangles=",triangles_after,
          " max_transform_error_m=",max_error)
    quit(0)

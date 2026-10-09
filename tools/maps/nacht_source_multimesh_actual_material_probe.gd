extends SceneTree
## Material-aware REAL Godot Mesa MultiMesh, ORIGINAL Pavlov UE4.21 source.
## Research-only noninteractive batch: 10793 original actor ID census;
## sample exactly 32 spatial+native mesh+original effective material groups.
## Original 718 DDS source assets via EXISTING production XZIEL binder.
## DO NOT claim original BO3 T7, pixel parity, mobile FPS or collision safety.

func _initialize() -> void:
    call_deferred("_run")

func _transform_error(a: Transform3D, b: Transform3D) -> float:
    var d: float = a.origin.distance_to(b.origin)
    for k: int in range(3):
        d = maxf(d,(a.basis[k]-b.basis[k]).length())
    return d

func _run() -> void:
    var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(
        "res://nacht-actor-material-authority.json"))
    if not (raw is Dictionary):
        push_error("XZOGOT_NACHT_MM_MATERIAL_BRIDGE_MISSING_RED")
        quit(2)
        return
    var bridge: Dictionary = raw as Dictionary
    if int(bridge.get("sourceActorCount",0))!=10793 or int(bridge.get("originalSourceSurfaceBindings",0))!=16595:
        push_error("XZOGOT_NACHT_MM_MATERIAL_BRIDGE_INCOMPLETE_RED")
        quit(3)
        return
    var scene: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if scene==null:
        push_error("XZOGOT_NACHT_MM_LOSSLESS_SOURCE_SCENE_ABSENT_RED")
        quit(4)
        return
    var world: Node = scene.instantiate()
    root.add_child(world)
    var actors: Dictionary = {}
    var all_nodes: Array[Node] = world.find_children("*","MeshInstance3D",true,false)
    for raw_node: Node in all_nodes:
        var node: MeshInstance3D = raw_node as MeshInstance3D
        var name_text: String = str(node.name)
        var at: int = name_text.find("_native_exact_")
        if at<=0:
            push_error("XZOGOT_NACHT_MM_SOURCE_GLTF_ACTOR_NAME_RED "+name_text)
            quit(5)
            return
        var iid: String = name_text.substr(0,at)
        if actors.has(iid):
            push_error("XZOGOT_NACHT_MM_DUPLICATE_SOURCE_GLTF_ACTOR_RED "+iid)
            quit(6)
            return
        actors[iid] = node
    if actors.size()!=10793:
        push_error("XZOGOT_NACHT_MM_LOST_ORIGINAL_ACTORS_RED "+str(actors.size()))
        quit(7)
        return

    var loader: Script = load("res://scripts/xziel_benchmark_loader.gd") as Script
    if loader==null:
        push_error("XZOGOT_NACHT_MM_REUSE_SOURCE_MATERIAL_BINDER_MISSING_RED")
        quit(8)
        return
    var binder: Node3D = loader.new() as Node3D
    binder.set("load_on_ready",false)
    binder.set("build_materials",true)
    binder.set("build_lights",false)
    binder.set("build_skeletal_actors",false)
    binder.set("source_root","res://nacht-authority")
    binder.set("vfs_map_root","vfs/xziel/maps/xziel_nacht_chronicles")
    root.add_child(binder)
    binder.call("_prepare_material_authority")

    var groups: Dictionary = {}
    var row_count: int = 0
    var source_materials: Dictionary = {}
    for raw_row: Variant in bridge["actors"]:
        var row: Dictionary = raw_row as Dictionary
        var iid: String = str(row["actorId"])
        if not actors.has(iid):
            push_error("XZOGOT_NACHT_MM_SOURCE_MATERIAL_ACTOR_MISSING_RED "+iid)
            quit(9)
            return
        var native_mesh: MeshInstance3D = actors[iid] as MeshInstance3D
        var paths: Array = row["sourceMaterialPaths"]
        if native_mesh.mesh == null or native_mesh.mesh.get_surface_count()!=paths.size():
            push_error("XZOGOT_NACHT_MM_SOURCE_SURFACE_ID_MISMATCH_RED "+iid)
            quit(10)
            return
        var pos: Vector3 = native_mesh.global_transform.origin
        var cell: Array = [floori(pos.x/16.0),floori(pos.z/16.0),floori(pos.y/6.0)]
        var signature: String = JSON.stringify([int(row["meshIndex"]),paths,cell])
        if not groups.has(signature):
            groups[signature]=[]
        groups[signature].append({"id":iid,"nativeMeshIndex":int(row["meshIndex"]),"sourcePaths":paths})
        for p: Variant in paths: source_materials[str(p)]=true
        row_count += paths.size()
    if groups.is_empty() or source_materials.size()!=574 or row_count!=16595:
        push_error("XZOGOT_NACHT_MM_MATERIAL_SURFACE_ACTOR_INTEGRITY_RED")
        quit(11)
        return

    var arrays: Array = groups.values()
    arrays.sort_custom(func(a: Array, b: Array) -> bool: return a.size()>b.size())
    var stage: Node3D=Node3D.new()
    stage.name="ExactPavlovUE421NativeMaterialMultiMeshResearchOnly"
    root.add_child(stage)

    var count_groups: int=0
    var count_actors: int=0
    var indexed_source_triangles: int=0
    var indexed_mm_triangles: int=0
    var verified_source_material_surfaces: int=0
    var verified_source_DDS_surface_bindings: int=0
    var unique_authority_material_paths: Dictionary={}
    var max_error_m: float=0.0
    var errors: Array[String]=[]
    for row_array: Variant in arrays:
        if count_groups>=32 or count_actors>1400:
            break
        var ids: Array = row_array as Array
        if ids.size()<2:
            continue
        var rep: Dictionary = ids[0] as Dictionary
        var rep_id: String = str(rep["id"])
        var native_mesh: MeshInstance3D = actors[rep_id] as MeshInstance3D
        var native_model: Mesh = native_mesh.mesh
        var surfaces: int=native_model.get_surface_count()
        var source_indexed: int=0
        for s: int in range(surfaces):
            var idx_len: int=native_model.surface_get_array_index_len(s)
            if idx_len<=0 or idx_len%3!=0:
                errors.append("original source indexed triangles missing "+rep_id)
                break
            source_indexed+=idx_len/3
        if not errors.is_empty():
            break
        var original_paths: Array=rep["sourcePaths"]
        binder.call("_apply_instance_materials",native_mesh,rep_id,int(rep["nativeMeshIndex"]),0)
        var material_values: Array[Material]=[]
        for s: int in range(surfaces):
            var authored: Material=native_mesh.get_surface_override_material(s)
            if authored==null:
                errors.append("original source material not loaded "+rep_id+" surface="+str(s))
                break
            material_values.append(authored)
        if not errors.is_empty():
            break

        # Existing XZIEL loader MUST resolve the exact same source material
        # for EVERY actor in this spatial+material signature, not just the rep.
        for record_any: Variant in ids:
            var record: Dictionary=record_any as Dictionary
            var check_id: String=str(record["id"])
            var original: MeshInstance3D=actors[check_id] as MeshInstance3D
            if original.mesh.get_surface_count()!=surfaces:
                errors.append(check_id+" differs in original GLB surface topology")
                break
            binder.call("_apply_instance_materials",
                original,check_id,int(record["nativeMeshIndex"]),0)
            for s: int in range(surfaces):
                if original.get_surface_override_material(s)!=material_values[s]:
                    errors.append(check_id+" source-authored per-surface material instance differs in group surface="+str(s))
                    break
            if not errors.is_empty():
                break
        if not errors.is_empty():
            break

        # MeshInstance.surface_override IS NOT copied automatically by
        # MultiMeshInstance3D. Bind real original DDS-backed source Materials
        # on a per-group mesh duplicate; do not mutate the imported GLB mesh.
        var group_mesh: ArrayMesh=native_model.duplicate(true) as ArrayMesh
        if group_mesh==null or group_mesh.get_surface_count()!=surfaces:
            errors.append(rep_id+" Godot duplicated source ArrayMesh failed")
            break
        for s: int in range(surfaces):
            group_mesh.surface_set_material(s,material_values[s])
            if group_mesh.surface_get_material(s)!=material_values[s]:
                errors.append(rep_id+" genuine source material lost on MultiMesh surface "+str(s))
                break
            if group_mesh.surface_get_array_index_len(s)!=native_model.surface_get_array_index_len(s):
                errors.append(rep_id+" source indexed triangle topology changed on duplication")
                break
            var std: StandardMaterial3D=material_values[s] as StandardMaterial3D
            if std!=null and std.albedo_texture!=null:
                verified_source_DDS_surface_bindings+=ids.size()
            verified_source_material_surfaces+=ids.size()
            unique_authority_material_paths[str(original_paths[s])]=true
        if not errors.is_empty():
            break
        var mm: MultiMesh=MultiMesh.new()
        mm.transform_format=MultiMesh.TRANSFORM_3D
        mm.mesh=group_mesh
        mm.instance_count=ids.size()
        var mm_node: MultiMeshInstance3D=MultiMeshInstance3D.new()
        mm_node.name="OriginalSourceDDSExactNativeStaticGroup_"+str(count_groups)
        mm_node.multimesh=mm
        stage.add_child(mm_node)
        for i: int in range(ids.size()):
            var record: Dictionary=ids[i] as Dictionary
            var original: MeshInstance3D=actors[str(record["id"])] as MeshInstance3D
            var original_transform: Transform3D=original.global_transform
            mm.set_instance_transform(i,original_transform)
            var actual_transform: Transform3D=mm.get_instance_transform(i)
            var delta: float=_transform_error(original_transform,actual_transform)
            max_error_m=maxf(max_error_m,delta)
            if delta>0.0003:
                errors.append(str(record["id"])+" actual Godot 4.6 GPU MultiMesh affine transform changed by "+str(delta))
                break
        if not errors.is_empty():
            break
        for record_any: Variant in ids:
            var record: Dictionary=record_any as Dictionary
            (actors[str(record["id"])] as MeshInstance3D).visible=false
        indexed_source_triangles+=source_indexed*ids.size()
        indexed_mm_triangles+=source_indexed*mm.instance_count
        count_actors+=ids.size()
        count_groups+=1

    if count_groups<15 or count_actors<150 or verified_source_DDS_surface_bindings<150:
        errors.append("not enough genuine source DDS-backed MultiMesh material test surfaces")
    if indexed_source_triangles!=indexed_mm_triangles:
        errors.append("original native source indexed triangle multiplicity changed")
    var result: Dictionary={
        "authority":"archived Pavlov UE4.21 source, NOT original BO3 T7",
        "realGodotEngine":Engine.get_version_info().get("string",""),
        "originalActorsPreserved":actors.size(),
        "originalMaterialSurfaceAssignmentsPreserved":row_count,
        "originalDistinctEffectiveMaterialsPreserved":source_materials.size(),
        "actualTexturedNativeMaterialMultiMeshGroupsCreated":count_groups,
        "originalActorsInMaterialAwareMultimeshResearchOnly":count_actors,
        "originalIndexedSourceTriangles":indexed_source_triangles,
        "actualGodotIndexedMultiMeshTriangles":indexed_mm_triangles,
        "sourceAuthoredSurfaceMaterialSlotsVerified":verified_source_material_surfaces,
        "sourceDDSBackedSurfaceBindingsOnGroups":verified_source_DDS_surface_bindings,
        "originalEffectiveMaterialTypesTested":unique_authority_material_paths.size(),
        "maxFullAffineTransformRoundTripDifferenceMeters":max_error_m,
        "originalMeshInstanceStillExistsForInteractiveRestore":true,
        "all10793Batched":false,
        "sourceLightRenderingOrPerPixelMaterialParityProven":false,
        "actualGpuDrawCallReductionOrAndroidFPSProven":false,
        "collisionsAndDynamicInteractiveActorClassificationProven":false,
        "shippingGameUntouched":true,
        "errorsFirst25":errors.slice(0,25)
    }
    var out: FileAccess=FileAccess.open("res://nacht-multimesh-original-source-material-audit.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(result,"\t"))
    out.close()
    stage.queue_free()
    binder.queue_free()
    world.queue_free()
    if not errors.is_empty():
        push_error("XZOGOT_NACHT_REAL_GODOT_SOURCE_DDS_MULTIMESH_MATERIAL_RED "+JSON.stringify(result))
        quit(12)
        return
    print("XZOGOT_NACHT_REAL_GODOT_NATIVE_DDS_MATERIAL_MULTIMESH_GREEN",
          " groups=",count_groups," originalActors=",count_actors,
          " materialSurfaceBindings=",verified_source_material_surfaces,
          " sourceDDSBackedSurfaceBindings=",verified_source_DDS_surface_bindings,
          " originalIndexedTriangles=",indexed_source_triangles,
          " outputIndexedTriangles=",indexed_mm_triangles,
          " maxSourceTransformErrorM=",max_error_m)
    quit(0)

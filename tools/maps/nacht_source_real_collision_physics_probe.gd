extends SceneTree
## Real Godot 4.6.1 physics smoke test of archived Pavlov UE4.21 triangles.
## RESEARCH ONLY: selective static mesh actors; NO claims that all 10793
## nodes have game-ready collisions, navigation, blockers or safe spawn.
## Never generate boxes/ramps or replace native triangles with guesses.

func _initialize() -> void:
    call_deferred("_run")

func _run() -> void:
    var resource: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if resource == null:
        push_error("XZOGOT_NACHT_PHYSICS_SOURCE_MERIDIAN_GLB_MISSING_RED")
        quit(2)
        return
    var scene: Node = resource.instantiate()
    root.add_child(scene)
    var nodes: Array[Node] = scene.find_children("*", "MeshInstance3D", true, false)
    if nodes.size() != 10793:
        push_error("XZOGOT_NACHT_PHYSICS_10793_ACTORS_NOT_PRESENT_RED")
        quit(3)
        return
    var mapping: Dictionary = {}
    for candidate: Node in nodes:
        var mesh_node: MeshInstance3D = candidate as MeshInstance3D
        var name_text: String = str(mesh_node.name)
        var cut: int = name_text.find("_native_exact_")
        if cut < 0:
            push_error("XZOGOT_NACHT_PHYSICS_ACTOR_ORIGINAL_SOURCE_ID_MISSING_RED")
            quit(4)
            return
        var name_id: String = name_text.substr(0, cut)
        if mapping.has(name_id):
            push_error("XZOGOT_NACHT_PHYSICS_ORIGINAL_SOURCE_ACTOR_DUPLICATE_RED")
            quit(5)
            return
        mapping[name_id] = mesh_node

    var authority: Variant = JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-actor-material-authority.json"))
    if not (authority is Dictionary):
        push_error("XZOGOT_NACHT_PHYSICS_SOURCE_SCENE_METADATA_ABSENT_RED")
        quit(6)
        return
    var report: Dictionary = authority as Dictionary
    if (int(report.get("sourceActorCount",0)) != 10793 or
        int(report.get("originalSourceSurfaceBindings",0)) != 16595):
        push_error("XZOGOT_NACHT_PHYSICS_AUTHORITY_SOURCE_ACTOR_CENSUS_RED")
        quit(7)
        return

    var trials: Array[Dictionary] = []
    var native_meshes: Dictionary = {}
    var rejected_degenerate: int = 0
    var rejected_complex: int = 0
    var rejected_no_faces: int = 0
    var errors: Array[String] = []
    # Analyze the ORIGINAL SOURCE mesh/triangle data. Select a diverse,
    # bounded sample of native models and independently positioned actors.
    for row_any: Variant in report["actors"]:
        if trials.size() >= 24:
            break
        var row: Dictionary = row_any as Dictionary
        var model: int = int(row["meshIndex"])
        if native_meshes.has(model):
            continue
        var actor_id: String = str(row["actorId"])
        if not mapping.has(actor_id):
            errors.append(actor_id + " missing from approved Godot scene")
            break
        var mi: MeshInstance3D = mapping[actor_id] as MeshInstance3D
        var mesh: Mesh = mi.mesh
        var indexed_triangles: int = 0
        var original_triangle_ray_candidates: Array[Array] = []
        if mesh == null:
            errors.append(actor_id + " original source mesh is null")
            break
        for surface: int in range(mesh.get_surface_count()):
            var indices_count: int = mesh.surface_get_array_index_len(surface)
            if indices_count == 0 or indices_count % 3 != 0:
                errors.append(actor_id + " non-indexed native source triangles unsupported")
                break
            indexed_triangles += indices_count / 3
        if not errors.is_empty():
            break
        if indexed_triangles > 5000 or indexed_triangles < 8:
            rejected_complex += 1
            continue
        for surface: int in range(mesh.get_surface_count()):
            var arrays: Array = mesh.surface_get_arrays(surface)
            var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
            var ids: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
            # Sample multiple distinct ORIGINAL indexed triangles, not an
            # invented collision proxy. First face may be an inner/occluded
            # surface and will not always be the first raycast hit.
            var step_faces: int = maxi(1, int((ids.size()/3)/10))
            for face: int in range(0,int(ids.size()/3),step_faces):
                var ix: int = face*3
                var a: Vector3 = mi.global_transform * verts[ids[ix]]
                var b: Vector3 = mi.global_transform * verts[ids[ix+1]]
                var c: Vector3 = mi.global_transform * verts[ids[ix+2]]
                var raw_normal: Vector3 = (b-a).cross(c-a)
                if raw_normal.length() < 0.10:
                    continue
                var center: Vector3 = (a+b+c)/3.0
                var normal: Vector3 = raw_normal.normalized()
                original_triangle_ray_candidates.append([
                    center+normal*0.5,center-normal*0.5])
                if original_triangle_ray_candidates.size()>=12:
                    break
            if original_triangle_ray_candidates.size()>=12:
                break
        if original_triangle_ray_candidates.is_empty():
            rejected_degenerate += 1
            continue
        native_meshes[model] = true
        trials.append({
            "sourceActorId":actor_id, "nativeModelIndex":model,
            "meshNode":mi, "originalIndexedTriangles":indexed_triangles,
            "originalAuthoredFaceRays":original_triangle_ray_candidates
        })
    if trials.size()<20 or not errors.is_empty():
        push_error("XZOGOT_NACHT_PHYSICS_TOO_FEW_VERIFIABLE_SOURCE_MESHES_RED "+
                   str(trials.size())+" errors="+str(errors))
        quit(8)
        return

    var passed: int = 0
    var indexed_source_triangles: int = 0
    var collision_shape_triangles: int = 0
    var max_hit_distance_m: float = 0.0
    var sample_results: Array[Dictionary] = []
    for test: Dictionary in trials:
        var mi: MeshInstance3D = test["meshNode"] as MeshInstance3D
        var shape: ConcavePolygonShape3D = mi.mesh.create_trimesh_shape() as ConcavePolygonShape3D
        if shape == null:
            errors.append(str(test["sourceActorId"])+" Godot failed to create ConcavePolygonShape3D")
            continue
        # Must be the same native indexed triangle stream. Allow NO hidden
        # simplification of walls/floors or generated collision proxies.
        var source_count: int = int(test["originalIndexedTriangles"])
        var physics_count: int = shape.get_faces().size()/3
        if source_count != physics_count:
            errors.append(str(test["sourceActorId"])+
                          " source-vs-shape triangles="+str(source_count)+"/"+str(physics_count))
            continue
        shape.backface_collision = true
        var body: StaticBody3D = StaticBody3D.new()
        body.name = "ResearchOnlyAuthoritativeSourceStatic_"+str(test["nativeModelIndex"])
        body.collision_layer = 1
        body.collision_mask = 0
        root.add_child(body)
        body.global_transform = mi.global_transform
        var collider: CollisionShape3D = CollisionShape3D.new()
        collider.shape = shape
        body.add_child(collider)
        # Verify physics server, NOT an AABB check in our own Python code.
        await physics_frame
        await physics_frame
        var hit: Dictionary = {}
        var used_trial: int = -1
        var hit_ray_origin: Vector3 = Vector3.ZERO
        var authored_rays: Array = test["originalAuthoredFaceRays"]
        for ray_index: int in range(authored_rays.size()):
            var endpoints: Array = authored_rays[ray_index] as Array
            for flip: bool in [false,true]:
                var ray_start: Vector3 = endpoints[1] if flip else endpoints[0]
                var ray_end: Vector3 = endpoints[0] if flip else endpoints[1]
                var ray: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
                    ray_start,ray_end,1)
                ray.collide_with_bodies = true
                ray.hit_back_faces = true
                hit = body.get_world_3d().direct_space_state.intersect_ray(ray)
                if not hit.is_empty() and hit.get("collider") == body:
                    used_trial = ray_index
                    hit_ray_origin = ray_start
                    break
            if used_trial >= 0:
                break
        if used_trial < 0:
            errors.append(str(test["sourceActorId"])+
                          " NONE of "+str(authored_rays.size())+
                          " independent original-source triangle raycasts hit the expected Godot PhysicsServer static body")
            print("XZOGOT_NACHT_PHYSICS_ORIGINAL_SOURCE_ACTOR_RAY_MISS_RED",
                  " source_actor=",test["sourceActorId"],
                  " native_mesh=",test["nativeModelIndex"],
                  " triangles=",source_count,
                  " first_src_ray=",authored_rays[0],
                  " actual_body_world=",body.global_transform,
                  " collider_disabled=",collider.disabled)
        else:
            passed += 1
            indexed_source_triangles += source_count
            collision_shape_triangles += physics_count
            var hit_distance: float = (hit["position"] as Vector3).distance_to(hit_ray_origin)
            max_hit_distance_m = maxf(max_hit_distance_m,hit_distance)
            sample_results.append({
                "actorID":str(test["sourceActorId"]),
                "sourceNativeModelType":int(test["nativeModelIndex"]),
                "originalTriangleCount":source_count,
                "GodotStaticBodyConcaveTriangleCount":physics_count,
                "originalTriangleRaysChecked":used_trial+1,
                "physicsServerRayHitSourceNativeTriangle":true
            })
        body.queue_free()
        await physics_frame
        if errors.size()>=6:
            break
    var result: Dictionary = {
        "authority":"Pavlov UE4.21 archived exact native original mesh GLB, not original BO3 T7",
        "sourceStaticActorCount":mapping.size(),
        "sourceStaticMaterialSurfaces":int(report["originalSourceSurfaceBindings"]),
        "researchStaticCollisionActorsTested":trials.size(),
        "researchActualPhysicsServerRayHitsPassed":passed,
        "uniqueOriginalNativeMeshTypesTested":native_meshes.size(),
        "originalTriangleCountOfPassedPhysicsShapes":indexed_source_triangles,
        "GodotConcaveCollisionTriangleCountOfPassedShapes":collision_shape_triangles,
        "maximumHitDistanceFromOriginalTrialRayOriginMeters":max_hit_distance_m,
        "rejectedTooComplexOrTinyModels":rejected_complex,
        "rejectedDegenerateOnlyModels":rejected_degenerate,
        "tests":sample_results,
        "sourceActorsCollisionEnabledInShipping":false,
        "entireMapGameplayCollisionParityProven":false,
        "originalDynamicBarricadeOrDoorClassificationProven":false,
        "mobilePhysicsCostOrFrameRateProven":false,
        "originalBO3T7Proven":false,
        "researchErrors":errors.slice(0,15)
    }
    var fd: FileAccess = FileAccess.open("res://nacht-source-native-static-physics-smoke.json",FileAccess.WRITE)
    fd.store_string(JSON.stringify(result,"\t"))
    fd.close()
    scene.queue_free()
    if passed<20 or not errors.is_empty() or indexed_source_triangles!=collision_shape_triangles:
        push_error("XZOGOT_NACHT_REAL_GODOT_SOURCE_NATIVE_TRIMESH_PHYSICS_RED "+JSON.stringify(result))
        quit(9)
        return
    print("XZOGOT_NACHT_REAL_GODOT_SOURCE_NATIVE_TRIMESH_STATIC_PHYSICS_GREEN",
          " originalActors=",mapping.size(),
          " nativeModelsCollisionTested=",passed,
          " sourceIndexedTriangles=",indexed_source_triangles,
          " actualGodotConcaveTriangles=",collision_shape_triangles,
          " realPhysicsServerRayHits=",passed)
    quit(0)

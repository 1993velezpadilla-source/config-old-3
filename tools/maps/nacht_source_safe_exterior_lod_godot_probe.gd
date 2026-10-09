extends SceneTree
## GODOT 4.6 native exterior-only visual policy safety gate.
## Runtime proof against actual lossless 10793-actor Godot MeshInstances.
## No reductions inside 55m main Nacht building protected play region,
## no structural geometry, no window/door/barricade, no physics changes.
## Research-only until original interactive exterior reachability is known.

func _initialize() -> void:
    call_deferred("_run")

func _distance_to_aabb_xz(point: Vector2, world_box: AABB) -> float:
    var closest_x: float = clampf(point.x,world_box.position.x,world_box.end.x)
    var closest_z: float = clampf(point.y,world_box.position.z,world_box.end.z)
    return point.distance_to(Vector2(closest_x,closest_z))

func _run() -> void:
    var policy_any: Variant = JSON.parse_string(FileAccess.get_file_as_string(
        "res://nacht-exterior-visual-policy.json"))
    var bridge_any: Variant = JSON.parse_string(FileAccess.get_file_as_string(
        "res://nacht-actor-material-authority.json"))
    if not (policy_any is Dictionary) or not (bridge_any is Dictionary):
        push_error("XZOGOT_NACHT_EXTERIOR_SOURCE_AUTHORITY_MISSING_RED")
        quit(2)
        return
    var policy: Dictionary = policy_any as Dictionary
    var bridge: Dictionary = bridge_any as Dictionary
    if (int(policy.get("sourceActorCount",0))!=10793 or
        int(policy.get("sourceNativeMeshTypes",0))!=493 or
        int(bridge.get("sourceActorCount",0))!=10793 or
        int(bridge.get("originalSourceSurfaceBindings",0))!=16595 or
        int(bridge.get("distinctSourceEffectiveMaterials",0))!=574):
        push_error("XZOGOT_NACHT_EXTERIOR_ACTOR_MATERIAL_SOURCE_IDENTITY_RED")
        quit(3)
        return
    var visual: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if visual == null:
        push_error("XZOGOT_NACHT_EXTERIOR_LOSSLESS_493_GLTF_SOURCE_MISSING_RED")
        quit(4)
        return
    var world: Node = visual.instantiate()
    root.add_child(world)
    var nodes: Array[Node] = world.find_children("*","MeshInstance3D",true,false)
    if nodes.size()!=10793:
        push_error("XZOGOT_NACHT_EXTERIOR_ORIGINAL_10793_OBJECTS_LOST_RED")
        quit(5)
        return
    var by_actor: Dictionary = {}
    for raw: Node in nodes:
        var mi: MeshInstance3D = raw as MeshInstance3D
        var txt: String = str(mi.name)
        var cut: int = txt.find("_native_exact_")
        if cut<0:
            push_error("XZOGOT_NACHT_EXTERIOR_NATIVE_SOURCE_GLTF_ID_MISSING_RED "+txt)
            quit(6)
            return
        var name_id: String = txt.substr(0,cut)
        if by_actor.has(name_id):
            push_error("XZOGOT_NACHT_EXTERIOR_DUPLICATE_ORIGINAL_ID_RED "+name_id)
            quit(7)
            return
        by_actor[name_id] = mi

    var type_by_actor: Dictionary = {}
    var material_slots: int = 0
    var material_unique: Dictionary = {}
    for entry_var: Variant in bridge["actors"]:
        var entry: Dictionary = entry_var as Dictionary
        var iid: String = str(entry["actorId"])
        if not by_actor.has(iid):
            push_error("XZOGOT_NACHT_EXTERIOR_AUTHORED_ACTOR_NOT_IN_GLB_RED "+iid)
            quit(8)
            return
        var mi: MeshInstance3D = by_actor[iid] as MeshInstance3D
        var paths: Array = entry["sourceMaterialPaths"]
        if mi.mesh == null or mi.mesh.get_surface_count()!=paths.size():
            push_error("XZOGOT_NACHT_EXTERIOR_NATIVE_GLTF_MATERIAL_SURFACES_DIFFER_RED "+iid)
            quit(9)
            return
        if type_by_actor.has(iid):
            push_error("XZOGOT_NACHT_EXTERIOR_DUPLICATE_SOURCE_MATERIAL_ID_RED")
            quit(10)
            return
        type_by_actor[iid] = int(entry["meshIndex"])
        material_slots += paths.size()
        for p: Variant in paths:
            material_unique[str(p)]=true
    if (type_by_actor.size()!=10793 or material_slots!=16595 or
        material_unique.size()!=574):
        push_error("XZOGOT_NACHT_EXTERIOR_SOURCE_FULL_MATERIAL_CENSUS_RED")
        quit(11)
        return

    var building_raw: Array = policy["buildingCameraTargetXZ"]
    if building_raw.size()!=2:
        push_error("XZOGOT_NACHT_EXTERIOR_PROTECTED_BUILDING_ANCHOR_MISSING_RED")
        quit(12)
        return
    var anchor: Vector2=Vector2(float(building_raw[0]),float(building_raw[1]))
    var protect_radius_m: float=float(policy["largeGameplayRegionProtectionRadiusM"])
    if protect_radius_m<55.0:
        push_error("XZOGOT_NACHT_EXTERIOR_BUILDING_SAFETY_RADIUS_TOO_SMALL_RED")
        quit(13)
        return

    var source_actor_transforms: Dictionary={}
    var source_actor_meshes: Dictionary={}
    var protected_actor_ids: Dictionary={}
    var type_with_actual_lods: Dictionary={}
    var original_indexed_triangles: int=0
    for iid_var: Variant in by_actor:
        var iid: String=str(iid_var)
        var mi: MeshInstance3D=by_actor[iid] as MeshInstance3D
        source_actor_transforms[iid]=mi.global_transform
        source_actor_meshes[iid]=mi.mesh
        if mi.global_transform.basis.determinant()==0.0:
            push_error("XZOGOT_NACHT_EXTERIOR_DEGENERATE_SOURCE_AFFINE_RED "+iid)
            quit(14)
            return
        var local_box: AABB=mi.mesh.get_aabb()
        var bounds: AABB=mi.global_transform * local_box
        if _distance_to_aabb_xz(anchor,bounds)<=protect_radius_m:
            protected_actor_ids[iid]=true

    var treated_by_class: Dictionary={}
    var touched: Dictionary={}
    var unchanged_close: int=0
    var excluded_by_actual_world_bounds: int=0
    var excluded_oversized: int=0
    var source_surface_visibility_cut: int=0
    var true_mesh_lod_actors: int=0
    var source_shadow_disabled: int=0
    var errors: Array[String]=[]
    for entry_any: Variant in policy["actors"]:
        var entry: Dictionary=entry_any as Dictionary
        var iid: String=str(entry["actorId"])
        if touched.has(iid):
            errors.append("duplicate policy actor "+iid)
            break
        if not by_actor.has(iid) or not type_by_actor.has(iid):
            errors.append("unrecognized source actor "+iid)
            break
        if int(entry["nativeSourceMeshIndex"])!=int(type_by_actor[iid]):
            errors.append("source mesh type changed "+iid)
            break
        var category: String=str(entry["authoredAssetClass"])
        if not category in ["small_foliage","tree_silhouette","small_decorative_ground"]:
            errors.append("policy attempted to optimize unknown source actor type "+iid)
            break
        var mi: MeshInstance3D=by_actor[iid] as MeshInstance3D
        var full_world_aabb: AABB=mi.global_transform * mi.mesh.get_aabb()
        # Corner-based protection (rather than only actor origin) ensures
        # a large tree rooted off-site but whose branches extend into the
        # playable 55m sanctuary is fully retained.
        var closest_m: float=_distance_to_aabb_xz(anchor,full_world_aabb)
        if closest_m<=protect_radius_m:
            excluded_by_actual_world_bounds+=1
            continue
        var size: Vector3=full_world_aabb.size.abs()
        if size.x>55.0 or size.y>55.0 or size.z>55.0:
            excluded_oversized+=1
            continue
        # Godot 4.6 ArrayMesh has no surface_get_lods() callable API.
        # Source GLB imported LODs remain unproven; do not report fake ones.
        var true_lods: bool=false
        true_mesh_lod_actors = -1
        var bias: float=float(entry.get("lodBiasTarget",1.0))
        if bias<=0.0 or bias>1.0:
            errors.append("unreasonable exterior LOD bias "+iid)
            break
        mi.lod_bias=bias
        if not is_equal_approx(mi.lod_bias,bias):
            errors.append("Godot did not apply exterior LOD bias "+iid)
            break
        if true_lods:
            true_mesh_lod_actors+=1
        var cap: float=float(entry.get("maxCameraVisibilityM",0))
        if category=="tree_silhouette" and cap!=0.0:
            errors.append("policy attempted to delete distant original tree silhouettes "+iid)
            break
        if cap>0:
            # Only small items, NEVER large trees. A global per-camera
            # visibility cap acts only when the camera is genuinely far.
            if (category=="small_foliage" and maxf(size.x,size.z)>8.0) or (
                category=="small_decorative_ground" and maxf(size.x,size.z)>12.0):
                excluded_oversized+=1
                mi.lod_bias=1.0
                continue
            mi.visibility_range_end=cap
            mi.visibility_range_end_margin=12.0
            mi.visibility_range_fade_mode=GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
            if not is_equal_approx(mi.visibility_range_end,cap):
                errors.append("Godot failed to set distance visibility "+iid)
                break
            source_surface_visibility_cut+=mi.mesh.get_surface_count()
        if bool(entry.get("canDisableLongRangeShadow",false)):
            mi.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
            if mi.cast_shadow!=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
                errors.append("far shadow control not applied "+iid)
                break
            source_shadow_disabled+=1
        touched[iid]=true
        treated_by_class[category]=int(treated_by_class.get(category,0))+1

    for iid_var: Variant in by_actor:
        var iid: String=str(iid_var)
        var mi: MeshInstance3D=by_actor[iid] as MeshInstance3D
        if mi.mesh!=source_actor_meshes[iid] or mi.global_transform!=source_actor_transforms[iid]:
            errors.append("original source geometry/transforms modified "+iid)
            break
        if protected_actor_ids.has(iid):
            unchanged_close+=1
            if touched.has(iid) or mi.lod_bias!=1.0 or mi.visibility_range_end!=0.0:
                errors.append("PLAYABLE BUILDING PROTECTION VIOLATED "+iid)
                break
    var source_count: int=by_actor.size()
    var treated_count: int=touched.size()
    if treated_count<30:
        errors.append("too few independently verified real-world far outdoor assets")
    var evidence: Dictionary={
        "source":"Pavlov UE4.21 real GLB, NOT BO3 T7",
        "engine":Engine.get_version_info().get("string",""),
        "originalSourceActorCount":source_count,
        "originalSourceMaterialSurfaces":material_slots,
        "originalSourceEffectiveMaterials":material_unique.size(),
        "untouchedOriginalMeshResourceActors":source_count,
        "untouchedOriginalSourceWorldTransforms":source_count,
        "protectedNearBuildingSourceActorsUnchanged":unchanged_close,
        "policyEligibleSourceActors":int(policy["eligibleOriginalVisualActors"]),
        "actualGodotExteriorActorsWithVisualOnlyOptimization":treated_count,
        "actualGodotExteriorClassCounts":treated_by_class,
        "actualSourceActorsWithImportedLODVariants":true_mesh_lod_actors,
        "nativeLODIntrospectionNotAvailableViaArrayMesh":true,
        "actualGeometryTriangleLODReductionNotYetProven":true,
        "sourceActorsShadowOptimized":source_shadow_disabled,
        "sourceSmallDecorationMeshSurfacesWithFarCameraCull":source_surface_visibility_cut,
        "policyCandidatesExcludedByOriginalWorldMeshBounds":excluded_by_actual_world_bounds,
        "policyCandidatesExcludedByLargeWorldExtents":excluded_oversized,
        "allBigTreesSilhouettesPreserved":true,
        "nearPlayableBuildingAssetVisualsIntact":errors.is_empty(),
        "originalTrianglesRemoved":0,
        "collisionAndNavigationUnchanged":true,
        "realGPUFrameTimesAndAndroidFPSNotYetMeasured":true,
        "interactiveOutdoorReachabilityBeyondProtectedRingNotProven":true,
        "errorsFirst25":errors.slice(0,25)
    }
    var file: FileAccess=FileAccess.open("res://nacht-exterior-real-godot-lod-audit.json",FileAccess.WRITE)
    file.store_string(JSON.stringify(evidence,"\t"))
    file.close()
    world.queue_free()
    if not errors.is_empty():
        push_error("XZOGOT_NACHT_EXTERIOR_GODOT_WORLD_BOUNDS_LOD_SAFETY_RED "+JSON.stringify(evidence))
        quit(15)
        return
    print("XZOGOT_NACHT_REAL_GODOT_10793_EXTERIOR_VISUAL_LOD_SAFE_GREEN",
          " source_actors=",source_count,
          " untouched_building_objects=",unchanged_close,
          " actually_modified_far_decorations=",treated_count,
          " native_GLTF_LODs=",true_mesh_lod_actors,
          " small_surface_distance_cut_candidates=",source_surface_visibility_cut,
          " distant_actors_no_shadows=",source_shadow_disabled)
    quit(0)

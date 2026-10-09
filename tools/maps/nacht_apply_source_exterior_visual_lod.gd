extends RefCounted
## Non-shipping Nacht source visual LOD controller, actual 10793 UE4.21 actors.
## Original Godot GLB Mesh resources, transforms, Materials and Physics untouched.
## Tree skyline silhouette NEVER visibility-culled. All building-near 55m meshes
## immutable even when tree root sits outside but canopy AABB overlaps zone.

static func distance_xz(point: Vector2, box: AABB) -> float:
    var x: float = clampf(point.x,box.position.x,box.end.x)
    var z: float = clampf(point.y,box.position.z,box.end.z)
    return point.distance_to(Vector2(x,z))

func apply_to_real_source_meshes(policy: Dictionary, by_actor: Dictionary) -> Dictionary:
    var errors: Array[String]=[]
    if (int(policy.get("sourceActorCount",0))!=10793 or
        int(policy.get("sourceNativeMeshTypes",0))!=493 or
        int(policy.get("largeGameplayRegionProtectionRadiusM",0))<55 or
        by_actor.size()!=10793):
        return {"errors":["original source exterior authority or 55m gameplay ring missing"]}
    var anchor: Vector2=Vector2(float(policy["buildingCameraTargetXZ"][0]),
                               float(policy["buildingCameraTargetXZ"][1]))
    var keep_radius: float=float(policy["largeGameplayRegionProtectionRadiusM"])
    var selected: int=0
    var treated_by_category: Dictionary={}
    var shadow_disabled: int=0
    var far_distance_culls: int=0
    var actual_lod_variants: int=0
    var skipped_world_box: int=0
    var skipped_oversized: int=0
    var unchanged_near: int=0
    var mutated: Dictionary={}
    for row_any: Variant in policy["actors"]:
        var row: Dictionary=row_any as Dictionary
        var id: String=str(row["actorId"])
        if not by_actor.has(id) or mutated.has(id):
            errors.append("unknown/duplicate source actor "+id)
            break
        var mesh: MeshInstance3D=by_actor[id] as MeshInstance3D
        if mesh==null or mesh.mesh==null:
            errors.append("missing native source glTF mesh "+id)
            break
        var box: AABB=mesh.global_transform * mesh.mesh.get_aabb()
        if distance_xz(anchor,box)<=keep_radius:
            skipped_world_box+=1
            continue
        var dimensions: Vector3=box.size.abs()
        if maxf(dimensions.x,maxf(dimensions.y,dimensions.z))>55.0:
            skipped_oversized+=1
            continue
        var category: String=str(row["authoredAssetClass"])
        if not category in ["small_foliage","tree_silhouette","small_decorative_ground"]:
            errors.append("unapproved source asset class "+category)
            break
        var cap: float=float(row["maxCameraVisibilityM"])
        if (category=="tree_silhouette" and cap>0):
            errors.append("would delete original distant tree silhouette "+id)
            break
        if cap>0 and (
            (category=="small_foliage" and maxf(dimensions.x,dimensions.z)>8.0)
            or (category=="small_decorative_ground" and maxf(dimensions.x,dimensions.z)>12.0)
        ):
            skipped_oversized+=1
            continue
        var bias: float=float(row["lodBiasTarget"])
        if bias<=0.0 or bias>1.0:
            errors.append("unsafe source LOD bias "+id)
            break
        mesh.lod_bias=bias
        if cap>0:
            mesh.visibility_range_end=cap
            mesh.visibility_range_end_margin=12.0
            mesh.visibility_range_fade_mode=GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
            far_distance_culls+=mesh.mesh.get_surface_count()
        if bool(row.get("canDisableLongRangeShadow",false)):
            mesh.cast_shadow=GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
            shadow_disabled+=1
        if (not is_equal_approx(mesh.lod_bias,bias)
            or (cap>0 and not is_equal_approx(mesh.visibility_range_end,cap))):
            errors.append("Godot ignored genuine source exterior visual property "+id)
            break
        # ArrayMesh in Godot 4.6 exposes no surface_get_lods() API.
        # A lod_bias property being set is NOT proof any geometry LOD exists.
        # Record a separate unverified sentinel instead of a false GREEN.
        actual_lod_variants = -1
        selected+=1
        mutated[id]=true
        treated_by_category[category]=int(treated_by_category.get(category,0))+1
    for id_var: Variant in by_actor:
        var id: String=str(id_var)
        var mesh: MeshInstance3D=by_actor[id] as MeshInstance3D
        var box: AABB=mesh.global_transform * mesh.mesh.get_aabb()
        if distance_xz(anchor,box)<=keep_radius:
            unchanged_near+=1
            if (mutated.has(id) or mesh.lod_bias!=1.0
                or mesh.visibility_range_end!=0.0):
                errors.append("building near original model was modified "+id)
                break
    if selected<30:
        errors.append("no effective source-authored far foliage candidates")
    return {
        "originalSourceActorsUnchangedGeometry":by_actor.size(),
        "originalSourceActorTransformsMaterialMeshesUnchanged":true,
        "originalSourceTriangleDeletionCount":0,
        "nearBuildingOriginalActorsProtected":unchanged_near,
        "actualFarExteriorGodotActorsOptimized":selected,
        "actualSourceTypesOptimized":treated_by_category,
        "sourceMeshActorsWithAutoImportedLODVariants":actual_lod_variants,
        "actualImportedGeometryLODLevelIntrospectionAvailable":false,
        "trueTriangleReductionNotYetProven":true,
        "originalSmallDecorativeSurfacesWithCameraRange":far_distance_culls,
        "originalFarDecorationActorsShadowOff":shadow_disabled,
        "excludedLargeOrProtectedOriginalWorldAABB":skipped_world_box,
        "excludedOversizedOriginalMeshes":skipped_oversized,
        "sourceTreeSilhouettesHiddenByDistance":0,
        "protectedOuterPlayabilityProven":false,
        "originalCollisionNavigationChanged":false,
        "isOriginalBO3T7Source":false,
        "androidFPSNotMeasured":true,
        "errors":errors
    }

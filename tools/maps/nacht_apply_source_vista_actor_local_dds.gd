extends RefCounted
## Actor-local ORIGINAL-UE4-source DDS image variants on actual Godot meshes.
## Research lookdev only; not evidence of reduced Android VRAM if full-res
## DDS still needed by foreground actors. Source mesh/collision not changed.
func _distance_to_aabb_xz(anchor: Vector2, box: AABB) -> float:
    var x: float=clampf(anchor.x,box.position.x,box.end.x)
    var z: float=clampf(anchor.y,box.position.z,box.end.z)
    return anchor.distance_to(Vector2(x,z))

func apply_authored_source_vistas(overview: Dictionary, by_actor: Dictionary) -> Dictionary:
    var errors: Array[String]=[]
    if int(overview.get("sourceModels",0))!=493 or int(overview.get("originalSourceActors",0))!=10793 or by_actor.size()!=10793:
        return {"errors":["source GLB 10793 actor vista authority invalid"]}
    var records: Array=overview["actorDetails"]
    if records.size()!=340:
        return {"errors":["expected exact authored 340 Vista source identities"]}
    var source_tex_cache: Dictionary={}
    var material_cache: Dictionary={}
    var source_material_checks: Array[Array]=[]
    var modified_ids: Dictionary={}
    var source_native_actor_unchanged: int=0
    var lowres_surfaces: int=0
    var skipped_due_near_aabb: int=0
    var skipped_no_highres: int=0
    var alpha_modes_preserved: int=0
    var native_vista_ids: Dictionary={}
    var resolution_counts: Dictionary={}
    var building: Vector2=Vector2(-2.494789,-7.258049)

    for datum_any: Variant in records:
        var datum: Dictionary=datum_any as Dictionary
        var iid: String=str(datum["originalActorID"])
        if native_vista_ids.has(iid) or not by_actor.has(iid):
            errors.append("actor duplicated or missing "+iid)
            break
        native_vista_ids[iid]=true
        if str(datum.get("sourceClassification",""))!="tree_silhouette":
            errors.append("not an authored-original vista silhouette: "+iid)
            break
        var mi: MeshInstance3D=by_actor[iid] as MeshInstance3D
        if mi.mesh==null:
            errors.append("source authored glTF model lost "+iid)
            break
        var old_mesh: Mesh=mi.mesh
        var old_transform: Transform3D=mi.global_transform
        var true_bounds: AABB=mi.global_transform*mi.mesh.get_aabb()
        var distance: float=_distance_to_aabb_xz(building,true_bounds)
        # Actor root alone being distant is not sufficient. The tree's
        # original full rendered geometry (including canopy) must lie away.
        if distance<=55.0:
            skipped_due_near_aabb+=1
            continue
        var target_edge: int=256 if distance>90.0 else 512
        for surface: int in range(mi.mesh.get_surface_count()):
            var source_mat: StandardMaterial3D=mi.get_surface_override_material(surface) as StandardMaterial3D
            if source_mat==null or source_mat.albedo_texture==null:
                continue
            var full_tex: Texture2D=source_mat.albedo_texture
            var full_image: Image=full_tex.get_image()
            if full_image==null or full_image.is_empty():
                errors.append("unable to obtain actual imported authored DDS image for "+iid)
                break
            var original_size: Vector2i=full_image.get_size()
            if maxi(original_size.x,original_size.y)<=target_edge:
                skipped_no_highres+=1
                continue
            var cache_key: String=str(full_tex.get_instance_id())+"@"+str(target_edge)
            var smaller_tex: Texture2D=source_tex_cache.get(cache_key,null) as Texture2D
            if smaller_tex==null:
                var pixels: Image=full_image.duplicate()
                if pixels.is_compressed():
                    var ok: Error=pixels.decompress()
                    if ok!=OK:
                        errors.append("DDS source decode RED actor="+iid)
                        break
                var scale: float=minf(1.0,float(target_edge)/float(maxi(original_size.x,original_size.y)))
                var w: int=maxi(1,roundi(original_size.x*scale))
                var h: int=maxi(1,roundi(original_size.y*scale))
                pixels.resize(w,h,Image.INTERPOLATE_LANCZOS)
                if pixels.has_mipmaps():
                    pixels.clear_mipmaps()
                pixels.generate_mipmaps()
                smaller_tex=ImageTexture.create_from_image(pixels)
                if smaller_tex==null or maxi(smaller_tex.get_width(),smaller_tex.get_height())>target_edge:
                    errors.append("real source-derived smaller ImageTexture creation failed "+iid)
                    break
                source_tex_cache[cache_key]=smaller_tex
            var key: String=str(source_mat.get_instance_id())+"@"+str(target_edge)
            var smaller_material: StandardMaterial3D=material_cache.get(key,null) as StandardMaterial3D
            if smaller_material==null:
                smaller_material=source_mat.duplicate(true) as StandardMaterial3D
                if smaller_material==null:
                    errors.append("cannot clone original authored Vista material "+iid)
                    break
                smaller_material.albedo_texture=smaller_tex
                material_cache[key]=smaller_material
            source_material_checks.append([source_mat,full_tex,original_size])
            mi.set_surface_override_material(surface,smaller_material)
            if (mi.get_surface_override_material(surface)!=smaller_material or
                source_mat.albedo_texture != full_tex or
                smaller_material.transparency!=source_mat.transparency):
                errors.append("native original near shared texture or tree alpha was overwritten "+iid)
                break
            alpha_modes_preserved+=1
            lowres_surfaces+=1
            modified_ids[iid]=true
            resolution_counts[target_edge]=int(resolution_counts.get(target_edge,0))+1
        if not errors.is_empty():
            break
        if mi.mesh!=old_mesh or mi.global_transform!=old_transform:
            errors.append("ORIGINAL native actor geometry/basis was mutated "+iid)
            break
        source_native_actor_unchanged+=1

    for src_item_any: Variant in source_material_checks:
        var src_item: Array=src_item_any as Array
        var mat: StandardMaterial3D=src_item[0] as StandardMaterial3D
        var tex: Texture2D=src_item[1] as Texture2D
        if mat.albedo_texture!=tex or tex.get_size()!=Vector2(src_item[2]):
            errors.append("shared source near DDS resolution mutated")
            break
    if modified_ids.size()<100 or lowres_surfaces<100 or source_native_actor_unchanged<200:
        errors.append("insufficient original Vista source texture-only actor safety coverage")
    return {
        "originalSourceGLBActorsUnchanged":by_actor.size(),
        "authorTagDistantTreeCandidateCount":records.size(),
        "sourceAuthoredVistaActorsWithSourceDerivedLowRes":modified_ids.size(),
        "sourceAuthoredNativeSurfaceAlbedoVariants":lowres_surfaces,
        "uniqueRealGodotLowerResolutionImageTextures":source_tex_cache.size(),
        "sourceAlbedoVariantTargetMaxEdgePx":resolution_counts,
        "authoredOriginalSourceMaterialsWithUnchangedTextureAndResolution":source_material_checks.size(),
        "sourceTreeTransparencyModesKept":alpha_modes_preserved,
        "originalSourceMeshAndActorAffinePreservedCount":source_native_actor_unchanged,
        "originalSourceCanopyAABBProtectsNearBuilding":skipped_due_near_aabb,
        "originalSmallTextureAlreadyBelowTarget":skipped_no_highres,
        "originalCollisionAndNavigationModified":false,
        "sourceOriginalSharedTextureResourceModified":false,
        "sourceOriginalNearMaterialQualityModified":false,
        "originalNativeSourceMeshesDecimated":false,
        "newGPUTextureMemoryMayBeADDITIONAL":true,
        "originalBO3T7Claim":false,
        "proofThatFarObjectsNeverVisible":false,
        "actualGPUPerformanceImprovementMeasured":false,
        "errors":errors
    }

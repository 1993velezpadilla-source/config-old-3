extends SceneTree
## RESEARCH-only source-registered Pavlov Nacht background vista DDS LOD test.
## Only real source-author-tagged 'vista' trees outside protected building AABBs.
## Per-actor MeshInstance surface MATERIAL OVERRIDES: NEVER global downscale
## textures/materials also used by the original close-up gameplay scene.
## Does not prove player never sees object or actual Android FPS.

func _initialize() -> void:
    call_deferred("_probe")

func _distance_to_building(aabb: AABB, building: Vector2) -> float:
    var x: float = clampf(building.x,aabb.position.x,aabb.end.x)
    var z: float = clampf(building.y,aabb.position.z,aabb.end.z)
    return building.distance_to(Vector2(x,z))

func _probe() -> void:
    var source_any: Variant = JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-actor-material-authority.json"))
    var vistas_any: Variant = JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-distant-authored-vista-policy.json"))
    if not (source_any is Dictionary) or not (vistas_any is Dictionary):
        push_error("XZOGOT_NACHT_VISTA_EXACT_SOURCE_BINDING_AUTHORITY_MISSING_RED")
        quit(2)
        return
    var bridge: Dictionary = source_any as Dictionary
    var policy: Dictionary = vistas_any as Dictionary
    if (int(bridge.get("sourceActorCount",0)) != 10793 or
        int(bridge.get("originalSourceSurfaceBindings",0)) != 16595 or
        int(bridge.get("distinctSourceEffectiveMaterials",0)) != 574 or
        int(policy.get("originalSourceActors",0)) != 10793 or
        int(policy.get("sourceModels",0)) != 493 or
        bool(policy.get("proofNeverVisibleOrReachable",true))):
        push_error("XZOGOT_NACHT_VISTA_ORIGINAL_PROVENANCE_OR_REACHABILITY_CLAIM_RED")
        quit(3)
        return

    var packed: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if packed == null:
        push_error("XZOGOT_NACHT_VISTA_REAL_GODOT_GLTF_SCENE_MISSING_RED")
        quit(4)
        return
    var world: Node = packed.instantiate()
    root.add_child(world)
    var raw_meshes: Array[Node] = world.find_children("*","MeshInstance3D",true,false)
    if raw_meshes.size() != 10793:
        push_error("XZOGOT_NACHT_VISTA_ALL_ORIGINAL_GLTF_ACTORS_MISSING_RED")
        quit(5)
        return

    var by_actor: Dictionary = {}
    for node: Node in raw_meshes:
        var mi: MeshInstance3D = node as MeshInstance3D
        var text_name: String = str(mi.name)
        var marker: int = text_name.find("_native_exact_")
        if marker < 0:
            push_error("XZOGOT_NACHT_VISTA_GLTF_LOSSLESS_SOURCE_ID_RED")
            quit(6)
            return
        var id: String = text_name.substr(0,marker)
        if by_actor.has(id):
            push_error("XZOGOT_NACHT_VISTA_DUPLICATE_SOURCE_ID_RED")
            quit(7)
            return
        by_actor[id] = mi
    var original_by_actor: Dictionary = {}
    var total_surfaces: int = 0
    for item_any: Variant in bridge["actors"]:
        var item: Dictionary = item_any as Dictionary
        var actor_id: String = str(item["actorId"])
        if not by_actor.has(actor_id) or original_by_actor.has(actor_id):
            push_error("XZOGOT_NACHT_VISTA_ACTOR_MATERIAL_ID_MISMATCH_RED")
            quit(8)
            return
        var mesh: MeshInstance3D = by_actor[actor_id] as MeshInstance3D
        var slot_paths: Array = item["sourceMaterialPaths"]
        if mesh.mesh == null or mesh.mesh.get_surface_count() != slot_paths.size():
            push_error("XZOGOT_NACHT_VISTA_GLTF_SURFACE_OR_SOURCE_MATERIAL_LOST_RED "+actor_id)
            quit(9)
            return
        original_by_actor[actor_id] = item
        total_surfaces += slot_paths.size()
    if original_by_actor.size()!=10793 or total_surfaces!=16595:
        push_error("XZOGOT_NACHT_VISTA_EXACT_AUTHORED_STATIC_SURFACE_CENSUS_RED")
        quit(10)
        return

    var script: Script = load("res://scripts/xziel_benchmark_loader.gd") as Script
    if script == null:
        push_error("XZOGOT_NACHT_VISTA_EXISTING_SOURCE_DDS_BINDER_MISSING_RED")
        quit(11)
        return
    var binder: Node3D = script.new() as Node3D
    binder.set("load_on_ready",false)
    binder.set("build_materials",true)
    binder.set("build_lights",false)
    binder.set("build_skeletal_actors",false)
    binder.set("source_root","res://nacht-authority")
    binder.set("vfs_map_root","vfs/xziel/maps/xziel_nacht_chronicles")
    root.add_child(binder)
    binder.call("_prepare_material_authority")

    var near_material_originals: Dictionary = {}
    var near_shared_source_paths: Dictionary = {}
    var vista_ids: Dictionary = {}
    for record_any: Variant in policy["actorDetails"]:
        var record: Dictionary = record_any as Dictionary
        var id: String = str(record["originalActorID"])
        if vista_ids.has(id):
            push_error("XZOGOT_NACHT_VISTA_DUPLICATE_CANDIDATE_RED "+id)
            quit(12)
            return
        vista_ids[id] = true
    if vista_ids.size() != int(policy["sourceVistaDistantActorsOutside55mCANDIDATES"]):
        push_error("XZOGOT_NACHT_VISTA_POLICY_ACTOR_COUNT_CHANGED_RED")
        quit(13)
        return

    # Reuse exactly the authored source material; never substitute matching
    # by texture basename or geometry color.
    var original_albedo_by_id: Dictionary = {}
    var downgraded_tex_by_id_and_size: Dictionary = {}
    var downgraded_material_by_id_and_size: Dictionary = {}
    var actor_count: int = 0
    var source_vista_rows: int = 0
    var guarded_aabb: int = 0
    var source_surfaces_replaced: int = 0
    var source_fullsize_textures: int = 0
    var source_generated_lowerres_textures: int = 0
    var source_declared_alpha_modes_kept: int = 0
    var rejected_small_or_unsupported: int = 0
    var all_original_mesh_resources: Dictionary = {}
    var exact_original_transforms: Dictionary = {}
    var examples: Array[Dictionary] = []
    var errors: Array[String] = []

    var anchor: Vector2 = Vector2(-2.494789,-7.258049)
    var resolutions: Dictionary = {}
    for record_any: Variant in policy["actorDetails"]:
        var record: Dictionary = record_any as Dictionary
        var id: String = str(record["originalActorID"])
        if not by_actor.has(id) or not original_by_actor.has(id):
            errors.append("vista actor absent in original GLB "+id)
            break
        var mi: MeshInstance3D = by_actor[id] as MeshInstance3D
        var actual_bounds: AABB = mi.global_transform * mi.mesh.get_aabb()
        var distance: float = _distance_to_building(actual_bounds,anchor)
        if distance <= 55.0:
            guarded_aabb += 1
            continue
        if maxf(actual_bounds.size.x,maxf(actual_bounds.size.y,actual_bounds.size.z))>55.0:
            guarded_aabb += 1
            continue
        if str(record["sourceClassification"]) != "tree_silhouette":
            errors.append("unknown original source vista LOD category "+id)
            break
        original_albedo_by_id[id] = []
        all_original_mesh_resources[id] = mi.mesh
        exact_original_transforms[id] = mi.global_transform
        var row: Dictionary = original_by_actor[id] as Dictionary
        binder.call("_apply_instance_materials",mi,id,int(row["meshIndex"]),0)
        var desired_edge: int = 256 if distance > 90.0 else 512
        var replaced_on_actor: int = 0
        for slot: int in range(mi.mesh.get_surface_count()):
            var material: StandardMaterial3D = mi.get_surface_override_material(slot) as StandardMaterial3D
            if material == null or material.albedo_texture == null:
                continue
            var texture: Texture2D = material.albedo_texture
            var original_texture_id: int = texture.get_instance_id()
            var original_image: Image = texture.get_image()
            if original_image == null or original_image.is_empty():
                errors.append(id+" original DDS get_image failed")
                break
            var before_size: Vector2i = original_image.get_size()
            source_fullsize_textures+=1
            original_albedo_by_id[id].append([slot,texture,before_size,material])
            if maxi(before_size.x,before_size.y) <= desired_edge:
                rejected_small_or_unsupported+=1
                continue
            var key: String = str(original_texture_id)+"@"+str(desired_edge)
            var downgraded: Texture2D = downgraded_tex_by_id_and_size.get(key,null) as Texture2D
            if downgraded == null:
                var pixels: Image=original_image.duplicate()
                if pixels.is_compressed():
                    var dec_error: Error = pixels.decompress()
                    if dec_error != OK:
                        errors.append(id+" authored compressed DDS cannot decompress for runtime research")
                        break
                var factor: float = minf(1.0,float(desired_edge)/float(maxi(before_size.x,before_size.y)))
                var w: int = maxi(1,int(round(float(before_size.x)*factor)))
                var h: int = maxi(1,int(round(float(before_size.y)*factor)))
                pixels.resize(w,h,Image.INTERPOLATE_LANCZOS)
                if pixels.has_mipmaps():
                    pixels.clear_mipmaps()
                pixels.generate_mipmaps()
                downgraded = ImageTexture.create_from_image(pixels)
                if downgraded == null or max(downgraded.get_width(),downgraded.get_height())>desired_edge:
                    errors.append(id+" true low-resolution original DDS image texture generation failed")
                    break
                downgraded_tex_by_id_and_size[key] = downgraded
                source_generated_lowerres_textures+=1
            var material_key: String = str(material.get_instance_id())+"@"+str(desired_edge)
            var far_mat: StandardMaterial3D = downgraded_material_by_id_and_size.get(material_key,null) as StandardMaterial3D
            if far_mat == null:
                far_mat = material.duplicate(true) as StandardMaterial3D
                if far_mat == null:
                    errors.append(id+" source-authored material duplication failed")
                    break
                far_mat.albedo_texture = downgraded
                downgraded_material_by_id_and_size[material_key] = far_mat
            # Crucial actor-LOCAL surface override, NOT edit native shared
            # material or original cached Texture2D resource, so a nearby
            # instance of the same 4 native vista models remains FULL RES.
            mi.set_surface_override_material(slot,far_mat)
            if (material.albedo_texture != texture or
                mi.get_surface_override_material(slot) == material or
                (far_mat as BaseMaterial3D).transparency != (material as BaseMaterial3D).transparency):
                errors.append(id+" original shared DDS or foliage alpha mode changed")
                break
            source_declared_alpha_modes_kept+=1
            source_surfaces_replaced+=1
            replaced_on_actor+=1
        if not errors.is_empty():break
        if mi.mesh != all_original_mesh_resources[id] or mi.global_transform != exact_original_transforms[id]:
            errors.append(id+" original source GLB mesh or affine transform changed")
            break
        if replaced_on_actor>0:
            actor_count+=1
            resolutions[desired_edge] = int(resolutions.get(desired_edge,0))+1
            if examples.size()<10:
                examples.append({"originalSourceActor":id,"originalNativeMeshIndex":row["meshIndex"],
                                 "distanceFromActualNativeWorldMeshBounds":distance,
                                 "maxFarAlbedoImageEdgePixels":desired_edge,
                                 "originalMaterialSurfacesLowResolution":replaced_on_actor})
    for id_var: Variant in original_albedo_by_id:
        var id: String = str(id_var)
        var mi: MeshInstance3D = by_actor[id] as MeshInstance3D
        for entry_any: Variant in original_albedo_by_id[id]:
            var entry: Array = entry_any as Array
            var src_mat: StandardMaterial3D = entry[3] as StandardMaterial3D
            var src_tex: Texture2D = entry[1] as Texture2D
            if src_mat.albedo_texture != src_tex or src_tex.get_size()!=Vector2(entry[2]):
                errors.append(id+" original near-shared DDS content or dimensions mutated")
                break
        if not errors.is_empty():break

    var result: Dictionary={
        "source":"archived Pavlov UE4.21 native source materials, not BO3 T7",
        "godot":Engine.get_version_info().get("string",""),
        "originalSourceGLTFActorsPreserved":raw_meshes.size(),
        "originalSourceMaterialSurfaceCensusPreserved":total_surfaces,
        "sourceVistaTaggedDistantCandidates":vista_ids.size(),
        "sourceVistaActorBoundsExcludedForNearRegion":guarded_aabb,
        "originalSourceVistaActorsActuallyUsingLowResPerActorDDS":actor_count,
        "originalSourceMaterialSurfaceOverridesWithReducedAlbedo":source_surfaces_replaced,
        "authoredDDSSourceReadBeforeLowResPerActor":source_fullsize_textures,
        "newTrueLowResDDSImagesCreatedWithSourcePixelData":source_generated_lowerres_textures,
        "lowResolutionTargetMaxImageEdgePixels":resolutions,
        "sharedOriginalMaterialAndTextureResourcesModified":false,
        "treesOriginalAlphaTransparencyModesPreserved":source_declared_alpha_modes_kept,
        "originalNativeMeshGeometryTransformsOrCollisionChanged":false,
        "screenshotVisualPixelABNeeded":true,
        "confirmedNeverVisibleFromPlayableNavigation":false,
        "totalAndroidGpuMemoryGainProven":false,
        "knownMemoryTradeoff":"If original texture also used up close, runtime must hold original AND low-res source-derived image simultaneously.",
        "exampleOriginalActorResults":examples,
        "errors":errors.slice(0,15)
    }
    var out: FileAccess=FileAccess.open("res://nacht-vista-actual-source-dds-lowres-report.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(result,"\t"))
    out.close()
    binder.queue_free()
    world.queue_free()
    if not errors.is_empty() or actor_count<5 or source_surfaces_replaced<5:
        push_error("XZOGOT_NACHT_VISTA_PER_ACTOR_SOURCE_IMAGE_DOWNSCALE_RED "+JSON.stringify(result))
        quit(14)
        return
    print("XZOGOT_NACHT_REAL_GODOT_VISTA_PER_ACTOR_SOURCE_DDS_LOWER_RESOLUTION_GREEN",
          " original_vista_actor_candidates=",vista_ids.size(),
          " actual_actor_specific_downscaled=",actor_count,
          " original_source_material_surfaces_lowres=",source_surfaces_replaced,
          " derived_lowres_source_textures=",source_generated_lowerres_textures,
          " original_near_shared_DDS_unchanged=true")
    quit(0)

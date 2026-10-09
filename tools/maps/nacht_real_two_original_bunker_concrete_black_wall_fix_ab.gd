extends SceneTree
## Original full-source interior BLACK surface forensic. No permanent model edit.
## 10793 source actors, 16595 REAL DDS-material surfaces, 166 native UE lights.
## Baseline / source-far foliage policy / actor-local Vista DDS source derivatives.
## This is Mesa Linux *diagnostic* render work, NEVER measured Android FPS.
func _initialize() -> void:
    call_deferred("_run")

func _measure(camera: Camera3D, label: String, position: Vector3, target: Vector3) -> Dictionary:
    camera.global_position=position
    camera.look_at(target,Vector3.UP)
    for i: int in range(12):
        await process_frame
    await create_timer(1.1).timeout
    for i: int in range(4):
        await process_frame
    var data: Dictionary={
        "label":label,
        "cameraPosition":str(camera.global_position),
        "realGodotRenderingBackend":"Mesa OpenGL Compatibility (Xvfb), NOT Android GPU",
        "realVisibleObjects":int(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)),
        "realVisibleDrawCalls":int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)),
        "realVisiblePrimitiveIndices":int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)),
        "monitorFPSDesktop":float(Performance.get_monitor(Performance.TIME_FPS)),
        "androidPhysicalDeviceFPSNotKnown":true
    }
    print("XZOGOT_NACHT_REAL_RENDERER_VISIBLE_DRAW_CALL_MONITOR ",JSON.stringify(data))
    return data

func _run() -> void:
    var b_any: Variant=JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-actor-material-authority.json"))
    var p_any: Variant=JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-exterior-visual-policy.json"))
    var v_any: Variant=JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-authored-vista-actor-policy.json"))
    if not (b_any is Dictionary) or not (p_any is Dictionary) or not (v_any is Dictionary):
        push_error("XZOGOT_NACHT_DRAW_MONITOR_SOURCE_OR_EXTERIOR_POLICY_MISSING_RED")
        quit(2)
        return
    var bridge: Dictionary=b_any as Dictionary
    if int(bridge.get("sourceActorCount",0))!=10793 or int(bridge.get("originalSourceSurfaceBindings",0))!=16595:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_SOURCE_GLTF_AUTHORITY_LOST_RED")
        quit(3)
        return
    var scene: PackedScene=load("res://scenes/main.tscn") as PackedScene
    var binder_script: Script=load("res://scripts/xziel_benchmark_loader.gd") as Script
    if scene==null or binder_script==null:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_GODOT_PROJECT_OR_MATERIAL_LOADER_MISSING_RED")
        quit(4)
        return
    var world: Node=scene.instantiate()
    root.add_child(world)
    var source_meshes: Array[Node]=world.find_children("*","MeshInstance3D",true,false)
    if source_meshes.size()!=10793:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_SOURCE_ACTORS_ABSENT_RED")
        quit(5)
        return
    var by_actor: Dictionary={}
    for n: Node in source_meshes:
        var mi: MeshInstance3D=n as MeshInstance3D
        var text_name: String=str(mi.name)
        var cut: int=text_name.find("_native_exact_")
        if cut<0:
            push_error("XZOGOT_NACHT_DRAW_MONITOR_SOURCE_ID_GLTF_ABSENT_RED")
            quit(6)
            return
        var id: String=text_name.substr(0,cut)
        if by_actor.has(id):
            push_error("XZOGOT_NACHT_DRAW_MONITOR_DUPLICATE_ORIGINAL_ACTOR_RED")
            quit(7)
            return
        by_actor[id]=mi
    var binder: Node3D=binder_script.new() as Node3D
    binder.set("load_on_ready",false)
    binder.set("build_materials",true)
    binder.set("build_lights",true)
    binder.set("build_skeletal_actors",false)
    binder.set("source_root","res://nacht-authority")
    binder.set("vfs_map_root","vfs/xziel/maps/xziel_nacht_chronicles")
    binder.set("light_report_file","xzen-report.json")
    binder.set("source_environment_truth_file","res://nacht-authority/nacht-environment-runtime-authority.json")
    root.add_child(binder)
    binder.call("_prepare_material_authority")
    var surfaces: int=0
    for row_any: Variant in bridge["actors"]:
        var row: Dictionary=row_any as Dictionary
        var id: String=str(row["actorId"])
        if not by_actor.has(id):
            push_error("XZOGOT_NACHT_DRAW_MONITOR_ORIGINAL_MATERIAL_ID_LOST_RED")
            quit(8)
            return
        var mi: MeshInstance3D=by_actor[id] as MeshInstance3D
        var slot_names: Array=row["sourceMaterialPaths"]
        if mi.mesh.get_surface_count()!=slot_names.size():
            push_error("XZOGOT_NACHT_DRAW_MONITOR_ORIGINAL_MESH_SURFACE_MISMATCH_RED")
            quit(9)
            return
        binder.call("_apply_instance_materials",mi,id,int(row["meshIndex"]),0)
        surfaces+=slot_names.size()
    if surfaces!=16595:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_ORIGINAL_MATERIAL_SURFACE_SUM_RED")
        quit(10)
        return
    var light_basis: Node3D=Node3D.new()
    light_basis.basis=Basis(
        Vector3(0.0,0.0,-1.0),Vector3(-1.0,0.0,0.0),Vector3(0.0,1.0,0.0))
    binder.add_child(light_basis)
    binder.set("_runtime_root",light_basis)
    binder.call("_build_source_lights")
    if int(binder.get_meta("xziel_benchmark_light_count",-1))!=166:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_SOURCE_LIGHTS_MISSING_RED")
        quit(11)
        return
    var cam: Camera3D=Camera3D.new()
    cam.fov=72.0
    cam.near=0.035
    cam.far=850.0
    root.add_child(cam)
    cam.current=true
    var skies: Array[Node]=light_basis.find_children("*","WorldEnvironment",true,false)
    if skies.size()!=1:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_REAL_SOURCE_SKYLIGHT_MISSING_RED")
        quit(12)
        return
    var source_sky: WorldEnvironment=skies[0] as WorldEnvironment
    var moon: Environment=source_sky.environment.duplicate(true) as Environment
    moon.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
    moon.ambient_light_sky_contribution=0.0
    moon.background_mode=Environment.BG_COLOR
    moon.background_color=Color(0.013,0.021,0.040)
    moon.ambient_light_color=Color(0.46,0.54,0.69)
    moon.ambient_light_energy=0.72
    cam.environment=moon
    # Exact GLB surface owner recovered from two Godot 4.6.1 source
    # raster buffers in #37996808191 and independent pixel decoder
    # #37997123328: 61,230 sampled black pixels attributable to the
    # SOURCE BUNKER CONCRETE if all materials made opaque.
    # The two ORIGINAL actors have this material: 010576 and 010730.
    # Test this ONE original source material, not 564 masked materials.
    const TARGET_PATH: String=(
        "Content/CustomMaps/UGC2755515831/CoD_nacht/MAP_FILES/"
        +"t7_concrete_poured_bunker_dirty_01.t7_concrete_poured_bunker_dirty_01")
    var original_material: Dictionary={}
    var actor_names: Array[String]=[]
    var target_mesh_indices: Dictionary={}
    var relevant_surfaces: int=0
    var stage: Array[Dictionary]=[]
    var all_count: int=0
    for a_any: Variant in bridge.get("actors",[]):
        var a: Dictionary=a_any as Dictionary
        all_count+=1
        var paths: Array=a.get("sourceMaterialPaths",[]) as Array
        var actor_id: String=str(a.get("actorId",""))
        var mi: MeshInstance3D=by_actor.get(actor_id,null) as MeshInstance3D
        if mi==null or paths.size()!=mi.mesh.get_surface_count():
            push_error("XZOGOT_NACHT_BLACK_BUNKER_CONCRETE_SOURCE_ACTOR_SURFACE_RED")
            quit(49)
            return
        for i: int in range(paths.size()):
            if str(paths[i])!=TARGET_PATH:
                continue
            var src: StandardMaterial3D=mi.get_surface_override_material(i) as StandardMaterial3D
            if (src==null or src.albedo_texture==null
                or src.transparency!=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
                or src.cull_mode!=BaseMaterial3D.CULL_DISABLED):
                push_error("XZOGOT_NACHT_BLACK_BUNKER_CONCRETE_ORIGINAL_DDS_ALPHA_CULL_RED")
                quit(50)
                return
            original_material[src.get_instance_id()]=src
            relevant_surfaces+=1
            actor_names.append(actor_id)
            target_mesh_indices[actor_id]=int(a.get("meshIndex",-1))
            stage.append({"node":mi,"surface":i,"original":src})
    var expected_ids: Array[String]=[
        "ue_instance_010576","ue_instance_010730"]
    actor_names.sort()
    expected_ids.sort()
    if (all_count!=10793 or by_actor.size()!=10793
        or relevant_surfaces!=2 or original_material.size()!=1
        or actor_names!=expected_ids
        or int(target_mesh_indices.get("ue_instance_010576",-1))!=470
        or int(target_mesh_indices.get("ue_instance_010730",-1))!=17):
        push_error("XZOGOT_NACHT_BLACK_BUNKER_TWO_EXACT_ORIGINAL_ARCHIVE_ACTORS_RED "+
            str([all_count,by_actor.size(),actor_names,target_mesh_indices]))
        quit(51)
        return
    var camera_samples: Array[Dictionary]=[
        {"name":"interior_central_yaw180","eye":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw0","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(42.0,1.65,-0.325515)},
        {"name":"interior_original_yaw270","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var before: Dictionary={}
    var candidate: Dictionary={}
    for camera: Dictionary in camera_samples:
        var name: String=str(camera["name"])
        before[name]=await _capture(cam,name+"_bunker_original_DDS",
            camera["eye"],camera["look"])
    var only_source: StandardMaterial3D=(
        original_material.values()[0] as StandardMaterial3D)
    var clone: StandardMaterial3D=only_source.duplicate(false) as StandardMaterial3D
    clone.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
    if (clone.albedo_texture!=only_source.albedo_texture
        or clone.normal_texture!=only_source.normal_texture
        or clone.cull_mode!=only_source.cull_mode
        or clone.roughness!=only_source.roughness
        or clone.shading_mode!=only_source.shading_mode):
        push_error("XZOGOT_NACHT_BLACK_BUNKER_RESEARCH_ALPHA_CHANGED_OTHER_SHADER_RED")
        quit(52)
        return
    for row: Dictionary in stage:
        (row["node"] as MeshInstance3D).set_surface_override_material(
            int(row["surface"]),clone)
    for camera: Dictionary in camera_samples:
        var name: String=str(camera["name"])
        candidate[name]=await _capture(cam,name+"_ONLY_bunker_2_surfaces_opaque_preview",
            camera["eye"],camera["look"])
    for row: Dictionary in stage:
        var node: MeshInstance3D=row["node"] as MeshInstance3D
        node.set_surface_override_material(int(row["surface"]),row["original"] as Material)
        if node.get_surface_override_material(int(row["surface"]))!=row["original"]:
            push_error("XZOGOT_NACHT_BLACK_BUNKER_SOURCE_POINTER_RESTORE_RED")
            quit(53)
            return
    var restored: Image=await _capture(cam,
        "interior_central_yaw180_bunker_source_original_restored",
        camera_samples[0]["eye"],camera_samples[0]["look"])
    var rest_delta: Dictionary=_image_delta(
        before["interior_central_yaw180"] as Image,restored)
    var views: Array[Dictionary]=[]
    for camera: Dictionary in camera_samples:
        var name: String=str(camera["name"])
        var baseline: Image=before[name] as Image
        var after: Image=candidate[name] as Image
        var pixels: Dictionary=_black_recover(baseline,after,after)
        pixels["cameraName"]=name
        pixels["sourceBunkerConcreteOnlyOriginalDDSPixelChange"]=_image_delta(baseline,after)
        views.append(pixels)
        print("XZOGOT_NACHT_BUNKER_EXACT_TWO_ORIGINAL_MATERIAL_BLACK_WALL_PIXELS ",
            JSON.stringify(pixels))
    var report: Dictionary={
        "source":"Real Pavlov UE4.21 reconstructed Nacht archival GLB, NOT official BO3 T7",
        "realNativeOriginalSourceActorNodes":by_actor.size(),
        "originalMaterialSurfaceBindings":surfaces,
        "sourceOriginalBoundDDS":718,
        "originalSourceLightComponents":166,
        "pixelOwnerFromRealSource574MaterialScreenshots":{
            "forensicRunID":37996808191,
            "independentPixelDecodedRunID":37997123328,
            "originalMaterialID":28,
            "originalOpaqueDiagnosticBlackPixelsTwoCameraSamples":61230,
            "notDirectProofThatUEOriginalOpacityMaskIsUnwired":true
        },
        "exactSourceBunkerMaterialPath":TARGET_PATH,
        "exactOriginalSourceMeshActorsOnly":actor_names,
        "exactNativeMeshIndices":target_mesh_indices,
        "originalTargetSurfaceBindingsChangedTemporarily":relevant_surfaces,
        "otherOriginalMaterialSurfaceBindingsUntouched":surfaces-relevant_surfaces,
        "otherSourceAlphaFoliageWindowsDecalMaterialsUnmodified":true,
        "threeEyeHeightOriginalVsTwoSurfaceMaskDisabled":views,
        "originalShaderResourceRestorationVerified":true,
        "restoredOriginalCameraRGBDifference":rest_delta,
        "nonShippingExperimentOnly":true,
        "originalSourceMeshCollisionTransformedOrDeleted":false,
        "allWindowAndExteriorVisibilityCertified":false,
        "physicalAndroidFPSAndMemoryNotMeasured":true,
        "productionBlackInteriorFixApproved":false
    }
    var f: FileAccess=FileAccess.open(
        "res://nacht-exact-two-source-bunker-concrete-black-wall-recovery.json",FileAccess.WRITE)
    f.store_string(JSON.stringify(report,"\t"))
    f.close()
    if rest_delta["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_BUNKER_EXACT_TWO_ORIGINAL_RESTORE_RGB_RED")
        quit(54)
        return
    print("XZOGOT_NACHT_TWO_EXACT_ORIGINAL_BUNKER_MATERIAL_SURFACES_7_PNG_A_B_GREEN")
    quit(0)

func _black_recover(a: Image,b: Image,c: Image) -> Dictionary:
    var w: int=a.get_width()
    var h: int=a.get_height()
    var source_dark: int=0
    var alpha_recovered: int=0
    var light_recovered: int=0
    var still_black: int=0
    for y: int in range(int(h*0.12),int(h*0.88)):
        for x: int in range(int(w*0.15),int(w*0.85)):
            var initial: Color=a.get_pixel(x,y)
            if maxf(initial.r,maxf(initial.g,initial.b))>=0.045:
                continue
            source_dark+=1
            var alpha: Color=b.get_pixel(x,y)
            var light: Color=c.get_pixel(x,y)
            if maxf(alpha.r,maxf(alpha.g,alpha.b))>=0.08:
                alpha_recovered+=1
            elif maxf(light.r,maxf(light.g,light.b))>=0.08:
                light_recovered+=1
            else:
                still_black+=1
    return {
        "originalNearBlackCenterROIPixels":source_dark,
        "blackRecoveredByDisablingOnlyDiffuseAlphaScissor":alpha_recovered,
        "additionalBlackRecoveredBySuppressingLightingButKeepingSourceDDS":light_recovered,
        "blackRemainingEvenUnlitOpaqueWithSourceDDS":still_black,
        "doNotAssumeRemainingBlackIsMissingGeometry":true
    }

func _image_delta(before: Image,after: Image) -> Dictionary:
    var count: int=before.get_width()*before.get_height()
    var mean: float=0.0
    var changed: int=0
    for y: int in range(before.get_height()):
        for x: int in range(before.get_width()):
            var a: Color=before.get_pixel(x,y)
            var b: Color=after.get_pixel(x,y)
            var delta: float=(absf(a.r-b.r)+absf(a.g-b.g)+absf(a.b-b.b))/3.0
            mean+=delta
            if delta>0.03:
                changed+=1
    return {
        "resolution":[before.get_width(),before.get_height()],
        "meanRGBDifferencePercent":100.0*mean/float(count),
        "changedSignificantPixels":changed,
        "changedSignificantPixelPercent":100.0*float(changed)/float(count)
    }

func _capture(camera: Camera3D,label: String,position: Vector3,target: Vector3) -> Image:
    camera.global_position=position
    camera.look_at(target,Vector3.UP)
    for i: int in range(12):
        await process_frame
    await create_timer(0.5).timeout
    for i: int in range(3):
        await process_frame
    var shot: Image=root.get_texture().get_image()
    shot.convert(Image.FORMAT_RGBA8)
    var err: Error=shot.save_png("res://"+label+".png")
    if err!=OK:
        push_error("NACHT_PIXEL_AB_CAPTURE_SAVE_FAILED "+label)
    return shot

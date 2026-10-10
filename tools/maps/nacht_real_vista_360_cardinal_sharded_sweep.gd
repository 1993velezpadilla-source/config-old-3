extends SceneTree
## VISUAL A/B original source protected LOD + 340 Vista DDS, before/after 32m batching.
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
    # Source-target 360 yaw sampling only. Candidate eye-height anchors are
    # NOT proven navigable positions or source-certified windows. 4 locations x
    # cardinal 4 headings tests both indoor/exterior directions, including
    # views potentially looking through openings. No deletion proof.
    var centers: Array[Dictionary]=[
        {"name":"interior_original","p":Vector3(11.61863,1.65,-0.325515)},
        {"name":"interior_central","p":Vector3(4.5,1.6,0.4)},
        {"name":"exterior_south_candidate","p":Vector3(-2.494789,1.65,-31.0)},
        {"name":"exterior_east_candidate","p":Vector3(31.0,1.65,-7.258049)}
    ]
    var directions: Array[Vector3]=[
        Vector3(1,0,0),Vector3(0,0,1),Vector3(-1,0,0),Vector3(0,0,-1)
    ]
    var points: Array[Dictionary]=[]
    for center: Dictionary in centers:
        for heading: int in range(4):
            var direction: Vector3=directions[heading]
            var label: String=str(center["name"])+"_yaw"+str(heading*90)
            var eye: Vector3=center["p"]
            points.append({"name":label,"camera":eye,"look":eye+direction*30.0,
                           "headingDegrees":heading*90})
    var shard_name: String=""
    for arg: String in OS.get_cmdline_user_args():
        if arg=="--shard=indoors" or arg=="--shard=outdoors":
            shard_name=arg.trim_prefix("--shard=")
    if shard_name!="indoors" and shard_name!="outdoors":
        push_error("XZOGOT_NACHT_SHARDED_SOURCE_CAMERA_ARGUMENT_REQUIRED_RED")
        quit(30)
        return
    var selected: Array[Dictionary]=[]
    for camera_any: Dictionary in points:
        var n: String=str(camera_any["name"])
        if (shard_name=="indoors" and n.begins_with("interior_")) or (
            shard_name=="outdoors" and n.begins_with("exterior_")):
            selected.append(camera_any)
    points=selected
    if points.size()!=8:
        push_error("XZOGOT_NACHT_VIEW_SWEEP_CARDINAL_POSES_RED")
        quit(31)
        return
    var exterior_script: Script=load("res://nacht_apply_source_exterior_visual_lod.gd") as Script
    var external: Dictionary=(exterior_script.new() as RefCounted).call(
        "apply_to_real_source_meshes",p_any,by_actor) as Dictionary
    if not (external.get("errors",[]) as Array).is_empty():
        push_error("XZOGOT_NACHT_VIEW_SWEEP_ORIGINAL_EXTERIOR_POLICY_RED")
        quit(32)
        return
    var vista_script: Script=load("res://nacht_apply_source_vista_actor_local_dds.gd") as Script
    var textures: Dictionary=(vista_script.new() as RefCounted).call(
        "apply_authored_source_vistas",v_any,by_actor) as Dictionary
    if not (textures.get("errors",[]) as Array).is_empty():
        push_error("XZOGOT_NACHT_VIEW_SWEEP_ACTOR_LOCAL_DDS_RED")
        quit(33)
        return
    var originals: Dictionary={}
    var before_gpu: Dictionary={}
    for view: Dictionary in points:
        var label: String=str(view["name"])
        originals[label]=await _capture(cam,label+"_before_spatial32m",view["camera"],view["look"])
        before_gpu[label]={
            "visibleDrawCalls":int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)),
            "visiblePrimitiveIndices":int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))}
    var batch_script: Script=load("res://nacht_apply_vista_spatial_multimesh_research.gd") as Script
    if batch_script==null:
        push_error("XZOGOT_NACHT_VIEW_SWEEP_BATCH_SCRIPT_RED")
        quit(34)
        return
    var batch_root: Node3D=Node3D.new()
    root.add_child(batch_root)
    var batch: Dictionary=(batch_script.new() as RefCounted).call(
        "apply_original_vista_instance_batching",v_any,p_any,by_actor,batch_root,32.0) as Dictionary
    if (not (batch.get("errors",[]) as Array).is_empty()
        or int(batch.get("originalSourceActorsStillPresent",0))!=10793
        or int(batch.get("originalVistaActorIDsVerified",0))!=340
        or int(batch.get("originalActorsTemporarilyHidden",0))!=282
        or int(batch.get("actualOriginalSourceMultimeshNodes",0))!=90):
        push_error("XZOGOT_NACHT_VIEW_SWEEP_BATCH_IDENTITY_MISMATCH_RED "+JSON.stringify(batch))
        quit(35)
        return
    var failures: Array[String]=[]
    var cases: Array[Dictionary]=[]
    var meaningfully_lit: int=0
    var tree_visible_perspective_certified: bool=false
    for view: Dictionary in points:
        var label: String=str(view["name"])
        var after: Image=await _capture(cam,label+"_after_spatial32m",view["camera"],view["look"])
        var before: Image=originals[label] as Image
        var diff: Dictionary=_compare(before,after)
        diff["cameraName"]=label
        diff["eyePosition"]=str(view["camera"])
        diff["cameraYawDeg"]=view["headingDegrees"]
        var prior: Dictionary=before_gpu[label]
        var calls_after: int=int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME))
        var primitives_after: int=int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))
        diff["sourceDrawCallsBefore"]=int(prior["visibleDrawCalls"])
        diff["sourceDrawCallsAfter"]=calls_after
        diff["visiblePrimitiveIndicesBefore"]=int(prior["visiblePrimitiveIndices"])
        diff["visiblePrimitiveIndicesAfter"]=primitives_after
        diff["sourceDrawCallReduction"]=int(prior["visibleDrawCalls"])-calls_after
        diff["visiblePrimitiveIndicesReduction"]=int(prior["visiblePrimitiveIndices"])-primitives_after
        var has_source_detail: bool=int(diff["significantVisiblePixelsBefore"])>=500
        diff["cameraHasSomeSourceSceneDetail"]=has_source_detail
        if has_source_detail:
            meaningfully_lit+=1
        if float(diff["meanRGBDifferencePercent"])>0.25 or                 float(diff["changedPixelsOverRGB3PercentPercent"])>1.0:
            failures.append(label+" original-source spatial 32m pixel parity RED")
        if calls_after<=0 or int(prior["visibleDrawCalls"])<=0:
            failures.append(label+" invalid measured Mesa draw calls")
        cases.append(diff)
        print("XZOGOT_NACHT_NATIVE_VIEW_SWEEP_32M_ACTUAL_RGB_AND_GPU ",JSON.stringify(diff))
    if meaningfully_lit<6:
        failures.append("only "+str(meaningfully_lit)+"/8 viewpoints contain sufficiently visible scene samples")
    var report: Dictionary={
        "source":"archived Pavlov UE4.21 original 10793 actors, NOT authentic BO3 T7 source",
        "renderer":"Godot 4.6.1 Mesa llvmpipe real rasterization, NOT physical Android GPU",
        "fullOriginalActors":source_meshes.size(),
        "originalSourceMaterialBindings":surfaces,
        "sourceLightsReconstructed":166,
        "originalVistaTreeIds":340,
        "originalActorsRetained":int(batch["originalSourceActorsStillPresent"]),
        "sourceMultiMeshGroups":int(batch["actualOriginalSourceMultimeshNodes"]),
        "originalActorsTemporarilyHidden":int(batch["originalActorsTemporarilyHidden"]),
        "sampledCandidateEyeHeightPositions":2,
        "shardName":shard_name,
        "cardinal360DegreesHeadingsPerSample":4,
        "pairedBeforeAfterScreenshots":16,
        "individualPairReports":cases,
        "viewsWithAtLeast500NonDarkSourcePixels":meaningfully_lit,
        "originalWorld3DNavigationAndWindowsNotCertified":true,
        "noPermanentOriginalSourceDeletes":true,
        "realPhysicalAndroidGPUFPSOrMemoryMeasured":false,
        "productionShipApproved":false,
        "errors":failures
    }
    var out: FileAccess=FileAccess.open("res://nacht-original-vista-360-candidate-"+shard_name+"-visual-sweep.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(report,"\t"))
    out.close()
    if not failures.is_empty():
        push_error("XZOGOT_NACHT_REAL_SOURCE_VISTA_360_CARDINAL_SWEEP_RED "+JSON.stringify(failures))
        quit(36)
        return
    print("XZOGOT_NACHT_REAL_SOURCE_VISTA_8_SHARDED_YAWS_16_PIXELS_GREEN " +shard_name)
    quit(0)

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

func _compare(before: Image,after: Image) -> Dictionary:
    if before.get_size()!=after.get_size():
        return {"error":"different image pixel dimensions"}
    var w: int=before.get_width()
    var h: int=before.get_height()
    var total: float=0.0
    var large: int=0
    var nonblack: int=0
    var max_diff: float=0.0
    for y: int in range(h):
        for x: int in range(w):
            var a: Color=before.get_pixel(x,y)
            var b: Color=after.get_pixel(x,y)
            var d: float=(absf(a.r-b.r)+absf(a.g-b.g)+absf(a.b-b.b))/3.0
            total+=d
            max_diff=maxf(max_diff,d)
            if d>0.03:
                large+=1
            if maxf(a.r,maxf(a.g,a.b))>0.09:
                nonblack+=1
    return {
        "resolution":[w,h],
        "meanRGBDifferencePercent":100.0*total/float(w*h),
        "changedPixelsOverRGB3Percent":large,
        "changedPixelsOverRGB3PercentPercent":100.0*float(large)/float(w*h),
        "maximumRGBDifference":max_diff,
        "significantVisiblePixelsBefore":nonblack,
        "physicalAndroidFPSNotBenchmarked":true
    }

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
    var policy_any: Variant=JSON.parse_string(FileAccess.get_file_as_string(
        "res://nacht-authority/source-original-26-architectural-policy.json"))
    if not (policy_any is Dictionary):
        push_error("XZOGOT_NACHT_26_ARCHITECTURAL_POLICY_FILE_ABSENT_RED")
        quit(22)
        return
    var policy: Dictionary=policy_any as Dictionary
    var stage_script: Script=load(
        "res://nacht_apply_conservative_opaque_architecture_research.gd") as Script
    if stage_script==null:
        push_error("XZOGOT_NACHT_26_ARCHITECTURAL_SOURCE_CONTROL_SCRIPT_ABSENT_RED")
        quit(23)
        return
    var controller: RefCounted=stage_script.new() as RefCounted
    var views: Array[Dictionary]=[
        {"name":"interior_central_yaw180","eye":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw0","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(42.0,1.65,-0.325515)},
        {"name":"interior_original_yaw270","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var before: Dictionary={}
    for v: Dictionary in views:
        before[str(v["name"])]=await _capture(
            cam,str(v["name"])+"_architectural_source_before",v["eye"],v["look"])
    var apply_result: Dictionary=controller.call(
        "apply_source_architecture_opaque_research",policy,bridge,by_actor) as Dictionary
    if (not (apply_result.get("errors",[]) as Array).is_empty()
        or int(apply_result.get("sourceOriginalActorsStillPresent",0))!=10793
        or int(apply_result.get("architecturalSourceMaterialsChanged",0))!=26
        or int(apply_result.get("architecturalSourceSurfaceOverridesChanged",0))!=1262):
        push_error("XZOGOT_NACHT_ARCHITECTURAL_ORIGINAL_ALPHA_PROTECTED_APPLY_RED "+
            JSON.stringify(apply_result))
        quit(24)
        return
    var after: Dictionary={}
    for v: Dictionary in views:
        after[str(v["name"])]=await _capture(
            cam,str(v["name"])+"_architectural_source_preview",v["eye"],v["look"])
    var restore: Dictionary=controller.call("restore_original_source_architecture") as Dictionary
    if (not (restore.get("errors",[]) as Array).is_empty()
        or int(restore.get("exactOriginalSurfacePointersRestored",0))!=1262):
        push_error("XZOGOT_NACHT_ARCHITECTURAL_SOURCE_ORIGINAL_RESTORE_RED "+
            JSON.stringify(restore))
        quit(25)
        return
    var restored: Image=await _capture(
        cam,"interior_central_yaw180_architectural_source_restored",
        views[0]["eye"],views[0]["look"])
    var restored_delta: Dictionary=_image_delta(
        before["interior_central_yaw180"] as Image,restored)
    var original_samples: Array[Dictionary]=[]
    for v: Dictionary in views:
        var name: String=str(v["name"])
        var baseline: Image=before[name] as Image
        var candidate: Image=after[name] as Image
        var dark: Dictionary=_black_recover(baseline,candidate,candidate)
        dark["camera"]=name
        dark["sourceOriginalVsArchitectureOnly"]=_image_delta(baseline,candidate)
        original_samples.append(dark)
        print("XZOGOT_NACHT_SAFE_26_BUILDING_ONLY_BLACK_PIXEL_RECOVERY ",
            JSON.stringify(dark))
    var out: Dictionary={
        "scene":"original 10793 Pavlov UE4.21 archive actors (NOT authentic BO3 T7)",
        "GodotRenderer":"Actual 4.6.1 Mesa Compatibility OpenGL NOT Android phone",
        "sourceActorsUnmodified":by_actor.size(),
        "sourceMaterialSurfaceBindings":surfaces,
        "sourceLightComponents":166,
        "sourceUsedDDS":718,
        "architecturalCandidateOriginalMaterials":26,
        "architecturalSourceBindingsPotentiallyFixed":1262,
        "otherOriginalMaterialPathsUntouched":548,
        "originalSourceActorGeometryNeverDeleted":true,
        "windowTreeFoliageDecalsNotAlteredByThisExperiment":true,
        "sourceGraphIncompleteSoMaskOutputStillUnproven":true,
        "actualOriginalArchitectureCandidateVsBaseline":original_samples,
        "originalSourceMaterialPointerRestoration":restore,
        "originalSourceRenderedRestorationRGBDifference":restored_delta,
        "shippingFixNotYetApproved":true,
        "physicalAndroidFPSVRAMNotMeasured":true,
        "allPlayableWindowsNotYetCovered":true
    }
    var output: FileAccess=FileAccess.open(
        "res://nacht-26-architecture-only-original-source-alpha-preview.json",
        FileAccess.WRITE)
    output.store_string(JSON.stringify(out,"\t"))
    output.close()
    if restored_delta["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_26_ARCHITECTURE_EXPERIMENT_SOURCE_RESTORE_PIXEL_RED")
        quit(26)
        return
    print("XZOGOT_NACHT_REAL_26_ARCHITECTURE_ONLY_ALPHA_7_PNG_RESTORE_GREEN")
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

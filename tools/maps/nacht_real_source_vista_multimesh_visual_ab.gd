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
    var points: Array[Dictionary]=[
        {"name":"overview","camera":Vector3(24.66175,37.85322,19.89849),
         "look":Vector3(-2.494789,3.153206,-7.258049)},
        {"name":"interior","camera":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(4.5,1.6,0.4)}
    ]
    var exterior_script: Script=load("res://nacht_apply_source_exterior_visual_lod.gd") as Script
    var control: RefCounted=exterior_script.new() as RefCounted
    var changes: Dictionary=control.call("apply_to_real_source_meshes",p_any,by_actor) as Dictionary
    if not (changes.get("errors",[]) as Array).is_empty():
        push_error("NACHT_AB_VISUAL_EXTERIOR_PROTECTION_RED "+JSON.stringify(changes))
        quit(13)
        return
    var vista_script: Script=load("res://nacht_apply_source_vista_actor_local_dds.gd") as Script
    var vista: Dictionary=(vista_script.new() as RefCounted).call("apply_authored_source_vistas",v_any,by_actor) as Dictionary
    if not (vista.get("errors",[]) as Array).is_empty():
        push_error("NACHT_AB_VISUAL_ORIGINAL_VISTA_SOURCE_DDS_RED "+JSON.stringify(vista))
        quit(14)
        return
    var nearest: MeshInstance3D=null
    var nearest_distance: float=999999.0
    var anchor: Vector3=Vector3(-2.494789,2.0,-7.258049)
    for datum_any: Variant in v_any["actorDetails"]:
        var source_id: String=str((datum_any as Dictionary)["originalActorID"])
        var mi: MeshInstance3D=by_actor[source_id] as MeshInstance3D
        if mi==null:
            continue
        var dis: float=Vector2(mi.global_position.x,mi.global_position.z).distance_to(Vector2(anchor.x,anchor.z))
        if dis<nearest_distance and dis>55.0:
            nearest_distance=dis
            nearest=mi
    if nearest==null:
        push_error("NACHT_AB_VISUAL_NO_AUTHORED_ORIGINAL_VISTA_TREE_RED")
        quit(15)
        return
    var focus: Vector3=nearest.global_position
    var direction: Vector3=Vector3(focus.x-anchor.x,0.0,focus.z-anchor.z).normalized()
    points.append({
        "name":"source_vista_near_tree",
        "camera":anchor+direction*23.0,
        "look":Vector3(focus.x,focus.y+4.0,focus.z)
    })
    var original_images: Dictionary={}
    for view: Dictionary in points:
        original_images[str(view["name"])]=await _capture(cam,
            str(view["name"])+"_before_spatial32m",
            view["camera"],view["look"])
    var batch_script: Script=load("res://nacht_apply_vista_spatial_multimesh_research.gd") as Script
    if batch_script==null:
        push_error("NACHT_AB_VISUAL_RESEARCH_BATCH_SCRIPT_ABSENT_RED")
        quit(16)
        return
    var stage: Node3D=Node3D.new()
    root.add_child(stage)
    var batch: Dictionary=(batch_script.new() as RefCounted).call(
        "apply_original_vista_instance_batching",v_any,p_any,by_actor,stage,32.0) as Dictionary
    if (not (batch.get("errors",[]) as Array).is_empty()
        or int(batch.get("originalSourceActorsStillPresent",0))!=10793
        or int(batch.get("originalActorsTemporarilyHidden",0))<200):
        push_error("NACHT_AB_VISUAL_ORIGINAL_BATCH_GUARD_RED "+JSON.stringify(batch))
        quit(17)
        return
    var cases: Array[Dictionary]=[]
    var all_errors: Array[String]=[]
    for view: Dictionary in points:
        var name: String=str(view["name"])
        var after: Image=await _capture(cam,name+"_after_spatial32m",
                                        view["camera"],view["look"])
        var original: Image=original_images[name] as Image
        var diff: Dictionary=_compare(original,after)
        diff["camera"]=name
        cases.append(diff)
        print("XZOGOT_NACHT_REAL_NATIVE_VISTA_ORIGINAL_VS_BATCH_SCREEN_RGB ",JSON.stringify(diff))
        if float(diff["meanRGBDifferencePercent"])>0.25:
            all_errors.append(name+" meanRGBDifferencePercent > 0.25%")
        if float(diff["changedPixelsOverRGB3PercentPercent"])>1.0:
            all_errors.append(name+" changed significant pixels > 1%")
        if int(diff["significantVisiblePixelsBefore"])<500 and name=="source_vista_near_tree":
            all_errors.append(name+" sample camera produced insufficient visible source scene pixels")
    var report: Dictionary={
        "source":"Original Pavlov UE4.21 full 10793 MeshInstance3D, 574 materials, 718 DDS, 166 lights; NOT BO3 T7",
        "renderer":"Godot 4.6.1 Mesa OpenGL Compatibility llvmpipe, NOT physical Android GPU",
        "actorAndSurfaceAuthority":[source_meshes.size(),surfaces],
        "originalVistaSourceDDS":vista,
        "protectedExteriorVisualLOD":changes,
        "experimental32mNativeSourceBatch":batch,
        "vistaCenterOriginalActorID":str(nearest.name),
        "cameraCases":cases,
        "realOriginalNachtPixelParityTested":true,
        "allReachable360WindowVisibilityCertified":false,
        "androidGPUFPSOrVRAMMeasured":false,
        "approvedToShip":false,
        "errors":all_errors
    }
    var out: FileAccess=FileAccess.open("res://nacht-native-source-vista-spatial-visual-ab.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(report,"\t"))
    out.close()
    if not all_errors.is_empty():
        push_error("XZOGOT_NACHT_REAL_NATIVE_VISTA_BATCH_VISUAL_CHANGE_REQUIRES_REVIEW_RED "+JSON.stringify(all_errors))
        quit(18)
        return
    print("XZOGOT_NACHT_REAL_SOURCE_VISTA_3_CAMERAS_VISUAL_PARITY_GREEN")
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

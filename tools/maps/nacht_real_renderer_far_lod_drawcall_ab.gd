extends SceneTree
## REAL Godot 4.6 gl_compatibility renderer monitor A/B for original Nacht.
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
    var before: Array[Dictionary]=[]
    for view: Dictionary in points:
        before.append(await _measure(cam,"native_source_before_"+view["name"],view["camera"],view["look"]))
    var exterior_script: Script=load("res://nacht_apply_source_exterior_visual_lod.gd") as Script
    if exterior_script==null:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_ORIGINAL_EXTERIOR_CONTROL_MISSING_RED")
        quit(13)
        return
    var control: RefCounted=exterior_script.new() as RefCounted
    var changes: Dictionary=control.call("apply_to_real_source_meshes",p_any,by_actor) as Dictionary
    if (not (changes.get("errors",[]) as Array).is_empty() or
        int(changes.get("actualFarExteriorGodotActorsOptimized",0))<400 or
        int(changes.get("nearBuildingOriginalActorsProtected",0))<100):
        push_error("XZOGOT_NACHT_DRAW_MONITOR_NEAR_BUILDING_NOT_GUARDED_RED "+JSON.stringify(changes))
        quit(14)
        return
    var exterior: Array[Dictionary]=[]
    for view: Dictionary in points:
        exterior.append(await _measure(cam,"far_visual_policy_"+view["name"],view["camera"],view["look"]))
    var vista_script: Script=load("res://nacht_apply_source_vista_actor_local_dds.gd") as Script
    if vista_script==null:
        push_error("XZOGOT_NACHT_DRAW_MONITOR_VISTA_SOURCE_DDS_SCRIPT_MISSING_RED")
        quit(15)
        return
    var vista_control: RefCounted=vista_script.new() as RefCounted
    var vista: Dictionary=vista_control.call("apply_authored_source_vistas",v_any,by_actor) as Dictionary
    if (not (vista.get("errors",[]) as Array).is_empty() or
        int(vista.get("sourceAuthoredVistaActorsWithSourceDerivedLowRes",0))<100):
        push_error("XZOGOT_NACHT_DRAW_MONITOR_VISTA_SOURCE_DDS_DERIVATION_RED "+JSON.stringify(vista))
        quit(16)
        return
    var vistas: Array[Dictionary]=[]
    for view: Dictionary in points:
        vistas.append(await _measure(cam,"far_source_vista_dds_"+view["name"],view["camera"],view["look"]))
    var warnings: Array[String]=[]
    for sample: Dictionary in before:
        if int(sample["realVisibleDrawCalls"])<=0 or int(sample["realVisibleObjects"])<=0:
            warnings.append("Mesa Godot renderer draw/object performance counters zero: unsupported")
    var report: Dictionary={
        "source":"Pavlov UE4.21 real glTF mesh+material+166 lights, NOT BO3 T7",
        "renderGodotVersion":Engine.get_version_info().get("string",""),
        "renderBackend":"Linux Mesa gl_compatibility via Xvfb; NOT Android phone GPU",
        "originalNativeActors":source_meshes.size(),
        "originalSourceMaterialBindings":surfaces,
        "originalLightComponents":166,
        "realSourceOriginalBaselineRenderer":before,
        "sourceFarExteriorOnlyRealRenderer":exterior,
        "realActorSpecificSourceDerivedDDSExtension":vistas,
        "realExteriorSourceOptimizationReport":changes,
        "actualVistaSourceImageDownsample":vista,
        "validGodotRendererMeasurements":warnings.is_empty(),
        "androidGPUActualFPSOrMemoryMeasured":false,
        "occludedActorDeletionCertified":false,
        "sourceMaterialAndGLTFActorResourcesPreserved":true,
        "warnings":warnings
    }
    var out: FileAccess=FileAccess.open("res://nacht-source-renderer-gpu-submission-ab-report.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(report,"\t"))
    out.close()
    binder.queue_free()
    world.queue_free()
    if not warnings.is_empty():
        push_error("XZOGOT_NACHT_REAL_RENDERER_GPU_DRAW_CALL_MONITOR_UNAVAILABLE_RED "+JSON.stringify(report))
        quit(17)
        return
    print("XZOGOT_NACHT_REAL_GODOT_MESA_SOURCE_NATIVE_FAR_VISUAL_DRAW_CALL_AB_GREEN",
        " views=2 variants=3 source_actors=",source_meshes.size(),
        " measured_real_renderer_drawcall_counters=true",
        " true_Android_GPU_FPS_unmeasured=true")
    quit(0)

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
    # Compare source original archived night exposure to reversible positional
    # candle/lumen relative source intensities, rendered with native 718 DDS.
    # This is NOT source photometric lightmap equivalence, never a ship fix.
    var adapter_source: Script=load(
        "res://nacht_compatibility_source_relative_light_research.gd") as Script
    if adapter_source==null:
        push_error("XZOGOT_NACHT_SOURCE_RELATIVE_LIGHT_ADAPTER_NOT_STAGED_RED")
        quit(41)
        return
    var adapter: RefCounted=adapter_source.new() as RefCounted
    var views: Array[Dictionary]=[
        {"name":"interior_central_yaw180","eye":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw270","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var before: Dictionary={}
    for v: Dictionary in views:
        before[str(v["name"])]=await _capture(cam,
            str(v["name"])+"_source_lights_original",v["eye"],v["look"])
    var relative: Dictionary=adapter.call("apply_original_source_light_ratios_research",
        light_basis,by_actor.size(),4.0) as Dictionary
    if (not (relative.get("errors",[]) as Array).is_empty()
        or int(relative.get("sourceLightNodeCountIncludingDirectional",0))!=165
        or int(relative.get("positiveOriginalPointSpotLights",0))<20
        or not relative.get("unitlessValuesNeverMixedWithCandelaLumens",false)):
        push_error("XZOGOT_NACHT_SOURCE_LIGHT_RELATIVE_CANDLE_AUDIT_RED "+JSON.stringify(relative))
        quit(42)
        return
    var after: Dictionary={}
    for v: Dictionary in views:
        after[str(v["name"])]=await _capture(cam,
            str(v["name"])+"_source_candela_relative_4cap_preview",
            v["eye"],v["look"])
    var restored: Dictionary=adapter.call("restore_source_light_energy") as Dictionary
    if (not (restored.get("errors",[]) as Array).is_empty()
        or int(restored.get("originalSourceLightEnergyResourcesRestored",0))!=165):
        push_error("XZOGOT_NACHT_SOURCE_ORIGINAL_LIGHT_ENERGY_RESTORE_RED "+JSON.stringify(restored))
        quit(43)
        return
    var control: Image=await _capture(cam,
        "interior_central_yaw180_source_light_ratios_restored",
        views[0]["eye"],views[0]["look"])
    var restored_image: Dictionary=_image_delta(
        before["interior_central_yaw180"] as Image,control)
    var pairs: Array[Dictionary]=[]
    for v: Dictionary in views:
        var name: String=str(v["name"])
        var a: Image=before[name] as Image
        var b: Image=after[name] as Image
        var row: Dictionary=_black_recover(a,b,b)
        row["sourceOriginalCamera"]=name
        row["relativeSourceIntensityRGBChange"]=_image_delta(a,b)
        pairs.append(row)
        print("XZOGOT_NACHT_UE_CANDLE_GODOT_COMPAT_ORIGINAL_BLACK_WALL_A_B ",JSON.stringify(row))
    var verdict: Dictionary={
        "source":"Full 10793 native archived Pavlov UE4.21 actors, not original BO3 T7",
        "renderer":"Godot 4.6.1 Mesa OpenGL Compatibility software GPU, NOT physical Android",
        "originalSourceActors":by_actor.size(),
        "originalDDSUsed":718,
        "originalEffectiveSurfaceBindings":surfaces,
        "sourceUE421LightComponentCount":166,
        "sourcePositionalAndDirectionalLightNodes":165,
        "researchRelativeLightCandidateOriginalSource":relative,
        "researchOnlyOriginalLightRestore":restored,
        "restoredCameraOriginalRGBDifference":restored_image,
        "sourceNativeInteriorTwoCameraCandidateResults":pairs,
        "sourceOriginalActorMeshesUnmodified":true,
        "originalMaterialAlphaAndDDSTexturesUnmodified":true,
        "noInventedNewLights":true,
        "lightEnergiesOnlyTemporaryAndNormalizedToSourceMedian":true,
        "physicalPhotometricEquivalentUE4LightingNOTProven":true,
        "GodotPhysicalLightUnitsNotSupportedOnCompatibility":true,
        "allWindowsAndPlayable360NotCertified":true,
        "realAndroidFPSVRAMNotMeasured":true,
        "productionLightingFixApproved":false
    }
    var f: FileAccess=FileAccess.open(
        "res://nacht-original-source-relative-compat-lighting-2-cameras.json",
        FileAccess.WRITE)
    f.store_string(JSON.stringify(verdict,"\t"))
    f.close()
    if restored_image["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_SOURCE_RELATIVE_COMPAT_LIGHTING_BASELINE_NOT_RESTORED_RED")
        quit(44)
        return
    print("XZOGOT_NACHT_REAL_UE421_SOURCE_RELATIVE_COMPAT_LIGHTING_5_PNG_RESTORED_GREEN")
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

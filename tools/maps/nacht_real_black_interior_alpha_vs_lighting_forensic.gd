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
    # Research only: original 718 source DDS, exactly 3 eye-height interiors.
    # Hypothesis: Godot alpha-scissor uses texture alpha when source UE4
    # OpacityMask graph output is unwired / incomplete. NO SHIPPING CHANGE.
    var cameras: Array[Dictionary]=[
        {"name":"interior_central_yaw180","eye":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw0","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(42.0,1.65,-0.325515)},
        {"name":"interior_original_yaw270","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var source_material_override_by_mesh: Dictionary={}
    var original_packed_mesh_surfaces: int=0
    var affected_alpha_scissor_source_surfaces: int=0
    var distinct_mask_materials: Dictionary={}
    var interior_near_masked_source_surfaces: int=0
    var original_alpha_masked_meshes: int=0
    for node_any: Node in source_meshes:
        var mesh_node: MeshInstance3D=node_any as MeshInstance3D
        var previous: Array[Material]=[]
        var masked_here: bool=false
        for i: int in range(mesh_node.mesh.get_surface_count()):
            var old: Material=mesh_node.get_surface_override_material(i)
            if old==null:
                push_error("XZOGOT_NACHT_ALPHA_SOURCE_UNBOUND_MATERIAL_RED "+str(mesh_node.name))
                quit(24)
                return
            previous.append(old)
            original_packed_mesh_surfaces+=1
            var std: StandardMaterial3D=old as StandardMaterial3D
            if std!=null and std.transparency==BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                affected_alpha_scissor_source_surfaces+=1
                distinct_mask_materials[old.get_instance_id()]=true
                masked_here=true
                var center: Vector3=(mesh_node.global_transform*mesh_node.mesh.get_aabb()).get_center()
                if center.distance_to(Vector3(-2.494789,1.65,-7.258049))<=55.0:
                    interior_near_masked_source_surfaces+=1
        if masked_here:
            original_alpha_masked_meshes+=1
        source_material_override_by_mesh[mesh_node.get_instance_id()]=previous
    if (original_packed_mesh_surfaces!=16595
        or affected_alpha_scissor_source_surfaces<13000
        or affected_alpha_scissor_source_surfaces>16595
        or distinct_mask_materials.size()<500):
        push_error("XZOGOT_NACHT_ALPHA_SOURCE_MATERIAL_IDENTITY_RED "+
            str([original_packed_mesh_surfaces,affected_alpha_scissor_source_surfaces,distinct_mask_materials.size()]))
        quit(25)
        return
    var baseline: Dictionary={}
    for c: Dictionary in cameras:
        baseline[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_source_as_is",c["eye"],c["look"])
    # Stage B: keep authored diffuse/normal DDS and UE original lighting,
    # disable ONLY the native engine's masked texture-alpha scissor. A/B only.
    var alpha_off_by_source: Dictionary={}
    for node_any: Node in source_meshes:
        var mesh_node: MeshInstance3D=node_any as MeshInstance3D
        var originals: Array=source_material_override_by_mesh[mesh_node.get_instance_id()]
        for i: int in range(originals.size()):
            var old: Material=originals[i] as Material
            var std: StandardMaterial3D=old as StandardMaterial3D
            if std==null or std.transparency!=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                continue
            var material_id: int=old.get_instance_id()
            if not alpha_off_by_source.has(material_id):
                var copy: StandardMaterial3D=std.duplicate(false) as StandardMaterial3D
                copy.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
                alpha_off_by_source[material_id]=copy
            mesh_node.set_surface_override_material(i,alpha_off_by_source[material_id])
    var no_alpha: Dictionary={}
    for c: Dictionary in cameras:
        no_alpha[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_only_source_mask_scissor_off",c["eye"],c["look"])
    # Stage C: keep the same source DDS and original cull, but suppress lighting
    # to test whether many black walls are from UE->Godot light/color translation.
    var unshaded_by_source: Dictionary={}
    for node_any: Node in source_meshes:
        var mesh_node: MeshInstance3D=node_any as MeshInstance3D
        var originals: Array=source_material_override_by_mesh[mesh_node.get_instance_id()]
        for i: int in range(originals.size()):
            var old: Material=originals[i] as Material
            var std: StandardMaterial3D=old as StandardMaterial3D
            if std==null:
                continue
            var material_id: int=old.get_instance_id()
            if not unshaded_by_source.has(material_id):
                var copy: StandardMaterial3D=std.duplicate(false) as StandardMaterial3D
                copy.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
                if copy.transparency==BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                    copy.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
                unshaded_by_source[material_id]=copy
            mesh_node.set_surface_override_material(i,unshaded_by_source[material_id])
    var unshaded: Dictionary={}
    for c: Dictionary in cameras:
        unshaded[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_same_DDS_no_alpha_no_light",c["eye"],c["look"])
    # Force original material assignments back, no saved asset changes.
    for node_any: Node in source_meshes:
        var mesh_node: MeshInstance3D=node_any as MeshInstance3D
        var originals: Array=source_material_override_by_mesh[mesh_node.get_instance_id()]
        for i: int in range(originals.size()):
            mesh_node.set_surface_override_material(i,originals[i] as Material)
    var restored: Image=await _capture(cam,
        "interior_central_yaw180_source_materials_restored",
        cameras[0]["eye"],cameras[0]["look"])
    var restore_delta: Dictionary=_image_delta(
        baseline["interior_central_yaw180"] as Image,restored)
    var results: Array[Dictionary]=[]
    for c: Dictionary in cameras:
        var key: String=str(c["name"])
        var original: Image=baseline[key] as Image
        var opaque: Image=no_alpha[key] as Image
        var bright: Image=unshaded[key] as Image
        var s: Dictionary=_black_recover(original,opaque,bright)
        s["sourceCamera"]=key
        s["pixelDeltaOnlyAlphaScissorDisabled"]=_image_delta(original,opaque)
        s["pixelDeltaUnshadedSameDDS"]=_image_delta(original,bright)
        results.append(s)
        print("XZOGOT_NACHT_INTERIOR_NATIVE_MASK_VS_LIGHT_A_B ",
            JSON.stringify(s))
    var report: Dictionary={
        "source":"full archived Pavlov UE4.21 native source (NOT genuine BO3 T7)",
        "renderer":"Actual Godot 4.6.1 Mesa software OpenGL, NOT physical Android",
        "nativeMeshActorNodes":source_meshes.size(),
        "nativeOriginalSourceSurfaceBindings":original_packed_mesh_surfaces,
        "sourceAlphaScissorSurfacesTested":affected_alpha_scissor_source_surfaces,
        "sourceDistinctMaskedMaterialResources":distinct_mask_materials.size(),
        "sourceMaskedMeshInstances":original_alpha_masked_meshes,
        "originalNear55mMaskedSurfaces":interior_near_masked_source_surfaces,
        "originalLightsReconstructed":166,
        "sourceUsedDDSStaged":718,
        "threeRealCameraSourceMaterialAlphaAndLightingExperiments":results,
        "postExperimentOriginalMaterialRestoreRGBDelta":restore_delta,
        "originalSourceAssetFilesUnchanged":true,
        "shippingMaterialBehaviorNotModified":true,
        "unlitExperimentNotAValidProductionLightingSolution":true,
        "alphaOffExperimentNotAProductionAlphaSolution":true,
        "noUnprovenGlobalAlphaOverrideShipped":true,
        "physicalAndroidFPSMeasured":false,
        "playableReachabilityOrEveryWindowCertified":false,
        "originalBlackInteriorVisualArtApproved":false
    }
    var out: FileAccess=FileAccess.open("res://nacht-original-three-camera-alpha-light-recovery.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(report,"\t"))
    out.close()
    if restore_delta["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_ALPHA_INTERIOR_MATERIAL_RESTORATION_NOT_EXACT_RED "+
            JSON.stringify(restore_delta))
        quit(26)
        return
    print("XZOGOT_NACHT_REAL_INTERIOR_3_CAMERA_SOURCE_ALPHA_VS_LIGHT_FORENSIC_GREEN")
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

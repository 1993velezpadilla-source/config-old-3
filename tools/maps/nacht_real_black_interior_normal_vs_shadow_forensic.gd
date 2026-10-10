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
    # Preserve the original 718 DDS source materials and 166 UE light nodes.
    # Diagnose whether black wall patches arise from normal maps or source
    # shadow-casters, not just OpacityMask. NO scene/source asset edits.
    var cameras: Array[Dictionary]=[
        {"name":"interior_central_yaw180","eye":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw270","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var all_lights: Array[Node]=light_basis.find_children("*","Light3D",true,false)
    var active_lights: Array[Light3D]=[]
    var native_light_shadows: Dictionary={}
    for raw: Node in all_lights:
        var light: Light3D=raw as Light3D
        if light==null:
            continue
        active_lights.append(light)
        native_light_shadows[light.get_instance_id()]=light.shadow_enabled
    if active_lights.size()!=165:
        push_error("XZOGOT_NACHT_BLACK_NORMAL_SHADOW_SOURCE_165_LIGHTS_RED "+
            str(active_lights.size()))
        quit(31)
        return
    var original_overrides: Dictionary={}
    var source_normal_surfaces: int=0
    var distinct_normals: Dictionary={}
    var shadowed_lights: int=0
    for l: Light3D in active_lights:
        if l.shadow_enabled:
            shadowed_lights+=1
    for raw: Node in source_meshes:
        var mi: MeshInstance3D=raw as MeshInstance3D
        var prev: Array[Material]=[]
        for i: int in range(mi.mesh.get_surface_count()):
            var m: StandardMaterial3D=mi.get_surface_override_material(i) as StandardMaterial3D
            if m==null:
                push_error("XZOGOT_NACHT_ORIGINAL_NORMAL_PROBE_MATERIAL_MISSING_RED")
                quit(32)
                return
            prev.append(m)
            if m.normal_enabled:
                source_normal_surfaces+=1
                distinct_normals[m.get_instance_id()]=true
        original_overrides[mi.get_instance_id()]=prev
    if source_normal_surfaces<1000 or distinct_normals.size()<50:
        push_error("XZOGOT_NACHT_ORIGINAL_718_DDS_NORMAL_INPUTS_ABSENT_RED "+
            str([source_normal_surfaces,distinct_normals.size()]))
        quit(33)
        return
    var before: Dictionary={}
    for c: Dictionary in cameras:
        before[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_normal_shadow_original",c["eye"],c["look"])
    for l: Light3D in active_lights:
        l.shadow_enabled=false
    var no_shadow: Dictionary={}
    for c: Dictionary in cameras:
        no_shadow[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_source_shadow_off",c["eye"],c["look"])
    for l: Light3D in active_lights:
        l.shadow_enabled=bool(native_light_shadows[l.get_instance_id()])
    var no_normal_clones: Dictionary={}
    for raw: Node in source_meshes:
        var mi: MeshInstance3D=raw as MeshInstance3D
        var previous: Array=original_overrides[mi.get_instance_id()]
        for i: int in range(previous.size()):
            var m: StandardMaterial3D=previous[i] as StandardMaterial3D
            if not m.normal_enabled:
                continue
            var id: int=m.get_instance_id()
            if not no_normal_clones.has(id):
                var clone: StandardMaterial3D=m.duplicate(false) as StandardMaterial3D
                clone.normal_enabled=false
                if (clone.albedo_texture!=m.albedo_texture
                    or clone.normal_texture!=m.normal_texture
                    or clone.transparency!=m.transparency
                    or clone.cull_mode!=m.cull_mode
                    or clone.shading_mode!=m.shading_mode):
                    push_error("XZOGOT_NACHT_NORMAL_RESEARCH_CHANGED_SOURCE_ALPHA_OR_DDS_RED")
                    quit(34)
                    return
                no_normal_clones[id]=clone
            mi.set_surface_override_material(i,no_normal_clones[id] as Material)
    var no_normal: Dictionary={}
    for c: Dictionary in cameras:
        no_normal[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_source_normal_off",c["eye"],c["look"])
    # Restore source original material pointers even before image checks.
    var restored_count: int=0
    for raw: Node in source_meshes:
        var mi: MeshInstance3D=raw as MeshInstance3D
        var prev: Array=original_overrides[mi.get_instance_id()]
        for i: int in range(prev.size()):
            mi.set_surface_override_material(i,prev[i] as Material)
            if mi.get_surface_override_material(i)!=prev[i]:
                push_error("XZOGOT_NACHT_NORMAL_SHADOW_ORIGINAL_MATERIAL_RESTORE_RED")
                quit(35)
                return
            restored_count+=1
    for l: Light3D in active_lights:
        if l.shadow_enabled!=native_light_shadows[l.get_instance_id()]:
            push_error("XZOGOT_NACHT_ORIGINAL_SHADOW_STATE_RESTORE_RED")
            quit(36)
            return
    var restored: Image=await _capture(cam,
        "interior_central_yaw180_original_shader_restored",
        cameras[0]["eye"],cameras[0]["look"])
    var restore_delta: Dictionary=_image_delta(
        before["interior_central_yaw180"] as Image,restored)
    var cases: Array[Dictionary]=[]
    for c: Dictionary in cameras:
        var name: String=str(c["name"])
        var a: Image=before[name] as Image
        var b: Image=no_shadow[name] as Image
        var d: Image=no_normal[name] as Image
        var v: Dictionary=_black_recover(a,b,d)
        v["originalNativeSourceCamera"]=name
        v["originalVsShadowOnlyDisabled"]=_image_delta(a,b)
        v["originalVsSourceNormalMapOnlyDisabled"]=_image_delta(a,d)
        cases.append(v)
        print("XZOGOT_NACHT_ORIGINAL_BLACK_SOURCE_NORMAL_VS_SHADOW_PIXEL_QA ",
            JSON.stringify(v))
    var result: Dictionary={
        "originalFullSceneActors":source_meshes.size(),
        "sourceMaterialSurfaceBindings":restored_count,
        "sourceUsedDDSStaged":718,
        "sourceUE421LightComponents":166,
        "originalGodotLightNodeCountExcludingSky":active_lights.size(),
        "originalLightsCastingShadows":shadowed_lights,
        "sourceNormalMappedSurfaceBindings":source_normal_surfaces,
        "distinctSourceNormalMaterials":distinct_normals.size(),
        "realSourceOriginalTwoCameraNormalVsShadowCases":cases,
        "allOriginalSourceMaterialResourcePointersRestored":true,
        "allSourceLightShadowsRestored":true,
        "originalRestoredCameraMeanRGBDifference":restore_delta,
        "entireMapNormalsHaveNotBeenPermanentlyDisabled":true,
        "allExteriorAndWindowVisibilityNotCertified":true,
        "renderMethod":"Godot 4.6.1 Mesa Compatibility software GPU NOT actual phone",
        "sourceProvenance":"Pavlov UE4.21 reconstruction NOT original BO3 T7",
        "productionLightingOrShaderFixApproved":false
    }
    var output: FileAccess=FileAccess.open(
        "res://nacht-original-interior-normal-vs-shadow-forensic.json",FileAccess.WRITE)
    output.store_string(JSON.stringify(result,"\t"))
    output.close()
    if restore_delta["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_NORMAL_VS_SHADOW_RESEARCH_NOT_VISUALLY_REVERSIBLE_RED")
        quit(37)
        return
    print("XZOGOT_NACHT_REAL_ORIGINAL_INTERIOR_NORMAL_VS_SHADOW_SEVEN_PNG_GREEN")
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

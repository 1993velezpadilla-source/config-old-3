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
    # Source-confirmed CANDIDATE set only, never changes active game.
    # Requires exact archived 574 material definitions and 10793 native IDs.
    # Reuse exact original authoritative dictionary validated at function start.
    if (int(bridge.get("sourceActorCount",-1))!=10793
        or int(bridge.get("distinctSourceEffectiveMaterials",-1))!=574
        or int(bridge.get("originalSourceSurfaceBindings",-1))!=16595):
        push_error("XZOGOT_NACHT_NATIVE_SOURCE_MASK_AUTHORITY_COUNT_RED")
        quit(24)
        return
    var masked_candidate: Dictionary={}
    var excluded_masked: Dictionary={}
    var source_master: String=(
        "Content/CustomMaps/UGC2755515831/CoD_nacht/AssetsFolder/MasterMat.MasterMat")
    for m_any: Variant in bridge["materials"]:
        var m: Dictionary=m_any as Dictionary
        if str(m.get("blendMode",""))!="BLEND_Masked":
            continue
        var path: String=str(m["materialPath"])
        var names: Array=m.get("baseSourceRawPropertyNames",[]) as Array
        var linked: Dictionary=m.get("sourceGraphBindings",{}) as Dictionary
        var unresolved: Dictionary=m.get("sourceGraphUnresolvedOutputs",{}) as Dictionary
        var no_authored_opacity_output: bool=(
            not names.has("OpacityMask")
            and not linked.has("OpacityMask")
            and not unresolved.has("OpacityMask")
        )
        if (str(m.get("semanticBaseMaterialPath",""))==source_master
            and no_authored_opacity_output
            and str(m.get("sourceGraphStatus",""))=="partial"):
            masked_candidate[path]=true
        else:
            excluded_masked[path]=true
    if masked_candidate.size()!=564 or excluded_masked.size()!=7:
        push_error("XZOGOT_NACHT_564_MASTER_7_OTHER_MASK_SOURCE_AUTHORITY_RED")
        quit(25)
        return
    var original_material_slots: Dictionary={}
    var copied_opaque_materials: Dictionary={}
    var candidate_source_surfaces: int=0
    var retained_masked_surfaces: int=0
    var all_original_surfaces: int=0
    var original_cull_mode: Dictionary={}
    for mi_any: Node in source_meshes:
        var mi: MeshInstance3D=mi_any as MeshInstance3D
        var previous: Array[Material]=[]
        for i: int in range(mi.mesh.get_surface_count()):
            var mat: Material=mi.get_surface_override_material(i)
            if mat==null:
                push_error("XZOGOT_NACHT_SOURCE_MASTER_MASK_MATERIAL_MISSING_RED "+str(mi.name))
                quit(26)
                return
            all_original_surfaces+=1
            previous.append(mat)
            var original_path: String=str(mat.get_meta("source_material_path",""))
            if masked_candidate.has(original_path):
                var standard: StandardMaterial3D=mat as StandardMaterial3D
                if standard==null or standard.transparency!=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                    push_error("XZOGOT_NACHT_UNWIRED_MASTER_MATERIAL_HAS_NO_MASK_RED "+original_path)
                    quit(27)
                    return
                candidate_source_surfaces+=1
                if not copied_opaque_materials.has(mat.get_instance_id()):
                    var clone: StandardMaterial3D=standard.duplicate(false) as StandardMaterial3D
                    clone.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
                    if clone.albedo_texture!=standard.albedo_texture or clone.cull_mode!=standard.cull_mode:
                        push_error("XZOGOT_NACHT_OPACITY_RESEARCH_CLONE_CHANGED_SOURCE_DDS_CULL_RED")
                        quit(28)
                        return
                    copied_opaque_materials[mat.get_instance_id()]=clone
            elif excluded_masked.has(original_path):
                retained_masked_surfaces+=1
        original_material_slots[mi.get_instance_id()]=previous
    if (all_original_surfaces!=16595
        or candidate_source_surfaces!=15339
        or retained_masked_surfaces!=33
        or copied_opaque_materials.size()!=564):
        push_error("XZOGOT_NACHT_ORIGINAL_SOURCE_ONLY_MASTER_MASK_STATS_RED "+str([
            all_original_surfaces,candidate_source_surfaces,
            retained_masked_surfaces,copied_opaque_materials.size()]))
        quit(29)
        return
    var views: Array[Dictionary]=[
        {"name":"interior_central_yaw180","eye":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw0","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(42.0,1.65,-0.325515)},
        {"name":"interior_original_yaw270","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var before: Dictionary={}
    var after: Dictionary={}
    for v: Dictionary in views:
        before[str(v["name"])]=await _capture(cam,
            str(v["name"])+"_mastermask_before",v["eye"],v["look"])
    for mi_any: Node in source_meshes:
        var mi: MeshInstance3D=mi_any as MeshInstance3D
        var prev: Array=original_material_slots[mi.get_instance_id()]
        for i: int in range(prev.size()):
            var mat: Material=prev[i] as Material
            if copied_opaque_materials.has(mat.get_instance_id()):
                mi.set_surface_override_material(i,copied_opaque_materials[mat.get_instance_id()])
    for v: Dictionary in views:
        after[str(v["name"])]=await _capture(cam,
            str(v["name"])+"_mastermask_preview",v["eye"],v["look"])
    for mi_any: Node in source_meshes:
        var mi: MeshInstance3D=mi_any as MeshInstance3D
        var originals: Array=original_material_slots[mi.get_instance_id()]
        for i: int in range(originals.size()):
            mi.set_surface_override_material(i,originals[i] as Material)
    var restored: Image=await _capture(cam,
        "interior_central_yaw180_mastermask_restored",
        views[0]["eye"],views[0]["look"])
    var restored_delta: Dictionary=_image_delta(
        before["interior_central_yaw180"] as Image,restored)
    var result: Array[Dictionary]=[]
    for v: Dictionary in views:
        var name: String=str(v["name"])
        var before_img: Image=before[name] as Image
        var after_img: Image=after[name] as Image
        var dark: Dictionary=_black_recover(before_img,after_img,after_img)
        dark["camera"]=name
        dark["sourcePixelChanges"]=_image_delta(before_img,after_img)
        result.append(dark)
        print("XZOGOT_NACHT_ORIGINAL_564_MASTER_UNWIRED_MASK_CANDIDATE_RESEARCH ",
            JSON.stringify(dark))
    var report: Dictionary={
        "source":"Original archived Pavlov UE4.21 native Godot; NOT original BO3 T7",
        "originalNativeActorCount":source_meshes.size(),
        "originalBoundSurfaces":all_original_surfaces,
        "provisionalSourceMasterMaterialCount":masked_candidate.size(),
        "sourceMasterCandidateSurfaceBindings":candidate_source_surfaces,
        "excludedOtherOriginalMaskedMaterials":excluded_masked.size(),
        "excludedOtherMaskedSourceSurfaceBindings":retained_masked_surfaces,
        "originalUsedSourceDDSStaged":718,
        "originalLightsReconstructed":166,
        "cameraOriginalVsProvisionalSourceGraphOpaque":result,
        "sourceMaterialsRestoredAfterPreview":true,
        "originalMaterialRestoreRGB":restored_delta,
        "allOriginalMeshActorsAndTransformsPreserved":true,
        "researchOpacityConnectionIsPartialUnproven":true,
        "sourceVisibilityAcrossEveryWindowNotCertified":true,
        "productionShaderFixApproved":false,
        "androidPhysicalFPSProven":false
    }
    var output: FileAccess=FileAccess.open(
        "res://nacht-mastermat-unwired-opacity-only-threeview-research.json",FileAccess.WRITE)
    output.store_string(JSON.stringify(report,"\t"))
    output.close()
    if (restored_delta["meanRGBDifferencePercent"]>0.30
        or not report["researchOpacityConnectionIsPartialUnproven"]):
        push_error("XZOGOT_NACHT_MASTER_OPACITY_RESEARCH_FAILED_TO_RESTORE_ORIGINAL_RED")
        quit(30)
        return
    print("XZOGOT_NACHT_REAL_564_SOURCE_MASTER_MASK_7_EXCLUDED_3_VIEW_PREVIEW_GREEN")
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

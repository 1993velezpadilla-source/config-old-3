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
    # The original 11 frame 564-MasterMat experiment proved quartile #3
    # alone restored 15,323 central interior dark pixels (not shipping safe).
    # Now isolate just 141 group-3 original material PATHS (not opaque IDs).
    # Two halves are sorted original material identity: first 70, last 71.
    var candidate_master_paths: Array[String]=[]
    var non_master_original_masks: Array[String]=[]
    const MASTER: String=(
        "Content/CustomMaps/UGC2755515831/CoD_nacht/AssetsFolder/MasterMat.MasterMat")
    for source_material_any: Variant in bridge["materials"]:
        var record: Dictionary=source_material_any as Dictionary
        if str(record.get("blendMode",""))!="BLEND_Masked":
            continue
        var raw: Array=record.get("baseSourceRawPropertyNames",[]) as Array
        var bindings: Dictionary=record.get("sourceGraphBindings",{}) as Dictionary
        var unknown: Dictionary=record.get("sourceGraphUnresolvedOutputs",{}) as Dictionary
        var matching_master: bool=(
            str(record.get("semanticBaseMaterialPath",""))==MASTER
            and str(record.get("sourceGraphStatus",""))=="partial"
            and not raw.has("OpacityMask") and not bindings.has("OpacityMask")
            and not unknown.has("OpacityMask")
        )
        if matching_master:
            candidate_master_paths.append(str(record["materialPath"]))
        else:
            non_master_original_masks.append(str(record["materialPath"]))
    candidate_master_paths.sort()
    if candidate_master_paths.size()!=564 or non_master_original_masks.size()!=7:
        push_error("XZOGOT_NACHT_SOURCE_MASK_GROUP3_ORIGINAL_ARCHIVE_AUTHORITY_RED")
        quit(71)
        return
    var group3_paths: Array[String]=[]
    for i: int in range(candidate_master_paths.size()):
        if i%4==3:
            group3_paths.append(candidate_master_paths[i])
    if group3_paths.size()!=141:
        push_error("XZOGOT_NACHT_SOURCE_GROUP3_EXACT_141_AUTHORED_MATERIALS_RED")
        quit(72)
        return
    var source_half: Dictionary={}
    for i: int in range(group3_paths.size()):
        source_half[group3_paths[i]]=0 if i<70 else 1
    var source_counts: Array[int]=[0,0]
    var all_source_surface_bindings: int=0
    var original_slots: Array[Dictionary]=[]
    var clone_by_original: Dictionary={}
    var all_excluded_mask_paths: Dictionary={}
    for actor_any: Variant in bridge["actors"]:
        var row: Dictionary=actor_any as Dictionary
        var id: String=str(row["actorId"])
        var node: MeshInstance3D=by_actor.get(id,null) as MeshInstance3D
        var paths: Array=row["sourceMaterialPaths"] as Array
        if node==null or node.mesh==null or paths.size()!=node.mesh.get_surface_count():
            push_error("XZOGOT_NACHT_SOURCE_GROUP3_ACTOR_AUTHORITY_RED "+id)
            quit(73)
            return
        all_source_surface_bindings+=paths.size()
        for slot: int in range(paths.size()):
            var path: String=str(paths[slot])
            if not source_half.has(path):
                if non_master_original_masks.has(path):
                    all_excluded_mask_paths[path]=true
                continue
            var original: StandardMaterial3D=node.get_surface_override_material(slot) as StandardMaterial3D
            if original==null or original.transparency!=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                push_error("XZOGOT_NACHT_SOURCE_GROUP3_EXPECTED_ORIGINAL_MASK_RED "+path)
                quit(74)
                return
            var half: int=int(source_half[path])
            source_counts[half]+=1
            var pointer: int=original.get_instance_id()
            if not clone_by_original.has(pointer):
                var clone: StandardMaterial3D=original.duplicate(false) as StandardMaterial3D
                clone.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
                if (clone.albedo_texture!=original.albedo_texture
                    or clone.normal_texture!=original.normal_texture
                    or clone.cull_mode!=original.cull_mode
                    or clone.roughness!=original.roughness
                    or clone.shading_mode!=original.shading_mode):
                    push_error("XZOGOT_NACHT_SOURCE_GROUP3_ORIGINAL_DDS_OR_CULL_CHANGED_RED")
                    quit(75)
                    return
                clone_by_original[pointer]=clone
            original_slots.append({
                "node":node,"surface":slot,"sourceMaterial":path,
                "sourceHalf":half,"original":original,"opaque":clone_by_original[pointer]
            })
    if (all_source_surface_bindings!=16595 or source_counts[0]+source_counts[1]!=5068
        or original_slots.size()!=5068 or clone_by_original.size()!=141
        or all_excluded_mask_paths.size()!=7):
        push_error("XZOGOT_NACHT_SOURCE_GROUP3_SURFACE_COUNT_DRIFT_RED "+
            str([all_source_surface_bindings,source_counts,original_slots.size(),
            clone_by_original.size(),all_excluded_mask_paths.size()]))
        quit(76)
        return
    var camera: Vector3=Vector3(4.5,1.6,0.4)
    var aim: Vector3=Vector3(4.5,1.6,-30.0)
    var before: Image=await _capture(cam,"source_group3_twohalves_original",camera,aim)
    _set_group3_opaque_subset(original_slots,[0,1])
    var positive: Image=await _capture(cam,"source_group3_twohalves_all141_positive",camera,aim)
    var true_black: Dictionary=_black_recover(before,positive,positive)
    if (int(true_black["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"])<11000
        or int(true_black["originalNearBlackCenterROIPixels"])<50000):
        push_error("XZOGOT_NACHT_ORIGINAL_GROUP3_FULL_MASK_CONTROL_15323_NOT_REPRODUCED_RED "+
            JSON.stringify(true_black))
        quit(77)
        return
    var comparisons: Array[Dictionary]=[]
    for half: int in range(2):
        _set_group3_opaque_subset(original_slots,[half])
        var pic: Image=await _capture(cam,
            "source_group3_twohalves_only_"+str(half),camera,aim)
        var result: Dictionary={
            "sourceHalf":half,
            "originalSourceMaterialCount":70 if half==0 else 71,
            "originalSourceBindings":source_counts[half],
            "originalMaterialPaths":[],
            "darkROIOriginalVsOnlyThisHalf":_black_recover(before,pic,pic),
            "wholeScreenOriginalVsOnlyThisHalfRGB":_image_delta(before,pic)
        }
        for source_path: String in group3_paths:
            if int(source_half[source_path])==half:
                (result["originalMaterialPaths"] as Array).append(source_path)
        comparisons.append(result)
        print("XZOGOT_NACHT_GROUP3_ORIGINAL_HALF_RECOVERY ",JSON.stringify({
            "half":half,
            "originalSourceBindings":source_counts[half],
            "blackROI":result["darkROIOriginalVsOnlyThisHalf"]
        }))
    _set_group3_opaque_subset(original_slots,[])
    for row: Dictionary in original_slots:
        if (row["node"] as MeshInstance3D).get_surface_override_material(int(row["surface"]))!=row["original"]:
            push_error("XZOGOT_NACHT_SOURCE_GROUP3_SOURCE_MATERIAL_POINTER_RESTORE_RED")
            quit(78)
            return
    var restore: Image=await _capture(cam,
        "source_group3_twohalves_original_restored",camera,aim)
    var restored_delta: Dictionary=_image_delta(before,restore)
    var report: Dictionary={
        "source":"Original archived Pavlov UE4.21 Nacht reconstruction NOT official BO3 T7",
        "actualGodotRenderer":"4.6.1 Mesa OpenGL Compatibility NOT physical Android",
        "originalSourceMeshActors":by_actor.size(),
        "originalMaterialSurfaceBindings":all_source_surface_bindings,
        "originalSourceLightComponents":166,
        "originalUsedDDS":718,
        "originalSource564MasterMatAvailable":candidate_master_paths.size(),
        "originalSevenNonMasterMaskedProtected":all_excluded_mask_paths.size(),
        "quartile3OriginalSourceMaterialCount":group3_paths.size(),
        "quartile3OriginalSourceBoundSurfaces":original_slots.size(),
        "quartile3FullUnsafePositiveControlBlackROI":true_black,
        "twoOriginalMaterialHalves":comparisons,
        "allOriginalSourceMaterialPointersRestored":true,
        "originalRestoredViewportRGB":restored_delta,
        "shadersPartiallyRecoveredUEOpacityMaskOutputNotProven":true,
        "allSourceMeshesAndTexturesPreserved":true,
        "allWindowFoliageCutoutMasksNotApprovedOpaque":true,
        "productionMaterialShaderFixNotApproved":true,
        "allPlayerWindowViewsNotCertified":true,
        "phoneFPSVRAMNotMeasured":true
    }
    var output: FileAccess=FileAccess.open(
        "res://nacht-original-source-quartile3-twohalves-black-region.json",FileAccess.WRITE)
    output.store_string(JSON.stringify(report,"\t"))
    output.close()
    if restored_delta["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_SOURCE_GROUP3_AFTER_ROLLBACK_CHANGED_PIXELS_RED")
        quit(79)
        return
    print("XZOGOT_NACHT_ORIGINAL_SOURCE_QUARTILE3_TWOHALVES_FIVE_PNG_GREEN")
    quit(0)

func _set_group3_opaque_subset(rows: Array[Dictionary],enabled: Array[int]) -> void:
    for row: Dictionary in rows:
        var next_mat: Material=row["original"] as Material
        if enabled.has(int(row["sourceHalf"])):
            next_mat=row["opaque"] as Material
        (row["node"] as MeshInstance3D).set_surface_override_material(
            int(row["surface"]),next_mat)

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

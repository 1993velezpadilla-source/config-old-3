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
    # Diagnostic: source 574-material alpha-scissor 4-way isolation.
    # Positive all-564 control MUST recover the known interior dark pixels.
    # Unlike the color-coded opacity pass, this measures visible source
    # original albedo/material changes with ALL OTHER source materials intact.
    const MASTER: String=(
        "Content/CustomMaps/UGC2755515831/CoD_nacht/AssetsFolder/MasterMat.MasterMat")
    var source_paths: Array[String]=[]
    var rejected_masked: Array[String]=[]
    for material_any: Variant in bridge["materials"]:
        var m: Dictionary=material_any as Dictionary
        if str(m.get("blendMode",""))!="BLEND_Masked":
            continue
        var linked: Dictionary=m.get("sourceGraphBindings",{}) as Dictionary
        var unresolved: Dictionary=m.get("sourceGraphUnresolvedOutputs",{}) as Dictionary
        var raw: Array=m.get("baseSourceRawPropertyNames",[]) as Array
        var path: String=str(m["materialPath"])
        var candidate: bool=(
            str(m.get("semanticBaseMaterialPath",""))==MASTER
            and not linked.has("OpacityMask")
            and not unresolved.has("OpacityMask")
            and not raw.has("OpacityMask")
            and str(m.get("sourceGraphStatus",""))=="partial"
        )
        if candidate:
            source_paths.append(path)
        else:
            rejected_masked.append(path)
    source_paths.sort()
    if source_paths.size()!=564 or rejected_masked.size()!=7:
        push_error("XZOGOT_NACHT_FOUR_GROUP_UNTRUSTED_MASK_SOURCE_CENSUS_RED "+
            str([source_paths.size(),rejected_masked.size()]))
        quit(61)
        return
    var partition_lookup: Dictionary={}
    for i: int in range(source_paths.size()):
        partition_lookup[source_paths[i]]=i%4
    var stage: Array[Dictionary]=[]
    var clones: Dictionary={}
    var counts: Array[int]=[0,0,0,0]
    var source_bound_surfaces: int=0
    var distinct_rejected_mask_source: Dictionary={}
    for actor_any: Variant in bridge["actors"]:
        var actor: Dictionary=actor_any as Dictionary
        var actor_id: String=str(actor["actorId"])
        var mi: MeshInstance3D=by_actor.get(actor_id,null) as MeshInstance3D
        var mat_paths: Array=actor["sourceMaterialPaths"] as Array
        if mi==null or mi.mesh.get_surface_count()!=mat_paths.size():
            push_error("XZOGOT_NACHT_FOUR_GROUP_NATIVE_SOURCE_SLOT_COUNT_RED "+actor_id)
            quit(62)
            return
        source_bound_surfaces+=mat_paths.size()
        for slot: int in range(mat_paths.size()):
            var material_path: String=str(mat_paths[slot])
            var old: StandardMaterial3D=mi.get_surface_override_material(slot) as StandardMaterial3D
            if old==null:
                push_error("XZOGOT_NACHT_FOUR_GROUP_ORIGINAL_BOUND_MATERIAL_MISSING_RED")
                quit(63)
                return
            if not partition_lookup.has(material_path):
                if rejected_masked.has(material_path):
                    distinct_rejected_mask_source[material_path]=true
                continue
            if old.transparency!=BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                push_error("XZOGOT_NACHT_FOUR_GROUP_ORIGINAL_SOURCE_NOT_MASKED_RED "+material_path)
                quit(64)
                return
            var index: int=int(partition_lookup[material_path])
            counts[index]+=1
            var key: int=old.get_instance_id()
            if not clones.has(key):
                var clone: StandardMaterial3D=old.duplicate(false) as StandardMaterial3D
                clone.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
                if (clone.albedo_texture!=old.albedo_texture or
                    clone.normal_texture!=old.normal_texture or
                    clone.cull_mode!=old.cull_mode or
                    clone.roughness!=old.roughness or
                    clone.shading_mode!=old.shading_mode):
                    push_error("XZOGOT_NACHT_FOUR_GROUP_SOURCE_DDS_CHANGED_RED")
                    quit(65)
                    return
                clones[key]=clone
            stage.append({"node":mi,"slot":slot,"original":old,
                "opaque":clones[key],"partition":index,"materialPath":material_path})
    if (source_bound_surfaces!=16595 or stage.size()!=15339
        or clones.size()!=564 or distinct_rejected_mask_source.size()!=7):
        push_error("XZOGOT_NACHT_FOUR_GROUP_ORIGINAL_MATERIAL_AUTHORITY_RED "+
            str([source_bound_surfaces,stage.size(),clones.size(),
            distinct_rejected_mask_source.size()]))
        quit(66)
        return
    var eye: Vector3=Vector3(4.5,1.6,0.4)
    var target: Vector3=Vector3(4.5,1.6,-30.0)
    var original: Image=await _capture(cam,"black_partition_original_source",eye,target)
    _mask_four_partition_override(stage,[0,1,2,3])
    var broad: Image=await _capture(cam,"black_partition_all_564_unsafe_positive_control",eye,target)
    var broad_recovered: Dictionary=_black_recover(original,broad,broad)
    if int(broad_recovered["blackRecoveredByDisablingOnlyDiffuseAlphaScissor"])<5000:
        push_error("XZOGOT_NACHT_FOUR_GROUP_ORIGINAL_BROAD_POSITIVE_CONTROL_NO_BLACK_REPAIR_RED "+
            JSON.stringify(broad_recovered))
        quit(67)
        return
    var results: Array[Dictionary]=[]
    # Two complementary experiments for each original UE material quartile.
    # "alone" measures whether that group is sufficient to fill black walls.
    # "all_except" detects whether that group was required when others fill.
    for group: int in range(4):
        _mask_four_partition_override(stage,[group])
        var alone: Image=await _capture(cam,
            "black_partition_only_group_"+str(group),eye,target)
        _mask_four_partition_override(stage,[
            (group+1)%4,(group+2)%4,(group+3)%4])
        var except: Image=await _capture(cam,
            "black_partition_all_except_group_"+str(group),eye,target)
        var entry: Dictionary={
            "sourcePartition":group,
            "nativeSourceMaterialsInPartition":141,
            "originalSourceSurfaceBindingsInPartition":counts[group],
            "oneOfFourOnlyBlackROI":_black_recover(original,alone,alone),
            "oneOfFourOnlyWholeImageRGB":_image_delta(original,alone),
            "allOtherThreePartitionsBlackROI":_black_recover(original,except,except),
            "allOtherThreePartitionsWholeImageRGB":_image_delta(original,except),
            "originalMaterialPathsInPartition":[]
        }
        for path: String in source_paths:
            if int(partition_lookup[path])==group:
                (entry["originalMaterialPathsInPartition"] as Array).append(path)
        results.append(entry)
        print("XZOGOT_NACHT_ORIGINAL_MATERIAL_MASK_SOURCE_QUARTILE_FORENSIC ",
            JSON.stringify({
                "sourcePartition":entry["sourcePartition"],
                "originalSourceSurfaceBindingsInPartition":entry["originalSourceSurfaceBindingsInPartition"],
                "oneOfFourOnlyBlackROI":entry["oneOfFourOnlyBlackROI"],
                "allOtherThreePartitionsBlackROI":entry["allOtherThreePartitionsBlackROI"]
            }))
    _mask_four_partition_override(stage,[])
    for entry: Dictionary in stage:
        if (entry["node"] as MeshInstance3D).get_surface_override_material(
            int(entry["slot"]))!=entry["original"]:
            push_error("XZOGOT_NACHT_FOUR_GROUP_ORIGINAL_RESOURCE_POINTER_RESTORE_RED")
            quit(68)
            return
    var restored: Image=await _capture(cam,
        "black_partition_original_source_restored",eye,target)
    var restore_rgb: Dictionary=_image_delta(original,restored)
    var report: Dictionary={
        "source":"archived Pavlov UE4.21 reconstructed Nacht, NOT original BO3 T7",
        "actualRenderer":"Godot 4.6.1 OpenGL Compatibility Mesa, NOT physical Android",
        "fullOriginalActors":by_actor.size(),
        "fullOriginalSurfaceBindings":source_bound_surfaces,
        "allOriginalUsedDDSTextureImages":718,
        "UE421SourceLightComponents":166,
        "sourceMaskedMasterMaterialCount":source_paths.size(),
        "sourceMaskedMasterSurfaceBindings":stage.size(),
        "excludedOriginalOtherMaskedMaterials":rejected_masked,
        "quartileSourceOriginalSurfaceBindings":counts,
        "originalDarkROI":_black_recover(original,original,original),
        "unsafeBroad564PositiveControlROI":broad_recovered,
        "unsafeBroad564PositiveControlRGB":_image_delta(original,broad),
        "fourSourceQuartileAloneAndLeaveOneOutResults":results,
        "originalMaterialResourcesRestoredExactly":true,
        "originalRenderedRestorationRGB":restore_rgb,
        "UEOpacityMaskGraphPartiallyReconstructedNotProven":true,
        "noSourceMeshDDSTexturesTransformedOrDeleted":true,
        "noWindowFoliageTransparentCardsApprovedToBecomeOpaque":true,
        "allOtherSourceMaterialsUntouched":true,
        "productionShipApproved":false,
        "everyPlayerEyeWindowViewCertified":false,
        "realMobileFPSOrThermalsUnmeasured":true
    }
    var out: FileAccess=FileAccess.open(
        "res://nacht-source-564-masked-material-four-quartile-positive-control-black-wall.json",
        FileAccess.WRITE)
    out.store_string(JSON.stringify(report,"\t"))
    out.close()
    if restore_rgb["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_FOUR_GROUP_ORIGINAL_FINAL_RGB_RESTORE_RED "+JSON.stringify(restore_rgb))
        quit(69)
        return
    print("XZOGOT_NACHT_SOURCE_564_MASTER_MASK_FOUR_PARTITION_REAL_IMAGE_BINARY_DIAG_GREEN")
    quit(0)

func _mask_four_partition_override(stage: Array[Dictionary],enabled: Array[int]) -> void:
    for entry: Dictionary in stage:
        var material: Material=entry["original"] as Material
        if enabled.has(int(entry["partition"])):
            material=entry["opaque"] as Material
        (entry["node"] as MeshInstance3D).set_surface_override_material(
            int(entry["slot"]),material)

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

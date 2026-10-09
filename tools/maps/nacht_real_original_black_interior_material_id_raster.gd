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
    # Forensics: EXACT source material ID raster. Black pixels are NOT mapped
    # via guessed material names. Two 6-bit-per-frame categorical encodings
    # encode all 574 original material paths in only 2 captures per camera.
    # Opaque unshaded override is TEMPORARY; never a shipping shader change.
    var names: Array[String]=[]
    var record_by_path: Dictionary={}
    for mat_any: Variant in bridge["materials"]:
        var row: Dictionary=mat_any as Dictionary
        var source_path: String=str(row["materialPath"])
        if record_by_path.has(source_path):
            push_error("XZOGOT_NACHT_BLACK_MATERIAL_OWNER_SOURCE_DUPLICATE_PATH_RED")
            quit(41)
            return
        record_by_path[source_path]=row
        names.append(source_path)
    names.sort()
    if names.size()!=574 or by_actor.size()!=10793:
        push_error("XZOGOT_NACHT_BLACK_MATERIAL_OWNER_ORIGINAL_SCENE_AUTHORITY_RED")
        quit(42)
        return
    var id_by_path: Dictionary={}
    var palette_report: Array[Dictionary]=[]
    for idx: int in range(names.size()):
        var name: String=names[idx]
        id_by_path[name]=idx+1
        palette_report.append({
            "sourceMaterialID":idx+1,
            "originalSourceMaterialPath":name,
            "sourceUEBlendMode":str((record_by_path[name] as Dictionary).get("blendMode","")),
            "sourceUEGraphStatus":str((record_by_path[name] as Dictionary).get("sourceGraphStatus",""))
        })
    var saved: Array[Dictionary]=[]
    var observed_source_surfaces: int=0
    var original_masks: int=0
    var original_backface: int=0
    var source_surface_counts: Dictionary={}
    for actor_any: Variant in bridge["actors"]:
        var actor: Dictionary=actor_any as Dictionary
        var actor_id: String=str(actor["actorId"])
        var mi: MeshInstance3D=by_actor.get(actor_id,null) as MeshInstance3D
        if mi==null or mi.mesh==null:
            push_error("XZOGOT_NACHT_BLACK_OWNER_ACTOR_MISSING_RED "+actor_id)
            quit(43)
            return
        var paths: Array=actor["sourceMaterialPaths"] as Array
        if paths.size()!=mi.mesh.get_surface_count():
            push_error("XZOGOT_NACHT_BLACK_OWNER_NATIVE_MESH_SOURCE_MATERIAL_COUNT_RED "+actor_id)
            quit(44)
            return
        for surface: int in range(paths.size()):
            var original: StandardMaterial3D=mi.get_surface_override_material(surface) as StandardMaterial3D
            if original==null:
                push_error("XZOGOT_NACHT_BLACK_OWNER_ORIGINAL_NATIVE_MATERIAL_UNAVAILABLE_RED")
                quit(45)
                return
            var path: String=str(paths[surface])
            if not id_by_path.has(path):
                push_error("XZOGOT_NACHT_BLACK_OWNER_ORIGINAL_SOURCE_MATERIAL_KEY_MISSING_RED "+path)
                quit(46)
                return
            if original.transparency==BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                original_masks+=1
            if original.cull_mode==BaseMaterial3D.CULL_BACK:
                original_backface+=1
            observed_source_surfaces+=1
            source_surface_counts[path]=int(source_surface_counts.get(path,0))+1
            saved.append({
                "node":mi, "surface":surface, "original":original,
                "sourceMaterialID":int(id_by_path[path])
            })
    if saved.size()!=16595 or observed_source_surfaces!=16595:
        push_error("XZOGOT_NACHT_BLACK_OWNER_MATERIAL_STAGE_COUNT_RED "+str(saved.size()))
        quit(47)
        return
    var cams: Array[Dictionary]=[
        {"name":"interior_central_yaw180","eye":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw270","eye":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var original_pixels: Dictionary={}
    var presence: Dictionary={}
    var encoded_low: Dictionary={}
    var encoded_high: Dictionary={}
    for c: Dictionary in cams:
        original_pixels[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_real_original_source_material",
            c["eye"],c["look"])
    # A solid unlit all-white source raster marks where actual geometry exists;
    # it must NEVER be counted as a production material fix.
    var white: StandardMaterial3D=_id_debug_solid(Color(1.0,1.0,1.0))
    for entry: Dictionary in saved:
        (entry["node"] as MeshInstance3D).set_surface_override_material(
            int(entry["surface"]),white)
    for c: Dictionary in cams:
        presence[str(c["name"])]=await _capture(cam,
            str(c["name"])+"_original_source_solid_presence",
            c["eye"],c["look"])
    # Each separate frame encodes a 6-bit base4 RGB word (64 combinations).
    # Two native views = 12-bit ID capacity. Original material ID must be
    # reverse-looked-up from the exact source authority manifest.
    var colors: Array[float]=[0.22,0.44,0.67,0.90]
    for digit_group: int in range(2):
        var clones: Dictionary={}
        for idx: int in range(1,575):
            var digit_code: int=idx if digit_group==0 else (idx/64)
            digit_code=idx%64 if digit_group==0 else int(idx/64)
            var r: float=colors[digit_code%4]
            var g: float=colors[int(digit_code/4)%4]
            var b: float=colors[int(digit_code/16)%4]
            clones[idx]=_id_debug_solid(Color(r,g,b))
        for entry: Dictionary in saved:
            (entry["node"] as MeshInstance3D).set_surface_override_material(
                int(entry["surface"]),clones[entry["sourceMaterialID"]] as Material)
        for c: Dictionary in cams:
            var name: String=str(c["name"])
            if digit_group==0:
                encoded_low[name]=await _capture(cam,name+"_original_material_id_low6",
                    c["eye"],c["look"])
            else:
                encoded_high[name]=await _capture(cam,name+"_original_material_id_high6",
                    c["eye"],c["look"])
    for entry: Dictionary in saved:
        var mi: MeshInstance3D=entry["node"] as MeshInstance3D
        mi.set_surface_override_material(
            int(entry["surface"]),entry["original"] as Material)
        if mi.get_surface_override_material(int(entry["surface"]))!=entry["original"]:
            push_error("XZOGOT_NACHT_BLACK_OWNER_ORIGINAL_POINTER_RESTORE_RED")
            quit(48)
            return
    var restored: Image=await _capture(cam,
        "interior_central_yaw180_original_shader_restore_control",
        cams[0]["eye"],cams[0]["look"])
    var delta: Dictionary=_image_delta(
        original_pixels["interior_central_yaw180"] as Image,restored)
    var counts: Array[Dictionary]=[]
    for path: String in names:
        counts.append({
            "sourceMaterialID":int(id_by_path[path]),
            "sourceOriginalMaterialPath":path,
            "originalSourceSurfaceBindings":int(source_surface_counts.get(path,0))
        })
    var result: Dictionary={
        "source":"Pavlov UE4.21 original archived scene NOT authentic BO3 T7",
        "originalSourceActorCount":by_actor.size(),
        "originalSourceSurfaceBindings":observed_source_surfaces,
        "originalDistinctEffectiveMaterials":names.size(),
        "originalSourceAlphaScissorSurfaces":original_masks,
        "originalSourceBackfaceCullingSurfaces":original_backface,
        "originalLightCount":166,
        "originalUsedDDS":718,
        "nativeRealOriginalEyeCameraNames":[cams[0]["name"],cams[1]["name"]],
        "materialIdCodec":"base4_rgb_two_frames_0.22_0.44_0.67_0.90",
        "sourceMaterialIDLookup":palette_report,
        "sourceMaterialOriginalSurfaceCounts":counts,
        "originalShaderMaterialPointersFullyRestored":true,
        "originalRestoredViewportMeanRGBDifference":delta,
        "allSourceTexturesAndOriginalMeshesUntouched":true,
        "sourceOpaqueIDPassDiagnosticOnly":true,
        "originalMaskedOpacityUnresolved":true,
        "actualRenderedBlackWallOwnerPendingIndependentPNGPixelDecode":true,
        "everyPlayableWindowOrInteriorPositionCertified":false,
        "physicalAndroidFPSMeasured":false,
        "productionBlackWallFixApproved":false
    }
    var file: FileAccess=FileAccess.open(
        "res://nacht-black-interior-original-source-per-material-id-raster.json",
        FileAccess.WRITE)
    file.store_string(JSON.stringify(result,"\t"))
    file.close()
    if delta["meanRGBDifferencePercent"]>0.30:
        push_error("XZOGOT_NACHT_BLACK_ORIGINAL_SOURCE_RESTORATION_RGB_RED")
        quit(49)
        return
    print("XZOGOT_NACHT_REAL_ORIGINAL_SOURCE_574_MATERIAL_ID_BLACK_WALL_TWO_FRAME_RASTER_GREEN")
    quit(0)

func _id_debug_solid(color: Color) -> StandardMaterial3D:
    var mat: StandardMaterial3D=StandardMaterial3D.new()
    mat.albedo_color=color
    mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
    mat.cull_mode=BaseMaterial3D.CULL_DISABLED
    return mat

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

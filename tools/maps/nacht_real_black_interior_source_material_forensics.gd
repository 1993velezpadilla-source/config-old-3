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
    # Source engine original reconstruction with 718 staged DDS; evaluate
    # three EXACT original source-player-eye cameras before any Vista batching.
    # Do not claim source actor locations are proven playable navmesh.
    var points: Array[Dictionary]=[
        {"name":"interior_central_yaw180","camera":Vector3(4.5,1.6,0.4),
         "look":Vector3(4.5,1.6,-30.0)},
        {"name":"interior_original_yaw0","camera":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(42.0,1.65,-0.325515)},
        {"name":"interior_original_yaw270","camera":Vector3(11.61863,1.65,-0.325515),
         "look":Vector3(11.61863,1.65,-30.0)}
    ]
    var original: Dictionary={}
    var no_cull: Dictionary={}
    var solid: Dictionary={}
    var original_materials: Dictionary={}
    var actor_interior_slots: int=0
    var distinct_interior_materials: Dictionary={}
    var original_missing_albedo_surfaces: int=0
    var source_alpha_masked_surfaces: int=0
    var native_backface_culling_surfaces: int=0
    var cube_details: Array[Dictionary]=[]
    for mesh_any: Node in source_meshes:
        var node: MeshInstance3D=mesh_any as MeshInstance3D
        var name_raw: String=str(node.name)
        var cut: int=name_raw.find("_native_exact_")
        var id: String=name_raw.substr(0,cut)
        if id=="ue_instance_000004" or id=="ue_instance_000005":
            var bound: AABB=node.global_transform*node.mesh.get_aabb()
            cube_details.append({
                "originalSourceActorID":id,
                "originalWorldBoundsCenter":str(bound.get_center()),
                "originalWorldBoundsSize":str(bound.size),
                "originalSourceMeshIndex":492,
                "actualBoundOriginalMaterialPaths":["xziel://ue/default-surface"]
            })
        var center: Vector3=(node.global_transform*node.mesh.get_aabb()).get_center()
        if center.distance_to(Vector3(-2.494789,1.65,-7.258049))>55.0:
            continue
        for surface: int in range(node.mesh.get_surface_count()):
            var mat: StandardMaterial3D=node.get_surface_override_material(surface) as StandardMaterial3D
            if mat==null:
                push_error("XZOGOT_NACHT_BLACK_ORIGINAL_INTERIOR_MATERIAL_UNBOUND_RED "+id)
                quit(25)
                return
            actor_interior_slots+=1
            distinct_interior_materials[mat.get_instance_id()]=true
            if mat.albedo_texture==null:
                original_missing_albedo_surfaces+=1
            if mat.transparency==BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR:
                source_alpha_masked_surfaces+=1
            if mat.cull_mode==BaseMaterial3D.CULL_BACK:
                native_backface_culling_surfaces+=1
    for view: Dictionary in points:
        original[str(view["name"])]=await _capture(cam,str(view["name"])+"_original",
            view["camera"],view["look"])
    # Stage 2: replace only current materials with identical cloned UE-derived
    # DDS mappings but disable cull. Changes here are ephemeral diagnostics.
    var no_cull_cache: Dictionary={}
    for mesh_any: Node in source_meshes:
        var node: MeshInstance3D=mesh_any as MeshInstance3D
        var prev: Array[Material]=[]
        for i: int in range(node.mesh.get_surface_count()):
            var mat: Material=node.get_surface_override_material(i)
            prev.append(mat)
            if not (mat is StandardMaterial3D):
                continue
            var key: int=mat.get_instance_id()
            if not no_cull_cache.has(key):
                var copied: StandardMaterial3D=(mat as StandardMaterial3D).duplicate(false) as StandardMaterial3D
                copied.cull_mode=BaseMaterial3D.CULL_DISABLED
                no_cull_cache[key]=copied
            node.set_surface_override_material(i,no_cull_cache[key])
        original_materials[node.get_instance_id()]=prev
    for view: Dictionary in points:
        no_cull[str(view["name"])]=await _capture(cam,str(view["name"])+"_nocull",
            view["camera"],view["look"])
    # Stage 3: debug all true source geometry with opaque, unshaded categorical
    # geometry colors. Black portions remaining despite this change are either
    # true scene gaps, blocked by some earlier face, or background—not merely
    # alpha-scissor or unlit diffuse texture. Only temporary debug overrides.
    var texture_debug: StandardMaterial3D=_debug_material(Color(0.12,0.86,0.30))
    var untextured_debug: StandardMaterial3D=_debug_material(Color(1.0,0.06,0.62))
    var source_alpha_debug: StandardMaterial3D=_debug_material(Color(0.05,0.72,1.0))
    var diagnostic_debug_surfaces: int=0
    for mesh_any: Node in source_meshes:
        var node: MeshInstance3D=mesh_any as MeshInstance3D
        for i: int in range(node.mesh.get_surface_count()):
            var mat: StandardMaterial3D=(original_materials[node.get_instance_id()] as Array)[i] as StandardMaterial3D
            var debug: Material=texture_debug
            if mat==null or mat.albedo_texture==null:
                debug=untextured_debug
            elif mat.transparency!=BaseMaterial3D.TRANSPARENCY_DISABLED:
                debug=source_alpha_debug
            node.set_surface_override_material(i,debug)
            diagnostic_debug_surfaces+=1
    if diagnostic_debug_surfaces!=16595:
        push_error("XZOGOT_NACHT_BLACK_FULL_SOURCE_SURFACE_COLOR_DIAG_AUDIT_RED "+str(diagnostic_debug_surfaces))
        quit(26)
        return
    for view: Dictionary in points:
        solid[str(view["name"])]=await _capture(cam,str(view["name"])+"_source_geometry_solid",
            view["camera"],view["look"])
    var cases: Array[Dictionary]=[]
    for view: Dictionary in points:
        var name: String=str(view["name"])
        var report: Dictionary=_black_roi(
            original[name] as Image,no_cull[name] as Image,solid[name] as Image)
        report["cameraName"]=name
        report["cameraWorldPosition"]=str(view["camera"])
        report["cameraLookTarget"]=str(view["look"])
        cases.append(report)
        print("XZOGOT_NACHT_BLACK_INTERIOR_SOURCE_REAL_3_STAGE_PIXELS ",JSON.stringify(report))
    var report: Dictionary={
        "scene":"Full archived 10793 Pavlov UE4.21 source nodes; NOT BO3 T7",
        "renderer":"Godot 4.6.1 actual Mesa OpenGL Compatibility; NOT physical Android",
        "sourceActors":source_meshes.size(),
        "materialSurfaceBindings":surfaces,
        "originalUE421SourceLights":166,
        "originalUsedDDSTextureImagesStaged":718,
        "interiorCenterWithin55mOriginalSurfaces":actor_interior_slots,
        "distinctActualGodotNearInteriorMaterialResources":distinct_interior_materials.size(),
        "interiorSurfacesWithoutAlbedoDDS":original_missing_albedo_surfaces,
        "interiorMaskedMaterialSurfaces":source_alpha_masked_surfaces,
        "interiorBackfaceCullingSurfaces":native_backface_culling_surfaces,
        "originalDefaultCubeActorIDsAndActualBounds":cube_details,
        "independentInteriorSourceCameraCases":cases,
        "diagnosticMaterialTintIsNotShippingShaderFix":true,
        "originalMeshesActorTransformsAndMaterialResourcesPreserved":true,
        "noPermanentSourceGeometryDeletion":true,
        "noPlayable360OrThroughWindowsCertification":true,
        "physicalAndroidFpsAndVRAMUnmeasured":true,
        "blackInteriorArtFidelityStillUnproven":true,
        "approvedToShip":false
    }
    var file: FileAccess=FileAccess.open("res://nacht-black-interior-source-provenance-3-stage.json",FileAccess.WRITE)
    file.store_string(JSON.stringify(report,"\t"))
    file.close()
    if actor_interior_slots<=200 or cube_details.size()!=2 or cases.size()!=3:
        push_error("XZOGOT_NACHT_BLACK_SOURCE_REAL_SCENE_FIDELITY_TRIAGE_MISSING_RED")
        quit(27)
        return
    print("XZOGOT_NACHT_REAL_SOURCE_BLACK_INTERIOR_ORIGINAL_NOCULL_SOLID_VISUAL_DIAGNOSTIC_GREEN")
    quit(0)

func _debug_material(color: Color) -> StandardMaterial3D:
    var mat: StandardMaterial3D=StandardMaterial3D.new()
    mat.albedo_color=color
    mat.shading_mode=BaseMaterial3D.SHADING_MODE_UNSHADED
    mat.cull_mode=BaseMaterial3D.CULL_DISABLED
    mat.transparency=BaseMaterial3D.TRANSPARENCY_DISABLED
    return mat

func _black_roi(original: Image,nocull: Image,solid: Image) -> Dictionary:
    var w: int=original.get_width()
    var h: int=original.get_height()
    var orig_black: int=0
    var rescued_cull: int=0
    var rescued_material: int=0
    var still_black: int=0
    var orig_flat_gray: int=0
    var roi_pixels: int=0
    for y: int in range(int(h*0.12),int(h*0.88)):
        for x: int in range(int(w*0.15),int(w*0.85)):
            var a: Color=original.get_pixel(x,y)
            var b: Color=nocull.get_pixel(x,y)
            var c: Color=solid.get_pixel(x,y)
            var dark: bool=maxf(a.r,maxf(a.g,a.b))<0.045
            roi_pixels+=1
            if (absf(a.r-a.g)<0.025 and absf(a.g-a.b)<0.025
                    and a.r>0.22 and a.r<0.64):
                orig_flat_gray+=1
            if not dark:
                continue
            orig_black+=1
            if maxf(b.r,maxf(b.g,b.b))>=0.08:
                rescued_cull+=1
            elif maxf(c.r,maxf(c.g,c.b))>=0.08:
                rescued_material+=1
            else:
                still_black+=1
    return {
        "resolution":[w,h],
        "interiorCenterROI":[0.15,0.12,0.85,0.88],
        "ROIAnalyzedPixels":roi_pixels,
        "originalNearBlackPixels":orig_black,
        "originalNearlyFlatGrayPixels":orig_flat_gray,
        "originalDarkPixelsChangedByDisablingSourceBackfaceCulling":rescued_cull,
        "originalDarkPixelsChangedByFullOpaqueCategoricalGeometryMaterial":rescued_material,
        "originalDarkPixelsStillBlackEvenWithSolidUnshadedNoCullDebug":still_black,
        "stillBlackMayBeTrueGeometryOrVoidNotCertified":true,
        "noNativeSourceMeshAssetsWereModified":true
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

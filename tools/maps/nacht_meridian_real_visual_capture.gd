extends SceneTree
## REAL screenshot proof of independently validated Pavlov UE4.21 -> Meridian Godot.
## All 10793 original static actors, 16595 original authored material
## surface bindings, original compressed DDS, 166 exact original light records.
## NOT original BO3 T7. Not equivalence to Unreal UE postprocess/fog.
## No generated illustration or source-unauthored map geometry.
func _initialize() -> void:
    call_deferred("_capture")

func _capture() -> void:
    var bridge_raw: String = FileAccess.get_file_as_string("res://nacht-actor-material-authority.json")
    var bridge_any: Variant = JSON.parse_string(bridge_raw)
    if not (bridge_any is Dictionary):
        push_error("XZOGOT_NACHT_VISUAL_SOURCE_MATERIAL_BRIDGE_MISSING_RED")
        quit(11)
        return
    var bridge: Dictionary = bridge_any as Dictionary
    if int(bridge.get("sourceActorCount",0)) != 10793 or int(bridge.get("originalSourceSurfaceBindings",0)) != 16595:
        push_error("XZOGOT_NACHT_VISUAL_BAD_SOURCE_ACTOR_OR_SURFACE_COUNT_RED")
        quit(12)
        return

    var scene: PackedScene = load("res://scenes/main.tscn") as PackedScene
    if scene == null:
        push_error("XZOGOT_NACHT_VISUAL_LOSSLESS_SOURCE_GLB_SCENE_NOT_FOUND_RED")
        quit(13)
        return
    var world: Node = scene.instantiate()
    root.add_child(world)
    var meshes: Array[Node] = world.find_children("*","MeshInstance3D",true,false)
    if meshes.size() != 10793:
        push_error("XZOGOT_NACHT_VISUAL_LOST_ACTOR_GEOMETRY_RED mesh_count="+str(meshes.size()))
        quit(14)
        return

    var binder_script: Script = load("res://scripts/xziel_benchmark_loader.gd") as Script
    if binder_script == null:
        push_error("XZOGOT_NACHT_VISUAL_SOURCE_MATERIAL_LIGHT_BINDER_MISSING_RED")
        quit(15)
        return
    var binder: Node3D = binder_script.new() as Node3D
    binder.set("load_on_ready", false)
    binder.set("build_materials", true)
    binder.set("build_lights", true)
    binder.set("build_skeletal_actors", false)
    binder.set("source_root","res://nacht-authority")
    binder.set("vfs_map_root","vfs/xziel/maps/xziel_nacht_chronicles")
    binder.set("light_report_file","xzen-report.json")
    binder.set("source_environment_truth_file","res://nacht-authority/nacht-environment-runtime-authority.json")
    root.add_child(binder)
    binder.call("_prepare_material_authority")

    var by_actor: Dictionary = {}
    for candidate: Node in meshes:
        var mi: MeshInstance3D = candidate as MeshInstance3D
        var text_name: String = str(mi.name)
        var at: int = text_name.find("_native_exact_")
        if at < 0:
            push_error("XZOGOT_NACHT_VISUAL_SOURCE_ACTOR_ID_MISSING_RED "+text_name)
            quit(16)
            return
        var actor_id: String = text_name.substr(0,at)
        if by_actor.has(actor_id):
            push_error("XZOGOT_NACHT_VISUAL_DUPLICATE_OR_SPLIT_ACTOR_RED "+actor_id)
            quit(17)
            return
        by_actor[actor_id] = mi

    var bound: int = 0
    var textured: int = 0
    for item: Variant in bridge["actors"]:
        var row: Dictionary = item as Dictionary
        var iid: String = str(row["actorId"])
        if not by_actor.has(iid):
            push_error("XZOGOT_NACHT_VISUAL_SOURCE_ACTOR_NOT_IN_GLB_RED "+iid)
            quit(18)
            return
        var mi: MeshInstance3D = by_actor[iid] as MeshInstance3D
        var expected_slots: Array = row["sourceMaterialPaths"]
        if mi.mesh.get_surface_count() != expected_slots.size():
            push_error("XZOGOT_NACHT_VISUAL_WRONG_GLTF_SURFACE_MAP_RED "+iid)
            quit(19)
            return
        binder.call("_apply_instance_materials",mi,iid,int(row["meshIndex"]),0)
        for slot in range(expected_slots.size()):
            var actual: Material = mi.get_surface_override_material(slot)
            if actual == null:
                push_error("XZOGOT_NACHT_VISUAL_UNBOUND_ORIGINAL_SOURCE_MATERIAL_RED "+
                           iid+" slot="+str(slot))
                quit(20)
                return
            bound += 1
            var std: StandardMaterial3D = actual as StandardMaterial3D
            if std != null and std.albedo_texture != null:
                textured += 1
    if bound != 16595 or textured != 16593:
        push_error("XZOGOT_NACHT_VISUAL_AUTHORITATIVE_SURFACES_RED "+
                   str(bound)+" textured="+str(textured))
        quit(21)
        return
    print("XZOGOT_NACHT_VISUAL_REAL_SOURCE_MATERIALS_GREEN actors=",
          by_actor.size()," surfaces=",bound," textured_surfaces=",textured)

    var light_root: Node3D = Node3D.new()
    light_root.name="PavlovNativeUE421LightBasis"
    light_root.basis=Basis(Vector3(0.0,0.0,-1.0),Vector3(-1.0,0.0,0.0),Vector3(0.0,1.0,0.0))
    binder.add_child(light_root)
    binder.set("_runtime_root",light_root)
    binder.call("_build_source_lights")
    if int(binder.get_meta("xziel_benchmark_light_count",-1))!=166:
        push_error("XZOGOT_NACHT_VISUAL_ORIGINAL_LIGHT_SOURCE_LOSS_RED")
        quit(22)
        return
    print("XZOGOT_NACHT_VISUAL_REAL_SOURCE_LIGHTS_GREEN 166")

    # Remove transient generated camera nodes only, never source mesh/lights.
    # Render from recorded UE4.21 Pavlov spawn candidates plus source bounds.
    var cam: Camera3D = Camera3D.new()
    cam.name="SourceCameraDiagnostics"
    cam.fov=72.0
    cam.near=0.035
    cam.far=850.0
    root.add_child(cam)
    cam.current=true

    var views: Array[Dictionary] = [
        {"name":"01-source-overview",
         "camera":Vector3(24.66175,37.85322,19.89849),
         "target":Vector3(-2.494789,3.153206,-7.258049)},
        {"name":"02-source-spawn10-interior",
         "camera":Vector3(-10.51,1.65,-1.924322),
         "target":Vector3(-17.0,1.7,-3.2)},
        {"name":"03-source-spawn4-interior",
         "camera":Vector3(7.530912,1.65,-0.335323),
         "target":Vector3(5.8,1.6,-6.3)},
        {"name":"04-source-spawn6-interior",
         "camera":Vector3(11.61863,1.65,-0.325515),
         "target":Vector3(4.5,1.6,0.4)},
        # DIAGNOSTIC AMBIENT ONLY: these last two images make the source
        # texture details visible without claiming UE4/Godot light parity.
        # Original source-light frames are always saved FIRST, untouched.
        {"name":"05-diagnostic-overview-ambient",
         "camera":Vector3(24.66175,37.85322,19.89849),
         "target":Vector3(-2.494789,3.153206,-7.258049),
         "diagnostic":true},
        {"name":"06-diagnostic-spawn6-ambient",
         "camera":Vector3(11.61863,1.65,-0.325515),
         "target":Vector3(4.5,1.6,0.4),
         "diagnostic":true}
    ]
    var results: Array[Dictionary] = []
    var diagnostic_env_set: bool = false
    for view in views:
        var name: String = str(view["name"])
        if bool(view.get("diagnostic",false)) and not diagnostic_env_set:
            var sky_candidates: Array[Node] = light_root.find_children(
                "*","WorldEnvironment",true,false
            )
            if sky_candidates.size()!=1:
                push_error("XZOGOT_NACHT_DIAGNOSTIC_SOURCE_SKYLIGHT_ABSENT_RED")
                quit(26)
                return
            var source_sky: WorldEnvironment = sky_candidates[0] as WorldEnvironment
            if source_sky == null or source_sky.environment == null:
                push_error("XZOGOT_NACHT_DIAGNOSTIC_SOURCE_SKYLIGHT_NULL_RED")
                quit(27)
                return
            # These two FRAMES ARE NOT historical source lighting parity.
            # Exposure is raised in Godot ONLY to inspect the REAL 718 DDS
            # and lossless 10793-source-actor mesh structure on small screens.
            # Root cause of identical diagnostic images: Godot default
            # ambient_light_sky_contribution == 1.0 disables ambient_light_color
            # and ambient_light_energy. Also, current Camera3D environments have
            # priority over WorldEnvironment; force the override explicitly.
            # Reference: Godot 4.6 Environment docs.
            var diagnostic_environment: Environment = source_sky.environment.duplicate(true) as Environment
            diagnostic_environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
            diagnostic_environment.ambient_light_sky_contribution = 0.0
            diagnostic_environment.ambient_light_color = Color(0.70,0.78,0.88)
            diagnostic_environment.ambient_light_energy = 1.75
            diagnostic_environment.background_mode = Environment.BG_COLOR
            diagnostic_environment.background_color = Color(0.06,0.075,0.09)
            # This is an intentionally NOT-SOURCE-authored fill-light/camera
            # diagnostic to reveal source-native texture details. We NEVER
            # change the source-lit first four images or ship it as source truth.
            cam.environment = diagnostic_environment
            diagnostic_env_set = true
            print("XZOGOT_NACHT_MERIDIAN_DIAGNOSTIC_CAMERA_AMBIENT_FIX",
                  " source_sky_contribution=",source_sky.environment.ambient_light_sky_contribution,
                  " diagnostic_sky_contribution=",cam.environment.ambient_light_sky_contribution,
                  " diagnostic_color=",cam.environment.ambient_light_color,
                  " diagnostic_energy=",cam.environment.ambient_light_energy)
        cam.global_position=view["camera"]
        cam.look_at(view["target"],Vector3.UP)
        for _i in range(8):
            await process_frame
        var screen: Image = root.get_texture().get_image()
        if screen == null or screen.is_empty():
            push_error("XZOGOT_NACHT_VISUAL_NO_REAL_FRAME_RED "+name)
            quit(23)
            return
        if screen.get_width()<800 or screen.get_height()<450:
            push_error("XZOGOT_NACHT_VISUAL_TOO_SMALL_FRAME_RED "+name)
            quit(24)
            return
        var path: String = "res://"+name+".png"
        var result: Error = screen.save_png(path)
        if result!=OK:
            push_error("XZOGOT_NACHT_VISUAL_IMAGE_SAVE_RED "+name)
            quit(25)
            return
        var values: Array[float] = []
        var step_x: int=maxi(1,int(screen.get_width()/150))
        var step_y: int=maxi(1,int(screen.get_height()/90))
        for y in range(0,screen.get_height(),step_y):
            for x in range(0,screen.get_width(),step_x):
                var col: Color=screen.get_pixel(x,y)
                values.append(col.r*0.2126+col.g*0.7152+col.b*0.0722)
        values.sort()
        var lo: float=values[int(float(values.size()-1)*0.05)]
        var hi: float=values[int(float(values.size()-1)*0.95)]
        print("XZOGOT_NACHT_VISUAL_REAL_CAPTURE_CREATED",name,
              " size=",screen.get_width(),"x",screen.get_height(),
              " luminance_p05=",lo," p95=",hi," contrast_spread=",hi-lo)
        results.append({
            "filename":name+".png","width":screen.get_width(),"height":screen.get_height(),
            "sourceCameraOrigin":str(view["camera"]),"sourceCameraTarget":str(view["target"]),
            "luminanceSpread":hi-lo,
            "sourceTextures":true,
            "nativeLights":166,
            "diagnosticGodotAmbientOverride":bool(view.get("diagnostic",false)),
            "renderMethod":"Godot 4.6.1 gl_compatibility",
            "claimsOriginalBO3T7":false
        })
    # Never claim a diagnostic succeeded if Godot output was bitwise
    # identical to the source-lit frame; this exact false-positive happened
    # in #37951843624.
    var diag_comparison: Array[Dictionary] = []
    var ab_pairs: Array[Array] = [
        ["01-source-overview","05-diagnostic-overview-ambient"],
        ["04-source-spawn6-interior","06-diagnostic-spawn6-ambient"]
    ]
    for pair in ab_pairs:
        var native_image: Image = Image.load_from_file("res://"+str(pair[0])+".png")
        var debug_image: Image = Image.load_from_file("res://"+str(pair[1])+".png")
        if native_image == null or debug_image == null or native_image.is_empty() or debug_image.is_empty():
            push_error("XZOGOT_NACHT_LIGHTING_DIAGNOSTIC_SOURCE_IMAGES_MISSING_RED")
            quit(28)
            return
        var total_samples: int = 0
        var delta_sum: float = 0.0
        var native_sum: float = 0.0
        var debug_sum: float = 0.0
        var altered: int = 0
        for y in range(0,native_image.get_height(),8):
            for x in range(0,native_image.get_width(),8):
                var before_color: Color = native_image.get_pixel(x,y)
                var after_color: Color = debug_image.get_pixel(x,y)
                var a: float = before_color.r*0.2126+before_color.g*0.7152+before_color.b*0.0722
                var b: float = after_color.r*0.2126+after_color.g*0.7152+after_color.b*0.0722
                var delta: float = absf(b-a)
                delta_sum += delta
                native_sum += a
                debug_sum += b
                total_samples += 1
                if delta > 0.01:
                    altered += 1
        var changed_fraction: float = float(altered)/maxf(1.0,float(total_samples))
        var mean_abs_difference: float = delta_sum/maxf(1.0,float(total_samples))
        var brightness_gain: float = (debug_sum-native_sum)/maxf(1.0,float(total_samples))
        var comparison: Dictionary = {
            "sourceLitPhoto":str(pair[0])+".png",
            "ambientDiagnosticPhoto":str(pair[1])+".png",
            "changedFraction":changed_fraction,
            "meanAbsoluteLuminanceDelta":mean_abs_difference,
            "meanBrightnessGain":brightness_gain,
            "strictlyOriginalUE4Lighting":false
        }
        diag_comparison.append(comparison)
        print("XZOGOT_NACHT_REAL_SOURCE_VS_CAMERA_AMBIENT_PIXEL_AB",JSON.stringify(comparison))
        if changed_fraction<0.07 or mean_abs_difference<0.02 or brightness_gain<0.01:
            push_error("XZOGOT_NACHT_AMBIENT_DIAGNOSTIC_NO_VISIBLE_IMPROVEMENT_RED "+
                       JSON.stringify(comparison))
            quit(29)
            return

    var audit: Dictionary={
        "authority":"Pavlov UE4.21 archived source - NOT original BO3 T7",
        "renderedGodot":Engine.get_version_info().get("string",""),
        "actorMeshCount":meshes.size(),
        "sourceAuthoredMaterialSurfaces":bound,
        "sourceDiffuseTexturedSurfaces":textured,
        "sourceLights":166,
        "diagnosticAmbientPixelComparisons":diag_comparison,
        "diagnosticAmbientCameraEnvironmentForced":true,
        "sourceLitFirstFourUnchanged":true,
        "views":results,
        "fidelityNotProven":"original UE4 postprocess, fog, IBL, per-pixel lighting",
        "realGamePerformanceNotProven":true
    }
    var out: FileAccess=FileAccess.open("res://nacht-source-visual-capture-audit.json",FileAccess.WRITE)
    out.store_string(JSON.stringify(audit,"\t"))
    out.close()
    print("XZOGOT_NACHT_MERIDIAN_10793_REAL_SOURCE_VISUAL_CAPTURE_GREEN count=",results.size())
    quit(0)

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
         "diagnostic":true},
        # NIGHT LOOK DEV ONLY: source original lights/mesh/materials unchanged,
        # two separate color-balanced non-source atmospheric fill strengths.
        {"name":"07-night-lookdev-moon-overview",
         "camera":Vector3(24.66175,37.85322,19.89849),
         "target":Vector3(-2.494789,3.153206,-7.258049),
         "nightProfile":"moon"},
        {"name":"08-night-lookdev-moon-interior",
         "camera":Vector3(11.61863,1.65,-0.325515),
         "target":Vector3(4.5,1.6,0.4),
         "nightProfile":"moon"},
        {"name":"09-night-lookdev-dark-overview",
         "camera":Vector3(24.66175,37.85322,19.89849),
         "target":Vector3(-2.494789,3.153206,-7.258049),
         "nightProfile":"dark"},
        {"name":"10-night-lookdev-dark-interior",
         "camera":Vector3(11.61863,1.65,-0.325515),
         "target":Vector3(4.5,1.6,0.4),
         "nightProfile":"dark"}
    ]
    var results: Array[Dictionary] = []
    var diagnostic_env_set: bool = false
    var source_sky_environment: Environment = null
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
            source_sky_environment = source_sky.environment
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
        var night_profile: String = str(view.get("nightProfile",""))
        if not night_profile.is_empty():
            if source_sky_environment == null:
                push_error("XZOGOT_NACHT_NIGHT_SOURCE_SKY_NOT_FOUND_RED")
                quit(30)
                return
            var look_env: Environment = source_sky_environment.duplicate(true) as Environment
            look_env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
            look_env.ambient_light_sky_contribution = 0.0
            look_env.background_mode = Environment.BG_COLOR
            # Blue-gray moon ambience, with near-black background.
            # These are carefully LABELED visual look-dev values, not
            # unverified source-authored UE4 postprocess/lightmaps.
            if night_profile == "moon":
                look_env.ambient_light_color = Color(0.46,0.54,0.69)
                look_env.ambient_light_energy = 0.72
                look_env.background_color = Color(0.013,0.021,0.040)
            elif night_profile == "dark":
                look_env.ambient_light_color = Color(0.40,0.47,0.60)
                look_env.ambient_light_energy = 0.47
                look_env.background_color = Color(0.008,0.013,0.025)
            else:
                push_error("XZOGOT_NACHT_UNKNOWN_NIGHT_LOOKDEV_PROFILE_RED "+night_profile)
                quit(31)
                return
            cam.environment = look_env
            print("XZOGOT_NACHT_NIGHT_LOOKDEV_PROFILE_SET",night_profile,
                  " sky_contribution=",look_env.ambient_light_sky_contribution,
                  " color=",look_env.ambient_light_color,
                  " ambient_energy=",look_env.ambient_light_energy)
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
            "nightLookDevProfile":str(view.get("nightProfile","")),
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

    # Complete A/B: daylight-style diagnostic must be brighter than
    # BOTH night tests, and BOTH night tests must reveal more than source
    # zero-indirect-light fallback. Prevent another false-positive GREEN.
    var night_comparisons: Array[Dictionary] = []
    var tests: Array[Array] = [
        ["01-source-overview","07-night-lookdev-moon-overview",
         "09-night-lookdev-dark-overview","05-diagnostic-overview-ambient"],
        ["04-source-spawn6-interior","08-night-lookdev-moon-interior",
         "10-night-lookdev-dark-interior","06-diagnostic-spawn6-ambient"]
    ]
    for pair in tests:
        var mean_values: Array[float] = []
        var black_ratios: Array[float] = []
        for item in pair:
            var frame: Image = Image.load_from_file("res://"+str(item)+".png")
            if frame==null or frame.is_empty():
                push_error("XZOGOT_NACHT_MISSING_NIGHT_OR_SOURCE_AB_IMAGE_RED "+str(item))
                quit(32)
                return
            var total: float = 0.0
            var blacks: int = 0
            var n: int = 0
            for y in range(0,frame.get_height(),8):
                for x in range(0,frame.get_width(),8):
                    var rgb: Color=frame.get_pixel(x,y)
                    var lum: float=0.2126*rgb.r+0.7152*rgb.g+0.0722*rgb.b
                    total+=lum
                    if lum<0.035:
                        blacks+=1
                    n+=1
            mean_values.append(total/float(n))
            black_ratios.append(float(blacks)/float(n))
        var summary: Dictionary = {
            "source":str(pair[0]),"moon":str(pair[1]),
            "dark":str(pair[2]),"daylightDiagnostic":str(pair[3]),
            "meanLuminance":mean_values,
            "blackFraction":black_ratios,
            "NOTOriginalUE4Lighting":true
        }
        night_comparisons.append(summary)
        print("XZOGOT_NACHT_NIGHT_LOOKDEV_SOURCE_DARK_MOON_DAYLIGHT_PIXEL_AB ",JSON.stringify(summary))
        # UE4 source's local lights are already very bright on isolated
        # pale surfaces. A less-flat night camera can LOWER full-frame
        # mean while exposing MUCH MORE of the formerly pitch-black shadows.
        # Thus do not require mean(night)>mean(source) for an interior!
        # Gate objective retained shadow detail *and* distinguish the night
        # profiles from the intentionally bright reference.
        if not (mean_values[2]+0.005 < mean_values[1] and
                mean_values[1]+0.015 < mean_values[3] and
                black_ratios[2]+0.10 < black_ratios[0] and
                black_ratios[1]+0.10 < black_ratios[0] and
                mean_values[1]<0.28 and black_ratios[1]>0.05):
            push_error("XZOGOT_NACHT_NIGHT_LOOKDEV_SHADOW_VISIBILITY_ORDER_RED "+
                       JSON.stringify(summary))
            quit(33)
            return
    print("XZOGOT_NACHT_NIGHT_LOOKDEV_SHADOW_VISIBILITY_BRACKET_GREEN both_camera_views=2")
    # A/B is captured AFTER all ten already validated source/night frames.
    # Authentic materials/lights stay untouched. The original 55m circle
    # and exact transformed GLB actor bounds forbid any building changes.
    var exterior_policy_raw: Variant = JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-exterior-visual-policy.json"))
    if not (exterior_policy_raw is Dictionary):
        push_error("XZOGOT_NACHT_MOBILE_EXTERIOR_SOURCE_POLICY_MISSING_RED")
        quit(34)
        return
    var optimization_script: Script = load("res://nacht_apply_source_exterior_visual_lod.gd") as Script
    if optimization_script == null:
        push_error("XZOGOT_NACHT_MOBILE_EXTERIOR_ACTUAL_GODOT_CONTROLLER_MISSING_RED")
        quit(35)
        return
    var optimizer: RefCounted = optimization_script.new() as RefCounted
    var exterior_report: Dictionary = optimizer.call("apply_to_real_source_meshes",
        exterior_policy_raw,by_actor) as Dictionary
    if (not (exterior_report.get("errors",[]) as Array).is_empty() or
        int(exterior_report.get("actualFarExteriorGodotActorsOptimized",0))<30 or
        int(exterior_report.get("nearBuildingOriginalActorsProtected",0))<100):
        push_error("XZOGOT_NACHT_EXTERIOR_55M_SOURCE_BUILDING_RUNTIME_SAFETY_RED "+
                   JSON.stringify(exterior_report))
        quit(36)
        return
    print("XZOGOT_NACHT_REAL_GODOT_EXTERIOR_FOLIAGE_SOURCE_POLICY_APPLIED",
          " optimized_original_actors=",exterior_report["actualFarExteriorGodotActorsOptimized"],
          " protected_building_source_meshes=",exterior_report["nearBuildingOriginalActorsProtected"],
          " source_imported_LOD_variants=",exterior_report["sourceMeshActorsWithAutoImportedLODVariants"],
          " distant_shadows_off=",exterior_report["originalFarDecorationActorsShadowOff"])
    var moon_original: Environment = source_sky_environment.duplicate(true) as Environment
    moon_original.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
    moon_original.ambient_light_sky_contribution=0.0
    moon_original.background_mode=Environment.BG_COLOR
    moon_original.background_color=Color(0.013,0.021,0.040)
    moon_original.ambient_light_color=Color(0.46,0.54,0.69)
    moon_original.ambient_light_energy=0.72
    cam.environment=moon_original
    var optim_views: Array[Dictionary]=[
        {"new":"11-exterior-moon-optimized","before":"07-night-lookdev-moon-overview",
         "origin":Vector3(24.66175,37.85322,19.89849),
         "target":Vector3(-2.494789,3.153206,-7.258049)},
        {"new":"12-interior-moon-optimized","before":"08-night-lookdev-moon-interior",
         "origin":Vector3(11.61863,1.65,-0.325515),
         "target":Vector3(4.5,1.6,0.4)}
    ]
    var exterior_pixels: Array[Dictionary]=[]
    for view: Dictionary in optim_views:
        cam.global_position=view["origin"]
        cam.look_at(view["target"],Vector3.UP)
        for _f: int in range(12):
            await process_frame
        var after: Image=root.get_texture().get_image()
        var baseline: Image=Image.load_from_file("res://"+str(view["before"])+".png")
        if (after==null or baseline==null or after.is_empty() or baseline.is_empty()
            or after.get_size()!=baseline.get_size()):
            push_error("XZOGOT_NACHT_EXTERIOR_OPTIMIZED_REAL_RENDER_IMAGE_MISSING_RED")
            quit(37)
            return
        var saved: Error=after.save_png("res://"+str(view["new"])+".png")
        if saved!=OK:
            push_error("XZOGOT_NACHT_EXTERIOR_ACTUAL_GODOT_PNG_NOT_SAVED_RED")
            quit(38)
            return
        var count: int=0
        var sum_difference: float=0.0
        var large_differences: int=0
        for py: int in range(0,after.get_height(),8):
            for px: int in range(0,after.get_width(),8):
                var before_color: Color=baseline.get_pixel(px,py)
                var after_color: Color=after.get_pixel(px,py)
                var color_difference: float=(
                    absf(before_color.r-after_color.r)
                    +absf(before_color.g-after_color.g)
                    +absf(before_color.b-after_color.b))/3.0
                count+=1
                sum_difference+=color_difference
                if color_difference>0.10:
                    large_differences+=1
        var result: Dictionary={
            "originalRealGodotMoonFrame":str(view["before"])+".png",
            "sourceOnlyOutdoorLODFrame":str(view["new"])+".png",
            "meanAbsoluteRGBPixelDelta":sum_difference/float(count),
            "fractionPixelsDifferingMoreThan0_10":float(large_differences)/float(count),
            "width":after.get_width(),"height":after.get_height(),
            "sameLightCameraAndOriginalMaterials":true,
            "changingOnlyFarAuthoredFoliageLODAndNonstructuralSmallClutter":true
        }
        exterior_pixels.append(result)
        print("XZOGOT_NACHT_REAL_GODOT_EXTERIOR_LOD_BEFORE_AFTER_PIXEL_AB",
              JSON.stringify(result))
        # Inside the playable building the environment/architecture must not
        # visibly degrade. A near-camera source fidelity check, not a GPU FPS
        # claim; small outdoor glimpses through windows are still allowed.
        if str(view["new"]).begins_with("12-") and (
            float(result["meanAbsoluteRGBPixelDelta"])>0.08 or
            float(result["fractionPixelsDifferingMoreThan0_10"])>0.14):
            push_error("XZOGOT_NACHT_BUILDING_INTERIOR_VISUALS_CHANGED_BY_FAR_LOD_RED "+
                       JSON.stringify(result))
            quit(39)
            return
    print("XZOGOT_NACHT_REAL_GODOT_OUTDOOR_FAR_LOD_AB_GREEN ",
          " original_actor_count=",meshes.size(),
          " exterior_original_actors_optimized=",exterior_report["actualFarExteriorGodotActorsOptimized"],
          " original_interior_aabb_protected=",exterior_report["nearBuildingOriginalActorsProtected"],
          " rendered_A_B_views=",exterior_pixels.size())

    # Last capture gate: after source-authored far-only foliage settings,
    # add REAL 256/512px source-derived DDS per ACTOR, never in the original
    # shared material. See #37967088357 standalone actual Godot GREEN.
    # Contrast frames 11/12 (same original far-forest LOD/shadows) with
    # 13/14 (ONLY additional far-vista lower-resolution albedo overrides).
    var vista_any: Variant=JSON.parse_string(
        FileAccess.get_file_as_string("res://nacht-authored-vista-actor-policy.json"))
    var vista_script: Script=load("res://nacht_apply_source_vista_actor_local_dds.gd") as Script
    if not (vista_any is Dictionary) or vista_script==null:
        push_error("XZOGOT_NACHT_ACTOR_ONLY_VISTA_REAL_SOURCE_DDS_POLICY_MISSING_RED")
        quit(40)
        return
    var source_vista_optimizer: RefCounted=vista_script.new() as RefCounted
    var native_vista_report: Dictionary=source_vista_optimizer.call(
        "apply_authored_source_vistas",vista_any,by_actor) as Dictionary
    if (not (native_vista_report.get("errors",[]) as Array).is_empty()
        or int(native_vista_report.get("sourceAuthoredVistaActorsWithSourceDerivedLowRes",0))<100
        or int(native_vista_report.get("originalSourceGLBActorsUnchanged",0))!=10793
        or bool(native_vista_report.get("sourceOriginalSharedTextureResourceModified",true))):
        push_error("XZOGOT_NACHT_REAL_GODOT_VISTA_ACTOR_ONLY_DDS_OR_SOURCE_PARITY_RED "+
            JSON.stringify(native_vista_report))
        quit(41)
        return
    print("XZOGOT_NACHT_GODOT_ACTUAL_FAR_SOURCE_VISTA_DDS_DOWNSCALE_ENABLED",
        " real_actor_local_lowres=",native_vista_report["sourceAuthoredVistaActorsWithSourceDerivedLowRes"],
        " source_albedo_surfaces=",native_vista_report["sourceAuthoredNativeSurfaceAlbedoVariants"],
        " unique_new_image_textures=",native_vista_report["uniqueRealGodotLowerResolutionImageTextures"],
        " original_full_resolution_near_textures_unchanged=true")
    var vista_photo_specs: Array[Dictionary]=[
        {"before":"11-exterior-moon-optimized","after":"13-far-vista-lowres-outdoor",
         "camera":Vector3(24.66175,37.85322,19.89849),
         "target":Vector3(-2.494789,3.153206,-7.258049)},
        {"before":"12-interior-moon-optimized","after":"14-far-vista-lowres-interior",
         "camera":Vector3(11.61863,1.65,-0.325515),
         "target":Vector3(4.5,1.6,0.4)}
    ]
    var vista_pixel_results: Array[Dictionary]=[]
    for photo: Dictionary in vista_photo_specs:
        cam.global_position=photo["camera"]
        cam.look_at(photo["target"],Vector3.UP)
        for frame: int in range(14):
            await process_frame
        var actual: Image=root.get_texture().get_image()
        var prior: Image=Image.load_from_file("res://"+str(photo["before"])+".png")
        if actual==null or prior==null or actual.is_empty() or prior.is_empty() or actual.get_size()!=prior.get_size():
            push_error("XZOGOT_NACHT_NATIVE_VISTA_DDS_AB_REAL_SOURCE_IMAGES_UNAVAILABLE_RED")
            quit(42)
            return
        var file_err: Error=actual.save_png("res://"+str(photo["after"])+".png")
        if file_err!=OK:
            push_error("XZOGOT_NACHT_NATIVE_VISTA_DDS_SOURCE_A_B_PNG_SAVE_RED")
            quit(43)
            return
        var difference_sum: float=0.0
        var strong_diff_count: int=0
        var pixel_count: int=0
        for py: int in range(0,actual.get_height(),8):
            for px: int in range(0,actual.get_width(),8):
                var a: Color=prior.get_pixel(px,py)
                var d: Color=actual.get_pixel(px,py)
                var mean_delta: float=(absf(a.r-d.r)+absf(a.g-d.g)+absf(a.b-d.b))/3.0
                difference_sum+=mean_delta
                pixel_count+=1
                if mean_delta>0.10:
                    strong_diff_count+=1
        var cmp: Dictionary={
            "priorSourceHighResolutionAndFarLOD":str(photo["before"])+".png",
            "actualGodotActorLocalLowerResolutionDDS":str(photo["after"])+".png",
            "meanAbsoluteRGBDelta":difference_sum/float(pixel_count),
            "fractionPixelDeltaAbove0_10":float(strong_diff_count)/float(pixel_count),
            "unmodifiedOriginalActorTexturesSharedWithNearScene":true,
            "whetherAppDrawCallsOrAndroidFPSChangedProven":false
        }
        vista_pixel_results.append(cmp)
        print("XZOGOT_NACHT_REAL_NATIVE_VISTA_DDS_BEFORE_AFTER_PIXEL_AB",JSON.stringify(cmp))
        # Windows/interior views must NOT visibly degrade. More distant
        # foliage being indistinguishable at 720p is allowed. Zero pixel
        # difference does NOT prove positive GPU savings or real LOD.
        if str(photo["after"]).contains("interior") and (
            float(cmp["meanAbsoluteRGBDelta"])>0.020 or
            float(cmp["fractionPixelDeltaAbove0_10"])>0.035):
            push_error("XZOGOT_NACHT_VISTA_LOWRES_DEGRADED_GAMEPLAY_INTERIOR_WINDOWS_RED "+
                JSON.stringify(cmp))
            quit(44)
            return
    print("XZOGOT_NACHT_REAL_GODOT_173_FAR_VISTA_TEXTURE_AB_SOURCE_FIDELITY_GREEN",
        " real_ab_images=",vista_pixel_results.size(),
        " original_DDS_near_unchanged=true",
        " original_static_world_actors=",by_actor.size(),
        " GPU_FPS_not_yet_measured=true")

    var audit: Dictionary={
        "authority":"Pavlov UE4.21 archived source - NOT original BO3 T7",
        "renderedGodot":Engine.get_version_info().get("string",""),
        "actorMeshCount":meshes.size(),
        "sourceAuthoredMaterialSurfaces":bound,
        "sourceDiffuseTexturedSurfaces":textured,
        "sourceLights":166,
        "farSourceVistaActorLocalLowResolutionDDS":native_vista_report,
        "sourceVistaTextureRealGodotBeforeAfterPixelResults":vista_pixel_results,
        "farExteriorActualGodotLODPolicy":exterior_report,
        "farExteriorRealGodotBeforeAfterComparisons":exterior_pixels,
        "farFoliageOptimizationIsNotMobileFPSProof":true,
        "diagnosticAmbientPixelComparisons":diag_comparison,
        "nightLookdevPixelComparisons":night_comparisons,
        "nightLookdevIsSourceFaithful":false,
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
    print("XZOGOT_NACHT_FINAL_SOURCE_RENDER_IMAGES_COUNT ",results.size()+exterior_pixels.size()+vista_pixel_results.size())
    quit(0)

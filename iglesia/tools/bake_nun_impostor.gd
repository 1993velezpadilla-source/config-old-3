extends SceneTree
## Render original, genuinely animated 24-bone Nun as 2.5D mobile sprites.
## A source-respecting in-game asset bake, NOT generative concept artwork.
## Headless screenshot is checked for real nontransparent model pixels.
const SOURCE := "res://assets/zombies/_bake_source/monja_basica_clean_rig.gltf"
const OUTPUT := "res://assets/zombies/nun_source_sprite/"
const FRAME_COUNT := 4
const DIRECTIONS := 4

func _initialize() -> void:
    call_deferred("_run_bake")

func _model_bounds(node: Node3D) -> AABB:
    var found: bool = false
    var merged := AABB()
    for candidate in node.find_children("*","MeshInstance3D",true,false):
        var mi: MeshInstance3D = candidate as MeshInstance3D
        if mi.mesh == null:
            continue
        var local_to_root: Transform3D = node.global_transform.affine_inverse() * mi.global_transform
        var box: AABB = local_to_root * mi.get_aabb()
        if not found:
            merged=box
            found=true
        else:
            merged=merged.merge(box)
    return merged

func _run_bake() -> void:
    var resource := load(SOURCE)
    if not (resource is PackedScene):
        push_error("IGLESIA_ORIGINAL_NUN_OFFLINE_SOURCE_SCENE_UNAVAILABLE")
        quit(1)
        return
    var viewport := SubViewport.new()
    viewport.name="RealNunSpriteBaker"
    viewport.size=Vector2i(384,640)
    viewport.transparent_bg=true
    viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
    viewport.msaa_3d=Viewport.MSAA_2X
    viewport.world_3d=World3D.new()
    root.add_child(viewport)
    var env_node := WorldEnvironment.new()
    var env := Environment.new()
    env.background_mode=Environment.BG_CLEAR_COLOR
    env.ambient_light_source=Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color=Color(0.75,0.72,0.69)
    env.ambient_light_energy=1.15
    env.tonemap_mode=Environment.TONE_MAPPER_FILMIC
    env_node.environment=env
    viewport.add_child(env_node)
    var model_root := Node3D.new()
    viewport.add_child(model_root)
    var real_nun := (resource as PackedScene).instantiate() as Node3D
    if real_nun == null:
        push_error("IGLESIA_ORIGINAL_NUN_RIG_ROOT_NOT_3D")
        quit(1)
        return
    model_root.add_child(real_nun)
    var walker: AnimationPlayer = null
    var clip: String = ""
    for candidate in real_nun.find_children("*","AnimationPlayer",true,false):
        var animation_player := candidate as AnimationPlayer
        for name in animation_player.get_animation_list():
            if "Walk" in name or "walk" in name:
                walker = animation_player
                clip = name
                break
    if walker == null:
        push_error("IGLESIA_ORIGINAL_NUN_SOURCE_WALK_CLIP_NOT_FOUND")
        quit(1)
        return
    walker.play(clip)
    walker.advance(0.0)
    await process_frame
    var bounds: AABB = _model_bounds(real_nun)
    if bounds.size.y < 0.05 or bounds.size.y > 40.0:
        push_error("IGLESIA_NUN_GLTF_INVALID_GEOMETRY_BOUNDS " + str(bounds))
        quit(1)
        return
    # Real Tripo character is ~0.979m in source coords. Align its own feet
    # on ground and scale to a realistic 1.76m WITHOUT changing asset origin.
    var size_scale: float = 1.76 / bounds.size.y
    real_nun.scale=Vector3.ONE*size_scale
    real_nun.position=Vector3(
        -bounds.get_center().x*size_scale,
        -bounds.position.y*size_scale,
        -bounds.get_center().z*size_scale
    )
    var camera := Camera3D.new()
    camera.name="InGameTrueFrameCamera"
    camera.projection=Camera3D.PROJECTION_ORTHOGONAL
    camera.size=2.15
    camera.position=Vector3(0.0,0.90,4.0)
    viewport.add_child(camera)
    camera.look_at(Vector3(0.0,0.90,0.0),Vector3.UP)
    camera.current=true
    var moon := DirectionalLight3D.new()
    moon.light_color=Color(0.53,0.67,0.98)
    moon.light_energy=1.2
    moon.rotation_degrees=Vector3(-35,20,0)
    viewport.add_child(moon)
    var candle := DirectionalLight3D.new()
    candle.light_color=Color(1.0,0.63,0.37)
    candle.light_energy=1.4
    candle.rotation_degrees=Vector3(-55,-55,0)
    viewport.add_child(candle)
    DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
    var generated:=0
    for facing in range(DIRECTIONS):
        model_root.rotation.y=deg_to_rad(float(facing)*90.0)
        for frame in range(FRAME_COUNT):
            var anim: Animation=walker.get_animation(clip)
            walker.seek(float(frame)/float(FRAME_COUNT)*anim.length,true)
            viewport.render_target_update_mode=SubViewport.UPDATE_ALWAYS
            # Read back AFTER an actual GPU render frame, not SceneTree ticks.
            await RenderingServer.frame_post_draw
            var picture: Image=viewport.get_texture().get_image()
            if picture==null or picture.is_empty():
                push_error("IGLESIA_NUN_BAKE_EMPTY_VIEWPORT")
                quit(1)
                return
            picture.convert(Image.FORMAT_RGBA8)
            var samples:=0
            for y in range(25,picture.get_height()-25,8):
                for x in range(25,picture.get_width()-25,8):
                    if picture.get_pixel(x,y).a>0.15:
                        samples+=1
            if samples<140:
                push_error("IGLESIA_NUN_BAKE_TRANSPARENT_OR_BLACK_SPRITE direction="
                    +str(facing)+" frame="+str(frame)+" coverage="+str(samples))
                quit(1)
                return
            var file: String=OUTPUT+"nun_%d_walk_%02d.png" % [facing,frame]
            var err: Error=picture.save_png(ProjectSettings.globalize_path(file))
            if err!=OK:
                push_error("IGLESIA_NUN_BAKE_WRITE_FAILED "+file)
                quit(1)
                return
            generated+=1
            print("IGLESIA_NUN_REAL_SOURCE_FRAME",file,"samples",samples)
    if generated!=16:
        push_error("IGLESIA_NUN_16_REAL_FRAMES_MISSING")
        quit(1)
        return
    print("IGLESIA_NUN_SOURCE_2D_SPRITE_BAKE_GREEN",generated,"frames from original 3D animated source")
    quit(0)

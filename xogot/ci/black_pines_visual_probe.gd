extends SceneTree
## TRUE Godot offscreen visuals, never a generated "real gameplay" image.
## Usage in xfvb: GODOT --path xogot --rendering-method gl_compatibility
##   --resolution 1360x900 --script res://ci/black_pines_visual_probe.gd
const MAP_SCENE:=preload("res://black_pines.tscn")
const DEST: String="res://black-pines-real-firstframe-overview.png"

func _init() -> void:
    call_deferred("_capture")

func _capture() -> void:
    var scene: Node3D=MAP_SCENE.instantiate() as Node3D
    if scene==null:
        push_error("BLACK_PINES_VISUAL_RED cannot instantiate original independent test map")
        quit(41)
        return
    scene.set("rounds_enabled",false)
    scene.set("preview_no_enemies",true)
    root.add_child(scene)
    # Distinguish ordinary fallback renders from the ACTUAL Blender -> GLB ->
    # Godot mount. A screenshot of placeholder cubes is not art approval.
    if OS.get_environment("BLACK_PINES_REQUIRE_BLENDER_MOUNT") == "1":
        var architecture: Node=scene.get_node_or_null("Architecture")
        var authored: Node=scene.get_node_or_null(
            "Architecture/BlenderOriginalArchitecturalVisuals")
        var mesh_count: int=authored.find_children(
            "*","MeshInstance3D",true,false).size() if authored!=null else 0
        var collision_count: int=architecture.find_children(
            "*","CollisionShape3D",true,false).size() if architecture!=null else 0
        var scenery: Node=scene.get_node_or_null("Scenery")
        var duplicate_props: int=scenery.find_children(
            "*","MeshInstance3D",true,false).size() if scenery!=null else -1
        if not bool(scene.get_meta("black_pines_blender_visuals_mounted",false)) or mesh_count<40 or collision_count<70:
            push_error("BLACK_PINES_BLENDER_MOUNT_RED authored_meshes="+str(mesh_count)
                +" native_collider_count="+str(collision_count))
            quit(45)
            return
        var solid_heroes: int=0
        if scenery!=null:
            for item: Node in scenery.get_children():
                if item is StaticBody3D and bool(item.get_meta(
                        "black_pines_hero_collision_authority",false)):
                    solid_heroes+=1
        if solid_heroes!=9:
            push_error("BLACK_PINES_BLENDER_MOUNT_RED hero_collision_proxies="+str(solid_heroes))
            quit(49)
            return
        print("BLACK_PINES_NINE_HERO_COLLIDERS_MOUNTED_GREEN", " count=",solid_heroes)
        if duplicate_props!=0 or not bool(scene.get_meta(
                "black_pines_duplicate_scenery_prevented",false)):
            push_error("BLACK_PINES_BLENDER_MOUNT_RED double_scenery_meshes="
                +str(duplicate_props))
            quit(46)
            return
        # Ensure all nine ORIGINAL hero assets survived Blender -> GLB ->
        # Godot, rather than merely existing in a source-side Blender report.
        var heroes: Dictionary={}
        for rendered: Node in authored.find_children(
                "*","MeshInstance3D",true,false):
            if str(rendered.name).begins_with("Forge_Hero_"):
                heroes[str(rendered.name)]=true
        if heroes.size()!=9:
            push_error("BLACK_PINES_BLENDER_MOUNT_RED room_hero_mesh_count="
                +str(heroes.size())+" expected=9")
            quit(48)
            return
        print("BLACK_PINES_NINE_HEROES_MOUNTED_GREEN original_meshes=9")
        print("BLACK_PINES_DOUBLE_FURNITURE_ELIMINATED_GREEN",
            " native_scenery_meshes=0 blender_only=true")
        print("BLACK_PINES_BLENDER_MOUNT_GREEN meshes=",mesh_count,
            " native_collision_shapes=",collision_count,
            " true_blender_visuals=true android_device_test=false")
    for i in range(8):
        await process_frame
    scene.call("set_roof_visible",false)
    var hud: CanvasLayer=scene.get_node_or_null("HUD") as CanvasLayer
    # Survey capture should display architecture, not touch controls. This
    # does NOT remove the HUD from actual playable sessions.
    if hud!=null:
        hud.visible=false
    var original_camera: Camera3D=scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
    if original_camera!=null:
        original_camera.current=false
    var camera:=Camera3D.new()
    camera.name="BlackPinesActualGodotCameraNotIllustration"
    camera.position=Vector3(32,40,45)
    camera.fov=52.0
    camera.near=0.04
    camera.far=150.0
    scene.add_child(camera)
    camera.look_at(Vector3(0,0,3))
    camera.current=true
    for i in range(24):
        await process_frame
    var frame: Image=root.get_texture().get_image()
    if frame==null or frame.get_width()<900:
        push_error("BLACK_PINES_VISUAL_RED no real Godot frame captured")
        quit(42)
        return
    var output: String=ProjectSettings.globalize_path(DEST)
    var status: Error=frame.save_png(output)
    if status!=OK:
        push_error("BLACK_PINES_VISUAL_RED PNG write error "+str(status))
        quit(43)
        return
    # Second frame: actual first-person view with the production mobile HUD.
    camera.current=false
    scene.call("set_roof_visible",true)
    if hud!=null:
        hud.visible=true
    if original_camera!=null:
        original_camera.current=true
    for i in range(18):
        await process_frame
    var fps: Image=root.get_texture().get_image()
    var fps_dest: String=ProjectSettings.globalize_path(
        "res://black-pines-real-firstperson-mobile-hud.png")
    if fps==null or fps.save_png(fps_dest)!=OK:
        push_error("BLACK_PINES_VISUAL_RED firstperson UI screenshot failed")
        quit(44)
        return
    print("BLACK_PINES_REAL_GODOT_1360x900_OVERVIEW_GREEN path=",output,
        " actual_frame_not_illustration=true physical_android_test=false")
    print("BLACK_PINES_REAL_GODOT_FIRSTPERSON_HUD_SCREENSHOT_GREEN path=",fps_dest)
    # Fidelity review needs honest close-up evidence of all nine rooms, not
    # just a distant overview and a single cramped player start view.
    # These are REAL Godot runtime frames, using the same loaded GLB.
    var room_shots: Array[Dictionary]=[
        {"id":"generator","eye":Vector3(-16,1.6,-5.0),"target":Vector3(-11,1.35,-12)},
        {"id":"isolation","eye":Vector3(-4.7,1.6,-5.0),"target":Vector3(2.3,1.2,-12)},
        {"id":"surgery","eye":Vector3(15.8,1.6,-5.2),"target":Vector3(13.8,1.2,-11)},
        {"id":"patients","eye":Vector3(-9.0,1.6,6.5),"target":Vector3(-14,1.1,-1)},
        {"id":"triage","eye":Vector3(3.5,1.6,5.8),"target":Vector3(-1,1.1,-0.5)},
        {"id":"cafeteria","eye":Vector3(9,1.6,5.4),"target":Vector3(13,1.2,1.5)},
        {"id":"security","eye":Vector3(-9,1.6,16.8),"target":Vector3(-15,1.2,12)},
        {"id":"yard","eye":Vector3(-3,1.6,12.2),"target":Vector3(5,1.2,18)},
        {"id":"garage","eye":Vector3(9,1.6,11.4),"target":Vector3(15,1.2,18)}
    ]
    if hud!=null:
        hud.visible=false
    if original_camera!=null:
        original_camera.current=false
    camera.current=true
    # During gallery capture the playable CharacterBody remains near spawn.
    # Its first-person gun/arms otherwise look like a disembodied floating
    # handgun in Triage views. Hide ONLY during visual review screenshots,
    # not during the actual FPS screenshot or live gameplay.
    var gallery_player: Node3D=scene.get_node_or_null("Player") as Node3D
    if gallery_player!=null:
        gallery_player.visible=false
    print("BLACK_PINES_GALLERY_FREECAM_PLAYER_HIDDEN_GREEN",
        " during_gallery_only=true live_player_unchanged=true")
    for room: Dictionary in room_shots:
        camera.global_position=room["eye"] as Vector3
        camera.look_at(room["target"] as Vector3)
        for i in range(8):
            await process_frame
        var still: Image=root.get_texture().get_image()
        var path: String=ProjectSettings.globalize_path(
            "res://black-pines-fidelity-"+str(room["id"])+".png")
        if still==null or still.get_width()<900 or still.save_png(path)!=OK:
            push_error("BLACK_PINES_NINE_ROOM_FIDELITY_RED "+str(room["id"]))
            quit(47)
            return
        print("BLACK_PINES_FIDELITY_REAL_ROOM_IMAGE room=",str(room["id"]),
            " path=",path)
    print("BLACK_PINES_NINE_ROOM_FIDELITY_CAPTURE_GREEN",
        " count=9 real_godot=true visual_perfection_not_certified=true")
    quit(0)

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
    quit(0)

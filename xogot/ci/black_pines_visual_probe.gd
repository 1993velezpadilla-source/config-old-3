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
    var original_camera: Camera3D=scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
    if original_camera!=null:
        original_camera.current=false
    var camera:=Camera3D.new()
    camera.name="BlackPinesActualGodotCameraNotIllustration"
    camera.position=Vector3(40,53,57)
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
    print("BLACK_PINES_REAL_GODOT_1360x900_OVERVIEW_GREEN path=",output,
        " actual_frame_not_illustration=true physical_android_test=false")
    quit(0)

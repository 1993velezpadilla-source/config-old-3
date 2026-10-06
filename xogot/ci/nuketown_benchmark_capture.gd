extends SceneTree

const EXPECTED_MESHES := 52
const EXPECTED_NATIVE_CHUNKS := 53
const EXPECTED_INSTANCES := 124
const EXPECTED_LIGHTS := 5

func _init() -> void:
	call_deferred("_capture")

func _xz_to_godot(v: Vector3) -> Vector3:
	# Same single root-basis conversion used by XzielBenchmarkLoader:
	# XZIEL +X -> Godot -Z, +Y -> -X, +Z -> +Y.
	return Vector3(-v.y, v.z, -v.x)

func _capture() -> void:
	var loader_script := load("res://scripts/xziel_benchmark_loader.gd")
	if loader_script == null:
		push_error("NUKETOWN_CAPTURE: benchmark loader missing")
		quit(2)
		return

	var world := Node3D.new()
	world.name = "NuketownBenchmarkCapture"
	root.add_child(world)

	var loader: Node3D = loader_script.new() as Node3D
	if loader == null:
		push_error("NUKETOWN_CAPTURE: loader instantiate failed")
		quit(3)
		return
	loader.name = "SourceWorld"
	loader.set("load_on_ready", true)
	world.add_child(loader)

	var ready := false
	for attempt in range(180):
		await create_timer(0.10).timeout
		if bool(loader.get_meta("xziel_benchmark_ready", false)):
			ready = true
			break
	if not ready:
		push_error(
			"NUKETOWN_CAPTURE: source world did not become ready "
			+ str(loader.get_meta("xziel_benchmark_instance_count", -1))
			+ "/"
			+ str(loader.get_meta("xziel_benchmark_source_instance_count", -1))
			+ " missing="
			+ str(loader.get_meta("xziel_benchmark_missing_meshes", -1))
		)
		quit(4)
		return

	var mesh_count := int(loader.get_meta("xziel_benchmark_mesh_count", -1))
	var instance_count := int(loader.get_meta("xziel_benchmark_instance_count", -1))
	var missing_meshes := int(loader.get_meta("xziel_benchmark_missing_meshes", -1))
	var light_count := int(loader.get_meta("xziel_benchmark_light_count", -1))
	var native_glb_count := int(loader.get_meta("xziel_benchmark_native_glb_mesh_count", -1))
	var native_glb_chunk_count := int(loader.get_meta("xziel_benchmark_native_glb_chunk_count", -1))
	var xzms_fallback_count := int(loader.get_meta("xziel_benchmark_xzms_fallback_mesh_count", -1))
	if mesh_count != EXPECTED_MESHES:
		push_error("NUKETOWN_CAPTURE: mesh count mismatch " + str(mesh_count))
		quit(5)
		return
	if instance_count != EXPECTED_INSTANCES:
		push_error("NUKETOWN_CAPTURE: instance count mismatch " + str(instance_count))
		quit(6)
		return
	if missing_meshes != 0:
		push_error("NUKETOWN_CAPTURE: missing meshes " + str(missing_meshes))
		quit(7)
		return
	if light_count != EXPECTED_LIGHTS:
		push_error("NUKETOWN_CAPTURE: light count mismatch " + str(light_count))
		quit(8)
		return
	if native_glb_count != EXPECTED_MESHES or xzms_fallback_count != 0:
		push_error(
			"NUKETOWN_CAPTURE: native GLB authority mismatch native="
			+ str(native_glb_count)
			+ " fallback="
			+ str(xzms_fallback_count)
		)
		quit(14)
		return
	if native_glb_chunk_count != EXPECTED_NATIVE_CHUNKS:
		push_error(
			"NUKETOWN_CAPTURE: Godot-safe mesh chunk count mismatch "
			+ str(native_glb_chunk_count)
		)
		quit(15)
		return

	print(
		"XZOGOT_NUKETOWN_WORLD_RUNTIME_GREEN ",
		"meshes=", mesh_count,
		" instances=", instance_count,
		" lights=", light_count,
		" missing=", missing_meshes,
		" native_glb=", native_glb_count,
		" native_chunks=", native_glb_chunk_count,
		" xzms_fallback=", xzms_fallback_count
	)

	var camera := Camera3D.new()
	camera.name = "SourceSpawnCamera"
	camera.fov = 72.0
	camera.near = 0.03
	camera.far = 500.0
	world.add_child(camera)
	camera.current = true

	# Pavlov_Spawn_1 is source-authored at (-2.8266, 3.8388, 3.4150) XZIEL m.
	# Lift to a human eye and look toward the map interior (-Y in XZIEL).
	var spawn_xz := Vector3(-2.8266447, 3.838793, 4.45)
	var target_xz := Vector3(-2.0, -18.0, 3.1)
	camera.global_position = _xz_to_godot(spawn_xz)
	camera.look_at(_xz_to_godot(target_xz), Vector3.UP)

	for i in range(8):
		await process_frame

	var spawn_image := root.get_texture().get_image()
	if spawn_image == null or spawn_image.is_empty():
		push_error("NUKETOWN_CAPTURE: spawn frame empty")
		quit(9)
		return
	if spawn_image.get_width() <= spawn_image.get_height():
		push_error("NUKETOWN_CAPTURE: spawn frame not landscape")
		quit(10)
		return
	var spawn_path := "/tmp/xogot-nuketown-spawn.png"
	if spawn_image.save_png(spawn_path) != OK:
		push_error("NUKETOWN_CAPTURE: spawn save failed")
		quit(11)
		return
	print(
		"XZOGOT_NUKETOWN_SPAWN_SCREENSHOT_GREEN ",
		spawn_path, " ", spawn_image.get_width(), "x", spawn_image.get_height()
	)

	# Source-world overview: high oblique shot centered on playable core, not on
	# the long outlier/background geometry in the full instance bounds.
	camera.fov = 62.0
	camera.global_position = _xz_to_godot(Vector3(2.0, -18.0, 32.0))
	camera.look_at(_xz_to_godot(Vector3(0.0, -20.0, 2.5)), Vector3.UP)
	for i in range(8):
		await process_frame

	var overview_image := root.get_texture().get_image()
	if overview_image == null or overview_image.is_empty():
		push_error("NUKETOWN_CAPTURE: overview frame empty")
		quit(12)
		return
	var overview_path := "/tmp/xogot-nuketown-overview.png"
	if overview_image.save_png(overview_path) != OK:
		push_error("NUKETOWN_CAPTURE: overview save failed")
		quit(13)
		return
	print(
		"XZOGOT_NUKETOWN_OVERVIEW_SCREENSHOT_GREEN ",
		overview_path, " ", overview_image.get_width(), "x", overview_image.get_height()
	)

	quit(0)

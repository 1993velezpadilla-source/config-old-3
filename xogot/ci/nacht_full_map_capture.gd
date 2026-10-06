extends SceneTree

const EXPECTED_PACKAGES := 3871
const EXPECTED_MESHES := 493
const EXPECTED_INSTANCES := 10793
const EXPECTED_ACTORS := 11023
const EXPECTED_LIGHTS := 166
const EXPECTED_TEXTURES := 1581

func _init() -> void:
	call_deferred("_capture")

func _fail(code: int, message: String) -> void:
	push_error("NACHT_CAPTURE: " + message)
	quit(code)

func _percentile(values: Array[float], fraction: float) -> float:
	if values.is_empty():
		return 0.0
	values.sort()
	var index := clampi(
		int(round(float(values.size() - 1) * clampf(fraction, 0.0, 1.0))),
		0,
		values.size() - 1
	)
	return values[index]

func _save_view(path: String, label: String) -> bool:
	for _i in range(12):
		await process_frame
	var image := root.get_texture().get_image()
	if image == null or image.is_empty():
		_fail(30, label + " frame empty")
		return false
	if image.get_width() <= image.get_height():
		_fail(31, label + " frame not landscape")
		return false
	if image.save_png(path) != OK:
		_fail(32, label + " save failed")
		return false
	print(
		"XZOGOT_NACHT_", label.to_upper(), "_SCREENSHOT_GREEN ",
		path, " ", image.get_width(), "x", image.get_height()
	)
	return true

func _capture() -> void:
	var packed := load("res://nacht_full_map.tscn") as PackedScene
	if packed == null:
		_fail(2, "nacht_full_map.tscn missing")
		return

	var scene := packed.instantiate() as Node3D
	if scene == null:
		_fail(3, "Nacht scene instantiate failed")
		return
	root.add_child(scene)

	var ready := false
	for _i in range(3000):
		await create_timer(0.05).timeout
		if bool(scene.get_meta("nacht_full_map_ready", false)):
			ready = true
			break
	if not ready:
		_fail(4, "full map did not become ready")
		return

	var packages := int(scene.get_meta("source_package_count", -1))
	var meshes := int(scene.get_meta("source_mesh_count", -1))
	var instances := int(scene.get_meta("runtime_instance_count", -1))
	var actors := int(scene.get_meta("runtime_actor_anchor_count", -1))
	var lights := int(scene.get_meta("runtime_light_count", -1))
	var textures := int(scene.get_meta("source_complete_texture_catalog_count", -1))
	var missing_meshes := int(scene.get_meta("missing_mesh_count", -1))
	var texture_failures := int(scene.get_meta("source_texture_load_failures", -1))

	if packages != EXPECTED_PACKAGES:
		_fail(5, "package count mismatch " + str(packages))
		return
	if meshes != EXPECTED_MESHES:
		_fail(6, "mesh count mismatch " + str(meshes))
		return
	if instances != EXPECTED_INSTANCES:
		_fail(7, "instance count mismatch " + str(instances))
		return
	if actors != EXPECTED_ACTORS:
		_fail(8, "actor count mismatch " + str(actors))
		return
	if lights != EXPECTED_LIGHTS:
		_fail(9, "light count mismatch " + str(lights))
		return
	if textures != EXPECTED_TEXTURES:
		_fail(10, "texture count mismatch " + str(textures))
		return
	if missing_meshes != 0 or texture_failures != 0:
		_fail(
			11,
			"runtime source losses missing_meshes=%d texture_failures=%d"
			% [missing_meshes, texture_failures]
		)
		return

	print(
		"XZOGOT_NACHT_CAPTURE_WORLD_GREEN ",
		"packages=", packages,
		" meshes=", meshes,
		" instances=", instances,
		" actors=", actors,
		" lights=", lights,
		" textures=", textures
	)

	var hud := scene.get_node_or_null("HUD")
	if hud is CanvasLayer:
		(hud as CanvasLayer).visible = false

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	var spawn_camera := scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	if player == null or spawn_camera == null:
		_fail(12, "source player/camera missing")
		return
	spawn_camera.fov = 72.0
	spawn_camera.near = 0.03
	spawn_camera.far = 800.0
	spawn_camera.current = true

	if not await _save_view("/tmp/xogot-nacht-spawn.png", "spawn"):
		return

	var anchors := get_nodes_in_group("nacht_source_actor")
	if anchors.size() != EXPECTED_ACTORS:
		_fail(13, "source actor group mismatch " + str(anchors.size()))
		return

	var xs: Array[float] = []
	var ys: Array[float] = []
	var zs: Array[float] = []
	for raw: Node in anchors:
		if raw is Node3D:
			var p := (raw as Node3D).global_position
			xs.append(p.x)
			ys.append(p.y)
			zs.append(p.z)
	if xs.size() < 100:
		_fail(14, "not enough source actor positions for overview")
		return

	# Use 5th-95th percentile bounds so source-authored background/outlier
	# anchors do not pull the overview camera miles away from the playable core.
	var low := Vector3(
		_percentile(xs.duplicate(), 0.05),
		_percentile(ys.duplicate(), 0.05),
		_percentile(zs.duplicate(), 0.05)
	)
	var high := Vector3(
		_percentile(xs.duplicate(), 0.95),
		_percentile(ys.duplicate(), 0.95),
		_percentile(zs.duplicate(), 0.95)
	)
	var center := (low + high) * 0.5
	var span := high - low
	var horizontal_radius := maxf(maxf(span.x, span.z) * 0.5, 12.0)
	var vertical_span := maxf(span.y, 8.0)

	var overview_camera := Camera3D.new()
	overview_camera.name = "NachtSourceOverviewCamera"
	overview_camera.fov = 58.0
	overview_camera.near = 0.05
	overview_camera.far = maxf(1200.0, horizontal_radius * 12.0)
	scene.add_child(overview_camera)
	overview_camera.global_position = center + Vector3(
		horizontal_radius * 0.9,
		maxf(horizontal_radius * 1.15, vertical_span * 1.8),
		horizontal_radius * 0.9
	)
	overview_camera.look_at(center, Vector3.UP)
	overview_camera.current = true

	print(
		"XZOGOT_NACHT_CAPTURE_OVERVIEW_BOUNDS ",
		"low=", low,
		" high=", high,
		" center=", center,
		" camera=", overview_camera.global_position
	)

	if not await _save_view("/tmp/xogot-nacht-overview.png", "overview"):
		return

	scene.queue_free()
	await process_frame
	quit(0)

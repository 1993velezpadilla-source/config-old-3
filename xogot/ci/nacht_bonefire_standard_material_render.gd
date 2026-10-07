extends SceneTree

const TEXTURE_PATH := "res://assets/ci/bonefire_alpha.dds"
const OUTPUT_PATH := "/tmp/bonefire-standard-material.png"

func _init() -> void:
	call_deferred("_run")

func _luma(c: Color) -> float:
	return c.r * 0.2126 + c.g * 0.7152 + c.b * 0.0722

func _run() -> void:
	var raw: Resource = load(TEXTURE_PATH)
	if not (raw is Texture2D):
		push_error("XZOGOT_BONEFIRE_STANDARD_RENDER_FAILURE texture_load")
		quit(5)
		return
	var texture := raw as Texture2D
	var source_image := texture.get_image()
	if source_image == null or source_image.is_empty():
		push_error("XZOGOT_BONEFIRE_STANDARD_RENDER_FAILURE source_image")
		quit(5)
		return
	if source_image.is_compressed() and source_image.decompress() != OK:
		push_error("XZOGOT_BONEFIRE_STANDARD_RENDER_FAILURE source_decompress")
		quit(5)
		return

	root.size = Vector2i(640, 320)
	RenderingServer.set_default_clear_color(Color(0.0, 0.0, 0.0, 1.0))

	var world := Node3D.new()
	root.add_child(world)

	var camera := Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 2.0
	camera.position = Vector3(0.0, 0.0, 2.0)
	camera.current = true
	world.add_child(camera)

	var quad := QuadMesh.new()
	quad.size = Vector2(4.0, 2.0)
	var material := StandardMaterial3D.new()
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.blend_mode = BaseMaterial3D.BLEND_MODE_MIX
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.cull_mode = BaseMaterial3D.CULL_DISABLED
	material.albedo_texture = texture
	quad.material = material

	var mesh := MeshInstance3D.new()
	mesh.mesh = quad
	world.add_child(mesh)

	for _i in range(8):
		await process_frame

	var image := root.get_texture().get_image()
	if image == null or image.is_empty():
		push_error("XZOGOT_BONEFIRE_STANDARD_RENDER_FAILURE frame_empty")
		quit(5)
		return
	if image.save_png(OUTPUT_PATH) != OK:
		push_error("XZOGOT_BONEFIRE_STANDARD_RENDER_FAILURE save")
		quit(5)
		return

	var dark := 0
	var bright := 0
	var samples := 0
	for y in range(0, image.get_height(), 4):
		for x in range(0, image.get_width(), 4):
			var lum := _luma(image.get_pixel(x, y))
			if lum < 0.025:
				dark += 1
			if lum > 0.10:
				bright += 1
			samples += 1
	var dark_ratio := float(dark) / float(maxi(1, samples))
	var bright_ratio := float(bright) / float(maxi(1, samples))
	print(
		"XZOGOT_BONEFIRE_STANDARD_RENDER_PROBE ",
		"dark_ratio=", dark_ratio,
		" bright_ratio=", bright_ratio,
		" samples=", samples,
		" output=", OUTPUT_PATH
	)
	# The source atlas is overwhelmingly transparent. A correct alpha-mix
	# render over black must therefore remain predominantly black while keeping
	# visible flame pixels.
	if dark_ratio < 0.65 or bright_ratio < 0.001:
		push_error("XZOGOT_BONEFIRE_STANDARD_RENDER_FAILURE alpha_mix")
		quit(5)
		return
	print("XZOGOT_BONEFIRE_STANDARD_RENDER_GREEN")
	quit(0)

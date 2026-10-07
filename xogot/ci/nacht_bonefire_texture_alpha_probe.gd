extends SceneTree

const TEXTURE_PATH := "res://assets/ci/bonefire_alpha.dds"

func _init() -> void:
	var raw: Resource = load(TEXTURE_PATH)
	if not (raw is Texture2D):
		push_error("XZOGOT_BONEFIRE_GODOT_ALPHA_FAILURE texture_load path=%s" % TEXTURE_PATH)
		quit(5)
		return
	var texture := raw as Texture2D
	var image := texture.get_image()
	if image == null or image.is_empty():
		push_error("XZOGOT_BONEFIRE_GODOT_ALPHA_FAILURE image_empty")
		quit(5)
		return
	var was_compressed := image.is_compressed()
	if was_compressed:
		var err := image.decompress()
		if err != OK:
			push_error("XZOGOT_BONEFIRE_GODOT_ALPHA_FAILURE decompress_error=%d" % int(err))
			quit(5)
			return

	var min_alpha := 1.0
	var max_alpha := 0.0
	var below_half := 0
	var zeroish := 0
	var opaqueish := 0
	var samples := 0
	var step_x := maxi(1, image.get_width() / 64)
	var step_y := maxi(1, image.get_height() / 32)
	for y in range(0, image.get_height(), step_y):
		for x in range(0, image.get_width(), step_x):
			var a := image.get_pixel(x, y).a
			min_alpha = minf(min_alpha, a)
			max_alpha = maxf(max_alpha, a)
			if a < 0.5:
				below_half += 1
			if a <= 0.01:
				zeroish += 1
			if a >= 0.99:
				opaqueish += 1
			samples += 1

	print(
		"XZOGOT_BONEFIRE_GODOT_ALPHA_PROBE ",
		"compressed=", was_compressed,
		" width=", image.get_width(),
		" height=", image.get_height(),
		" min_alpha=", min_alpha,
		" max_alpha=", max_alpha,
		" below_half=", below_half,
		" zeroish=", zeroish,
		" opaqueish=", opaqueish,
		" samples=", samples
	)

	if image.get_width() != 2048 or image.get_height() != 1024:
		push_error("XZOGOT_BONEFIRE_GODOT_ALPHA_FAILURE unexpected_dimensions")
		quit(5)
		return
	if min_alpha > 0.05 or max_alpha < 0.95:
		push_error("XZOGOT_BONEFIRE_GODOT_ALPHA_FAILURE alpha_range")
		quit(5)
		return
	if below_half < int(samples * 0.70):
		push_error("XZOGOT_BONEFIRE_GODOT_ALPHA_FAILURE transparency_population")
		quit(5)
		return

	print("XZOGOT_BONEFIRE_GODOT_ALPHA_GREEN")
	quit(0)

extends SceneTree

const FULL_AUTHORITY_PATH := "res://assets/benchmarks/nacht_particle_slice/placed-particle-material-authority.json"
const FULL_DDS_ROOT := "res://assets/benchmarks/nacht_particle_slice/textures_dds"
const MINI_AUTHORITY_PATH := "res://placed-particle-material-authority.json"
const MINI_DDS_ROOT := "res://textures_dds"
const TARGET_TOKEN := "bonefire2b_fwd2"

func _fail(message: String) -> void:
	push_error("NACHT_PARTICLE_TEXTURE_ALPHA_PROBE: " + message)
	quit(2)

func _init() -> void:
	var authority_path := (
		MINI_AUTHORITY_PATH
		if FileAccess.file_exists(MINI_AUTHORITY_PATH)
		else FULL_AUTHORITY_PATH
	)
	var dds_root := (
		MINI_DDS_ROOT
		if FileAccess.file_exists(MINI_AUTHORITY_PATH)
		else FULL_DDS_ROOT
	)
	if not FileAccess.file_exists(authority_path):
		_fail("placed particle material authority missing")
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(authority_path))
	if not (parsed is Dictionary):
		_fail("authority JSON invalid")
		return
	var authority := parsed as Dictionary
	var target: Dictionary = {}
	for raw: Variant in authority.get("nativeTextures", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		if str(row.get("objectPath", "")).to_lower().contains(TARGET_TOKEN):
			target = row
			break
	if target.is_empty():
		_fail("BoneFire2B native texture absent")
		return

	var source_file := str(target.get("file", ""))
	if source_file.is_empty():
		_fail("BoneFire2B runtime source file missing")
		return
	var dds_path := dds_root.path_join(source_file.get_basename() + ".dds")
	if not FileAccess.file_exists(dds_path):
		_fail("DDS missing " + dds_path)
		return

	var texture_raw: Resource = load(dds_path)
	if not (texture_raw is Texture2D):
		_fail(
			"Godot DDS resource load failed class="
			+ ("null" if texture_raw == null else texture_raw.get_class())
		)
		return
	var image := (texture_raw as Texture2D).get_image()
	if image == null or image.is_empty():
		_fail("Godot DDS Texture2D image unavailable")
		return
	if image.is_compressed():
		var decompress_error := image.decompress()
		if decompress_error != OK:
			_fail("Godot DDS image decompress failed error=" + str(decompress_error))
			return
	if image.get_width() != int(target.get("width", -1)):
		_fail("width mismatch")
		return
	if image.get_height() != int(target.get("height", -1)):
		_fail("height mismatch")
		return

	var min_alpha := 1.0
	var max_alpha := 0.0
	var below_half := 0
	var zero_alpha := 0
	var samples := 0
	var step_x := maxi(1, image.get_width() / 128)
	var step_y := maxi(1, image.get_height() / 64)
	for y in range(0, image.get_height(), step_y):
		for x in range(0, image.get_width(), step_x):
			var alpha := image.get_pixel(x, y).a
			min_alpha = minf(min_alpha, alpha)
			max_alpha = maxf(max_alpha, alpha)
			if alpha < 0.5:
				below_half += 1
			if alpha <= 0.00001:
				zero_alpha += 1
			samples += 1

	if min_alpha > 0.01:
		_fail("BoneFire2B alpha floor lost min=" + str(min_alpha))
		return
	if max_alpha < 0.5:
		_fail("BoneFire2B alpha ceiling lost max=" + str(max_alpha))
		return
	if below_half <= 0 or zero_alpha <= 0:
		_fail("BoneFire2B transparent texels lost")
		return

	print(
		"XZOGOT_NACHT_GODOT_DDS_ALPHA_GREEN ",
		"source=", str(target.get("objectPath", "")),
		" format=", str(target.get("format", "")),
		" size=", image.get_width(), "x", image.get_height(),
		" min_alpha=", min_alpha,
		" max_alpha=", max_alpha,
		" below_half=", below_half, "/", samples,
		" zero_alpha=", zero_alpha, "/", samples
	)
	quit()

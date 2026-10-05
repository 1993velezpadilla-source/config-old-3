class_name WeaponTextureRegistry
extends RefCounted

const DATA_PATH := "res://data/weapon_material_bindings.json"
static var _cache: Dictionary = {}

static func _data() -> Dictionary:
	if not _cache.is_empty():
		return _cache
	if not FileAccess.file_exists(DATA_PATH):
		return {}
	var file := FileAccess.open(DATA_PATH, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if parsed is Dictionary:
		_cache = parsed as Dictionary
	return _cache

static func _normalize_material_name(value: String) -> String:
	var normalized := value.strip_edges().to_lower()
	# Blender can suffix duplicated datablocks with .001/.002. Bind those back
	# to the original CUE4Parse material instance name.
	if normalized.length() > 4 and normalized[-4] == ".":
		var suffix := normalized.right(3)
		if suffix.is_valid_int():
			normalized = normalized.left(-4)
	return normalized

static func _binding_for_name(material_name: String) -> Dictionary:
	var materials: Dictionary = _data().get("materials", {}) as Dictionary
	var wanted := _normalize_material_name(material_name)
	for key_var: Variant in materials.keys():
		var key := str(key_var)
		if _normalize_material_name(key) == wanted:
			return (materials[key] as Dictionary).duplicate(true)
	return {}

static func _load_texture(path: String) -> Texture2D:
	if path.is_empty() or not ResourceLoader.exists(path):
		return null
	return load(path) as Texture2D

static func _build_material(material_name: String, binding: Dictionary) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.resource_name = "Runtime_" + material_name
	material.albedo_color = Color(1.0, 1.0, 1.0, 1.0)
	material.metallic = clampf(float(binding.get("metallic", 0.34)), 0.0, 1.0)
	material.roughness = clampf(float(binding.get("roughness", 0.42)), 0.04, 1.0)

	var albedo := _load_texture(str(binding.get("albedo", "")))
	if albedo != null:
		material.albedo_texture = albedo

	var normal := _load_texture(str(binding.get("normal", "")))
	if normal != null:
		material.normal_enabled = true
		material.normal_texture = normal
		material.normal_scale = float(binding.get("normal_scale", 1.0))

	if bool(binding.get("two_sided", false)):
		material.cull_mode = BaseMaterial3D.CULL_DISABLED

	return material

static func _build_invisible_material(material_name: String) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.resource_name = "RuntimeHidden_" + material_name
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.albedo_color = Color(0.0, 0.0, 0.0, 0.0)
	material.no_depth_test = true
	return material

static func _is_intentionally_invisible(material_name: String) -> bool:
	var lower := _normalize_material_name(material_name)
	return lower.contains("invisible") or lower.contains("hidden")

static func apply_to_model(root: Node3D, weapon_id: String) -> Dictionary:
	if root == null:
		return {"surfaces": 0, "textured": 0, "missing": []}

	var data := _data()
	var fallback_names: Array = (
		(data.get("weapon_materials", {}) as Dictionary).get(weapon_id, []) as Array
	)
	var fallback_index := 0
	var surfaces := 0
	var resolved := 0
	var textured := 0
	var hidden := 0
	var missing: Array[String] = []

	for node: Node in root.find_children("*", "MeshInstance3D", true, false):
		if not (node is MeshInstance3D):
			continue
		var mesh_instance := node as MeshInstance3D
		mesh_instance.layers = mesh_instance.layers | (1 << 1)
		if mesh_instance.mesh == null:
			continue
		for surface_index in range(mesh_instance.mesh.get_surface_count()):
			surfaces += 1
			var source_material: Material = mesh_instance.get_active_material(surface_index)
			var material_name := ""
			if source_material != null:
				material_name = source_material.resource_name

			var binding := _binding_for_name(material_name)
			var binding_name := material_name
			if binding.is_empty() and fallback_index < fallback_names.size():
				binding_name = str(fallback_names[fallback_index])
				binding = _binding_for_name(binding_name)
			fallback_index += 1

			if binding.is_empty():
				if _is_intentionally_invisible(material_name):
					mesh_instance.set_surface_override_material(
						surface_index,
						_build_invisible_material(material_name)
					)
					resolved += 1
					hidden += 1
					continue
				missing.append(material_name if not material_name.is_empty() else ("surface_" + str(surface_index)))
				continue

			mesh_instance.set_surface_override_material(
				surface_index,
				_build_material(binding_name, binding)
			)
			resolved += 1
			textured += 1

	var report := {
		"weapon_id": weapon_id,
		"surfaces": surfaces,
		"resolved": resolved,
		"textured": textured,
		"hidden": hidden,
		"missing": missing,
		"ready": surfaces > 0 and resolved == surfaces,
	}
	return report

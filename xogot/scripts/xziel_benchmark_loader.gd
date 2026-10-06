class_name XzielBenchmarkLoader
extends Node3D

## Runtime bridge for the already-resolved XZIEL static-world payload.
##
## The old UE map work already produced source-authoritative geometry, transforms,
## material bindings, ASTC textures and lights. This loader consumes those files
## directly in Godot instead of reparsing cooked Unreal packages or inventing
## placements/material offsets.

@export_dir var source_root: String = "res://assets/benchmarks/nuketown_xziel"
@export var load_on_ready: bool = true
@export var build_materials: bool = true
@export var build_lights: bool = true
@export var cast_geometry_shadows: bool = true
@export var max_instances: int = 0

const VISUAL_SCENE_FILE := "visual-scene.json"
const MATERIAL_BINDINGS_FILE := "material-binding-manifest.json"
const TEXTURE_REPORT_FILE := "xzml-report.json"
const LIGHT_REPORT_FILE := "xzen-report.json"
const VFS_MAP_ROOT := "vfs/xziel/maps/xziel_nuketown_zombies"
const XZMS_HEADER_BYTES := 56
const XZMS_SUBMESH_BYTES := 16
const XZTX_HEADER_BYTES := 80
const XZTX_MIP_RECORD_BYTES := 24

const XZMS_ATTR_POSITION := 1 << 0
const XZMS_ATTR_NORMAL := 1 << 1
const XZMS_ATTR_UV0 := 1 << 2
const XZMS_ATTR_TANGENT := 1 << 6

var _mesh_cache: Dictionary = {}
var _material_cache: Dictionary = {}
var _texture_cache: Dictionary = {}
var _material_records: Dictionary = {}
var _texture_runtime_files: Dictionary = {}
var _mesh_material_paths: Dictionary = {}
var _instance_overrides: Dictionary = {}
var _runtime_root: Node3D
var _native_glb_mesh_count: int = 0
var _xzms_fallback_mesh_count: int = 0

func _ready() -> void:
	if load_on_ready:
		call_deferred("_load_benchmark_world")

func _load_benchmark_world() -> void:
	if _runtime_root != null:
		_runtime_root.queue_free()
		_runtime_root = null

	var scene := _read_json(_source_path(VISUAL_SCENE_FILE))
	if scene.is_empty():
		push_error("XZIEL benchmark: visual scene missing")
		return
	if str(scene.get("format", "")) != "xziel_visual_scene_v1":
		push_error("XZIEL benchmark: unsupported visual scene format")
		return

	_prepare_material_authority()
	_native_glb_mesh_count = 0
	_xzms_fallback_mesh_count = 0

	_runtime_root = Node3D.new()
	_runtime_root.name = "XZIELSceneRoot"
	# XZIEL runtime coordinates are meters, X,-Y,Z (Z-up).
	# Keep all child source matrices untouched and rotate the parent basis once:
	# XZIEL +X -> Godot -Z, XZIEL +Y -> Godot -X, XZIEL +Z -> Godot +Y.
	_runtime_root.basis = Basis(
		Vector3(0.0, 0.0, -1.0),
		Vector3(-1.0, 0.0, 0.0),
		Vector3(0.0, 1.0, 0.0)
	)
	add_child(_runtime_root)

	var meshes: Array = scene.get("meshes", [])
	var instances: Array = scene.get("instances", [])
	var instance_limit := instances.size()
	if max_instances > 0:
		instance_limit = mini(instance_limit, max_instances)

	var created := 0
	var missing_meshes := 0
	for instance_index in range(instance_limit):
		var instance: Dictionary = instances[instance_index]
		var mesh_index := int(instance.get("meshIndex", -1))
		if mesh_index < 0 or mesh_index >= meshes.size():
			continue
		var mesh_row: Dictionary = meshes[mesh_index]
		var runtime_file := str(mesh_row.get("runtimeFile", ""))
		var mesh := _load_benchmark_mesh(runtime_file, mesh_index)
		if mesh == null:
			missing_meshes += 1
			continue

		var node := MeshInstance3D.new()
		node.name = str(instance.get("instanceId", "ue_instance_%06d" % instance_index))
		node.mesh = mesh
		node.cast_shadow = (
			GeometryInstance3D.SHADOW_CASTING_SETTING_ON
			if cast_geometry_shadows
			else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		)
		node.transform = _transform_from_row_major(instance.get("matrixRowMajor", []))
		node.set_meta("source_component_path", str(instance.get("sourceComponentPath", "")))
		node.set_meta("source_scene_mesh_index", mesh_index)
		node.set_meta("source_instance_index", instance.get("sourceInstanceIndex", null))
		_apply_instance_material_overrides(node, str(instance.get("instanceId", "")))
		_runtime_root.add_child(node)
		created += 1

	if build_lights:
		_build_source_lights()

	var summary: Dictionary = scene.get("summary", {})
	set_meta("xziel_benchmark_ready", missing_meshes == 0 and created == instance_limit)
	set_meta("xziel_benchmark_mesh_count", meshes.size())
	set_meta("xziel_benchmark_instance_count", created)
	set_meta("xziel_benchmark_source_instance_count", instances.size())
	set_meta("xziel_benchmark_missing_meshes", missing_meshes)
	set_meta("xziel_benchmark_source_ready", bool(summary.get("ready", false)))
	set_meta("xziel_benchmark_native_glb_mesh_count", _native_glb_mesh_count)
	set_meta("xziel_benchmark_xzms_fallback_mesh_count", _xzms_fallback_mesh_count)
	print(
		"XZOGOT_XZIEL_BENCHMARK_WORLD ",
		"meshes=", meshes.size(),
		" instances=", created,
		"/", instance_limit,
		" missing=", missing_meshes,
		" native_glb=", _native_glb_mesh_count,
		" xzms_fallback=", _xzms_fallback_mesh_count,
		" materials=", _material_cache.size(),
		" textures=", _texture_cache.size()
	)

func _source_path(relative: String) -> String:
	return source_root.path_join(relative)

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _prepare_material_authority() -> void:
	_material_records.clear()
	_texture_runtime_files.clear()
	_mesh_material_paths.clear()
	_instance_overrides.clear()

	if not build_materials:
		return

	var bindings := _read_json(_source_path(MATERIAL_BINDINGS_FILE))
	var texture_report := _read_json(_source_path(TEXTURE_REPORT_FILE))

	for raw: Variant in bindings.get("materials", []):
		if raw is Dictionary:
			var record := raw as Dictionary
			_material_records[str(record.get("materialPath", ""))] = record

	for raw: Variant in texture_report.get("textureAssets", []):
		if raw is Dictionary:
			var texture_row := raw as Dictionary
			_texture_runtime_files[str(texture_row.get("sourcePath", ""))] = str(
				texture_row.get("runtimeFile", "")
			)

	for raw: Variant in bindings.get("meshes", []):
		if not (raw is Dictionary):
			continue
		var mesh_row := raw as Dictionary
		var mesh_index := int(mesh_row.get("sceneMeshIndex", -1))
		var submesh_count := int(mesh_row.get("submeshCount", 0))
		var paths: Array[String] = []
		paths.resize(submesh_count)
		paths.fill("")
		for section_raw: Variant in mesh_row.get("sections", []):
			if section_raw is Dictionary:
				var section := section_raw as Dictionary
				var submesh := int(section.get("submeshIndex", -1))
				if submesh >= 0 and submesh < paths.size():
					paths[submesh] = str(section.get("baseMaterialPath", ""))
		_mesh_material_paths[mesh_index] = paths

	for raw: Variant in bindings.get("instanceOverrides", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var by_slot: Dictionary = {}
		for slot_raw: Variant in row.get("slotOverrides", []):
			if slot_raw is Dictionary:
				var slot := slot_raw as Dictionary
				by_slot[int(slot.get("slotIndex", -1))] = str(slot.get("materialPath", ""))
		var submesh_paths: Dictionary = {}
		for submesh_raw: Variant in row.get("affectedSubmeshes", []):
			var submesh := int(submesh_raw)
			if by_slot.has(submesh):
				submesh_paths[submesh] = by_slot[submesh]
		_instance_overrides[str(row.get("instanceId", ""))] = submesh_paths

func _find_first_mesh_instance(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D:
		return node as MeshInstance3D
	for child: Node in node.get_children():
		var found := _find_first_mesh_instance(child)
		if found != null:
			return found
	return null

func _load_benchmark_mesh(runtime_file: String, scene_mesh_index: int) -> ArrayMesh:
	var cache_key := runtime_file.get_basename()
	if _mesh_cache.has(cache_key):
		return _mesh_cache[cache_key] as ArrayMesh

	var native_name := runtime_file.get_basename() + ".glb"
	var native_path := _source_path(VFS_MAP_ROOT.path_join("meshes_glb").path_join(native_name))
	if ResourceLoader.exists(native_path):
		var packed := load(native_path) as PackedScene
		if packed != null:
			var instance := packed.instantiate()
			if instance != null:
				var mesh_node := _find_first_mesh_instance(instance)
				if mesh_node != null and mesh_node.mesh is ArrayMesh:
					var mesh := (mesh_node.mesh as ArrayMesh).duplicate() as ArrayMesh
					var base_materials: Array = _mesh_material_paths.get(scene_mesh_index, [])
					if build_materials:
						for surface in range(mini(mesh.get_surface_count(), base_materials.size())):
							var material := _material_for_path(str(base_materials[surface]))
							if material != null:
								mesh.surface_set_material(surface, material)
					instance.free()
					_mesh_cache[cache_key] = mesh
					_native_glb_mesh_count += 1
					return mesh
				instance.free()

	# Truthful compatibility fallback for source artifacts staged before the
	# native GLB conversion. Shipping/mobile benchmark paths should use GLB.
	var fallback := _load_xzmesh(runtime_file, scene_mesh_index)
	if fallback != null:
		_mesh_cache[cache_key] = fallback
		_xzms_fallback_mesh_count += 1
	return fallback

func _load_xzmesh(runtime_file: String, scene_mesh_index: int) -> ArrayMesh:
	if _mesh_cache.has(runtime_file):
		return _mesh_cache[runtime_file] as ArrayMesh

	var path := _source_path(VFS_MAP_ROOT.path_join("meshes").path_join(runtime_file))
	if not FileAccess.file_exists(path):
		push_error("XZIEL benchmark mesh missing: " + path)
		return null
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < XZMS_HEADER_BYTES or bytes.slice(0, 4).get_string_from_ascii() != "XZMS":
		push_error("XZIEL benchmark invalid XZMS: " + runtime_file)
		return null

	var version := int(bytes.decode_u32(4))
	var vertex_count := int(bytes.decode_u32(8))
	var index_count := int(bytes.decode_u32(12))
	var submesh_count := int(bytes.decode_u32(16))
	var vertex_stride := int(bytes.decode_u32(24))
	var submesh_stride := int(bytes.decode_u32(28))
	if version < 3 or version > 4 or vertex_count <= 0 or index_count <= 0 or submesh_count <= 0:
		push_error("XZIEL benchmark unsupported XZMS header: " + runtime_file)
		return null
	if (version == 3 and vertex_stride != 72) or (version == 4 and vertex_stride != 104):
		push_error("XZIEL benchmark bad XZMS vertex stride: " + runtime_file)
		return null
	if submesh_stride != XZMS_SUBMESH_BYTES:
		push_error("XZIEL benchmark bad XZMS submesh stride: " + runtime_file)
		return null

	var vertex_offset := XZMS_HEADER_BYTES
	var index_offset := vertex_offset + vertex_count * vertex_stride
	var submesh_offset := index_offset + index_count * 4
	if submesh_offset + submesh_count * submesh_stride != bytes.size():
		push_error("XZIEL benchmark XZMS size mismatch: " + runtime_file)
		return null

	var positions := PackedVector3Array()
	var normals := PackedVector3Array()
	var uv0 := PackedVector2Array()
	var tangents := PackedFloat32Array()
	positions.resize(vertex_count)
	normals.resize(vertex_count)
	uv0.resize(vertex_count)
	tangents.resize(vertex_count * 4)
	for vertex_index in range(vertex_count):
		var at := vertex_offset + vertex_index * vertex_stride
		positions[vertex_index] = Vector3(
			bytes.decode_float(at),
			bytes.decode_float(at + 4),
			bytes.decode_float(at + 8)
		)
		normals[vertex_index] = Vector3(
			bytes.decode_float(at + 12),
			bytes.decode_float(at + 16),
			bytes.decode_float(at + 20)
		)
		if version >= 3:
			for tangent_component in range(4):
				tangents[vertex_index * 4 + tangent_component] = bytes.decode_float(
					at + 24 + tangent_component * 4
				)
			uv0[vertex_index] = Vector2(
				bytes.decode_float(at + 40),
				bytes.decode_float(at + 44)
			)
		else:
			uv0[vertex_index] = Vector2(
				bytes.decode_float(at + 24),
				bytes.decode_float(at + 28)
			)

	var mesh := ArrayMesh.new()
	var base_materials: Array = _mesh_material_paths.get(scene_mesh_index, [])
	for submesh_index in range(submesh_count):
		var sat := submesh_offset + submesh_index * submesh_stride
		var first_index := int(bytes.decode_u32(sat))
		var sub_index_count := int(bytes.decode_u32(sat + 4))
		var attr := int(bytes.decode_u32(sat + 12))
		if sub_index_count <= 0 or first_index < 0 or first_index + sub_index_count > index_count:
			continue

		var global_to_local: Dictionary = {}
		var local_positions := PackedVector3Array()
		var local_normals := PackedVector3Array()
		var local_uv := PackedVector2Array()
		var local_tangents := PackedFloat32Array()
		var local_indices := PackedInt32Array()

		for source_index_offset in range(sub_index_count):
			var global_index := int(bytes.decode_u32(index_offset + (first_index + source_index_offset) * 4))
			if global_index < 0 or global_index >= vertex_count:
				continue
			var local_index: int
			if global_to_local.has(global_index):
				local_index = int(global_to_local[global_index])
			else:
				local_index = local_positions.size()
				global_to_local[global_index] = local_index
				local_positions.append(positions[global_index])
				if (attr & XZMS_ATTR_NORMAL) != 0:
					local_normals.append(normals[global_index])
				if (attr & XZMS_ATTR_UV0) != 0:
					local_uv.append(uv0[global_index])
				if (attr & XZMS_ATTR_TANGENT) != 0:
					for tangent_component in range(4):
						local_tangents.append(tangents[global_index * 4 + tangent_component])
			local_indices.append(local_index)

		if local_positions.is_empty() or local_indices.size() < 3:
			continue
		var arrays: Array = []
		arrays.resize(Mesh.ARRAY_MAX)
		arrays[Mesh.ARRAY_VERTEX] = local_positions
		if not local_normals.is_empty():
			arrays[Mesh.ARRAY_NORMAL] = local_normals
		if not local_uv.is_empty():
			arrays[Mesh.ARRAY_TEX_UV] = local_uv
		if not local_tangents.is_empty():
			arrays[Mesh.ARRAY_TANGENT] = local_tangents
		arrays[Mesh.ARRAY_INDEX] = local_indices
		mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)

		var surface := mesh.get_surface_count() - 1
		if build_materials and submesh_index < base_materials.size():
			var material_path := str(base_materials[submesh_index])
			var material := _material_for_path(material_path)
			if material != null:
				mesh.surface_set_material(surface, material)

	_mesh_cache[runtime_file] = mesh
	return mesh

func _material_for_path(material_path: String) -> Material:
	if material_path.is_empty():
		return null
	if _material_cache.has(material_path):
		return _material_cache[material_path] as Material
	var record: Dictionary = _material_records.get(material_path, {})
	if record.is_empty():
		return null

	var material := StandardMaterial3D.new()
	material.resource_name = material_path.get_file()

	var canonical: Dictionary = record.get("canonicalTextures", {})
	var diffuse := _texture_for_source(str(canonical.get("diffuse", "")))
	var normal := _texture_for_source(str(canonical.get("normal", "")))
	var emissive := _texture_for_source(str(canonical.get("emissive", "")))
	if diffuse != null:
		material.albedo_texture = diffuse
	else:
		var colors: Array = record.get("colors", [])
		if not colors.is_empty() and colors[0] is Dictionary:
			var color_row := colors[0] as Dictionary
			material.albedo_color = Color(
				float(color_row.get("r", 1.0)),
				float(color_row.get("g", 1.0)),
				float(color_row.get("b", 1.0)),
				float(color_row.get("a", 1.0))
			)

	if normal != null:
		material.normal_enabled = true
		material.normal_texture = normal
	if emissive != null:
		material.emission_enabled = true
		material.emission_texture = emissive
		material.emission = Color.WHITE

	material.metallic = clampf(_source_scalar(record, "metallic", 0.0), 0.0, 1.0)
	material.roughness = clampf(_source_scalar(record, "roughness", 1.0), 0.0, 1.0)
	material.metallic_specular = maxf(0.0, _source_scalar(record, "specular", 0.5))
	material.cull_mode = (
		BaseMaterial3D.CULL_DISABLED
		if bool(record.get("twoSided", false))
		else BaseMaterial3D.CULL_BACK
	)

	var blend_mode := str(record.get("blendMode", "BLEND_Opaque"))
	if bool(record.get("isMasked", false)):
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA_SCISSOR
		material.alpha_scissor_threshold = float(record.get("opacityMaskClipValue", 0.333))
	elif blend_mode == "BLEND_Translucent":
		material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA

	if str(record.get("shadingModel", "")) == "MSM_Unlit":
		material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED

	material.set_meta("source_material_path", material_path)
	material.set_meta("source_blend_mode", blend_mode)
	material.set_meta("source_specular_mask_path", str(canonical.get("specular_masks", "")))
	_material_cache[material_path] = material
	return material

func _source_scalar(record: Dictionary, token: String, fallback: float) -> float:
	var needle := token.to_lower()
	for raw: Variant in record.get("scalars", []):
		if raw is Dictionary:
			var row := raw as Dictionary
			if str(row.get("name", "")).to_lower().contains(needle):
				return float(row.get("value", fallback))
	return fallback

func _texture_for_source(source_path: String) -> Texture2D:
	if source_path.is_empty():
		return null
	if _texture_cache.has(source_path):
		return _texture_cache[source_path] as Texture2D
	var runtime_file := str(_texture_runtime_files.get(source_path, ""))
	if runtime_file.is_empty():
		return null
	var texture := _load_xztexture(runtime_file)
	if texture != null:
		_texture_cache[source_path] = texture
	return texture

func _load_xztexture(runtime_file: String) -> Texture2D:
	var path := _source_path(VFS_MAP_ROOT.path_join("textures").path_join(runtime_file))
	if not FileAccess.file_exists(path):
		return null
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < XZTX_HEADER_BYTES or bytes.slice(0, 4).get_string_from_ascii() != "XZTX":
		return null
	var version := int(bytes.decode_u32(4))
	var width := int(bytes.decode_u32(8))
	var height := int(bytes.decode_u32(12))
	var depth := int(bytes.decode_u32(16))
	var mip_count := int(bytes.decode_u32(20))
	var format_name_bytes := int(bytes.decode_u32(28))
	var mip_record_bytes := int(bytes.decode_u32(32))
	var mip_table_offset := int(bytes.decode_u32(36))
	var payload_offset := int(bytes.decode_u32(40))
	var payload_bytes := int(bytes.decode_u32(44))
	if version != 1 or depth != 1 or mip_count <= 0:
		return null
	if mip_record_bytes != XZTX_MIP_RECORD_BYTES or mip_table_offset != XZTX_HEADER_BYTES:
		return null
	if payload_offset < XZTX_HEADER_BYTES or payload_offset + payload_bytes != bytes.size():
		return null
	var format_name := bytes.slice(48, 48 + format_name_bytes).get_string_from_ascii()
	var image_format: Image.Format
	match format_name:
		"PF_ASTC_6x6":
			image_format = Image.FORMAT_ASTC_6x6
		_:
			push_warning("XZIEL benchmark unsupported XZTX format: " + format_name)
			return null
	var payload := bytes.slice(payload_offset, payload_offset + payload_bytes)
	var image := Image.create_from_data(width, height, mip_count > 1, image_format, payload)
	if image == null or image.is_empty():
		return null
	var texture := ImageTexture.create_from_image(image)
	texture.resource_name = runtime_file
	return texture

func _apply_instance_material_overrides(node: MeshInstance3D, instance_id: String) -> void:
	if not build_materials or not _instance_overrides.has(instance_id):
		return
	var overrides: Dictionary = _instance_overrides[instance_id]
	for submesh_raw: Variant in overrides.keys():
		var surface := int(submesh_raw)
		if surface < 0 or surface >= node.get_surface_override_material_count():
			continue
		var material := _material_for_path(str(overrides[submesh_raw]))
		if material != null:
			node.set_surface_override_material(surface, material)

func _transform_from_row_major(raw: Variant) -> Transform3D:
	if not (raw is Array):
		return Transform3D.IDENTITY
	var m := raw as Array
	if m.size() != 16:
		return Transform3D.IDENTITY
	return Transform3D(
		Basis(
			Vector3(float(m[0]), float(m[4]), float(m[8])),
			Vector3(float(m[1]), float(m[5]), float(m[9])),
			Vector3(float(m[2]), float(m[6]), float(m[10]))
		),
		Vector3(float(m[3]), float(m[7]), float(m[11]))
	)

func _build_source_lights() -> void:
	var report := _read_json(_source_path(LIGHT_REPORT_FILE))
	if report.is_empty():
		return
	var created := 0
	var environment: Environment = null
	var world_environment: WorldEnvironment = null

	for raw: Variant in report.get("lights", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var type := str(row.get("componentType", ""))
		var source_position := _vec3(row.get("worldPositionMeters", []))
		var color := _color3(row.get("color", []))
		var intensity := float(row.get("intensity", 1.0))
		match type:
			"point":
				var light := OmniLight3D.new()
				light.name = str(row.get("id", "SourcePointLight"))
				light.position = source_position
				light.light_color = color
				light.omni_range = float(row.get("radiusMeters", 10.0))
				light.light_energy = 1.0
				# Source positional intensity is in candelas. Preserve the
				# physically equivalent lumens for projects using physical units.
				if str(row.get("units", "")) == "Candelas":
					light.light_intensity_lumens = intensity * 4.0 * PI
				light.set_meta("source_intensity", intensity)
				light.set_meta("source_intensity_units", str(row.get("units", "")))
				_runtime_root.add_child(light)
				created += 1
			"directional":
				var light := DirectionalLight3D.new()
				light.name = str(row.get("id", "SourceDirectionalLight"))
				light.position = source_position
				light.light_color = color
				light.light_energy = 1.0
				light.light_intensity_lux = intensity
				light.basis = _directional_basis_xziel(row.get("worldRotationUE", {}))
				light.set_meta("source_intensity", intensity)
				light.set_meta("source_rotation_ue", row.get("worldRotationUE", {}))
				_runtime_root.add_child(light)
				created += 1
			"sky":
				if world_environment == null:
					world_environment = WorldEnvironment.new()
					world_environment.name = "SourceSkyEnvironment"
					environment = Environment.new()
					environment.background_mode = Environment.BG_COLOR
					environment.background_color = color
					environment.background_energy_multiplier = intensity
					environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
					environment.ambient_light_color = color
					environment.ambient_light_energy = intensity
					world_environment.environment = environment
					_runtime_root.add_child(world_environment)
					world_environment.set_meta("source_sky_intensity", intensity)
					created += 1

	set_meta("xziel_benchmark_light_count", created)
	print("XZOGOT_XZIEL_BENCHMARK_LIGHTS ", created)

func _directional_basis_xziel(raw: Variant) -> Basis:
	if not (raw is Dictionary):
		return Basis.IDENTITY
	var rot := raw as Dictionary
	var pitch := deg_to_rad(float(rot.get("Pitch", 0.0)))
	var yaw := deg_to_rad(float(rot.get("Yaw", 0.0)))
	# UE +X forward, +Y right, +Z up -> XZIEL +X forward, -Y left, +Z up.
	var forward := Vector3(
		cos(pitch) * cos(yaw),
		-cos(pitch) * sin(yaw),
		sin(pitch)
	).normalized()
	var source_up := Vector3(0.0, 0.0, 1.0)
	var z_axis := -forward
	var x_axis := source_up.cross(z_axis).normalized()
	if x_axis.length_squared() < 0.000001:
		x_axis = Vector3(1.0, 0.0, 0.0)
	var y_axis := z_axis.cross(x_axis).normalized()
	return Basis(x_axis, y_axis, z_axis)

func _vec3(raw: Variant) -> Vector3:
	if not (raw is Array):
		return Vector3.ZERO
	var values := raw as Array
	if values.size() != 3:
		return Vector3.ZERO
	return Vector3(float(values[0]), float(values[1]), float(values[2]))

func _color3(raw: Variant) -> Color:
	if not (raw is Array):
		return Color.WHITE
	var values := raw as Array
	if values.size() < 3:
		return Color.WHITE
	return Color(float(values[0]), float(values[1]), float(values[2]), 1.0)

class_name WeaponSW357ReloadGeometry
extends RefCounted

# Source-fidelity rendering fix: the original single-surface SW357 mesh binds
# the speedloader, spare cartridges and spent cases to reload-only bones.
# Keep the original complete skinned mesh for reload; draw a per-instance
# triangle-filtered copy in HIP, ADS, fire and equip. Never mutate the GLB.
static func _is_reload_only_bone(bone_name: String) -> bool:
	return bone_name == "tag_speedloader" or bone_name == "tag_bullets" or bone_name.begins_with("tag_spent")

static func _source_mesh(root: Node3D) -> MeshInstance3D:
	if root == null:
		return null
	var stack: Array[Node] = [root]
	while not stack.is_empty():
		var current: Node = stack.pop_back()
		if current is MeshInstance3D:
			var candidate := current as MeshInstance3D
			if candidate.mesh != null and candidate.skin != null and not (candidate.mesh is PrimitiveMesh):
				return candidate
		for child: Node in current.get_children():
			stack.append(child)
	return null

static func prepare(root: Node3D) -> Dictionary:
	var gun := _source_mesh(root)
	if gun == null:
		push_error("XZOGOT_SW357_RUNTIME_SOURCE_SKIN_MISSING")
		return {}
	var original: Mesh = gun.mesh
	var skin: Skin = gun.skin
	var filtered := ArrayMesh.new()
	var removed_triangles := 0
	var removed_vertices := 0
	for surface_idx in range(original.get_surface_count()):
		var arr: Array = original.surface_get_arrays(surface_idx)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var source_indices: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
		var bones: PackedInt32Array = arr[Mesh.ARRAY_BONES]
		var weights: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
		var stride: int = 8 if (original.surface_get_format(surface_idx) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS) != 0 else 4
		if source_indices.is_empty() or source_indices.size() % 3 != 0 or bones.size() < verts.size() * stride or weights.size() < verts.size() * stride:
			push_error("XZOGOT_SW357_RUNTIME_SOURCE_SURFACE_INVALID " + str(surface_idx))
			return {}
		var auxiliary := PackedByteArray()
		auxiliary.resize(verts.size())
		for vertex_idx in range(verts.size()):
			var strongest := 0.0
			var best_bone := ""
			for influence in range(stride):
				var at: int = vertex_idx * stride + influence
				if weights[at] > strongest:
					strongest = weights[at]
					var binding: int = bones[at]
					if binding >= 0 and binding < skin.get_bind_count():
						best_bone = str(skin.get_bind_name(binding))
			auxiliary[vertex_idx] = 1 if strongest >= 0.25 and _is_reload_only_bone(best_bone) else 0
			removed_vertices += int(auxiliary[vertex_idx])
		var kept := PackedInt32Array()
		for idx in range(0, source_indices.size(), 3):
			var a: int = source_indices[idx]
			var b: int = source_indices[idx + 1]
			var c: int = source_indices[idx + 2]
			if a < 0 or b < 0 or c < 0 or a >= auxiliary.size() or b >= auxiliary.size() or c >= auxiliary.size():
				push_error("XZOGOT_SW357_RUNTIME_INDEX_OUT_OF_RANGE " + str(surface_idx))
				return {}
			if auxiliary[a] != 0 and auxiliary[b] != 0 and auxiliary[c] != 0:
				removed_triangles += 1
			else:
				kept.append(a)
				kept.append(b)
				kept.append(c)
		arr[Mesh.ARRAY_INDEX] = kept
		# Godot's imported GLB custom channels are decoded as float arrays,
		# whereas ArrayMesh accepts packed bytes for custom channels. Positions,
		# normals, UVs, skin indices and weights are preserved.
		for channel in range(Mesh.ARRAY_CUSTOM0, Mesh.ARRAY_CUSTOM3 + 1):
			if arr[channel] != null and not (arr[channel] is PackedByteArray):
				arr[channel] = null
		var flags: int = original.surface_get_format(surface_idx) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
		filtered.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr, [], {}, flags)
		if filtered.get_surface_count() != surface_idx + 1:
			push_error("XZOGOT_SW357_RUNTIME_FILTER_BUILD_RED " + str(surface_idx))
			return {}
		filtered.surface_set_material(surface_idx, original.surface_get_material(surface_idx))
	if removed_triangles <= 0:
		push_error("XZOGOT_SW357_RUNTIME_RELOAD_BONE_TRIANGLES_MISSING")
		return {}
	gun.mesh = filtered
	print("XZOGOT_SW357_RUNTIME_IDLE_GEOMETRY_READY removed_vertices=", removed_vertices, " removed_triangles=", removed_triangles, " original_reload_mesh_saved=true")
	return {
		"node": gun,
		"original": original,
		"idle": filtered,
		"removed_triangles": removed_triangles,
		"removed_vertices": removed_vertices,
	}

static func set_reload_props_visible(state: Dictionary, show: bool) -> bool:
	if state.is_empty():
		return false
	var gun: MeshInstance3D = state.get("node") as MeshInstance3D
	if gun == null or not is_instance_valid(gun):
		return false
	var mesh: Mesh = state.get("original" if show else "idle") as Mesh
	if mesh == null:
		return false
	if gun.mesh != mesh:
		gun.mesh = mesh
	return gun.mesh == mesh

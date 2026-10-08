class_name WeaponSourceOffstageReloadGeometry
extends RefCounted

# ORIGINAL SOURCE AUTHORITY: the real Mosin glTF puts stripper clip, rounds and
# j_clip at z=-2.50m; the original PTRS puts j_clip at z=-1.68m.
# These are non-shipping idle staging positions for reload-only attachments.
# Do not delete or transform any GLB. Retain its fully skinned mesh for reload;
# suppress ONLY 100%-reload-part triangles in HIP/ADS and restore on reload.
# MOSIN: j_clip, tag_stripper, tag_round1, tag_round2 (619 source vertices).
# PTRS: j_clip (485 source vertices). Both values measured in recovered glTF.
static func _reload_only_bone(weapon_id: String, bone: String) -> bool:
	if weapon_id == "mosin":
		return bone in ["j_clip", "tag_stripper", "tag_round1", "tag_round2"]
	if weapon_id == "ptrs":
		return bone == "j_clip"
	return false

static func _skinned_mesh(node: Node) -> MeshInstance3D:
	if node is MeshInstance3D:
		var item := node as MeshInstance3D
		if item.mesh != null and item.skin != null and not (item.mesh is PrimitiveMesh):
			return item
	for child: Node in node.get_children():
		var found := _skinned_mesh(child)
		if found != null:
			return found
	return null

static func prepare(root: Node3D, weapon_id: String) -> Dictionary:
	if root == null or weapon_id not in ["mosin", "ptrs"]:
		return {}
	var item: MeshInstance3D = _skinned_mesh(root)
	if item == null:
		push_error("XZOGOT_SOURCE_OFFSTAGE_SKIN_MISSING " + weapon_id)
		return {}
	var original: Mesh = item.mesh
	var skin: Skin = item.skin
	var filtered := ArrayMesh.new()
	var removed_vertices := 0
	var removed_triangles := 0
	var retained_triangles := 0
	for surface_idx in range(original.get_surface_count()):
		var arr: Array = original.surface_get_arrays(surface_idx)
		var verts: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		var indices: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
		var bones: PackedInt32Array = arr[Mesh.ARRAY_BONES]
		var weights: PackedFloat32Array = arr[Mesh.ARRAY_WEIGHTS]
		var stride: int = 8 if (original.surface_get_format(surface_idx) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS) != 0 else 4
		if verts.is_empty() or indices.size() % 3 != 0 or indices.is_empty() or bones.size() < verts.size() * stride or weights.size() < verts.size() * stride:
			push_error("XZOGOT_SOURCE_OFFSTAGE_SKIN_INVALID " + weapon_id + " surface=" + str(surface_idx))
			return {}
		var auxiliary := PackedByteArray()
		auxiliary.resize(verts.size())
		for vid in range(verts.size()):
			var strongest := 0.0
			var strongest_bone := ""
			for influence in range(stride):
				var at: int = vid * stride + influence
				if weights[at] > strongest:
					strongest = weights[at]
					var binding: int = bones[at]
					if binding >= 0 and binding < skin.get_bind_count():
						strongest_bone = str(skin.get_bind_name(binding))
			# Source-authoritative distance, not an invented animated pose.
			# Never remove body, scope, handle or actual barrel vertices.
			if strongest >= 0.95 and verts[vid].z < -1.0 and _reload_only_bone(weapon_id, strongest_bone):
				auxiliary[vid] = 1
				removed_vertices += 1
		var kept := PackedInt32Array()
		var mixed_triangles := 0
		for at in range(0, indices.size(), 3):
			var a: int = indices[at]
			var b: int = indices[at + 1]
			var c: int = indices[at + 2]
			if a < 0 or b < 0 or c < 0 or a >= verts.size() or b >= verts.size() or c >= verts.size():
				push_error("XZOGOT_SOURCE_OFFSTAGE_INDEX_INVALID " + weapon_id)
				return {}
			var count: int = int(auxiliary[a]) + int(auxiliary[b]) + int(auxiliary[c])
			if count == 3:
				removed_triangles += 1
			elif count == 0:
				kept.append_array(PackedInt32Array([a, b, c]))
				retained_triangles += 1
			else:
				mixed_triangles += 1
		if mixed_triangles > 0:
			# Fail closed instead of cutting genuine firearm mesh triangles.
			push_error("XZOGOT_SOURCE_OFFSTAGE_MIXED_SURFACE_RED " + weapon_id + " count=" + str(mixed_triangles))
			return {}
		var idle_verts := verts.duplicate()
		for vid in range(verts.size()):
			if auxiliary[vid] != 0:
				# Only de-indexed vertices become zero. Bounds must exclude the
				# offstage reload parts; these zero vertices never render.
				idle_verts[vid] = Vector3.ZERO
		arr[Mesh.ARRAY_VERTEX] = idle_verts
		# Keep same number and ordering of material surfaces. Fully hidden
		# surfaces receive only a zero-area triangle at a de-indexed origin.
		if kept.is_empty():
			if verts.size() < 3:
				push_error("XZOGOT_SOURCE_OFFSTAGE_DEGENERATE_SURFACE_RED " + weapon_id)
				return {}
			kept = PackedInt32Array([0, 0, 0])
		arr[Mesh.ARRAY_INDEX] = kept
		for custom_channel in range(Mesh.ARRAY_CUSTOM0, Mesh.ARRAY_CUSTOM3 + 1):
			if arr[custom_channel] != null and not (arr[custom_channel] is PackedByteArray):
				arr[custom_channel] = null
		var flags: int = original.surface_get_format(surface_idx) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS
		filtered.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr, [], {}, flags)
		filtered.surface_set_material(surface_idx, original.surface_get_material(surface_idx))
	if removed_triangles <= 0 or removed_vertices <= 0:
		push_error("XZOGOT_SOURCE_OFFSTAGE_NO_RELOAD_TRIANGLES " + weapon_id)
		return {}
	item.mesh = filtered
	print("XZOGOT_SOURCE_OFFSTAGE_IDLE_READY ", weapon_id,
		" removed_vertices=", removed_vertices, " triangles=", removed_triangles,
		" core_triangles=", retained_triangles, " reload_mesh_original_preserved=true")
	return {
		"node": item, "idle": filtered, "original": original,
		"removed_vertices": removed_vertices,
		"removed_triangles": removed_triangles,
		"retained_triangles": retained_triangles,
	}

static func set_reload_visible(state: Dictionary, show_original: bool) -> bool:
	var gun: MeshInstance3D = state.get("node") as MeshInstance3D
	if gun == null or not is_instance_valid(gun):
		return false
	var mesh: Mesh = state.get("original" if show_original else "idle") as Mesh
	if mesh == null:
		return false
	gun.mesh = mesh
	return gun.mesh == mesh

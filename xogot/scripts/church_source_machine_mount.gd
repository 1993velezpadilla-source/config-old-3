class_name ChurchSourceMachineMount
extends RefCounted

# Visual-only reference attachment: NEVER modifies machine gameplay, costs,
# network state, physics colliders or interaction timing.
const DIRECTORY := "res://assets/reference/church/machines/"
const SOURCE_ID := "PAVLOV_UE421_WORKSHOP_REFERENCE"

static func _mesh_corners(node: Node, frame: Node3D, points: Array[Vector3]) -> void:
	if node is MeshInstance3D:
		var mi: MeshInstance3D = node as MeshInstance3D
		if mi.mesh != null:
			var a: AABB = mi.get_aabb()
			for ix in range(2):
				for iy in range(2):
					for iz in range(2):
						var p := a.position + Vector3(a.size.x * float(ix), a.size.y * float(iy), a.size.z * float(iz))
						points.append(frame.to_local(mi.to_global(p)))
	for child: Node in node.get_children():
		_mesh_corners(child, frame, points)

static func attach(church: Node3D, machine_name: String, parts: Array[String], desired_size: Vector3) -> bool:
	var body: StaticBody3D = church.get_node_or_null(machine_name) as StaticBody3D
	if body == null or parts.is_empty():
		return false
	var source_root := Node3D.new()
	source_root.name = "ArchivedWorkshopReference3D"
	body.add_child(source_root)
	for part: String in parts:
		var path: String = DIRECTORY + part + ".glb"
		if not ResourceLoader.exists(path):
			source_root.queue_free()
			return false
		var resource: PackedScene = load(path) as PackedScene
		if resource == null:
			source_root.queue_free()
			return false
		var model: Node3D = resource.instantiate() as Node3D
		if model == null:
			source_root.queue_free()
			return false
		model.name = "SourcePart_" + part
		source_root.add_child(model)
	var pts: Array[Vector3] = []
	_mesh_corners(source_root, source_root, pts)
	if pts.is_empty():
		source_root.queue_free()
		return false
	var pmin: Vector3 = pts[0]
	var pmax: Vector3 = pts[0]
	for p: Vector3 in pts:
		pmin = pmin.min(p)
		pmax = pmax.max(p)
	var dims: Vector3 = pmax - pmin
	if dims.x <= 0.0001 or dims.y <= 0.0001 or dims.z <= 0.0001:
		source_root.queue_free()
		return false
	# The archived Mystery Box candidate contains an extreme 88m vertical
	# source bound vs 5.7m depth. It produces a narrow pole when fitted.
	# Reject its current visual rather than stretching it or falsely approving.
	if machine_name == "MysteryBoxSocket" and dims.y > dims.z * 6.0:
		body.set_meta("source_reference_visual_rejected", true)
		body.set_meta("source_reference_reject_reason", "ARCHIVE_BOX_MESH_ABNORMAL_ASPECT")
		body.set_meta("source_reference_raw_size", dims)
		print("XZOGOT_CHURCH_MYSTERY_SOURCE_VISUAL_REJECTED_BAD_PROPORTIONS ", dims)
		source_root.queue_free()
		return false
	# Preserve proportional source geometry. Never axis-squash visuals to fake a
	# successful matching machine; compare actual screenshot silhouette later.
	var uniform: float = minf(desired_size.x / dims.x, minf(desired_size.y / dims.y, desired_size.z / dims.z))
	if not is_finite(uniform) or uniform < 0.000001:
		source_root.queue_free()
		return false
	source_root.scale = Vector3.ONE * uniform
	source_root.position = -(pmin + pmax) * 0.5 * uniform
	# Hide ONLY the static primitive box; authored interactive animation nodes
	# remain operational until visually audited and separately replaced.
	for child: Node in body.get_children():
		if child is MeshInstance3D and child != source_root:
			var mesh: MeshInstance3D = child as MeshInstance3D
			if mesh.mesh is BoxMesh:
				mesh.visible = false
	body.set_meta("source_reference_visual_loaded", true)
	body.set_meta("source_reference_provenance", SOURCE_ID)
	body.set_meta("source_reference_parts", parts)
	body.set_meta("source_reference_uniform_scale", uniform)
	body.add_to_group("church_source_machine_visual")
	print("XZOGOT_CHURCH_ARCHIVED_SOURCE_MACHINE_MOUNTED ", machine_name, " parts=", parts.size(), " bounds=", dims)
	return true

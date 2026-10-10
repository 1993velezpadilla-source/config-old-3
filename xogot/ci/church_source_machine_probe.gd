extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, explanation: String) -> void:
	push_error("CHURCH_SOURCE_MACHINE_PROBE: " + explanation)
	quit(code)

func _real_mesh_count(node: Node) -> int:
	var count: int = 0
	if node is MeshInstance3D and (node as MeshInstance3D).mesh != null:
		count += 1
	for child: Node in node.get_children():
		count += _real_mesh_count(child)
	return count

func _run() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "Church map missing")
		return
	var church: Node = packed.instantiate()
	root.add_child(church)
	await process_frame
	var names: Array[String] = ["MysteryBoxSocket", "SanctumForge", "PowerSwitch"]
	for machine_name: String in names:
		var machine: StaticBody3D = church.get_node_or_null(machine_name) as StaticBody3D
		if machine == null:
			_fail(3, "Active machine backend absent: " + machine_name)
			return
		if not bool(machine.get_meta("source_reference_visual_loaded", false)):
			_fail(4, "Source GLB not mounted as actual live model: " + machine_name)
			return
		if str(machine.get_meta("source_reference_provenance", "")) != "PAVLOV_UE421_WORKSHOP_REFERENCE":
			_fail(5, "Source provenance label missing: " + machine_name)
			return
		var ref_root: Node = machine.get_node_or_null("ArchivedWorkshopReference3D")
		if ref_root == null or _real_mesh_count(ref_root) == 0:
			_fail(6, "No original-source triangles imported: " + machine_name)
			return
		# Godot dynamically assigns a nonliteral name to new physics
		# children. Discover by NODE TYPE, not a guessed textual name.
		var collision: CollisionShape3D = null
		for child: Node in machine.get_children():
			if child is CollisionShape3D:
				collision = child as CollisionShape3D
				break
		if collision == null or not (collision.shape is BoxShape3D):
			_fail(7, "Gameplay collider removed by visual replacement: " + machine_name)
			return
		if not machine.has_method("interact"):
			_fail(8, "Visual replacement destroyed gameplay interaction method")
			return
		print("XZOGOT_CHURCH_FUNCTIONAL_SOURCE_MACHINE_3D_GREEN ", machine_name,
			" meshes=", _real_mesh_count(ref_root),
			" parts=", (machine.get_meta("source_reference_parts", []) as Array).size())
	if get_nodes_in_group("church_source_machine_visual").size() != names.size():
		_fail(9, "Three archived machine reference visuals must be mounted")
		return
	var box: Node = church.get_node_or_null("MysteryBoxSocket")
	var source: Node = box.get_node_or_null("ArchivedWorkshopReference3D")
	if source == null:
		_fail(10, "Archived animated box visual missing")
		return
	var actor: AnimationPlayer = null
	var stack: Array[Node] = [source]
	while not stack.is_empty():
		var obj: Node = stack.pop_back()
		if obj is AnimationPlayer:
			actor = obj as AnimationPlayer
			break
		for child: Node in obj.get_children():
			stack.append(child)
	if actor == null or not actor.has_animation("open") or not actor.has_animation("weapon_rise"):
		_fail(11, "Source box missing real open/weapon rise skeletal clips")
		return
	box.call("_animate_mystery_box")
	if not bool(box.get_meta("source_box_open_animation_played", false)):
		_fail(12, "Source box model imported but interaction does not actually animate")
		return
	print("XZOGOT_CHURCH_SOURCE_BOX_OPEN_AUTHORED_ANIMATION_GREEN")
	print("XZOGOT_CHURCH_THREE_ARCHIVED_MACHINE_MODELS_MOUNTED_GREEN")
	print("XZOGOT_CHURCH_MACHINE_GAMEPLAY_BACKEND_COLLISION_PRESERVED")
	church.queue_free()
	await process_frame
	quit(0)

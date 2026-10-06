extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NACHT_FULL_MAP_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed := load("res://nacht_full_map.tscn") as PackedScene
	if packed == null:
		_fail(2, "nacht_full_map.tscn missing")
		return

	var scene := packed.instantiate()
	root.add_child(scene)

	var ready := false
	for _i in range(2400):
		await create_timer(0.05).timeout
		if bool(scene.get_meta("nacht_full_map_ready", false)):
			ready = true
			break
	if not ready:
		_fail(3, "full map did not become ready")
		return

	var packages := int(scene.get_meta("source_package_count", -1))
	var meshes := int(scene.get_meta("source_mesh_count", -1))
	var source_instances := int(scene.get_meta("source_instance_count", -1))
	var runtime_instances := int(scene.get_meta("runtime_instance_count", -1))
	var missing_meshes := int(scene.get_meta("missing_mesh_count", -1))
	var source_actors := int(scene.get_meta("source_actor_anchor_count", -1))
	var runtime_actors := int(scene.get_meta("runtime_actor_anchor_count", -1))
	var collisions := int(scene.get_meta("world_collision_count", -1))
	var source_lights := int(scene.get_meta("source_light_count", -1))
	var runtime_lights := int(scene.get_meta("runtime_light_count", -1))

	if packages != 3871:
		_fail(4, "package authority mismatch " + str(packages))
		return
	if meshes <= 0:
		_fail(5, "no source meshes")
		return
	if source_instances <= 0 or runtime_instances != source_instances:
		_fail(6, "instance coverage mismatch %d/%d" % [runtime_instances, source_instances])
		return
	if missing_meshes != 0:
		_fail(7, "missing mesh bridge count " + str(missing_meshes))
		return
	if source_actors <= 0 or runtime_actors != source_actors:
		_fail(8, "actor coverage mismatch %d/%d" % [runtime_actors, source_actors])
		return
	if get_nodes_in_group("nacht_source_actor").size() != source_actors:
		_fail(9, "actor runtime group mismatch")
		return
	if collisions <= 0:
		_fail(10, "no world collision generated")
		return
	if source_lights <= 0 or runtime_lights != source_lights:
		_fail(11, "light coverage mismatch %d/%d" % [runtime_lights, source_lights])
		return

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	var weapon := scene.get_node_or_null("Player/Weapon")
	var round_manager := scene.get_node_or_null("RoundManager")
	if player == null or weapon == null or round_manager == null:
		_fail(12, "player weapon or round manager missing")
		return
	if bool(round_manager.get("auto_start")):
		_fail(13, "round manager must remain gated until Nacht source spawns/nav are wired")
		return

	print(
		"XZOGOT_NACHT_FULL_MAP_PROBE_GREEN ",
		"packages=", packages,
		" meshes=", meshes,
		" instances=", runtime_instances,
		" actors=", runtime_actors,
		" collisions=", collisions,
		" lights=", runtime_lights,
		" player=", player.global_position
	)
	scene.queue_free()
	await process_frame
	quit(0)

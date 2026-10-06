extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NUKETOWN_FULL_MAP_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed := load("res://nuketown_full_map.tscn") as PackedScene
	if packed == null:
		_fail(2, "scene missing")
		return
	var scene := packed.instantiate()
	root.add_child(scene)

	var ready := false
	for _attempt in range(900):
		await create_timer(0.05).timeout
		if bool(scene.get_meta("nuketown_full_map_ready", false)):
			ready = true
			break
	if not ready:
		_fail(3, "full map never became ready")
		return

	var mesh_count := int(scene.get_meta("source_mesh_count", -1))
	var instance_count := int(scene.get_meta("source_instance_count", -1))
	var actor_count := int(scene.get_meta("source_actor_anchor_count", -1))
	var collision_count := int(scene.get_meta("source_collision_count", -1))
	var spawn_count := int(scene.get_meta("source_spawn_count", -1))
	var wallbuy_count := int(scene.get_meta("source_wallbuy_count", -1))
	var mystery_count := int(scene.get_meta("source_mystery_count", -1))
	var ladder_count := int(scene.get_meta("source_ladder_count", -1))

	if mesh_count != 52:
		_fail(4, "mesh count mismatch " + str(mesh_count))
		return
	if instance_count != 124:
		_fail(5, "instance count mismatch " + str(instance_count))
		return
	if actor_count != 233:
		_fail(6, "actor anchor count mismatch " + str(actor_count))
		return
	if collision_count < 124:
		_fail(7, "collision coverage too low " + str(collision_count))
		return
	if spawn_count != 3:
		_fail(8, "source spawn count mismatch " + str(spawn_count))
		return
	if wallbuy_count != 3:
		_fail(9, "source wallbuy count mismatch " + str(wallbuy_count))
		return
	if mystery_count != 1:
		_fail(10, "source mystery count mismatch " + str(mystery_count))
		return
	if ladder_count != 2:
		_fail(11, "source ladder count mismatch " + str(ladder_count))
		return

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		_fail(12, "player missing")
		return
	if not player.has_meta("nuketown_source_spawn_export"):
		_fail(13, "player was not placed from source spawn")
		return

	if get_nodes_in_group("nuketown_source_spawn").size() != 3:
		_fail(14, "spawn marker group mismatch")
		return
	if get_nodes_in_group("nuketown_source_wallbuy").size() != 3:
		_fail(15, "wallbuy marker group mismatch")
		return
	var wallbuy_ids: Array[String] = []
	for node: Node in get_nodes_in_group("nuketown_source_wallbuy"):
		wallbuy_ids.append(str(node.get_meta("source_weapon_id", "")))
		if not bool(node.get_meta("source_price_known", false)):
			_fail(18, "source wallbuy price truth missing")
			return
		if int(node.get_meta("source_price", -1)) != 0:
			_fail(19, "source wallbuy price mismatch " + str(node.get_meta("source_price", -1)))
			return
		if bool(node.get_meta("source_interaction_ready", true)):
			_fail(20, "source-only wallbuy was silently aliased into current catalog")
			return
	wallbuy_ids.sort()
	var expected_wallbuy_ids: Array[String] = ["crminigun", "crraygun", "stingray"]
	expected_wallbuy_ids.sort()
	if wallbuy_ids != expected_wallbuy_ids:
		_fail(21, "source wallbuy weapon ids mismatch " + str(wallbuy_ids))
		return
	if get_nodes_in_group("nuketown_source_mystery").size() != 1:
		_fail(16, "mystery marker group mismatch")
		return
	var mystery_node: Node = get_nodes_in_group("nuketown_source_mystery")[0]
	if int(mystery_node.get_meta("source_item_pool_count", -1)) != 52:
		_fail(22, "source mystery pool count mismatch")
		return
	if not bool(mystery_node.get_meta("source_replicated", false)):
		_fail(23, "source mystery replication flag missing")
		return
	if not bool(mystery_node.get_meta("source_always_relevant", false)):
		_fail(24, "source mystery always-relevant flag missing")
		return
	if bool(mystery_node.get_meta("source_interaction_ready", true)):
		_fail(25, "source mystery pool was silently replaced by current catalog")
		return
	if get_nodes_in_group("nuketown_world_collision").size() < 124:
		_fail(17, "collision group mismatch")
		return

	print(
		"XZOGOT_NUKETOWN_FULL_MAP_PROBE_GREEN ",
		"meshes=", mesh_count,
		" instances=", instance_count,
		" actors=", actor_count,
		" collisions=", collision_count,
		" spawns=", spawn_count,
		" wallbuys=", wallbuy_count,
		" mystery=", mystery_count,
		" ladders=", ladder_count,
		" player=", player.global_position
	)
	scene.queue_free()
	await process_frame
	quit(0)

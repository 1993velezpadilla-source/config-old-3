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
	var interactable_count := int(scene.get_meta("source_interactable_count", -1))
	var covered_actor_count := int(scene.get_meta("source_covered_actor_count", -1))
	var coverage_class_count := int(scene.get_meta("source_coverage_class_count", -1))
	var navigation_polygon_count := int(scene.get_meta("navigation_polygon_count", -1))
	var zombie_spawn_anchor_count := int(scene.get_meta("zombie_spawn_anchor_count", -1))
	var source_audio_ambient_count := int(scene.get_meta("source_audio_ambient_count", -1))
	var source_audio_source_stream_count := int(scene.get_meta("source_audio_source_stream_count", -1))
	var source_audio_fallback_stream_count := int(scene.get_meta("source_audio_fallback_stream_count", -1))
	var source_audio_missing_stream_count := int(scene.get_meta("source_audio_missing_stream_count", -1))
	var source_audio_join_sound_count := int(scene.get_meta("source_audio_join_sound_count", -1))

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
	if covered_actor_count != 233 or coverage_class_count != 37:
		_fail(26, "source actor coverage mismatch")
		return
	if get_nodes_in_group("nuketown_source_covered_actor").size() != 233:
		_fail(27, "covered source actor group mismatch")
		return
	if interactable_count != 6:
		_fail(28, "source interactable adapter count mismatch " + str(interactable_count))
		return
	if get_nodes_in_group("nuketown_source_wallbuy_runtime").size() != 3:
		_fail(29, "wallbuy runtime adapter mismatch")
		return
	if get_nodes_in_group("nuketown_source_mystery_runtime").size() != 1:
		_fail(30, "mystery runtime adapter mismatch")
		return
	if get_nodes_in_group("nuketown_source_ladder_runtime").size() != 2:
		_fail(31, "ladder runtime adapter mismatch")
		return
	if source_audio_ambient_count != 4:
		_fail(55, "source ambient runtime count mismatch " + str(source_audio_ambient_count))
		return
	if source_audio_join_sound_count != 3:
		_fail(56, "source join-sound route count mismatch " + str(source_audio_join_sound_count))
		return
	if get_nodes_in_group("nuketown_source_ambient_runtime").size() != 4:
		_fail(57, "source ambient runtime group mismatch")
		return
	if get_nodes_in_group("nuketown_source_join_audio_runtime").size() != 1:
		_fail(58, "source join audio router missing")
		return
	if source_audio_source_stream_count + source_audio_fallback_stream_count + source_audio_missing_stream_count != 4:
		_fail(59, "source ambient disposition total mismatch")
		return
	if navigation_polygon_count <= 0:
		_fail(46, "source-collision navigation bake produced no polygons")
		return
	if zombie_spawn_anchor_count < 4:
		_fail(47, "insufficient zombie spawn anchors " + str(zombie_spawn_anchor_count))
		return
	if get_nodes_in_group("zombie_path_network").size() != 1:
		_fail(48, "Nuketown zombie path network missing or duplicated")
		return
	if get_nodes_in_group("nuketown_zombie_spawn_anchor").size() != zombie_spawn_anchor_count:
		_fail(49, "zombie spawn anchor group mismatch")
		return
	var nav_runtime: Node = get_nodes_in_group("zombie_path_network")[0]
	var nav_spawns: Array[Node] = []
	for nav_spawn: Node in get_nodes_in_group("nuketown_zombie_spawn_anchor"):
		nav_spawns.append(nav_spawn)
	if nav_spawns.size() >= 2:
		var a := (nav_spawns[0] as Node3D).global_position
		var b := (nav_spawns[1] as Node3D).global_position
		var path: Array[Vector3] = nav_runtime.call("request_path", a, b) as Array[Vector3]
		if path.size() < 2:
			_fail(50, "navigation path query did not connect perimeter spawns")
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
		if bool(node.get_meta("source_item_catalog_ready", true)):
			_fail(20, "source-only wallbuy was silently added to the native catalog")
			return
		if not bool(node.get_meta("source_interaction_ready", false)):
			_fail(36, "source wallbuy external bridge is not runtime-ready")
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
	if not bool(mystery_node.get_meta("source_interaction_ready", false)):
		_fail(25, "source mystery runtime bridge not ready")
		return
	if not bool(mystery_node.get_meta("source_price_known", false)):
		_fail(37, "mystery price truth missing")
		return
	if int(mystery_node.get_meta("source_price", -1)) != 950:
		_fail(38, "mystery source price mismatch")
		return
	if get_nodes_in_group("nuketown_world_collision").size() < 124:
		_fail(17, "collision group mismatch")
		return

	var runtime_wallbuy: Node = get_nodes_in_group("nuketown_source_wallbuy_runtime")[0]
	if not bool(runtime_wallbuy.call("interact", player)):
		_fail(32, "source wallbuy runtime interaction failed")
		return
	var weapon := player.get_node_or_null("Weapon")
	if weapon == null or not weapon.has_method("get_source_external_item_id"):
		_fail(33, "source external weapon bridge missing")
		return
	if str(weapon.call("get_source_external_item_id")).is_empty():
		_fail(34, "source wallbuy did not preserve external item id")
		return
	if not bool(weapon.call("is_source_external_placeholder")):
		_fail(35, "external source item placeholder was not explicit")
		return

	var mystery_runtime: Node = get_nodes_in_group("nuketown_source_mystery_runtime")[0]
	if str(mystery_runtime.get("source_sfx_path")).get_file() != "music_box_00.wav":
		_fail(60, "mystery source audio path not wired")
		return
	if not ResourceLoader.exists(str(mystery_runtime.get("source_sfx_fallback"))):
		_fail(61, "mystery fallback audio missing")
		return
	var points_before_mystery := int(player.call("get_points"))
	if points_before_mystery != 500:
		_fail(39, "unexpected starting points before mystery test " + str(points_before_mystery))
		return
	if bool(mystery_runtime.call("interact", player)):
		_fail(40, "mystery incorrectly accepted insufficient points")
		return
	player.call("add_points", 450)
	if int(player.call("get_points")) != 950:
		_fail(41, "mystery affordability setup failed")
		return
	if not bool(mystery_runtime.call("interact", player)):
		_fail(42, "source mystery runtime interaction failed")
		return
	if int(player.call("get_points")) != 0:
		_fail(43, "mystery did not subtract exact source price")
		return
	var mystery_source_id := str(weapon.call("get_source_external_item_id"))
	var source_pool: Array = mystery_node.get_meta("source_item_pool", [])
	if not source_pool.has(mystery_source_id):
		_fail(44, "mystery result not in exact source pool " + mystery_source_id)
		return
	if not bool(weapon.call("is_source_external_placeholder")):
		_fail(45, "mystery external item placeholder was not explicit")
		return

	var round_manager := scene.get_node_or_null("RoundManager")
	if round_manager == null:
		_fail(51, "round manager missing from full map")
		return
	if not bool(scene.get_meta("round_manager_activated_from_source_nav", false)):
		_fail(52, "round system did not wait for source navigation")
		return
	round_manager.call("start_next_round")
	var probe_zombie: Node = round_manager.call("spawn_one") as Node
	if probe_zombie == null:
		_fail(53, "round manager could not spawn on Nuketown navigation anchors")
		return
	if str(probe_zombie.get_meta("spawn_entry_kind", "")) != "offscreen":
		_fail(54, "Nuketown zombie did not use direct nav entry")
		return
	round_manager.call("dev_clear_zombies")

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

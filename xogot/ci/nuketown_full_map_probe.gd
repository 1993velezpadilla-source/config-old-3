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
	var source_skeletal_visual_count := int(scene.get_meta("source_skeletal_visual_count", -1))
	var source_skeletal_clip_count := int(scene.get_meta("source_skeletal_clip_count", -1))
	var navigation_polygon_count := int(scene.get_meta("navigation_polygon_count", -1))
	var zombie_spawn_anchor_count := int(scene.get_meta("zombie_spawn_anchor_count", -1))
	var source_audio_ambient_count := int(scene.get_meta("source_audio_ambient_count", -1))
	var source_audio_source_stream_count := int(scene.get_meta("source_audio_source_stream_count", -1))
	var source_audio_fallback_stream_count := int(scene.get_meta("source_audio_fallback_stream_count", -1))
	var source_audio_missing_stream_count := int(scene.get_meta("source_audio_missing_stream_count", -1))
	var source_audio_join_sound_count := int(scene.get_meta("source_audio_join_sound_count", -1))
	var source_loader := scene.get_node_or_null("NuketownSourceWorld")
	if source_loader == null:
		_fail(93, "Nuketown source loader missing")
		return
	var alias_resolved := int(source_loader.get_meta("xziel_benchmark_material_alias_resolved_count", -1))
	var alias_hits := int(source_loader.get_meta("xziel_benchmark_material_alias_hits", -1))
	var textured_materials := int(source_loader.get_meta("xziel_benchmark_material_textured_count", -1))
	var flat_fallbacks := int(source_loader.get_meta("xziel_benchmark_material_flat_fallback_count", -1))
	if alias_resolved < 100:
		_fail(94, "source material alias resolver recovered too few mappings " + str(alias_resolved))
		return
	if alias_hits <= 0:
		_fail(95, "source material aliases were resolved but never consumed")
		return
	if textured_materials <= 132:
		_fail(96, "source material texture recovery did not improve baseline " + str(textured_materials))
		return
	if flat_fallbacks >= 529:
		_fail(97, "source flat fallback count did not improve baseline " + str(flat_fallbacks))
		return

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
	if source_skeletal_visual_count != 3:
		_fail(98, "source skeletal visual count mismatch " + str(source_skeletal_visual_count))
		return
	if source_skeletal_clip_count != 9:
		_fail(99, "source skeletal clip count mismatch " + str(source_skeletal_clip_count))
		return
	var skeletal_visuals := get_nodes_in_group("nuketown_source_skeletal_visual")
	if skeletal_visuals.size() != 3:
		_fail(100, "source skeletal visual group mismatch " + str(skeletal_visuals.size()))
		return
	for skeletal_visual: Node in skeletal_visuals:
		if str(skeletal_visual.get_meta("source_xzsk_file", "")).is_empty():
			_fail(101, "source skeletal visual missing exact XZSK identity")
			return
		if str(skeletal_visual.get_meta("source_skeleton_hash", "")).is_empty():
			_fail(102, "source skeletal visual missing skeleton hash")
			return
		if not bool(skeletal_visual.get_meta("source_transform_from_cooked_component", false)):
			_fail(103, "source skeletal visual lost exact cooked-component transform authority")
			return
		if bool(skeletal_visual.get_meta("source_animation_playback_decoded", true)):
			_fail(104, "source skeletal visual invented animation playback state")
			return
	print(
		"XZOGOT_NUKETOWN_SKELETAL_RUNTIME_GREEN visuals=",
		source_skeletal_visual_count,
		" clips=", source_skeletal_clip_count
	)
	var expected_dispositions := {
		"Enter_your_key_C": "PAVLOV_MENU_KEY_FLOW_EXCLUDED_FROM_XOGOT_SHIPPING",
		"OldFashionedGod_C": "PAVLOV_ADMIN_GOD_DAMAGE_FLOW_EXCLUDED_FROM_XOGOT_SHIPPING",
		"disgod_C": "PAVLOV_ADMIN_DISABLE_GOD_FLOW_EXCLUDED_FROM_XOGOT_SHIPPING",
		"speed_C": "PAVLOV_ADMIN_SPEED_HELPER_EXCLUDED_FROM_XOGOT_SHIPPING",
		"tpout1_C": "PAVLOV_ADMIN_TELEPORT_WHITELIST_EXCLUDED_FROM_XOGOT_SHIPPING",
		"viptp_C": "PAVLOV_VIP_TELEPORT_WHITELIST_EXCLUDED_FROM_XOGOT_SHIPPING",
		"NewBlueprint_11_C": "PAVLOV_SKIN_SETTER_REPLACED_BY_XOGOT_PLAYER_SKINS",
		"NewBlueprint_19_C": "PAVLOV_SKIN_SETTER_REPLACED_BY_XOGOT_PLAYER_SKINS",
		"NewBlueprint_C": "MYSTERY_BOX_SOURCE_CLEANUP_HELPER_REPLACED",
		"cash_text_C": "PAVLOV_CASH_TEXT_REPLACED_BY_XOGOT_HUD",
		"GamemodeDetector_C": "PAVLOV_GAMEMODE_DETECTOR_REPLACED_BY_XOGOT_MATCH_RUNTIME",
	}
	var seen_dispositions: Dictionary = {}
	for source_actor: Node in get_nodes_in_group("nuketown_source_covered_actor"):
		var source_class := str(source_actor.get_meta("source_class_name", ""))
		if expected_dispositions.has(source_class):
			seen_dispositions[source_class] = str(source_actor.get_meta("source_disposition", ""))
	for source_class_var: Variant in expected_dispositions.keys():
		var source_class := str(source_class_var)
		if not seen_dispositions.has(source_class):
			_fail(76, "custom Blueprint disposition missing " + source_class)
			return
		if str(seen_dispositions[source_class]) != str(expected_dispositions[source_class]):
			_fail(77, "custom Blueprint disposition mismatch " + source_class + " -> " + str(seen_dispositions[source_class]))
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
	var source_audio_runtime: Node = get_nodes_in_group("nuketown_source_audio_runtime")[0]
	if int(source_audio_runtime.call("get_join_route_count")) != 3:
		_fail(62, "source join route count mismatch")
		return
	if absf(float(source_audio_runtime.call("get_join_delay", "JoinSounds_C")) - 2.0) > 0.001:
		_fail(63, "base join delay mismatch")
		return
	if absf(float(source_audio_runtime.call("get_join_delay", "JoinSounds_2_C")) - 8.0) > 0.001:
		_fail(64, "creator join delay mismatch")
		return
	if absf(float(source_audio_runtime.call("get_join_delay", "JoinSounds_3_C")) - 13.0) > 0.001:
		_fail(65, "admin join delay mismatch")
		return
	if not bool(source_audio_runtime.call("join_source_decision", "JoinSounds_C", "", "", false)):
		_fail(66, "base join source route should be unconditional")
		return
	if not bool(source_audio_runtime.call(
		"join_source_decision",
		"JoinSounds_2_C",
		"76561198801811658",
		"",
		false
	)):
		_fail(67, "creator Steam whitelist truth mismatch")
		return
	if bool(source_audio_runtime.call(
		"join_source_decision",
		"JoinSounds_2_C",
		"not_whitelisted",
		"",
		false
	)):
		_fail(68, "creator whitelist accepted unknown Steam identity")
		return
	if not bool(source_audio_runtime.call(
		"join_source_decision",
		"JoinSounds_3_C",
		"",
		"Psycho_gamer",
		true
	)):
		_fail(69, "admin Shack whitelist truth mismatch")
		return
	if bool(source_audio_runtime.call(
		"join_source_decision",
		"JoinSounds_3_C",
		"",
		"not_whitelisted",
		true
	)):
		_fail(70, "admin whitelist accepted unknown Shack identity")
		return
	if source_audio_source_stream_count != 4:
		_fail(71, "all four ambient source WAVs were not active " + str(source_audio_source_stream_count))
		return
	if source_audio_fallback_stream_count != 0:
		_fail(72, "ambient fallback used despite mounted source WAVs " + str(source_audio_fallback_stream_count))
		return
	if source_audio_missing_stream_count != 0:
		_fail(73, "mounted source WAV route still missing " + str(source_audio_missing_stream_count))
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
	var player := scene.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		_fail(12, "player missing")
		return

	var nav_runtime: Node = get_nodes_in_group("zombie_path_network")[0]
	var nav_spawns: Array[Node] = []
	for nav_spawn: Node in get_nodes_in_group("nuketown_zombie_spawn_anchor"):
		nav_spawns.append(nav_spawn)
	if nav_spawns.size() != 10:
		_fail(78, "expected exactly 10 nav-generated zombie spawns, got " + str(nav_spawns.size()))
		return
	var proven_spawn_routes := 0
	for spawn_node: Node in nav_spawns:
		if not (spawn_node is Node3D):
			_fail(79, "zombie spawn anchor is not Node3D")
			return
		var spawn_pos := (spawn_node as Node3D).global_position
		var path_to_player: Array[Vector3] = nav_runtime.call(
			"request_path",
			spawn_pos,
			player.global_position
		) as Array[Vector3]
		if path_to_player.size() < 2:
			_fail(
				80,
				"nav spawn cannot route to player " +
				str(spawn_node.get_meta("spawn_id", spawn_node.name)) +
				" path=" + str(path_to_player.size())
			)
			return
		proven_spawn_routes += 1
	if proven_spawn_routes != 10:
		_fail(81, "not all nav spawn routes were proven " + str(proven_spawn_routes))
		return
	print("XZOGOT_NUKETOWN_NAV_ALL_SPAWNS_GREEN routes=", proven_spawn_routes)

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
	if not bool(mystery_runtime.get_meta("source_mystery_visual_ready", false)):
		_fail(88, "Mystery Box source skinned visual not ready")
		return
	if int(mystery_runtime.get_meta("source_mystery_animation_count", -1)) != 7:
		_fail(89, "Mystery Box source animation count mismatch " + str(mystery_runtime.get_meta("source_mystery_animation_count", -1)))
		return
	if get_nodes_in_group("nuketown_source_mystery_visual").size() != 1:
		_fail(90, "Mystery Box source visual group mismatch")
		return
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
	if not bool(mystery_runtime.get_meta("mystery_source_anim_active", false)):
		_fail(91, "Mystery Box did not start the recovered source animation sequence")
		return
	var mystery_sequence: Array = mystery_runtime.get_meta("mystery_source_anim_sequence", [])
	if mystery_sequence.size() != 3:
		_fail(92, "Mystery Box source animation sequence incomplete " + str(mystery_sequence))
		return
	var mystery_source_id := str(weapon.call("get_source_external_item_id"))
	var source_pool: Array = mystery_node.get_meta("source_item_pool", [])
	if not source_pool.has(mystery_source_id):
		_fail(44, "mystery result not in exact source pool " + mystery_source_id)
		return
	if not bool(weapon.call("is_source_external_placeholder")):
		_fail(45, "mystery external item placeholder was not explicit")
		return
	if not bool(mystery_runtime.get_meta("source_sfx_active", false)):
		_fail(74, "Mystery Box did not play mounted source WAV")
		return
	var mystery_active_sfx := str(mystery_runtime.get_meta("active_sfx_path", ""))
	if not mystery_active_sfx.ends_with("music_box_00.wav"):
		_fail(75, "Mystery Box active source WAV mismatch " + mystery_active_sfx)
		return

	var round_manager := scene.get_node_or_null("RoundManager")
	if round_manager == null:
		_fail(51, "round manager missing from full map")
		return
	if not bool(scene.get_meta("round_manager_activated_from_source_nav", false)):
		_fail(52, "round system did not wait for source navigation")
		return
	# Keep CI deterministic: disable first-round auto timer, then manually start
	# R1. Once started, RoundManager continues processing even with auto_start
	# false, so clearing R1 must naturally advance to R2.
	round_manager.set("auto_start", false)
	round_manager.set("round_break", 0.15)
	round_manager.call("reset_network_match")
	round_manager.call("start_next_round")
	if int(round_manager.call("get_round")) != 1:
		_fail(82, "manual Nuketown round 1 did not start")
		return
	var round_one_total := int(round_manager.call("get_round_total"))
	if round_one_total <= 0:
		_fail(83, "Nuketown round 1 population is empty")
		return
	var probe_zombie: Node = round_manager.call("spawn_one") as Node
	if probe_zombie == null:
		_fail(53, "round manager could not spawn on Nuketown navigation anchors")
		return
	if str(probe_zombie.get_meta("spawn_entry_kind", "")) != "offscreen":
		_fail(54, "Nuketown zombie did not use direct nav entry")
		return
	if int(round_manager.call("get_alive")) != 1:
		_fail(84, "round manager alive count did not register Nuketown zombie")
		return
	round_manager.call("dev_clear_zombies")
	var round_two_started := false
	for _round_wait in range(80):
		await create_timer(0.05).timeout
		if int(round_manager.call("get_round")) >= 2:
			round_two_started = true
			break
	if not round_two_started:
		_fail(
			85,
			"Nuketown round transition stalled at round " +
			str(round_manager.call("get_round"))
		)
		return
	if int(round_manager.call("get_round")) != 2:
		_fail(86, "unexpected Nuketown next round " + str(round_manager.call("get_round")))
		return
	if int(round_manager.call("get_round_total")) <= round_one_total:
		_fail(87, "round 2 population did not grow from round 1")
		return
	print(
		"XZOGOT_NUKETOWN_ROUND_TRANSITION_GREEN ",
		"round1_total=", round_one_total,
		" round2_total=", round_manager.call("get_round_total")
	)
	round_manager.call("set_dev_no_zombies", true)

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
		" skeletal_visuals=", source_skeletal_visual_count,
		" skeletal_clips=", source_skeletal_clip_count,
		" player=", player.global_position
	)
	scene.queue_free()
	await process_frame
	quit(0)

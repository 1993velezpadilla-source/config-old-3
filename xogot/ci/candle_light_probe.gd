extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("CANDLE_LIGHT_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame

	var managers: Array[Node] = get_nodes_in_group("xz_candle_manager")
	if managers.size() != 1:
		_fail(3, "expected exactly one candle manager, got %d" % managers.size())
		return
	var manager: Node = managers[0]
	if not manager.has_method("get_candle_count"):
		_fail(4, "candle manager API missing")
		return

	var candle_count: int = int(manager.call("get_candle_count"))
	if candle_count != 72:
		_fail(5, "expected 72 candles, got %d" % candle_count)
		return

	var counts: Dictionary = manager.call("get_state_counts") as Dictionary
	var total: int = 0
	for key: String in counts.keys():
		total += int(counts[key])
	if total != 72:
		_fail(6, "state accounting mismatch: %d" % total)
		return
	if int(counts.get("OFF", 0)) <= 0:
		_fail(7, "no extinguished candles")
		return
	if int(counts.get("DIM", 0)) <= 0:
		_fail(8, "no dim candles")
		return
	if int(counts.get("NORMAL", 0)) <= 0:
		_fail(9, "no normal candles")
		return
	if int(counts.get("STRONG", 0)) <= 0:
		_fail(10, "no strong candles")
		return
	if int(counts.get("FLICKER_HEAVY", 0)) <= 0:
		_fail(11, "no heavy-flicker candles")
		return

	var active_lights: int = int(manager.call("get_active_dynamic_light_count"))
	if active_lights < 0 or active_lights > 8:
		_fail(12, "dynamic light budget violated: %d" % active_lights)
		return

	var candle_nodes: Array[Node] = get_nodes_in_group("xz_candle")
	if candle_nodes.size() != 72:
		_fail(13, "candle runtime group mismatch")
		return
	var candidates: Array[Node] = get_nodes_in_group("xz_candle_light_candidate")
	if candidates.size() < 8:
		_fail(14, "not enough real-light candidates")
		return

	var stained: Array[Node] = get_nodes_in_group("stained_glass_light")
	if stained.size() != 4:
		_fail(15, "expected four stained-glass beams, got %d" % stained.size())
		return
	for node: Node in stained:
		if not (node is SpotLight3D):
			_fail(16, "stained glass group contains non-spotlight")
			return
		var light := node as SpotLight3D
		if light.shadow_enabled:
			_fail(17, "stained-glass beam unexpectedly enables shadows")
			return

	var placement_file := FileAccess.open("res://assets/gifts/gift_runtime_placements.json", FileAccess.READ)
	if placement_file == null:
		_fail(18, "gift placement manifest missing")
		return
	var parsed: Variant = JSON.parse_string(placement_file.get_as_text())
	if not (parsed is Dictionary):
		_fail(19, "gift placement manifest invalid")
		return
	var manifest := parsed as Dictionary
	var placements: Array = manifest.get("placements", []) as Array
	if placements.size() != 32:
		_fail(20, "expected 32 hero placements, got %d" % placements.size())
		return

	var has_candleholder: bool = false
	var has_stained: bool = false
	for placement_var: Variant in placements:
		var placement := placement_var as Dictionary
		var bundle: String = str(placement.get("bundle", ""))
		if bundle == "candleholders":
			has_candleholder = true
		if bundle == "stained_single" or bundle == "stained_multi":
			has_stained = true
	if not has_candleholder or not has_stained:
		_fail(21, "candleholder/stained-glass hero placements missing")
		return

	print("XZOGOT_CANDLE_STATES_GREEN ", counts)
	print("XZOGOT_CANDLE_LIGHT_BUDGET_GREEN ", active_lights, "/8")
	print("XZOGOT_STAINED_GLASS_LIGHT_PROBE_GREEN 4")
	print("XZOGOT_CANDLE_LIGHT_SYSTEM_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)

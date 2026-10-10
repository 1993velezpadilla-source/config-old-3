extends SceneTree

# Three complete live round loops in the EXISTING church: spawn each actual
# CharacterBody3D zombie, apply actual weapon-hit path, observe deaths and
# the director's round-clear signal. High-round formula is a separate contract.
func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("CHURCH_THREE_ROUNDS_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "Church scene missing")
		return
	var church: Node = packed.instantiate()
	root.add_child(church)
	await process_frame
	await physics_frame
	var director: Node = church.get_node_or_null("RoundManager")
	var player: Node = church.get_node_or_null("Player")
	if director == null or player == null:
		_fail(3, "Live player or round director missing")
		return
	player.set("auto_knife_enabled", false)
	player.set("health", 999999.0)
	# Suppress asynchronous auto-spawning only; spawn_one() and all live
	# collision, hit, death, round bookkeeping remain exactly production.
	director.set("_network_match_active", false)
	director.set("auto_start", false)
	var total_kills: int = 0
	for expected_round in range(1, 4):
		director.call("start_next_round")
		if int(director.call("get_round")) != expected_round:
			_fail(4, "Round progression skipped round " + str(expected_round))
			return
		var total: int = int(director.call("get_round_total"))
		if total <= 0 or total > 30:
			_fail(5, "Broken early-round zombie population: " + str(total))
			return
		for index in range(total):
			var zombie: Node = director.call("spawn_one")
			if zombie == null:
				_fail(6, "Real spawn pipeline failed in round %d enemy %d" % [expected_round, index])
				return
			if not zombie.has_method("apply_hitscan_damage"):
				_fail(7, "Zombie has no actual hit registration")
				return
			var pos: Vector3 = (zombie as Node3D).global_position
			zombie.call("apply_hitscan_damage", 999999.0, null, pos + Vector3(0.0, 1.0, 0.0))
			await process_frame
			total_kills += 1
		if int(director.call("get_alive")) != 0 or int(director.call("get_remaining_to_spawn")) != 0:
			_fail(8, "Round not properly cleared after every actual zombie died")
			return
		print("XZOGOT_CHURCH_REAL_ROUND_CLEARED ", expected_round, " kills=", total)
	if total_kills < 18:
		_fail(9, "Live test spawned too few real enemies")
		return
	print("XZOGOT_CHURCH_THREE_LIVE_WAVES_GREEN total_kills=", total_kills)
	# No 20-round hard cap: stress the director's formula at high round
	# indices separately without pretending to spawn thousands of enemies.
	var last: int = 0
	for round_id: int in [10, 20, 50, 100, 250, 500, 1000]:
		var count: int = int(director.call("zombies_for_round", round_id, 1))
		if count <= last:
			_fail(10, "Unbounded round population not increasing at " + str(round_id))
			return
		last = count
	if int(director.call("get_simultaneous_cap")) > 24:
		_fail(11, "Mobile simultaneous enemy cap was increased beyond 24")
		return
	print("XZOGOT_CHURCH_ROUNDS_1000_FORMULA_GREEN simultaneous_cap=",director.call("get_simultaneous_cap"))
	church.queue_free()
	await process_frame
	quit(0)

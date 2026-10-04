extends SceneTree

# Rendered CI characterization for the full church. This intentionally runs with
# a real viewport (Xvfb in CI), not --headless, so geometry, lights, animation,
# HUD and zombie processing all contribute to measured frame cadence.
# Keep the 12-Monja load intact; CI uses a short sample window because llvmpipe
# software rendering is orders of magnitude slower than the Android GPU target.

const WARMUP_FRAMES := 8
const SAMPLE_FRAMES := 24
const TARGET_ZOMBIES := 12
const CI_P95_LIMIT_MS := 180.0
const CI_MAX_LIMIT_MS := 500.0
const CI_DRAW_CALL_LIMIT := 6000.0
const CI_STATIC_MEMORY_LIMIT_MB := 1536.0

var _scene: Node
var _player: Node3D
var _round_manager: Node

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("PERFORMANCE_PROBE: " + message)
	quit(code)

func _wait_frames(count: int) -> void:
	for _i in range(count):
		await process_frame

func _percentile(sorted_values: Array[float], q: float) -> float:
	if sorted_values.is_empty():
		return 0.0
	var index := int(round((sorted_values.size() - 1) * clampf(q, 0.0, 1.0)))
	return sorted_values[index]

func _spawn_load() -> int:
	if _round_manager == null:
		return 0
	_round_manager.set("auto_start", false)
	if _round_manager.has_method("start_next_round"):
		_round_manager.call("start_next_round")

	var spawned := 0
	for i in range(TARGET_ZOMBIES):
		if not _round_manager.has_method("spawn_one"):
			break
		var zombie: Node3D = _round_manager.call("spawn_one") as Node3D
		if zombie == null:
			continue
		var row := int(i / 4)
		var col := i % 4
		zombie.global_position = Vector3(
			-4.2 + float(col) * 2.8,
			0.38,
			-4.0 - float(row) * 4.2
		)
		if zombie.has_method("configure_direct"):
			zombie.call("configure_direct", _player, null)
		zombie.set("phase", 2)
		zombie.set_meta("performance_probe_zombie", true)
		spawned += 1
	return spawned

func _run() -> void:
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return

	_scene = packed.instantiate()
	root.add_child(_scene)
	await _wait_frames(45)

	_player = _scene.get_node_or_null("Player") as Node3D
	_round_manager = _scene.get_node_or_null("RoundManager")
	if _player == null or _round_manager == null:
		_fail(3, "player or round manager missing")
		return

	# Use the normal powered presentation and keep the player in the nave where
	# the authored architecture, stained-light FX, HUD and zombie load are visible.
	set_meta("power_on", true)
	for node: Node in get_nodes_in_group("xz_power_light_rig"):
		if node.has_method("dev_trigger_startup"):
			node.call("dev_trigger_startup")
	_player.global_position = Vector3(0.0, 0.38, 7.0)
	_player.rotation.y = 0.0

	var spawned := _spawn_load()
	if spawned < TARGET_ZOMBIES:
		_fail(4, "expected %d active Monjas, got %d" % [TARGET_ZOMBIES, spawned])
		return

	await _wait_frames(WARMUP_FRAMES)

	var samples: Array[float] = []
	var draw_call_peak := 0.0
	var object_peak := 0.0
	var primitive_peak := 0.0
	var process_peak_ms := 0.0
	var physics_peak_ms := 0.0

	for _i in range(SAMPLE_FRAMES):
		var start_us := Time.get_ticks_usec()
		await process_frame
		var elapsed_ms := float(Time.get_ticks_usec() - start_us) / 1000.0
		samples.append(elapsed_ms)

		draw_call_peak = maxf(
			draw_call_peak,
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)
		)
		object_peak = maxf(
			object_peak,
			Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)
		)
		primitive_peak = maxf(
			primitive_peak,
			Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)
		)
		process_peak_ms = maxf(
			process_peak_ms,
			Performance.get_monitor(Performance.TIME_PROCESS) * 1000.0
		)
		physics_peak_ms = maxf(
			physics_peak_ms,
			Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0
		)

	samples.sort()
	var sum_ms := 0.0
	for value: float in samples:
		sum_ms += value
	var avg_ms := sum_ms / float(samples.size())
	var median_ms := _percentile(samples, 0.50)
	var p95_ms := _percentile(samples, 0.95)
	var p99_ms := _percentile(samples, 0.99)
	var max_ms := samples[samples.size() - 1]
	var static_memory_mb := Performance.get_monitor(Performance.MEMORY_STATIC) / (1024.0 * 1024.0)
	var node_count := Performance.get_monitor(Performance.OBJECT_NODE_COUNT)

	print(
		"XZOGOT_PERF_METRICS ",
		"frames=", SAMPLE_FRAMES,
		" zombies=", spawned,
		" avg_ms=", snappedf(avg_ms, 0.01),
		" median_ms=", snappedf(median_ms, 0.01),
		" p95_ms=", snappedf(p95_ms, 0.01),
		" p99_ms=", snappedf(p99_ms, 0.01),
		" max_ms=", snappedf(max_ms, 0.01),
		" draw_peak=", int(draw_call_peak),
		" objects_peak=", int(object_peak),
		" primitives_peak=", int(primitive_peak),
		" process_peak_ms=", snappedf(process_peak_ms, 0.01),
		" physics_peak_ms=", snappedf(physics_peak_ms, 0.01),
		" static_mem_mb=", snappedf(static_memory_mb, 0.1),
		" nodes=", int(node_count)
	)

	# CI runner budgets are intentionally broad: this is a regression/stall gate,
	# not a claim that GitHub's software-rendered VM equals Android GPU FPS.
	if p95_ms > CI_P95_LIMIT_MS:
		_fail(10, "p95 %.2fms exceeds %.2fms" % [p95_ms, CI_P95_LIMIT_MS])
		return
	if max_ms > CI_MAX_LIMIT_MS:
		_fail(11, "max frame %.2fms exceeds %.2fms" % [max_ms, CI_MAX_LIMIT_MS])
		return
	if draw_call_peak > CI_DRAW_CALL_LIMIT:
		_fail(12, "draw-call peak %.0f exceeds %.0f" % [draw_call_peak, CI_DRAW_CALL_LIMIT])
		return
	if static_memory_mb > CI_STATIC_MEMORY_LIMIT_MB:
		_fail(13, "static memory %.1fMB exceeds %.1fMB" % [static_memory_mb, CI_STATIC_MEMORY_LIMIT_MB])
		return

	print("XZOGOT_RENDER_PERFORMANCE_GATE_GREEN")
	quit(0)

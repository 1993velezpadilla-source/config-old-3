extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("GIFT_RUNTIME_PROBE: " + message)
	quit(code)

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _run() -> void:
	var split_manifest := _read_json("res://assets/gifts/gift_pack_manifest.json")
	var pack_manifest := _read_json("res://assets/gifts/gift_runtime_pack_manifest.json")
	var altar_map := _read_json("res://assets/gifts/altar_semantic_map.json")
	if split_manifest.is_empty() or pack_manifest.is_empty() or altar_map.is_empty():
		_fail(2, "one or more gift manifests missing")
		return

	var totals: Dictionary = split_manifest.get("totals", {}) as Dictionary
	if int(totals.get("sourceBundles", 0)) != 8:
		_fail(3, "source bundle count must be 8")
		return
	if int(totals.get("individualModels", 0)) != 104:
		_fail(4, "split model count must be 104")
		return
	if int(totals.get("triangles", 0)) != 14986049:
		_fail(5, "triangle conservation total changed")
		return
	if int(totals.get("validationFailures", -1)) != 0:
		_fail(6, "split validation failures present")
		return

	var packs: Array = pack_manifest.get("packs", []) as Array
	if packs.size() != 8:
		_fail(7, "runtime pack count must be 8")
		return
	var pack_models: int = 0
	var pack_triangles: int = 0
	var seen: Dictionary = {}
	for pack_var: Variant in packs:
		var pack := pack_var as Dictionary
		var bundle: String = str(pack.get("bundle", ""))
		if bundle.is_empty() or seen.has(bundle):
			_fail(8, "invalid/duplicate bundle: " + bundle)
			return
		seen[bundle] = true
		pack_models += int(pack.get("models", 0))
		pack_triangles += int(pack.get("triangles", 0))
		var digest: String = str(pack.get("sha256", ""))
		if digest.length() != 64:
			_fail(9, "invalid sha256 for " + bundle)
			return
		if int(pack.get("archive_bytes", 0)) <= 0:
			_fail(10, "invalid archive size for " + bundle)
			return
	if pack_models != 104 or pack_triangles != 14986049:
		_fail(11, "pack totals do not conserve split totals")
		return

	var altar_models: Dictionary = altar_map.get("models", {}) as Dictionary
	if altar_models.size() != 9:
		_fail(12, "altar semantic map must contain 9 models")
		return
	for expected: String in [
		"MainAltar",
		"SmallAltar",
		"PulpitStairs",
		"Confessional",
		"ThroneChair",
		"TallLectern",
		"TripodBookLectern",
		"CredenzaCabinet",
		"Railing",
	]:
		if not altar_models.values().has(expected):
			_fail(13, "altar semantic name missing: " + expected)
			return

	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(14, "main scene missing")
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	var present: int = int(scene.call("_gift_split_present_count"))
	if present != 0 and present != 104:
		_fail(15, "partial gift runtime is forbidden: %d/104" % present)
		return
	if present == 104:
		print("XZOGOT_GIFT_RUNTIME_FULL_READY_104")
	else:
		print("XZOGOT_GIFT_RUNTIME_AUTHORING_MODE_0_104")

	# Fused source sheets may exist for authoring, but no runtime node is allowed
	# to instantiate them as a gameplay prop.
	for node: Node in scene.find_children("*", "Node3D", true, false):
		if not node.has_meta("source_asset"):
			continue
		var source: String = str(node.get_meta("source_asset"))
		if source.begins_with("res://assets/gifts/") and not source.begins_with("res://assets/gifts_split/"):
			_fail(16, "fused gift source instantiated: " + source)
			return

	print("XZOGOT_GIFT_RUNTIME_CONTRACT_GREEN present=", present)
	scene.queue_free()
	await process_frame
	quit(0)

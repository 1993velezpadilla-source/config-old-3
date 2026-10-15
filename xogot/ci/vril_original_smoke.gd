extends SceneTree
## Real Godot 4.6 import gate, not just a GLB magic-byte check.
## Exit code nonzero if any original stock viewmodel, original animation,
## Dead Cell map, or gallery scene fails to instantiate.

var errors: Array[String] = []


func _initialize() -> void:
	call_deferred("_check_all")


func _fail(message: String) -> void:
	errors.append(message)
	printerr("VRIL_GODOT_RED: ", message)


func _find_player(root: Node) -> AnimationPlayer:
	if root is AnimationPlayer:
		return root as AnimationPlayer
	for child in root.get_children():
		var p: AnimationPlayer = _find_player(child)
		if p != null:
			return p
	return null


func _check_all() -> void:
	var catalog_path := "res://assets/vril_original/weapons/catalog.json"
	if not FileAccess.file_exists(catalog_path):
		_fail("Missing catalog")
		quit(1)
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(catalog_path))
	if typeof(data) != TYPE_DICTIONARY:
		_fail("Catalog is invalid JSON")
		quit(1)
		return
	var weapons: Array = data.get("weapons", [])
	var with_animation: int = 0
	for entry in weapons:
		var path := "res://assets/vril_original/weapons/" + str(entry.get("resource", ""))
		var packed := load(path) as PackedScene
		if packed == null:
			_fail("Godot cannot IMPORT " + path)
			continue
		var instance := packed.instantiate()
		if instance == null:
			_fail("Godot cannot INSTANTIATE " + path)
			continue
		var player: AnimationPlayer = _find_player(instance)
		if int(entry.get("frames", 0)) > 1:
			if player == null or player.get_animation_list().size() == 0:
				_fail("Original frame animation missing for " + path)
			else:
				with_animation += 1
		instance.free()
	if not FileAccess.file_exists("res://assets/vril_original/dead_cell.json"):
		_fail("Dead Cell map JSON is absent")
	var gallery := load("res://vril_original_gallery.tscn") as PackedScene
	if gallery == null:
		_fail("Original gallery scene could not be imported")
	else:
		var instance := gallery.instantiate()
		if instance == null:
			_fail("Original gallery scene could not instantiate")
		else:
			root.add_child(instance)
			await process_frame
			instance.queue_free()
	if errors.is_empty():
		print("VRIL_GODOT46_RUNTIME_GREEN ", weapons.size(),
				" original viewmodels, ", with_animation,
				" animations, map and gallery parsed")
		quit(0)
	else:
		print("VRIL_GODOT46_RUNTIME_RED total=", errors.size())
		quit(1)

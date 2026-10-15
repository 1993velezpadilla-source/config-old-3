extends SceneTree
## FAIL unless NEW map, EXISTING advanced gameplay and original models ALL work.
func _initialize() -> void:
	call_deferred("_verify")

func _verify() -> void:
	var expected := [
		"res://virin_survival_square.tscn",
		"res://scripts/player.gd",
		"res://scripts/weapon.gd",
		"res://scripts/zombie_dummy.gd",
		"res://scripts/round_manager.gd",
		"res://assets/zombies/source_waw/honorgd/zombie.glb",
		"res://assets/vril_original/weapons/mp40/v_mp40.glb",
		"res://assets/vril_original/weapons/catalog.json",
	]
	for path in expected:
		if not ResourceLoader.exists(path) and not FileAccess.file_exists(path):
			printerr("SURVIVAL_SQUARE_RED missing actual advanced dependency: ", path)
			quit(11)
			return
	var packed := load("res://virin_survival_square.tscn") as PackedScene
	if packed == null:
		quit(12)
		return
	var game := packed.instantiate()
	root.add_child(game)
	await process_frame
	await physics_frame
	await process_frame
	var player: Node = game.get_node_or_null("Player")
	var weapon: Node = game.get_node_or_null("Player/Weapon")
	var rounds: Node = game.get_node_or_null("RoundManager")
	if player == null or weapon == null or rounds == null:
		printerr("SURVIVAL_SQUARE_RED missing advanced Player Weapon RoundManager")
		quit(13)
		return
	if str(root.get_tree().get_meta("active_map_id", "")) != "virin_survival_square":
		printerr("SURVIVAL_SQUARE_RED wrong active map")
		quit(14)
		return
	if not game.has_node("NEW_FLOOR_NOT_DEAD_CELL") or not game.has_node("NorthWall") or not game.has_node("SouthWall"):
		printerr("SURVIVAL_SQUARE_RED no new authored box map")
		quit(15)
		return
	if get_nodes_in_group("zombie_spawn_anchor").size() != 8:
		printerr("SURVIVAL_SQUARE_RED not all 8 near-player spawn anchors exist")
		quit(16)
		return
	if int(rounds.call("get_round")) != 1 or not bool(rounds.call("is_endless_survival")):
		printerr("SURVIVAL_SQUARE_RED first survival round or infinite rounds missing")
		quit(17)
		return
	var catalog: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(
		"res://assets/vril_original/weapons/catalog.json")) as Dictionary
	if catalog.get("weapons", []).size() != 41:
		printerr("SURVIVAL_SQUARE_RED original arsenal missing")
		quit(18)
		return
	var gun_view: Node = game.get_node_or_null("Player/Head/Camera3D/AuthenticNZPFirstPersonGunAndHands")
	if gun_view == null or gun_view.get_child_count() < 1:
		printerr("SURVIVAL_SQUARE_RED original hands-and-gun model never mounted")
		quit(19)
		return
	var zombies: int = 0
	for _i in range(15):
		await physics_frame
		zombies = get_nodes_in_group("zombie").size()
		if zombies > 0:
			break
	if zombies < 1:
		printerr("SURVIVAL_SQUARE_RED round started but no real chase zombie spawned")
		quit(20)
		return
	print("VIRIN_SURVIVAL_REAL_ENGINE_GREEN original41=41 square22m=true round=1 live_zombies=",zombies,
		" weapon_model=",gun_view.get_child(0).name)
	quit(0)

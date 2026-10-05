extends SceneTree

const SHEEP_RUNNER := "res://assets/zombies/sheep/sheep_runner_animated.glb"
const SHEEP_BRUTE := "res://assets/zombies/sheep/sheep_brute_animated.glb"
const ELITE_NUN := "res://assets/zombies/monja_elite/cmu_runtime/monja_black_white_cmu_rig.gltf"

func _fail(code: int, message: String) -> void:
	push_error("SPECIAL_ENEMY_ASSET_PROBE: " + message)
	quit(code)

func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child: Node in node.get_children():
		var found := _find_skeleton(child)
		if found != null:
			return found
	return null

func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null

func _has_token(player: AnimationPlayer, token: String) -> bool:
	var want := token.to_lower()
	for name: StringName in player.get_animation_list():
		if want in str(name).to_lower():
			return true
	return false

func _validate_asset(path: String, label: String, minimum_bones: int, required_tokens: Array[String]) -> void:
	if not ResourceLoader.exists(path):
		_fail(2, "%s missing: %s" % [label, path])
		return
	var packed := load(path) as PackedScene
	if packed == null:
		_fail(3, "%s failed to load as PackedScene" % label)
		return
	var root := packed.instantiate()
	if root == null:
		_fail(4, "%s failed to instantiate" % label)
		return
	var skeleton := _find_skeleton(root)
	if skeleton == null:
		root.free()
		_fail(5, "%s Skeleton3D missing" % label)
		return
	if skeleton.get_bone_count() < minimum_bones:
		var count := skeleton.get_bone_count()
		root.free()
		_fail(6, "%s bone count %d < %d" % [label, count, minimum_bones])
		return
	var player := _find_animation_player(root)
	if player == null:
		root.free()
		_fail(7, "%s AnimationPlayer missing" % label)
		return
	for token: String in required_tokens:
		if not _has_token(player, token):
			var names := player.get_animation_list()
			root.free()
			_fail(8, "%s missing clip token %s in %s" % [label, token, names])
			return
	print("XZOGOT_SPECIAL_ENEMY_ASSET_GREEN ", label, " bones=", skeleton.get_bone_count(), " anims=", player.get_animation_list().size())
	root.free()

func _initialize() -> void:
	var mode := OS.get_environment("XZOGOT_SPECIAL_ENEMY_MODE").strip_edges().to_lower()
	if mode.is_empty():
		mode = "all"

	if mode == "sheep" or mode == "all":
		var sheep_tokens: Array[String] = ["Sheep_Idle", "Sheep_Run", "Sheep_Attack", "Sheep_Death"]
		_validate_asset(SHEEP_RUNNER, "sheep_runner", 20, sheep_tokens)
		_validate_asset(SHEEP_BRUTE, "sheep_brute", 20, sheep_tokens)
		print("XZOGOT_SHEEP_ASSET_PAIR_GODOT_GREEN")

	if mode == "elite" or mode == "all":
		var elite_tokens: Array[String] = [
			"CMU_ZombieWalk_104_41",
			"CMU_DragBadLeg_105_25",
			"CMU_StiffWalk_74_01",
			"CMU_WoundedLeg_139_19",
			"CMU_Strike_02_05",
			"CMU_PunchKick_111_19",
			"CMU_Crawl_111_03",
			"CMU_FallOnFace_90_16",
			"CMU_GetUpFaceDown_140_01",
		]
		_validate_asset(ELITE_NUN, "monja_elite_cmu", 20, elite_tokens)
		print("XZOGOT_ELITE_MONJA_CMU_GODOT_GREEN")

	print("XZOGOT_SPECIAL_ENEMY_ASSET_GATE_GREEN mode=", mode)
	quit(0)

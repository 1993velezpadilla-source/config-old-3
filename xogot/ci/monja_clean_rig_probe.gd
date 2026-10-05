extends SceneTree

const CLEAN_PATH := "res://assets/zombies/monja_clean/clean_runtime/monja_basica_clean_rig.gltf"
const CMU_PATH := "res://assets/zombies/monja_clean/cmu_runtime/monja_basica_cmu_rig.gltf"

func _fail(code: int, message: String) -> void:
	push_error("MONJA_CLEAN_RIG_PROBE: " + message)
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

func _has_anim_token(player: AnimationPlayer, token: String) -> bool:
	for anim_name: StringName in player.get_animation_list():
		if token.to_lower() in str(anim_name).to_lower():
			return true
	return false

func _initialize() -> void:
	if not ResourceLoader.exists(CLEAN_PATH):
		_fail(2, "clean rig asset missing")
		return

	var packed := load(CLEAN_PATH) as PackedScene
	if packed == null:
		_fail(3, "clean rig did not load as PackedScene")
		return

	var root := packed.instantiate()
	if root == null:
		_fail(4, "clean rig failed to instantiate")
		return

	var skeleton := _find_skeleton(root)
	if skeleton == null:
		root.free()
		_fail(5, "Skeleton3D missing")
		return
	if skeleton.get_bone_count() < 20:
		var count := skeleton.get_bone_count()
		root.free()
		_fail(6, "too few bones: %d" % count)
		return

	var player := _find_animation_player(root)
	if player == null:
		root.free()
		_fail(7, "AnimationPlayer missing")
		return

	for token: String in ["Idle_Clean", "Walk_Clean", "Attack_Clean", "Hit_Clean", "Death_Clean"]:
		if not _has_anim_token(player, token):
			var names := player.get_animation_list()
			root.free()
			_fail(8, "missing animation token %s in %s" % [token, names])
			return

	print("XZOGOT_MONJA_CLEAN_GODOT_SKELETON_GREEN ", skeleton.get_bone_count())
	print("XZOGOT_MONJA_CLEAN_GODOT_ANIMS_GREEN ", player.get_animation_list())
	root.free()

	# CMU is optional until authored, but once present it becomes part of the
	# production gate.  This prevents a partially-exported 9-clip runtime from
	# silently falling back to the clean rig in gameplay.
	if ResourceLoader.exists(CMU_PATH):
		var cmu_packed := load(CMU_PATH) as PackedScene
		if cmu_packed == null:
			_fail(9, "CMU rig did not load as PackedScene")
			return
		var cmu_root := cmu_packed.instantiate()
		if cmu_root == null:
			_fail(10, "CMU rig failed to instantiate")
			return
		var cmu_skeleton := _find_skeleton(cmu_root)
		var cmu_player := _find_animation_player(cmu_root)
		if cmu_skeleton == null or cmu_skeleton.get_bone_count() < 20:
			cmu_root.free()
			_fail(11, "CMU Skeleton3D missing or too small")
			return
		if cmu_player == null:
			cmu_root.free()
			_fail(12, "CMU AnimationPlayer missing")
			return
		for token: String in ["Idle_Clean", "Walk_Clean", "Attack_Clean", "Hit_Clean", "Death_Clean", "104_41", "105_25", "74_01", "139_19", "02_05", "111_19", "111_03", "90_16", "140_01"]:
			if not _has_anim_token(cmu_player, token):
				var cmu_names := cmu_player.get_animation_list()
				cmu_root.free()
				_fail(13, "missing CMU animation token %s in %s" % [token, cmu_names])
				return
		print("XZOGOT_MONJA_CMU_GODOT_GREEN ", cmu_skeleton.get_bone_count(), " ", cmu_player.get_animation_list())
		cmu_root.free()

	print("XZOGOT_MONJA_CLEAN_GODOT_GATE_GREEN")
	quit(0)

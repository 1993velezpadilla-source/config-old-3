class_name ChroniclesTemplateRegistry
extends RefCounted

# Original-first template: the source must actually exist. Neither a texture,
# a model filename nor a placeholder can count as an authenticated zombie rig.
const MANIFEST_PATH := "res://data/church_chronicles_template.json"
const REQUIRED_ROLES: Array[String] = ["idle", "walk", "attack", "hit", "death", "crawl"]
static var _cached: Dictionary = {}

static func contract() -> Dictionary:
	if not FileAccess.file_exists(MANIFEST_PATH):
		return {}
	var file := FileAccess.open(MANIFEST_PATH, FileAccess.READ)
	if file == null:
		return {}
	var decoded: Variant = JSON.parse_string(file.get_as_text())
	return decoded as Dictionary if decoded is Dictionary else {}

static func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for child: Node in node.get_children():
		var found: Skeleton3D = _find_skeleton(child)
		if found != null:
			return found
	return null

static func _find_anim_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found: AnimationPlayer = _find_anim_player(child)
		if found != null:
			return found
	return null

static func _mesh_count(node: Node) -> int:
	var count: int = 1 if node is MeshInstance3D and (node as MeshInstance3D).mesh != null else 0
	for child: Node in node.get_children():
		count += _mesh_count(child)
	return count

static func inspect_original_zombie() -> Dictionary:
	if not _cached.is_empty():
		return _cached.duplicate(true)
	var manifest: Dictionary = contract()
	var spec: Dictionary = manifest.get("originalZombie", {}) as Dictionary
	var result: Dictionary = {
		"ready": false,
		"path": str(spec.get("sourcePath", "")),
		"status": str(spec.get("status", "SOURCE_MISSING_NOT_STAGED")),
		"roles": {},
		"boneCount": 0,
		"meshCount": 0,
		"reason": "SOURCE_MISSING_NOT_STAGED",
	}
	var path: String = str(result["path"])
	if path.is_empty() or not ResourceLoader.exists(path):
		_cached = result
		return result.duplicate(true)
	if str(spec.get("status", "")) != "VERIFIED_IMPORT" or not bool(spec.get("sourceProvenanceVerified", false)):
		result["reason"] = "SOURCE_PROVENANCE_NOT_VERIFIED"
		_cached = result
		return result.duplicate(true)
	if not path.begins_with("res://assets/zombies/chronicles/"):
		result["reason"] = "SOURCE_PATH_NOT_IN_ISOLATED_ASSET_LANE"
		_cached = result
		return result.duplicate(true)
	var clip_names: Dictionary = spec.get("animationRoles", {}) as Dictionary
	for role: String in REQUIRED_ROLES:
		if str(clip_names.get(role, "")).is_empty():
			result["reason"] = "MISSING_CLIP_MAPPING_" + role
			_cached = result
			return result.duplicate(true)
	var packed: PackedScene = load(path) as PackedScene
	if packed == null:
		result["reason"] = "SOURCE_NOT_PACKED_SCENE"
		_cached = result
		return result.duplicate(true)
	var instance: Node = packed.instantiate()
	if instance == null:
		result["reason"] = "SOURCE_CANNOT_INSTANTIATE"
		_cached = result
		return result.duplicate(true)
	var rig: Skeleton3D = _find_skeleton(instance)
	var anim_player: AnimationPlayer = _find_anim_player(instance)
	result["boneCount"] = rig.get_bone_count() if rig != null else 0
	result["meshCount"] = _mesh_count(instance)
	if rig == null or rig.get_bone_count() < 20:
		result["reason"] = "ORIGINAL_SKELETON_MISSING_OR_TOO_FEW_BONES"
	elif anim_player == null:
		result["reason"] = "ORIGINAL_ANIMATION_PLAYER_MISSING"
	elif int(result["meshCount"]) < 1:
		result["reason"] = "ORIGINAL_NO_MESH"
	else:
		var missing_roles: Array[String] = []
		for role: String in REQUIRED_ROLES:
			var clip: String = str(clip_names.get(role, ""))
			if not anim_player.has_animation(clip):
				missing_roles.append(role)
		if not missing_roles.is_empty():
			result["reason"] = "ORIGINAL_CLIPS_MISSING:" + ",".join(missing_roles)
		else:
			result["ready"] = true
			result["roles"] = clip_names.duplicate(true)
			result["reason"] = "VERIFIED_RIG_AND_SIX_ROLES"
	instance.free()
	_cached = result
	return result.duplicate(true)


# Previously decoded Pavlov UE4.21 community source. This is technically
# real skinned/animated reference geometry, NOT official BO3/T7 provenance.
static func inspect_workshop_zombie() -> Dictionary:
	var spec: Dictionary = contract().get("workshopZombie", {}) as Dictionary
	var path: String = str(spec.get("sourcePath", ""))
	var result: Dictionary = {"ready":false,"path":path,"reason":"REFERENCE_UNSTAGED","roles":{}}
	if str(spec.get("sourceEngine", "")) != "PAVLOV_UE421":
		return result
	if str(spec.get("status", "")) != "VERIFIED_REFERENCE_IMPORT":
		return result
	if not path.begins_with("res://assets/zombies/chronicles/") or not ResourceLoader.exists(path):
		result["reason"] = "REFERENCE_SCENE_FILE_MISSING"
		return result
	var packed: PackedScene = load(path) as PackedScene
	if packed == null:
		result["reason"] = "REFERENCE_SCENE_UNREADABLE"
		return result
	var node: Node = packed.instantiate()
	if node == null:
		result["reason"] = "REFERENCE_SCENE_CANNOT_INSTANTIATE"
		return result
	var skeleton: Skeleton3D = _find_skeleton(node)
	var animation: AnimationPlayer = _find_anim_player(node)
	var bones: int = skeleton.get_bone_count() if skeleton != null else 0
	var meshes: int = _mesh_count(node)
	var roles: Dictionary = spec.get("animationRoles", {}) as Dictionary
	result["bones"] = bones
	result["meshes"] = meshes
	if bones != 102 or meshes < 1 or animation == null:
		result["reason"] = "REFERENCE_MISSING_102BONE_RIG_MESH_OR_ANIM_PLAYER"
	else:
		var missing: Array[String] = []
		for role: String in ["idle","walk","attack","hit","death"]:
			var name: String = str(roles.get(role, ""))
			if name.is_empty() or not animation.has_animation(name):
				missing.append(role)
		if missing.is_empty():
			result["ready"] = true
			result["roles"] = roles.duplicate(true)
			result["reason"] = "REFERENCE_RIG_PLUS_FIVE_AUTHORED_MOTION_ROLES"
		else:
			result["reason"] = "SOURCE_CLIP_ROLE_MISSING_" + ",".join(missing)
	node.free()
	return result

static func workshop_zombie_ready() -> bool:
	return bool(inspect_workshop_zombie().get("ready", false))

static func workshop_zombie_path() -> String:
	return str(inspect_workshop_zombie().get("path", "")) if workshop_zombie_ready() else ""

static func workshop_zombie_roles() -> Dictionary:
	return inspect_workshop_zombie().get("roles", {}) as Dictionary

static func original_zombie_ready() -> bool:
	return bool(inspect_original_zombie().get("ready", false))

static func original_zombie_path() -> String:
	var result: Dictionary = inspect_original_zombie()
	return str(result.get("path", "")) if bool(result.get("ready", false)) else ""

static func original_zombie_roles() -> Dictionary:
	return inspect_original_zombie().get("roles", {}) as Dictionary

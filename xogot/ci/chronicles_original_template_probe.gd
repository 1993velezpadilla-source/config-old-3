extends SceneTree

const Registry = preload("res://scripts/chronicles_template_registry.gd")

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("CHRONICLES_TEMPLATE_PROBE: " + message)
	quit(code)

func _run() -> void:
	var spec: Dictionary = Registry.contract()
	if spec.get("sourceLane", "") != "BO3_ZOMBIES_CHRONICLES":
		_fail(2, "source identity contract absent")
		return
	var rig: Dictionary = Registry.inspect_original_zombie()
	if not bool(rig.get("ready", false)):
		print("XZOGOT_CHRONICLES_ORIGINAL_SOURCE_PENDING ", rig.get("reason", "UNKNOWN"))
	else:
		print("XZOGOT_CHRONICLES_ORIGINAL_SKELETON_GREEN bones=", rig["boneCount"], " meshes=", rig["meshCount"])
		print("XZOGOT_CHRONICLES_ORIGINAL_SIX_ANIMATIONS_GREEN")
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(3, "church scene missing")
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame
	var player: Node3D = scene.get_node_or_null("Player") as Node3D
	var round_manager: Node = scene.get_node_or_null("RoundManager")
	if player == null or round_manager == null:
		_fail(4, "church player/director missing")
		return
	round_manager.set("auto_start", false)
	var zombie_script: Script = load("res://scripts/zombie_dummy.gd") as Script
	if zombie_script == null:
		_fail(5, "zombie behaviour missing")
		return
	var actor := CharacterBody3D.new()
	actor.name = "OriginalTemplateRuntimeActorProbe"
	actor.set_script(zombie_script)
	actor.global_position = player.global_position + Vector3(3.5, 0.15, 0.0)
	actor.call("configure_direct", player, null)
	scene.add_child(actor)
	await process_frame
	await physics_frame
	var collider: CollisionShape3D = actor.get_node_or_null("ZombieCollider") as CollisionShape3D
	if collider == null or not (collider.shape is CapsuleShape3D):
		_fail(6, "real physical zombie capsule missing")
		return
	var capsule: CapsuleShape3D = collider.shape as CapsuleShape3D
	if absf(capsule.radius - float(actor.get("collider_radius"))) > 0.001:
		_fail(7, "source model changed gameplay collision radius")
		return
	if absf(capsule.height - float(actor.get("collider_height"))) > 0.001:
		_fail(8, "source model changed gameplay collision height")
		return
	if rig["ready"]:
		if str(actor.get_meta("zombie_source_lane", "")) != "BO3_CHRONICLES_VERIFIED":
			_fail(9, "verified original source not actually mounted in church zombie actor")
			return
		if not bool(actor.get_meta("chronicles_uniform_skinning_fit", false)):
			_fail(10, "original skeleton axis-squashed instead of uniform fitting")
			return
	else:
		if str(actor.get_meta("zombie_source_lane", "")) == "BO3_CHRONICLES_VERIFIED":
			_fail(11, "original source reported ready without validated rig")
			return
		print("XZOGOT_CHURCH_CURRENT_NUN_ACTOR_NOT_ORIGINAL")
	var first_distance: float = actor.global_position.distance_to(player.global_position)
	for frame in range(65):
		await physics_frame
	var last_distance: float = actor.global_position.distance_to(player.global_position)
	if last_distance >= first_distance - 0.30:
		_fail(12, "zombie collision/AI chase not progressing: %.2f -> %.2f" % [first_distance, last_distance])
		return
	if not actor.has_method("apply_hitscan_damage"):
		_fail(13, "visual swap broke weapon hit API")
		return
	print("XZOGOT_CHURCH_TEMPLATE_PHYSICAL_CHASE_GREEN ", first_distance, " -> ", last_distance)
	print("XZOGOT_CHURCH_TEMPLATE_COLLISION_INDEPENDENT_OF_SKIN_GREEN")
	var perks: Array[Node] = get_nodes_in_group("perk_machine")
	if perks.size() != 6:
		_fail(14, "six powered perk mechanics missing")
		return
	for machine: Node in perks:
		if not machine.has_method("interact") or not machine.has_method("get_perk_id"):
			_fail(15, "machine backend not connected")
			return
	print("XZOGOT_CHURCH_TEMPLATE_SIX_MACHINE_BACKENDS_GREEN")
	var hands_source: Dictionary = spec.get("originalHandsAndInteractions", {}) as Dictionary
	if hands_source.get("status", "") != "VERIFIED_IMPORT":
		print("XZOGOT_CHRONICLES_ORIGINAL_HANDS_AND_DRINK_ANIM_PENDING")
	var originals: Dictionary = spec.get("originalSoundsAndParticles", {}) as Dictionary
	if originals.get("status", "") != "VERIFIED_IMPORT":
		print("XZOGOT_CHRONICLES_ORIGINAL_SFX_VFX_PENDING")
	print("XZOGOT_CHURCH_CHRONICLES_TEMPLATE_INFRASTRUCTURE_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)

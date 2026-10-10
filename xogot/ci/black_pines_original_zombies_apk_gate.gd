extends SceneTree
# The original gameplay template must never silently ship a nun/fallback zombie.
# The preserved Black Pines architecture, UI, power, perks and weapon runtime
# are loaded from the existing scene; no art generation or third-party fetch.
const SOURCE_ZOMBIE := "res://assets/zombies/source_waw/honorgd/zombie.glb"
const SOURCE_MP40 := "res://assets/weapons/aether_waw_real/mp40/viewmodel.glb"

func _init() -> void:
	call_deferred("_run")

func _reject(why: String) -> void:
	push_error("BLACK_PINES_ORIGINAL_RUNTIME_RED " + why)
	quit(52)

func _run() -> void:
	if not ResourceLoader.exists(SOURCE_ZOMBIE) or not ResourceLoader.exists(SOURCE_MP40):
		_reject("Existing original WaW GLB references are missing; never substitute procedural guns/nuns")
		return
	var packed: PackedScene = load("res://black_pines.tscn") as PackedScene
	if packed == null:
		_reject("existing sanatorium scene missing")
		return
	var scene: Node3D = packed.instantiate() as Node3D
	if scene == null:
		_reject("sanatorium scene failed to instantiate")
		return
	scene.set("rounds_enabled", false)
	scene.set("preview_no_enemies", true)
	root.add_child(scene)
	await process_frame
	await physics_frame
	var player: Node3D = scene.get_node_or_null("Player") as Node3D
	var director: Node = scene.get_node_or_null("RoundManager")
	var weapon: Node = scene.get_node_or_null("Player/Weapon")
	if player == null or director == null or weapon == null:
		_reject("actual player/weapon/director missing")
		return
	if str(get_tree().get_meta("active_map_id", "")) != "black_pines":
		_reject("sanatorium map contract not active")
		return
	if bool(director.get("special_rounds_enabled")) or not bool(director.get("endless_rounds_enabled")):
		_reject("original zombie endless rounds not active")
		return
	for round_n: int in [1, 5, 12, 20, 50, 100]:
		for serial: int in [1, 2, 7, 13]:
			var variant: String = str(director.call("_enemy_variant_for_spawn", round_n, serial))
			if variant != "normal":
				_reject("non-original zombie variant at round %d serial %d: %s" % [round_n, serial, variant])
				return
	var zombie_script: Script = load("res://scripts/zombie_dummy.gd") as Script
	if zombie_script == null:
		_reject("shared original zombie AI script missing")
		return
	var zombie := CharacterBody3D.new()
	zombie.name = "BlackPinesOriginalWaWRuntimeAcceptance"
	zombie.set_script(zombie_script)
	zombie.set("enemy_variant", "normal")
	zombie.call("configure_direct", player, null)
	zombie.position = player.global_position + Vector3(1.6, 0.0, 2.3)
	scene.add_child(zombie)
	await process_frame
	if not bool(zombie.get_meta("zombie_source_waw", false)):
		_reject("source model missing; game fell back to monja or procedural zombie")
		return
	if not bool(zombie.get_meta("zombie_rig_ready", false)):
		_reject("actual imported zombie AnimationPlayer missing")
		return
	var animator: AnimationPlayer = zombie.get("_animation_player") as AnimationPlayer
	if animator == null or animator.get_animation_list().is_empty():
		_reject("real source zombie has no usable animation clips")
		return
	print("BLACK_PINES_WAW_ORIGINAL_ZOMBIE_RIG_GREEN model=", zombie.get_meta("zombie_model", ""), " animations=", animator.get_animation_list().size())
	if not bool(weapon.call("equip_weapon", "mp40", true)):
		_reject("original MP40 failed to equip")
		return
	await process_frame
	if not bool(weapon.get_meta("weapon_source_weapon_attachment_ready", false)):
		_reject("source MP40 hands/grip socket not connected")
		return
	if str(weapon.get_meta("weapon_asset_lane", "")) == "procedural_fallback_dev_only":
		_reject("procedural substitute weapon detected")
		return
	print("BLACK_PINES_ORIGINAL_MP40_SOURCE_HANDS_GREEN")
	print("BLACK_PINES_FUNCTIONAL_APK_SOURCE_BASELINE_GREEN")
	quit(0)

extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var script := load("res://scripts/zombie_dummy.gd") as Script
	if script == null:
		push_error("NUN_SPRITE_GATE_FAIL: zombie script unavailable")
		quit(1)
		return
	var zombie := CharacterBody3D.new()
	zombie.set_script(script)
	root.add_child(zombie)
	await process_frame
	var collider := zombie.get_node_or_null("ZombieCollider") as CollisionShape3D
	if collider == null or collider.shape == null:
		push_error("NUN_SPRITE_GATE_FAIL: gameplay collider missing")
		quit(2)
		return
	var sprite := zombie.get_node_or_null("NunEnemy01Sprite") as Sprite3D
	var path := "res://assets/zombies/nun_enemy_01_master.png"
	if ResourceLoader.exists(path):
		if sprite == null or sprite.texture == null:
			push_error("NUN_SPRITE_GATE_FAIL: PNG present but Sprite3D missing")
			quit(3)
			return
		if sprite.texture.get_height() < 1024:
			push_error("NUN_SPRITE_GATE_FAIL: sprite source too small")
			quit(4)
			return
		print("NUN_SPRITE_GATE_GREEN sprite=", sprite.texture.get_size())
	else:
		if sprite != null:
			push_error("NUN_SPRITE_GATE_FAIL: invalid Sprite3D without PNG")
			quit(5)
			return
		print("NUN_SPRITE_GATE_FALLBACK_GREEN: PNG not committed yet")
	quit(0)

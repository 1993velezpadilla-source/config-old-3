extends SceneTree

# ORIGINAL SOURCE OPTICAL GLASS — NOT the logical tag_scope marker.
# Local GLB source geometry, recovered ProjectAether WAW meshes:
# Mosin: mtl_rus_scope_glass 33 vertices, local AABB
#   [-.16278622,.06743748,-.02619235]..[-.16046198,.09442782,.00079794]
# PTRS:  mtl_rus_scope_glass 21 vertices, local AABB
#   [-.07055729,.07699380,-.01740112]..[-.06133007,.11120188,.01740110]
# Both original tag_scope joints have the same local rest translation
#   (-.012297968,.034821290,-.011682908) — demonstrably NOT a glass center.
# This READ-ONLY test compares true glass center vs original scope tag and
# eye distance in genuine Godot 4.6.1. No source stats, rig or GLBs modified.
const STUB = preload("res://ci/ads_dummy_player.gd")
const WEAPON = preload("res://scripts/weapon.gd")
const OUT := "/tmp/xogot-source-scope-glass"
const IDS: Array[String] = ["mosin", "ptrs"]
const TAG_REST := Vector3(-0.012297968, 0.03482129, -0.011682908)
const GLASS_REST: Dictionary = {
	"mosin": Vector3(-0.16162410, 0.08093265, -0.012697205),
	"ptrs": Vector3(-0.06594368, 0.09409784, 0.0),
}
const MODES: Array[String] = [
	"original_tag_source",
	"original_tag_at_40cm",
	"source_glass_at_25cm",
	"source_glass_at_40cm",
	"source_glass_at_60cm",
]

func _init() -> void:
	call_deferred("_run")

func _error(message: String) -> void:
	push_error("XZOGOT_SCOPE_GLASS_EYELINE_RED " + message)
	quit(2)

func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		var s := node as Skeleton3D
		if s.find_bone("tag_scope") >= 0:
			return s
	for child: Node in node.get_children():
		var sk := _find_skeleton(child)
		if sk != null:
			return sk
	return null

func _screenshot(label: String) -> bool:
	await process_frame
	await process_frame
	var frame := root.get_texture().get_image()
	return frame != null and not frame.is_empty() and frame.save_png(OUT + "/" + label + ".png") == OK

func _run() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var world := Node3D.new()
	root.add_child(world)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.background_mode = Environment.BG_COLOR
	env.environment.background_color = Color(0.08, 0.09, 0.11)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.environment.ambient_light_energy = 0.8
	world.add_child(env)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-32.0, 20.0, 0.0)
	light.light_energy = 1.25
	world.add_child(light)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(STUB)
	world.add_child(player)
	var head := Node3D.new()
	head.name = "Head"
	player.add_child(head)
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.current = true
	camera.fov = 66
	camera.near = 0.025
	head.add_child(camera)
	var weapon := Node.new()
	weapon.name = "Weapon"
	weapon.set_script(WEAPON)
	player.add_child(weapon)
	await process_frame
	var total := 0
	for id: String in IDS:
		player.set_meta("ads_toggled", false)
		if not bool(weapon.call("equip_weapon", id, true)):
			_error("failed original source equip " + id)
			return
		await create_timer(0.65).timeout
		player.set_meta("ads_toggled", true)
		await create_timer(0.7).timeout
		weapon.call("_update_visual_recoil", 0.7)
		var view: Node3D = weapon.get("_view_root") as Node3D
		var gun: Node3D = weapon.get("_weapon_model_root") as Node3D
		if view == null or gun == null:
			_error("source gun/view missing " + id)
			return
		var sk := _find_skeleton(gun)
		if sk == null:
			_error("source scope bone skeleton missing " + id)
			return
		var idx: int = sk.find_bone("tag_scope")
		if idx < 0:
			_error("original source tag_scope missing " + id)
			return
		weapon.set_process(false)
		var hands_anim: AnimationPlayer = weapon.get("_hands_animation_player") as AnimationPlayer
		if hands_anim != null:
			hands_anim.pause()
		var source_anim: AnimationPlayer = weapon.get("_asset_animation_player") as AnimationPlayer
		if source_anim != null:
			source_anim.pause()
		var pos := view.position
		var rot := view.quaternion
		var original_tag: Dictionary = weapon.call("_gun_skeleton_bone_world", "tag_scope")
		if not bool(original_tag.get("found", false)):
			_error("original source tag unavailable " + id)
			return
		var tag_world: Vector3 = original_tag.get("position", Vector3.ZERO)
		var native_offset: Vector3 = GLASS_REST[id] - TAG_REST
		if native_offset.length() < 0.05 or native_offset.length() > 0.18:
			_error("source measured glass-rest offset not plausible " + id)
			return
		# Source position offset is expressed in ORIGINAL GLB joint-local
		# meters. Use the real imported tag_scope bone basis, not a magic
		# camera-space shift. If the source joint is animated, this rotates
		# the offset with its original pose.
		var joint_basis := (
			sk.global_transform.basis * sk.get_bone_global_pose(idx).basis
		).orthonormalized()
		var glass_world: Vector3 = tag_world + joint_basis * native_offset
		print("XZOGOT_SCOPE_SOURCE_GEOMETRY id=",id,
			" source_tag_local=",TAG_REST, " source_glass_local=",GLASS_REST[id],
			" native_offset_local_m=",native_offset,
			" tag_camera=",camera.to_local(tag_world),
			" glass_camera=",camera.to_local(glass_world))
		for mode: String in MODES:
			view.position = pos
			view.quaternion = rot
			await process_frame
			var is_glass := mode.begins_with("source_glass")
			var target_depth: float = -0.4
			if mode.ends_with("25cm"):
				target_depth = -0.25
			elif mode.ends_with("60cm"):
				target_depth = -0.6
			var anchor: Vector3 = glass_world if is_glass else tag_world
			var before: Vector3 = camera.to_local(anchor)
			if mode != "original_tag_source":
				view.position += Vector3(-before.x, -before.y, target_depth - before.z)
			await process_frame
			# The source bone and glass point must move together; derive
			# actual displacement from the camera after the viewroot moves.
			var movement := view.position - pos
			var tag_actual: Dictionary = weapon.call("_gun_skeleton_bone_world", "tag_scope")
			var tag_actual_cam: Vector3 = camera.to_local(tag_actual.get("position", tag_world))
			var glass_actual_cam: Vector3 = tag_actual_cam + (
				camera.global_transform.basis.inverse()
				* (joint_basis * native_offset)
			)
			print("XZOGOT_SCOPE_GLASS_AB_POINT id=",id," mode=",mode,
				" view_correction=",movement,
				" tag_cam=",tag_actual_cam," glass_cam=",glass_actual_cam,
				" source_DT_Weapons_untouched=true")
			if not await _screenshot(id+"-ads-"+mode):
				_error("original Godot PNG missing " + id + ":" + mode)
				return
			total += 1
		view.position = pos
		view.quaternion = rot
		weapon.set_process(true)
		player.set_meta("ads_toggled", false)
	if total != 10:
		_error("expected 10 original glass-alignment screenshots, got " + str(total))
		return
	print("XZOGOT_SOURCE_GLASS_EYELINE_DIAGNOSTIC_GREEN frames=10 guns=2 source_assets_unchanged=true")
	quit(0)

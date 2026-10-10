extends SceneTree

# Report actual FPS source-model camera-space extents. Earlier tests approved
# named bones and ADS tables while real screenshots showed invisible gun
# sights. This diagnostic does NOT claim pixel-aligned aiming.
func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("CHURCH_VIEWMODEL_GEOMETRY_DIAGNOSTIC: " + message)
	quit(code)

func _mesh_bounds_in_camera(node: Node, camera: Camera3D, out: Array[Vector3]) -> void:
	if node is MeshInstance3D:
		var mesh_node: MeshInstance3D = node as MeshInstance3D
		if mesh_node.mesh != null:
			var a: AABB = mesh_node.get_aabb()
			for ix in range(2):
				for iy in range(2):
					for iz in range(2):
						var p: Vector3 = a.position + Vector3(
							a.size.x * float(ix), a.size.y * float(iy), a.size.z * float(iz))
						out.append(camera.to_local(mesh_node.to_global(p)))
	for child: Node in node.get_children():
		_mesh_bounds_in_camera(child,camera,out)

func _diagnose(root_node: Node3D, camera: Camera3D, weapon_id: String, role: String) -> void:
	var points: Array[Vector3] = []
	_mesh_bounds_in_camera(root_node,camera,points)
	if points.is_empty():
		_fail(8, "No authored GLB mesh found for " + weapon_id + ":" + role)
		return
	var vmin: Vector3 = points[0]
	var vmax: Vector3 = points[0]
	for p: Vector3 in points:
		vmin=vmin.min(p)
		vmax=vmax.max(p)
	print("XZOGOT_SOURCE_FPS_CAMERA_SPACE_GEOMETRY ",weapon_id," ",role,
		" min=",vmin," max=",vmax," center=",(vmin+vmax)*0.5,
		" approx_size=",vmax-vmin," visible_forward_z=",vmin.z< -camera.near)

func _run() -> void:
	var scene_resource: PackedScene=load("res://main.tscn") as PackedScene
	if scene_resource==null:
		_fail(2,"Church scene missing")
		return
	var scene: Node=scene_resource.instantiate()
	root.add_child(scene)
	await process_frame
	var player: Node3D=scene.get_node_or_null("Player") as Node3D
	var camera: Camera3D=scene.get_node_or_null("Player/Head/Camera3D") as Camera3D
	var weapon: Node=scene.get_node_or_null("Player/Weapon")
	if player==null or camera==null or weapon==null:
		_fail(3,"Source FPS pipeline missing")
		return
	for weapon_id: String in ["colt","mp40"]:
		if not bool(weapon.call("equip_weapon",weapon_id,true)):
			_fail(4,"Weapon equip unavailable "+weapon_id)
			return
		weapon.call("_play_asset_animation","idle",0.0)
		for frame in range(42):
			await process_frame
		var hand_node: Node3D=weapon.get("_hands_model_root") as Node3D
		var gun_node: Node3D=weapon.get("_weapon_model_root") as Node3D
		if hand_node==null or gun_node==null:
			_fail(5,"Real GLB source hands or gun root missing")
			return
		_diagnose(hand_node,camera,weapon_id,"hands")
		_diagnose(gun_node,camera,weapon_id,"gun")
		var player_anim: AnimationPlayer=weapon.get("_hands_animation_player") as AnimationPlayer
		if player_anim==null:
			_fail(6,"No source PSA runtime")
			return
		print("XZOGOT_SOURCE_FPS_ANIM_STATE ",weapon_id,
			" clip=",player_anim.current_animation," playing=",player_anim.is_playing(),
			" frame=",player_anim.current_animation_position,
			" root_pos=",(weapon.get("_view_root") as Node3D).position,
			" gun_local_transform=",gun_node.transform,
			" socket_name=",gun_node.get_parent().name)
	print("XZOGOT_SOURCE_2_WEAPON_FPS_BOUNDS_DIAGNOSTIC_COMPLETE")
	scene.queue_free()
	await process_frame
	quit(0)

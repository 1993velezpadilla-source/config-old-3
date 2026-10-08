extends SceneTree

# Original WaW meshes and PSA bind weights: diagnose the "two pistols" /
# floating magazine/sight geometry visible in genuine 48-frame HIP/ADS proof.
# Read-only original GLBs and 2008 source clips; NEVER hide or mutate meshes.
const STUB = preload("res://ci/ads_dummy_player.gd")
const WEAPON = preload("res://scripts/weapon.gd")
const IDS: Array[String] = ["colt", "walther", "nambu", "tt33", "357"]

func _init() -> void:
	call_deferred("_run")

func _fail(reason: String) -> void:
	push_error("XZOGOT_PISTOL_NATIVE_RIG_AUDIT_RED " + reason)
	quit(2)

func _analyze(root_node: Node3D, weapon_id: String, role: String) -> int:
	if root_node == null:
		return 0
	var stack: Array[Node] = [root_node]
	var mesh_count := 0
	while not stack.is_empty():
		var node: Node = stack.pop_back()
		if node is MeshInstance3D:
			var part := node as MeshInstance3D
			if part.mesh == null:
				continue
			mesh_count += 1
			print("XZOGOT_NATIVE_COMPONENT id=",weapon_id," role=",role,
				" mesh=",part.get_path(), " skin=",part.skin != null,
				" material_surfaces=",part.mesh.get_surface_count(),
				" local_aabb=",part.mesh.get_aabb(),
				" visible=",part.is_visible_in_tree())
			if part.skin != null:
				var skin: Skin = part.skin
				var counts: Dictionary = {}
				var weighted: Dictionary = {}
				var samples: Dictionary = {}
				for surface_idx in range(part.mesh.get_surface_count()):
					var a: Array = part.mesh.surface_get_arrays(surface_idx)
					var verts: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
					var bindings: PackedInt32Array = a[Mesh.ARRAY_BONES]
					var weights: PackedFloat32Array = a[Mesh.ARRAY_WEIGHTS]
					var stride := 8 if (part.mesh.surface_get_format(surface_idx) & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS) != 0 else 4
					if bindings.size() < verts.size() * stride or weights.size() < verts.size() * stride:
						_fail("invalid skinned surface " + weapon_id + " " + str(surface_idx))
						return -1
					for v in range(verts.size()):
						var best := 0.0
						var name := ""
						for k in range(stride):
							var p := v*stride+k
							if weights[p] > best:
								var b: int = bindings[p]
								if b >= 0 and b < skin.get_bind_count():
									best = weights[p]
									name = str(skin.get_bind_name(b))
						if name.is_empty():
							continue
						counts[name] = int(counts.get(name,0)) + 1
						weighted[name] = float(weighted.get(name,0.0)) + best
						if not samples.has(name):
							samples[name] = verts[v]
				var ordered: Array = counts.keys()
				ordered.sort_custom(func(a: Variant,b: Variant) -> bool:
					return int(counts[a]) > int(counts[b]))
				for i in range(mini(ordered.size(),32)):
					var bone := str(ordered[i])
					print("XZOGOT_NATIVE_SKIN_BONE id=",weapon_id,
						" mesh=",part.name," name=",bone,
						" strongest_vertices=",counts[bone],
						" total_weights=",weighted[bone],
						" sample_local=",samples[bone])
			else:
				print("XZOGOT_NATIVE_UNSKINNED_MESH id=",weapon_id," role=",role,
					" name=",part.name)
		for child: Node in node.get_children():
			stack.append(child)
	return mesh_count

func _run() -> void:
	var scene := Node3D.new()
	root.add_child(scene)
	var player := CharacterBody3D.new()
	player.name = "Player"
	player.set_script(STUB)
	scene.add_child(player)
	var head := Node3D.new()
	head.name = "Head"
	player.add_child(head)
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	head.add_child(camera)
	var weapon := Node.new()
	weapon.name = "Weapon"
	weapon.set_script(WEAPON)
	player.add_child(weapon)
	await process_frame
	for id: String in IDS:
		if not bool(weapon.call("equip_weapon",id,true)):
			_fail("unable to equip " + id)
			return
		await create_timer(0.8).timeout
		var gun := weapon.get("_weapon_model_root") as Node3D
		var hands := weapon.get("_hands_model_root") as Node3D
		var gun_anim := weapon.get("_asset_animation_player") as AnimationPlayer
		var hand_anim := weapon.get("_hands_animation_player") as AnimationPlayer
		print("XZOGOT_PISTOL_SKELETON_CONTEXT id=",id,
			" model_roll=",weapon.get_meta("weapon_source_gun_roll_correction_deg",-1),
			" gun_action=",gun_anim.get_assigned_animation() if gun_anim != null else "<missing>",
			" hands_action=",hand_anim.get_assigned_animation() if hand_anim != null else "<missing>")
		var gun_count := _analyze(gun,id,"original_gun")
		var hand_count := _analyze(hands,id,"source_hands")
		if gun_count <= 0 or hand_count <= 0:
			_fail("missing skinned gun/hands evidence " + id)
			return
	print("XZOGOT_PISTOL_NATIVE_RIG_AUDIT_GREEN audited=5 source_geometry_unmodified=true")
	quit(0)

extends Node3D

## Full Nuketown source-world runtime.
##
## This is intentionally separate from the church map. It consumes the exact
## source-authoritative XZIEL world payload, preserves every extracted actor
## anchor from the .umap, generates walkable collision from every imported mesh
## instance, and places the Xogot player at the source Pavlov spawn.
##
## Gameplay adapters are attached only when their source semantics are proven.
## Unknown Blueprint values are preserved as metadata instead of guessed.

@export_dir var source_root: String = "res://assets/benchmarks/nuketown_xziel"
@export var build_world_collision: bool = true
@export var preserve_all_actor_anchors: bool = true
@export var place_player_at_source_spawn: bool = true
@export var spawn_anchor_index: int = 0

const SOURCE_LOADER := preload("res://scripts/xziel_benchmark_loader.gd")
const INTERACTABLE := preload("res://scripts/interactable.gd")
const NUKETOWN_NAVIGATION := preload("res://scripts/nuketown_navigation_runtime.gd")
const NUKETOWN_AUDIO := preload("res://scripts/nuketown_source_audio_runtime.gd")
const WeaponCatalog := preload("res://scripts/weapon_catalog.gd")
const VISUAL_SCENE_FILE := "visual-scene.json"
const SOURCE_GAMEPLAY_FILE := "res://data/nuketown_source_gameplay.json"
const SOURCE_ACTOR_COVERAGE_FILE := "res://data/nuketown_actor_coverage.json"
const MYSTERY_SOURCE_VISUAL := "res://assets/benchmarks/nuketown_xziel/mystery_source/mystery_box_source.gltf"

var _source_loader: Node3D
var _source_actor_root: Node3D
var _navigation_runtime: Node3D
var _source_audio_runtime: Node3D
var _source_gameplay_truth: Dictionary = {}
var _source_actor_coverage: Dictionary = {}
var _collision_count: int = 0
var _actor_anchor_count: int = 0
var _source_spawn_count: int = 0
var _source_wallbuy_count: int = 0
var _source_mystery_count: int = 0
var _source_ladder_count: int = 0
var _source_interactable_count: int = 0
var _source_covered_actor_count: int = 0

func _ready() -> void:
	get_tree().set_meta("active_map_id", "nuketown_xziel_full")
	get_tree().set_meta("nuketown_full_map_ready", false)
	call_deferred("_boot_full_map")

func _boot_full_map() -> void:
	_source_gameplay_truth = _read_json(SOURCE_GAMEPLAY_FILE)
	_source_actor_coverage = _read_json(SOURCE_ACTOR_COVERAGE_FILE)
	if _source_gameplay_truth.is_empty():
		push_error("NUKETOWN_FULL_MAP: source gameplay truth missing")
		return
	if int(_source_gameplay_truth.get("schemaVersion", 0)) != 1:
		push_error("NUKETOWN_FULL_MAP: unsupported source gameplay truth schema")
		return
	if int(_source_actor_coverage.get("schemaVersion", 0)) != 2:
		push_error("NUKETOWN_FULL_MAP: source actor coverage missing")
		return

	_source_loader = SOURCE_LOADER.new() as Node3D
	if _source_loader == null:
		push_error("NUKETOWN_FULL_MAP: source loader instantiate failed")
		return
	_source_loader.name = "NuketownSourceWorld"
	_source_loader.set("source_root", source_root)
	_source_loader.set("load_on_ready", true)
	add_child(_source_loader)

	var ready := false
	for _attempt in range(600):
		await get_tree().create_timer(0.05).timeout
		if bool(_source_loader.get_meta("xziel_benchmark_ready", false)):
			ready = true
			break
	if not ready:
		push_error(
			"NUKETOWN_FULL_MAP: source world failed "
			+ str(_source_loader.get_meta("xziel_benchmark_instance_count", -1))
			+ "/"
			+ str(_source_loader.get_meta("xziel_benchmark_source_instance_count", -1))
		)
		return

	var scene := _read_json(source_root.path_join(VISUAL_SCENE_FILE))
	if scene.is_empty():
		push_error("NUKETOWN_FULL_MAP: visual-scene.json missing")
		return
	if not _validate_actor_coverage(scene):
		return

	if preserve_all_actor_anchors:
		_build_source_actor_anchors(scene)

	if not _build_source_audio_runtime():
		return

	if build_world_collision:
		_collision_count = _build_collision_recursive(_source_loader)

	if place_player_at_source_spawn:
		_place_player_from_source(scene)

	if not await _build_navigation_runtime():
		return

	set_meta("source_mesh_count", int(_source_loader.get_meta("xziel_benchmark_mesh_count", -1)))
	set_meta("source_instance_count", int(_source_loader.get_meta("xziel_benchmark_instance_count", -1)))
	set_meta("source_actor_anchor_count", _actor_anchor_count)
	set_meta("source_collision_count", _collision_count)
	set_meta("source_spawn_count", _source_spawn_count)
	set_meta("source_wallbuy_count", _source_wallbuy_count)
	set_meta("source_mystery_count", _source_mystery_count)
	set_meta("source_ladder_count", _source_ladder_count)
	set_meta("source_interactable_count", _source_interactable_count)
	set_meta("source_covered_actor_count", _source_covered_actor_count)
	set_meta("source_coverage_class_count", int(_source_actor_coverage.get("sourceClassCount", 0)))
	set_meta("source_gameplay_truth_schema", int(_source_gameplay_truth.get("schemaVersion", 0)))
	set_meta("navigation_polygon_count", int(_navigation_runtime.call("get_polygon_count")))
	set_meta("zombie_spawn_anchor_count", int(_navigation_runtime.call("get_spawn_anchor_count")))
	set_meta("nuketown_round_runtime_ready", bool(_navigation_runtime.call("is_navigation_ready")))
	set_meta("source_audio_ambient_count", int(_source_audio_runtime.call("get_ambient_runtime_count")))
	set_meta("source_audio_source_stream_count", int(_source_audio_runtime.call("get_source_stream_count")))
	set_meta("source_audio_fallback_stream_count", int(_source_audio_runtime.call("get_fallback_stream_count")))
	set_meta("source_audio_missing_stream_count", int(_source_audio_runtime.call("get_missing_stream_count")))
	set_meta("source_audio_join_sound_count", int(_source_audio_runtime.get_meta("join_sound_count", -1)))
	var mystery_truth: Dictionary = _source_gameplay_truth.get("mysteryBox", {})
	set_meta("source_mystery_pool_count", (mystery_truth.get("pool", []) as Array).size())
	set_meta("nuketown_full_map_ready", true)
	get_tree().set_meta("nuketown_full_map_ready", true)

	print(
		"XZOGOT_NUKETOWN_FULL_MAP_GREEN ",
		"meshes=", get_meta("source_mesh_count"),
		" instances=", get_meta("source_instance_count"),
		" actors=", _actor_anchor_count,
		" collisions=", _collision_count,
		" spawns=", _source_spawn_count,
		" wallbuys=", _source_wallbuy_count,
		" mystery=", _source_mystery_count,
		" ladders=", _source_ladder_count
	)

func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	return parsed as Dictionary if parsed is Dictionary else {}

func _validate_actor_coverage(scene: Dictionary) -> bool:
	var actual: Dictionary = {}
	var total := 0
	for raw: Variant in scene.get("actorAnchors", []):
		if not (raw is Dictionary):
			continue
		var class_id := str((raw as Dictionary).get("className", ""))
		actual[class_id] = int(actual.get(class_id, 0)) + 1
		total += 1
	var expected_classes: Dictionary = _source_actor_coverage.get("classes", {})
	if total != int(_source_actor_coverage.get("sourceActorCount", -1)):
		push_error("NUKETOWN_FULL_MAP: actor coverage total mismatch " + str(total))
		return false
	if actual.size() != int(_source_actor_coverage.get("sourceClassCount", -1)):
		push_error("NUKETOWN_FULL_MAP: actor coverage class-count mismatch")
		return false
	for class_var: Variant in expected_classes.keys():
		var class_id := str(class_var)
		var row: Dictionary = expected_classes[class_id]
		if int(actual.get(class_id, -1)) != int(row.get("count", -2)):
			push_error("NUKETOWN_FULL_MAP: uncovered actor class " + class_id)
			return false
	_source_covered_actor_count = total
	print("XZOGOT_NUKETOWN_ACTOR_COVERAGE_GREEN actors=", total, " classes=", actual.size())
	return true

func _source_disposition(source_class: String) -> String:
	var classes: Dictionary = _source_actor_coverage.get("classes", {})
	var row: Dictionary = classes.get(source_class, {})
	return str(row.get("disposition", "UNCLASSIFIED"))

func _make_source_interactable(
	marker: Marker3D,
	kind: int,
	prompt: String,
	size: Vector3
) -> StaticBody3D:
	var node := INTERACTABLE.new() as StaticBody3D
	node.name = marker.name + "_Runtime"
	node.transform = marker.transform
	node.collision_layer = 8
	node.collision_mask = 0
	node.set("interaction_kind", kind)
	node.set("prompt_text", prompt)
	node.set("one_shot", false)
	node.set_meta("source_actor_adapter", true)
	node.set_meta("source_class_name", marker.get_meta("source_class_name", ""))
	node.set_meta("source_export_index", marker.get_meta("source_export_index", -1))
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	node.add_child(collision)
	_source_actor_root.add_child(node)
	_source_interactable_count += 1
	return node

func _find_animation_player_recursive(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child: Node in node.get_children():
		var found := _find_animation_player_recursive(child)
		if found != null:
			return found
	return null

func _attach_mystery_source_visual(runtime: Node3D) -> bool:
	if not ResourceLoader.exists(MYSTERY_SOURCE_VISUAL):
		push_error("NUKETOWN_FULL_MAP: Mystery source visual missing")
		return false
	var packed := load(MYSTERY_SOURCE_VISUAL) as PackedScene
	if packed == null:
		push_error("NUKETOWN_FULL_MAP: Mystery source visual failed to import")
		return false
	var visual := packed.instantiate() as Node3D
	if visual == null:
		push_error("NUKETOWN_FULL_MAP: Mystery source visual instantiate failed")
		return false
	visual.name = "MysterySourceVisual"
	visual.add_to_group("nuketown_source_mystery_visual")
	runtime.add_child(visual)
	var animation_player := _find_animation_player_recursive(visual)
	if animation_player == null:
		push_error("NUKETOWN_FULL_MAP: Mystery source AnimationPlayer missing")
		return false
	var source_clips: Array[String] = []
	for raw_name: StringName in animation_player.get_animation_list():
		var clip := str(raw_name)
		if clip != "RESET":
			source_clips.append(clip)
	source_clips.sort()
	runtime.set_meta("source_mystery_visual_ready", true)
	runtime.set_meta("source_mystery_animation_count", source_clips.size())
	runtime.set_meta("source_mystery_animation_names", source_clips)
	if runtime.has_method("refresh_source_animation_player"):
		runtime.call("refresh_source_animation_player")
	print("XZOGOT_MYSTERY_SOURCE_VISUAL_GREEN clips=", source_clips.size(), " names=", source_clips)
	return source_clips.size() == 7

func _source_basis() -> Basis:
	# Same single coordinate conversion as XzielBenchmarkLoader.
	# XZIEL +X -> Godot -Z, +Y -> -X, +Z -> +Y.
	return Basis(
		Vector3(0.0, 0.0, -1.0),
		Vector3(-1.0, 0.0, 0.0),
		Vector3(0.0, 1.0, 0.0)
	)

func _transform_from_row_major(raw: Variant) -> Transform3D:
	if not (raw is Array):
		return Transform3D.IDENTITY
	var m := raw as Array
	if m.size() != 16:
		return Transform3D.IDENTITY
	return Transform3D(
		Basis(
			Vector3(float(m[0]), float(m[4]), float(m[8])),
			Vector3(float(m[1]), float(m[5]), float(m[9])),
			Vector3(float(m[2]), float(m[6]), float(m[10]))
		),
		Vector3(float(m[3]), float(m[7]), float(m[11]))
	)

func _safe_name(raw: String) -> String:
	var result := raw.get_file()
	result = result.replace(".", "_")
	result = result.replace(":", "_")
	result = result.replace("/", "_")
	if result.is_empty():
		result = "SourceActor"
	return result

func _build_source_actor_anchors(scene: Dictionary) -> void:
	_source_actor_root = Node3D.new()
	_source_actor_root.name = "SourceActorAnchors"
	_source_actor_root.basis = _source_basis()
	add_child(_source_actor_root)

	for raw: Variant in scene.get("actorAnchors", []):
		if not (raw is Dictionary):
			continue
		var row := raw as Dictionary
		var marker := Marker3D.new()
		marker.name = _safe_name(str(row.get("objectPath", "SourceActor")))
		marker.transform = _transform_from_row_major(row.get("matrixRowMajor", []))
		marker.set_meta("source_package_path", str(row.get("packagePath", "")))
		marker.set_meta("source_object_path", str(row.get("objectPath", "")))
		marker.set_meta("source_class_name", str(row.get("className", "")))
		marker.set_meta("source_export_index", int(row.get("exportIndex", -1)))
		marker.set_meta("source_anchor_source", str(row.get("anchorSource", "")))
		var disposition := _source_disposition(str(row.get("className", "")))
		marker.set_meta("source_disposition", disposition)
		if disposition == "UNCLASSIFIED":
			push_error("NUKETOWN_FULL_MAP: silent source actor drop " + str(row.get("className", "")))
			continue
		marker.add_to_group("nuketown_source_covered_actor")
		_source_actor_root.add_child(marker)
		_actor_anchor_count += 1

		var source_class := str(row.get("className", ""))
		match source_class:
			"Pavlov_Spawn":
				marker.add_to_group("nuketown_source_spawn")
				_source_spawn_count += 1
			"Pavlov_Ladder":
				marker.add_to_group("nuketown_source_ladder")
				var ladder := _make_source_interactable(
					marker,
					INTERACTABLE.Kind.LADDER,
					"CLIMB",
					Vector3(0.9, 2.4, 0.45)
				)
				var source_scale := marker.transform.basis.get_scale()
				var inferred_height := maxf(2.0, maxf(source_scale.x, maxf(source_scale.y, source_scale.z)))
				ladder.set("ladder_climb_height", inferred_height)
				ladder.set_meta("source_ladder_height_inferred", true)
				ladder.add_to_group("nuketown_source_ladder_runtime")
				_source_ladder_count += 1
			"wallbuy_C", "wallbuy_2_C", "wallbuy_3_C":
				marker.add_to_group("nuketown_source_wallbuy")
				var wallbuys: Dictionary = _source_gameplay_truth.get("wallbuys", {})
				var source_wallbuy: Dictionary = wallbuys.get(source_class, {})
				var source_weapon_id := str(source_wallbuy.get("itemId", ""))
				var source_price := int(source_wallbuy.get("price", -1))
				var catalog_ready := WeaponCatalog.has_weapon(source_weapon_id)
				marker.set_meta("source_weapon_id", source_weapon_id)
				marker.set_meta("source_price_known", source_price >= 0)
				marker.set_meta("source_price", source_price)
				marker.set_meta("source_price_authority", str(source_wallbuy.get("priceAuthority", "")))
				marker.set_meta("source_item_catalog_ready", catalog_ready)
				marker.set_meta("source_interaction_ready", source_price >= 0)
				var wallbuy_runtime := _make_source_interactable(
					marker,
					INTERACTABLE.Kind.WALLBUY,
					"BUY " + source_weapon_id.to_upper(),
					Vector3(0.75, 1.25, 0.40)
				)
				wallbuy_runtime.set("weapon_id", source_weapon_id)
				wallbuy_runtime.set("price", source_price)
				wallbuy_runtime.set("source_external_item", not catalog_ready)
				wallbuy_runtime.set("source_item_authority", str(source_wallbuy.get("priceAuthority", "")))
				wallbuy_runtime.add_to_group("nuketown_source_wallbuy_runtime")
				_source_wallbuy_count += 1
			"NewBlueprint1_2_C":
				marker.add_to_group("nuketown_source_mystery")
				var mystery: Dictionary = _source_gameplay_truth.get("mysteryBox", {})
				var pool: Array = mystery.get("pool", [])
				var supported := 0
				for item_raw: Variant in pool:
					if WeaponCatalog.has_weapon(str(item_raw)):
						supported += 1
				marker.set_meta("source_item_pool", pool.duplicate())
				marker.set_meta("source_item_pool_count", pool.size())
				marker.set_meta("source_supported_item_count", supported)
				marker.set_meta("source_replicated", bool(mystery.get("replicated", false)))
				marker.set_meta("source_always_relevant", bool(mystery.get("alwaysRelevant", false)))
				marker.set_meta("source_item_class", str(mystery.get("itemClass", "")))
				marker.set_meta("source_interaction_ready", pool.size() > 0)
				var mystery_runtime := _make_source_interactable(
					marker,
					INTERACTABLE.Kind.MYSTERY,
					"USE MYSTERY BOX",
					Vector3(1.15, 1.25, 0.85)
				)
				var mystery_price := int(mystery.get("price", -1))
				mystery_runtime.set("price", mystery_price)
				mystery_runtime.set_meta("source_price", mystery_price)
				mystery_runtime.set_meta("source_price_authority", str(mystery.get("priceAuthority", "")))
				mystery_runtime.set_meta("source_selection_authority", str(mystery.get("selectionAuthority", "")))
				marker.set_meta("source_price", mystery_price)
				marker.set_meta("source_price_known", mystery_price >= 0)
				marker.set_meta("source_price_authority", str(mystery.get("priceAuthority", "")))
				var typed_pool: Array[String] = []
				for item_raw: Variant in pool:
					typed_pool.append(str(item_raw))
				mystery_runtime.set("source_item_pool", typed_pool)
				mystery_runtime.set("source_item_authority", str(mystery.get("itemClass", "")))
				if not _attach_mystery_source_visual(mystery_runtime):
					push_error("NUKETOWN_FULL_MAP: Mystery source visual bridge failed")
				mystery_runtime.add_to_group("nuketown_source_mystery_runtime")
				_source_mystery_count += 1
			_:
				pass

func _build_collision_recursive(node: Node) -> int:
	var created := 0
	if node is MeshInstance3D:
		var mesh_node := node as MeshInstance3D
		if mesh_node.mesh != null and not mesh_node.has_node("SourceCollision"):
			var shape := mesh_node.mesh.create_trimesh_shape()
			if shape != null:
				var body := StaticBody3D.new()
				body.name = "SourceCollision"
				body.collision_layer = 1
				body.collision_mask = 1
				body.add_to_group("nuketown_world_collision")
				body.set_meta("source_generated_collision", true)
				var collision := CollisionShape3D.new()
				collision.name = "CollisionShape3D"
				collision.shape = shape
				body.add_child(collision)
				mesh_node.add_child(body)
				created += 1
	for child: Node in node.get_children():
		created += _build_collision_recursive(child)
	return created

func _build_source_audio_runtime() -> bool:
	if _source_actor_root == null:
		push_error("NUKETOWN_FULL_MAP: source actor root missing before audio build")
		return false
	_source_audio_runtime = NUKETOWN_AUDIO.new() as Node3D
	if _source_audio_runtime == null:
		push_error("NUKETOWN_FULL_MAP: source audio runtime instantiate failed")
		return false
	_source_audio_runtime.name = "NuketownSourceAudioRuntime"
	add_child(_source_audio_runtime)
	if not bool(_source_audio_runtime.call("configure", _source_actor_root)):
		push_error("NUKETOWN_FULL_MAP: source audio coverage failed")
		return false

	var mystery_path := str(_source_audio_runtime.call("mystery_source_path"))
	var mystery_fallback := str(_source_audio_runtime.call("mystery_fallback_path"))
	for mystery_runtime: Node in get_tree().get_nodes_in_group("nuketown_source_mystery_runtime"):
		mystery_runtime.set("source_sfx_path", mystery_path)
		mystery_runtime.set("source_sfx_fallback", mystery_fallback)
		mystery_runtime.set_meta("source_audio_reference", "music_box_00")
		mystery_runtime.set_meta("source_audio_policy", "SOURCE_IF_MOUNTED_ELSE_FALLBACK")

	print(
		"XZOGOT_NUKETOWN_AUDIO_BRIDGE_GREEN ambient=",
		_source_audio_runtime.call("get_ambient_runtime_count"),
		" source=", _source_audio_runtime.call("get_source_stream_count"),
		" fallback=", _source_audio_runtime.call("get_fallback_stream_count"),
		" missing=", _source_audio_runtime.call("get_missing_stream_count")
	)
	return true

func _build_navigation_runtime() -> bool:
	_navigation_runtime = NUKETOWN_NAVIGATION.new() as Node3D
	if _navigation_runtime == null:
		push_error("NUKETOWN_FULL_MAP: navigation runtime instantiate failed")
		return false
	_navigation_runtime.name = "NuketownNavigationRuntime"
	add_child(_navigation_runtime)
	_navigation_runtime.call("begin_bake")

	var succeeded := false
	for _attempt in range(2400):
		if bool(_navigation_runtime.call("is_navigation_ready")):
			succeeded = true
			break
		if _navigation_runtime.has_meta("navigation_failure"):
			break
		await get_tree().create_timer(0.05).timeout

	if not succeeded:
		push_error(
			"NUKETOWN_FULL_MAP: navigation bake failed " +
			str(_navigation_runtime.get_meta("navigation_failure", "TIMEOUT"))
		)
		return false

	var round_manager := get_node_or_null("RoundManager")
	if round_manager != null:
		round_manager.set("auto_start", true)
		if round_manager.has_method("reset_network_match"):
			round_manager.call("reset_network_match")
		set_meta("round_manager_activated_from_source_nav", true)

	print(
		"XZOGOT_NUKETOWN_ROUNDS_READY nav_polygons=",
		_navigation_runtime.call("get_polygon_count"),
		" spawns=", _navigation_runtime.call("get_spawn_anchor_count")
	)
	return true

func _place_player_from_source(scene: Dictionary) -> void:
	var spawn_rows: Array[Dictionary] = []
	for raw: Variant in scene.get("actorAnchors", []):
		if raw is Dictionary:
			var row := raw as Dictionary
			if str(row.get("className", "")) == "Pavlov_Spawn":
				spawn_rows.append(row)
	if spawn_rows.is_empty():
		push_error("NUKETOWN_FULL_MAP: no source Pavlov_Spawn anchors")
		return

	spawn_rows.sort_custom(
		func(a: Dictionary, b: Dictionary) -> bool:
			return int(a.get("exportIndex", 0)) < int(b.get("exportIndex", 0))
	)
	var index := clampi(spawn_anchor_index, 0, spawn_rows.size() - 1)
	var source_transform := _transform_from_row_major(spawn_rows[index].get("matrixRowMajor", []))
	var godot_transform := Transform3D(_source_basis(), Vector3.ZERO) * source_transform

	var player := get_node_or_null("Player") as CharacterBody3D
	if player == null:
		push_error("NUKETOWN_FULL_MAP: Player node missing")
		return
	player.set("use_nav_spawn", false)
	player.global_position = godot_transform.origin + Vector3(0.0, 0.18, 0.0)
	player.rotation.y = godot_transform.basis.get_euler().y
	player.set_meta("nuketown_source_spawn_export", int(spawn_rows[index].get("exportIndex", -1)))
	print(
		"XZOGOT_NUKETOWN_SOURCE_SPAWN_GREEN ",
		player.global_position,
		" export=", player.get_meta("nuketown_source_spawn_export")
	)

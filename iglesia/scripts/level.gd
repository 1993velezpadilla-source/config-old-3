extends Node3D
## Original Iglesia nave 01. Geometry / physics authored anew in metres.
## Bench & altar GLBs are permitted ART only; no source scene, gameplay or Virin code.
const HALF_WIDTH := 8.5
const HALF_LENGTH := 15.5
const PEW_ROWS: Array[float] = [-7.1, -4.8, -2.5, -0.2, 2.1, 4.4, 6.7]
const PEW_CENTERS: Array[float] = [-4.55, 4.55]
var nav: AStarGrid2D
var stone: StandardMaterial3D
var stone_dark: StandardMaterial3D
var floor_mat: StandardMaterial3D
var wood: StandardMaterial3D
var altar_mat: StandardMaterial3D
var debug_missing_art: bool = false

func _ready() -> void:
    _materials()
    _architecture()
    _pews()
    _altar()
    _tripo_original_fixtures()
    _navigation_grid()

func _mat(color: Color, rough: float = 0.85) -> StandardMaterial3D:
    var result := StandardMaterial3D.new()
    result.albedo_color = color
    result.roughness = rough
    return result

func _materials() -> void:
    stone = _mat(Color(0.68, 0.63, 0.57), 0.93)
    var tex_path := "res://assets/materials/stone_wall_diff_4k.jpg"
    if ResourceLoader.exists(tex_path):
        stone.albedo_texture = load(tex_path)
        stone.uv1_scale = Vector3(3.0, 2.0, 1.0)
        stone.uv1_triplanar = true
    var normal_path := "res://assets/materials/stone_wall_nor_gl_4k.jpg"
    if ResourceLoader.exists(normal_path):
        stone.normal_enabled = true
        stone.normal_texture = load(normal_path)
    var rough_path := "res://assets/materials/stone_wall_rough_4k.jpg"
    if ResourceLoader.exists(rough_path):
        stone.roughness_texture = load(rough_path)
    stone_dark = _mat(Color(0.13, 0.13, 0.14))
    floor_mat = _mat(Color(0.18, 0.16, 0.16), 0.9)
    wood = _mat(Color(0.29, 0.13, 0.065))
    altar_mat = _mat(Color(0.52, 0.43, 0.35))

func _box(part_name: String, center: Vector3, box_size: Vector3, mat: Material, solid: bool = true) -> Node3D:
    var root: Node3D = StaticBody3D.new() if solid else Node3D.new()
    root.name = part_name
    root.position = center
    add_child(root)
    var shape_mesh := BoxMesh.new()
    shape_mesh.size = box_size
    var visual := MeshInstance3D.new()
    visual.mesh = shape_mesh
    visual.material_override = mat
    root.add_child(visual)
    if solid:
        var body := root as StaticBody3D
        var shape := CollisionShape3D.new()
        var box_shape := BoxShape3D.new()
        box_shape.size = box_size
        shape.shape = box_shape
        body.add_child(shape)
    return root

func _proxy(part_name: String, center: Vector3, dimensions: Vector3) -> StaticBody3D:
    var root := StaticBody3D.new()
    root.name = part_name
    root.position = center
    add_child(root)
    var col := CollisionShape3D.new()
    var box := BoxShape3D.new()
    box.size = dimensions
    col.shape = box
    root.add_child(col)
    return root

func _architecture() -> void:
    _box("SolidFloor", Vector3(0, -0.24, 0), Vector3(17.0, 0.48, 31.0), floor_mat)
    _box("WestStoneWall", Vector3(-8.5, 4.1, 0), Vector3(0.5, 8.2, 31.0), stone)
    _box("EastStoneWall", Vector3(8.5, 4.1, 0), Vector3(0.5, 8.2, 31.0), stone)
    _box("BackStoneWall", Vector3(0, 4.1, 15.5), Vector3(17.0, 8.2, 0.5), stone)
    _box("AltarStoneWall", Vector3(0, 4.1, -15.5), Vector3(17.0, 8.2, 0.5), stone)
    _box("StoneAisle", Vector3(0.0, 0.016, 0.2), Vector3(3.6, 0.03, 27.0), stone_dark, false)
    _box("ChancelStep", Vector3(0.0, 0.16, -11.55), Vector3(8.2, 0.32, 4.2), stone)
    _box("ChancelTop", Vector3(0.0, 0.37, -12.50), Vector3(7.1, 0.28, 2.3), stone)
    for z_pos in [-10.0, -4.0, 2.0, 8.0]:
        for side in [-1.0, 1.0]:
            _box("GothicPillar", Vector3(side * 7.35, 3.0, z_pos), Vector3(0.72, 6.0, 0.78), stone)
            var pane := _box("DamagedStainedGlass", Vector3(side * 8.15, 4.7, z_pos + 2.7), Vector3(0.11, 2.9, 1.55), _mat(Color(0.095, 0.20, 0.34), 0.18), false)
            pane.rotation.y = 0.0
    for x_pos in [-6.4, -3.2, 0.0, 3.2, 6.4]:
        _box("RoofTruss", Vector3(x_pos, 7.95, 0), Vector3(0.3, 0.4, 30.6), wood, false)
    _box("CeilingRidge", Vector3(0, 8.5, 0), Vector3(16.4, 0.4, 30.5), stone_dark, false)
    # One readable chalk-outline ammo wall-buy to validate economy.
    _box("MP40WallBuyBoard", Vector3(8.07, 1.56, 8.0), Vector3(0.14, 1.30, 1.55), wood, false)
    var label := Label3D.new()
    label.name = "MP40AmmoPrice"
    label.text = "MP40  +96\\n500 PUNTOS"
    label.font_size = 36
    label.pixel_size = 0.0048
    label.modulate = Color(1.0, 0.92, 0.70)
    label.position = Vector3(7.95, 1.5, 8.0)
    label.rotation_degrees.y = -90
    add_child(label)

func _import_owner_asset(file_path: String, name_text: String, pos: Vector3, max_size: Vector3, yaw: float) -> void:
    if not ResourceLoader.exists(file_path):
        debug_missing_art = true
        push_warning("IGLESIA_ART_PENDING: %s; production screenshots not approved" % file_path)
        return
    var res := load(file_path)
    if not (res is PackedScene):
        debug_missing_art = true
        push_warning("IGLESIA_GLTF_IMPORT_RED: " + file_path)
        return
    var root := (res as PackedScene).instantiate() as Node3D
    if root == null:
        debug_missing_art = true
        return
    root.name = name_text
    add_child(root)
    root.position = pos
    root.rotation.y = yaw
    # Fixed-size furniture contract: no accidental giant altar or benches.
    # Mesh bounds measured in local scene coordinates after importing.
    var source_bounds := _scene_bounds(root)
    if source_bounds.size.length() > 0.001:
        var ratio := minf(max_size.x / maxf(source_bounds.size.x, 0.01),
            minf(max_size.y / maxf(source_bounds.size.y, 0.01),
                 max_size.z / maxf(source_bounds.size.z, 0.01)))
        root.scale = Vector3.ONE * clampf(ratio, 0.02, 10.0)
        root.position.y = pos.y - source_bounds.position.y * root.scale.y
        # Keep the original mesh as visuals only. Physics proxies are separate.
    for node in root.find_children("*", "CollisionShape3D", true, false):
        (node as CollisionShape3D).disabled = true

func _scene_bounds(instance: Node3D) -> AABB:
    var merged := AABB()
    var initialized := false
    for obj in instance.find_children("*", "MeshInstance3D", true, false):
        var mesh_node := obj as MeshInstance3D
        if mesh_node.mesh == null:
            continue
        var transform_to_root := instance.global_transform.affine_inverse() * mesh_node.global_transform
        var box := mesh_node.get_aabb()
        for xi in [box.position.x, box.end.x]:
            for yi in [box.position.y, box.end.y]:
                for zi in [box.position.z, box.end.z]:
                    var p := transform_to_root * Vector3(xi, yi, zi)
                    if not initialized:
                        merged = AABB(p, Vector3.ZERO)
                        initialized = true
                    else:
                        merged = merged.expand(p)
    return merged

func _pews() -> void:
    for z in PEW_ROWS:
        for x in PEW_CENTERS:
            var pew_name := "ApprovedTripoBench_%s_%s" % [str(x), str(z)]
            _proxy("PewSolidCollision_%s" % pew_name, Vector3(x, 0.57, z), Vector3(4.25, 1.14, 0.92))
            _import_owner_asset("res://assets/bench.glb", pew_name, Vector3(x, 0, z),
                Vector3(4.25, 1.25, 1.03), deg_to_rad(180.0))
            if debug_missing_art:
                _box("DEBUG_MISSING_BENCH_ART", Vector3(x, 0.58, z), Vector3(4.25, 1.10, 0.85), _mat(Color(0.85, 0.20, 0.16)), false)

func _altar() -> void:
    # This ONE authentic Tripo altar has its own fit profile, not the generic
    # narrow 1.30 m deep auto-fit which shrank the altar. Facing toward +Z,
    # the main aisle/player, instead of facing the stone wall at -Z.
    const ALTAR_BASE_Y := 0.51  # top of our ChancelTop (0.37 + 0.28 / 2)
    const ALTAR_MAX_SIZE := Vector3(4.10, 2.38, 2.16)
    _proxy("AltarCollisionNoWalkThrough", Vector3(0.0, ALTAR_BASE_Y + ALTAR_MAX_SIZE.y * 0.5, -12.4), ALTAR_MAX_SIZE)
    _import_owner_asset("res://assets/altar.glb", "ApprovedTripoAltar", Vector3(0, ALTAR_BASE_Y, -12.4),
        ALTAR_MAX_SIZE, deg_to_rad(0.0))
    if debug_missing_art:
        _box("DEBUG_MISSING_ALTAR_ART", Vector3(0, 1.1, -12.4), Vector3(3.15, 1.5, 1.28), _mat(Color(0.88, 0.18, 0.16)), false)

func _navigation_grid() -> void:
    # Explicit grid excludes physical furniture + outer walls, so the zombies
    # cannot choose a path straight through the pews. No baked old navmesh.
    nav = AStarGrid2D.new()
    nav.region = Rect2i(0, 0, 67, 123)
    nav.cell_size = Vector2(0.25, 0.25)
    nav.diagonal_mode = AStarGrid2D.DIAGONAL_MODE_NEVER
    nav.update()
    for i in range(nav.region.size.x):
        for j in range(nav.region.size.y):
            var p := Vector3(-8.25 + float(i) * 0.25, 0, -15.25 + float(j) * 0.25)
            var solid := absf(p.x) > 7.8 or absf(p.z) > 14.65
            for z in PEW_ROWS:
                for x in PEW_CENTERS:
                    if absf(p.x - x) < 2.42 and absf(p.z - z) < 0.72:
                        solid = true
            if absf(p.x) < 1.86 and absf(p.z + 12.4) < 0.85:
                solid = true
            if solid:
                nav.set_point_solid(Vector2i(i, j), true)

func world_to_cell(pos: Vector3) -> Vector2i:
    return Vector2i(clampi(roundi((pos.x + 8.25) * 4.0), 0, 66),
        clampi(roundi((pos.z + 15.25) * 4.0), 0, 122))

func next_step(from_world: Vector3, to_world: Vector3) -> Vector3:
    var a := world_to_cell(from_world)
    var b := world_to_cell(to_world)
    if nav.is_point_solid(a) or nav.is_point_solid(b):
        return from_world
    var ids := nav.get_id_path(a, b, false)
    if ids.size() < 2:
        return from_world
    var next_id: Vector2i = ids[1]
    return Vector3(-8.25 + float(next_id.x) * 0.25, 0, -15.25 + float(next_id.y) * 0.25)


# No procedural, generated or CC0 replacement chandeliers. Load user GLBs
# only, recorded with exact SHA by tools/stage_tripo_fixtures.py.
func _tripo_original_fixtures() -> void:
    var path := "res://assets/tripo/fixtures_catalog.json"
    if not FileAccess.file_exists(path):
        debug_missing_art = true
        push_warning("TRIPO_FIXTURE_CATALOG_NOT_STAGED")
        return
    var record = JSON.parse_string(FileAccess.get_file_as_string(path))
    if not (record is Dictionary):
        debug_missing_art = true
        push_warning("TRIPO_FIXTURE_CATALOG_INVALID")
        return
    var slots: Dictionary = {}
    for entry in record.get("fixtures", []):
        if not (entry is Dictionary):
            continue
        var asset_path: String = str(entry.get("destination", ""))
        var kind: String = str(entry.get("kind", ""))
        if not asset_path.begins_with("res://assets/tripo/fixtures/"):
            debug_missing_art = true
            push_warning("TRIPO_UNVERIFIED_RESOURCE_PATH " + asset_path)
            continue
        var index: int = int(slots.get(kind, 0))
        slots[kind] = index + 1
        var anchor := Vector3.ZERO
        var dims := Vector3.ZERO
        var contact := ""
        var yaw := 0.0
        match kind:
            "ceiling_chandelier":
                # Ceiling lower plane: y=8.30. Top of original model touches it.
                anchor = Vector3(0, 8.29, clampf(-11.0 + 6.0 * float(index), -12, 11))
                dims = Vector3(2.4, 2.45, 2.4)
                contact = "top"
            "wall_sconce":
                # Wall interior planes x=±8.25, not world-air.
                var side := -1.0 if index % 2 == 0 else 1.0
                anchor = Vector3(side * 8.25, 4.25,
                    clampf(-10.5 + 4.7 * float(floori(float(index) / 2.0)), -12, 11))
                yaw = -PI * 0.5 if side < 0.0 else PI * 0.5
                dims = Vector3(1.0, 1.45, 0.8)
                contact = "back"
            "standing_candelabrum":
                var side := -1.0 if index % 2 == 0 else 1.0
                anchor = Vector3(side * 6.35, 0.02,
                    clampf(-10.5 + 4.5 * float(floori(float(index) / 2.0)), -12, 11))
                # Original Tripo triple-cup floor holders were huge on Android.
                # Stay below waist-height; do not stretch these compact props.
                dims = Vector3(0.65, 0.90, 0.65)
                contact = "bottom"
            _:
                debug_missing_art = true
                push_warning("TRIPO_UNCLASSIFIED_FIXTURE " + kind)
                continue
        if not ResourceLoader.exists(asset_path):
            debug_missing_art = true
            push_warning("TRIPO_OWNER_FIXTURE_MISSING " + asset_path)
            continue
        var packed = load(asset_path)
        if not (packed is PackedScene):
            debug_missing_art = true
            push_warning("TRIPO_OWNER_FIXTURE_IMPORT_RED " + asset_path)
            continue
        var node = (packed as PackedScene).instantiate()
        if not (node is Node3D):
            debug_missing_art = true
            node.queue_free()
            continue
        var model := node as Node3D
        add_child(model)
        var bounds: AABB = _scene_bounds(model)
        if bounds.size.length() < 0.001:
            debug_missing_art = true
            model.queue_free()
            continue
        var scale_factor := minf(dims.x / maxf(bounds.size.x, 0.001),
            minf(dims.y / maxf(bounds.size.y, 0.001),
                 dims.z / maxf(bounds.size.z, 0.001)))
        scale_factor = clampf(scale_factor, 0.0001, 100.0)
        model.scale = Vector3.ONE * scale_factor
        model.rotation.y = yaw
        var local_contact := bounds.position + bounds.size * 0.5
        if contact == "top":
            local_contact.y = bounds.end.y
        elif contact == "bottom":
            local_contact.y = bounds.position.y
        else:
            local_contact.z = bounds.end.z
        model.position = anchor - Basis(Vector3.UP, yaw) * (local_contact * scale_factor)
        model.name = "ApprovedTripo_%s_%03d" % [kind, index]
        model.add_to_group("iglesia_tripo_fixture")
        _original_tripo_practical_light(kind, anchor, index)
        model.set_meta("anchor_kind", contact)
        model.set_meta("fit_ceiling", dims)
        model.set_meta("art_original_tripo", true)
        model.set_meta("anchor_world", anchor)
        for collider in model.find_children("*", "CollisionShape3D", true, false):
            (collider as CollisionShape3D).disabled = true
        print("IGLESIA_ORIGINAL_TRIPO_FIXTURE_ANCHORED ", model.name, " ", anchor)



# Practical photons only. All fixture meshes must come from the original GLBs.
func _original_tripo_practical_light(kind: String, anchor: Vector3, index: int) -> void:
    # Four dynamic, shadowless practicals instead of eight. Their original
    # metal fixtures remain visible at every mount point.
    if kind != "ceiling_chandelier" and kind != "wall_sconce":
        return
    if index >= 4 or index % 2 != 0:
        return
    var bulb := OmniLight3D.new()
    bulb.name = "SourceTripoLight_%s_%02d" % [kind, index]
    bulb.light_color = Color(1.0, 0.61, 0.32)
    bulb.light_energy = 0.95 if kind == "ceiling_chandelier" else 0.48
    bulb.omni_range = 5.6 if kind == "ceiling_chandelier" else 3.0
    bulb.shadow_enabled = false
    bulb.position = anchor + (Vector3(0, -1.2, 0) if kind == "ceiling_chandelier" else Vector3(-0.4 if anchor.x > 0 else 0.4, 0, 0))
    add_child(bulb)

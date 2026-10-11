extends SceneTree
## Export real authored Xogot church_fresh.gd altar geometry through Godot 4.6's
## GLTFDocument, preserving original materials and coordinates. No fake GLB.
## Run: godot --headless --path tools/altar_bridge/godot --script res://export_altar.gd -- --output /abs/altar.glb

const ALTAR_PREFIXES := PackedStringArray([
	"ChancelStep", "Altar", "Reredos", "Cross"
])
const ORIGINAL_ALTAR_ORIGIN := Vector3(-17.81, 0.0, 15.82)

func _initialize() -> void:
	call_deferred("_export")

func _fail(message: String) -> void:
	push_error("XZIEL_ALTAR_GODOT_EXPORT: " + message)
	quit(1)

func _export() -> void:
	var argv := OS.get_cmdline_user_args()
	if argv.size() != 2 or argv[0] != "--output":
		_fail("expected --output /absolute/output.glb")
		return
	var path: String = argv[1]
	if not path.is_absolute_path() or not path.ends_with(".glb"):
		_fail("output must be absolute *.glb")
		return
	var church_script: Script = load("res://church_fresh.gd") as Script
	if church_script == null:
		_fail("original church_fresh.gd not available")
		return
	var church := Node3D.new()
	church.name = "GodotChurchOriginal"
	church.set_script(church_script)
	root.add_child(church) # its _ready builds genuine Godot altar and materials.

	var exported := Node3D.new()
	exported.name = "XzielAltarFromGodot"
	var count: int = 0
	var names: Array[String] = []
	for child in church.get_children():
		if not (child is MeshInstance3D):
			continue
		var match_name: bool = false
		for prefix in ALTAR_PREFIXES:
			if String(child.name).begins_with(prefix):
				match_name = true
				break
		if not match_name:
			continue
		var clone := (child as MeshInstance3D).duplicate() as MeshInstance3D
		if clone == null:
			_fail("cannot copy altar component: " + String(child.name))
			return
		exported.add_child(clone)
		clone.owner = exported
		clone.position -= ORIGINAL_ALTAR_ORIGIN
		names.append(String(child.name))
		count += 1
	if count != 11:
		_fail("Godot altar changed! Expected 11 meshes, got " + str(count))
		return
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var doc := GLTFDocument.new()
	var state := GLTFState.new()
	var err := doc.append_from_scene(exported, state)
	if err != OK:
		_fail("append_from_scene failed: " + str(err))
		return
	err = doc.write_to_filesystem(state, path)
	if err != OK:
		_fail("write_to_filesystem failed: " + str(err))
		return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() < 2048:
		_fail("GLB file empty/truncated")
		return
	print("XZIEL_GODOT_ALTAR_EXPORT_GREEN count=", count, " size=", file.get_length(), " names=", names)
	quit(0)

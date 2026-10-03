extends Node3D

const CHURCH_PATH := "res://assets/church/sanctum_current.glb"

func _ready() -> void:
	if not ResourceLoader.exists(CHURCH_PATH):
		print("XZOGOT: detailed church GLB not present; using navigation fallback visuals.")
		return
	var packed: PackedScene = load(CHURCH_PATH) as PackedScene
	if packed == null:
		push_warning("XZOGOT: failed to load " + CHURCH_PATH)
		return
	var church: Node = packed.instantiate()
	church.name = "SanctumCurrent"
	add_child(church)
	print("XZOGOT: detailed church GLB loaded.")

extends SceneTree
## Fail fast on real Godot parser before any 2GB archived Nacht sources are fetched.
func _initialize() -> void:
    var paths: Array[String]=[
        "res://nacht_real_source_vista_multimesh_visual_ab.gd",
        "res://nacht_apply_vista_spatial_multimesh_research.gd",
        "res://nacht_apply_source_exterior_visual_lod.gd",
        "res://nacht_apply_source_vista_actor_local_dds.gd"
    ]
    for path: String in paths:
        var script: Script=load(path) as Script
        if script==null or not script.can_instantiate():
            push_error("XZOGOT_NACHT_REAL_PIXEL_SOURCE_GDSCRIPT_PARSER_RED "+path)
            quit(2)
            return
    print("XZOGOT_NACHT_REAL_SOURCE_GODOT_PARSER_PREFLIGHT_GREEN scripts=",paths.size())
    quit(0)

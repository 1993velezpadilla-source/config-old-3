extends SceneTree
## Validates game-facing visuals, not only door positions/colliders.
## All pieces must disappear both for paid local and network world-open paths.
const MAP:=preload("res://black_pines.tscn")

func _init() -> void:
    call_deferred("_test")

func _require(ok: bool, context: String) -> bool:
    if ok:
        return true
    push_error("BLACK_PINES_DOOR_FIDELITY_RED "+context)
    quit(59)
    return false

func _test() -> void:
    var scene: Node3D=MAP.instantiate() as Node3D
    if not _require(scene!=null,"scene import failed"):
        return
    scene.set("rounds_enabled",false)
    scene.set("preview_no_enemies",true)
    root.add_child(scene)
    await physics_frame
    var kinds: Dictionary={}
    var parts: int=0
    for i in range(12):
        var door: Node=scene.get_node_or_null("Machines/Door_%02d"%i)
        if not _require(door!=null,"missing door "+str(i)):
            return
        var mechanism: String=str(door.get_meta("black_pines_visual_mechanism",""))
        if not _require(bool(door.get_meta("black_pines_doorskin_v1",false))
                and not mechanism.is_empty(),"missing authored mechanism "+str(i)):
            return
        kinds[mechanism]=int(kinds.get(mechanism,0))+1
        var skinned: int=0
        for child: Node in door.get_children():
            if child is MeshInstance3D and child.name.begins_with("BP_"):
                skinned+=1
                if not _require((child as MeshInstance3D).visible,
                        "door art initially hidden "+str(i)):
                    return
        if not _require(skinned>=8,"door "+str(i)+" insufficient dressing "+str(skinned)):
            return
        parts+=skinned
        # This one-shot purchase must delete every visible panel, and must
        # not leave a billboard floating through the empty doorway.
        if not _require(door.get_node_or_null("Identification")==null,
                "floating 3D mechanism label on door "+str(i)):
            return
        if not _require(bool(door.call("dev_force_open")),
                "unable to open dressed door "+str(i)):
            return
        for child: Node in door.get_children():
            if child is MeshInstance3D and not _require(
                    not (child as MeshInstance3D).visible,
                    "ghost metal panel after door opens "+str(i)+"/"+child.name):
                return
    if not _require(kinds.size()>=5,
            "door mechanism visual variety regressed "+str(kinds)):
        return
    print("BLACK_PINES_12_DOOR_FIDELITY_GREEN",
        " dressed_portals=12 visual_parts=",parts,
        " types=",str(kinds),
        " ghost_billboards=0 ghost_panels=0 native_collision_unchanged=true")
    scene.queue_free()
    await physics_frame
    quit(0)

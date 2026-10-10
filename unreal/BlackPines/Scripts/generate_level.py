"""Run in Unreal Editor via Tools > Execute Python Script.

Creates a nine-zone original Black Pines graybox. This does NOT port
Godot gameplay, BO3 map assets, zombies, or packaged Android code.
"""
import sys
from pathlib import Path
import unreal

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
from layout_model import read_layout, rooms, walls, hero_blockouts, markers

PROJECT = Path(unreal.Paths.project_dir()).resolve()
LAYOUT = PROJECT.parent.parent / "xogot" / "data" / "black_pines_layout.json"
MAP_PATH = "/Game/Maps/BlackPinesSanatorium"


def location(godot_xyz):
    x, y, z = godot_xyz
    return unreal.Vector(100.0 * x, -100.0 * z, 100.0 * y)


def scale(godot_xyz):
    x, y, z = godot_xyz
    return unreal.Vector(x, z, y)


def main():
    if not LAYOUT.is_file():
        raise RuntimeError("Missing common original layout: " + str(LAYOUT))
    data = read_layout(LAYOUT)
    assets = unreal.EditorAssetLibrary
    assets.make_directory("/Game/Maps")
    if assets.does_asset_exist(MAP_PATH):
        raise RuntimeError("Existing map protected; refusing to overwrite " + MAP_PATH)

    cube = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        raise RuntimeError("UE built-in Cube static mesh unavailable")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    if not levels.new_level(MAP_PATH, False):
        raise RuntimeError("Could not create UE editor level")

    counts = {"Floor": 0, "Wall": 0, "HeroProxy": 0, "Marker": 0}
    specs = list(rooms(data)) + list(walls(data)) + list(hero_blockouts(data))
    for spec in specs:
        actor = actors.spawn_actor_from_class(
            unreal.StaticMeshActor, location(spec["center"]))
        if not actor:
            raise RuntimeError("Could not spawn " + spec["name"])
        actor.set_actor_label(spec["name"])
        actor.set_actor_scale3d(scale(spec["dimensions"]))
        actor.get_editor_property("static_mesh_component").set_static_mesh(cube)
        counts[spec["category"]] += 1

    for name, pos in markers(data):
        actor = actors.spawn_actor_from_class(unreal.Actor, location(pos))
        if not actor:
            raise RuntimeError("Could not spawn " + name)
        actor.set_actor_label("BP_" + name)
        counts["Marker"] += 1

    sun = actors.spawn_actor_from_class(
        unreal.DirectionalLight, unreal.Vector(0, 0, 600),
        unreal.Rotator(-55, -35, 0))
    if sun:
        sun.set_actor_label("BP_Prototype_KeyLight")

    if not levels.save_current_level():
        raise RuntimeError("Could not save created Unreal level")
    unreal.log("BLACK_PINES_UNREAL_BLOCKOUT_CREATED " + str(counts))
    unreal.log("UNREAL_RENDER_AND_APK_NOT_YET_VERIFIED")


if __name__ == "__main__":
    main()

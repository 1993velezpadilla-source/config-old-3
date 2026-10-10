"""Blender GUI registration/real operator smoke; run with Blender -b --python."""
import bpy
from pathlib import Path
import sys

repo_root = Path.cwd()
sys.path.insert(0,str(repo_root/"xogot"/"tools"))
import black_pines_forge_gui as gui

gui.register()
try:
    bpy.context.scene.bp_forge_layout = str(
        repo_root/"xogot"/"data"/"black_pines_layout.json")
    bpy.context.scene.bp_forge_export = str(
        repo_root/"build"/"black-pines"/"forge-gui-test.glb")
    assert bpy.ops.bp_forge.build() == {'FINISHED'}, "GUI build operator failed"
    assert bpy.ops.bp_forge.audit() == {'FINISHED'}, "GUI audit operator failed"
    assert bpy.ops.bp_forge.export() == {'FINISHED'}, "GUI GLB export failed"
    out=repo_root/"build"/"black-pines"/"forge-gui-test.glb"
    assert out.is_file() and out.stat().st_size>10000
    print("BLACK_PINES_FORGE_GUI_REAL_OPERATOR_GREEN",
          "layout=9zones", "export_bytes=",out.stat().st_size)
finally:
    gui.unregister()

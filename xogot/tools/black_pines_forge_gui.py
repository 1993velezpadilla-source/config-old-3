"""BLACK PINES FORGE GUI — Blender sidebar for original mobile zombie map.

Install: Blender Preferences > Add-ons > Install this .py > enable.
Open 3D Viewport > N > Black Pines Forge.
No paid API, ripped game geometry, or external art dependency.
The same black_pines_author/build_forge_detail backend powers headless CI.
"""
bl_info = {
    "name": "Black Pines Forge GUI",
    "author": "ZOMBIESSSSSSS PORTABLE / Original Map Pipeline",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "3D Viewport > N > Black Pines Forge",
    "description": "Build, audit and export original Black Pines level",
    "category": "3D View",
}
import bpy
import importlib
import json
import sys
from pathlib import Path


def _backend():
    path = str(Path(__file__).resolve().parent)
    if path not in sys.path:
        sys.path.insert(0, path)
    return importlib.import_module("black_pines_author")


def _layout(scene):
    path = Path(bpy.path.abspath(scene.bp_forge_layout))
    if not path.is_file():
        raise FileNotFoundError("Forge JSON manifest missing: " + str(path))
    data = json.loads(path.read_text(encoding="utf-8"))
    _backend().validate(data)
    return data


class BP_FORGE_OT_build(bpy.types.Operator):
    bl_idname = "bp_forge.build"
    bl_label = "01 - Forge Entire Map"
    bl_description = "Rebuild all nine original rooms, details and fidelity baseline"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            api = _backend()
            data = _layout(context.scene)
            report = api.build(data)  # same build as GitHub CI!
            context.scene["bp_forge_last_report"] = json.dumps(report)
            self.report({'INFO'},
                "Forge GREEN: %d mesh objects" % report["fidelity"]["meshObjects"])
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, "BLACK_PINES_FORGE_RED: " + str(exc))
            return {'CANCELLED'}


class BP_FORGE_OT_audit(bpy.types.Operator):
    bl_idname = "bp_forge.audit"
    bl_label = "02 - Fidelity Pass"
    bl_description = "Count original room landmarks, door frames, triangles and draw nodes"

    def execute(self, context):
        try:
            api = _backend()
            result = api.forge_detail.fidelity_pass(api,_layout(context.scene))
            context.scene["bp_forge_fidelity_report"] = json.dumps(result)
            if not result["pass"]:
                self.report({'ERROR'},
                    "Fidelity RED: " + ", ".join(result["issues"]))
                return {'CANCELLED'}
            self.report({'INFO'},
                "Fidelity GREEN: %d rooms / %d tris" %
                (result["roomLandmarkCount"],result["triangles"]))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, "BLACK_PINES_FIDELITY_RED: "+str(exc))
            return {'CANCELLED'}


class BP_FORGE_OT_export(bpy.types.Operator):
    bl_idname = "bp_forge.export"
    bl_label = "03 - Export Original GLB"
    bl_description = "Require Fidelity Pass before exporting production visual mesh"

    def execute(self, context):
        try:
            api = _backend()
            result = api.forge_detail.fidelity_pass(api,_layout(context.scene))
            if not result["pass"]:
                self.report({'ERROR'},"Fidelity RED; cannot export: "+
                    ", ".join(result["issues"]))
                return {'CANCELLED'}
            filepath = Path(bpy.path.abspath(context.scene.bp_forge_export))
            filepath.parent.mkdir(parents=True,exist_ok=True)
            bpy.ops.object.select_all(action="DESELECT")
            chosen = [obj for obj in bpy.context.scene.objects if obj.type=="MESH"]
            if not chosen:
                raise RuntimeError("no Forge meshes")
            for obj in chosen:
                obj.select_set(True)
            bpy.context.view_layer.objects.active=chosen[0]
            bpy.ops.export_scene.gltf(
                filepath=str(filepath.resolve()), export_format="GLB",
                use_selection=True, export_apply=False)
            if filepath.stat().st_size<10000:
                raise RuntimeError("GLB export unexpectedly empty")
            self.report({'INFO'},"Forge GLB exported: "+str(filepath))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},"BLACK_PINES_GLTF_RED: "+str(exc))
            return {'CANCELLED'}


class BP_FORGE_PT_sidebar(bpy.types.Panel):
    bl_label = "Black Pines Forge"
    bl_idname = "BP_FORGE_PT_sidebar"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Black Pines Forge'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Original / No Ripped Assets")
        layout.prop(context.scene, "bp_forge_layout",text="Map Manifest")
        layout.operator("bp_forge.build",icon='MOD_BUILD')
        layout.operator("bp_forge.audit",icon='CHECKMARK')
        layout.prop(context.scene,"bp_forge_export",text="Output GLB")
        layout.operator("bp_forge.export",icon='EXPORT')
        layout.separator()
        layout.label(text="9 rooms / 12 doors / 12 windows")
        layout.label(text="Fidelity is gated, not 'perfect'")
        layout.label(text="Godot owns ALL collision + zombies")


CLASSES = (BP_FORGE_OT_build,BP_FORGE_OT_audit,
           BP_FORGE_OT_export,BP_FORGE_PT_sidebar)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.bp_forge_layout = bpy.props.StringProperty(
        name="Black Pines JSON",
        default="//xogot/data/black_pines_layout.json",
        subtype='FILE_PATH')
    bpy.types.Scene.bp_forge_export = bpy.props.StringProperty(
        name="Original GLB",
        default="//xogot/assets/black_pines/black_pines_architecture.glb",
        subtype='FILE_PATH')


def unregister():
    del bpy.types.Scene.bp_forge_layout
    del bpy.types.Scene.bp_forge_export
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()

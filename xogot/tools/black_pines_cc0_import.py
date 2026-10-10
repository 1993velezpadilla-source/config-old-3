"""Blender 4 import for FOUR actual 3DAssets.dev CC0 hospital props.

Downloaded binary glTF 2.0 source meshes, not generated substitutes.
Blender saves editable merged props in .blend; mobile export preserves each
as a distinct original named authored asset. No gameplay collisions changed.
"""
import json
import math
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

_IMPORTED={}

def _files():
    root=Path(__file__).resolve().parent
    manifest=root/"black_pines_cc0_manifest.json"
    if not manifest.is_file():
        manifest=root.parent/"data"/"black_pines_cc0_manifest.json"
    assets=root/"cc0_models"
    if not assets.is_dir():
        assets=root.parent/"assets"/"black_pines"/"cc0_source"
    return manifest,assets

def build(layout):
    _IMPORTED.clear()
    path,folder=_files()
    if not path.is_file():
        raise RuntimeError("BLACK_PINES_CC0_RED missing asset source manifest")
    registry=json.loads(path.read_text())
    if registry.get("license")!="CC0-1.0" or len(registry["assetSet"])!=4:
        raise RuntimeError("BLACK_PINES_CC0_RED illegal license or file count")
    rooms={str(row["id"]) for row in layout["cells"]}
    total_tris=0
    for spec in registry["assetSet"]:
        asset_id=spec["id"]
        if spec["room"] not in rooms or not asset_id.replace("_","").isalnum():
            raise RuntimeError("BLACK_PINES_CC0_RED unapproved room/id "+asset_id)
        file=folder/(asset_id+".glb")
        if not file.is_file() or file.stat().st_size<1000:
            raise RuntimeError("BLACK_PINES_CC0_RED missing actual GLB "+str(file))
        before=set(bpy.data.objects)
        bpy.ops.object.select_all(action="DESELECT")
        bpy.ops.import_scene.gltf(filepath=str(file.resolve()))
        bpy.context.view_layer.update()
        created=list(set(bpy.data.objects)-before)
        meshes=[obj for obj in created if obj.type=="MESH"]
        if not meshes:
            raise RuntimeError("BLACK_PINES_CC0_RED glTF importer returned no meshes "+asset_id)
        # Resolve all glTF pivot parent matrices into true Blender Z-up
        # geometry. This supports named wheel/head/articulation nodes.
        for obj in meshes:
            matrix=obj.matrix_world.copy()
            obj.data=obj.data.copy()
            obj.data.transform(matrix)
            obj.parent=None
            obj.matrix_world=Matrix.Identity(4)
        for obj in created:
            if obj.type=="EMPTY":
                bpy.data.objects.remove(obj,do_unlink=True)
        verts=[v.co for obj in meshes for v in obj.data.vertices]
        if not verts:
            raise RuntimeError("BLACK_PINES_CC0_RED empty model "+asset_id)
        xmid=(min(v.x for v in verts)+max(v.x for v in verts))*.5
        ymid=(min(v.y for v in verts)+max(v.y for v in verts))*.5
        floor=min(v.z for v in verts)
        x,up,z=map(float,spec["position"])
        spin=Matrix.Rotation(math.radians(float(spec.get("rotation",0))),4,"Z")
        for obj in meshes:
            obj.data.transform(Matrix.Translation(Vector((-xmid,-ymid,-floor))))
            obj.data.transform(spin)
            obj.location=Vector((x,-z,up))
        bpy.ops.object.select_all(action="DESELECT")
        for obj in meshes:
            obj.select_set(True)
        bpy.context.view_layer.objects.active=meshes[0]
        bpy.ops.object.join()
        merged=meshes[0]
        merged.name="Forge_CC0_"+asset_id
        merged.data.name=merged.name+"_Geometry"
        merged["cc0AssetPage"]=spec["page"]
        merged["cc0License"]="CC0-1.0"
        merged["cc0Room"]=spec["room"]
        merged.data.calc_loop_triangles()
        tris=len(merged.data.loop_triangles)
        if tris<100 or tris>int(spec["triangles"])*2:
            raise RuntimeError("BLACK_PINES_CC0_RED abnormal model complexity "+
                               asset_id+" triangles="+str(tris))
        total_tris+=tris
        _IMPORTED[asset_id]={"object":merged.name,"triangles":tris,
                              "room":spec["room"],"source":spec["page"]}
    if total_tris>6000 or len(_IMPORTED)!=4:
        raise RuntimeError("BLACK_PINES_CC0_RED import count/budget invalid")
    print("BLACK_PINES_FOUR_CC0_BLENDER_IMPORT_GREEN count=4 triangles="+str(total_tris))
    return {"assetCount":4,"totalTriangles":total_tris,
            "assets":dict(_IMPORTED),"license":"CC0-1.0",
            "thirdPartyAssetsDisclosed":True,
            "collisionMeshesModified":False,
            "physicalAndroidPerformanceVerified":False}

def guard():
    errors=[]
    if len(_IMPORTED)!=4:
        errors.append("CC0 Blender import did not create four assets")
    for id in ("wheelchair","iv_stand","privacy_screen","surgical_lamp"):
        obj=bpy.data.objects.get("Forge_CC0_"+id)
        if obj is None or obj.type!="MESH":
            errors.append("missing licensed real CC0 hospital mesh "+id)
        elif obj.get("cc0License")!="CC0-1.0":
            errors.append("missing asset license provenance "+id)
    return errors

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def _deps():
    import trimesh
    return trimesh


def _scene_meshes(path: Path):
    trimesh=_deps()
    loaded=trimesh.load(path,force="scene",process=False)
    meshes=[g.copy() for g in loaded.geometry.values() if hasattr(g,"faces")]
    if not meshes:
        raise RuntimeError(f"no mesh geometry in {path}")
    return meshes


def _foreground_bbox(image: Image.Image) -> tuple[int,int,int,int]:
    rgba=np.asarray(image.convert("RGBA"),dtype=np.uint8)
    h,w=rgba.shape[:2]
    alpha=rgba[:,:,3]
    use_alpha=(int(alpha.min())<245 and int(alpha.max())>8)
    if use_alpha:
        mask=alpha>24
    else:
        rgb=rgba[:,:,:3].astype(np.float32)
        patch=max(4,min(h,w)//24)
        corners=np.concatenate([
            rgb[:patch,:patch].reshape(-1,3),
            rgb[:patch,-patch:].reshape(-1,3),
            rgb[-patch:,:patch].reshape(-1,3),
            rgb[-patch:,-patch:].reshape(-1,3),
        ],axis=0)
        bg=np.median(corners,axis=0)
        mask=np.linalg.norm(rgb-bg,axis=2)>20.0

    ys,xs=np.where(mask)
    if len(xs)<128:
        return (0,0,w,h)

    x0,x1=int(xs.min()),int(xs.max())+1
    y0,y1=int(ys.min()),int(ys.max())+1
    # Keep a tiny border so hood/fingers are not clipped by imperfect masks.
    px=max(2,int((x1-x0)*0.015))
    py=max(2,int((y1-y0)*0.015))
    return (
        max(0,x0-px),
        max(0,y0-py),
        min(w,x1+px),
        min(h,y1+py),
    )


def _delivery_texture(source: Path, edge: int) -> tuple[Image.Image,dict]:
    image=Image.open(source).convert("RGBA")
    bbox=_foreground_bbox(image)
    crop=image.crop(bbox)
    # The projection maps the recovered subject bounds directly onto the native
    # x/z body bounds. Use a square delivery atlas so UV math remains trivial;
    # this is a reprojection diagnostic, not evidence of new source detail.
    crop=crop.resize((int(edge),int(edge)),Image.Resampling.LANCZOS)
    bg=Image.new("RGB",crop.size,(20,20,20))
    bg.paste(crop,mask=crop.getchannel("A"))
    return bg,{
        "source_size":[int(image.width),int(image.height)],
        "source_bbox":[int(v) for v in bbox],
        "delivery_edge":int(edge),
        "policy":"front-visible source-pixel projection; no generated texture detail",
    }


def project_source_front(
    source_image: Path,
    native_mesh: Path,
    output_glb: Path,
    *,
    texture_edge: int=4096,
) -> dict:
    trimesh=_deps()
    meshes=_scene_meshes(native_mesh)
    mesh=trimesh.util.concatenate(meshes)
    vertices=np.asarray(mesh.vertices,dtype=np.float64)
    if len(vertices)==0:
        raise RuntimeError("native mesh has no vertices")

    lo=vertices.min(axis=0)
    hi=vertices.max(axis=0)
    dx=max(float(hi[0]-lo[0]),1e-8)
    dz=max(float(hi[2]-lo[2]),1e-8)

    # Hunyuan native output is Z-up. HAYUYA's Blender evidence defines front as
    # -Y after glTF import, so x/z is the stable front projection plane.
    u=np.clip((vertices[:,0]-lo[0])/dx,0.0,1.0)
    v=np.clip((vertices[:,2]-lo[2])/dz,0.0,1.0)
    uv=np.stack([u,v],axis=1)

    texture,tex_meta=_delivery_texture(source_image,int(texture_edge))
    material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=texture,
        metallicFactor=0.0,
        roughnessFactor=0.82,
    )
    mesh.visual=trimesh.visual.TextureVisuals(uv=uv,material=material)
    try:
        mesh.fix_normals(multibody=True)
    except TypeError:
        mesh.fix_normals()

    output_glb.parent.mkdir(parents=True,exist_ok=True)
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(
            trimesh.Scene(mesh),
            include_normals=True,
        )
    )
    blob=output_glb.read_bytes()
    if blob[:4]!=b"glTF":
        raise RuntimeError("front projection produced invalid GLB")

    report={
        "schema":1,
        "method":"hayuya-native-source-front-projection-v1",
        "source_image":str(source_image),
        "native_mesh":str(native_mesh),
        "output_glb":str(output_glb),
        "faces":int(len(mesh.faces)),
        "vertices":int(len(mesh.vertices)),
        "front_axis":"-Y",
        "projection_plane":"XZ",
        "texture":tex_meta,
        "geometry_preserved":True,
        "diagnostic_only":True,
        "production_eligible":False,
        "reason":"single-view source projection must pass front face gate and later multiview Judge before promotion",
        "bytes":len(blob),
    }
    output_glb.with_suffix(".projection.json").write_text(
        json.dumps(report,indent=2)+"\n",encoding="utf-8"
    )
    print("HAYUYA_SOURCE_FRONT_PROJECTION_PASS",json.dumps(report,separators=(",",":")))
    return report


def main()->int:
    p=argparse.ArgumentParser(description="Project real source pixels onto native HAYUYA front geometry.")
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--mesh",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--texture-edge",type=int,default=4096)
    a=p.parse_args()
    project_source_front(a.source,a.mesh,a.output,texture_edge=a.texture_edge)
    return 0


if __name__=="__main__":
    raise SystemExit(main())

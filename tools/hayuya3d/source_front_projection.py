#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


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


def _delivery_texture(source: Path, edge: int):
    image=Image.open(source).convert("RGBA")
    bbox=_foreground_bbox(image)
    crop=image.crop(bbox).resize((int(edge),int(edge)),Image.Resampling.LANCZOS)

    # Build a foreground mask at reduced resolution, then extrapolate nearest
    # real subject colors through transparent/dark background. The projection
    # must color the mesh itself; source-image background must never become a
    # dark material halo around the generated silhouette.
    from scipy.ndimage import distance_transform_edt

    low_edge=min(1024,max(256,int(edge)//4))
    small=crop.resize((low_edge,low_edge),Image.Resampling.LANCZOS)
    rgba=np.asarray(small,dtype=np.uint8)
    alpha=rgba[:,:,3]
    use_alpha=(int(alpha.min())<245 and int(alpha.max())>8)

    if use_alpha:
        foreground=alpha>24
    else:
        rgbf=rgba[:,:,:3].astype(np.float32)
        patch=max(4,low_edge//24)
        corners=np.concatenate([
            rgbf[:patch,:patch].reshape(-1,3),
            rgbf[:patch,-patch:].reshape(-1,3),
            rgbf[-patch:,:patch].reshape(-1,3),
            rgbf[-patch:,-patch:].reshape(-1,3),
        ],axis=0)
        bg=np.median(corners,axis=0)
        foreground=np.linalg.norm(rgbf-bg,axis=2)>20.0

    rgb=rgba[:,:,:3].copy()
    extrapolated=False
    if int(np.count_nonzero(foreground))>=128 and np.any(~foreground):
        _,indices=distance_transform_edt(
            ~foreground,
            return_indices=True,
        )
        missing=~foreground
        rgb[missing]=rgb[
            indices[0][missing],
            indices[1][missing],
        ]
        extrapolated=True

    filled=Image.fromarray(rgb,"RGB").resize(
        (int(edge),int(edge)),
        Image.Resampling.LANCZOS,
    )
    mask=Image.fromarray(
        (foreground.astype(np.uint8)*255),
        "L",
    ).resize(
        (int(edge),int(edge)),
        Image.Resampling.LANCZOS,
    )

    # Keep exact source detail where the subject exists, using the extrapolated
    # image only outside the source foreground. Crucially, preserve the actual
    # subject silhouette in alpha so renderers can distinguish real source
    # foreground from extrapolated support pixels.
    sharp_rgb=filled.copy()
    sharp_rgb.paste(crop.convert("RGB"),mask=mask)

    # Quality pass: preserve the source photograph, but restore high-frequency
    # detail lost by the large 4K delivery resize. Keep this deliberately
    # conservative and apply it only to real foreground pixels so silhouettes
    # and extrapolated support colors cannot develop ringing/halos.
    detail_radius=max(0.8,min(1.6,float(edge)/4096.0*1.15))
    detail_rgb=sharp_rgb.filter(
        ImageFilter.UnsharpMask(
            radius=detail_radius,
            percent=118,
            threshold=2,
        )
    )
    detail_rgb=ImageEnhance.Contrast(detail_rgb).enhance(1.035)
    detail_rgb=ImageEnhance.Color(detail_rgb).enhance(1.015)
    sharp_rgb=Image.composite(detail_rgb,sharp_rgb,mask)

    sharp=sharp_rgb.convert("RGBA")
    sharp.putalpha(mask)

    # Derive a subtle PBR micro-normal map from luminance detail. This does not
    # change silhouette or base geometry; it gives cloth/skin/hood fine relief
    # in renderers that honor glTF normal textures.
    normal_edge=min(2048,int(edge))
    normal_rgb=sharp_rgb.resize(
        (normal_edge,normal_edge),
        Image.Resampling.LANCZOS,
    )
    normal_mask=mask.resize(
        (normal_edge,normal_edge),
        Image.Resampling.LANCZOS,
    )
    normal_arr=np.asarray(normal_rgb,dtype=np.float32)/255.0
    luma=(
        normal_arr[:,:,0]*0.2126+
        normal_arr[:,:,1]*0.7152+
        normal_arr[:,:,2]*0.0722
    )
    try:
        from scipy.ndimage import gaussian_filter
        luma=gaussian_filter(luma,sigma=0.75,mode="nearest")
    except Exception:
        pass
    gy,gx=np.gradient(luma)
    normal_strength=6.0
    nx=-gx*normal_strength
    ny=gy*normal_strength
    nz=np.ones_like(nx,dtype=np.float32)
    norm=np.sqrt(nx*nx+ny*ny+nz*nz)
    nx/=np.maximum(norm,1e-8)
    ny/=np.maximum(norm,1e-8)
    nz/=np.maximum(norm,1e-8)
    normal_np=np.stack([
        (nx*0.5+0.5)*255.0,
        (ny*0.5+0.5)*255.0,
        (nz*0.5+0.5)*255.0,
    ],axis=2)
    normal_np=np.clip(normal_np,0,255).astype(np.uint8)
    normal_valid=np.asarray(normal_mask,dtype=np.uint8)>24
    normal_np[~normal_valid]=np.array([128,128,255],dtype=np.uint8)
    normal_texture=Image.fromarray(normal_np,"RGB")

    # Hidden/rear surfaces must not inherit source-background pixels or the
    # nearest-edge "streaks" produced by 2D nearest-neighbour extrapolation.
    # Build a deliberately low-frequency texture from the median subject color
    # at each body height. This preserves broad hood/skin/garment color changes
    # while suppressing eyes, mouth and edge stripes on occluded geometry.
    row_rgb=np.zeros((low_edge,3),dtype=np.float32)
    row_valid=np.zeros((low_edge,),dtype=bool)
    for yy in range(low_edge):
        row_mask=foreground[yy]
        if np.any(row_mask):
            row_rgb[yy]=np.median(rgba[yy,row_mask,:3],axis=0)
            row_valid[yy]=True

    valid_rows=np.flatnonzero(row_valid)
    if len(valid_rows):
        for yy in range(low_edge):
            if not row_valid[yy]:
                nearest=valid_rows[np.argmin(np.abs(valid_rows-yy))]
                row_rgb[yy]=row_rgb[nearest]
    else:
        row_rgb[:]=np.median(rgb.reshape(-1,3),axis=0)

    try:
        from scipy.ndimage import gaussian_filter1d
        row_rgb=gaussian_filter1d(
            row_rgb,
            sigma=max(3.0,float(low_edge)/64.0),
            axis=0,
            mode="nearest",
        )
    except Exception:
        pass

    global_subject=np.median(
        rgba[foreground,:3],
        axis=0,
    ) if np.any(foreground) else np.median(rgb.reshape(-1,3),axis=0)
    row_rgb=row_rgb*0.82+global_subject[None,:]*0.18
    row_rgb=np.clip(row_rgb,0,255).astype(np.uint8)
    low_small=np.repeat(row_rgb[:,None,:],low_edge,axis=1)
    low=Image.fromarray(low_small,"RGB").resize(
        (int(edge),int(edge)),
        Image.Resampling.BICUBIC,
    )
    radius=max(16.0,float(edge)/96.0)
    low=low.filter(ImageFilter.GaussianBlur(radius=radius))
    low=ImageEnhance.Color(low).enhance(0.52)
    low=ImageEnhance.Contrast(low).enhance(0.72)

    return sharp,low,normal_texture,{
        "source_size":[int(image.width),int(image.height)],
        "source_bbox":[int(v) for v in bbox],
        "delivery_edge":int(edge),
        "low_frequency_blur_radius":float(radius),
        "foreground_background_extrapolated":bool(extrapolated),
        "hidden_surface_strategy":"smoothed_subject_height_bands",
        "visible_surface_alpha_silhouette":True,
        "visible_quality_pass":{
            "unsharp_radius":float(detail_radius),
            "unsharp_percent":118,
            "contrast":1.035,
            "color":1.015,
        },
        "normal_texture":{
            "edge":int(normal_edge),
            "strength":float(normal_strength),
            "source":"luminance_microdetail",
        },
        "policy":"detail-enhanced visible source projection plus 2K micro-normal and height-banded hidden colors",
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
    ext=hi-lo

    # Hunyuan3D's raw GLB is Y-up. The earlier diagnostic incorrectly treated
    # raw Z as height, which projected source pixels across depth and produced
    # the obvious vertical smearing seen on the Monja. Detect the dominant
    # body-height axis defensively and project the source onto the two image
    # axes. For current Hunyuan output this resolves to X/Y.
    up_axis=int(np.argmax(ext))
    if up_axis!=1:
        raise RuntimeError(
            "unexpected Hunyuan orientation for source projection: "
            f"extents={ext.tolist()} up_axis={up_axis}"
        )
    horizontal_axis=0
    depth_axis=2
    du=max(float(ext[horizontal_axis]),1e-8)
    dv=max(float(ext[up_axis]),1e-8)
    u=np.clip(
        (vertices[:,horizontal_axis]-lo[horizontal_axis])/du,
        0.0,1.0,
    )
    v=np.clip(
        (vertices[:,up_axis]-lo[up_axis])/dv,
        0.0,1.0,
    )
    uv=np.stack([u,v],axis=1)

    # Visibility-aware front projection. The old v2 path gave every layer the
    # same XY UVs, so a veil/neck surface behind the face could receive the
    # exact same facial pixels ("photo sticker on a mannequin"). Build a
    # coarse front-depth envelope in XY and texture only faces that are both
    # front-facing and on that visible envelope.
    faces=np.asarray(mesh.faces,dtype=np.int64)
    face_vertices=vertices[faces]
    face_normals=np.asarray(mesh.face_normals,dtype=np.float64)

    grid=max(256,min(1024,int(texture_edge)//4))
    gx=np.clip(np.rint(u*(grid-1)).astype(np.int64),0,grid-1)
    gy=np.clip(np.rint(v*(grid-1)).astype(np.int64),0,grid-1)

    front=np.full((grid,grid),-np.inf,dtype=np.float64)
    np.maximum.at(front,(gy,gx),vertices[:,depth_axis])

    # Expand sparse vertex samples slightly so tiny triangles whose centroid
    # falls between raster points still inherit the nearest front depth.
    try:
        from scipy.ndimage import maximum_filter
        front=maximum_filter(front,size=5,mode="nearest")
    except Exception:
        padded=np.pad(front,2,mode="edge")
        windows=[]
        for oy in range(5):
            for ox in range(5):
                windows.append(padded[oy:oy+grid,ox:ox+grid])
        front=np.maximum.reduce(windows)

    front_at_vertex=front[gy,gx]
    depth_extent=max(float(ext[depth_axis]),1e-8)
    depth_tolerance=max(depth_extent*0.0095,1e-6)
    vertex_front_visible=(
        vertices[:,depth_axis] >= (front_at_vertex-depth_tolerance)
    )
    visible_vertex_count=vertex_front_visible[faces].sum(axis=1)

    # Classify on the triangle centroid too. The old >=2 visible vertices rule
    # admitted side/internal triangles near an otherwise visible edge, which
    # created dark seam loops through the face/neck after the material split.
    face_centroids=face_vertices.mean(axis=1)
    cu=np.clip(
        (face_centroids[:,horizontal_axis]-lo[horizontal_axis])/du,
        0.0,1.0,
    )
    cv=np.clip(
        (face_centroids[:,up_axis]-lo[up_axis])/dv,
        0.0,1.0,
    )
    cgx=np.clip(np.rint(cu*(grid-1)).astype(np.int64),0,grid-1)
    cgy=np.clip(np.rint(cv*(grid-1)).astype(np.int64),0,grid-1)
    centroid_front=front[cgy,cgx]
    centroid_visible=(
        face_centroids[:,depth_axis] >=
        (centroid_front-depth_tolerance*0.78)
    )

    # +Z is Hunyuan's current source-facing direction. Require a meaningful
    # front-facing normal so near-edge side walls do not become "front".
    visible_faces=(
        centroid_visible
        & (visible_vertex_count>=1)
        & (face_normals[:,depth_axis]>0.045)
    )
    hidden_faces=~visible_faces

    texture,low_texture,normal_texture,tex_meta=_delivery_texture(source_image,int(texture_edge))
    projected_material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=texture,
        normalTexture=normal_texture,
        metallicFactor=0.0,
        roughnessFactor=0.82,
        alphaMode="MASK",
        alphaCutoff=0.08,
    )
    hidden_material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=low_texture,
        metallicFactor=0.0,
        roughnessFactor=0.90,
    )

    scene=trimesh.Scene()
    if np.any(visible_faces):
        front_mesh=mesh.submesh([np.flatnonzero(visible_faces)],append=True,repair=False)
        front_vertices=np.asarray(front_mesh.vertices,dtype=np.float64)
        fu=np.clip(
            (front_vertices[:,horizontal_axis]-lo[horizontal_axis])/du,
            0.0,1.0,
        )
        fv=np.clip(
            (front_vertices[:,up_axis]-lo[up_axis])/dv,
            0.0,1.0,
        )
        front_mesh.visual=trimesh.visual.TextureVisuals(
            uv=np.stack([fu,fv],axis=1),
            material=projected_material,
        )
        scene.add_geometry(front_mesh,node_name="source_visible_front")

    if np.any(hidden_faces):
        back_mesh=mesh.submesh([np.flatnonzero(hidden_faces)],append=True,repair=False)
        back_vertices=np.asarray(back_mesh.vertices,dtype=np.float64)
        bu=np.clip((back_vertices[:,horizontal_axis]-lo[horizontal_axis])/du,0.0,1.0)
        bv=np.clip((back_vertices[:,up_axis]-lo[up_axis])/dv,0.0,1.0)
        back_mesh.visual=trimesh.visual.TextureVisuals(
            uv=np.stack([bu,bv],axis=1),
            material=hidden_material,
        )
        scene.add_geometry(back_mesh,node_name="occluded_low_frequency")

    output_glb.parent.mkdir(parents=True,exist_ok=True)
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(
            scene,
            include_normals=True,
        )
    )
    blob=output_glb.read_bytes()
    if blob[:4]!=b"glTF":
        raise RuntimeError("front projection produced invalid GLB")

    report={
        "schema":1,
        "method":"hayuya-native-source-front-projection-v9-pbr-detail-normal-y-up",
        "source_image":str(source_image),
        "native_mesh":str(native_mesh),
        "output_glb":str(output_glb),
        "faces":int(len(mesh.faces)),
        "vertices":int(len(mesh.vertices)),
        "visible_projected_faces":int(np.count_nonzero(visible_faces)),
        "occluded_neutral_faces":int(np.count_nonzero(hidden_faces)),
        "visible_projected_fraction":float(np.mean(visible_faces)) if len(visible_faces) else 0.0,
        "depth_grid":int(grid),
        "depth_tolerance_fraction":0.0095,
        "front_normal_threshold":0.045,
        "centroid_depth_required":True,
        "source_mesh_up_axis":"Y",
        "source_mesh_front_axis":"+Z",
        "blender_evidence_front_axis":"-Y",
        "projection_plane":"XY",
        "texture":tex_meta,
        "geometry_preserved":True,
        "diagnostic_only":True,
        "production_eligible":False,
        "occlusion_aware":True,
        "frequency_split_hidden_surfaces":True,
        "reason":"single-view visibility-aware fallback; cloud texture backends remain preferred and promotion still requires face/multiview gates",
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

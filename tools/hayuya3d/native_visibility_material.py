from __future__ import annotations

from pathlib import Path


def _edge_energy(image) -> float:
    import numpy as np

    arr=np.asarray(image,dtype=np.float32)
    if arr.ndim==3:
        arr=arr[:,:,0]*0.2126+arr[:,:,1]*0.7152+arr[:,:,2]*0.0722
    if arr.shape[0]<2 or arr.shape[1]<2:
        return 0.0
    return float(
        np.abs(np.diff(arr,axis=1)).mean()
        +np.abs(np.diff(arr,axis=0)).mean()
    )


def apply_visibility_material(
    source_image:Path,
    native_mesh:Path,
    output_glb:Path,
    *,
    texture_edge:int,
)->dict:
    """Apply source detail only to +Z-visible faces of the same native mesh."""
    import numpy as np
    import trimesh
    from PIL import Image

    from source_front_projection import _delivery_texture

    scene=trimesh.load(native_mesh,force="scene",process=False)
    records=[]
    all_world=[]
    transforms={}

    for node_name in scene.graph.nodes_geometry:
        transform,geom_name=scene.graph.get(node_name)
        geom=scene.geometry[geom_name]
        if not hasattr(geom,"vertices") or not hasattr(geom,"faces"):
            continue
        transform=np.asarray(transform,dtype=np.float64)
        previous=transforms.get(geom_name)
        if previous is not None and not np.allclose(previous,transform):
            raise RuntimeError(
                "visibility material cannot safely bake shared geometry "
                f"under multiple transforms: {geom_name}"
            )
        transforms[geom_name]=transform
        local=np.asarray(geom.vertices,dtype=np.float64)
        hom=np.concatenate(
            [local,np.ones((len(local),1),dtype=np.float64)],
            axis=1,
        )
        world=(hom@transform.T)[:,:3]
        records.append((node_name,geom_name,geom,world))
        all_world.append(world)

    if not records:
        raise RuntimeError(f"no triangle geometry in {native_mesh}")

    world_all=np.concatenate(all_world,axis=0)
    lo=world_all.min(axis=0)
    hi=world_all.max(axis=0)
    ext=hi-lo
    if int(np.argmax(ext))!=1:
        raise RuntimeError(
            "visibility material expects Y-up native geometry; "
            f"extents={ext.tolist()}"
        )

    du=max(float(ext[0]),1e-8)
    dv=max(float(ext[1]),1e-8)
    edge=max(512,int(texture_edge))

    sharp,low,normal_tex,orm_tex,source_meta=_delivery_texture(
        Path(source_image),
        edge,
    )
    front_material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=sharp,
        normalTexture=normal_tex,
        metallicRoughnessTexture=orm_tex,
        occlusionTexture=orm_tex,
        metallicFactor=0.0,
        roughnessFactor=1.0,
        alphaMode="MASK",
        alphaCutoff=0.08,
    )
    hidden_material=trimesh.visual.material.PBRMaterial(
        baseColorTexture=low,
        metallicFactor=0.0,
        roughnessFactor=0.90,
    )
    materials=trimesh.visual.material.MultiMaterial(
        materials=[front_material,hidden_material]
    )

    grid=max(256,min(1024,edge//4))
    front=np.full((grid,grid),-np.inf,dtype=np.float64)
    uv_records=[]

    for _node,_name,_geom,world in records:
        u=np.clip((world[:,0]-lo[0])/du,0.0,1.0)
        v=np.clip((world[:,1]-lo[1])/dv,0.0,1.0)
        gx=np.clip(np.rint(u*(grid-1)).astype(np.int64),0,grid-1)
        gy=np.clip(np.rint(v*(grid-1)).astype(np.int64),0,grid-1)
        np.maximum.at(front,(gy,gx),world[:,2])
        uv_records.append((u,v,gx,gy))

    try:
        from scipy.ndimage import maximum_filter
        front=maximum_filter(front,size=5,mode="nearest")
    except Exception:
        padded=np.pad(front,2,mode="edge")
        windows=[
            padded[oy:oy+grid,ox:ox+grid]
            for oy in range(5)
            for ox in range(5)
        ]
        front=np.maximum.reduce(windows)

    depth_extent=max(float(ext[2]),1e-8)
    tolerance=max(depth_extent*0.0095,1e-6)
    visible_total=0
    hidden_total=0
    visible_us=[]

    for (_node,geom_name,geom,world),(u,v,gx,gy) in zip(records,uv_records):
        faces=np.asarray(geom.faces,dtype=np.int64)
        tri=world[faces]
        e1=tri[:,1]-tri[:,0]
        e2=tri[:,2]-tri[:,0]
        normals=np.cross(e1,e2)
        normals/=np.maximum(
            np.linalg.norm(normals,axis=1,keepdims=True),
            1e-12,
        )

        vertex_visible=world[:,2]>=(front[gy,gx]-tolerance)
        visible_count=vertex_visible[faces].sum(axis=1)

        centroids=tri.mean(axis=1)
        cu=np.clip((centroids[:,0]-lo[0])/du,0.0,1.0)
        cv=np.clip((centroids[:,1]-lo[1])/dv,0.0,1.0)
        cgx=np.clip(np.rint(cu*(grid-1)).astype(np.int64),0,grid-1)
        cgy=np.clip(np.rint(cv*(grid-1)).astype(np.int64),0,grid-1)
        centroid_visible=centroids[:,2]>=(front[cgy,cgx]-tolerance*0.78)

        visible=(
            centroid_visible
            &(visible_count>=1)
            &(normals[:,2]>0.045)
        )
        face_materials=np.where(visible,0,1).astype(np.int64)
        geom.visual=trimesh.visual.TextureVisuals(
            uv=np.stack([u,v],axis=1),
            material=materials,
            face_materials=face_materials,
        )
        scene.geometry[geom_name]=geom

        visible_total+=int(np.count_nonzero(visible))
        hidden_total+=int(len(visible)-np.count_nonzero(visible))
        if np.any(visible):
            ids=np.unique(faces[visible].reshape(-1))
            visible_us.append(u[ids])

    output_glb.parent.mkdir(parents=True,exist_ok=True)
    output_glb.write_bytes(
        trimesh.exchange.gltf.export_glb(scene,include_normals=True)
    )
    blob=output_glb.read_bytes()
    if blob[:4]!=b"glTF" or len(blob)<1024:
        raise RuntimeError("visibility material produced invalid GLB")

    front_u_span=0.0
    if visible_us:
        values=np.concatenate(visible_us)
        if len(values):
            front_u_span=float(values.max()-values.min())

    sharp_small=sharp.convert("RGB").resize(
        (512,512),Image.Resampling.BILINEAR
    )
    low_small=low.convert("RGB").resize(
        (512,512),Image.Resampling.BILINEAR
    )
    front_energy=_edge_energy(sharp_small)
    hidden_energy=_edge_energy(low_small)

    return {
        "schema":1,
        "method":"native-visibility-face-materials-v1",
        "source_image":str(source_image),
        "native_mesh":str(native_mesh),
        "output_glb":str(output_glb),
        "texture_edge":int(edge),
        "source_meta":source_meta,
        "visible_projected_faces":int(visible_total),
        "occluded_low_frequency_faces":int(hidden_total),
        "visible_projected_fraction":float(visible_total)/float(
            max(1,visible_total+hidden_total)
        ),
        "front_uv_span":float(front_u_span),
        "front_edge_energy":float(front_energy),
        "hidden_edge_energy":float(hidden_energy),
        "hidden_to_front_high_frequency_ratio":float(
            hidden_energy/max(front_energy,1e-6)
        ),
        "projection_plane":"XY",
        "source_mesh_front_axis":"+Z",
        "source_mesh_up_axis":"Y",
        "same_native_mesh":True,
        "face_materials_only":True,
        "geometry_replacement_allowed":False,
        "projection_proxy_created":False,
        "bytes":int(len(blob)),
    }

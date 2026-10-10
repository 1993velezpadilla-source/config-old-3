"""Forge Surface Pass 2: authored floor pattern, facade and weathering.

Original procedural geometry ONLY. A tile strip is one batchable Blender mesh
per room, not hundreds of Godot MeshInstance draws. Designed for mobile.
"""
import bpy
import math
import random
from mathutils import Vector

def build_surfaces(api, layout, cube, tube, sign):
    rnd=random.Random(20261010)
    done={}
    x=layout["cellBoundaries"]["x"]
    z=layout["cellBoundaries"]["z"]
    palette={
        "industrial":("industrial","plaster","rust"),
        "medical":("medical","plaster","ice"),
        "lobby":("lobby","medical","brass"),
        "outdoor":("outdoor","snow","wet")}
    for cell in layout["cells"]:
        name=str(cell["id"])
        col,row=int(cell["col"]),int(cell["row"])
        left,right=float(x[col]),float(x[col+1])
        near,far=float(z[row]),float(z[row+1])
        key=str(cell["floor"])
        mats=palette.get(key,palette["industrial"])
        # Faces have tiny actual grout gaps, and existing floor still carries
        # all collision. Vertex colors alone aren't trusted by glTF mobile.
        # One mesh object per entire room = 9 objects for ~1,000 tiles.
        verts=[]
        faces=[]
        mat_idx=[]
        nx=max(2, int((right-left)/.90))
        nz=max(2, int((far-near)/.90))
        dx=(right-left)/nx
        dz=(far-near)/nz
        for i in range(nx):
            for j in range(nz):
                xx=left+i*dx
                zz=near+j*dz
                if (name=="yard" and (i+j)%5==0):
                    continue
                sx=max(.08,.5*dx-.037)
                sz=max(.08,.5*dz-.037)
                px=xx+dx*.5
                pz=zz+dz*.5
                y=.018+rnd.uniform(-.001,.001)
                start=len(verts)
                # Blender native x,-z,y
                verts.extend(((px-sx,-(pz-sz),y),
                              (px+sx,-(pz-sz),y),
                              (px+sx,-(pz+sz),y),
                              (px-sx,-(pz+sz),y)))
                faces.append((start,start+1,start+2,start+3))
                h=(i*71+j*37+row*11+col*13)%43
                mat_idx.append(2 if h==0 else (1 if h<5 else 0))
        mesh=bpy.data.meshes.new("Forge_Tilemesh_"+name)
        mesh.from_pydata(verts,[],faces)
        mesh.update()
        # glTF requires UV0 for original procedural PBR tile textures.
        # One 0..1 UV tile per quad; no per-tile texture/material copies.
        uv=mesh.uv_layers.new(name="UVMap")
        quad_uv=((0.,0.),(1.,0.),(1.,1.),(0.,1.))
        for polygon in mesh.polygons:
            for corner,loop_index in enumerate(polygon.loop_indices):
                uv.data[loop_index].uv=quad_uv[corner]
        obj=bpy.data.objects.new("Forge_TiledFloor_"+name,mesh)
        bpy.context.collection.objects.link(obj)
        for m in mats:
            obj.data.materials.append(api.mat(m))
        for poly,mi in zip(obj.data.polygons,mat_idx):
            poly.material_index=mi
        api.COUNTS["trim"]+=1
        done[name]=len(faces)
        # Stenciled hospital room plates near the back and emergency wayfinding.
        # Wall-mounted, mesh-collapsed Blender default Bfont.
        wall_z=near+.28
        sign(api,"ZONE_"+name,((left+right)*.5,2.35,wall_z),
             name.upper().replace("_"," "),.30)
        # Old exposed heater and ceiling ducts, visually ABOVE player head.
        for k in range(2):
            xx=left+1.2+k*1.5
            tube(api,"CeilingConduit_%s_%d"%(name,k),
                 (xx,3.22,near+.65),(xx,3.22,far-.65),
                 .022,"dark_metal",7)
        # Small color break with shallow wall patch at safe wall corners.
        if name != "yard":
            for i in range(3):
                xx=(left+.65) if i%2==0 else (right-.65)
                zz=near+2.+i*3.
                cube(api,"PlasterWear_%s_%d"%(name,i),
                     (xx,1.20,zz),(.034,rnd.uniform(.65,1.6),
                      rnd.uniform(.44,.91)), "lobby" if i%2==0 else "wet",
                     .009,"decal")
    # Exterior recognizable sanatorium silhouette: banded concrete cornice,
    # corner buttresses, wide lit institutional marquee above entrance.
    # No collision or new traversable ledges; authoritative level stays native.
    for xx in (-17.64,17.64):
        for zz in (-14.63,20.63):
            cube(api,"FacadeCorner_%s_%s"%(xx,zz),
                 (xx,2.15,zz),(.52,4.25,.52),"industrial",.095,"trim")
    # Entrance parapet at z=+21, above 3.8m roof. Important: no overhead
    # cap through the interior, keeping roof-toggle truthful in Godot.
    cube(api,"Facade_MarqueeBack",(0,4.29,20.91),
         (10.4,.88,.40),"dark_metal",.10,"trim")
    cube(api,"Facade_MarqueeFace",(0,4.30,21.15),
         (9.98,.67,.05),"industrial",.045,"trim")
    sign(api,"FACADE",(0,4.12,21.21),"BLACK PINES SANATORIUM",.47)
    for xx in (-17.7,17.7):
        cube(api,"Facade_LeftRightCornice_"+str(xx),
             (xx,3.75,3),(.66,.22,35.0),"brass",.039,"trim")
    # Generic weathered ambulance wheel clusters; distinct from box-car.
    for i,px in enumerate((2.9,5.7)):
        for j,pz in enumerate((16.9,18.7)):
            tube(api,"Ambulance_Axle_%d_%d"%(i,j),
                 (px,.39,pz-.20),(px,.39,pz+.20),
                 .34,"dark_metal",12)
            tube(api,"Ambulance_Hub_%d_%d"%(i,j),
                 (px,.39,pz-.24),(px,.39,pz+.24),
                 .11,"brass",10)
    return {"perRoomTileFaces":done,
            "batchedRoomFloorCount":len(done),
            "facadeBranding":True,
            "mobileBatchedFloorTiles":True}

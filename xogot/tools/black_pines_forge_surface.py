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
    # FIDELITY PASS: turn the overly simple giant beige cuboid into an
    # unmistakable ORIGINAL sanatorium emergency response ambulance.
    # Roof beacon is already in hospital_kit, wheels in surface pass above.
    # All elements are visual-only; the shared yard BoxShape3D remains the
    # low-cost Godot collision authority. No third-party emblems.
    ambulance_parts = []
    def vehicle_box(name,xyz,dims,material,bevel=.019):
        obj=cube(api,"AmbulanceVisual_"+name,xyz,dims,material,bevel,"prop")
        ambulance_parts.append(obj.name)
        return obj
    # Four relieved windows, a navy medical side stripe, service door,
    # windshield and recognizable front end (vehicle front faces +X).
    # The windshield slopes WITH the original shaped front cabin.
    # Previously it was an upright box floating outside the van's hood.
    # This four-vertex translucent-profile panel is source-authored and UVd.
    window_verts=[(6.31,-17.26,1.742),
                  (6.31,-18.34,1.742),
                  (6.837,-18.38,1.086),
                  (6.837,-17.22,1.086)]
    window_mesh=bpy.data.meshes.new("BP_ActualAngledCabGlass")
    window_mesh.from_pydata(window_verts,[],[(0,1,2,3)])
    window_mesh.update()
    window_uv=window_mesh.uv_layers.new(name="UVMap")
    for loop_index,coord in zip(window_mesh.polygons[0].loop_indices,
                                ((0.,1.),(1.,1.),(1.,0.),(0.,0.))):
        window_uv.data[loop_index].uv=coord
    pane=bpy.data.objects.new("Forge_AmbulanceVisual_CabWindshield",
                              window_mesh)
    bpy.context.collection.objects.link(pane)
    window_mesh.materials.append(api.mat("dark_glass"))
    api.COUNTS["prop"]+=1
    ambulance_parts.append(pane.name)
    # Three-dimensional ORIGINAL A-pillars, glass surround and twin wipers.
    # Never fake structural windscreen borders with a rectangular billboard.
    frame_segments=[
        ("ApostNorth",(6.31,1.745,17.26),(6.837,1.086,17.22),.026),
        ("ApostSouth",(6.31,1.745,18.34),(6.837,1.086,18.38),.026),
        ("TopHeader",(6.31,1.745,17.26),(6.31,1.745,18.34),.026),
        ("WiperLeft",(6.79,1.15,17.31),(6.64,1.25,17.70),.012),
        ("WiperRight",(6.79,1.15,18.30),(6.64,1.25,17.91),.012),
    ]
    for name,begin,end,diam in frame_segments:
        obj=tube(api,"AmbulanceWindshield"+name,begin,end,
                 diam,"dark_metal",8)
        ambulance_parts.append(obj.name)
    vehicle_box("FrontGrille",(7.005,.66,17.8),(.072,.39,.85),"dark_metal",.018)
    for side,side_z,outside in (
            ("NORTH",16.936,-1),("SOUTH",18.664,1)):
        vehicle_box("SideCabWindow_"+side,
                    (6.06,1.31,side_z),(.62,.47,.034),"dark_glass",.023)
        vehicle_box("SideStripe_"+side,
                    (3.75,.84,side_z), (3.46,.17,.045),"red",.008)
        vehicle_box("SideSafetyStripe_"+side,
                    (3.75,.99,side_z), (3.46,.065,.050),"brass",.007)
        vehicle_box("SideDoorSeam_"+side,
                    (4.85,1.51,side_z),(.033,1.08,.029),"dark_metal",.006)
        vehicle_box("SideHandle_"+side,
                    (4.61,1.41,side_z+outside*.038),(.21,.045,.044),
                    "brass",.012)
        vehicle_box("SideWindowRear_"+side,
                    (2.46,1.68,side_z),(.48,.49,.032),"dark_glass",.012)
        # Unique emergency vehicle livery; DO NOT use the protected
        # Red Cross emblem or reproduce any commercial game's logos.
        sign(api,"AMBULANCE_"+side,(3.76,1.62,side_z+outside*.055),
             "BLACK PINES  /  MEDICAL",.19,
             face_negative_z=(outside<0))
    for idx,side_z in enumerate((17.26,18.34)):
        vehicle_box("FrontHeadlamp_"+str(idx),
                    (7.056,.76,side_z),(.06,.18,.34),"light",.024)
        vehicle_box("FrontIndicator_"+str(idx),
                    (7.059,.49,side_z),(.067,.11,.23),"brass",.01)
        vehicle_box("RearStopLamp_"+str(idx),
                    (1.972,.76,side_z),(.055,.20,.29),"red",.019)
    vehicle_box("FrontBumper",(7.08,.35,17.8),(.15,.16,1.80),"dark_metal",.045)
    vehicle_box("RearBumper",(1.98,.35,17.8),(.13,.16,1.88),"dark_metal",.044)
    vehicle_box("RearServiceSplit",(1.957,1.47,17.8),(.04,1.05,.039),"industrial",.009)
    vehicle_box("CabHood",(6.79,.91,17.8),(.39,.09,1.45),"industrial",.038)
    for side,zside in (("NORTH",16.72),("SOUTH",18.88)):
        vehicle_box("WingMirror_"+side,(6.71,1.23,zside),(.17,.22,.14),
                    "dark_metal",.034)
    # No protrusion through any window opening or zombie path. Bounds remain
    # inside the yard ambulance fixture and floor/collision above the wheels.
    assert len(ambulance_parts)>=20
    return {"perRoomTileFaces":done,
            "batchedRoomFloorCount":len(done),
            "facadeBranding":True,
            "ambulanceSignatureParts":len(ambulance_parts),
            "ambulanceSideLabels":2,
            "ambulanceProtectedEmblems":False,
            "mobileBatchedFloorTiles":True}

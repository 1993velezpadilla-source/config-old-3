# SPDX-License-Identifier: MIT
# Cathedral of Absolution / Cripplegate
# Autonomous Blender production builder. Generates real .blend/.glb/.fbx assets
# from the approved character bible using MPFB2 + procedural production geometry.

import argparse, importlib, json, math, random, sys, traceback
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

random.seed(260921)

def args_after_dashes():
    return sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--assets-root", required=True)
    p.add_argument("--spec", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--only", default="")
    return p.parse_args(args_after_dashes())

def dynamic_import(suffix, key):
    try:
        importlib.import_module("bl_ext.user_default.mpfb")
    except Exception:
        pass
    for n in list(sys.modules):
        if n.endswith(suffix):
            m=importlib.import_module(n)
            if hasattr(m,key): return getattr(m,key)
    raise RuntimeError(f"MPFB symbol not found: {suffix}.{key}")

def clean_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.curves,bpy.data.cameras,bpy.data.lights):
        for b in list(datablocks):
            if b.users==0: datablocks.remove(b)

def find_asset(root, basename):
    hits=list(Path(root).rglob(basename))
    hits.sort(key=lambda p:(len(p.parts),len(str(p))))
    return str(hits[0]) if hits else None

def hexrgb(s):
    s=s.lstrip("#")
    raw=[int(s[i:i+2],16)/255.0 for i in (0,2,4)]
    return tuple(c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4 for c in raw)

PALETTE={
 "spectral_ivory":"#BDB6AA","waterlogged_linen":"#9E978B","pale_corpse":"#96969A",
 "pale_spirit":"#E8E6E2","pale_drowned":"#C9D6E0","bruise_blue":"#4A5A6B",
 "water_bruise":"#6E7A8F","wet_black":"#0B0B0C","tarnished_silver":"#7A7A7F",
 "mud_silt":"#4B463B","drowned_ivory":"#D8D5C9","drowned_blue":"#5B6B7A",
 "ash_blue":"#46515F","dirty_ivory":"#B0A392","corpse_skin":"#8C8580",
 "bruise":"#6A5966","rope":"#6F5843","tarnished_brass":"#7A664A","soot":"#2E2A28",
 "choir_red":"#7A4B45","gravecoat":"#2E2A28","iron":"#3B3C40","dark_iron":"#3B3C40",
 "old_wood":"#4F392D","burgundy":"#6A3B3A","oxidized_metal":"#5E6A57",
 "oxidized_brass":"#7A664A","wax":"#D8CEC1","glass_blue":"#3A66A8",
 "glass_cyan":"#5DA3C4","glass_magenta":"#824C86","amber":"#B6814A"
}


def mat(name, color, rough=0.72, metal=0.0, emission=None, alpha=1.0, noise=True):
    m=bpy.data.materials.new(name); m.use_nodes=True
    nodes=m.node_tree.nodes; links=m.node_tree.links
    bsdf=nodes.get("Principled BSDF")
    rgb=hexrgb(color) if isinstance(color,str) else color
    bsdf.inputs["Base Color"].default_value=(*rgb,1)
    if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value=rough
    if "Metallic" in bsdf.inputs: bsdf.inputs["Metallic"].default_value=metal
    if "Alpha" in bsdf.inputs: bsdf.inputs["Alpha"].default_value=alpha
    if emission:
        e=hexrgb(emission) if isinstance(emission,str) else emission
        if "Emission Color" in bsdf.inputs: bsdf.inputs["Emission Color"].default_value=(*e,1)
        elif "Emission" in bsdf.inputs: bsdf.inputs["Emission"].default_value=(*e,1)
        if "Emission Strength" in bsdf.inputs: bsdf.inputs["Emission Strength"].default_value=1.5
    if alpha<1.0:
        m.surface_render_method='DITHERED' if hasattr(m,'surface_render_method') else 'BLENDED'
    if noise:
        lname=name.lower()
        cloth=any(k in lname for k in ("ivory","blue","linen","cloth","burgundy","spectral","robe","habit","veil","wimple"))
        skin=any(k in lname for k in ("skin","corpse","bruise","face"))
        # Broad color breakup: low-frequency, subtle.
        macro=nodes.new("ShaderNodeTexNoise")
        macro.inputs["Scale"].default_value=7.0 if cloth else (4.0 if skin else 6.0)
        macro.inputs["Detail"].default_value=3.0
        macro.inputs["Roughness"].default_value=.68
        ramp=nodes.new("ShaderNodeValToRGB")
        if cloth:
            c0=tuple(max(0,c*.78) for c in rgb)+(1,); c1=tuple(min(1,c*1.05) for c in rgb)+(1,)
        elif skin:
            c0=tuple(max(0,c*.86) for c in rgb)+(1,); c1=tuple(min(1,c*1.04) for c in rgb)+(1,)
        else:
            c0=tuple(max(0,c*.72) for c in rgb)+(1,); c1=tuple(min(1,c*1.06) for c in rgb)+(1,)
        ramp.color_ramp.elements[0].color=c0; ramp.color_ramp.elements[1].color=c1
        if cloth:
            macro.inputs["Scale"].default_value=9.0
            macro.inputs["Detail"].default_value=4.0
        links.new(macro.outputs["Fac"],ramp.inputs["Fac"]); links.new(ramp.outputs["Color"],bsdf.inputs["Base Color"])
        # Separate micro-normal: this is intentionally much finer and shallower than prior passes.
        micro=nodes.new("ShaderNodeTexNoise")
        micro.inputs["Scale"].default_value=185.0 if cloth else (120.0 if skin else 70.0)
        micro.inputs["Detail"].default_value=3.0
        micro.inputs["Roughness"].default_value=.64
        bump=nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value=.12 if cloth else (.055 if skin else .10)
        bump.inputs["Distance"].default_value=.0010 if cloth else (.00060 if skin else .0018)
        links.new(micro.outputs["Fac"],bump.inputs["Height"]); links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
    return m

def assign(o,m):
    if o.type=="MESH":
        o.data.materials.clear(); o.data.materials.append(m)
        for p in o.data.polygons: p.use_smooth=True

def local_bounds(o):
    pts=[Vector(c) for c in o.bound_box]
    lo=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)))
    hi=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)))
    return lo,hi

def apply_obj(o):
    bpy.context.view_layer.objects.active=o; o.select_set(True)
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True); o.select_set(False)

def exact_height(body,target):
    lo,hi=local_bounds(body); h=hi.z-lo.z
    if h>1e-5:
        s=target/h; body.scale=(s,s,s); apply_obj(body)

def frustum(name,z0,z1,rx0,ry0,rx1,ry1,material,segments=48,tattered=0.0,phase=0.0):
    vs=[]; fs=[]
    for ring,(z,rx,ry) in enumerate(((z0,rx0,ry0),(z1,rx1,ry1))):
        for i in range(segments):
            a=2*math.pi*i/segments
            zz=z
            if ring==0 and tattered:
                zz += tattered*(0.25+0.75*abs(math.sin(a*5+phase)))*(-1 if i%3 else -0.35)
            vs.append((rx*math.cos(a),ry*math.sin(a),zz))
    for i in range(segments):
        j=(i+1)%segments
        fs.append((i,j,segments+j,segments+i))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("ClothThickness","SOLIDIFY"); sol.thickness=0.005; sol.offset=0
    bev=o.modifiers.new("FrayedEdgeSoft","BEVEL"); bev.width=0.0025; bev.segments=2
    return o

def cube(name,loc,scale,material,bevel=.01):
    bpy.ops.mesh.primitive_cube_add(location=loc); o=bpy.context.object; o.name=name; o.scale=scale; apply_obj(o); assign(o,material)
    if bevel:
        b=o.modifiers.new("EdgeWear","BEVEL"); b.width=bevel; b.segments=2
    return o

def cyl(name,loc,radius,depth,material,verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=radius,depth=depth,location=loc); o=bpy.context.object; o.name=name; assign(o,material)
    return o

def uv_sphere(name,loc,scale,material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=16,location=loc); o=bpy.context.object; o.name=name; o.scale=scale; apply_obj(o); assign(o,material); return o

def torus(name,loc,major,minor,material,rot=(0,0,0)):
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=32,minor_segments=8,location=loc,rotation=rot)
    o=bpy.context.object; o.name=name; assign(o,material); return o

def cross_prop(name,loc,size,material):
    a=cube(name+"_V",loc,(size*.16,size*.08,size),material,size*.03)
    b=cube(name+"_H",(loc[0],loc[1],loc[2]+size*.22),(size*.58,size*.08,size*.14),material,size*.03)
    return [a,b]


def cone_between(name,p0,p1,r0,r1,material,verts=28):
    p0,p1=Vector(p0),Vector(p1)
    axis=p1-p0
    if axis.length < 1e-6:
        return None
    n=axis.normalized()
    helper=Vector((0,0,1)) if abs(n.z)<0.9 else Vector((0,1,0))
    u=n.cross(helper).normalized()
    v=n.cross(u).normalized()
    vs=[]; fs=[]
    for center,r in ((p0,r0),(p1,r1)):
        for i in range(verts):
            a=2*math.pi*i/verts
            q=center+r*(u*math.cos(a)+v*math.sin(a))
            vs.append(tuple(q))
    for i in range(verts):
        j=(i+1)%verts
        fs.append((i,j,verts+j,verts+i))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("ClothThickness","SOLIDIFY"); sol.thickness=.004; sol.offset=0
    return o


def open_veil(name,h,material,outer=True,translucent=False):
    seg=42
    rings=5
    zs=[.982,.930,.855,.745,.645] if outer else [.968,.938,.895,.840,.785]
    rxs=[.076,.086,.100,.118,.137] if outer else [.067,.073,.080,.090,.100]
    rys=[.066,.072,.079,.086,.092] if outer else [.056,.060,.064,.068,.072]
    vs=[]; fs=[]
    for r in range(rings):
        z=zs[r]*h
        for i in range(seg):
            a=-2.03 + 4.06*i/(seg-1)
            x=rxs[r]*h*math.sin(a)
            y=rys[r]*h*math.cos(a)
            zz=z
            if r==rings-1:
                zz -= (.022 if outer else .009)*h*(.2+.8*abs(math.sin(i*1.73+0.4)))
            vs.append((x,y,zz))
    for r in range(rings-1):
        for i in range(seg-1):
            a=r*seg+i; b=a+1; c=(r+1)*seg+i+1; d=(r+1)*seg+i
            fs.append((a,b,c,d))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("VeilThickness","SOLIDIFY"); sol.thickness=.0028; sol.offset=0
    sub=o.modifiers.new("VeilSmooth","SUBSURF"); sub.subdivision_type="SIMPLE"; sub.levels=1; sub.render_levels=1
    return o
def belt_loop(name,h,material,z=.555,scale_y=.72):
    o=torus(name,(0,0,z*h),.094*h,.0065*h,material)
    o.scale.y=scale_y; apply_obj(o)
    return o



def cloth_patches(prefix,h,material,count=5):
    out=[]
    placements=[(-.070,.390,.020,.025,.2),(.070,.445,.017,.022,1.1),(-.052,.515,.016,.020,2.0),(.062,.575,.014,.018,2.7),(-.078,.635,.013,.016,3.4)]
    for i,(x,z,wid,hh,ph) in enumerate(placements[:count]):
        out.append(irregular_patch(f"{prefix}_{i:02}",h,material,x,z,wid,hh,-.126,ph))
    return out

def sleeve_pair(h,material,ragged=False,cuff_material=None):
    out=[]
    for side,label in ((-1,"L"),(1,"R")):
        p0=(side*.145*h,-.006*h,.760*h)
        p1=(side*.245*h,-.018*h,.645*h)
        o=cone_between(f"Sleeve_{label}",p0,p1,.040*h,.030*h,material,36)
        if o: out.append(o)
        if ragged and o:
            cuffmat=cuff_material or material
            p2=(side*.305*h,-.020*h,.555*h)
            c=cone_between(f"CuffRag_{label}",p1,p2,.034*h,.040*h,cuffmat,30)
            if c: out.append(c)
    return out

def shoulder_bib(h,material,name="ShoulderBib",front_y=-.112):
    out=[]
    for front in (True,False):
        y=(front_y if front else .088)*h
        pts=[]
        for i in range(9):
            t=i/8; x=(-.16+.32*t)*h
            pts.append((x,y,.805*h))
        for i in reversed(range(9)):
            t=i/8; x=(-.18+.36*t)*h
            pts.append((x,y,(.695-.010*(i%2))*h))
        mesh=bpy.data.meshes.new(f"{name}{'Front' if front else 'Back'}Mesh")
        mesh.from_pydata(pts,[],[tuple(range(len(pts)))]); mesh.update()
        o=bpy.data.objects.new(f"{name}{'Front' if front else 'Back'}",mesh)
        bpy.context.collection.objects.link(o); assign(o,material)
        sol=o.modifiers.new("BibThickness","SOLIDIFY"); sol.thickness=.003; sol.offset=0
        out.append(o)
    return out


def front_panel(name,h,material,z0,z1,half_bottom,half_top,y=-.118,ragged=False):
    pts=[(-half_bottom*h,y*h,z0*h),(half_bottom*h,y*h,z0*h),(half_top*h,y*h,z1*h),(-half_top*h,y*h,z1*h)]
    if ragged:
        pts=[(-half_bottom*h,y*h,(z0+.016)*h),(-.045*h,y*h,(z0-.010)*h),(0,y*h,(z0+.005)*h),(.050*h,y*h,(z0-.012)*h),(half_bottom*h,y*h,(z0+.014)*h),(half_top*h,y*h,z1*h),(-half_top*h,y*h,z1*h)]
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(pts,[],[tuple(range(len(pts)))]); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("PanelThickness","SOLIDIFY"); sol.thickness=.0035; sol.offset=0
    bev=o.modifiers.new("PanelEdgeSoft","BEVEL"); bev.width=.0018*h; bev.segments=2
    return o

def head_wimple(body,h,mats,style):
    ivory=mats["spectral_ivory"] if style=="stained_shade" else mats["dirty_ivory"]
    fy=face_front_y(body,h)-.004*h
    out=[]
    out.append(cube("WimpleForehead",(0,fy,.955*h),(.066*h,.003*h,.014*h),ivory,.002*h))
    for side in (-1,1):
        strip=cube("WimpleSide_"+("L" if side<0 else "R"),(side*.060*h,fy,.905*h),(.012*h,.003*h,.052*h),ivory,.002*h)
        strip.rotation_euler.y=math.radians(side*5); out.append(strip)
    out.append(front_panel("WimpleChest",h,ivory,.742,.842,.135,.105,fy/h+.003,True))
    return out

def shoe_pair(h,material):
    out=[]
    for side,label in ((-1,"L"),(1,"R")):
        o=uv_sphere("Shoe_"+label,(side*.055*h,-.020*h,.040*h),(.070*h,.110*h,.038*h),material)
        o.rotation_euler.x=math.radians(4); out.append(o)
    return out

def llorona_tears(body,h,mats):
    fy=face_front_y(body,h)-.010*h
    dark=mats["wet_black"]; out=[]
    for side in (-1,1):
        x=side*.020*h
        pts=[(x,fy,.905*h),(x+side*.004*h,fy-.001*h,.885*h),(x+side*.007*h,fy-.001*h,.865*h)]
        out.append(curve_chain("TearTrail_"+("L" if side<0 else "R"),pts,dark,.0018*h))
    return out




def spectral_tatters(h,mats):
    return []

def body_group_shell(body,name,material,group_names,min_weight=.08,offset=.004):
    ids={body.vertex_groups[g].index for g in group_names if g in body.vertex_groups}
    if not ids: return None
    keep=set()
    for v in body.data.vertices:
        if any(gr.group in ids and gr.weight>=min_weight for gr in v.groups):
            keep.add(v.index)
    if not keep: return None
    o=body.copy(); o.data=body.data.copy(); o.name=name; bpy.context.collection.objects.link(o)
    bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if v.index not in keep],context='VERTS')
    bm.to_mesh(o.data); bm.free(); o.data.update()
    for v in o.data.vertices: v.co += v.normal*offset
    o.data.materials.clear(); o.data.materials.append(material)
    for p in o.data.polygons: p.material_index=0; p.use_smooth=True
    sol=o.modifiers.new("GarmentThickness","SOLIDIFY"); sol.thickness=max(.0018,offset*.65); sol.offset=1
    return o

def irregular_patch(name,h,material,x,z,w=.030,hh=.030,y=-.124,phase=0.0):
    pts=[]; n=7
    for i in range(n):
        a=2*math.pi*i/n
        rw=w*(.72+.28*abs(math.sin(phase+i*1.7)))
        rh=hh*(.70+.30*abs(math.cos(phase+i*1.2)))
        pts.append(((x+rw*math.cos(a))*h,y*h,(z+rh*math.sin(a))*h))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(pts,[],[tuple(range(n))]); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("PatchThickness","SOLIDIFY"); sol.thickness=.0015*h; sol.offset=0
    return o



def rope_belt_with_tails(h,rope_mat,metal_mat,name="RopeBelt"):
    out=[]
    belt=torus(name,(0,-.004*h,.557*h),.089*h,.0072*h,rope_mat)
    belt.scale.y=.72; apply_obj(belt); out.append(belt)
    knot=uv_sphere(name+"_Knot",(.040*h,-.081*h,.550*h),(.015*h,.010*h,.015*h),rope_mat); out.append(knot)
    out.append(curve_chain(name+"_TailA",[(.040*h,-.081*h,.550*h),(.049*h,-.088*h,.455*h),(.044*h,-.092*h,.355*h)],rope_mat,.0057*h))
    out.append(curve_chain(name+"_TailB",[(.026*h,-.080*h,.550*h),(.018*h,-.088*h,.475*h),(.024*h,-.093*h,.400*h)],rope_mat,.0050*h))
    out.extend(cross_prop(name+"_Cross",(.046*h,-.096*h,.326*h),.034*h,metal_mat))
    return out

def hood_shell(name,h,material,profile,theta_max=2.60,segments=80,phase=.0,tatter=.0):
    """Smooth open-face hood with a closed crown. No copied facial triangles."""
    vs=[]; fs=[]
    # profile entries: z, rx, ry
    top_index=0
    vs.append((0,.010*h,1.012*h))
    for r,(zf,rxf,ryf) in enumerate(profile):
        for i in range(segments):
            t=-theta_max+(2*theta_max)*i/(segments-1)
            fold=.0035*math.sin(t*4.0+phase+r*.6)+.0018*math.sin(t*7.0+r*.3)
            x=(rxf+fold)*h*math.sin(t)
            y=(ryf+.5*fold)*h*math.cos(t)
            z=zf*h+.002*h*math.sin(t*3+r*.5)
            if r==len(profile)-1 and tatter:
                z-=tatter*h*(.25+.55*abs(math.sin(i*.31+phase))+.20*abs(math.sin(i*.67)))
            vs.append((x,y,z))
    # crown fan leaves the front opening unbridged
    base=1
    for i in range(segments-1):
        fs.append((top_index,base+i,base+i+1))
    for r in range(len(profile)-1):
        a0=1+r*segments; b0=1+(r+1)*segments
        for i in range(segments-1):
            fs.append((a0+i,a0+i+1,b0+i+1,b0+i))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("HoodThickness","SOLIDIFY"); sol.thickness=.0018*h; sol.offset=0
    sub=o.modifiers.new("HoodSmooth","SUBSURF"); sub.subdivision_type="CATMULL_CLARK"; sub.levels=1; sub.render_levels=1
    return o



def sister_mouth_pose(body,h):
    fy=face_front_y(body,h)
    for v in body.data.vertices:
        z=v.co.z/h; x=abs(v.co.x/h)
        if v.co.y > fy+.045*h or x>.046: continue
        if .843<z<.854:
            v.co.z-=.0070*h
            v.co.y+=.0023*h
        elif .855<z<.866:
            v.co.z+=.0030*h
            v.co.y+=.0010*h
    body.data.update()



def sister_fitted_wimple(body,h,mats):
    """Pass 36: fitted side/chin wimple; crown/coif supplies the forehead cloth without a pasted patch."""
    ivory=mats["dirty_ivory"]; fy=face_front_y(body,h); out=[]
    # Pass 35 exposed a rectangular forehead island. Remove that copied-skin band entirely.
    # Keep only anatomy-following temple/jaw cloth, joined visually into the under-wimple.
    frame=body_region_shell(body,"NunFittedWimple",ivory,
        lambda q: (
            (.838<q.z/h<.946 and .050<abs(q.x/h)<.068 and q.y<fy+.026*h) or
            (.810<q.z/h<.850 and abs(q.x/h)<.070 and q.y<fy+.028*h)
        ),.0018*h)
    if frame:
        bev=frame.modifiers.new("WimpleEdgeSoft","BEVEL"); bev.width=.0006*h; bev.segments=2
        out.append(frame)
    under=body_region_shell(body,"NunUnderWimple",ivory,
        lambda q:.705<q.z/h<.822 and abs(q.x/h)<.138 and q.y/h<.112,.0026*h)
    if under: out.append(under)
    return out

def sister_mouth_slit(body,h,mats):
    """Clearly readable but narrow undead mouth opening on the visible facial surface."""
    fy=face_front_y(body,h)
    dark=mat("M_SisterMouthSlit","#070405",.98,0,noise=False)
    teeth=mat("M_SisterTeethHint","#766C59",.82,0,noise=False)
    pts=[(-.019*h,fy-.0040*h,.850*h),(0,fy-.0045*h,.847*h),(.019*h,fy-.0040*h,.850*h)]
    slit=curve_chain("SisterMouthSlit",pts,dark,.00155*h)
    tooth=cube("SisterTeethHint",(0,fy-.0048*h,.855*h),(.010*h,.0009*h,.0014*h),teeth,.0002*h)
    return [slit,tooth]

def sister_cloth_distress(mats):
    for key,dirt_hex,fac in (("ash_blue","#252A34",.24),("dirty_ivory","#57493E",.20)):
        m=mats.get(key)
        if not m or not m.use_nodes: continue
        nodes=m.node_tree.nodes; links=m.node_tree.links
        bsdf=nodes.get("Principled BSDF")
        if not bsdf: continue
        base=bsdf.inputs.get("Base Color")
        if not base: continue
        if base.is_linked and base.links:
            lk=base.links[0]; src=lk.from_socket; links.remove(lk)
        else:
            n=nodes.new("ShaderNodeRGB"); n.outputs[0].default_value=base.default_value; src=n.outputs[0]
        coord=nodes.new("ShaderNodeTexCoord")
        dirttex=nodes.new("ShaderNodeTexNoise")
        dirttex.inputs["Scale"].default_value=17.0; dirttex.inputs["Detail"].default_value=5.0; dirttex.inputs["Roughness"].default_value=.80
        links.new(coord.outputs["Generated"],dirttex.inputs["Vector"])
        dr=nodes.new("ShaderNodeValToRGB")
        dr.color_ramp.elements[0].position=.28; dr.color_ramp.elements[1].position=.76
        dr.color_ramp.elements[0].color=(0,0,0,1); dr.color_ramp.elements[1].color=(1,1,1,1)
        links.new(dirttex.outputs["Fac"],dr.inputs["Fac"])
        dirt=nodes.new("ShaderNodeMixRGB"); dirt.blend_type="MULTIPLY"; dirt.inputs[0].default_value=fac
        links.new(src,dirt.inputs[1]); dirt.inputs[2].default_value=(*hexrgb(dirt_hex),1)
        aged=nodes.new("ShaderNodeMixRGB"); aged.blend_type="MIX"
        links.new(dr.outputs["Color"],aged.inputs[0]); links.new(dirt.outputs["Color"],aged.inputs[1]); links.new(src,aged.inputs[2])
        wave=nodes.new("ShaderNodeTexWave"); wave.wave_type="BANDS"; wave.bands_direction="X"
        if "Scale" in wave.inputs: wave.inputs["Scale"].default_value=34.0
        if "Distortion" in wave.inputs: wave.inputs["Distortion"].default_value=6.0
        if "Detail" in wave.inputs: wave.inputs["Detail"].default_value=4.0
        links.new(coord.outputs["Generated"],wave.inputs["Vector"])
        wr=nodes.new("ShaderNodeValToRGB")
        wr.color_ramp.elements[0].color=(.78,.78,.78,1); wr.color_ramp.elements[1].color=(1.0,1.0,1.0,1)
        links.new(wave.outputs["Color"],wr.inputs["Fac"])
        woven=nodes.new("ShaderNodeMixRGB"); woven.blend_type="MULTIPLY"; woven.inputs[0].default_value=.10
        links.new(aged.outputs["Color"],woven.inputs[1]); links.new(wr.outputs["Color"],woven.inputs[2])
        links.new(woven.outputs["Color"],base)
        rough=nodes.new("ShaderNodeMapRange")
        rough.inputs["From Min"].default_value=0.0; rough.inputs["From Max"].default_value=1.0
        rough.inputs["To Min"].default_value=.70; rough.inputs["To Max"].default_value=.93
        links.new(dirttex.outputs["Fac"],rough.inputs["Value"])
        if "Roughness" in bsdf.inputs: links.new(rough.outputs["Result"],bsdf.inputs["Roughness"])

def sister_cuff_overlays(body,h,mats):
    """Dirty ivory torn lower-sleeve overlays, fitted directly to arm topology."""
    out=[]; ivory=mats["dirty_ivory"]
    for side,label in ((-1,"L"),(1,"R")):
        o=body_region_shell(body,"NunCuff_"+label,ivory,
            lambda q,side=side: q.x*side>0 and abs(q.x/h)>.205 and .575<q.z/h<.735,.0036*h)
        if o: out.append(o)
    return out


def sister_mouth_cavity(body,h,mats):
    # Pass 22 revealed the previous helper could read as a floating dark oval below
    # the chin. Keep the mouth shading on the facial material itself.
    return []

def sister_full_sleeves(rig,h,mats):
    out=[]; blue=mats["ash_blue"]; ivory=mats["dirty_ivory"]
    for side,label in (("l","L"),("r","R")):
        uh,ut=bone_points(rig,"upperarm_"+side)
        lh,lt=bone_points(rig,"lowerarm_"+side)
        if uh is None or lh is None: continue
        upper=cone_between("NunUpperSleeve_"+label,uh,ut,.043*h,.036*h,blue,40)
        lower=cone_between("NunLowerSleeve_"+label,lh,lt,.037*h,.029*h,blue,40)
        if upper: out.append(upper)
        if lower: out.append(lower)
        axis=(lt-lh).normalized()
        cuff=cone_between("NunCuff_"+label,lt-axis*.012*h,lt+axis*.030*h,.031*h,.034*h,ivory,36)
        if cuff: out.append(cuff)
    return out








def sister_paint_footwear(body,h):
    leather=mat("M_SisterFootLeather","#211D1C",.78,0,noise=True)
    idx=len(body.data.materials); body.data.materials.append(leather)
    for p in body.data.polygons:
        c=p.center
        if c.z/h < .110:
            p.material_index=idx






def sister_shoe_from_body(body,h,side,label,material):
    pts=[v.co.copy() for v in body.data.vertices if v.co.z/h < .118 and v.co.x*side>0]
    if not pts: return []
    xmin=min(p.x for p in pts); xmax=max(p.x for p in pts)
    ymin=min(p.y for p in pts); ymax=max(p.y for p in pts)
    zmin=min(p.z for p in pts); zmax=max(p.z for p in pts)
    cx=(xmin+xmax)*.5; cy=(ymin+ymax)*.5-.012*h
    sx=max((xmax-xmin)*.56,.038*h)
    sy=max((ymax-ymin)*.60,.075*h)
    sz=max((zmax-zmin)*.36,.022*h)
    shoe=cube("SisterShoe_"+label,(cx,cy,zmin+sz*.95),(sx,sy,sz),material,.012*h)
    # low sole extends slightly forward and sideways, like the worn shoes in the concept
    sole=cube("SisterSole_"+label,(cx,cy-.006*h,zmin+.006*h),(sx*1.05,sy*1.05,.008*h),material,.006*h)
    return [shoe,sole]






def sister_extremity_decay(body,h):
    hand=mat("M_SisterHandDecay","#8A7B7F",.88,0,noise=True)
    idx=len(body.data.materials); body.data.materials.append(hand)
    for p in body.data.polygons:
        c=p.center
        if abs(c.x/h)>.225 and .445<c.z/h<.635:
            p.material_index=idx

def sister_face_scars(body,h,mats):
    fy=face_front_y(body,h)
    scar=mat("M_SisterScar","#4B2630",.82,0,noise=False)
    out=[]
    lines=[
      [(-.045*h,fy-.0018*h,.900*h),(-.030*h,fy-.0022*h,.886*h),(-.015*h,fy-.0018*h,.877*h)],
      [(.030*h,fy-.0018*h,.925*h),(.043*h,fy-.0022*h,.910*h),(.051*h,fy-.0018*h,.892*h)],
      [(-.052*h,fy-.0015*h,.850*h),(-.040*h,fy-.0018*h,.842*h)]
    ]
    for i,pts in enumerate(lines):
        out.append(curve_chain(f"SisterScar_{i:02}",pts,scar,.00055*h))
    return out




def sister_boot_pair(body,rig,h,mats):
    """Pass 34: compact closed low shoes; one upper + thin sole, no spherical toe proxies."""
    leather=mat('M_SisterBootLeather','#171516',.80,0,noise=True)
    sole_mat=mat('M_SisterBootSole','#0C0B0C',.90,0,noise=True)
    out=[]
    for sign,label,bone in ((-1,'L','foot_l'),(1,'R','foot_r')):
        pts=[v.co for v in body.data.vertices if v.co.z/h<.090 and v.co.x*sign>.010*h]
        if pts:
            cx=sum(p.x for p in pts)/len(pts); cy=sum(p.y for p in pts)/len(pts)
        else:
            cx=sign*.045*h; cy=-.015*h
        # Pass 36: slimmer closed low shoe, pulled over the anatomical foot instead of sitting outside it.
        upper=cube('SisterShoe_'+label,(cx,cy-.004*h,.030*h),(.030*h,.052*h,.026*h),leather,.010*h)
        out.append(upper)
        sol=cube('SisterSole_'+label,(cx,cy-.006*h,.008*h),(.032*h,.055*h,.0050*h),sole_mat,.0030*h)
        out.append(sol)
    return out

def nun_coif_cap(name,h,material,rx,ry,rz,cz,phase=0.0):
    """Closed crown with a progressively opening face aperture."""
    seg=96
    ring_specs=[
        (.18,math.pi),(.38,math.pi),(.58,3.05),(.78,2.86),
        (.98,2.66),(1.16,2.52),(1.34,2.42)
    ]
    vs=[(0,.008*h,(cz+rz)*h)]; fs=[]
    rings=[]
    for ridx,(phi,tmax) in enumerate(ring_specs):
        base=len(vs); rings.append((base,tmax))
        for i in range(seg):
            u=i/(seg-1)
            t=-tmax+2*tmax*u
            r=math.sin(phi)
            fold=.0018*math.sin(t*5+phase+ridx*.4)
            x=(rx*r+fold)*h*math.sin(t)
            y=(.008+ry*r*math.cos(t))*h
            z=(cz+rz*math.cos(phi)+.0015*math.sin(t*4+ridx*.6))*h
            vs.append((x,y,z))
    # top fan
    b0=rings[0][0]
    for i in range(seg-1): fs.append((0,b0+i,b0+i+1))
    # connect rings by index (opening widens smoothly lower down)
    for r in range(len(rings)-1):
        a0=rings[r][0]; b0=rings[r+1][0]
        for i in range(seg-1):
            fs.append((a0+i,a0+i+1,b0+i+1,b0+i))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("CoifThickness","SOLIDIFY"); sol.thickness=.0020*h; sol.offset=0
    sub=o.modifiers.new("CoifSmooth","SUBSURF"); sub.subdivision_type="CATMULL_CLARK"; sub.levels=1; sub.render_levels=1
    return o






def wimple_face_frame(body,h,material):
    """Soft oval wimple framing the face; closes the exposed scalp/hairline without covering facial features."""
    fy=face_front_y(body,h)
    seg=80; cz=.895*h; y=fy-.006*h
    inner_rx=.052*h; inner_rz=.080*h
    outer_rx=.066*h; outer_rz=.098*h
    vs=[]; fs=[]
    for ring,(rx,rz) in enumerate(((outer_rx,outer_rz),(inner_rx,inner_rz))):
        for i in range(seg):
            a=2*math.pi*i/seg
            x=rx*math.cos(a)
            z=cz+rz*math.sin(a)
            yy=y-.0015*h*math.cos(a*2)
            vs.append((x,yy,z))
    for i in range(seg):
        j=(i+1)%seg
        fs.append((i,j,seg+j,seg+i))
    mesh=bpy.data.meshes.new("WimpleFaceFrameMesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new("WimpleFaceFrame",mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("WimpleThickness","SOLIDIFY"); sol.thickness=.0020*h; sol.offset=0
    bev=o.modifiers.new("WimpleSoft","BEVEL"); bev.width=.0012*h; bev.segments=2
    sub=o.modifiers.new("WimpleSmooth","SUBSURF"); sub.subdivision_type="CATMULL_CLARK"; sub.levels=1; sub.render_levels=1
    return o










def sister_wimple_frame(body,h,material):
    """Pass 34: one continuous fitted U-shaped cloth ribbon from jaw to jaw over the brow."""
    fy=face_front_y(body,h)
    n=72; center_z=.895*h; rx=.055*h; rz=.072*h
    inner=[]; outer=[]
    # Front-facing upper/side arc only: left jaw -> brow -> right jaw. No floating vertical bars.
    for i in range(n):
        t=i/(n-1)
        a=math.pi*(1.08-1.16*t)  # slightly below left temple across brow to right temple
        x=rx*math.cos(a)
        z=center_z+rz*math.sin(a)
        # Pull cloth close to facial surface; subtle depth/fold variation only.
        y=fy+(.0035+.0020*math.cos(a*2.0))*h
        nx=math.cos(a); nz=math.sin(a)
        half=.0042*h
        inner.append((x-half*nx,y,z-half*nz))
        outer.append((x+half*nx,y,z+half*nz))
    vs=inner+outer; fs=[]
    for i in range(n-1): fs.append((i,i+1,n+i+1,n+i))
    mesh=bpy.data.meshes.new('SisterWimpleFrameMesh'); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new('SisterWimpleFrame',mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new('WimpleThickness','SOLIDIFY'); sol.thickness=.0014*h; sol.offset=0
    bev=o.modifiers.new('WimpleSoft','BEVEL'); bev.width=.0007*h; bev.segments=3
    sub=o.modifiers.new('WimpleSmooth','SUBSURF'); sub.subdivision_type='CATMULL_CLARK'; sub.levels=2; sub.render_levels=2
    return o

def sister_mouth_slit(body,h,mats):
    fy=face_front_y(body,h)
    dark=mat("M_SisterMouthSlit","#11090D",.94,0,noise=False)
    pts=[(-.017*h,fy-.0010*h,.850*h),(0,fy-.0015*h,.8485*h),(.017*h,fy-.0010*h,.850*h)]
    return curve_chain("SisterMouthSlit",pts,dark,.00115*h)




def sister_layered_hem(h,mats):
    ivory=mats["dirty_ivory"]; blue=mats["ash_blue"]; out=[]
    a=garment_shell("IvoryRagLayerA",h,ivory,[
        (.045,.130,.088,0),(.095,.141,.095,0),(.155,.144,.097,0),(.220,.141,.095,0),(.290,.133,.091,0),(.375,.119,.084,0)
    ],120,.090,.82,1)
    b=garment_shell("IvoryRagLayerB",h,ivory,[
        (.075,.136,.092,0),(.120,.146,.098,0),(.175,.146,.097,0),(.230,.141,.095,0),(.285,.131,.090,0)
    ],120,.082,1.70,1)
    out.extend([a,b])
    punch_cloth_holes(a,h,[(-.060,.205,.017,.028,True),(.074,.300,.017,.026,False)])
    punch_cloth_holes(b,h,[(.045,.145,.015,.023,True),(-.082,.255,.014,.022,False)])
    for i,(x,z,wid,hh,ph) in enumerate([(-.082,.320,.011,.038,.3),(-.030,.300,.010,.034,1.1),(.036,.330,.011,.040,2.0),(.088,.292,.010,.036,2.9)]):
        out.append(irregular_patch(f"BlueRagTab_{i:02}",h,blue,x,z,wid,hh,-.103,ph))
    return out

def sister_fitted_face_wimple(body,h,mats):
    ivory=mats["dirty_ivory"]; out=[]; fy=face_front_y(body,h)
    # Forehead band hugs actual forehead.
    a=body_region_shell(body,"NunForeheadWimple",ivory,
        lambda q:.938<q.z/h<.982 and abs(q.x/h)<.070 and q.y<fy+.030*h,.0032*h)
    if a: out.append(a)
    # Temple/jaw strips frame face without forming a floating ring.
    l=body_region_shell(body,"NunTempleWimple_L",ivory,
        lambda q:.842<q.z/h<.952 and -.080<q.x/h<-.048 and q.y<fy+.036*h,.0030*h)
    r=body_region_shell(body,"NunTempleWimple_R",ivory,
        lambda q:.842<q.z/h<.952 and .048<q.x/h<.080 and q.y<fy+.036*h,.0030*h)
    if l: out.append(l)
    if r: out.append(r)
    chin=body_region_shell(body,"NunChinWimple",ivory,
        lambda q:.800<q.z/h<.845 and abs(q.x/h)<.085 and q.y<fy+.040*h,.0030*h)
    if chin: out.append(chin)
    return out

def sister_closed_shoes(body,h,mats):
    """Pass 30: fitted low-profile closed shoes, no sphere/toe proxies."""
    leather=mat("M_SisterClosedShoes","#171516",.82,0,noise=True)
    sole_mat=mat("M_SisterSole","#0D0C0D",.90,0,noise=True)
    out=[]
    for sign,label in ((-1,"L"),(1,"R")):
        # Build a shallow closed upper from the actual foot surface so scale follows anatomy.
        upper=body_region_shell(body,"SisterShoeUpper_"+label,leather,
            lambda q,sign=sign: q.x*sign>.012*h and q.z/h<.075,.0045*h)
        if upper: out.append(upper)
        pts=[v.co for v in body.data.vertices if v.co.x*sign>.012*h and v.co.z/h<.075]
        if pts:
            minx,maxx=min(q.x for q in pts),max(q.x for q in pts)
            miny,maxy=min(q.y for q in pts),max(q.y for q in pts)
            minz=min(q.z for q in pts)
            sole=cube("SisterSole_"+label,((minx+maxx)/2,(miny+maxy)/2,minz+.004*h),
                ((maxx-minx)*.54,(maxy-miny)*.54,.005*h),sole_mat,.002*h)
            out.append(sole)
    return out

def sister_face_scars(body,h,mats):
    fy=face_front_y(body,h)
    scar=mat("M_SisterScar","#4A242A",.82,0,noise=False)
    out=[]
    out.append(curve_chain("SisterScarCheek",[
        (-.058*h,fy-.0035*h,.884*h),(-.046*h,fy-.0042*h,.872*h),(-.036*h,fy-.0038*h,.858*h)
    ],scar,.00055*h))
    out.append(curve_chain("SisterScarBrow",[
        (.014*h,fy-.0035*h,.932*h),(.026*h,fy-.0040*h,.925*h),(.038*h,fy-.0032*h,.918*h)
    ],scar,.00045*h))
    return out




def sister_wimple_fitted(body,h,material):
    fy=face_front_y(body,h)
    return body_region_shell(body,"SisterWimpleFitted",material,
        lambda q: (
            (.947<q.z/h<.978 and abs(q.x/h)<.070 and q.y<fy+.040*h) or
            (.842<q.z/h<.952 and .048<abs(q.x/h)<.079 and q.y<fy+.045*h) or
            (.812<q.z/h<.850 and abs(q.x/h)<.062 and q.y<fy+.050*h)
        ),.0032*h)

def punch_cloth_holes(obj,h,spots):
    if not obj or obj.type!="MESH": return
    bm=bmesh.new(); bm.from_mesh(obj.data)
    doomed=[]
    for f in bm.faces:
        c=f.calc_center_median()
        x=c.x/h; y=c.y/h; z=c.z/h
        for sx,sz,rx,rz,front_only in spots:
            if front_only and y>0: continue
            if ((x-sx)/rx)**2 + ((z-sz)/rz)**2 < 1.0:
                doomed.append(f); break
    if doomed:
        bmesh.ops.delete(bm,geom=doomed,context='FACES')
    bm.to_mesh(obj.data); bm.free(); obj.data.update()

def sister_shoe_box(name,center,axis,h,material):
    o=cube(name,tuple(center),(.056*h,.092*h,.026*h),material,.012*h)
    o.rotation_mode="QUATERNION"; o.rotation_quaternion=axis.to_track_quat("Y","Z")
    return o




def priority_head_cover(body,h,style,mats):
    out=[]
    if style=="sister_of_ash":
        ivory=mats["dirty_ivory"]; blue=mats["ash_blue"]
        out.append(nun_coif_cap("NunInnerCoif",h,ivory,.069,.059,.108,.899,.10))
        out.append(nun_coif_cap("NunOuterHood",h,blue,.078,.067,.119,.898,.60))
        out.extend(sister_fitted_wimple(body,h,mats))
        # soft neck cloth closes the throat transition without a flat bib
        neck=body_region_shell(body,"NunNeckWimple",ivory,
            lambda q:.742<q.z/h<.835 and abs(q.x/h)<.120 and q.y/h<.145,.0030*h)
        if neck: out.append(neck)
        out.append(drape_open("NunBackVeil",h,blue,[
            (.946,.064,.055),(.916,.071,.061),(.882,.079,.067),(.846,.088,.074),
            (.812,.098,.081),(.780,.110,.089),(.750,.122,.097),(.722,.134,.104)
        ],segments=112,theta_max=2.56,tatter=.070,phase=.66,subdiv=2))
    elif style=="stained_shade":
        out.append(nun_coif_cap("ShadeHood",h,mats["spectral_ivory"],.080,.070,.120,.894,.55))
    elif style=="la_llorona":
        out.append(nun_coif_cap("HairCap",h,mats["wet_black"],.079,.069,.118,.894,.3))
    return out

def eye_socket_rings(body,h,mats,style):
    return []

def stained_cloth_accents(h,mats):
    cols=[mats["glass_blue"],mats["glass_cyan"],mats["glass_magenta"],mats["amber"]]
    out=[]
    spots=[(-.112,.66,.012,.022,.4),(.110,.61,.010,.020,1.2),(-.095,.49,.011,.019,2.0),(.100,.43,.010,.018,2.7),(-.120,.31,.009,.017,3.4)]
    for i,(x,z,wid,hh,ph) in enumerate(spots):
        out.append(irregular_patch(f"StainedCloth_{i:02}",h,cols[i%len(cols)],x,z,wid,hh,-.128,ph))
    return out




def cut_mouth_open(body,h,style):
    if style=="sister_of_ash": return
    fy=face_front_y(body,h)
    bm=bmesh.new(); bm.from_mesh(body.data)
    doomed=[]
    for f in bm.faces:
        c=f.calc_center_median(); z=c.z/h; x=abs(c.x/h)
        if .842 < z < .859 and x < .023 and c.y < fy + .018*h:
            doomed.append(f)
    if doomed: bmesh.ops.delete(bm,geom=doomed,context='FACES')
    bm.to_mesh(body.data); bm.free(); body.data.update()

def eye_socket_discs(body,h,mats,style):
    fy=face_front_y(body,h)
    col="#473A43" if style!="stained_shade" else "#46525E"
    m=mat("M_"+style+"_SocketShade",col,.90,0,noise=True)
    out=[]
    for side in (-1,1):
        o=uv_sphere("SocketShade_"+("L" if side<0 else "R"),(side*.020*h,fy-.004*h,.904*h),(.016*h,.0020*h,.010*h),m)
        out.append(o)
    return out












def paint_face_regions(body,h,mats,style):
    if style!="sister_of_ash": return
    fy=face_front_y(body,h)
    def make_attr(name,fn):
        old=body.data.color_attributes.get(name)
        if old: body.data.color_attributes.remove(old)
        attr=body.data.color_attributes.new(name=name,type='FLOAT_COLOR',domain='CORNER')
        for poly in body.data.polygons:
            for li in poly.loop_indices:
                v=body.data.vertices[body.data.loops[li].vertex_index].co
                a=max(0.0,min(1.0,fn(v))); attr.data[li].color=(a,a,a,1)
        return attr
    def g(v,cx,cz,rx,rz):
        dx=(v.x/h-cx)/rx; dz=(v.z/h-cz)/rz
        front=max(0.0,min(1.0,1.0-(v.y-fy)/(.074*h)))
        return math.exp(-(dx*dx+dz*dz)*1.02)*front
    eye_attr=make_attr("SisterEyeMask",lambda v:max(
        1.10*g(v,-.022,.905,.043,.035),.88*g(v,.022,.907,.041,.033),
        1.00*g(v,-.050,.874,.054,.044),.78*g(v,.050,.875,.052,.042)))
    cheek_attr=make_attr("SisterCheekMask",lambda v:max(
        .94*g(v,-.052,.867,.056,.056),.74*g(v,.052,.869,.053,.053)))
    temple_attr=make_attr("SisterTempleMask",lambda v:max(
        .76*g(v,-.061,.926,.045,.054),.58*g(v,.061,.927,.043,.052)))
    nose_attr=make_attr("SisterNoseMask",lambda v:.46*g(v,0,.883,.031,.046))
    mouth_attr=make_attr("SisterMouthMask",lambda v:1.00*g(v,0,.849,.048,.024))
    eye_col=hexrgb("#1C151D"); cheek_col=hexrgb("#443239"); temple_col=hexrgb("#554149"); nose_col=hexrgb("#604B53"); lip=hexrgb("#10080C")
    for m in body.data.materials:
        if not m: continue
        m.use_nodes=True; nodes=m.node_tree.nodes; links=m.node_tree.links
        bsdf=nodes.get("Principled BSDF")
        if not bsdf: continue
        base=bsdf.inputs.get("Base Color")
        if not base: continue
        if base.is_linked and base.links:
            prev=base.links[0].from_socket; links.remove(base.links[0])
        else:
            prevn=nodes.new("ShaderNodeRGB"); prevn.outputs[0].default_value=base.default_value; prev=prevn.outputs[0]
        def mix_attr(attr,color,src):
            vc=nodes.new("ShaderNodeVertexColor"); vc.layer_name=attr.name
            mx=nodes.new("ShaderNodeMixRGB"); mx.blend_type="MIX"
            links.new(vc.outputs["Color"],mx.inputs[0]); links.new(src,mx.inputs[1]); mx.inputs[2].default_value=(*color,1)
            return mx.outputs["Color"]
        c1=mix_attr(temple_attr,temple_col,prev)
        c2=mix_attr(cheek_attr,cheek_col,c1)
        c3=mix_attr(nose_attr,nose_col,c2)
        c4=mix_attr(eye_attr,eye_col,c3)
        c5=mix_attr(mouth_attr,lip,c4)
        links.new(c5,base)
    vg=body.vertex_groups.get("FaceDamage") or body.vertex_groups.new(name="FaceDamage")
    ids=[v.index for v in body.data.vertices if .823<v.co.z/h<.968 and abs(v.co.x/h)<.095 and v.co.y<fy+.064*h]
    if ids: vg.add(ids,1.0,"REPLACE")
    tex=bpy.data.textures.new("T_SisterFaceDamage",type="CLOUDS"); tex.noise_scale=.011; tex.noise_depth=2
    dis=body.modifiers.new("FaceDamage","DISPLACE"); dis.texture=tex; dis.strength=.00090*h; dis.mid_level=.5; dis.vertex_group=vg.name

def mouth_cavity(body,h,mats,style):
    if style=="sister_of_ash": return []
    fy=face_front_y(body,h)
    dark=mat("M_"+style+"_Cavity","#100B0D",.94,0,noise=False)
    cavity=uv_sphere("MouthCavity",(0,fy-.006*h,.850*h),(.019*h,.0022*h,.010*h),dark)
    return [cavity]

def body_region_shell(body,name,material,keep_fn,offset=0.004):
    """Copy an exact body surface region so clothing follows anatomy and inherited skin weights."""
    o=body.copy(); o.data=body.data.copy(); o.name=name
    bpy.context.collection.objects.link(o)
    bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table()
    kill=[v for v in bm.verts if not keep_fn(v.co)]
    bmesh.ops.delete(bm,geom=kill,context='VERTS')
    bm.to_mesh(o.data); bm.free()
    o.data.update()
    # Push the garment slightly off the skin along vertex normals.
    for v in o.data.vertices:
        v.co += v.normal*offset
    o.data.materials.clear(); o.data.materials.append(material)
    for p in o.data.polygons:
        p.material_index=0; p.use_smooth=True
    # Keep inherited armature modifier and weights from body.copy().
    sol=o.modifiers.new("GarmentThickness","SOLIDIFY"); sol.thickness=max(.0018,offset*.65); sol.offset=1
    return o













def fitted_priority_clothes(body,h,style,mats):
    out=[]
    if style=="sister_of_ash":
        main=mats["ash_blue"]; ivory=mats["dirty_ivory"]
        bod=body_region_shell(body,"FittedBodice",main,
            lambda q:.525<q.z/h<.805 and abs(q.x/h)<.150 and q.y/h<.145,.0034*h)
        if bod: out.append(bod)
        # Coordinate-based fitted sleeves guarantee upper arm + forearm coverage.
        l=body_region_shell(body,"NunSleeve_L",main,
            lambda q:-.365<q.x/h<-.095 and .505<q.z/h<.805,.0037*h)
        r=body_region_shell(body,"NunSleeve_R",main,
            lambda q:.095<q.x/h<.365 and .505<q.z/h<.805,.0037*h)
        if l: out.append(l)
        if r: out.append(r)
        # Dirty ivory cuffs close to wrists.
        lc=body_region_shell(body,"NunCuff_L",ivory,
            lambda q:-.360<q.x/h<-.180 and .490<q.z/h<.600,.0040*h)
        rc=body_region_shell(body,"NunCuff_R",ivory,
            lambda q:.180<q.x/h<.360 and .490<q.z/h<.600,.0040*h)
        if lc: out.append(lc)
        if rc: out.append(rc)
    elif style=="stained_shade":
        main=mats["ash_blue"]
        o=body_region_shell(body,"FittedBodice",main,lambda q:.515<q.z/h<.795 and abs(q.x/h)<.160 and q.y/h<.140,.0045*h)
        if o: out.append(o)
    elif style=="la_llorona":
        main=mats["spectral_ivory"]
        o=body_region_shell(body,"LloronaFittedBodice",main,lambda q:.510<q.z/h<.830 and abs(q.x/h)<.165 and q.y/h<.140,.0045*h)
        if o: out.append(o)
    return out

def rigid_bind_mesh(obj,rig,bone):
    if not obj or obj.type!="MESH" or bone not in rig.data.bones: return
    # Remove stale armature modifiers first.
    for mod in list(obj.modifiers):
        if mod.type=="ARMATURE": obj.modifiers.remove(mod)
    vg=obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
    if len(obj.data.vertices):
        vg.add(list(range(len(obj.data.vertices))),1.0,"REPLACE")
    mod=obj.modifiers.new("GameRig","ARMATURE"); mod.object=rig
    obj.parent=rig; obj.matrix_parent_inverse=rig.matrix_world.inverted()





def garment_shell(name,h,material,profile,segments=72,tatter=0.0,phase=0.0,subdiv=1):
    vs=[]; fs=[]; rings=len(profile)
    hero=name.startswith(("BlueOuterSkirt","IvoryUnderSkirt","IvoryRagLayer"))
    for r,(zf,rxf,ryf,yoff) in enumerate(profile):
        for i in range(segments):
            a=2*math.pi*i/segments
            if hero:
                fold=.070*math.sin(a*7.0+phase+r*.34)+.025*math.sin(a*13.0+phase*.63+r*.15)
                gather=.016*math.sin(a*3.0+r*.55)
            else:
                fold=.024*math.sin(a*6.0+phase+r*.31)+.010*math.sin(a*11.0+phase*.7)
                gather=0.0
            wob=1.0 + fold
            x=(rxf+gather)*h*wob*math.cos(a)
            y=yoff*h + (ryf+.45*gather)*h*(1.0+.62*fold)*math.sin(a)
            z=zf*h
            if hero:
                z += .005*h*math.sin(a*5.0+r*.8)
            if r==0 and tatter:
                tear=.24+.42*abs(math.sin(a*3.2+phase))+.34*abs(math.sin(a*7.1+phase*.4))
                if i%17 in (0,1): tear*=1.45
                z -= tatter*h*min(1.45,tear)
            vs.append((x,y,z))
    for r in range(rings-1):
        for i in range(segments):
            j=(i+1)%segments
            a=r*segments+i; b=r*segments+j; c=(r+1)*segments+j; d=(r+1)*segments+i
            fs.append((a,b,c,d))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("ClothThickness","SOLIDIFY"); sol.thickness=.0022*h; sol.offset=0
    bev=o.modifiers.new("ClothEdgeSoft","BEVEL"); bev.width=.0010*h; bev.segments=2
    if subdiv:
        sub=o.modifiers.new("ClothSmooth","SUBSURF"); sub.subdivision_type="CATMULL_CLARK"; sub.levels=subdiv; sub.render_levels=subdiv
    return o

def drape_open(name,h,material,profile,segments=64,theta_max=2.42,tatter=0.0,phase=0.0,subdiv=1):
    vs=[]; fs=[]; rings=len(profile)
    clothy=("Veil" in name or "Cape" in name or "Drape" in name or "Wimple" in name)
    for r,(zf,rxf,ryf) in enumerate(profile):
        for i in range(segments):
            t=-theta_max + (2.0*theta_max)*i/(segments-1)
            fold=(.0060*math.sin(t*4.0+phase+r*.37)+.0028*math.sin(t*8.0+r*.71)) if clothy else 0.0
            x=(rxf+fold)*h*math.sin(t)
            y=(ryf+.55*fold)*h*math.cos(t)
            z=zf*h + (.0030*h*math.sin(t*3.0+r*.8) if clothy else 0)
            if r==rings-1 and tatter:
                tear=.26+.46*abs(math.sin(i*.34+phase))+.20*abs(math.sin(i*.79+phase*.5))
                if i%19 in (0,1): tear*=1.35
                z -= tatter*h*min(1.35,tear)
            vs.append((x,y,z))
    for r in range(rings-1):
        for i in range(segments-1):
            a=r*segments+i; b=a+1; c=(r+1)*segments+i+1; d=(r+1)*segments+i
            fs.append((a,b,c,d))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("DrapeThickness","SOLIDIFY"); sol.thickness=.0018*h; sol.offset=0
    bev=o.modifiers.new("DrapeEdgeSoft","BEVEL"); bev.width=.0010*h; bev.segments=2
    if subdiv:
        sub=o.modifiers.new("DrapeSmooth","SUBSURF"); sub.subdivision_type="CATMULL_CLARK"; sub.levels=subdiv; sub.render_levels=subdiv
    return o

def curved_panel(name,h,material,z0,z1,w0,w1,yfront=-.125,rows=7,cols=18,ragged=False):
    vs=[]; fs=[]
    for r in range(rows):
        u=r/(rows-1)
        z=(z0+(z1-z0)*u)*h
        width=(w0+(w1-w0)*u)*h
        for c in range(cols):
            t=c/(cols-1)
            x=(-width+2*width*t)
            bulge=(1.0-(x/max(width,1e-6))**2)
            y=(yfront-.010*bulge)*h
            zz=z
            if ragged and r==0:
                zz -= .012*h*abs(math.sin(c*1.37+.4))
            vs.append((x,y,zz))
    for r in range(rows-1):
        for c in range(cols-1):
            a=r*cols+c; b=a+1; cc=(r+1)*cols+c+1; d=(r+1)*cols+c
            fs.append((a,b,cc,d))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("PanelThickness","SOLIDIFY"); sol.thickness=.0028*h; sol.offset=0
    sub=o.modifiers.new("PanelSmooth","SUBSURF"); sub.subdivision_type="SIMPLE"; sub.levels=1; sub.render_levels=1
    return o

def bone_points(rig,bone_name):
    b=rig.data.bones.get(bone_name)
    if not b: return None,None
    return rig.matrix_world @ b.head_local, rig.matrix_world @ b.tail_local

def bone_sleeves(rig,h,main_mat,cuff_mat):
    out=[]
    for side,label in (("l","L"),("r","R")):
        uh,ut=bone_points(rig,"upperarm_"+side)
        lh,lt=bone_points(rig,"lowerarm_"+side)
        if uh is None or lh is None: continue
        a=cone_between("SleeveUpper_"+label,uh,ut,.040*h,.034*h,main_mat,40)
        b=cone_between("SleeveLower_"+label,lh,lt,.035*h,.028*h,main_mat,40)
        if a: out.append(a)
        if b: out.append(b)
        axis=(lt-lh).normalized()
        cuff_end=lt+axis*.050*h
        c=cone_between("SleeveCuff_"+label,lt,cuff_end,.032*h,.041*h,cuff_mat,36)
        if c: out.append(c)
    return out

def hair_lock(name,h,material,x0,z0,z1,y=-.076,width=.018,wave=.010,phase=0.0):
    rows=8; vs=[]; fs=[]
    for r in range(rows):
        u=r/(rows-1)
        z=(z0+(z1-z0)*u)*h
        x=(x0 + wave*math.sin(phase+u*3.2))*h
        yy=(y+.006*math.sin(phase*1.3+u*2.7))*h
        wid=width*h*(1.0-.45*u)
        vs.append((x-wid,yy,z)); vs.append((x+wid,yy,z))
    for r in range(rows-1):
        a=r*2; fs.append((a,a+1,a+3,a+2))
    mesh=bpy.data.meshes.new(name+"Mesh"); mesh.from_pydata(vs,[],fs); mesh.update()
    o=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("HairThickness","SOLIDIFY"); sol.thickness=.0018*h; sol.offset=0
    bev=o.modifiers.new("HairEdgeSoft","BEVEL"); bev.width=.0008*h; bev.segments=2
    return o





def llorona_hair_mesh(h,mats):
    m=mats["wet_black"]; out=[]
    # Dense rear mass plus many fine curved wet strands; no flat barcode curtains.
    out.append(drape_open("HairDrape",h,m,[
        (.995,.067,.061),(.965,.074,.067),(.925,.083,.074),(.875,.095,.082),
        (.810,.109,.091),(.730,.126,.101),(.640,.143,.111),(.535,.158,.120),(.430,.166,.126)
    ],segments=96,theta_max=2.78,tatter=.085,phase=.7,subdiv=1))
    for i in range(58):
        side=-1 if i%2==0 else 1
        band=(i%29)/28.0
        x=side*(.022+.070*band)*h
        z0=(.988-.0025*(i%7))*h
        z1=(.39+.20*((i*11)%17)/16.0)*h
        y=(-.082-.008*math.sin(i*.63))*h
        wave=.010*h*math.sin(i*.91)
        pts=[(x,y,z0),(x*1.02+wave,y-.006*h,z0-.16*h),(x*1.08-wave,y+.004*h,z0-.36*h),(x*1.14+wave*.5,y+.012*h,z1)]
        out.append(curve_chain("HairStrand_%02d"%i,pts,m,.00125*h))
    return out













def sculpt_priority_face(body,h,style):
    fy=face_front_y(body,h)
    strength=1.52 if style=="sister_of_ash" else (1.05 if style=="la_llorona" else 1.10)
    for v in body.data.vertices:
        z=v.co.z/h; x=v.co.x/h; y=v.co.y; ax=abs(x)
        if z<.79: continue
        # narrow jaw/chin and temples for a starved corpse silhouette
        if .800<z<.870: v.co.x*=1.0-.205*strength
        elif .930<z<.985: v.co.x*=1.0-.075*strength
        if y < fy + .068*h:
            if .888<z<.937 and .006<ax<.053: v.co.y += .0128*h*strength
            if .844<z<.902 and .020<ax<.078: v.co.y += .0120*h*strength
            if .871<z<.926 and ax<.028: v.co.x*=.85
            if .828<z<.868 and ax<.042: v.co.y += .0055*h*strength
            if .800<z<.840 and ax<.055:
                v.co.y -= .0018*h
                v.co.x*=.970
            if x<0 and .848<z<.916: v.co.z -= .0016*h
    body.data.update()

def force_priority_eyes(parts,style):
    eye=parts.get("eyes")
    if not eye or eye.type!="MESH": return
    if style=="sister_of_ash":
        pale=mat("M_sister_of_ash_MilkyEye","#D6D3CB",.28,0,noise=False)
        dull=mat("M_sister_of_ash_DeadEye","#7C8083",.34,0,noise=False)
        eye.data.materials.clear(); eye.data.materials.append(pale); eye.data.materials.append(dull)
        for p in eye.data.polygons:
            p.use_smooth=True
            p.material_index=1 if p.center.x<0 else 0
        return
    if style=="la_llorona": col="#6F6B68"; em=None
    elif style=="stained_shade": col="#CBDDE6"; em="#789DB2"
    else: col="#D2D0C9"; em=None
    m=mat("M_"+style+"_MilkyEyes",col,.24,0,emission=em,noise=False); assign(eye,m)

def spectral_cloth_ribbons(h,mats):
    out=[]; ivory=mats["spectral_ivory"]
    for side in (-1,1):
        for j in range(5):
            x0=side*(.115+.012*j)
            z0=.74-.040*j
            z1=.28-.030*(j%2)
            o=hair_lock("SpectralCloth_%s_%02d"%("L" if side<0 else "R",j),h,ivory,x0,z0,z1,-.060,.014,.010,phase=.9*j)
            out.append(o)
    return out









def sister_boots(h,mats):
    return []




def sister_skin_shader(body,h,style):
    if style!="sister_of_ash": return
    corpse=hexrgb("#A79D98")
    for m in body.data.materials:
        if not m: continue
        m.use_nodes=True; nodes=m.node_tree.nodes; links=m.node_tree.links
        bsdf=nodes.get("Principled BSDF")
        if not bsdf: continue
        base=bsdf.inputs.get("Base Color")
        if not base: continue
        original=None
        if base.is_linked and base.links:
            lk=base.links[0]; original=lk.from_socket; links.remove(lk)
        sat=nodes.new("ShaderNodeHueSaturation"); sat.inputs["Saturation"].default_value=.26; sat.inputs["Value"].default_value=.90
        if original: links.new(original,sat.inputs["Color"])
        else: sat.inputs["Color"].default_value=(.62,.54,.52,1)
        tint=nodes.new("ShaderNodeMixRGB"); tint.blend_type="MIX"; tint.inputs[0].default_value=.70
        links.new(sat.outputs["Color"],tint.inputs[1]); tint.inputs[2].default_value=(*corpse,1)
        tex=nodes.new("ShaderNodeTexCoord")
        noise=nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value=5.0; noise.inputs["Detail"].default_value=5.0; noise.inputs["Roughness"].default_value=.75
        links.new(tex.outputs["Generated"],noise.inputs["Vector"])
        mott=nodes.new("ShaderNodeValToRGB")
        mott.color_ramp.elements[0].color=(.40,.33,.36,1); mott.color_ramp.elements[1].color=(.82,.76,.73,1)
        links.new(noise.outputs["Fac"],mott.inputs["Fac"])
        skinmix=nodes.new("ShaderNodeMixRGB"); skinmix.blend_type="MULTIPLY"; skinmix.inputs[0].default_value=.16
        links.new(tint.outputs["Color"],skinmix.inputs[1]); links.new(mott.outputs["Color"],skinmix.inputs[2])
        links.new(skinmix.outputs["Color"],base)
        if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value=.82
        if "Subsurface Weight" in bsdf.inputs: bsdf.inputs["Subsurface Weight"].default_value=.012
        elif "Subsurface" in bsdf.inputs: bsdf.inputs["Subsurface"].default_value=.012
        micro=nodes.new("ShaderNodeTexNoise"); micro.inputs["Scale"].default_value=190.0; micro.inputs["Detail"].default_value=3.0; micro.inputs["Roughness"].default_value=.68
        links.new(tex.outputs["Generated"],micro.inputs["Vector"])
        bump=nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value=.075; bump.inputs["Distance"].default_value=.00055
        links.new(micro.outputs["Fac"],bump.inputs["Height"]); links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])


def nun_outfit(h,mats,stained=False):
    ivory=mats["spectral_ivory"] if stained else mats["dirty_ivory"]
    blue=mats["ash_blue"]; rope=mats["rope"]; metal=mats.get("oxidized_metal",mats.get("old_wood"))
    out=[]
    # Raise the under-habit off the floor so its torn ankle hem and closed shoes remain visible.
    under=garment_shell("IvoryUnderSkirt",h,ivory,[
        (.050,.125,.085,0),(.105,.135,.091,0),(.180,.138,.093,0),(.270,.135,.092,0),
        (.370,.128,.089,0),(.475,.117,.084,0),(.580,.107,.079,0),(.700,.098,.074,0)
    ],124,.085,.40,1)
    out.append(under)
    punch_cloth_holes(under,h,[(-.055,.165,.019,.030,True),(.070,.240,.017,.027,True),(-.080,.315,.015,.027,False)])
    outer=garment_shell("BlueOuterSkirt",h,blue,[
        (.305,.114,.083,-.002),(.350,.121,.087,-.002),(.410,.124,.089,-.003),
        (.475,.121,.087,-.003),(.540,.114,.083,-.004),(.605,.106,.079,-.004),
        (.665,.099,.074,-.004),(.720,.095,.071,-.004)
    ],124,.125,1.55,1)
    out.append(outer)
    punch_cloth_holes(outer,h,[(-.070,.420,.017,.028,True),(.060,.495,.015,.023,True),(.090,.365,.014,.024,False)])
    out.extend(sister_layered_hem(h,mats))
    # Broad dirty-ivory shoulder mantle like the reference, with layered torn edge.
    out.append(drape_open("ShoulderCape",h,ivory,[
        (.838,.086,.070),(.814,.099,.078),(.788,.113,.087),(.762,.128,.097),
        (.736,.143,.107),(.710,.158,.117),(.690,.170,.124)
    ],112,2.46,.080,1.55,1))
    out.append(drape_open("ShoulderCapeLower",h,ivory,[
        (.805,.091,.072),(.782,.105,.080),(.758,.120,.089),(.734,.135,.099),(.712,.150,.108)
    ],108,2.38,.070,2.20,1))
    out.append(drape_open("OuterVeil",h,blue,[
        (.965,.048,.044),(.940,.053,.048),(.910,.059,.052),(.878,.066,.057),
        (.844,.075,.064),(.812,.085,.071),(.782,.096,.079),(.754,.107,.086),(.730,.118,.093)
    ],116,2.52,.100,.92,1))
    out.extend(rope_belt_with_tails(h,rope,metal,"RopeBelt"))
    return out

def llorona_outfit(h,mats):
    ivory=mats["spectral_ivory"]; linen=mats.get("waterlogged_linen",ivory); rope=mats["rope"]
    metal=mats.get("tarnished_silver") or mats.get("oxidized_metal"); out=[]
    out.append(garment_shell("LloronaUnderSkirt",h,linen,[
        (.012,.168,.111,0),(.090,.179,.117,0),(.205,.181,.118,0),(.335,.174,.114,0),(.455,.153,.105,0),(.555,.132,.094,0),(.620,.121,.087,0)
    ],92,.085,.20,1))
    out.append(garment_shell("LloronaOuterSkirt",h,ivory,[
        (.060,.182,.120,-.004),(.160,.184,.121,-.004),(.280,.178,.117,-.004),(.405,.164,.110,-.005),(.520,.143,.101,-.005),(.600,.125,.090,-.005),(.645,.120,.087,-.005)
    ],92,.100,1.10,1))
    out.append(drape_open("LloronaLaceDrape",h,linen,[
        (.842,.082,.067),(.818,.092,.073),(.792,.104,.080),(.765,.117,.088),(.740,.130,.096)
    ],80,2.62,.045,1.3,1))
    out.extend(rope_belt_with_tails(h,rope,metal,"RosaryBelt"))
    mud=mats.get("mud_silt")
    if mud: out.append(garment_shell("MudHem",h,mud,[(.012,.184,.121,0),(.055,.185,.122,0),(.105,.183,.121,0),(.160,.177,.117,0),(.220,.168,.112,0)],84,.060,.9,1))
    return out


def stained_halo(h,mats):
    metal=mats["oxidized_metal"]; out=[]
    y=.118*h; cz=.905*h; ro=.155*h; ri=.046*h
    out.append(torus("StainedHalo",(0,y,cz),ro,.0060*h,metal,rot=(math.radians(90),0,0)))
    cols=[mats["glass_blue"],mats["glass_cyan"],mats["glass_magenta"],mats["amber"]]
    seg=14
    for i in range(seg):
        a0=2*math.pi*i/seg; a1=2*math.pi*(i+1)/seg
        mid=(a0+a1)*.5
        outer=ro*(.91+.055*math.sin(i*2.31))
        vs=[(ri*math.cos(a0),y,cz+ri*math.sin(a0)),
            (outer*math.cos(a0),y,cz+outer*math.sin(a0)),
            (outer*math.cos(a1),y,cz+outer*math.sin(a1)),
            (ri*math.cos(a1),y,cz+ri*math.sin(a1))]
        mesh=bpy.data.meshes.new(f"HaloPane{i:02}Mesh"); mesh.from_pydata(vs,[],[(0,1,2,3)]); mesh.update()
        o=bpy.data.objects.new(f"HaloPane{i:02}",mesh); bpy.context.collection.objects.link(o); assign(o,cols[i%4]); out.append(o)
    return out


def parent_to_bone(obj,rig,bone):
    if bone not in rig.data.bones: return
    mw=obj.matrix_world.copy()
    obj.parent=rig; obj.parent_type="BONE"; obj.parent_bone=bone
    obj.matrix_world=mw

def bind_mesh_vertical(obj,rig,h):
    if obj.type!="MESH": return
    for g in ("pelvis","spine_01","spine_02","spine_03"):
        if g not in obj.vertex_groups: obj.vertex_groups.new(name=g)
    for v in obj.data.vertices:
        z=(obj.matrix_world @ v.co).z/max(h,1e-6)
        if z < .46: bone="pelvis"
        elif z < .59: bone="spine_01"
        elif z < .72: bone="spine_02"
        else: bone="spine_03"
        obj.vertex_groups[bone].add([v.index],1.0,"REPLACE")
    mod=obj.modifiers.new("GameRig","ARMATURE"); mod.object=rig
    obj.parent=rig

def bind_sleeve(obj,rig,h,left=True):
    if obj.type!="MESH": return
    a="upperarm_l" if left else "upperarm_r"; b="lowerarm_l" if left else "lowerarm_r"
    ga=obj.vertex_groups.get(a) or obj.vertex_groups.new(name=a)
    gb=obj.vertex_groups.get(b) or obj.vertex_groups.new(name=b)
    for v in obj.data.vertices:
        z=(obj.matrix_world @ v.co).z/max(h,1e-6)
        t=max(0,min(1,(.765-z)/.22))
        ga.add([v.index],1-t,"REPLACE"); gb.add([v.index],t,"REPLACE")
    mod=obj.modifiers.new("GameRig","ARMATURE"); mod.object=rig
    obj.parent=rig

def bind_generated_to_rig(body,rig,h):
    for o in list(bpy.context.scene.objects):
        if o==body or o==rig: continue
        n=o.name
        if o.type=="CURVE":
            if n.startswith(("SisterMouthSlit","SisterScar")): parent_to_bone(o,rig,"head")
            elif n.startswith("Hair"): parent_to_bone(o,rig,"head")
            elif n.startswith(("RopeBelt","RosaryBelt")): parent_to_bone(o,rig,"pelvis")
            continue
        if o.type!="MESH": continue
        if n.startswith("Eye") or n.startswith(("HairLock","HairRibbon","HairFace")) or n=="HairDrape" or n in ("OuterVeil","InnerWimple","NunBackVeil","SisterWimpleFrame","StainedHalo","NunCoif","NunHoodCrown","NunForeheadBand","NunInnerCoif","NunOuterHood","NunWimpleBrow","NunWimpleSides","NunWimpleNeck","ShadeHood","HairCap") or n.startswith(("HaloGlass","HaloPane","SocketRing")):
            rigid_bind_mesh(o,rig,"head"); continue
        if n.startswith(("SleeveUpper_L","SleeveLower_L","SleeveCuff_L")):
            parent_to_bone(o,rig,"upperarm_l" if "Upper" in n else "lowerarm_l"); continue
        if n.startswith("Sleeve_L") or n.startswith("CuffRag_L"):
            bind_sleeve(o,rig,h,True); continue
        if n.startswith(("SleeveUpper_R","SleeveLower_R","SleeveCuff_R")):
            parent_to_bone(o,rig,"upperarm_r" if "Upper" in n else "lowerarm_r"); continue
        if n.startswith("Sleeve_R") or n.startswith("CuffRag_R"):
            bind_sleeve(o,rig,h,False); continue
        if n.startswith(("WimpleForehead","WimpleSide","EyeShadow","SocketShade","MouthDecay","MouthCavity","SisterMouthCavity","SisterMouthSlit","SisterTeethHint","TeethHint","CheekDecay","TearTrail")):
            rigid_bind_mesh(o,rig,"head"); continue
        if n.startswith(("NunCross","RosaryCross")):
            parent_to_bone(o,rig,"spine_02"); continue
        if n.startswith(("RopeBelt","RosaryBelt")):
            parent_to_bone(o,rig,"pelvis"); continue
        if n.startswith(("SisterShoe_L","SisterAnkle_L","SisterSole_L","SisterToeCap_L")):
            parent_to_bone(o,rig,"foot_l"); continue
        if n.startswith(("SisterShoe_R","SisterAnkle_R","SisterSole_R","SisterToeCap_R")):
            parent_to_bone(o,rig,"foot_r"); continue
        if n.startswith(("NunSleeve","NunFootSock")):
            continue
        if n.startswith(("Dress","Llorona","Ivory","Blue","RepairPatch","OuterRobe","UnderRobe","Stole","ShoulderCape","WimpleBib","WimpleChestBib","IvoryChestBib","SpectralCloth","GlassShard","MudHem")):
            bind_mesh_vertical(o,rig,h)

def curve_chain(name,pts,material,bevel=.008):
    c=bpy.data.curves.new(name+"Curve","CURVE"); c.dimensions="3D"; c.bevel_depth=bevel; c.bevel_resolution=2
    sp=c.splines.new("BEZIER"); sp.bezier_points.add(len(pts)-1)
    for bp,p in zip(sp.bezier_points,pts):
        bp.co=p; bp.handle_left_type=bp.handle_right_type="AUTO"
    o=bpy.data.objects.new(name,c); bpy.context.collection.objects.link(o)
    o.data.materials.append(material)
    return o

def hair_strands(zhead,h,material,count=26,length=.62):
    objs=[]
    for i in range(count):
        a=2*math.pi*i/count
        x=.075*math.cos(a); y=.07*math.sin(a)
        pts=[(x,y,zhead),(x*1.2,y+.015,zhead-.18*h),(x*1.7,y+.04,zhead-length*h)]
        objs.append(curve_chain(f"Hair_{i:02}",pts,material,.0045))
    return objs

def add_eyes(z,front_y,eye_mat):
    return [uv_sphere("Eye_L",(-.032,front_y,z),(.014,.010,.014),eye_mat),
            uv_sphere("Eye_R",(.032,front_y,z),(.014,.010,.014),eye_mat)]


def face_front_y(body,h):
    ys=[]
    for v in body.data.vertices:
        z=v.co.z/max(h,1e-6)
        if .84 < z < .95:
            ys.append(v.co.y)
    return min(ys) if ys else -.055*h



def add_face_details(body,h,mats,style):
    fy=face_front_y(body,h)
    bruise=mats.get("bruise") or mats.get("bruise_blue") or mats.get("water_bruise") or mats.get("corpse_skin")
    dark=mats.get("soot") or mats.get("wet_black") or bruise
    # Small under-eye and mouth decals; deliberately narrower than the facial features.
    for side in (-1,1):
        p=curved_panel("EyeShadow_"+("L" if side<0 else "R"),h,bruise,.895,.915,.011,.009,fy/h-.010,3,6,False)
        p.location.x=side*.020*h
    curved_panel("MouthDecay",h,dark,.844,.856,.016,.013,fy/h-.011,3,8,False)
    p=curved_panel("CheekDecay",h,bruise,.862,.882,.012,.010,fy/h-.008,3,6,False)
    p.location.x=-.038*h
    return fy

def llorona_hair(h,mats):
    m=mats["wet_black"]; out=[]
    out.append(open_veil("HairCap",h,m,False))
    for i in range(34):
        side=-1 if i%2==0 else 1
        band=(i%17)/16
        x=side*(.028+.040*band)*h
        front=(i%5 in (0,1))
        y=(-.060 if front else .045)*h + .010*h*math.sin(i*.9)
        z0=(.955-.018*(i%4))*h
        length=(.40+.16*((i*7)%11)/10)*h
        pts=[(x,y,z0),(x*1.05,y+.010*h,z0-.13*h),(x*1.25,y+.020*h,z0-length)]
        out.append(curve_chain("HairClump_%02d"%i,pts,m,.0038*h))
    return out


def llorona_hair_ribbons(h,mats):
    m=mats["wet_black"]; out=[]
    # Back curtain.
    out.append(front_panel("HairBack",h,m,.54,.965,.105,.075,.060,True))
    # Front-side wet locks, intentionally asymmetric.
    for side,label in ((-1,"L"),(1,"R")):
        for j in range(5):
            x0=side*(.038+.010*j)*h
            y=-.074*h-.002*j*h
            ztop=(.955-.014*j)*h
            zbot=(.56+.025*j)*h
            pts=[
                (x0-.018*h,y,zbot),
                (x0+.018*h,y,zbot-.018*h*(j%2)),
                (x0+.013*h,y,ztop),
                (x0-.013*h,y,ztop)
            ]
            mesh=bpy.data.meshes.new(f"HairRibbon_{label}_{j}Mesh")
            mesh.from_pydata(pts,[],[(0,1,2,3)]); mesh.update()
            o=bpy.data.objects.new(f"HairRibbon_{label}_{j}",mesh); bpy.context.collection.objects.link(o); assign(o,m)
            sol=o.modifiers.new("HairThickness","SOLIDIFY"); sol.thickness=.0025; sol.offset=0
            out.append(o)
    return out

def llorona_rosary(h,mats):
    metal=mats.get("tarnished_silver") or mats.get("oxidized_metal")
    rope=mats.get("rope") or metal
    out=[]
    pts=[(-.015*h,-.136*h,.655*h),(.018*h,-.139*h,.585*h),(-.005*h,-.141*h,.515*h),(0,-.143*h,.455*h)]
    out.append(curve_chain("RosaryChain",pts,rope,.004*h))
    out.extend(cross_prop("RosaryCross",(0,-.145*h,.430*h),.032*h,metal))
    return out

def add_damage_sockets(h):
    coll=bpy.data.collections.get("DAMAGE_SOCKETS") or bpy.data.collections.new("DAMAGE_SOCKETS")
    if coll.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(coll)
    pts={"HEAD":(0,0,.88*h),"WAIST":(0,0,.50*h),
         "L_SHOULDER":(-.20*h,0,.72*h),"R_SHOULDER":(.20*h,0,.72*h),
         "L_ELBOW":(-.31*h,0,.62*h),"R_ELBOW":(.31*h,0,.62*h),
         "L_HIP":(-.08*h,0,.48*h),"R_HIP":(.08*h,0,.48*h),
         "L_KNEE":(-.08*h,0,.26*h),"R_KNEE":(.08*h,0,.26*h)}
    for n,p in pts.items():
        e=bpy.data.objects.new("SOCKET_"+n,None); e.empty_display_type="SPHERE"; e.empty_display_size=.025*h; e.location=p
        coll.objects.link(e)

def robe_for_style(style,h,w,d,mats):
    if style=="sister_of_ash":
        return nun_outfit(h,mats,False)
    if style=="stained_shade":
        return nun_outfit(h,mats,True)
    if style=="la_llorona":
        return llorona_outfit(h,mats)
    objs=[]
    ivory=mats.get("dirty_ivory") or mats.get("spectral_ivory") or next(iter(mats.values()))
    blue=mats.get("ash_blue") or mats.get("drowned_blue") or ivory
    burg=mats.get("burgundy") or mats.get("choir_red") or blue
    soot=mats.get("soot") or mats.get("gravecoat") or blue
    if style in ("lost_child","waterbound_child"):
        outer=mats.get("spectral_ivory") or mats.get("drowned_ivory") or ivory
        objs.append(frustum("DressOuter",.08*h,.73*h,.30*w,.24*d,.18*w,.20*d,outer,56,.035*h,.4))
        objs.append(frustum("DressUpper",.58*h,.86*h,.19*w,.18*d,.18*w,.17*d,outer,48,.012*h,.9))
    elif style=="grave_sexton":
        objs.append(frustum("UnderRobe",.08*h,.70*h,.29*w,.24*d,.19*w,.18*d,ivory,48,.025*h,.2))
        objs.append(frustum("GraveCoat",.12*h,.86*h,.31*w,.27*d,.21*w,.20*d,soot,48,.035*h,1.2))
    elif style=="censer_brute":
        objs.append(frustum("HeavyUnder",.05*h,.72*h,.31*w,.27*d,.24*w,.22*d,ivory,48,.035*h,.5))
        objs.append(frustum("HeavyOuter",.10*h,.88*h,.35*w,.31*d,.26*w,.25*d,soot,48,.045*h,1.5))
        objs.append(frustum("BurgundyStole",.18*h,.84*h,.10*w,.255*d,.08*w,.22*d,burg,32,.025*h,.8))
    elif style=="reliquary_horror":
        objs.append(frustum("BossUnder",.04*h,.74*h,.34*w,.30*d,.25*w,.23*d,ivory,56,.045*h,.4))
        objs.append(frustum("BossOuter",.08*h,.90*h,.38*w,.34*d,.29*w,.27*d,soot,56,.055*h,1.5))
        objs.append(frustum("BossBurgundy",.10*h,.86*h,.16*w,.30*d,.11*w,.24*d,burg,40,.035*h,.2))
    else:
        objs.append(frustum("UnderRobe",.06*h,.70*h,.29*w,.24*d,.18*w,.18*d,ivory,48,.030*h,.3))
        objs.append(frustum("OuterRobe",.12*h,.84*h,.30*w,.26*d,.20*w,.20*d,blue if style in ("bell_ringer",) else burg,48,.040*h,.9))
        if style in ("choir_wretch","penitent_deacon"):
            objs.append(frustum("Stole",.16*h,.84*h,.09*w,.265*d,.07*w,.21*d,burg,28,.025*h,.5))
    return objs

def veil(style,h,w,d,material):
    # rear/side veil sheet, face stays visible on -Y.
    ztop=.95*h; zbot=.58*h; y=.18*d
    vs=[(-.24*w,y,ztop),(.24*w,y,ztop),(.36*w,y*1.05,zbot),(-.36*w,y*1.05,zbot)]
    mesh=bpy.data.meshes.new("VeilMesh"); mesh.from_pydata(vs,[],[(0,1,2,3)]); mesh.update()
    o=bpy.data.objects.new("Veil",mesh); bpy.context.collection.objects.link(o); assign(o,material)
    sol=o.modifiers.new("VeilThickness","SOLIDIFY"); sol.thickness=.004
    return o

def bell_prop(h,material,rope_mat):
    z=.43*h
    chain=curve_chain("BellRope",[(-.10,0,.66*h),(-.13,-.02,.53*h),(-.13,-.03,z+.05)],rope_mat,.008)
    bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.065*h,radius2=.035*h,depth=.09*h,location=(-.13,-.03,z))
    b=bpy.context.object; b.name="Bell"; assign(b,material)
    return [chain,b]

def shovel_prop(h,metal,wood):
    handle=cyl("ShovelHandle",(-.28,0,.38*h),.012*h,.72*h,wood,16); handle.rotation_euler=(0,math.radians(-8),0)
    blade=cube("ShovelBlade",(-.31,0,.08*h),(.055*h,.012*h,.09*h),metal,.012*h)
    return [handle,blade]

def lantern_prop(h,metal,wax):
    x=.20; z=.48*h
    frame=cube("Lantern",(x,-.03,z),(.055,.055,.09),metal,.008)
    glow=uv_sphere("LanternGlow",(x,-.03,z),(.025,.025,.04),wax)
    return [frame,glow]

def censer_prop(h,metal,rope):
    x=-.22*h; z=.30*h
    chain=curve_chain("CenserChain",[(-.14*h,0,.72*h),(-.18*h,-.01,.52*h),(x,-.02,z+.10*h)],metal,.010*h)
    bowl=uv_sphere("Censer",(x,-.02,z),(.09*h,.09*h,.11*h),metal)
    ring=torus("CenserRing",(x,-.02,z+.05*h),.08*h,.009*h,metal)
    return [chain,bowl,ring]

def shrine_back(h,wood,metal,wax):
    objs=[]
    z=.72*h
    objs.append(cube("ShrineSpine",(0,.14*h,z),(.04*h,.025*h,.26*h),wood,.01*h))
    for i,x in enumerate((-.16*h,0,.16*h)):
        objs += cross_prop(f"ShrineCross{i}",(x,.14*h,.82*h+(i%2)*.08*h),.10*h,metal)
        candle=cyl(f"Candle{i}",(x,.12*h,.98*h+(i%2)*.05*h),.012*h,.06*h,wax,16); objs.append(candle)
    return objs



def glass_shards(h,materials):
    return stained_cloth_accents(h,materials)

def setup_skin(body,mats,style):
    tint_hex="#655E5C" if style=="sister_of_ash" else ("#85898D" if style=="la_llorona" else ("#81868E" if style=="stained_shade" else "#8B837C"))
    tint=hexrgb(tint_hex)
    for m in body.data.materials:
        if not m: continue
        m.use_nodes=True; nodes=m.node_tree.nodes; links=m.node_tree.links
        bsdf=nodes.get("Principled BSDF")
        if not bsdf: continue
        base=bsdf.inputs.get("Base Color")
        if base:
            src=None
            if base.is_linked and base.links:
                old=base.links[0]; src=old.from_socket; links.remove(old)
            mix=nodes.new("ShaderNodeMixRGB"); mix.blend_type="MULTIPLY"; mix.inputs[0].default_value=.72
            if src: links.new(src,mix.inputs[1])
            else: mix.inputs[1].default_value=(.62,.56,.52,1)
            mix.inputs[2].default_value=(*tint,1); links.new(mix.outputs["Color"],base)
        noise=nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value=5.2; noise.inputs["Detail"].default_value=4.0; noise.inputs["Roughness"].default_value=.72
        bump=nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value=.16; bump.inputs["Distance"].default_value=.004
        links.new(noise.outputs["Fac"],bump.inputs["Height"]); links.new(bump.outputs["Normal"],bsdf.inputs["Normal"])
        if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value=.76
        if "Specular IOR Level" in bsdf.inputs: bsdf.inputs["Specular IOR Level"].default_value=.18

def tint_asset(obj,hex_color,rough=.55,emission=None):
    if not obj or obj.type!="MESH": return
    tint=hexrgb(hex_color)
    for m in obj.data.materials:
        if not m: continue
        m.use_nodes=True
        bsdf=m.node_tree.nodes.get("Principled BSDF")
        if not bsdf: continue
        base=bsdf.inputs.get("Base Color")
        if base:
            if base.is_linked and base.links:
                old=base.links[0]; src=old.from_socket; m.node_tree.links.remove(old)
                mix=m.node_tree.nodes.new("ShaderNodeMixRGB"); mix.blend_type="MULTIPLY"; mix.inputs[0].default_value=.72
                m.node_tree.links.new(src,mix.inputs[1]); mix.inputs[2].default_value=(*tint,1)
                m.node_tree.links.new(mix.outputs["Color"],base)
            else: base.default_value=(*tint,1)
        if "Roughness" in bsdf.inputs: bsdf.inputs["Roughness"].default_value=rough
        if emission:
            ec=hexrgb(emission)
            if "Emission Color" in bsdf.inputs: bsdf.inputs["Emission Color"].default_value=(*ec,1)
            if "Emission Strength" in bsdf.inputs: bsdf.inputs["Emission Strength"].default_value=.45

def equip_priority_parts(body,style,assets_root,HumanService):
    made={}
    eye_path=find_asset(assets_root,"low-poly.mhclo")
    print("EYE_ASSET",eye_path)
    if eye_path:
        try:
            made["eyes"]=HumanService.add_mhclo_asset(eye_path,body,asset_type="Eyes",material_type="PROCEDURAL_EYES",subdiv_levels=1)
            tint_asset(made["eyes"],"#C8CAC5",.24,"#A9C3CC" if style=="stained_shade" else None)
        except Exception as exc: print("eye asset warning",repr(exc))
    teeth_path=find_asset(assets_root,"teeth_base.mhclo")
    print("TEETH_ASSET",teeth_path)
    if teeth_path:
        try:
            made["teeth"]=HumanService.add_mhclo_asset(teeth_path,body,asset_type="Teeth",material_type="GAMEENGINE",subdiv_levels=0)
            tint_asset(made["teeth"],"#9B8E6D",.70)
        except Exception as exc: print("teeth asset warning",repr(exc))
    if style=="la_llorona":
        hair_path=find_asset(assets_root,"long01.mhclo")
        print("HAIR_ASSET",hair_path)
        if hair_path:
            try:
                made["hair"]=HumanService.add_mhclo_asset(hair_path,body,asset_type="Hair",material_type="GAMEENGINE",subdiv_levels=1)
                tint_asset(made["hair"],"#08090A",.28)
            except Exception as exc: print("hair asset warning",repr(exc))
    return made

def create_actions(rig,names):
    def bone(name):
        return rig.pose.bones.get(name)
    keys=["pelvis","spine_01","spine_02","spine_03","neck_01","head","upperarm_l","lowerarm_l","upperarm_r","lowerarm_r","thigh_l","calf_l","thigh_r","calf_r"]
    def set_rot(n,xyz,frame,action):
        pb=bone(n)
        if not pb:return
        pb.rotation_mode="XYZ"; pb.rotation_euler=tuple(math.radians(v) for v in xyz)
        pb.keyframe_insert("rotation_euler",frame=frame,group=n)
    def set_loc(n,xyz,frame):
        pb=bone(n)
        if not pb:return
        pb.location=xyz; pb.keyframe_insert("location",frame=frame,group=n)
    for nm in names:
        act=bpy.data.actions.new("ANIM_"+nm.upper()); rig.animation_data_create(); rig.animation_data.action=act
        for k in keys:
            pb=bone(k)
            if pb:
                pb.rotation_mode="XYZ"; pb.rotation_euler=(0,0,0); pb.location=(0,0,0)
                pb.keyframe_insert("rotation_euler",frame=1,group=k)
        if nm in ("walk","float"):
            for f,s in ((1,1),(12,-1),(24,1)):
                set_rot("thigh_l",(22*s,0,0),f,act); set_rot("thigh_r",(-22*s,0,0),f,act)
                set_rot("upperarm_l",(-15*s,0,8),f,act); set_rot("upperarm_r",(15*s,0,-8),f,act)
                set_rot("spine_03",(2,0,2*s),f,act)
        elif nm in ("run","panic_run","enraged"):
            for f,s in ((1,1),(8,-1),(16,1)):
                set_rot("thigh_l",(35*s,0,0),f,act); set_rot("thigh_r",(-35*s,0,0),f,act)
                set_rot("upperarm_l",(-32*s,0,8),f,act); set_rot("upperarm_r",(32*s,0,-8),f,act)
                set_rot("spine_03",(10,0,3*s),f,act)
        elif nm in ("attack","heavy_attack","chain_swing","slam","lunge"):
            set_rot("spine_03",(12,0,0),6,act); set_rot("upperarm_r",(-65,0,-20),8,act); set_rot("lowerarm_r",(-35,0,0),8,act)
            set_rot("upperarm_r",(35,0,-10),16,act); set_rot("spine_03",(-5,0,0),16,act)
        elif nm in ("scream","warning"):
            set_rot("head",(-18,0,0),8,act); set_rot("spine_03",(-10,0,0),8,act); set_rot("upperarm_l",(-30,0,35),8,act); set_rot("upperarm_r",(-30,0,-35),8,act)
        elif nm in ("weep","cry","sob"):
            set_rot("head",(22,0,0),10,act); set_rot("spine_03",(18,0,0),10,act); set_rot("upperarm_l",(-70,0,30),10,act); set_rot("upperarm_r",(-70,0,-30),10,act)
        elif nm in ("beckon","guide","gift","false_comfort","prayer"):
            set_rot("upperarm_r",(-55,0,-20),10,act); set_rot("lowerarm_r",(-20,0,0),10,act); set_rot("head",(0,0,-8),10,act)
        elif nm in ("hit",):
            set_rot("spine_03",(0,0,18),4,act); set_rot("head",(0,0,15),4,act); set_rot("spine_03",(0,0,0),10,act)
        elif nm in ("death","collapse"):
            set_rot("spine_03",(55,0,12),18,act); set_rot("head",(28,0,20),18,act); set_loc("pelvis",(0,0,-.35),30)
        elif nm in ("vanish","dissipate"):
            set_rot("spine_03",(0,0,12),15,act); set_rot("head",(-10,0,-15),15,act)
        else:
            for f,a in ((1,-2),(20,2),(40,-2)):
                set_rot("spine_03",(a,0,0),f,act); set_rot("head",(-a*.5,0,a*.3),f,act)
        act.use_fake_user=True
    rig.animation_data.action=None

def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        if o and o.name in bpy.context.view_layer.objects: o.select_set(True)
    if objs: bpy.context.view_layer.objects.active=objs[0]

def export_files(folder,objs):
    glb=folder/"model.glb"; fbx=folder/"model.fbx"
    select_only(objs)
    try:
        bpy.ops.export_scene.gltf(filepath=str(glb),export_format="GLB",use_selection=True,export_cameras=False,export_lights=False,export_animations=True,export_animation_mode="ACTIONS",export_apply=True)
    except Exception:
        bpy.ops.export_scene.gltf(filepath=str(glb),export_format="GLB",use_selection=True,export_cameras=False,export_lights=False,export_animations=True,export_apply=True)
    select_only(objs)
    bpy.ops.export_scene.fbx(filepath=str(fbx),use_selection=True,add_leaf_bones=False,bake_anim=True,bake_anim_use_all_actions=True,path_mode="AUTO")
    return glb,fbx

def look_at(o,target):
    o.rotation_euler=(Vector(target)-o.location).to_track_quat("-Z","Y").to_euler()



def pose_review(rig,style):
    def rot(n,xyz):
        pb=rig.pose.bones.get(n)
        if not pb: return
        pb.rotation_mode="XYZ"; pb.rotation_euler=tuple(math.radians(v) for v in xyz)
    if style=="la_llorona":
        rot("spine_03",(10,0,-4)); rot("head",(-8,0,8))
        rot("upperarm_l",(4,-4,48)); rot("lowerarm_l",(-14,0,8))
        rot("upperarm_r",(-22,6,-34)); rot("lowerarm_r",(-22,0,-8))
    elif style=="stained_shade":
        rot("spine_03",(6,0,3)); rot("head",(-10,0,-9))
        rot("upperarm_l",(0,0,50)); rot("lowerarm_l",(-10,0,5))
        rot("upperarm_r",(0,0,-46)); rot("lowerarm_r",(-12,0,-5))
    else:
        rot("spine_03",(12,0,4)); rot("neck_01",(-7,0,-4)); rot("head",(-10,0,9))
        rot("upperarm_l",(0,-4,52)); rot("lowerarm_l",(-15,0,6))
        rot("upperarm_r",(0,4,-46)); rot("lowerarm_r",(-18,0,-5))
    bpy.context.view_layer.update()



def preview(body,folder,style):
    scene=bpy.context.scene; scene.render.engine="BLENDER_EEVEE_NEXT"
    scene.render.resolution_x=720; scene.render.resolution_y=900; scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"; scene.world.color=(.004,.005,.007)
    try: scene.view_settings.exposure=-.65
    except Exception: pass
    lo,hi=local_bounds(body); h=hi.z-lo.z; target=(0,0,lo.z+h*.51); dist=max(3.25,h*2.0)
    bpy.ops.object.camera_add(location=(.18*dist,-dist,lo.z+h*.54))
    cam=bpy.context.object; cam.name="PreviewCamera"; cam.data.lens=56; scene.camera=cam
    for name,loc,en,size,col in [
      ("Key",(-.52*dist,-.64*dist,lo.z+h*.80),330,1.9,(.68,.74,.84)),
      ("Rim",(.55*dist,.26*dist,lo.z+h*.68),215,1.4,(.66,.18,.08)),
      ("Fill",(.04*dist,-.28*dist,lo.z+h*.36),110,1.55,(.36,.40,.46))]:
        bpy.ops.object.light_add(type="AREA",location=loc); L=bpy.context.object
        L.name=name; L.data.energy=en; L.data.size=size; L.data.color=col; look_at(L,target)
    bpy.ops.mesh.primitive_plane_add(size=max(8,h*4),location=(0,0,lo.z-.01)); g=bpy.context.object
    assign(g,mat("M_PreviewGround","#0A0C10",.88,0,noise=False))
    def render_at(path,location,tgt):
        cam.location=location; look_at(cam,tgt); scene.render.filepath=str(path); bpy.ops.render.render(write_still=True)
    render_at(folder/"preview.png",(.18*dist,-dist,lo.z+h*.54),target)
    render_at(folder/"preview_side.png",(dist*.95,-.08*dist,lo.z+h*.54),target)
    render_at(folder/"preview_back.png",(-.15*dist,dist,lo.z+h*.54),target)
    face_t=(0,-.005*h,lo.z+h*.895)
    render_at(folder/"preview_face.png",(.055*h,-.62*h,lo.z+h*.895),face_t)
    return folder/"preview.png"

def collect_character_objects():
    return [o for o in bpy.context.scene.objects if o.type in {"MESH","ARMATURE","CURVE","EMPTY"} and not o.name.startswith(("Camera","Key","Rim","Fill","PreviewGround"))]

def make_character(ch,assets_root,outroot,HumanService,ObjectService,TargetService):
    clean_scene()
    macro=TargetService.get_default_macro_info_dict()
    for k in ("gender","age","weight","muscle"):
        if k in macro: macro[k]=float(ch.get(k,macro[k]))
    body=HumanService.create_human(mask_helpers=True,detailed_helpers=False,extra_vertex_groups=True,feet_on_ground=True,scale=.1,macro_detail_dict=macro)
    body.name=ch["id"]+"_Body"
    exact_height(body,float(ch["height_m"]))
    # Apply a skin preset before our art-directed material.
    skin=(find_asset(assets_root,"young_caucasian_female.mhmat") if float(ch.get("gender",0.5))>=0.5 else find_asset(assets_root,"middleage_caucasian_male.mhmat")) or find_asset(assets_root,"young_caucasian_male.mhmat")
    if skin:
        try: HumanService.set_character_skin(skin,body,skin_type="GAMEENGINE")
        except Exception: pass
    rig=HumanService.add_builtin_rig(body,"game_engine")
    if rig is None: raise RuntimeError("MPFB game_engine rig creation failed")
    rig.name=ch["id"]+"_Rig"
    parts=equip_priority_parts(body,ch["style"],assets_root,HumanService)
    print("MPFB_PARTS",ch["id"],sorted(parts.keys()))
    # Bounds after rig fitting.
    lo,hi=local_bounds(body); h=hi.z-lo.z; w=hi.x-lo.x; d=hi.y-lo.y

    mats={}
    for key in set(ch["palette"]+["corpse_skin","dirty_ivory","ash_blue","burgundy","soot","rope","old_wood","oxidized_metal","wax","tarnished_brass","dark_iron","spectral_ivory","wet_black"]):
        if key not in PALETTE: continue
        rough=.72; metal=0; emission=None; alpha=1
        if key in ("wet_black",): rough=.20
        if key in ("tarnished_silver","tarnished_brass","oxidized_metal","oxidized_brass","iron","dark_iron"): rough=.48; metal=.70
        if key.startswith("glass_") or key=="amber": rough=.28; emission=PALETTE[key]
        if key=="spectral_ivory" and ch["style"]=="stained_shade": alpha=.72
        mats[key]=mat("M_"+ch["id"]+"_"+key,PALETTE[key],rough,metal,emission,alpha)
    setup_skin(body,mats,ch["style"])
    style=ch["style"]
    if style=="sister_of_ash":
        sister_cloth_distress(mats)
    sister_skin_shader(body,h,style)
    if style in ("sister_of_ash","la_llorona","stained_shade"):
        sculpt_priority_face(body,h,style)
        force_priority_eyes(parts,style)
    robe_objs=robe_for_style(style,h,w,d,mats)
    if style in ("sister_of_ash","la_llorona","stained_shade"):
        for _o in robe_objs or []:
            if _o and hasattr(_o,"scale"):
                _o.scale.x *= .82
                _o.scale.y *= .90
    if style in ("sister_of_ash","stained_shade","la_llorona"):
        fitted_priority_clothes(body,h,style,mats)
        priority_head_cover(body,h,style,mats)
    if style=="sister_of_ash":
        sister_mouth_pose(body,h)
        sister_mouth_slit(body,h,mats)
        # Paint any residual underlying foot polygons as leather so no bare toes can leak around the closed upper.
        sister_paint_footwear(body,h)
        sister_boot_pair(body,rig,h,mats)
    veilmat=mats.get("spectral_ivory") or mats.get("dirty_ivory")
    if style in ("lost_child","waterbound_child","bell_ringer","choir_wretch","penitent_deacon","censer_brute","reliquary_horror"):
        veil(style,h,w,d,veilmat)
    if style=="la_llorona":
        if parts.get("hair"):
            try: bpy.data.objects.remove(parts["hair"],do_unlink=True)
            except Exception: pass
            parts.pop("hair",None)
        print("LA_LLORONA_LONG_HAIR")
        llorona_hair_mesh(h,mats)
    elif style in ("lost_child","waterbound_child"):
        hair_strands(.97*h,h,mats["wet_black"],22,.28)
    if style=="bell_ringer": bell_prop(h,mats["tarnished_brass"],mats["rope"])
    if style=="grave_sexton": shovel_prop(h,mats.get("iron",mats["dark_iron"]),mats["old_wood"])
    if style=="penitent_deacon": lantern_prop(h,mats["oxidized_metal"],mats["wax"])
    if style=="censer_brute": censer_prop(h,mats.get("oxidized_brass",mats["tarnished_brass"]),mats["rope"])
    if style=="reliquary_horror":
        censer_prop(h,mats.get("oxidized_brass",mats["tarnished_brass"]),mats["rope"]); shrine_back(h,mats["old_wood"],mats["dark_iron"],mats["wax"])
    if style=="stained_shade":
        glass_shards(h,mats); stained_halo(h,mats); spectral_tatters(h,mats)
    if style=="la_llorona":
        llorona_tears(body,h,mats)
    if style=="lost_child":
        cross_prop("RosaryCross",(0,-.12*d,.53*h),.035*h,mats.get("tarnished_silver",mats["oxidized_metal"]))
    if style=="lost_child":
        uv_sphere("ClothDoll",(0.16,-.04,.34*h),(.05*h,.035*h,.09*h),mats["dirty_ivory"])
    if style in ("sister_of_ash","la_llorona","stained_shade"):
        paint_face_regions(body,h,mats,style)
        if style!="sister_of_ash":
            cut_mouth_open(body,h,style)
            mouth_cavity(body,h,mats,style)
            eye_socket_rings(body,h,mats,style)
    add_damage_sockets(h) if ch["category"] not in ("random_encounter",) else None
    bind_generated_to_rig(body,rig,h)
    create_actions(rig,ch["animations"])
    folder=outroot/ch["id"]; folder.mkdir(parents=True,exist_ok=True)
    objs=collect_character_objects()
    glb,fbx=export_files(folder,objs)
    blend=folder/"model.blend"
    try: bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
    except Exception: bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    for pb in rig.pose.bones:
        pb.rotation_mode="QUATERNION"
        pb.rotation_quaternion=(1.0,0.0,0.0,0.0)
        pb.location=(0.0,0.0,0.0)
        pb.scale=(1.0,1.0,1.0)
    bpy.context.view_layer.update()
    png=preview(body,folder,style)
    tri=sum(sum(max(1,len(p.vertices)-2) for p in o.data.polygons) for o in objs if o.type=="MESH")
    manifest={"id":ch["id"],"name":ch["name"],"category":ch["category"],"style":style,"height_m":ch["height_m"],"rig":"game_engine","bones":len(rig.data.bones),"triangles_estimate":tri,"animations":ch["animations"],"materials":ch["palette"],"outputs":[glb.name,fbx.name,blend.name,png.name,"preview_side.png","preview_back.png","preview_face.png"],"production_status":"Sister of Ash pass 35 — continuous fitted U-wimple, compact closed shoes without toe spheres, full crown coverage and layered habit retained"}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest

def main():
    args=parse_args(); spec=json.loads(Path(args.spec).read_text(encoding="utf-8")); out=Path(args.out_dir); out.mkdir(parents=True,exist_ok=True)
    HumanService=dynamic_import("mpfb.services.humanservice","HumanService")
    ObjectService=dynamic_import("mpfb.services.objectservice","ObjectService")
    TargetService=dynamic_import("mpfb.services.targetservice","TargetService")
    only={x.strip() for x in args.only.split(",") if x.strip()}
    manifests=[]; errors={}
    for ch in spec["characters"]:
        if only and ch["id"] not in only: continue
        print("\\n=== BUILD",ch["id"],"===")
        try:
            manifests.append(make_character(ch,args.assets_root,out,HumanService,ObjectService,TargetService))
        except Exception as e:
            errors[ch["id"]]=repr(e); traceback.print_exc()
    summary={"project":spec["project"],"built":[m["id"] for m in manifests],"errors":errors}
    (out/"roster_build_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    if errors: raise RuntimeError("Character build failures: "+json.dumps(errors))
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()

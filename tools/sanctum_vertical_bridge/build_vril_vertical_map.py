#!/usr/bin/env python3
"""Restore exact Oct-02 Sanctum Vertical GLB into native Vril XZSM v2 plus BSP.

The original GLB is kept as visual authority. Vril has no GLB/Vulkan physics
loader; the original .navbin and .glb collision hulls cannot be mounted as BSP.
This opt-in Android preview reconstructs conservative Quake collision for the
three walkable floors and 4 connections without replacing the original source.
It is NOT proof of a fully faithful 3-floor runtime port.
"""
from pathlib import Path
from PIL import Image
import argparse
import hashlib
import json
import math
import re
import struct
import numpy as np
import trimesh

S = 39.3700787402
CX = -17.81026649475
CZ = 27.3547916412
YMIN = -4.16482270837
MAP = "sanctum_vertical"
VER = 2
TRIS_PER_BATCH = 17000
POINTS_PER_FACE = 3
def quake(points):
    a = np.asarray(points, dtype=np.float64)
    return np.column_stack(((a[:,0]-CX)*S,(CZ-a[:,2])*S,(a[:,1]-YMIN)*S))
def name_slug(s):
    return re.sub('[^a-z0-9_]+','_',str(s).lower())[:35]
def kv(k,v):
    return '"%s" "%s"\n'%(k,v)
def bb(mn,mx,texture="null"):
    a=[int(round(x)) for x in mn]
    b=[int(round(x)) for x in mx]
    assert all(b[i]-a[i]>0 for i in range(3)),(a,b)
    x1,y1,z1=a; x2,y2,z2=b
    planes=[
        ((x1,y1,z1),(x1,y1+1,z1),(x1,y1,z1+1)),
        ((x1,y1,z1),(x1,y1,z1+1),(x1+1,y1,z1)),
        ((x1,y1,z1),(x1+1,y1,z1),(x1,y1+1,z1)),
        ((x2,y2,z2),(x2,y2+1,z2),(x2+1,y2,z2)),
        ((x2,y2,z2),(x2+1,y2,z2),(x2,y2,z2+1)),
        ((x2,y2,z2),(x2,y2,z2+1),(x2,y2+1,z2)),
    ]
    axes=[('[ 0 -1 0 0 ]','[ 0 0 -1 0 ]'),('[ 1 0 0 0 ]','[ 0 0 -1 0 ]'),('[ -1 0 0 0 ]','[ 0 -1 0 0 ]'),('[ 1 0 0 0 ]','[ 0 -1 0 0 ]'),('[ -1 0 0 0 ]','[ 0 0 -1 0 ]'),('[ 0 1 0 0 ]','[ 0 0 -1 0 ]')]
    return '{\n'+''.join('( %d %d %d ) ( %d %d %d ) ( %d %d %d ) %s %s %s 0 1 1\n'%(tuple(p[0])+tuple(p[1])+tuple(p[2])+(texture,*axes[i])) for i,p in enumerate(planes))+'}\n'
def point(cls,xyz,props=None):
    return '{\n'+kv('classname',cls)+kv('origin',' '.join(str(int(round(x))) for x in xyz))+''.join(kv(k,v) for k,v in (props or {}).items())+'}\n'
def brush(cls,mn,mx,texture='trigger',props=None):
    return '{\n'+kv('classname',cls)+''.join(kv(k,v) for k,v in (props or {}).items())+bb(mn,mx,texture)+'}\n'

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--glb',type=Path,required=True)
    p.add_argument('--vertical-report',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--texture-max',type=int,default=1024)
    a=p.parse_args()
    report=json.loads(a.vertical_report.read_text())
    assert report['status']=='PASS' and report['vertical_span_m']>=7.4
    scene=trimesh.load(str(a.glb),force='scene',process=False)
    nodes=list(scene.graph.nodes_geometry)
    assert len(nodes)>90,(len(nodes),'Not original vertical project')
    texdir=a.out/'nzp/textures/xziel/sanctum_vertical'
    model=a.out/'nzp/models/xziel/sanctum_vertical/vertical.xzsm'
    source=a.out/'maps/sanctum_vertical.map'
    texdir.mkdir(parents=True,exist_ok=True)
    model.parent.mkdir(parents=True,exist_ok=True)
    source.parent.mkdir(parents=True,exist_ok=True)
    texture_map={}
    batches=[]
    collision={}
    total_triangles=0
    all_q_bounds=[]
    for node in sorted(nodes):
        tf,key=scene.graph[node]
        mesh=scene.geometry[key]
        if len(mesh.faces)==0:continue
        xyz=trimesh.transform_points(mesh.vertices,tf)
        q=quake(xyz)
        if node.startswith(('SANCTUM_MAIN_FLOOR_','SANCTUM_UPPER_','SANCTUM_UNDERCROFT_FLOOR','SANCTUM_UNDERCROFT_RAMP')):
            if 'GUARD' not in node:
                collision[node]=(q.min(axis=0),q.max(axis=0),q,xyz)
        mat=getattr(mesh.visual,'material',None)
        if mat is None:
            key_name="untextured"
        else:
            key_name=str(getattr(mat,'name', 'material'))
        tex_name=texture_map.get(key_name)
        if tex_name is None:
            idx=len(texture_map)
            stem=f"{idx:03d}_{name_slug(key_name)}"
            tex_name=f"textures/xziel/sanctum_vertical/{stem}"
            base=getattr(mat,'baseColorFactor',None) if mat is not None else None
            rgba=np.asarray(base if base is not None else [255,255,255,255],dtype=np.float64)
            if rgba.ndim!=1 or rgba.size!=4:rgba=np.full(4,255.0,dtype=np.float64)
            if rgba.max()<=1.1: rgba*=255.0
            img=getattr(mat,'baseColorTexture',None) if mat is not None else None
            if img is None:
                img=getattr(mat,'image',None) if mat is not None else None
            if isinstance(img,Image.Image):
                im=img.convert('RGBA').copy()
                if max(im.size)>a.texture_max:
                    im.thumbnail((a.texture_max,a.texture_max),Image.Resampling.LANCZOS)
                # Actual imported image carries authored colors; factor is
                # intentionally not multiplied twice into baked bitmap.
            else:
                im=Image.new('RGBA',(8,8),tuple(int(v) for v in np.clip(rgba,0,255)))
            im.save(texdir/(stem+'.png'),format="PNG",optimize=True)
            texture_map[key_name]=tex_name
        uv=getattr(mesh.visual,'uv',None)
        if uv is None or len(uv)!=len(mesh.vertices):
            uv=np.zeros((len(mesh.vertices),2),dtype=float)
        faces=np.asarray(mesh.faces,dtype=np.int64)
        for start in range(0,len(faces),TRIS_PER_BATCH):
            indices, inverse=np.unique(faces[start:start+TRIS_PER_BATCH].ravel(),return_inverse=True)
            vertices=q[indices]
            coords=np.asarray(uv)[indices]
            # Trimesh glTF importer UV is flipped relative to OpenGL.
            rgb=np.full((len(vertices),4),255,dtype=np.uint8)
            mn=vertices.min(axis=0);mx=vertices.max(axis=0)
            data=bytearray()
            for v,t,c in zip(vertices,coords,rgb):
                data+=struct.pack('<5f4B',float(v[0]),float(v[1]),float(v[2]),
                     float(t[0]),float(1.0-t[1]),int(c[0]),int(c[1]),int(c[2]),255)
            idx=inverse.astype('<u2',copy=False).tobytes()
            assert len(indices)<65535 and len(inverse)<65535
            batches.append((tex_name,len(indices),len(inverse),mn,mx,bytes(data),idx))
            total_triangles+=len(inverse)//3
    assert len(batches)<512 and total_triangles>130000 and len(texture_map)>=20,(len(batches),total_triangles,len(texture_map))
    with model.open('wb') as f:
        f.write(struct.pack('<4sIIII',b'XZSM',VER,len(batches),sum(b[1] for b in batches),sum(b[2] for b in batches)))
        for tex,nv,ni,mn,mx,data,idx in batches:
            name=tex.encode('utf8')
            assert len(name)<96
            f.write(struct.pack('<II96s6f',nv,ni,name.ljust(96,b'\0'),*map(float,mn),*map(float,mx)))
            f.write(data);f.write(idx)
    # Real authored floor panels preserve the original *visible* holes so the
    # undercroft is reachable. Physics brushes are from the same GLB nodes.
    floor_names=[n for n in collision if n.startswith('SANCTUM_MAIN_FLOOR_') or n=='SANCTUM_UNDERCROFT_FLOOR' or (n.startswith('SANCTUM_UPPER_') and any(k in n for k in ('WALKWAY','BRIDGE')))]
    ramp_names=[n for n in collision if '_RAMP_' in n]
    assert len(floor_names)>=10 and len(ramp_names)==4,(floor_names,ramp_names)
    parts=['// Sanctum V2 vertical: authored GLB collision proxy / native NZ:P\n','{\n',
           kv('mapversion','220'),kv('classname','worldspawn'),
           kv('message','XZIEL: SANCTUM V2 VERTICAL PREVIEW'),
           kv('chaptertitle','SANCTUM V2'),kv('location','Three-floor vertical church'),
           kv('person','XZIEL'),kv('wad','../../textures/wad/zhlt.wad;../../textures/wad/Example_02.wad')]
    # Sealed world. The visible church is solely the authored 3D model.
    parts.extend([
        bb((-1280,-1600,-96),(1280,1600,-64),'tiles_me'),
        bb((-1280,-1600,2120),(1280,1600,2152),'ceilings_64'),
        bb((-1312,-1600,-64),(-1280,1600,2120),'facility_wall_l'),
        bb((1280,-1600,-64),(1312,1600,2120),'facility_wall_l'),
        bb((-1280,-1632,-64),(1280,-1600,2120),'facility_wall_l'),
        bb((-1280,1600,-64),(1280,1632,2120),'facility_wall_l')])
    for n in sorted(floor_names):
        mn,mx,*_=collision[n]
        # Signed subunit offsets deliberately kept; brush quantization max < 1u
        lo=np.round(mn).astype(int);hi=np.round(mx).astype(int)
        for i in range(3):
            if hi[i] <=lo[i]:hi[i]=lo[i]+1
        parts.append(bb(lo,hi,'tiles_me'))
    # One brush per 7-8u step approximates original sloped mesh. Vril cannot
    # directly consume GLB collision hulls. Ramps remain reachable, not precise.
    for n in sorted(ramp_names):
        mn,mx,q,xyz=collision[n]
        z=xyz[:,2];height=q[:,2]
        zlo,zhi=float(z.min()),float(z.max())
        h_lo=float(np.max(height[np.abs(z-zlo)<.03]))
        h_hi=float(np.max(height[np.abs(z-zhi)<.03]))
        if not np.isfinite(h_lo+h_hi):raise SystemExit(f'{n} invalid ramp')
        steps=28
        for i in range(steps):
            t0=i/steps;t1=(i+1)/steps
            z0=zlo+(zhi-zlo)*t0;z1=zlo+(zhi-zlo)*t1
            y0=(CZ-z0)*S;y1=(CZ-z1)*S
            top=h_lo+(h_hi-h_lo)*(i+.5)/steps
            x0,x1=int(round(mn[0])),int(round(mx[0]))
            a0,a1=sorted((int(round(y0)),int(round(y1))))
            # stop each stair at closest available floor's height; solid support
            bottom=0 if 'UNDERCROFT' in n else 125
            top_i=max(bottom+6,int(round(top)))
            if x1>x0 and a1>a0:parts.append(bb((x0,a0,bottom),(x1,a1,top_i),'tiles_me'))
    parts.append('}\n')
    # Exactly four spawn slots on the main floor, facing into the nave.
    nave_z=(report['floor_heights_m']['nave']-YMIN)*S
    for i,(x,y) in enumerate([(-80,-100),(-40,-100),(-80,-40),(-40,-40)],1):
        parts.append(point(f'info_player_{i}_spawn',(x,y,nave_z+40),
                  {'weapon':'0','currentmag':'0','currentammo':'0','angle':'0'}))
    parts.append(brush('spawn_zone',(-480,-690,int(nave_z)+4),(480,690,int(nave_z)+180),'trigger',
                       {'zone_name':'church','adjacent_zones':'','zone_target':'sanctum_vertical_zombies'}))
    for (x,y) in [(-420,-520),(420,-520),(-420,520),(420,520)]:
        parts.append(point('spawn_zombie',(x,y,nave_z+40),
            {'targetname':'sanctum_vertical_zombies','spawnflags':'4','angle':'180'}))
    for (x,y) in [(-360,-420),(360,-420),(-360,420),(360,420)]:
        parts.append(point('light',(x,y,nave_z+220),{'_light':'450','wait':'1','style':'0'}))
    source.write_text(''.join(parts),encoding='utf8')
    (a.out/'nzp/maps/sanctum_vertical.txt').parent.mkdir(parents=True,exist_ok=True)
    (a.out/'nzp/maps/sanctum_vertical.txt').write_text(
        'XZIEL: SANCTUM V2\nTHREE FLOOR CHURCH\nNave Gallery Undercroft\nVertical test build\nFrom Oct 2 original GLB\nXZIEL\n\n\n\nXZIEL\n0\n1\n',encoding='utf8')
    result={'status':'CONVERTED_NOT_DEVICE_PROVEN','name':MAP,
      'source_sha256':hashlib.sha256(a.glb.read_bytes()).hexdigest(),
      'mesh_nodes':len(nodes),'batches':len(batches),'triangles':total_triangles,
      'textures':len(texture_map),'floor_panels':len(floor_names),'ramps':len(ramp_names),
      'height_m':report['vertical_span_m'],'xzsm':str(model),'quake_map':str(source),
      'collision':'authored floor AABB + 28-step ramp approximations (NOT original Vulkan hulls)',
      'required_device_checks':['gallery visible','basement traversal','two upper ramps','all floors solid','spawns','textures']}
    (a.out/'sanctum_vertical_bridge_report.json').write_text(json.dumps(result,indent=2)+'\n')
    print('XZIEL_SANCTUM_VERTICAL_BRIDGE_CONVERTED',json.dumps({k:result[k] for k in ('mesh_nodes','triangles','textures','floor_panels','ramps')}))
if __name__=='__main__':main()

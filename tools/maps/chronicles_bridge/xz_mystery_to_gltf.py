#!/usr/bin/env python3
import argparse, base64, json, math, struct
from pathlib import Path

COMPONENT_FLOAT = 5126
COMPONENT_U16 = 5123
COMPONENT_U32 = 5125
TARGET_ARRAY = 34962
TARGET_ELEMENT = 34963

def u32(data, o): return struct.unpack_from("<I", data, o)[0]
def i32(data, o): return struct.unpack_from("<i", data, o)[0]
def u64(data, o): return struct.unpack_from("<Q", data, o)[0]
def f32s(data, o, n): return struct.unpack_from("<" + "f"*n, data, o)

def norm_quat(q):
    l = math.sqrt(sum(v*v for v in q))
    return [0.0,0.0,0.0,1.0] if l < 1e-12 else [v/l for v in q]

def mat_mul(a,b):
    out=[0.0]*16
    for c in range(4):
        for r in range(4):
            out[c*4+r]=sum(a[k*4+r]*b[c*4+k] for k in range(4))
    return out

def trs_matrix(t,q,s):
    x,y,z,w = norm_quat(q)
    xx,yy,zz=x*x,y*y,z*z
    xy,xz,yz=x*y,x*z,y*z
    wx,wy,wz=w*x,w*y,w*z
    return [
        (1-2*(yy+zz))*s[0], (2*(xy+wz))*s[0], (2*(xz-wy))*s[0], 0.0,
        (2*(xy-wz))*s[1], (1-2*(xx+zz))*s[1], (2*(yz+wx))*s[1], 0.0,
        (2*(xz+wy))*s[2], (2*(yz-wx))*s[2], (1-2*(xx+yy))*s[2], 0.0,
        t[0], t[1], t[2], 1.0
    ]

def inv_affine(m):
    a00,a01,a02 = m[0],m[4],m[8]
    a10,a11,a12 = m[1],m[5],m[9]
    a20,a21,a22 = m[2],m[6],m[10]
    det = a00*(a11*a22-a12*a21)-a01*(a10*a22-a12*a20)+a02*(a10*a21-a11*a20)
    if abs(det) < 1e-12:
        raise ValueError("singular bind matrix")
    d=1.0/det
    b00=(a11*a22-a12*a21)*d; b01=(a02*a21-a01*a22)*d; b02=(a01*a12-a02*a11)*d
    b10=(a12*a20-a10*a22)*d; b11=(a00*a22-a02*a20)*d; b12=(a02*a10-a00*a12)*d
    b20=(a10*a21-a11*a20)*d; b21=(a01*a20-a00*a21)*d; b22=(a00*a11-a01*a10)*d
    tx,ty,tz=m[12],m[13],m[14]
    itx=-(b00*tx+b01*ty+b02*tz)
    ity=-(b10*tx+b11*ty+b12*tz)
    itz=-(b20*tx+b21*ty+b22*tz)
    return [b00,b10,b20,0.0,b01,b11,b21,0.0,b02,b12,b22,0.0,itx,ity,itz,1.0]

def parse_rig(path):
    data=Path(path).read_bytes()
    if data[:4] != b"XZRG" or u32(data,4) != 1: raise ValueError("bad XZRG")
    count=u32(data,12); stride=u32(data,16); bone_off=u32(data,20)
    str_off=u32(data,24); str_bytes=u32(data,28); skel_hash=u64(data,32)
    strings=data[str_off:str_off+str_bytes]
    bones=[]
    for i in range(count):
        o=bone_off+i*stride
        parent=i32(data,o); no=u32(data,o+4); nb=u32(data,o+8)
        q=list(f32s(data,o+16,4)); t=list(f32s(data,o+32,3)); s=list(f32s(data,o+44,3))
        name=strings[no:no+nb].decode("utf-8","replace")
        bones.append({"name":name,"parent":parent,"rotation":norm_quat(q),"translation":t,"scale":s})
    return skel_hash,bones

def parse_mesh(path):
    data=Path(path).read_bytes()
    if data[:4] != b"XZSK" or u32(data,4) != 2: raise ValueError("bad XZSK")
    bone_count=u32(data,12); vcount=u32(data,16); icount=u32(data,20); scount=u32(data,24)
    bstride=u32(data,28); vstride=u32(data,32); sstride=u32(data,36)
    bo=u32(data,40); vo=u32(data,44); io=u32(data,48); so=u32(data,52); st=u32(data,56); sb=u32(data,60)
    skel_hash=u64(data,64); strings=data[st:st+sb]
    bone_remap=[]
    for i in range(bone_count):
        o=bo+i*bstride
        no=u32(data,o+4); nb=u32(data,o+8); skidx=u32(data,o+12)
        bone_remap.append({"name":strings[no:no+nb].decode("utf-8","replace"),"skeleton_index":skidx})
    pos=[]; nrm=[]; tan=[]; uv=[]; joints0=[]; weights0=[]; joints1=[]; weights1=[]
    for i in range(vcount):
        o=vo+i*vstride
        vals=f32s(data,o,26)
        pos.append(vals[0:3]); nrm.append(vals[3:6]); tan.append(vals[6:10]); uv.append(vals[10:12])
        js=list(struct.unpack_from("<8H",data,o+104)); ws=list(struct.unpack_from("<8H",data,o+120))
        remapped=[bone_remap[j]["skeleton_index"] if j < len(bone_remap) else 0 for j in js]
        wf=[w/65535.0 for w in ws]
        total=sum(wf)
        if total > 0:
            wf=[w/total for w in wf]
        joints0.append(remapped[:4]); weights0.append(wf[:4]); joints1.append(remapped[4:]); weights1.append(wf[4:])
    indices=list(struct.unpack_from("<"+"I"*icount,data,io))
    sections=[]
    for i in range(scount):
        o=so+i*sstride
        sections.append({"first":u32(data,o),"count":u32(data,o+4),"material":u32(data,o+8),"cast_shadow":bool(u32(data,o+12))})
    return skel_hash, {"pos":pos,"nrm":nrm,"tan":tan,"uv":uv,"j0":joints0,"w0":weights0,"j1":joints1,"w1":weights1,"indices":indices,"sections":sections}

def parse_anim(path):
    data=Path(path).read_bytes()
    if data[:4] != b"XZAN" or u32(data,4) != 1: raise ValueError("bad XZAN")
    flags=u32(data,8); frames=u32(data,12); fps=struct.unpack_from("<f",data,16)[0]; duration=struct.unpack_from("<f",data,20)[0]
    tracks=u32(data,24); stride=u32(data,28); to=u32(data,32); po=u32(data,36); pb=u32(data,40); skel_hash=u64(data,48)
    payload=data[po:po+pb]
    out=[]
    for i in range(tracks):
        o=to+i*stride
        vals=struct.unpack_from("<14I",data,o)
        pc,rc,sc,shc,ptc,rtc,stc, pof,rof,sof,shof,ptof,rtof,stof = vals
        def vecs(off,count,n): return [list(x) for x in struct.iter_unpack("<"+"f"*n,payload[off:off+count*n*4])]
        def times(off,count): return list(struct.unpack_from("<"+"f"*count,payload,off)) if count else []
        out.append({
            "pos":vecs(pof,pc,3),"rot":[norm_quat(x) for x in vecs(rof,rc,4)],"scale":vecs(sof,sc,3),
            "shared":times(shof,shc),"pt":times(ptof,ptc),"rt":times(rtof,rtc),"st":times(stof,stc)
        })
    return skel_hash,frames,fps,duration,bool(flags & 2),out

class Builder:
    def __init__(self):
        self.buf=bytearray(); self.views=[]; self.accessors=[]
    def add(self, raw, component, typ, count, target=None, minv=None, maxv=None):
        while len(self.buf)%4: self.buf.append(0)
        off=len(self.buf); self.buf.extend(raw)
        view={"buffer":0,"byteOffset":off,"byteLength":len(raw)}
        if target: view["target"]=target
        vi=len(self.views); self.views.append(view)
        acc={"bufferView":vi,"componentType":component,"count":count,"type":typ}
        if minv is not None: acc["min"]=minv
        if maxv is not None: acc["max"]=maxv
        ai=len(self.accessors); self.accessors.append(acc)
        return ai
    def floats(self, rows, typ, target=None, minmax=False):
        flat=[float(v) for r in rows for v in r]
        raw=struct.pack("<"+"f"*len(flat),*flat)
        mn=mx=None
        if minmax and rows:
            dims=len(rows[0]); mn=[min(r[d] for r in rows) for d in range(dims)]; mx=[max(r[d] for r in rows) for d in range(dims)]
        return self.add(raw,COMPONENT_FLOAT,typ,len(rows),target,mn,mx)
    def u16s(self, rows, typ, target=None):
        flat=[int(v) for r in rows for v in r]
        return self.add(struct.pack("<"+"H"*len(flat),*flat),COMPONENT_U16,typ,len(rows),target)
    def u32s(self, vals, target=None):
        return self.add(struct.pack("<"+"I"*len(vals),*vals),COMPONENT_U32,"SCALAR",len(vals),target)
    def scalars(self, vals, minmax=True):
        rows=[[float(v)] for v in vals]
        return self.floats(rows,"SCALAR",None,minmax)

def choose_times(track, key_count, key_name, frames, fps, duration):
    if key_count <= 0: return []
    specific=track[key_name]
    shared=track["shared"]
    raw = specific if len(specific)==key_count else shared if len(shared)==key_count else []
    if raw: return [min(duration,max(0.0,v/fps)) for v in raw]
    if key_count == 1: return [0.0]
    step=duration/float(key_count-1)
    return [step*i for i in range(key_count)]

def safe_anim_name(package):
    stem=Path(package).stem
    for token in ["o_zombie_magic_box_","untitled_Anim_Armature_006_"]:
        if token in stem: stem=stem.split(token,1)[1]
    return stem.replace(" ","_")

def find_report(root, leaf):
    hits=list(Path(root).glob(f"**/{leaf}/report.json"))
    if len(hits)!=1: raise SystemExit(f"expected one {leaf}/report.json, got {hits}")
    return hits[0], json.loads(hits[0].read_text())

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("artifact_root"); ap.add_argument("output_dir")
    args=ap.parse_args()
    rpath,rj=find_report(args.artifact_root,"xzrg")
    mpath,mj=find_report(args.artifact_root,"xzsk")
    apath,aj=find_report(args.artifact_root,"xzan")
    meshrow=next(x for x in mj["meshes"] if "/box/1/untitled.uasset" in x["packagePath"].replace("\\","/"))
    skh=meshrow["skeletonHash"]
    rigrow=next(x for x in rj["skeletons"] if x["skeletonHash"]==skh)
    animrows=[x for x in aj["animations"] if x["skeletonHash"]==skh and "/box/1/" in x["packagePath"].replace("\\","/")]
    if len(animrows)!=7: raise SystemExit(f"expected 7 mystery animations, got {len(animrows)}")
    rigfile=rpath.parent/rigrow["file"]; meshfile=mpath.parent/meshrow["file"]
    rig_hash,bones=parse_rig(rigfile); mesh_hash,mesh=parse_mesh(meshfile)
    if f"{rig_hash:016x}"!=skh or f"{mesh_hash:016x}"!=skh: raise SystemExit("skeleton hash mismatch")
    if max((j for row in mesh["j0"]+mesh["j1"] for j in row),default=0) >= len(bones): raise SystemExit("joint remap exceeds rig")

    b=Builder()
    pos_a=b.floats(mesh["pos"],"VEC3",TARGET_ARRAY,True)
    nrm_a=b.floats(mesh["nrm"],"VEC3",TARGET_ARRAY)
    tan_a=b.floats(mesh["tan"],"VEC4",TARGET_ARRAY)
    uv_a=b.floats(mesh["uv"],"VEC2",TARGET_ARRAY)
    j0_a=b.u16s(mesh["j0"],"VEC4",TARGET_ARRAY); w0_a=b.floats(mesh["w0"],"VEC4",TARGET_ARRAY)
    j1_a=b.u16s(mesh["j1"],"VEC4",TARGET_ARRAY); w1_a=b.floats(mesh["w1"],"VEC4",TARGET_ARRAY)
    idx_a=b.u32s(mesh["indices"],TARGET_ELEMENT)

    local=[trs_matrix(x["translation"],x["rotation"],x["scale"]) for x in bones]
    glob=[]
    for i,x in enumerate(bones):
        glob.append(local[i] if x["parent"]<0 else mat_mul(glob[x["parent"]],local[i]))
    ibm=[inv_affine(x) for x in glob]
    ibm_a=b.floats(ibm,"MAT4")

    nodes=[]
    for x in bones:
        nodes.append({"name":x["name"],"translation":x["translation"],"rotation":x["rotation"],"scale":x["scale"]})
    roots=[]
    for i,x in enumerate(bones):
        if x["parent"]<0: roots.append(i)
        else: nodes[x["parent"]].setdefault("children",[]).append(i)
    mesh_node=len(nodes); nodes.append({"name":"MysteryBox_SourceMesh","mesh":0,"skin":0})

    materials=[]
    maxmat=max((s["material"] for s in mesh["sections"]),default=0)
    for i in range(maxmat+1):
        materials.append({"name":f"SourceMaterial_{i:02d}","pbrMetallicRoughness":{"baseColorFactor":[0.72,0.72,0.72,1.0],"metallicFactor":0.0,"roughnessFactor":0.75}})
    prims=[]
    index_view=b.accessors[idx_a]["bufferView"]
    for s in mesh["sections"]:
        acc={"bufferView":index_view,"byteOffset":s["first"]*4,"componentType":COMPONENT_U32,"count":s["count"],"type":"SCALAR"}
        ai=len(b.accessors); b.accessors.append(acc)
        prims.append({"attributes":{"POSITION":pos_a,"NORMAL":nrm_a,"TANGENT":tan_a,"TEXCOORD_0":uv_a,"JOINTS_0":j0_a,"WEIGHTS_0":w0_a,"JOINTS_1":j1_a,"WEIGHTS_1":w1_a},"indices":ai,"material":s["material"],"mode":4})
    animations=[]
    manifest_anims=[]
    for row in sorted(animrows,key=lambda x:x["packagePath"]):
        h,frames,fps,duration,additive,tracks=parse_anim(apath.parent/row["file"])
        if h!=rig_hash: raise SystemExit(f"animation hash mismatch {row['file']}")
        samplers=[]; channels=[]
        for ti,tr in enumerate(tracks[:len(bones)]):
            for key,path_name,typ in [("pos","translation","VEC3"),("rot","rotation","VEC4"),("scale","scale","VEC3")]:
                vals=tr[key]
                if not vals: continue
                time_key={"pos":"pt","rot":"rt","scale":"st"}[key]
                times=choose_times(tr,len(vals),time_key,frames,fps,duration)
                ia=b.scalars(times,True); oa=b.floats(vals,typ)
                si=len(samplers); samplers.append({"input":ia,"output":oa,"interpolation":"LINEAR"})
                channels.append({"sampler":si,"target":{"node":ti,"path":path_name}})
        name=safe_anim_name(row["packagePath"])
        animations.append({"name":name,"samplers":samplers,"channels":channels})
        manifest_anims.append({"name":name,"packagePath":row["packagePath"],"frames":frames,"fps":fps,"duration":duration,"additive":additive})
    outdir=Path(args.output_dir); outdir.mkdir(parents=True,exist_ok=True)
    gltf={
        "asset":{"version":"2.0","generator":"XZIEL XZRG/XZSK/XZAN source bridge"},
        "scene":0,
        "scenes":[{"name":"MysteryBox_Source","nodes":roots+[mesh_node]}],
        "nodes":nodes,
        "meshes":[{"name":"MysteryBox_SourceMesh","primitives":prims}],
        "skins":[{"name":"MysteryBox_SourceSkin","joints":list(range(len(bones))),"skeleton":roots[0] if roots else 0,"inverseBindMatrices":ibm_a}],
        "materials":materials,
        "animations":animations,
        "buffers":[{"byteLength":len(b.buf),"uri":"data:application/octet-stream;base64,"+base64.b64encode(bytes(b.buf)).decode("ascii")}],
        "bufferViews":b.views,
        "accessors":b.accessors
    }
    out=(outdir/"mystery_box_source.gltf")
    out.write_text(json.dumps(gltf,separators=(",",":")))
    manifest={"schemaVersion":1,"sourceGeometry":meshrow["packagePath"],"sourceSkeleton":rigrow["packagePath"],"skeletonHash":skh,"bones":len(bones),"vertices":len(mesh["pos"]),"indices":len(mesh["indices"]),"sections":len(mesh["sections"]),"animations":manifest_anims,"ready":True}
    (outdir/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(f"XZOGOT_MYSTERY_GLTF_GREEN bones={len(bones)} vertices={len(mesh['pos'])} animations={len(animations)}")

if __name__=="__main__":
    main()

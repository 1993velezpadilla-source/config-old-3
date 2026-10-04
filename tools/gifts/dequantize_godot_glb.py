#!/usr/bin/env python3
"""Remove KHR_mesh_quantization from GLBs without altering topology or textures.

Godot 4.6.x does not import KHR_mesh_quantization. This tool expands quantized
vertex attributes to FLOAT while preserving accessor values exactly as decoded
by the extension. Indices, materials, images, UVs already stored as FLOAT, and
all external texture bytes are untouched.
"""
from __future__ import annotations
import argparse, json, struct
from pathlib import Path

JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
FLOAT = 5126
COMP = {
    5120: ('b', 1, True, 127.0),
    5121: ('B', 1, False, 255.0),
    5122: ('h', 2, True, 32767.0),
    5123: ('H', 2, False, 65535.0),
    5125: ('I', 4, False, 4294967295.0),
    5126: ('f', 4, None, None),
}
NCOMP = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT2':4,'MAT3':9,'MAT4':16}

def pad4(data: bytes, fill: bytes=b'\0') -> bytes:
    return data + fill * ((-len(data)) & 3)

def read_glb(path: Path):
    data = path.read_bytes()
    magic, ver, total = struct.unpack_from('<4sII', data, 0)
    if magic != b'glTF' or ver != 2 or total != len(data):
        raise ValueError(f'{path}: invalid GLB header')
    off=12; js=None; bin_data=b''; extras=[]
    while off < total:
        ln, typ = struct.unpack_from('<II',data,off); off += 8
        chunk=data[off:off+ln]; off += ln
        if typ == JSON_CHUNK:
            js=json.loads(chunk.rstrip(b' \0').decode('utf-8'))
        elif typ == BIN_CHUNK:
            bin_data=chunk
        else:
            extras.append((typ,chunk))
    if js is None:
        raise ValueError(f'{path}: no JSON chunk')
    return js, bytearray(bin_data), extras

def write_glb(path: Path, js: dict, bin_data: bytes, extras):
    j=pad4(json.dumps(js,separators=(',',':'),ensure_ascii=False).encode('utf-8'),b' ')
    b=pad4(bytes(bin_data),b'\0')
    chunks=[struct.pack('<II',len(j),JSON_CHUNK)+j]
    if b:
        chunks.append(struct.pack('<II',len(b),BIN_CHUNK)+b)
    for typ,chunk in extras:
        chunk=pad4(chunk,b'\0')
        chunks.append(struct.pack('<II',len(chunk),typ)+chunk)
    body=b''.join(chunks)
    path.write_bytes(struct.pack('<4sII',b'glTF',2,12+len(body))+body)

def decode_component(raw, ctype: int, normalized: bool) -> float:
    if ctype == FLOAT:
        return float(raw)
    _,_,signed,maxv=COMP[ctype]
    if not normalized:
        return float(raw)
    return max(float(raw)/maxv,-1.0) if signed else float(raw)/maxv

def convert(path: Path) -> tuple[int,int]:
    js,bin_data,extras=read_glb(path)
    if 'KHR_mesh_quantization' not in js.get('extensionsUsed',[]) and 'KHR_mesh_quantization' not in js.get('extensionsRequired',[]):
        return 0,0
    accessors=js.get('accessors',[]); views=js.get('bufferViews',[])
    targets=[]; seen=set()
    for mesh in js.get('meshes',[]):
        for prim in mesh.get('primitives',[]):
            for sem,ai in prim.get('attributes',{}).items():
                if sem.startswith('JOINTS_'):
                    continue
                a=accessors[ai]
                if a.get('componentType') != FLOAT and ai not in seen:
                    seen.add(ai); targets.append((sem,ai))
    converted_values=0
    for sem,ai in targets:
        a=accessors[ai]; ctype=a['componentType']; typ=a['type']; count=int(a['count'])
        if ctype not in COMP:
            raise ValueError(f'{path}: unsupported componentType {ctype}')
        fmt,size,_,_=COMP[ctype]; n=NCOMP[typ]
        bv=views[a['bufferView']]
        stride=int(bv.get('byteStride',size*n))
        base=int(bv.get('byteOffset',0))+int(a.get('byteOffset',0))
        normalized=bool(a.get('normalized',False))
        out=bytearray(count*n*4)
        unpack='<'+fmt*n
        for i in range(count):
            vals=struct.unpack_from(unpack,bin_data,base+i*stride)
            fvals=[decode_component(v,ctype,normalized) for v in vals]
            struct.pack_into('<'+'f'*n,out,i*n*4,*fvals)
        while len(bin_data)&3:
            bin_data.append(0)
        new_off=len(bin_data); bin_data.extend(out)
        views.append({'buffer':int(bv.get('buffer',0)),'byteOffset':new_off,'byteLength':len(out)})
        a['bufferView']=len(views)-1
        a['byteOffset']=0
        a['componentType']=FLOAT
        a.pop('normalized',None)
        converted_values += count*n
    if js.get('buffers'):
        js['buffers'][0]['byteLength']=len(bin_data)
    remaining=False
    for mesh in js.get('meshes',[]):
        for prim in mesh.get('primitives',[]):
            for sem,ai in prim.get('attributes',{}).items():
                if sem.startswith('JOINTS_'):
                    continue
                if accessors[ai].get('componentType') != FLOAT:
                    remaining=True
    if not remaining:
        for key in ('extensionsUsed','extensionsRequired'):
            if key in js:
                js[key]=[x for x in js[key] if x!='KHR_mesh_quantization']
                if not js[key]:
                    js.pop(key)
    write_glb(path,js,bin_data,extras)
    sidecar=Path(str(path)+'.import')
    if sidecar.exists():
        sidecar.unlink()
    return len(targets),converted_values

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('root',type=Path)
    args=ap.parse_args()
    paths=[args.root] if args.root.is_file() else sorted(args.root.rglob('*.glb'))
    files=attrs=values=0
    for p in paths:
        a,v=convert(p)
        if a:
            files+=1; attrs+=a; values+=v
            print('XZOGOT_GLTF_DEQUANTIZED',p,a,v)
    print('XZOGOT_GLTF_DEQUANTIZE_GREEN',files,attrs,values)

if __name__=='__main__':
    main()

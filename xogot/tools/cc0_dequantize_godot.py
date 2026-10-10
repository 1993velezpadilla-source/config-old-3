#!/usr/bin/env python3
"""Turn KHR_mesh_quantization POS/NORMAL into core float32 glTF2.

The 3DAssets.dev CC0 hospital GLBs require mesh quantization, which the
Godot 4.6.1-stable importer rejects. Pure-stdlib offline rewrite: preserve
actual mesh, nodes, materials, geometry, and pivots, without source forgery.
Retain separately the original GLBs and SHA256 audit manifest.
"""
import argparse
import json
import pathlib
import struct


def dequant_glb(blob):
    if len(blob)<20 or blob[:4]!=b'glTF':
        raise ValueError('not binary glTF')
    _,version,total=struct.unpack_from('<4sII',blob)
    if version!=2 or total!=len(blob):
        raise ValueError('GLB2 header invalid')
    chunks=[]
    offset=12
    while offset<len(blob):
        length,kind=struct.unpack_from('<I4s',blob,offset)
        offset+=8
        if offset+length>len(blob):
            raise ValueError('corrupt GLB chunk')
        chunks.append((kind,blob[offset:offset+length]))
        offset+=length
    if (len(chunks)!=2 or chunks[0][0]!=b'JSON'
            or chunks[1][0]!=b'BIN\x00'):
        raise ValueError('expected self-contained JSON+BIN GLB')
    data=json.loads(chunks[0][1].decode('utf8').strip(' \x00'))
    if 'KHR_mesh_quantization' not in data.get('extensionsRequired',[]):
        raise ValueError('source does not require mesh quantization')
    if len(data.get('buffers',[]))!=1:
        raise ValueError('expected one original binary buffer')
    original=chunks[1][1]
    output=bytearray(original)
    views=data['bufferViews']
    seen=set()
    decoded=0
    for mesh in data['meshes']:
        for primitive in mesh['primitives']:
            for semantic,accessor_id in primitive['attributes'].items():
                if semantic not in ('POSITION','NORMAL') or accessor_id in seen:
                    continue
                seen.add(accessor_id)
                accessor=data['accessors'][accessor_id]
                if (accessor.get('componentType')!=5122
                        or not accessor.get('normalized')
                        or accessor.get('type')!='VEC3'):
                    raise ValueError('unexpected '+semantic+' format')
                old=views[accessor['bufferView']]
                if old.get('buffer')!=0:
                    raise ValueError('unexpected buffer index')
                first=int(old.get('byteOffset',0))+int(accessor.get('byteOffset',0))
                stride=int(old.get('byteStride',6))
                count=int(accessor['count'])
                if count<3 or first+(count-1)*stride+6>len(original):
                    raise ValueError('accessor out of bounds')
                if len(output)%4:
                    output.extend(b'\x00'*(-len(output)%4))
                dest=len(output)
                minimum=[float('inf')]*3
                maximum=[float('-inf')]*3
                for i in range(count):
                    quantized=struct.unpack_from('<3h',original,first+i*stride)
                    vector=[max(-1.0,float(v)/32767.0) for v in quantized]
                    for k,x in enumerate(vector):
                        minimum[k]=min(minimum[k],x)
                        maximum[k]=max(maximum[k],x)
                    output.extend(struct.pack('<3f',*vector))
                views.append({'buffer':0,'byteOffset':dest,'byteLength':count*12})
                accessor['bufferView']=len(views)-1
                accessor.pop('byteOffset',None)
                accessor.pop('normalized',None)
                accessor['componentType']=5126
                accessor['min']=minimum
                accessor['max']=maximum
                decoded+=1
    if decoded<2:
        raise ValueError('converted no position/normal accessors')
    for field in ('extensionsRequired','extensionsUsed'):
        data[field]=[v for v in data.get(field,[])
                     if v!='KHR_mesh_quantization']
    data['buffers'][0]['byteLength']=len(output)
    document=json.dumps(data,separators=(',',':'),ensure_ascii=False).encode('utf8')
    document+=b' '*(-len(document)%4)
    output.extend(b'\x00'*(-len(output)%4))
    payload=(struct.pack('<I4s',len(document),b'JSON')+document+
             struct.pack('<I4s',len(output),b'BIN\x00')+bytes(output))
    encoded=struct.pack('<4sII',b'glTF',2,12+len(payload))+payload
    if len(encoded)!=12+len(payload):
        raise AssertionError('output GLB header size mismatch')
    return encoded,decoded


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',required=True,type=pathlib.Path)
    ap.add_argument('--dest',required=True,type=pathlib.Path)
    opt=ap.parse_args()
    opt.dest.mkdir(parents=True,exist_ok=True)
    models=sorted(opt.source.glob('*.glb'))
    if len(models)!=16:
        raise RuntimeError('expected exactly 16 previously CC0-approved models')
    total=0
    for file in models:
        converted,n=dequant_glb(file.read_bytes())
        (opt.dest/file.name).write_bytes(converted)
        total+=n
        print('BLACK_PINES_CC0_DEQUANTIZED_GODOT_GLTF2_GREEN',
              file.name,'accessors=',n,'bytes=',len(converted),flush=True)
    print('BLACK_PINES_CC0_ALL_16_GODOT_COMPATIBLE_GREEN',
          'files=',len(models),'accessors=',total,flush=True)


if __name__=='__main__':
    main()

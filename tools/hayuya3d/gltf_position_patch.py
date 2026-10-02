#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import asdict,dataclass
from pathlib import Path
from typing import Iterable


JSON_CHUNK=0x4E4F534A
BIN_CHUNK=0x004E4942


@dataclass
class PositionPatchResult:
    source_glb:str
    output_glb:str
    patched_accessors:list[int]
    patched_vertices:int
    skin_signature_before:str
    skin_signature_after:str
    skin_payload_preserved:bool
    runtime_signature_before:str=""
    runtime_signature_after:str=""
    runtime_payload_preserved:bool=True
    ready:bool=True
    error:str|None=None
    method:str="hayuya-gltf-position-patch-v1"


def _chunks(path:Path)->tuple[int,list[tuple[int,bytes]]]:
    blob=path.read_bytes()
    if len(blob)<20 or blob[:4]!=b"glTF":
        raise ValueError("not a GLB")
    version,total=struct.unpack_from("<II",blob,4)
    if version!=2 or total>len(blob):
        raise ValueError("invalid GLB header")
    out=[]
    offset=12
    while offset+8<=total:
        length,kind=struct.unpack_from("<II",blob,offset)
        offset+=8
        end=offset+length
        if end>total:
            raise ValueError("GLB chunk exceeds file")
        out.append((kind,blob[offset:end]))
        offset=end
    return version,out


def _doc_and_bin(path:Path)->tuple[dict,bytes,list[tuple[int,bytes]]]:
    _,chunks=_chunks(path)
    doc=None
    binary=None
    for kind,payload in chunks:
        if kind==JSON_CHUNK and doc is None:
            doc=json.loads(payload.rstrip(b"\x00 \t\r\n").decode("utf-8"))
        elif kind==BIN_CHUNK and binary is None:
            binary=payload
    if doc is None:
        raise ValueError("GLB JSON chunk missing")
    if binary is None:
        raise ValueError("GLB BIN chunk missing")
    return doc,binary,chunks


def _pad4(payload:bytes,pad:bytes)->bytes:
    while len(payload)%4:
        payload+=pad
    return payload


def _accessor_layout(doc:dict,index:int,expected_type:str|None=None):
    accessors=doc.get("accessors") or []
    views=doc.get("bufferViews") or []
    if not isinstance(index,int) or not (0<=index<len(accessors)):
        raise ValueError(f"invalid accessor index {index}")
    accessor=accessors[index]
    if accessor.get("sparse") is not None:
        raise ValueError(f"sparse accessor unsupported: {index}")
    if expected_type and accessor.get("type")!=expected_type:
        raise ValueError(
            f"accessor {index} type {accessor.get('type')} != {expected_type}"
        )
    view_index=accessor.get("bufferView")
    if not isinstance(view_index,int) or not (0<=view_index<len(views)):
        raise ValueError(f"accessor {index} missing valid bufferView")
    view=views[view_index]
    if int(view.get("buffer") or 0)!=0:
        raise ValueError("GLB patcher supports embedded buffer 0 only")
    component=int(accessor.get("componentType") or 0)
    widths={
        5120:1,5121:1,5122:2,5123:2,5125:4,5126:4,
    }
    dimensions={
        "SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,
        "MAT2":4,"MAT3":9,"MAT4":16,
    }
    if component not in widths:
        raise ValueError(f"unsupported component type {component}")
    dims=dimensions.get(str(accessor.get("type")))
    if dims is None:
        raise ValueError(f"unsupported accessor type {accessor.get('type')}")
    packed=widths[component]*dims
    stride=int(view.get("byteStride") or packed)
    if stride<packed:
        raise ValueError("invalid accessor stride")
    base=int(view.get("byteOffset") or 0)+int(accessor.get("byteOffset") or 0)
    return accessor,view,component,dims,packed,stride,base


def read_position_accessor(path:Path,index:int)->list[tuple[float,float,float]]:
    doc,binary,_=_doc_and_bin(path)
    accessor,_,component,dims,packed,stride,base=_accessor_layout(
        doc,index,"VEC3"
    )
    if component!=5126 or dims!=3:
        raise ValueError("POSITION patching requires float32 VEC3")
    rows=[]
    for row in range(int(accessor.get("count") or 0)):
        pos=base+row*stride
        if pos+packed>len(binary):
            raise ValueError("POSITION accessor reads past BIN chunk")
        rows.append(struct.unpack_from("<3f",binary,pos))
    return rows


def mesh_position_accessors(
    doc:dict,
    *,
    skinned_only:bool=False,
)->list[int]:
    meshes=doc.get("meshes") or []
    selected=set()
    skinned_meshes=set()
    if skinned_only:
        for node in doc.get("nodes") or []:
            mesh=node.get("mesh")
            skin=node.get("skin")
            if isinstance(mesh,int) and isinstance(skin,int):
                skinned_meshes.add(mesh)
    else:
        skinned_meshes=set(range(len(meshes)))

    for mesh_index in sorted(skinned_meshes):
        if not (0<=mesh_index<len(meshes)):
            continue
        for primitive in meshes[mesh_index].get("primitives") or []:
            if "KHR_draco_mesh_compression" in (primitive.get("extensions") or {}):
                raise ValueError("Draco POSITION patching is not supported")
            position=(primitive.get("attributes") or {}).get("POSITION")
            if isinstance(position,int):
                selected.add(position)
    return sorted(selected)


def mesh_nodes_identity_for_accessors(doc:dict,accessors:Iterable[int])->bool:
    targets=set(accessors)
    meshes=doc.get("meshes") or []
    target_meshes=set()
    for mesh_index,mesh in enumerate(meshes):
        for primitive in mesh.get("primitives") or []:
            if (primitive.get("attributes") or {}).get("POSITION") in targets:
                target_meshes.add(mesh_index)
                break

    def close(values,target):
        return len(values)==len(target) and all(
            abs(float(a)-float(b))<=1e-7
            for a,b in zip(values,target)
        )

    identity_matrix=[
        1,0,0,0,
        0,1,0,0,
        0,0,1,0,
        0,0,0,1,
    ]
    for node in doc.get("nodes") or []:
        if node.get("mesh") not in target_meshes:
            continue
        if "matrix" in node and not close(node["matrix"],identity_matrix):
            return False
        if "translation" in node and not close(node["translation"],[0,0,0]):
            return False
        if "rotation" in node and not close(node["rotation"],[0,0,0,1]):
            return False
        if "scale" in node and not close(node["scale"],[1,1,1]):
            return False
    return True


def _raw_accessor_elements(doc:dict,binary:bytes,index:int)->bytes:
    accessor,_,_,_,packed,stride,base=_accessor_layout(doc,index)
    chunks=[]
    for row in range(int(accessor.get("count") or 0)):
        pos=base+row*stride
        if pos+packed>len(binary):
            raise ValueError(f"accessor {index} reads past BIN chunk")
        chunks.append(binary[pos:pos+packed])
    return b"".join(chunks)


def skin_payload_signature(path:Path)->str:
    doc,binary,_=_doc_and_bin(path)
    indices=[]
    for mesh in doc.get("meshes") or []:
        for primitive in mesh.get("primitives") or []:
            attrs=primitive.get("attributes") or {}
            for name,index in attrs.items():
                if (
                    isinstance(index,int)
                    and (
                        str(name).startswith("JOINTS_")
                        or str(name).startswith("WEIGHTS_")
                    )
                ):
                    indices.append((str(name),index))
    digest=hashlib.sha256()
    for name,index in sorted(indices,key=lambda x:(x[0],x[1])):
        digest.update(name.encode())
        digest.update(struct.pack("<I",index))
        digest.update(_raw_accessor_elements(doc,binary,index))
    return digest.hexdigest()


def runtime_payload_signature(path:Path)->str:
    """Hash runtime-critical GLB payload while excluding material/texture/POSITION.

    This deliberately demands byte-stable skinning, animations and morph
    deltas for topology-preserving appearance edits. POSITION is excluded so
    seam-aware head-wrap can legally deform the base while keeping runtime
    payload unchanged.
    """
    doc,binary,_=_doc_and_bin(path)
    digest=hashlib.sha256()

    def add_json(tag:str,value)->None:
        digest.update(tag.encode("utf-8"))
        digest.update(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",",":"),
            ).encode("utf-8")
        )

    def add_accessor(tag:str,index)->None:
        if index is None:
            add_json(tag,None)
            return
        if not isinstance(index,int):
            raise ValueError(f"{tag} accessor is not an integer: {index}")
        accessors=doc.get("accessors") or []
        if not (0<=index<len(accessors)):
            raise ValueError(f"{tag} invalid accessor: {index}")
        accessor=accessors[index]
        add_json(tag+":meta",{
            "componentType":accessor.get("componentType"),
            "count":accessor.get("count"),
            "type":accessor.get("type"),
            "normalized":bool(accessor.get("normalized",False)),
        })
        digest.update(_raw_accessor_elements(doc,binary,index))

    meshes=doc.get("meshes") or []
    for mesh_index,mesh in enumerate(meshes):
        add_json(
            f"mesh:{mesh_index}:weights",
            mesh.get("weights"),
        )
        for primitive_index,primitive in enumerate(mesh.get("primitives") or []):
            attrs=primitive.get("attributes") or {}
            for semantic,index in sorted(attrs.items()):
                if (
                    str(semantic).startswith("JOINTS_")
                    or str(semantic).startswith("WEIGHTS_")
                ):
                    add_accessor(
                        f"mesh:{mesh_index}:primitive:{primitive_index}:"
                        f"attr:{semantic}",
                        index,
                    )
            for target_index,target in enumerate(primitive.get("targets") or []):
                for semantic,index in sorted((target or {}).items()):
                    add_accessor(
                        f"mesh:{mesh_index}:primitive:{primitive_index}:"
                        f"target:{target_index}:{semantic}",
                        index,
                    )

    nodes=doc.get("nodes") or []
    node_runtime=[]
    for node in nodes:
        node_runtime.append({
            "mesh":node.get("mesh"),
            "skin":node.get("skin"),
            "children":node.get("children"),
            "matrix":node.get("matrix"),
            "translation":node.get("translation"),
            "rotation":node.get("rotation"),
            "scale":node.get("scale"),
            "weights":node.get("weights"),
        })
    add_json("nodes",node_runtime)

    for skin_index,skin in enumerate(doc.get("skins") or []):
        add_json(f"skin:{skin_index}:joints",skin.get("joints") or [])
        add_json(f"skin:{skin_index}:skeleton",skin.get("skeleton"))
        add_accessor(
            f"skin:{skin_index}:inverseBindMatrices",
            skin.get("inverseBindMatrices"),
        )

    for animation_index,animation in enumerate(doc.get("animations") or []):
        add_json(
            f"animation:{animation_index}:channels",
            animation.get("channels") or [],
        )
        for sampler_index,sampler in enumerate(animation.get("samplers") or []):
            add_json(
                f"animation:{animation_index}:sampler:{sampler_index}:interpolation",
                sampler.get("interpolation","LINEAR"),
            )
            add_accessor(
                f"animation:{animation_index}:sampler:{sampler_index}:input",
                sampler.get("input"),
            )
            add_accessor(
                f"animation:{animation_index}:sampler:{sampler_index}:output",
                sampler.get("output"),
            )

    return digest.hexdigest()


def patch_position_accessors(
    source_glb:Path,
    output_glb:Path,
    replacements:dict[int,Iterable[Iterable[float]]],
)->PositionPatchResult:
    before_signature=""
    runtime_before=""
    runtime_after=""
    try:
        doc,binary,chunks=_doc_and_bin(source_glb)
        before_signature=skin_payload_signature(source_glb)
        runtime_before=runtime_payload_signature(source_glb)
        patched=bytearray(binary)
        patched_vertices=0

        for index,rows_raw in sorted(replacements.items()):
            rows=[tuple(float(x) for x in row) for row in rows_raw]
            accessor,_,component,dims,packed,stride,base=_accessor_layout(
                doc,index,"VEC3"
            )
            if component!=5126 or dims!=3:
                raise ValueError(
                    f"POSITION accessor {index} must be float32 VEC3"
                )
            count=int(accessor.get("count") or 0)
            if len(rows)!=count:
                raise ValueError(
                    f"POSITION replacement count mismatch {index}: "
                    f"{len(rows)} != {count}"
                )
            finite_rows=[]
            for row_index,row in enumerate(rows):
                if len(row)!=3 or not all(math.isfinite(x) for x in row):
                    raise ValueError(
                        f"non-finite POSITION replacement {index}:{row_index}"
                    )
                pos=base+row_index*stride
                if pos+packed>len(patched):
                    raise ValueError("POSITION patch writes past BIN chunk")
                struct.pack_into("<3f",patched,pos,*row)
                finite_rows.append(row)
            accessor["min"]=[
                min(row[axis] for row in finite_rows)
                for axis in range(3)
            ]
            accessor["max"]=[
                max(row[axis] for row in finite_rows)
                for axis in range(3)
            ]
            patched_vertices+=count

        raw_json=_pad4(
            json.dumps(doc,separators=(",",":")).encode("utf-8"),
            b" ",
        )
        raw_bin=_pad4(bytes(patched),b"\x00")
        rebuilt=[]
        json_done=False
        bin_done=False
        for kind,payload in chunks:
            if kind==JSON_CHUNK and not json_done:
                rebuilt.append((kind,raw_json))
                json_done=True
            elif kind==BIN_CHUNK and not bin_done:
                rebuilt.append((kind,raw_bin))
                bin_done=True
            else:
                rebuilt.append((kind,payload))
        if not json_done or not bin_done:
            raise ValueError("GLB is missing JSON or BIN chunk")

        total=12+sum(8+len(payload) for _,payload in rebuilt)
        output=bytearray(b"glTF")
        output.extend(struct.pack("<II",2,total))
        for kind,payload in rebuilt:
            output.extend(struct.pack("<II",len(payload),kind))
            output.extend(payload)
        output_glb.parent.mkdir(parents=True,exist_ok=True)
        output_glb.write_bytes(bytes(output))

        after_signature=skin_payload_signature(output_glb)
        preserved=before_signature==after_signature
        if not preserved:
            raise RuntimeError("JOINTS/WEIGHTS payload changed during POSITION patch")
        runtime_after=runtime_payload_signature(output_glb)
        runtime_preserved=runtime_before==runtime_after
        if not runtime_preserved:
            raise RuntimeError(
                "runtime payload changed during POSITION patch "
                "(skin/animation/morph)"
            )
        return PositionPatchResult(
            source_glb=str(source_glb),
            output_glb=str(output_glb),
            patched_accessors=sorted(replacements),
            patched_vertices=patched_vertices,
            skin_signature_before=before_signature,
            skin_signature_after=after_signature,
            skin_payload_preserved=True,
            runtime_signature_before=runtime_before,
            runtime_signature_after=runtime_after,
            runtime_payload_preserved=True,
            ready=True,
        )
    except Exception as exc:
        return PositionPatchResult(
            source_glb=str(source_glb),
            output_glb=str(output_glb),
            patched_accessors=sorted(replacements),
            patched_vertices=0,
            skin_signature_before=before_signature,
            skin_signature_after="",
            skin_payload_preserved=False,
            runtime_signature_before=runtime_before,
            runtime_signature_after=runtime_after,
            runtime_payload_preserved=False,
            ready=False,
            error=f"{type(exc).__name__}:{exc}",
        )


def main()->int:
    import argparse
    parser=argparse.ArgumentParser(
        description="Patch GLB POSITION accessors without touching skin payloads."
    )
    parser.add_argument("glb",type=Path)
    parser.add_argument("--list",action="store_true")
    args=parser.parse_args()
    doc,_,_=_doc_and_bin(args.glb)
    accessors=mesh_position_accessors(doc,skinned_only=False)
    print(json.dumps({
        "position_accessors":accessors,
        "identity_nodes":mesh_nodes_identity_for_accessors(doc,accessors),
        "skin_signature":skin_payload_signature(args.glb),
    },indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())

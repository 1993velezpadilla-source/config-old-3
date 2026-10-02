#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import struct
from pathlib import Path

JSON_CHUNK=0x4E4F534A
BIN_CHUNK=0x004E4942


def read_glb(path:Path)->tuple[dict,bytes]:
    data=path.read_bytes()
    if len(data)<20 or data[:4]!=b"glTF":
        raise ValueError("not a GLB")
    _,version,total=struct.unpack_from("<4sII",data,0)
    if version!=2 or total!=len(data):
        raise ValueError("invalid GLB header")
    offset=12
    doc=None
    bin_blob=b""
    while offset+8<=total:
        length,kind=struct.unpack_from("<II",data,offset)
        offset+=8
        payload=data[offset:offset+length]
        offset+=length
        if kind==JSON_CHUNK:
            doc=json.loads(payload.decode("utf-8").rstrip("\x00 \t\r\n"))
        elif kind==BIN_CHUNK:
            bin_blob=payload
    if doc is None:
        raise ValueError("missing JSON chunk")
    return doc,bin_blob


def write_glb(path:Path,doc:dict,bin_blob:bytes)->None:
    doc=copy.deepcopy(doc)
    buffers=doc.setdefault("buffers",[])
    if buffers:
        buffers[0]["byteLength"]=len(bin_blob)
    elif bin_blob:
        buffers.append({"byteLength":len(bin_blob)})

    json_bytes=json.dumps(
        doc,
        ensure_ascii=False,
        separators=(",",":"),
    ).encode("utf-8")
    json_pad=(-len(json_bytes))%4
    json_payload=json_bytes+b" "*json_pad

    bin_pad=(-len(bin_blob))%4
    bin_payload=bin_blob+b"\x00"*bin_pad

    chunks=[
        struct.pack("<II",len(json_payload),JSON_CHUNK)+json_payload,
    ]
    if bin_payload:
        chunks.append(struct.pack("<II",len(bin_payload),BIN_CHUNK)+bin_payload)
    total=12+sum(len(x) for x in chunks)
    payload=struct.pack("<4sII",b"glTF",2,total)+b"".join(chunks)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(payload)


def replace_embedded_images(
    input_glb:Path,
    output_glb:Path,
    replacements:dict[int,tuple[str,bytes]],
)->dict:
    """Append replacement image payloads without moving any existing bufferView.

    Geometry, skins, animation buffers and the original image bytes retain their
    offsets. Only selected image objects are repointed to newly appended views.
    """
    doc,bin_blob=read_glb(input_glb)
    images=doc.get("images") or []
    views=doc.setdefault("bufferViews",[])
    if not isinstance(images,list):
        raise ValueError("invalid images table")

    rewritten=[]
    out=bytearray(bin_blob)
    for image_index in sorted(replacements):
        if not (0<=int(image_index)<len(images)):
            raise IndexError(f"image index out of range: {image_index}")
        mime,payload=replacements[image_index]
        if not payload:
            raise ValueError(f"empty replacement image: {image_index}")
        image=images[image_index]
        if not isinstance(image,dict):
            raise ValueError(f"invalid image entry: {image_index}")
        old_view=image.get("bufferView")
        if not isinstance(old_view,int):
            raise ValueError(f"image is not embedded: {image_index}")

        while len(out)%4:
            out.append(0)
        byte_offset=len(out)
        out.extend(payload)
        new_view_index=len(views)
        views.append({
            "buffer":0,
            "byteOffset":byte_offset,
            "byteLength":len(payload),
        })
        image["bufferView"]=new_view_index
        image["mimeType"]=str(mime)
        image.pop("uri",None)
        rewritten.append({
            "image_index":int(image_index),
            "old_buffer_view":old_view,
            "new_buffer_view":new_view_index,
            "byte_offset":byte_offset,
            "byte_length":len(payload),
            "mime_type":str(mime),
        })

    write_glb(output_glb,doc,bytes(out))
    return {
        "input":str(input_glb),
        "output":str(output_glb),
        "rewritten":rewritten,
        "appended_bytes":len(out)-len(bin_blob),
    }

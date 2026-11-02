#!/usr/bin/env python3
"""Convert local user-owned CoD4 IWD/IWI material to optional Vril IWVT RGBA.

Prototype: one base-color texture per gun (not full original materials).
Never publishes original material or model bytes.
"""
from __future__ import annotations
from pathlib import Path
import argparse,hashlib,struct,subprocess,tempfile,zipfile
from PIL import Image
from iw3_glb_to_iwvm import load_glb


def first_color_iwi(glb:Path) -> str:
    d,_=load_glb(glb)
    for mat in d.get("materials",[]):
        color=(mat.get("pbrMetallicRoughness") or {}).get("baseColorTexture")
        if color is None:continue
        tex_idx=color.get("index")
        textures=d.get("textures",[])
        if not isinstance(tex_idx,int) or not 0<=tex_idx<len(textures):continue
        image_idx=textures[tex_idx].get("source")
        images=d.get("images",[])
        if not isinstance(image_idx,int) or not 0<=image_idx<len(images):continue
        uri=images[image_idx].get("uri","")
        if isinstance(uri,str) and uri.lower().endswith(".dds"):
            name=Path(uri).name
            if not name or len(name)>150:raise ValueError("Bad original baseColor filename")
            return "images/"+name[:-4].lower()+".iwi"
    raise ValueError("No original CoD4 glTF base-color reference")


def iwvt_from_dds(path:Path) -> bytes:
    with Image.open(path) as src:
        if src.width<1 or src.height<1 or src.width>4096 or src.height>4096:
            raise ValueError("Original texture dimension exceeds GLES upload limit")
        rgba=src.convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        data=rgba.tobytes()
        return struct.pack("<4sIII",b"IWVT",1,rgba.width,rgba.height)+data


def convert_private(glb:Path,iwds:list[Path],converter:Path,archive:Path,viewmodel:str):
    if not (viewmodel.startswith("v_") and len(viewmodel)<70 and
            all(c.isalnum() or c=="_" for c in viewmodel)):
        raise ValueError("Unsafe viewmodel target")
    if not converter.is_file():raise FileNotFoundError("Missing OAT ImageConverter")
    wanted=first_color_iwi(glb)
    material_count=len(load_glb(glb)[0].get("materials",[]))
    with tempfile.TemporaryDirectory(prefix="iw3-private-material-") as tmp:
        source=Path(tmp)/Path(wanted).name
        for archive_iwd in iwds:
            with zipfile.ZipFile(archive_iwd) as z:
                members={k.filename.lower().replace("\\","/"):k for k in z.infolist()}
                if wanted not in members:continue
                info=members[wanted]
                if info.file_size<12 or info.file_size>64*1024*1024:
                    raise ValueError("Suspicious original IWI file size")
                source.write_bytes(z.read(info))
                break
        if not source.is_file():raise FileNotFoundError("Original texture missing from supplied IWD archives")
        result=subprocess.run([str(converter.resolve()),str(source)],cwd=tmp,
                              capture_output=True,check=False,timeout=90)
        dds=source.with_suffix(".dds")
        if result.returncode or not dds.is_file():
            raise ValueError("Original IWI converter did not write decoded DDS")
        encoded=iwvt_from_dds(dds)
    target=f"nzp/models/iw3/{viewmodel}.iwvt"
    with zipfile.ZipFile(archive,"a",compression=zipfile.ZIP_DEFLATED) as z:
        if target in z.namelist():raise ValueError("Refusing to override existing material")
        z.writestr(target,encoded)
    archive.with_suffix(".version").write_text(
        hashlib.sha256(archive.read_bytes()).hexdigest()+"\n",encoding="ascii")
    return dict(texture_pixels=(len(encoded)-16)//4,texture_bytes=len(encoded),
                original_glb_materials=material_count,
                exact_multimaterial_model_supported=False,
                original_image_bytes_published=False,texture_entry=target)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--glb",type=Path,required=True)
    p.add_argument("--iwd-dir",type=Path,required=True)
    p.add_argument("--oat-image-converter",type=Path,required=True)
    p.add_argument("--nzp-data",type=Path,required=True)
    p.add_argument("--viewmodel",required=True)
    a=p.parse_args()
    print(convert_private(a.glb,sorted(a.iwd_dir.rglob("*.iwd")),
                          a.oat_image_converter,a.nzp_data,a.viewmodel))

#!/usr/bin/env python3
"""Inject ONLY synthetic cube triangles to prove real GLES first-person dispatch.

No Activision data is loaded, copied or shipped by this probe.
The original v0.26 branch and package ID are never changed.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import struct
import zipfile

MODEL="nzp/models/iw3/v_colt.iwvm"
TEXTURE="nzp/models/iw3/v_colt.iwvt"



def cube():
    """Small color-grid test prism in the LOWER-RIGHT first-person view.

    Previously 7..12 forward, +/-2 across/height: a giant white/red
    rectangle blocked the player's entire aim reticle. This mesh is a
    **diagnostic shape**, never a replacement for genuine COD4 guns.
    Quake local axes: +X forward, +Y left, +Z up.
    """
    corner={
        "near_low_right": (12.0,-4.0,-3.5),
        "near_low_left": (12.0,-2.6,-3.5),
        "near_up_right": (12.0,-4.0,-2.7),
        "near_up_left": (12.0,-2.6,-2.7),
        "far_low_right": (19.0,-4.0,-3.5),
        "far_low_left": (19.0,-2.6,-3.5),
        "far_up_right": (19.0,-4.0,-2.7),
        "far_up_left": (19.0,-2.6,-2.7),
    }
    # Separate UVs per face and orientation; intentional 24 vertices
    # ensures the GLES texture-array path is exercised, not solid color.
    faces=[
        ("near_low_right","near_low_left","near_up_left","near_up_right"),
        ("far_low_left","far_low_right","far_up_right","far_up_left"),
        ("near_low_left","far_low_left","far_up_left","near_up_left"),
        ("far_low_right","near_low_right","near_up_right","far_up_right"),
        ("near_up_right","near_up_left","far_up_left","far_up_right"),
        ("far_low_right","far_low_left","near_low_left","near_low_right"),
    ]
    uv=((0.0,0.0),(1.0,0.0),(1.0,1.0),(0.0,1.0))
    vertices=[]
    indices=[]
    for face in faces:
        start=len(vertices)
        vertices.extend((*corner[name],*tex) for name,tex in zip(face,uv))
        indices.extend(start+i for i in (0,1,2,0,2,3))
    packed=b"".join(struct.pack("<5f",*v) for v in vertices)
    face_data=struct.pack("<"+"H"*len(indices),*indices)
    return struct.pack("<4sIII",b"IWVM",1,len(vertices),len(indices))+packed+face_data


def synthetic_rgba():
    # Four synthetic texels, not original Call of Duty image data.
    return (struct.pack("<4sIII",b"IWVT",1,2,2)
            +bytes([230,30,70,255,  245,245,245,255,
                    50,150,230,255,  50,50,50,255]))


def inject(package:Path):
    if not package.is_file():raise FileNotFoundError(package)
    with zipfile.ZipFile(package,"a",compression=zipfile.ZIP_DEFLATED) as z:
        assert "nzp/progs.dat" in z.namelist(), "Missing real NZP gamedir"
        if MODEL in z.namelist() or TEXTURE in z.namelist():
            raise RuntimeError("Synthetic probe target already present")
        z.writestr(MODEL,cube())
        z.writestr(TEXTURE,synthetic_rgba())
    digest=hashlib.sha256(package.read_bytes()).hexdigest()
    package.with_suffix(".version").write_text(digest+"\n",encoding="ascii")
    with zipfile.ZipFile(package) as z:
        assert z.read(MODEL)==cube()
        assert z.read(TEXTURE)==synthetic_rgba()
    return digest


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("game_data_zip",type=Path)
    args=ap.parse_args()
    digest=inject(args.game_data_zip)
    print(f"SYNTHETIC reduced lower-right IWVM test prism mounted under NZP gamedir; data version SHA256 {digest}")

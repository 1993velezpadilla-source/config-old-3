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


def cube():
    # Front of camera; Quake coords X forward, Z up.
    points = [
      (7.,-2.,-2.),(12.,-2.,-2.),(12.,2.,-2.),(7.,2.,-2.),
      (7.,-2.,2.),(12.,-2.,2.),(12.,2.,2.),(7.,2.,2.),
    ]
    faces = [
      (0,1,2),(0,2,3), (4,6,5),(4,7,6),
      (0,4,5),(0,5,1), (1,5,6),(1,6,2),
      (2,6,7),(2,7,3), (3,7,4),(3,4,0),
    ]
    vertices = b"".join(struct.pack("<5f",*p,0.,0.) for p in points)
    idx = b"".join(struct.pack("<3H",*f) for f in faces)
    return struct.pack("<4sIII",b"IWVM",1,len(points),len(faces)*3)+vertices+idx


def inject(package:Path):
    if not package.is_file():raise FileNotFoundError(package)
    with zipfile.ZipFile(package,"a",compression=zipfile.ZIP_DEFLATED) as z:
        assert "nzp/progs.dat" in z.namelist(), "Missing real NZP gamedir"
        if MODEL in z.namelist():raise RuntimeError("Probe target already present")
        z.writestr(MODEL,cube())
    digest=hashlib.sha256(package.read_bytes()).hexdigest()
    package.with_suffix(".version").write_text(digest+"\n",encoding="ascii")
    with zipfile.ZipFile(package) as z:
        assert z.read(MODEL)==cube()
    return digest


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("game_data_zip",type=Path)
    args=ap.parse_args()
    digest=inject(args.game_data_zip)
    print(f"SYNTHETIC IWVM cube mounted under NZP gamedir; data version SHA256 {digest}")

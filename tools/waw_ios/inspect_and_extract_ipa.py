#!/usr/bin/env python3
"""Analyze and extract ORIGINAL Marmalade/iOS World at War Zombies IPA.

Read-only original IPA input. Does NOT claim to convert iOS ARMv6 Mach-O
to an Android ARM64 ELF or provide a playable APK.
No protected game assets are committed to GitHub.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import lzma
import plistlib
import struct
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

def parse_macho(binary: bytes, target: Path) -> dict:
    if binary[:4] != bytes.fromhex("cefaedfe"):
        raise ValueError("Expected thin little-endian Mach-O ARMv6")
    _, cpu, subcpu, filetype, ncmds, sizeofcmds, _ = struct.unpack_from("<7I",binary,0)
    if cpu != 12:
        raise ValueError(f"Unexpected CPU type: {cpu}")
    target.mkdir(parents=True,exist_ok=True)
    (target/"kiwi.original.MachO.armv6").write_bytes(binary)
    p=28
    sections=[]
    cryptid=None
    for _ in range(ncmds):
        cmd,size=struct.unpack_from("<II",binary,p)
        if cmd==1:
            nsects=struct.unpack_from("<I",binary,p+48)[0]
            for idx in range(nsects):
                i=p+56+68*idx
                name,segment,addr,length,offset,alignment=struct.unpack_from("<16s16sIIII",binary,i)
                name=name.rstrip(b"\0").decode("ascii","replace")
                if name not in ("s3e_code","s3e_data"):
                    continue
                raw=binary[offset:offset+length]
                (target/(name+".ARMv6.bin")).write_bytes(raw)
                sections.append(dict(name=name,address=hex(addr),length=length,
                                     file_offset=offset,sha256=hashlib.sha256(raw).hexdigest()))
        if cmd==0x21:cryptid=struct.unpack_from("<I",binary,p+16)[0]
        p+=size
    assert p==28+sizeofcmds
    return dict(platform="iOS",container="Mach-O",cpu="ARMv6 32-bit",
                encryption_id=cryptid,sections=sections)

def unpack_dz(b: bytes) -> list:
    if b[:4]!=b"DTRZ":raise ValueError("Expected Marmalade DTRZ")
    n,dirs=struct.unpack_from("<HH",b,4)
    p=9
    def read_name():
        nonlocal p
        end=b.index(0,p)
        name=b[p:end].decode("utf8","replace")
        p=end+1
        return name
    files=[read_name() for _ in range(n)]
    foldernames=[read_name().replace("\\","/") for _ in range(dirs-1)]
    attrs=[struct.unpack_from("<HHH",b,p+i*6) for i in range(n)]
    p+=6*n
    fmt,nloc=struct.unpack_from("<HH",b,p)
    p+=4
    if nloc!=n:raise ValueError("Unexpected DZ location count")
    locations=[struct.unpack_from("<IIII",b,p+i*16) for i in range(n)]
    out=[]
    for i,(start,size_a,size_b,method) in enumerate(locations):
        folderidx=attrs[i][0]
        folder=foldernames[folderidx-1] if folderidx else ""
        rel=PurePosixPath(folder)/files[i]
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Unsafe embedded filename")
        following=[loc[0] for loc in locations if loc[0]>start]
        end=min(following) if following else len(b)
        if not 0<=start<end<=len(b):raise ValueError("Invalid offsets")
        part=b[start:end]
        if method==0x200:
            decoder=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
            data=decoder.decompress(part)
            if not decoder.eof:raise ValueError("Truncated LZMA")
        elif method==0x100:
            data=part[:size_a]
        else:
            raise ValueError(f"Unsupported DZ compression method {method:#x}")
        if len(data) not in (size_a,size_b):
            raise ValueError(f"Unexpected size for {rel}")
        out.append((rel,data))
    return out

def run(ipa:Path,out:Path)->None:
    out.mkdir(parents=True,exist_ok=True)
    report=dict(input_name=ipa.name,sha256=hashlib.sha256(ipa.read_bytes()).hexdigest(),archives=[])
    with ZipFile(ipa) as z:
        meta=plistlib.loads(z.read("Payload/kiwi.app/Info.plist"))
        report.update(bundle_id=meta.get("CFBundleIdentifier"),
                      version=meta.get("CFBundleVersion"),
                      minimum_ios=meta.get("MinimumOSVersion"))
        report["binary"]=parse_macho(z.read("Payload/kiwi.app/kiwi"),out/"native")
        for item in z.namelist():
            if not item.endswith(".dz"):continue
            name=PurePosixPath(item).name
            unpacked=unpack_dz(z.read(item))
            manifest=[]
            for rel,data in unpacked:
                target=out/"resources"/name/str(rel)
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
                manifest.append(dict(file=str(rel),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
            report["archives"].append(dict(archive=name,entries=manifest))
    (out/"manifest.json").write_text(json.dumps(report,indent=2),encoding="utf8")
    print(f"Extracted {sum(len(z['entries']) for z in report['archives'])} original Marmalade resources.")
    print("Native iOS ARMv6 binary preserved for reverse engineering; Android port NOT yet built.")

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("ipa",type=Path)
    ap.add_argument("output",type=Path)
    args=ap.parse_args()
    run(args.ipa,args.output)

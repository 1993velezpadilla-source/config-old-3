#!/usr/bin/env python3
"""Inspect a user-owned GTA Chinatown Wars Android ARM64 libGame.so.

The tool is intentionally dependency-free so CI can validate the parser
without bundling any Rockstar binary.  It fingerprints the ELF, enumerates
dynamic/static symbols when present, extracts the GNU build-id, and groups
symbols/strings useful for the 3D camera + streaming investigation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

ELF_MAGIC = b"\x7fELF"
ELFCLASS64 = 2
ELFDATA2LSB = 1
EM_AARCH64 = 183
SHT_SYMTAB = 2
SHT_STRTAB = 3
SHT_DYNSYM = 11

ELF64_EHDR = struct.Struct("<16sHHIQQQIHHHHHH")
ELF64_SHDR = struct.Struct("<IIQQQQIIQQ")
ELF64_SYM = struct.Struct("<IBBHQQ")

KNOWN_JNI_EXPORTS = (
    "Java_com_rockstargames_oswrapper_GameNative_implOnActivityCreated",
    "Java_com_rockstargames_oswrapper_GameNative_implOnInitialSetup",
    "Java_com_rockstargames_oswrapper_GameNative_implOnSurfaceCreated",
    "Java_com_rockstargames_oswrapper_GameNative_implOnSurfaceChanged",
    "Java_com_rockstargames_oswrapper_GameNative_implOnDrawFrame",
    "Java_com_rockstargames_oswrapper_GameNative_implOnGameResume",
    "Java_com_rockstargames_oswrapper_GameNative_implOnGamePause",
    "Java_com_rockstargames_oswrapper_GameNative_implOnGamepadAxesChanged",
    "Java_com_rockstargames_oswrapper_GameNative_implOnTouchStart",
    "Java_com_rockstargames_oswrapper_GameNative_implOnTouchMove",
    "Java_com_rockstargames_oswrapper_GameNative_implOnTouchEnd",
)

CANDIDATE_TERMS = {
    "camera": (
        "camera", "cam", "view", "fov", "nearclip", "farclip",
        "projection", "perspective", "matproj", "matmodelview",
    ),
    "streaming": (
        "stream", "sector", "worldblock", "world_block", "resident",
        "streamradius", "stream_radius",
    ),
    "lod_culling": (
        "lod", "cull", "frustum", "visibility", "visible", "distance",
        "drawdistance", "draw_distance", "culldistance", "cull_distance",
        "fade_distance", "fadedistance",
    ),
    "player_render": (
        "ped", "player", "skin", "skeleton", "body", "weapon",
        "character", "modelrender", "model_render",
    ),
}


def cstr(blob: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(blob):
        return ""
    end = blob.find(b"\0", offset)
    if end < 0:
        end = len(blob)
    return blob[offset:end].decode("utf-8", "replace")


def ascii_strings(blob: bytes, min_len: int = 5):
    pattern = rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}"
    for m in re.finditer(pattern, blob):
        yield m.start(), m.group().decode("ascii", "replace")


def parse_note_build_id(blob: bytes) -> str | None:
    pos = 0
    while pos + 12 <= len(blob):
        namesz, descsz, ntype = struct.unpack_from("<III", blob, pos)
        pos += 12
        if namesz > len(blob) - pos:
            return None
        name = blob[pos:pos + namesz].rstrip(b"\0")
        pos += (namesz + 3) & ~3
        if descsz > len(blob) - pos:
            return None
        desc = blob[pos:pos + descsz]
        pos += (descsz + 3) & ~3
        if name == b"GNU" and ntype == 3:
            return desc.hex()
    return None


def classify(text: str) -> list[str]:
    low = text.lower()
    out = []
    for category, terms in CANDIDATE_TERMS.items():
        if any(term in low for term in terms):
            out.append(category)
    return out


def inspect_elf(path: Path) -> dict:
    blob = path.read_bytes()
    if len(blob) < ELF64_EHDR.size:
        raise ValueError("file is too small to be an ELF64 shared object")

    hdr = ELF64_EHDR.unpack_from(blob, 0)
    ident = hdr[0]
    if ident[:4] != ELF_MAGIC:
        raise ValueError("not an ELF file")
    if ident[4] != ELFCLASS64:
        raise ValueError(f"expected ELF64, got class={ident[4]}")
    if ident[5] != ELFDATA2LSB:
        raise ValueError("expected little-endian ELF")

    e_type, e_machine = hdr[1], hdr[2]
    e_shoff = hdr[6]
    e_shentsize, e_shnum, e_shstrndx = hdr[11], hdr[12], hdr[13]
    if e_machine != EM_AARCH64:
        raise ValueError(f"expected AArch64 e_machine=183, got {e_machine}")
    if e_shentsize < ELF64_SHDR.size:
        raise ValueError("section header entry is smaller than ELF64_SHDR")
    if e_shnum == 0:
        raise ValueError("ELF has no section headers")
    if e_shoff + e_shentsize * e_shnum > len(blob):
        raise ValueError("section header table lies outside the file")

    shdrs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        shdrs.append(ELF64_SHDR.unpack_from(blob, off))

    if e_shstrndx >= len(shdrs):
        raise ValueError("invalid section-name string table index")
    shstr = shdrs[e_shstrndx]
    shstr_off, shstr_size = shstr[4], shstr[5]
    if shstr_off + shstr_size > len(blob):
        raise ValueError("section-name string table lies outside file")
    shstr_blob = blob[shstr_off:shstr_off + shstr_size]

    sections = []
    section_by_name = {}
    for idx, sh in enumerate(shdrs):
        name = cstr(shstr_blob, sh[0])
        entry = {
            "index": idx,
            "name": name,
            "type": sh[1],
            "addr": sh[3],
            "offset": sh[4],
            "size": sh[5],
            "link": sh[6],
            "entsize": sh[9],
        }
        sections.append(entry)
        if name:
            section_by_name[name] = entry

    symbols = []
    seen = set()
    for sec in sections:
        if sec["type"] not in (SHT_DYNSYM, SHT_SYMTAB):
            continue
        if sec["link"] >= len(sections):
            continue
        strsec = sections[sec["link"]]
        if strsec["type"] != SHT_STRTAB:
            continue
        so, ss = sec["offset"], sec["size"]
        st_off, st_size = strsec["offset"], strsec["size"]
        if so + ss > len(blob) or st_off + st_size > len(blob):
            continue
        strtab = blob[st_off:st_off + st_size]
        entsize = sec["entsize"] or ELF64_SYM.size
        if entsize < ELF64_SYM.size:
            continue
        count = ss // entsize
        for i in range(count):
            ent_off = so + i * entsize
            st_name, st_info, st_other, st_shndx, st_value, st_size = ELF64_SYM.unpack_from(blob, ent_off)
            name = cstr(strtab, st_name)
            if not name or name in seen:
                continue
            seen.add(name)
            symbols.append({
                "name": name,
                "value": st_value,
                "size": st_size,
                "bind": st_info >> 4,
                "type": st_info & 0xF,
                "section_index": st_shndx,
            })

    build_id = None
    for sec in sections:
        if sec["name"] == ".note.gnu.build-id":
            start, size = sec["offset"], sec["size"]
            if start + size <= len(blob):
                build_id = parse_note_build_id(blob[start:start + size])
            break

    text = section_by_name.get(".text")
    text_sha256 = None
    text_size = 0
    if text and text["offset"] + text["size"] <= len(blob):
        text_blob = blob[text["offset"]:text["offset"] + text["size"]]
        text_sha256 = hashlib.sha256(text_blob).hexdigest()
        text_size = len(text_blob)

    sym_by_name = {s["name"]: s for s in symbols}
    known_jni = {name: (name in sym_by_name) for name in KNOWN_JNI_EXPORTS}
    known_jni_details = {
        name: (
            {
                "present": True,
                "value": sym_by_name[name]["value"],
                "size": sym_by_name[name]["size"],
            }
            if name in sym_by_name
            else {"present": False, "value": None, "size": None}
        )
        for name in KNOWN_JNI_EXPORTS
    }

    candidates = {key: [] for key in CANDIDATE_TERMS}
    for sym in symbols:
        cats = classify(sym["name"])
        for cat in cats:
            candidates[cat].append({
                "source": "symbol",
                "name": sym["name"],
                "value": sym["value"],
                "size": sym["size"],
            })

    string_candidates = {key: [] for key in CANDIDATE_TERMS}
    for offset, s in ascii_strings(blob):
        cats = classify(s)
        if not cats:
            continue
        if len(s) > 180:
            s = s[:177] + "..."
        for cat in cats:
            bucket = string_candidates[cat]
            if len(bucket) < 200:
                bucket.append({"offset": offset, "text": s})

    return {
        "path": str(path),
        "file_size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "elf": {
            "class": 64,
            "little_endian": True,
            "e_type": e_type,
            "machine": "AArch64",
            "machine_id": e_machine,
            "section_count": e_shnum,
            "build_id": build_id,
        },
        "text": {
            "size": text_size,
            "sha256": text_sha256,
        },
        "symbols": {
            "count": len(symbols),
            "known_jni": known_jni,
            "known_jni_details": known_jni_details,
            "known_jni_present": sum(1 for x in known_jni.values() if x),
            "candidate_groups": candidates,
        },
        "strings": {
            "candidate_groups": string_candidates,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path, help="Path to libGame.so from a user-owned CTW APK")
    ap.add_argument("--out", type=Path, help="Write the JSON report to this path")
    ap.add_argument(
        "--require-jni",
        action="store_true",
        help="Fail unless all known GameNative JNI exports are present",
    )
    args = ap.parse_args()

    try:
        report = inspect_elf(args.libgame)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    report["ok"] = True
    if args.require_jni:
        missing = [k for k, v in report["symbols"]["known_jni"].items() if not v]
        report["missing_known_jni"] = missing
        report["ok"] = not missing

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

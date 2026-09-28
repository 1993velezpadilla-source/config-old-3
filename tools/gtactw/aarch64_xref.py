#!/usr/bin/env python3
"""AArch64 static xref scanner for a user-owned CTW Android libGame.so.

Finds literal-address construction patterns (ADRP + ADD immediate) in .text
that resolve into strings related to camera, streaming, LOD/culling and player
rendering.  The output is evidence for manual/RVA verification; it does not
patch the binary and does not guess function addresses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

import elf_probe


def sign_extend(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return (value ^ sign) - sign


def decode_adrp(insn: int, pc: int):
    if (insn & 0x9F000000) != 0x90000000:
        return None
    rd = insn & 0x1F
    immlo = (insn >> 29) & 0x3
    immhi = (insn >> 5) & 0x7FFFF
    imm21 = sign_extend((immhi << 2) | immlo, 21)
    target_page = (pc & ~0xFFF) + (imm21 << 12)
    return rd, target_page


def decode_adr(insn: int, pc: int):
    if (insn & 0x9F000000) != 0x10000000:
        return None
    rd = insn & 0x1F
    immlo = (insn >> 29) & 0x3
    immhi = (insn >> 5) & 0x7FFFF
    imm21 = sign_extend((immhi << 2) | immlo, 21)
    return rd, pc + imm21


def decode_add_imm64(insn: int):
    # ADD (immediate), 64-bit, without flags.
    if (insn & 0xFF000000) != 0x91000000:
        return None
    shift = (insn >> 22) & 0x1
    imm12 = (insn >> 10) & 0xFFF
    rn = (insn >> 5) & 0x1F
    rd = insn & 0x1F
    imm = imm12 << (12 if shift else 0)
    return rd, rn, imm


def decode_bl(insn: int, pc: int):
    if (insn & 0xFC000000) != 0x94000000:
        return None
    imm26 = sign_extend(insn & 0x03FFFFFF, 26)
    return pc + (imm26 << 2)


def _read_sections(blob: bytes):
    if len(blob) < elf_probe.ELF64_EHDR.size:
        raise ValueError("file too small")
    hdr = elf_probe.ELF64_EHDR.unpack_from(blob, 0)
    ident = hdr[0]
    if ident[:4] != elf_probe.ELF_MAGIC or ident[4] != elf_probe.ELFCLASS64:
        raise ValueError("expected ELF64")
    if hdr[2] != elf_probe.EM_AARCH64:
        raise ValueError("expected AArch64 ELF")

    e_shoff = hdr[6]
    e_shentsize, e_shnum, e_shstrndx = hdr[11], hdr[12], hdr[13]
    shdrs = [
        elf_probe.ELF64_SHDR.unpack_from(blob, e_shoff + i * e_shentsize)
        for i in range(e_shnum)
    ]
    shstr_hdr = shdrs[e_shstrndx]
    shstr = blob[shstr_hdr[4]:shstr_hdr[4] + shstr_hdr[5]]

    sections = []
    for i, sh in enumerate(shdrs):
        name = elf_probe.cstr(shstr, sh[0])
        sections.append({
            "index": i,
            "name": name,
            "type": sh[1],
            "flags": sh[2],
            "addr": sh[3],
            "offset": sh[4],
            "size": sh[5],
            "link": sh[6],
            "entsize": sh[9],
        })
    return sections


def _symbols(blob: bytes, sections: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for sec in sections:
        if sec["type"] not in (elf_probe.SHT_DYNSYM, elf_probe.SHT_SYMTAB):
            continue
        if sec["link"] >= len(sections):
            continue
        strsec = sections[sec["link"]]
        strtab = blob[strsec["offset"]:strsec["offset"] + strsec["size"]]
        entsize = sec["entsize"] or elf_probe.ELF64_SYM.size
        for pos in range(sec["offset"], sec["offset"] + sec["size"], entsize):
            if pos + elf_probe.ELF64_SYM.size > len(blob):
                break
            st_name, st_info, _, st_shndx, st_value, st_size = elf_probe.ELF64_SYM.unpack_from(blob, pos)
            name = elf_probe.cstr(strtab, st_name)
            if not name or name in seen:
                continue
            seen.add(name)
            if (st_info & 0xF) == 2 and st_value:
                out.append({
                    "name": name,
                    "value": st_value,
                    "size": st_size,
                    "section_index": st_shndx,
                })
    return sorted(out, key=lambda x: x["value"])


def _candidate_strings(blob: bytes, sections: list[dict]) -> list[dict]:
    out = []
    for sec in sections:
        if not sec["size"] or sec["offset"] + sec["size"] > len(blob):
            continue
        # Ignore executable code and symbol tables; scan data/string sections.
        if sec["name"] == ".text" or sec["type"] in (elf_probe.SHT_DYNSYM, elf_probe.SHT_SYMTAB):
            continue
        data = blob[sec["offset"]:sec["offset"] + sec["size"]]
        for rel, text in elf_probe.ascii_strings(data):
            cats = elf_probe.classify(text)
            if not cats:
                continue
            out.append({
                "section": sec["name"],
                "file_offset": sec["offset"] + rel,
                "va": sec["addr"] + rel,
                "text": text[:180],
                "categories": cats,
            })
    return out


def _owner_function(pc: int, symbols: list[dict]):
    best = None
    for sym in symbols:
        if sym["value"] > pc:
            break
        if sym["size"] and pc >= sym["value"] + sym["size"]:
            continue
        best = sym
    if best is None:
        # Stripped/zero-size symbols: use nearest preceding function as a hint.
        preceding = [s for s in symbols if s["value"] <= pc]
        best = preceding[-1] if preceding else None
    return best


def scan_libgame(path: Path) -> dict:
    blob = path.read_bytes()
    sections = _read_sections(blob)
    text = next((s for s in sections if s["name"] == ".text"), None)
    if not text:
        raise ValueError("ELF has no .text section")
    if text["offset"] + text["size"] > len(blob):
        raise ValueError(".text lies outside file")

    strings = _candidate_strings(blob, sections)
    by_va = sorted(strings, key=lambda x: x["va"])
    funcs = _symbols(blob, sections)

    text_blob = blob[text["offset"]:text["offset"] + text["size"]]
    xrefs = []

    def add_xref(pc: int, target: int, reg: int, form: str):
        hit = None
        for s in by_va:
            start = s["va"]
            end = start + len(s["text"]) + 1
            if start <= target < end:
                hit = s
                break
        if not hit:
            return

        owner = _owner_function(pc, funcs)
        item = {
            "pc_rva": pc,
            "target_va": target,
            "register": reg,
            "form": form,
            "string": hit["text"],
            "string_va": hit["va"],
            "categories": hit["categories"],
            "function": owner["name"] if owner else None,
            "function_rva": owner["value"] if owner else None,
            "function_size": owner["size"] if owner else None,
        }
        key = (item["pc_rva"], item["target_va"], item["form"])
        if not any(
            (x["pc_rva"], x["target_va"], x.get("form")) == key
            for x in xrefs
        ):
            xrefs.append(item)

    word_count = len(text_blob) // 4
    for word_index in range(word_count):
        rel = word_index * 4
        pc = text["addr"] + rel
        insn = struct.unpack_from("<I", text_blob, rel)[0]

        adr = decode_adr(insn, pc)
        if adr:
            rd, target = adr
            add_xref(pc, target, rd, "adr")

        adrp = decode_adrp(insn, pc)
        if not adrp:
            continue

        adrp_rd, page = adrp
        # Optimized AArch64 commonly schedules unrelated instructions between
        # ADRP and the matching ADD. Search a short basic-block window.
        for lookahead in range(1, 5):
            next_index = word_index + lookahead
            if next_index >= word_count:
                break
            insn2 = struct.unpack_from(
                "<I", text_blob, next_index * 4
            )[0]
            add = decode_add_imm64(insn2)
            if not add:
                continue
            add_rd, add_rn, imm = add
            if add_rd == adrp_rd and add_rn == adrp_rd:
                add_xref(pc, page + imm, adrp_rd, f"adrp+add(+{lookahead})")
                break

    grouped = {k: [] for k in elf_probe.CANDIDATE_TERMS}
    for x in xrefs:
        for cat in x["categories"]:
            grouped[cat].append(x)

    candidate_rvas = {
        int(x["function_rva"])
        for x in xrefs
        if x.get("function_rva") is not None
    }
    call_neighborhoods = {
        rva: {"incoming": [], "outgoing": []}
        for rva in candidate_rvas
    }
    exact_funcs = {int(s["value"]): s for s in funcs}

    for word_index in range(word_count):
        pc = text["addr"] + word_index * 4
        insn = struct.unpack_from("<I", text_blob, word_index * 4)[0]
        target = decode_bl(insn, pc)
        if target is None:
            continue

        caller = _owner_function(pc, funcs)
        callee = exact_funcs.get(int(target)) or _owner_function(int(target), funcs)
        caller_rva = int(caller["value"]) if caller else None
        callee_rva = int(callee["value"]) if callee else None

        edge = {
            "call_site_rva": pc,
            "caller": caller["name"] if caller else None,
            "caller_rva": caller_rva,
            "target_rva": int(target),
            "callee": callee["name"] if callee else None,
            "callee_rva": callee_rva,
        }

        if caller_rva in call_neighborhoods:
            call_neighborhoods[caller_rva]["outgoing"].append(edge)
        if callee_rva in call_neighborhoods:
            call_neighborhoods[callee_rva]["incoming"].append(edge)

    call_neighborhoods_json = {
        f"0x{rva:X}": value
        for rva, value in sorted(call_neighborhoods.items())
    }

    function_fingerprints = {}
    funcs_by_rva = {int(s["value"]): s for s in funcs}
    func_values = sorted(funcs_by_rva)
    text_start = int(text["addr"])
    text_end = text_start + int(text["size"])
    for rva in sorted(candidate_rvas):
        if rva < text_start or rva >= text_end:
            continue
        sym = funcs_by_rva.get(rva)
        size = int(sym["size"]) if sym and sym.get("size") else 0
        if size <= 0:
            next_values = [v for v in func_values if v > rva]
            inferred_end = next_values[0] if next_values else text_end
            size = max(0, inferred_end - rva)
        size = min(size, 4096)
        if size <= 0:
            continue

        rel = rva - text_start
        raw = text_blob[rel:rel + size]
        if not raw:
            continue
        function_fingerprints[f"0x{rva:X}"] = {
            "function": sym["name"] if sym else None,
            "rva": rva,
            "size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "prefix_hex": raw[:32].hex(),
        }

    return {
        "path": str(path),
        "text": {
            "rva": text["addr"],
            "size": text["size"],
        },
        "candidate_string_count": len(strings),
        "xref_count": len(xrefs),
        "groups": grouped,
        "xrefs": xrefs,
        "candidate_call_neighborhoods": call_neighborhoods_json,
        "candidate_function_fingerprints": function_fingerprints,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        report = scan_libgame(args.libgame)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    report["ok"] = True
    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

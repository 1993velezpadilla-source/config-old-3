#!/usr/bin/env python3
"""Map AArch64 PLT imports back to CTW caller functions.

This is a static evidence tool for a user-owned libGame.so.  It uses ELF
.rela.plt + .plt metadata when available to identify functions that call
specific imported APIs such as glUniformMatrix4fv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

import aarch64_xref
import elf_probe


SHT_RELA = 4
SHN_UNDEF = 0
ELF64_RELA = struct.Struct("<QQq")


INTERESTING_IMPORTS = {
    "projection": {
        "glUniformMatrix4fv",
        "glGetUniformLocation",
        "glUseProgram",
    },
    "render": {
        "glDrawArrays",
        "glDrawElements",
        "glVertexAttribPointer",
    },
    "visibility": {
        "glEnable",
        "glDisable",
        "glDepthMask",
        "glScissor",
    },
}



DRAW_FRAME_SYMBOL = (
    "Java_com_rockstargames_oswrapper_GameNative_implOnDrawFrame"
)


def _symbol_call_hops(
    text_blob: bytes,
    text_addr: int,
    funcs: list[dict],
    root_name: str = DRAW_FRAME_SYMBOL,
) -> dict[int, dict]:
    """Return shortest symbol-to-symbol BL paths from the frame entrypoint."""
    exact = {int(f["value"]): f for f in funcs}
    by_name = {f["name"]: f for f in funcs}
    root = by_name.get(root_name)
    if root is None:
        return {}

    adjacency: dict[int, set[int]] = {}
    for rel in range(0, len(text_blob) - 3, 4):
        pc = text_addr + rel
        insn = struct.unpack_from("<I", text_blob, rel)[0]
        target = aarch64_xref.decode_bl(insn, pc)
        if target is None or int(target) not in exact:
            continue
        owner = aarch64_xref._owner_function(pc, funcs)
        if owner is None:
            continue
        src = int(owner["value"])
        dst = int(target)
        if src == dst:
            continue
        adjacency.setdefault(src, set()).add(dst)

    root_rva = int(root["value"])
    result = {
        root_rva: {
            "hops": 0,
            "path_rvas": [root_rva],
            "path_functions": [root["name"]],
        }
    }
    queue = [root_rva]
    while queue:
        src = queue.pop(0)
        src_item = result[src]
        for dst in sorted(adjacency.get(src, ())):
            if dst in result:
                continue
            sym = exact[dst]
            result[dst] = {
                "hops": src_item["hops"] + 1,
                "path_rvas": src_item["path_rvas"] + [dst],
                "path_functions": (
                    src_item["path_functions"] + [sym["name"]]
                ),
            }
            queue.append(dst)
    return result

def _dynsym_with_indices(blob: bytes, sections: list[dict]) -> tuple[list[dict], bytes]:
    dyn = next((s for s in sections if s["name"] == ".dynsym"), None)
    if dyn is None:
        raise ValueError("ELF has no .dynsym")
    if dyn["link"] >= len(sections):
        raise ValueError(".dynsym has invalid linked string table")

    strsec = sections[dyn["link"]]
    strtab = blob[strsec["offset"]:strsec["offset"] + strsec["size"]]
    entsize = dyn["entsize"] or elf_probe.ELF64_SYM.size
    if entsize < elf_probe.ELF64_SYM.size:
        raise ValueError(".dynsym entry size is too small")

    symbols = []
    count = dyn["size"] // entsize
    for index in range(count):
        off = dyn["offset"] + index * entsize
        if off + elf_probe.ELF64_SYM.size > len(blob):
            break
        st_name, st_info, st_other, st_shndx, st_value, st_size = (
            elf_probe.ELF64_SYM.unpack_from(blob, off)
        )
        symbols.append({
            "index": index,
            "name": elf_probe.cstr(strtab, st_name),
            "bind": st_info >> 4,
            "type": st_info & 0xF,
            "section_index": st_shndx,
            "value": st_value,
            "size": st_size,
        })
    return symbols, strtab


def _import_category(name: str) -> list[str]:
    return [
        category
        for category, names in INTERESTING_IMPORTS.items()
        if name in names
    ]


def _plt_imports(blob: bytes, sections: list[dict]) -> list[dict]:
    plt = next(
        (
            s for s in sections
            if s["name"] in (".plt", ".plt.sec")
        ),
        None,
    )
    rela = next(
        (
            s for s in sections
            if s["name"] in (".rela.plt", ".rela.plt.sec")
            or (s["type"] == SHT_RELA and "plt" in s["name"])
        ),
        None,
    )
    if not plt or not rela:
        return []
    if rela["link"] >= len(sections):
        return []

    dynsym_sec = sections[rela["link"]]
    if dynsym_sec["name"] != ".dynsym":
        return []

    symbols, _ = _dynsym_with_indices(blob, sections)

    entsize = rela["entsize"] or ELF64_RELA.size
    if entsize < ELF64_RELA.size:
        return []
    relocs = []
    count = rela["size"] // entsize
    for i in range(count):
        off = rela["offset"] + i * entsize
        if off + ELF64_RELA.size > len(blob):
            break
        r_offset, r_info, r_addend = ELF64_RELA.unpack_from(blob, off)
        sym_index = r_info >> 32
        r_type = r_info & 0xFFFFFFFF
        if sym_index >= len(symbols):
            continue
        sym = symbols[sym_index]
        if not sym["name"] or sym["section_index"] != SHN_UNDEF:
            continue
        relocs.append({
            "index": i,
            "got_rva": r_offset,
            "relocation_type": r_type,
            "symbol_index": sym_index,
            "symbol": sym["name"],
            "categories": _import_category(sym["name"]),
        })

    if not relocs:
        return []

    # Conventional AArch64 PLT: 32-byte resolver header + 16-byte entries.
    # Some toolchains use .plt.sec without the initial resolver header.
    header = 0 if plt["name"] == ".plt.sec" else 32
    stride = 16
    needed = header + stride * len(relocs)
    if plt["size"] < needed:
        return []

    for i, item in enumerate(relocs):
        item["plt_rva"] = int(plt["addr"]) + header + i * stride
        item["plt_section"] = plt["name"]
        item["layout"] = {
            "header_bytes": header,
            "entry_bytes": stride,
            "heuristic": "conventional AArch64 PLT layout",
        }
    return relocs


def scan_plt_calls(path: Path) -> dict:
    blob = path.read_bytes()
    sections = aarch64_xref._read_sections(blob)
    text = next((s for s in sections if s["name"] == ".text"), None)
    if not text:
        raise ValueError("ELF has no .text")

    imports = _plt_imports(blob, sections)
    plt_by_rva = {int(x["plt_rva"]): x for x in imports}
    funcs = aarch64_xref._symbols(blob, sections)

    text_blob = blob[text["offset"]:text["offset"] + text["size"]]
    reachability = _symbol_call_hops(
        text_blob,
        int(text["addr"]),
        funcs,
    )
    callers = []
    grouped = {key: [] for key in INTERESTING_IMPORTS}

    for rel in range(0, len(text_blob) - 3, 4):
        insn = struct.unpack_from("<I", text_blob, rel)[0]
        pc = int(text["addr"]) + rel
        target = aarch64_xref.decode_bl(insn, pc)
        if target is None:
            continue
        imp = plt_by_rva.get(int(target))
        if imp is None:
            continue

        owner = aarch64_xref._owner_function(pc, funcs)
        caller_rva = int(owner["value"]) if owner else None
        reachable = reachability.get(caller_rva) if caller_rva is not None else None
        item = {
            "call_site_rva": pc,
            "caller": owner["name"] if owner else None,
            "caller_rva": caller_rva,
            "caller_size": int(owner["size"]) if owner else None,
            "import_symbol": imp["symbol"],
            "plt_rva": imp["plt_rva"],
            "got_rva": imp["got_rva"],
            "categories": imp["categories"],
            "draw_frame_reachable": reachable is not None,
            "draw_frame_hops": reachable["hops"] if reachable else None,
            "draw_frame_path_rvas": reachable["path_rvas"] if reachable else [],
            "draw_frame_path_functions": (
                reachable["path_functions"] if reachable else []
            ),
        }
        callers.append(item)
        for category in imp["categories"]:
            grouped[category].append(item)

    return {
        "path": str(path),
        "imports": imports,
        "interesting_import_count": sum(1 for x in imports if x["categories"]),
        "call_count": len(callers),
        "draw_frame_symbol": DRAW_FRAME_SYMBOL,
        "draw_frame_reachable_symbol_count": len(reachability),
        "groups": grouped,
        "calls": callers,
        "note": (
            "PLT mapping uses conventional AArch64 .plt/.rela.plt layout; "
            "treat matches as evidence until disassembly/runtime verification."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        report = scan_plt_calls(args.libgame)
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

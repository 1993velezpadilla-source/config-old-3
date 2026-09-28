#!/usr/bin/env python3
"""Fail-closed AArch64 prologue safety probe for CTW runtime hooks.

The native hook overwrites 16 bytes. A simple trampoline may copy those four
instructions only when none are PC-relative/control-flow instructions whose
meaning would change at the trampoline address.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

import aarch64_xref


PROLOGUE_BYTES = 16
PROLOGUE_INSTRUCTIONS = 4


def classify_instruction(insn: int) -> tuple[str, bool, str]:
    # ADR / ADRP.
    if (insn & 0x9F000000) == 0x10000000:
        return ("adr", False, "PC-relative ADR")
    if (insn & 0x9F000000) == 0x90000000:
        return ("adrp", False, "PC-relative ADRP")

    # Unconditional immediate branches B / BL.
    if (insn & 0xFC000000) == 0x14000000:
        return ("b", False, "PC-relative branch")
    if (insn & 0xFC000000) == 0x94000000:
        return ("bl", False, "PC-relative call")

    # Conditional immediate branch B.cond.
    if (insn & 0xFF000010) == 0x54000000:
        return ("b.cond", False, "PC-relative conditional branch")

    # Compare-and-branch CBZ / CBNZ, W/X variants.
    if (insn & 0x7E000000) == 0x34000000:
        return ("cbz/cbnz", False, "PC-relative compare branch")

    # Test-and-branch TBZ / TBNZ.
    if (insn & 0x7E000000) == 0x36000000:
        return ("tbz/tbnz", False, "PC-relative test branch")

    # Load literal family (LDR/LDRSW/PRFM literal): opc in bits 31:30,
    # fixed 0b011 at 29:27. These encode PC-relative imm19.
    if (insn & 0x3B000000) == 0x18000000:
        return ("literal-load", False, "PC-relative literal load/prefetch")

    # Exception/return/indirect branch terminate or redirect control flow.
    # They are not suitable inside the copied entry block.
    if (insn & 0xFFFFFC1F) == 0xD65F0000:
        return ("ret", False, "return in overwritten prologue")
    if (insn & 0xFFFFFC1F) == 0xD61F0000:
        return ("br", False, "indirect branch in overwritten prologue")
    if (insn & 0xFFFFFC1F) == 0xD63F0000:
        return ("blr", False, "indirect call in overwritten prologue")

    return ("other", True, "position-independent for simple copy probe")


def _read_exec_prefix(blob: bytes, rva: int, size: int = PROLOGUE_BYTES) -> bytes:
    sections = aarch64_xref._read_sections(blob)
    for sec in sections:
        if not (int(sec.get("flags") or 0) & 0x4):  # SHF_EXECINSTR
            continue
        start = int(sec["addr"])
        end = start + int(sec["size"])
        if rva < start or rva + size > end:
            continue
        file_off = int(sec["offset"]) + (rva - start)
        raw = blob[file_off:file_off + size]
        if len(raw) != size:
            raise ValueError(f"RVA 0x{rva:X} prologue is truncated")
        return raw
    raise ValueError(f"RVA 0x{rva:X} is not in an executable section")


def analyze_bytes(raw: bytes, rva: int = 0) -> dict:
    if len(raw) != PROLOGUE_BYTES:
        raise ValueError(f"need exactly {PROLOGUE_BYTES} prologue bytes")

    instructions = []
    safe = True
    for i in range(PROLOGUE_INSTRUCTIONS):
        insn = struct.unpack_from("<I", raw, i * 4)[0]
        kind, relocatable, reason = classify_instruction(insn)
        if not relocatable:
            safe = False
        instructions.append({
            "index": i,
            "rva": rva + i * 4,
            "word": f"0x{insn:08X}",
            "kind": kind,
            "relocatable_for_simple_copy": relocatable,
            "reason": reason,
        })

    return {
        "rva": rva,
        "bytes_hex": raw.hex(),
        "instruction_count": PROLOGUE_INSTRUCTIONS,
        "simple_copy_trampoline_safe": safe,
        "instructions": instructions,
        "note": (
            "safe=true only means the first 16 bytes contain no recognized "
            "PC-relative/control-flow hazards. ABI verification is still required."
        ),
    }


def analyze_target(path: Path, rva: int) -> dict:
    blob = path.read_bytes()
    raw = _read_exec_prefix(blob, rva)
    result = analyze_bytes(raw, rva)
    result["path"] = str(path)
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("rva", type=lambda x: int(x, 0))
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        report = analyze_target(args.libgame, args.rva)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    report["ok"] = True
    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["simple_copy_trampoline_safe"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

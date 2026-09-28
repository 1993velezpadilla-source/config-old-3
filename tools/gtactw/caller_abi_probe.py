#!/usr/bin/env python3
"""Static caller-side ABI evidence for CTW AArch64 hook candidates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct

import aarch64_xref
import abi_probe
import elf_probe
import profile_template


def _text_and_functions(libgame: Path):
    blob = libgame.read_bytes()
    sections = aarch64_xref._read_sections(blob)
    text = next((s for s in sections if s["name"] == ".text"), None)
    if text is None:
        raise ValueError("ELF has no .text")
    funcs = aarch64_xref._symbols(blob, sections)
    text_blob = blob[text["offset"]:text["offset"] + text["size"]]
    return blob, text, text_blob, funcs


def direct_call_sites(libgame: Path, target_rva: int) -> list[dict]:
    if not isinstance(target_rva, int) or target_rva <= 0:
        raise ValueError("target_rva must be positive")

    _, text, text_blob, funcs = _text_and_functions(libgame)
    out = []
    for rel in range(0, len(text_blob) - 3, 4):
        insn = struct.unpack_from("<I", text_blob, rel)[0]
        pc = int(text["addr"]) + rel
        target = aarch64_xref.decode_bl(insn, pc)
        if target != target_rva:
            continue
        owner = aarch64_xref._owner_function(pc, funcs)
        out.append({
            "call_site_rva": pc,
            "caller": owner["name"] if owner else None,
            "caller_rva": int(owner["value"]) if owner else None,
            "caller_size": int(owner["size"]) if owner else None,
        })
    return out


def _parsed_window(
    objdump: str,
    libgame: Path,
    start: int,
    stop: int,
) -> list[dict]:
    text = abi_probe.disassemble_window(
        objdump,
        libgame,
        start,
        max(4, stop - start),
    )
    return abi_probe.parse_objdump(
        text,
        requested_rva=start,
    )["instructions"]



def _prepared_value_kind(
    reg: str,
    mnemonic: str,
    operands: str,
) -> str:
    ops = abi_probe._split_operands(operands)
    first = ops[0].lower() if ops else ""
    m = mnemonic.lower()

    if reg.startswith("v"):
        n = reg[1:]
        if re.search(rf"\bs{n}\b", first):
            return "float32_like"
        if re.search(rf"\bd{n}\b", first):
            return "float64_like"
        if re.search(rf"\b[qv]{n}\b", first):
            return "vector_or_aggregate"
        return "fp_value"

    n = reg[1:]
    if re.search(rf"\bw{n}\b", first):
        return "scalar_32_like"

    if m in {"adr", "adrp"}:
        return "address_like"
    if m == "add" and len(ops) >= 2 and ops[1].strip().lower() == "sp":
        return "stack_address_like"
    if m == "mov" and len(ops) >= 2 and ops[1].strip().lower() == "sp":
        return "stack_address_like"
    if m.startswith("ldr") or m.startswith("ldur"):
        return "loaded_64_value"
    if m in {"mov", "movz", "movn", "movk"}:
        return "scalar_or_pointer_64"
    return "scalar_or_pointer_64"


def _return_consumption_kind(
    reg: str,
    mnemonic: str,
    operands: str,
) -> str:
    m = mnemonic.lower()
    if reg == "x0":
        if m in {"cbz", "cbnz", "tbz", "tbnz"}:
            return "branch_condition_integer_or_bool"
        if m in {"cmp", "cmn", "tst"}:
            return "integer_compare"
        if m.startswith("str"):
            return "stored_gpr_value"
        if "[" in operands and re.search(r"\bx0\b", operands, re.IGNORECASE):
            return "possible_pointer_use"
        return "gpr_value_use"

    if m.startswith("f"):
        return "floating_value_use"
    if m.startswith("str"):
        return "stored_fp_or_vector_value"
    return "fp_or_vector_use"


def _call_context(
    instructions: list[dict],
    call_site: int,
    *,
    lookback: int = 16,
    lookahead: int = 12,
) -> dict:
    index = next(
        (i for i, ins in enumerate(instructions) if ins["address"] == call_site),
        None,
    )
    if index is None:
        raise ValueError(f"call site 0x{call_site:X} missing from disassembly")

    before = instructions[max(0, index - lookback):index]
    after = instructions[index + 1:index + 1 + lookahead]

    # Track the final access before the call. A local write is strong evidence
    # that the caller prepares that argument. A read-only occurrence means the
    # value may simply be passed through from the caller's own ABI.
    prepared = {}
    for ins in before:
        reads, writes = abi_probe._instruction_arg_reads_writes(
            ins["mnemonic"],
            ins["operands"],
        )
        for reg in sorted(reads | writes):
            if reg.startswith(("x", "v")) and reg[1:].isdigit():
                n = int(reg[1:])
                if n > 7:
                    continue
                if reg in reads and reg in writes:
                    mode = "read_write"
                elif reg in writes:
                    mode = "write"
                else:
                    mode = "read"
                prepared[reg] = {
                    "mode": mode,
                    "address": ins["address"],
                    "mnemonic": ins["mnemonic"],
                    "operands": ins["operands"],
                    "kind_hint": _prepared_value_kind(
                        reg,
                        ins["mnemonic"],
                        ins["operands"],
                    ) if mode in {"write", "read_write"} else None,
                }

    prepared_local = sorted(
        reg
        for reg, item in prepared.items()
        if item["mode"] in {"write", "read_write"}
    )
    passthrough_possible = sorted(
        reg
        for reg, item in prepared.items()
        if item["mode"] == "read"
    )

    # Return-use evidence. Stop on a new call or explicit control-transfer;
    # otherwise look for x0/v0 read-before-overwrite.
    return_use = {}
    unresolved = {"x0", "v0"}
    for ins in after:
        mnemonic = ins["mnemonic"]
        if mnemonic in abi_probe.CALL_MNEMONICS:
            break
        if mnemonic in {"b", "br", "ret", "eret"}:
            break

        reads, writes = abi_probe._instruction_arg_reads_writes(
            mnemonic,
            ins["operands"],
        )
        for reg in list(unresolved):
            if reg in reads:
                return_use[reg] = {
                    "status": "consumed",
                    "address": ins["address"],
                    "mnemonic": mnemonic,
                    "operands": ins["operands"],
                    "kind_hint": _return_consumption_kind(
                        reg,
                        mnemonic,
                        ins["operands"],
                    ),
                }
                unresolved.remove(reg)
            elif reg in writes:
                return_use[reg] = {
                    "status": "overwritten_without_read",
                    "address": ins["address"],
                    "mnemonic": mnemonic,
                    "operands": ins["operands"],
                }
                unresolved.remove(reg)
        if not unresolved:
            break

    for reg in unresolved:
        return_use[reg] = {
            "status": "not_observed_in_window",
            "address": None,
            "mnemonic": None,
            "operands": None,
        }

    return {
        "prepared_registers": prepared,
        "locally_prepared_argument_registers": prepared_local,
        "possible_passthrough_argument_registers": passthrough_possible,
        "return_use": return_use,
        "before": [ins["text"] for ins in before[-8:]],
        "after": [ins["text"] for ins in after[:8]],
        "note": (
            "Caller-side evidence is heuristic. Local writes before BL suggest "
            "argument preparation; post-call x0/v0 reads suggest return use. "
            "It never verifies a prototype automatically."
        ),
    }


def probe_target_callers(
    libgame: Path,
    target_rva: int,
    *,
    objdump_path: Path | None = None,
    max_callers: int = 16,
) -> dict:
    if max_callers < 1 or max_callers > 64:
        raise ValueError("max_callers must be between 1 and 64")

    elf = elf_probe.inspect_elf(libgame)
    if elf.get("elf", {}).get("machine") != "AArch64":
        raise ValueError("libGame is not AArch64")

    objdump = abi_probe.find_objdump(objdump_path)
    sites = direct_call_sites(libgame, target_rva)
    out = []

    for site in sites[:max_callers]:
        caller_rva = site.get("caller_rva")
        caller_size = site.get("caller_size")
        call_site = site["call_site_rva"]

        if isinstance(caller_rva, int) and caller_rva > 0:
            start = caller_rva
            if isinstance(caller_size, int) and caller_size > 0:
                stop = min(
                    caller_rva + caller_size,
                    call_site + 4 * 13,
                )
            else:
                stop = call_site + 4 * 13
        else:
            start = max(0, call_site - 4 * 16)
            stop = call_site + 4 * 13

        instructions = _parsed_window(
            objdump,
            libgame,
            start,
            stop,
        )
        context = _call_context(instructions, call_site)
        out.append({
            **site,
            "context": context,
        })

    return {
        "target_rva": target_rva,
        "target_rva_hex": f"0x{target_rva:X}",
        "direct_call_site_count": len(sites),
        "callers_analyzed": len(out),
        "callers": out,
        "objdump": objdump,
        "note": (
            "Only direct AArch64 BL call sites are covered. Indirect calls "
            "through function pointers/registers are not inferred."
        ),
    }


def probe_profile_callers(
    libgame: Path,
    profile_path: Path,
    *,
    objdump_path: Path | None = None,
    top: int = 3,
    max_callers: int = 16,
) -> dict:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    candidates = abi_probe._candidate_targets(profile, top)
    result = {}
    errors = []

    for key in profile_template.TARGET_KEYS:
        entries = []
        for candidate in candidates.get(key, []):
            rva = candidate.get("rva")
            if not isinstance(rva, int) or rva <= 0:
                continue
            try:
                caller_report = probe_target_callers(
                    libgame,
                    rva,
                    objdump_path=objdump_path,
                    max_callers=max_callers,
                )
                entries.append({
                    **candidate,
                    "caller_abi_evidence": caller_report,
                })
            except Exception as exc:
                errors.append({
                    "target": key,
                    "rva": rva,
                    "error": str(exc),
                })
        result[key] = entries

    return {
        "ok": not errors,
        "libgame": str(libgame),
        "profile": str(profile_path),
        "targets": result,
        "errors": errors,
        "note": (
            "Caller-side evidence complements callee ABI hints and remains "
            "manual-review evidence only."
        ),
    }




def attach_caller_abi_evidence(profile: dict, report: dict) -> dict:
    """Attach caller-side evidence to matching ABI candidates by exact RVA."""
    out = json.loads(json.dumps(profile))
    ledger = out.setdefault("abi_verification", {})

    by_target = {}
    for key in profile_template.TARGET_KEYS:
        mapping = {}
        for item in report.get("targets", {}).get(key, []):
            if not isinstance(item, dict):
                continue
            rva = item.get("rva")
            evidence = item.get("caller_abi_evidence")
            if (
                isinstance(rva, int)
                and rva > 0
                and isinstance(evidence, dict)
            ):
                mapping[rva] = evidence
        by_target[key] = mapping

    for key in profile_template.TARGET_KEYS:
        item = ledger.get(key)
        if not isinstance(item, dict):
            continue
        candidates = item.get("candidates")
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            rva = candidate.get("rva")
            evidence = by_target.get(key, {}).get(rva)
            if evidence is not None:
                candidate["caller_abi_evidence"] = evidence

    out["caller_abi_probe_note"] = report.get("note")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("--objdump", type=Path)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--max-callers", type=int, default=16)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    try:
        report = probe_profile_callers(
            args.libgame,
            args.profile,
            objdump_path=args.objdump,
            top=args.top,
            max_callers=args.max_callers,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

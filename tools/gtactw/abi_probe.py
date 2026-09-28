#!/usr/bin/env python3
"""Produce ABI evidence for CTW AArch64 hook candidates.

This tool never declares an ABI verified. It uses llvm-objdump to disassemble
small windows around candidate RVAs from a CTW profile and summarizes evidence:
prologue/stack size hints, argument-register mentions, branches/calls, returns,
and the raw instruction window.

Use only with a user-owned libGame.so.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import aarch64_prologue
import elf_probe
import profile_template


INSN_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+(?:[0-9a-fA-F]{2}(?:\s+|$))*"
    r"([A-Za-z.][A-Za-z0-9.]*)\s*(.*)$"
)
REG_RE = re.compile(
    r"\b(?:x|w)(?:[0-9]|[12][0-9]|3[01])\b"
    r"|\b(?:v|q|d|s)(?:[0-9]|[12][0-9]|3[01])\b",
    re.IGNORECASE,
)
ARG_GPR_RE = re.compile(r"\b[wx]([0-7])\b", re.IGNORECASE)
ARG_FP_RE = re.compile(r"\b[vqds]([0-7])\b", re.IGNORECASE)
IMM_RE = re.compile(r"#(?:0x)?([0-9a-fA-F]+)")
TARGET_RE = re.compile(r"\b(?:0x)?([0-9a-fA-F]+)\b")
SYMBOL_RE = re.compile(r"<([^>]+)>")

CALL_MNEMONICS = {"bl", "blr"}
RETURN_MNEMONICS = {"ret", "eret"}
BRANCH_MNEMONICS = {
    "b", "br", "bl", "blr",
    "cbz", "cbnz", "tbz", "tbnz",
}
WRITE_FIRST_MNEMONICS = {
    "mov", "movz", "movn", "movk",
    "add", "adds", "sub", "subs",
    "and", "ands", "orr", "eor", "bic",
    "lsl", "lsr", "asr",
    "adr", "adrp",
    "ldr", "ldrb", "ldrh", "ldrsw",
    "ldur", "ldp",
    "fmov", "fadd", "fsub", "fmul", "fdiv",
    "fcvt", "scvtf", "ucvtf",
}


def find_objdump(explicit: Path | None = None) -> str:
    if explicit is not None:
        if explicit.is_file():
            return str(explicit)
        raise FileNotFoundError(explicit)

    for name in ("llvm-objdump", "aarch64-linux-android-objdump"):
        found = shutil.which(name)
        if found:
            return found

    roots = []
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(key)
        if value:
            roots.append(Path(value))

    for root in roots:
        ndk_root = root / "ndk"
        if not ndk_root.is_dir():
            continue
        versions = sorted(
            (p for p in ndk_root.iterdir() if p.is_dir()),
            reverse=True,
        )
        for version in versions:
            prebuilt = version / "toolchains" / "llvm" / "prebuilt"
            if not prebuilt.is_dir():
                continue
            for host in prebuilt.iterdir():
                candidate = host / "bin" / (
                    "llvm-objdump.exe" if os.name == "nt" else "llvm-objdump"
                )
                if candidate.is_file():
                    return str(candidate)

    raise FileNotFoundError(
        "llvm-objdump not found; install Android NDK or pass --objdump"
    )


def _split_operands(text: str) -> list[str]:
    out = []
    buf = []
    depth = 0
    for ch in text:
        if ch in "[{(":
            depth += 1
        elif ch in "]})" and depth:
            depth -= 1
        if ch == "," and depth == 0:
            item = "".join(buf).strip()
            if item:
                out.append(item)
            buf = []
        else:
            buf.append(ch)
    item = "".join(buf).strip()
    if item:
        out.append(item)
    return out


def _registers(text: str) -> list[str]:
    seen = []
    for match in REG_RE.finditer(text):
        reg = match.group(0).lower()
        if reg not in seen:
            seen.append(reg)
    return seen



def _canonical_arg_registers(text: str) -> set[str]:
    out = set()
    for reg in _registers(text):
        m = re.fullmatch(r"[xw]([0-7])", reg)
        if m:
            out.add(f"x{int(m.group(1))}")
            continue
        m = re.fullmatch(r"[vqds]([0-7])", reg)
        if m:
            out.add(f"v{int(m.group(1))}")
    return out


def _instruction_arg_reads_writes(
    mnemonic: str,
    operands: str,
) -> tuple[set[str], set[str]]:
    """Approximate AArch64 argument-register reads/writes for dataflow hints."""
    ops = _split_operands(operands)
    op_regs = [_canonical_arg_registers(op) for op in ops]
    all_regs = set().union(*op_regs) if op_regs else set()
    reads: set[str] = set()
    writes: set[str] = set()

    m = mnemonic.lower()

    # Stores consume value registers and address/base registers.
    if m.startswith("st"):
        reads |= all_regs
        return reads, writes

    # Pair loads write the first two register operands and read the address.
    if m.startswith("ldp") or m.startswith("ldnp"):
        if len(op_regs) >= 1:
            writes |= op_regs[0]
        if len(op_regs) >= 2:
            writes |= op_regs[1]
        for regs in op_regs[2:]:
            reads |= regs
        return reads, writes

    # Scalar/vector loads write the first operand and read address operands.
    if m.startswith("ldr") or m.startswith("ldur") or m in {
        "ldxr", "ldaxr", "ldar", "ldapr",
    }:
        if op_regs:
            writes |= op_regs[0]
        for regs in op_regs[1:]:
            reads |= regs
        return reads, writes

    # Compare/test and register-controlled branches only consume registers.
    if m in {
        "cmp", "cmn", "tst",
        "cbz", "cbnz", "tbz", "tbnz",
        "br", "blr", "ret",
    }:
        reads |= all_regs
        return reads, writes

    # No destination register.
    if m in {"b", "bl", "nop", "dmb", "dsb", "isb"}:
        return reads, writes

    # System register read/write forms.
    if m == "mrs":
        if op_regs:
            writes |= op_regs[0]
        return reads, writes
    if m == "msr":
        reads |= all_regs
        return reads, writes

    # Common AArch64 ALU/move/FP forms write operand 0 and consume the rest.
    if ops and (
        m in WRITE_FIRST_MNEMONICS
        or m.startswith("csel")
        or m.startswith("cs")
        or m.startswith("madd")
        or m.startswith("msub")
        or m.startswith("mul")
        or m.startswith("sdiv")
        or m.startswith("udiv")
        or m.startswith("neg")
        or m.startswith("f")
    ):
        writes |= op_regs[0]
        for regs in op_regs[1:]:
            reads |= regs
        return reads, writes

    # Conservative fallback: unknown instructions are treated as reads. This
    # avoids falsely declaring an incoming argument overwritten.
    reads |= all_regs
    return reads, writes


def _argument_read_before_write(instructions: list[dict]) -> dict:
    first_access: dict[str, dict] = {}

    for ins in instructions:
        reads, writes = _instruction_arg_reads_writes(
            ins["mnemonic"],
            ins["operands"],
        )
        for reg in sorted(reads | writes):
            if reg in first_access:
                continue
            if reg in reads and reg in writes:
                mode = "read_write"
            elif reg in reads:
                mode = "read"
            else:
                mode = "write"
            first_access[reg] = {
                "mode": mode,
                "address": ins["address"],
                "mnemonic": ins["mnemonic"],
                "operands": ins["operands"],
            }

    gpr_inputs = sorted(
        int(reg[1:])
        for reg, item in first_access.items()
        if reg.startswith("x") and item["mode"] in {"read", "read_write"}
    )
    gpr_overwritten = sorted(
        int(reg[1:])
        for reg, item in first_access.items()
        if reg.startswith("x") and item["mode"] == "write"
    )
    fp_inputs = sorted(
        int(reg[1:])
        for reg, item in first_access.items()
        if reg.startswith("v") and item["mode"] in {"read", "read_write"}
    )
    fp_overwritten = sorted(
        int(reg[1:])
        for reg, item in first_access.items()
        if reg.startswith("v") and item["mode"] == "write"
    )

    return {
        "first_access": first_access,
        "likely_gpr_inputs_x0_x7": gpr_inputs,
        "overwritten_gpr_before_read_x0_x7": gpr_overwritten,
        "likely_fp_inputs_v0_v7": fp_inputs,
        "overwritten_fp_before_read_v0_v7": fp_overwritten,
    }


def parse_objdump(text: str, *, requested_rva: int | None = None) -> dict:
    instructions = []
    for raw in text.splitlines():
        m = INSN_RE.match(raw)
        if not m:
            continue
        address = int(m.group(1), 16)
        mnemonic = m.group(2).lower()
        operands = m.group(3).strip()
        instructions.append({
            "address": address,
            "mnemonic": mnemonic,
            "operands": operands,
            "text": f"{mnemonic} {operands}".rstrip(),
            "registers": _registers(operands),
        })

    if not instructions:
        raise ValueError("objdump output contains no parsed AArch64 instructions")

    gpr_mentions = {i: [] for i in range(8)}
    fp_mentions = {i: [] for i in range(8)}
    first_gpr = {}
    first_fp = {}
    calls = []
    branches = []
    returns = []
    stack_allocations = []
    saved_registers = []
    prologue = []

    for index, ins in enumerate(instructions):
        mnemonic = ins["mnemonic"]
        operands = ins["operands"]
        ops = _split_operands(operands)

        if index < 8:
            prologue.append(ins["text"])

        for m in ARG_GPR_RE.finditer(operands):
            n = int(m.group(1))
            if ins["address"] not in gpr_mentions[n]:
                gpr_mentions[n].append(ins["address"])
            first_gpr.setdefault(n, {
                "address": ins["address"],
                "mnemonic": mnemonic,
                "operands": operands,
            })

        for m in ARG_FP_RE.finditer(operands):
            n = int(m.group(1))
            if ins["address"] not in fp_mentions[n]:
                fp_mentions[n].append(ins["address"])
            first_fp.setdefault(n, {
                "address": ins["address"],
                "mnemonic": mnemonic,
                "operands": operands,
            })

        if mnemonic in CALL_MNEMONICS:
            symbol = None
            sm = SYMBOL_RE.search(operands)
            if sm:
                symbol = sm.group(1)
            target = None
            tm = TARGET_RE.search(operands)
            if tm and mnemonic == "bl":
                try:
                    target = int(tm.group(1), 16)
                except ValueError:
                    target = None
            calls.append({
                "address": ins["address"],
                "mnemonic": mnemonic,
                "target_rva": target,
                "symbol": symbol,
                "operands": operands,
            })

        if mnemonic in BRANCH_MNEMONICS:
            branches.append({
                "address": ins["address"],
                "mnemonic": mnemonic,
                "operands": operands,
            })

        if mnemonic in RETURN_MNEMONICS:
            returns.append(ins["address"])

        # Common AArch64 stack allocation forms.
        if mnemonic == "sub" and len(ops) >= 3:
            if ops[0].lower() == "sp" and ops[1].lower() == "sp":
                im = IMM_RE.search(ops[2])
                if im:
                    stack_allocations.append({
                        "address": ins["address"],
                        "bytes": int(im.group(1), 16),
                        "form": "sub sp, sp, #imm",
                    })

        if mnemonic == "stp" and "[sp" in operands.lower():
            regs = _registers(ops[0] + "," + ops[1]) if len(ops) >= 2 else []
            for reg in regs:
                if reg not in saved_registers:
                    saved_registers.append(reg)
            # Pre-index save often encodes frame size as negative immediate.
            neg = re.search(r"\[sp,\s*#-(?:0x)?([0-9a-fA-F]+)\]!", operands)
            if neg:
                stack_allocations.append({
                    "address": ins["address"],
                    "bytes": int(neg.group(1), 16),
                    "form": "stp pre-index",
                })

    # First-use heuristics: a first operand that is written before any other
    # mention can mean that register is not an incoming argument. This is only
    # a hint, never ABI verification.
    likely_gpr_inputs = []
    overwritten_gpr_early = []
    likely_fp_inputs = []

    for n, info in first_gpr.items():
        first_ins = next(
            x for x in instructions if x["address"] == info["address"]
        )
        ops = _split_operands(first_ins["operands"])
        target_reg = f"x{n}"
        target_w = f"w{n}"
        first_op_regs = _registers(ops[0]) if ops else []
        writes_first = (
            first_ins["mnemonic"] in WRITE_FIRST_MNEMONICS
            and (
                target_reg in first_op_regs
                or target_w in first_op_regs
            )
        )
        if writes_first:
            overwritten_gpr_early.append(n)
        else:
            likely_gpr_inputs.append(n)

    for n, info in first_fp.items():
        first_ins = next(
            x for x in instructions if x["address"] == info["address"]
        )
        ops = _split_operands(first_ins["operands"])
        regs = _registers(ops[0]) if ops else []
        forms = {f"v{n}", f"q{n}", f"d{n}", f"s{n}"}
        writes_first = (
            first_ins["mnemonic"] in WRITE_FIRST_MNEMONICS
            and any(reg in forms for reg in regs)
        )
        if not writes_first:
            likely_fp_inputs.append(n)

    dataflow = _argument_read_before_write(instructions)
    likely_gpr_inputs = dataflow["likely_gpr_inputs_x0_x7"]
    overwritten_gpr_early = dataflow[
        "overwritten_gpr_before_read_x0_x7"
    ]
    likely_fp_inputs = dataflow["likely_fp_inputs_v0_v7"]

    stack_hint = max(
        (x["bytes"] for x in stack_allocations),
        default=None,
    )

    return {
        "requested_rva": requested_rva,
        "first_instruction_rva": instructions[0]["address"],
        "last_instruction_rva": instructions[-1]["address"],
        "instruction_count": len(instructions),
        "prologue": prologue,
        "stack_frame_bytes_hint": stack_hint,
        "stack_allocations": stack_allocations,
        "saved_registers": saved_registers,
        "argument_register_hints": {
            "likely_gpr_inputs_x0_x7": likely_gpr_inputs,
            "overwritten_gpr_early_x0_x7": overwritten_gpr_early,
            "likely_fp_inputs_v0_v7": likely_fp_inputs,
            "overwritten_fp_before_read_v0_v7": dataflow[
                "overwritten_fp_before_read_v0_v7"
            ],
            "first_access": dataflow["first_access"],
            "analysis": "read_before_write",
            "gpr_mentions": {
                f"x{n}": addrs
                for n, addrs in gpr_mentions.items()
                if addrs
            },
            "fp_mentions": {
                f"v{n}": addrs
                for n, addrs in fp_mentions.items()
                if addrs
            },
        },
        "calls": calls,
        "branches": branches,
        "returns": returns,
        "instructions": instructions,
        "verification_status": "abi_hint_only",
    }


def disassemble_window(
    objdump: str,
    libgame: Path,
    rva: int,
    size: int,
) -> str:
    stop = rva + size
    proc = subprocess.run(
        [
            objdump,
            "-d",
            "-C",
            "--no-show-raw-insn",
            f"--start-address=0x{rva:X}",
            f"--stop-address=0x{stop:X}",
            str(libgame),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"llvm-objdump failed: {detail}")
    return proc.stdout


def _candidate_targets(profile: dict, top: int) -> dict[str, list[dict]]:
    out = {}
    targets = profile.get("patch_targets_rva", {})
    verification = profile.get("target_verification", {})
    rankings = profile.get("target_evidence_rankings", {})

    for key in profile_template.TARGET_KEYS:
        verified = verification.get(key, {})
        rva = targets.get(key)
        if (
            isinstance(rva, int)
            and rva > 0
            and isinstance(verified, dict)
            and verified.get("status") == "verified"
        ):
            out[key] = [{
                "rva": rva,
                "source": "verified_target",
                "score": None,
                "function": None,
            }]
            continue

        candidates = []
        for item in rankings.get(key, [])[:top]:
            rva = item.get("rva")
            if not isinstance(rva, int) or rva <= 0:
                continue
            candidates.append({
                "rva": rva,
                "source": "evidence_ranking",
                "score": item.get("score"),
                "function": item.get("function"),
                "reasons": item.get("reasons", []),
            })
        out[key] = candidates
    return out


def probe_profile(
    libgame: Path,
    profile_path: Path,
    *,
    objdump_path: Path | None = None,
    top: int = 3,
    window: int = 256,
) -> dict:
    if top < 1 or top > 16:
        raise ValueError("top must be between 1 and 16")
    if window < 32 or window > 4096 or window % 4:
        raise ValueError("window must be a 4-byte multiple between 32 and 4096")

    # Validate basic architecture before invoking external disassembly.
    elf = elf_probe.inspect_elf(libgame)
    if elf.get("elf", {}).get("machine") != "AArch64":
        raise ValueError("libGame is not AArch64")

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    objdump = find_objdump(objdump_path)
    candidates = _candidate_targets(profile, top)

    targets = {}
    errors = []
    for key, items in candidates.items():
        target_entries = []
        for item in items:
            try:
                text = disassemble_window(
                    objdump,
                    libgame,
                    int(item["rva"]),
                    window,
                )
                evidence = parse_objdump(
                    text,
                    requested_rva=int(item["rva"]),
                )
                prologue = aarch64_prologue.analyze_target(
                    libgame,
                    int(item["rva"]),
                )
                evidence["prologue_relocation"] = prologue
                target_entries.append({
                    **item,
                    "abi_evidence": evidence,
                })
            except Exception as exc:
                errors.append({
                    "target": key,
                    "rva": item.get("rva"),
                    "error": str(exc),
                })
        targets[key] = target_entries

    return {
        "ok": not errors,
        "libgame": str(libgame),
        "profile": str(profile_path),
        "objdump": objdump,
        "window_bytes": window,
        "top_candidates_per_target": top,
        "targets": targets,
        "errors": errors,
        "note": (
            "ABI evidence is heuristic. Prologue relocation safety only "
            "indicates whether the first 16 bytes are suitable for a simple "
            "copy trampoline. Do not install a runtime hook until the target "
            "function prototype/adapter is explicitly verified."
        ),
    }



def attach_abi_evidence(profile: dict, report: dict) -> dict:
    """Attach ABI candidate evidence without changing verification status."""
    out = json.loads(json.dumps(profile))
    ledger = out.setdefault("abi_verification", {})

    for key in profile_template.TARGET_KEYS:
        item = ledger.setdefault(key, {
            "status": "pending",
            "prototype": None,
            "calling_convention": "aarch64_aapcs64",
            "adapter": None,
            "evidence": [],
        })
        # Never promote status/prototype/adapter automatically.
        candidates = []
        for candidate in report.get("targets", {}).get(key, []):
            evidence = candidate.get("abi_evidence")
            if not isinstance(evidence, dict):
                continue
            prologue = evidence.get("prologue_relocation", {})
            simple_safe = bool(
                isinstance(prologue, dict)
                and prologue.get("simple_copy_trampoline_safe")
            )
            candidates.append({
                "rva": candidate.get("rva"),
                "source": candidate.get("source"),
                "function": candidate.get("function"),
                "score": candidate.get("score"),
                "reasons": candidate.get("reasons", []),
                "trampoline_strategy_hint": (
                    "simple_copy_trampoline_candidate"
                    if simple_safe
                    else "advanced_relocator_required"
                ),
                "abi_evidence": evidence,
            })
        item["candidates"] = candidates
        item["last_probe_status"] = (
            "evidence_collected" if candidates else "no_candidate_evidence"
        )

    out["abi_probe_note"] = report.get("note")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("libgame", type=Path)
    ap.add_argument("profile", type=Path)
    ap.add_argument("--objdump", type=Path)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--window", type=int, default=256)
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--updated-profile-out",
        type=Path,
        help="Write profile with ABI candidate evidence attached (still pending)",
    )
    args = ap.parse_args()

    try:
        report = probe_profile(
            args.libgame,
            args.profile,
            objdump_path=args.objdump,
            top=args.top,
            window=args.window,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        return 2

    payload = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload + "\n", encoding="utf-8")
    if args.updated_profile_out:
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        updated = attach_abi_evidence(profile, report)
        args.updated_profile_out.parent.mkdir(parents=True, exist_ok=True)
        args.updated_profile_out.write_text(
            json.dumps(updated, indent=2) + "\n",
            encoding="utf-8",
        )
    print(payload)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

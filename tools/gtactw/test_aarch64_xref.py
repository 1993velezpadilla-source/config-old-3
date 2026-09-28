#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aarch64_xref
import elf_probe


def align(value, n):
    return (value + n - 1) & ~(n - 1)


def encode_adrp(rd: int, pc: int, target: int) -> int:
    delta_pages = ((target & ~0xFFF) - (pc & ~0xFFF)) >> 12
    imm21 = delta_pages & ((1 << 21) - 1)
    immlo = imm21 & 0x3
    immhi = (imm21 >> 2) & 0x7FFFF
    return 0x90000000 | (immlo << 29) | (immhi << 5) | rd


def encode_adr(rd: int, pc: int, target: int) -> int:
    imm21 = (target - pc) & ((1 << 21) - 1)
    immlo = imm21 & 0x3
    immhi = (imm21 >> 2) & 0x7FFFF
    return 0x10000000 | (immlo << 29) | (immhi << 5) | rd


def encode_add(rd: int, rn: int, imm: int) -> int:
    return 0x91000000 | ((imm & 0xFFF) << 10) | (rn << 5) | rd


def encode_bl(pc: int, target: int) -> int:
    imm26 = ((target - pc) >> 2) & 0x03FFFFFF
    return 0x94000000 | imm26


def make_xref_fixture(path: Path):
    shstr = b"\0.shstrtab\0.dynstr\0.dynsym\0.text\0.rodata\0"

    def sno(name: bytes):
        return shstr.index(name)

    func = b"RenderWorldFrame"
    caller = b"MainLoopCaller"
    dynstr = b"\0" + func + b"\0" + caller + b"\0"
    func_off = dynstr.index(func)
    caller_off = dynstr.index(caller)

    cam = b"CameraFarClipDistance"
    world = b"WorldBlockStreamer"
    rodata = cam + b"\0" + world + b"\0"
    cam_va = 0x4000
    world_va = 0x4000 + len(cam) + 1

    text_words = [
        encode_adrp(0, 0x1000, cam_va),
        0xD503201F,  # nop: exercise non-adjacent ADRP+ADD recovery
        encode_add(0, 0, cam_va & 0xFFF),
        encode_adr(1, 0x100C, world_va),
        encode_bl(0x1010, 0x1000),
        0xD65F03C0,  # ret
    ]
    text = struct.pack("<6I", *text_words)

    sym0 = b"\0" * elf_probe.ELF64_SYM.size
    sym1 = elf_probe.ELF64_SYM.pack(
        func_off, 0x12, 0, 4, 0x1000, 16
    )
    sym2 = elf_probe.ELF64_SYM.pack(
        caller_off, 0x12, 0, 4, 0x1010, 8
    )
    dynsym = sym0 + sym1 + sym2

    cursor = elf_probe.ELF64_EHDR.size
    parts = {}
    for name, payload, al in (
        (".shstrtab", shstr, 1),
        (".dynstr", dynstr, 1),
        (".dynsym", dynsym, 8),
        (".text", text, 4),
        (".rodata", rodata, 1),
    ):
        cursor = align(cursor, al)
        parts[name] = (cursor, payload)
        cursor += len(payload)

    shoff = align(cursor, 8)
    sections = 6
    blob = bytearray(shoff + sections * elf_probe.ELF64_SHDR.size)

    ident = bytearray(16)
    ident[:4] = elf_probe.ELF_MAGIC
    ident[4] = elf_probe.ELFCLASS64
    ident[5] = elf_probe.ELFDATA2LSB
    ident[6] = 1

    hdr = elf_probe.ELF64_EHDR.pack(
        bytes(ident), 3, elf_probe.EM_AARCH64, 1,
        0, 0, shoff, 0,
        elf_probe.ELF64_EHDR.size, 0, 0,
        elf_probe.ELF64_SHDR.size, sections, 1,
    )
    blob[:len(hdr)] = hdr

    for off, payload in parts.values():
        blob[off:off + len(payload)] = payload

    shdrs = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (sno(b".shstrtab"), 3, 0, 0, parts[".shstrtab"][0], len(shstr), 0, 0, 1, 0),
        (sno(b".dynstr"), 3, 0, 0, parts[".dynstr"][0], len(dynstr), 0, 0, 1, 0),
        (sno(b".dynsym"), 11, 0, 0, parts[".dynsym"][0], len(dynsym), 2, 1, 8, elf_probe.ELF64_SYM.size),
        (sno(b".text"), 1, 0x6, 0x1000, parts[".text"][0], len(text), 0, 0, 4, 0),
        (sno(b".rodata"), 1, 0x2, 0x4000, parts[".rodata"][0], len(rodata), 0, 0, 1, 0),
    ]
    for i, sec in enumerate(shdrs):
        off = shoff + i * elf_probe.ELF64_SHDR.size
        blob[off:off + elf_probe.ELF64_SHDR.size] = elf_probe.ELF64_SHDR.pack(*sec)

    path.write_bytes(blob)


class Aarch64XrefTests(unittest.TestCase):
    def test_camera_and_streaming_xrefs(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libGame.so"
            make_xref_fixture(path)
            report = aarch64_xref.scan_libgame(path)

        self.assertEqual(report["xref_count"], 2)
        self.assertEqual(len(report["groups"]["camera"]), 1)
        self.assertEqual(len(report["groups"]["streaming"]), 1)
        self.assertEqual(
            report["groups"]["camera"][0]["function"],
            "RenderWorldFrame",
        )
        self.assertEqual(
            report["groups"]["streaming"][0]["function_rva"],
            0x1000,
        )
        self.assertEqual(
            report["groups"]["camera"][0]["form"],
            "adrp+add(+2)",
        )
        self.assertEqual(
            report["groups"]["streaming"][0]["form"],
            "adr",
        )
        neighborhood = report["candidate_call_neighborhoods"]["0x1000"]
        self.assertEqual(len(neighborhood["incoming"]), 1)
        self.assertEqual(
            neighborhood["incoming"][0]["caller"],
            "MainLoopCaller",
        )
        self.assertEqual(
            neighborhood["incoming"][0]["callee"],
            "RenderWorldFrame",
        )

    def test_decoder_rejects_other_instructions(self):
        self.assertIsNone(aarch64_xref.decode_adrp(0xD503201F, 0x1000))
        self.assertIsNone(aarch64_xref.decode_adr(0xD503201F, 0x1000))
        self.assertIsNone(aarch64_xref.decode_add_imm64(0xD65F03C0))
        self.assertIsNone(aarch64_xref.decode_bl(0xD65F03C0, 0x1000))
        self.assertEqual(
            aarch64_xref.decode_bl(encode_bl(0x1010, 0x1000), 0x1010),
            0x1000,
        )


if __name__ == "__main__":
    unittest.main()

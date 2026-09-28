#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aarch64_xref
import elf_probe
import plt_calls


def align(value, n):
    return (value + n - 1) & ~(n - 1)


def encode_bl(pc: int, target: int) -> int:
    imm26 = ((target - pc) >> 2) & 0x03FFFFFF
    return 0x94000000 | imm26


def make_fixture(path: Path):
    shstr = (
        b"\0.shstrtab\0.dynstr\0.dynsym\0.text\0.plt\0.rela.plt\0"
    )

    def sno(name: bytes):
        return shstr.index(name)

    draw = plt_calls.DRAW_FRAME_SYMBOL.encode()
    caller = b"UploadProjection"
    imported = b"glUniformMatrix4fv"
    dynstr = b"\0" + draw + b"\0" + caller + b"\0" + imported + b"\0"
    draw_off = dynstr.index(draw)
    caller_off = dynstr.index(caller)
    import_off = dynstr.index(imported)

    sym0 = b"\0" * elf_probe.ELF64_SYM.size
    sym1 = elf_probe.ELF64_SYM.pack(
        draw_off, 0x12, 0, 4, 0x1000, 8
    )
    sym2 = elf_probe.ELF64_SYM.pack(
        caller_off, 0x12, 0, 4, 0x1010, 8
    )
    sym3 = elf_probe.ELF64_SYM.pack(
        import_off, 0x12, 0, 0, 0, 0
    )
    dynsym = sym0 + sym1 + sym2 + sym3

    plt_addr = 0x3000
    plt_entry = plt_addr + 32
    text = struct.pack(
        "<IIIIII",
        encode_bl(0x1000, 0x1010),
        0xD65F03C0,
        0xD503201F,
        0xD503201F,
        encode_bl(0x1010, plt_entry),
        0xD65F03C0,
    )
    plt = b"\x00" * 48

    # Symbol index 3, relocation type 1026 (R_AARCH64_JUMP_SLOT).
    r_info = (3 << 32) | 1026
    rela = plt_calls.ELF64_RELA.pack(0x5000, r_info, 0)

    cursor = elf_probe.ELF64_EHDR.size
    parts = {}
    for name, payload, al in (
        (".shstrtab", shstr, 1),
        (".dynstr", dynstr, 1),
        (".dynsym", dynsym, 8),
        (".text", text, 4),
        (".plt", plt, 16),
        (".rela.plt", rela, 8),
    ):
        cursor = align(cursor, al)
        parts[name] = (cursor, payload)
        cursor += len(payload)

    shoff = align(cursor, 8)
    shnum = 7
    blob = bytearray(shoff + shnum * elf_probe.ELF64_SHDR.size)

    ident = bytearray(16)
    ident[:4] = elf_probe.ELF_MAGIC
    ident[4] = elf_probe.ELFCLASS64
    ident[5] = elf_probe.ELFDATA2LSB
    ident[6] = 1

    hdr = elf_probe.ELF64_EHDR.pack(
        bytes(ident), 3, elf_probe.EM_AARCH64, 1,
        0, 0, shoff, 0,
        elf_probe.ELF64_EHDR.size, 0, 0,
        elf_probe.ELF64_SHDR.size, shnum, 1,
    )
    blob[:len(hdr)] = hdr

    for off, payload in parts.values():
        blob[off:off + len(payload)] = payload

    sections = [
        (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        (sno(b".shstrtab"), 3, 0, 0, parts[".shstrtab"][0], len(shstr), 0, 0, 1, 0),
        (sno(b".dynstr"), 3, 0, 0, parts[".dynstr"][0], len(dynstr), 0, 0, 1, 0),
        (sno(b".dynsym"), 11, 0, 0, parts[".dynsym"][0], len(dynsym), 2, 1, 8, elf_probe.ELF64_SYM.size),
        (sno(b".text"), 1, 0x6, 0x1000, parts[".text"][0], len(text), 0, 0, 4, 0),
        (sno(b".plt"), 1, 0x6, plt_addr, parts[".plt"][0], len(plt), 0, 0, 16, 0),
        (sno(b".rela.plt"), plt_calls.SHT_RELA, 0, 0, parts[".rela.plt"][0], len(rela), 3, 0, 8, plt_calls.ELF64_RELA.size),
    ]
    for i, sec in enumerate(sections):
        off = shoff + i * elf_probe.ELF64_SHDR.size
        blob[off:off + elf_probe.ELF64_SHDR.size] = (
            elf_probe.ELF64_SHDR.pack(*sec)
        )

    path.write_bytes(blob)


class PltCallsTests(unittest.TestCase):
    def test_maps_gl_uniform_matrix_caller(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libGame.so"
            make_fixture(path)
            report = plt_calls.scan_plt_calls(path)

        self.assertEqual(report["interesting_import_count"], 1)
        self.assertEqual(report["call_count"], 1)
        item = report["groups"]["projection"][0]
        self.assertEqual(item["caller"], "UploadProjection")
        self.assertEqual(item["caller_rva"], 0x1010)
        self.assertEqual(item["import_symbol"], "glUniformMatrix4fv")
        self.assertEqual(item["plt_rva"], 0x3020)
        self.assertEqual(item["got_rva"], 0x5000)
        self.assertTrue(item["draw_frame_reachable"])
        self.assertEqual(item["draw_frame_hops"], 1)
        self.assertEqual(
            item["draw_frame_path_functions"],
            [plt_calls.DRAW_FRAME_SYMBOL, "UploadProjection"],
        )

    def test_import_categories(self):
        self.assertIn(
            "projection",
            plt_calls._import_category("glUniformMatrix4fv"),
        )
        self.assertIn(
            "render",
            plt_calls._import_category("glDrawElements"),
        )
        self.assertIn(
            "projection",
            plt_calls._import_category("glDepthRangef"),
        )
        self.assertIn(
            "projection",
            plt_calls._import_category("glViewport"),
        )
        self.assertIn(
            "visibility",
            plt_calls._import_category("glCullFace"),
        )
        self.assertEqual(
            plt_calls._import_category("malloc"),
            [],
        )


if __name__ == "__main__":
    unittest.main()

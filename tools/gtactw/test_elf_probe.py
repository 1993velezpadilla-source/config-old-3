#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elf_probe


def align(value, n):
    return (value + n - 1) & ~(n - 1)


def make_fixture(path: Path):
    shstr = b"\0.shstrtab\0.dynstr\0.dynsym\0.text\0.note.gnu.build-id\0"
    def sno(name: bytes):
        return shstr.index(name)

    jni = b"Java_com_rockstargames_oswrapper_GameNative_implOnDrawFrame"
    setup = b"Java_com_rockstargames_oswrapper_GameNative_implOnInitialSetup"
    cam = b"CameraFarClipDistance"
    dynstr = b"\0" + jni + b"\0" + setup + b"\0" + cam + b"\0"
    jni_off = dynstr.index(jni)
    setup_off = dynstr.index(setup)
    cam_off = dynstr.index(cam)

    sym0 = b"\0" * elf_probe.ELF64_SYM.size
    sym1 = elf_probe.ELF64_SYM.pack(jni_off, 0x12, 0, 4, 0x1000, 4)
    sym2 = elf_probe.ELF64_SYM.pack(cam_off, 0x12, 0, 4, 0x1004, 4)
    sym3 = elf_probe.ELF64_SYM.pack(setup_off, 0x12, 0, 4, 0x1008, 4)
    dynsym = sym0 + sym1 + sym2 + sym3
    text = b"\x1f\x20\x03\xd5\xc0\x03\x5f\xd6\x1f\x20\x03\xd5"
    build_id_bytes = bytes(range(1, 21))
    note = struct.pack("<III", 4, len(build_id_bytes), 3) + b"GNU\0" + build_id_bytes

    cursor = elf_probe.ELF64_EHDR.size
    parts = {}

    for name, payload, al in (
        (".shstrtab", shstr, 1),
        (".dynstr", dynstr, 1),
        (".dynsym", dynsym, 8),
        (".text", text, 4),
        (".note.gnu.build-id", note, 4),
    ):
        cursor = align(cursor, al)
        parts[name] = (cursor, payload)
        cursor += len(payload)

    shoff = align(cursor, 8)
    e_shnum = 6
    total = shoff + e_shnum * elf_probe.ELF64_SHDR.size
    blob = bytearray(total)

    ident = bytearray(16)
    ident[:4] = elf_probe.ELF_MAGIC
    ident[4] = elf_probe.ELFCLASS64
    ident[5] = elf_probe.ELFDATA2LSB
    ident[6] = 1

    hdr = elf_probe.ELF64_EHDR.pack(
        bytes(ident), 3, elf_probe.EM_AARCH64, 1,
        0, 0, shoff, 0,
        elf_probe.ELF64_EHDR.size, 0, 0,
        elf_probe.ELF64_SHDR.size, e_shnum, 1,
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
        (sno(b".note.gnu.build-id"), 7, 0, 0, parts[".note.gnu.build-id"][0], len(note), 0, 0, 4, 0),
    ]
    for i, sec in enumerate(sections):
        off = shoff + i * elf_probe.ELF64_SHDR.size
        blob[off:off + elf_probe.ELF64_SHDR.size] = elf_probe.ELF64_SHDR.pack(*sec)

    path.write_bytes(blob)
    return build_id_bytes.hex()


class ElfProbeTests(unittest.TestCase):
    def test_arm64_fixture_symbols_build_id_and_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "libGame.so"
            expected_build_id = make_fixture(path)
            report = elf_probe.inspect_elf(path)

        self.assertEqual(report["elf"]["machine"], "AArch64")
        self.assertEqual(report["elf"]["build_id"], expected_build_id)
        draw_name = "Java_com_rockstargames_oswrapper_GameNative_implOnDrawFrame"
        self.assertTrue(report["symbols"]["known_jni"][draw_name])
        self.assertEqual(
            report["symbols"]["known_jni_details"][draw_name]["value"],
            0x1000,
        )
        names = {
            x["name"]
            for x in report["symbols"]["candidate_groups"]["camera"]
            if x["source"] == "symbol"
        }
        self.assertIn("CameraFarClipDistance", names)
        self.assertEqual(report["text"]["size"], 12)

    def test_rejects_non_elf(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.so"
            path.write_bytes(b"not an elf")
            with self.assertRaises(ValueError):
                elf_probe.inspect_elf(path)

    def test_classify_streaming_and_player(self):
        self.assertIn("streaming", elf_probe.classify("WorldBlockStreamer"))
        self.assertIn("player_render", elf_probe.classify("PlayerSkeletonRender"))
        self.assertIn("camera", elf_probe.classify("uniform matProj"))
        self.assertIn("lod_culling", elf_probe.classify("DrawDistanceCull"))
        self.assertIn("player_render", elf_probe.classify("CharacterModelRender"))


if __name__ == "__main__":
    unittest.main()

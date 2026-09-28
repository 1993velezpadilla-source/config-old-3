#!/usr/bin/env python3
import json
import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elf_probe
import profile_template
import profile_verify_binary


def align(value, n):
    return (value + n - 1) & ~(n - 1)


def make_fixture(path: Path):
    shstr = b"\0.shstrtab\0.dynstr\0.dynsym\0.text\0.note.gnu.build-id\0"
    def sno(name: bytes):
        return shstr.index(name)

    prefix = b"Java_com_rockstargames_oswrapper_GameNative_"
    names = [
        prefix + b"implOnDrawFrame",
        prefix + b"implOnInitialSetup",
        prefix + b"implOnGamepadAxesChanged",
    ]
    dynstr = b"\0" + b"\0".join(names) + b"\0"
    name_offsets = [dynstr.index(name) for name in names]

    text = bytes(range(160))
    dynsym = b"\0" * elf_probe.ELF64_SYM.size
    for offset, rva in zip(name_offsets, (0x1000, 0x1010, 0x1020)):
        dynsym += elf_probe.ELF64_SYM.pack(
            offset, 0x12, 0, 4, rva, 16
        )

    build_id_bytes = bytes(range(1, 21))
    note = (
        struct.pack("<III", 4, len(build_id_bytes), 3)
        + b"GNU\0"
        + build_id_bytes
    )

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
    shnum = 6
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
        (sno(b".note.gnu.build-id"), 7, 0, 0, parts[".note.gnu.build-id"][0], len(note), 0, 0, 4, 0),
    ]
    for i, sec in enumerate(sections):
        off = shoff + i * elf_probe.ELF64_SHDR.size
        blob[off:off + elf_probe.ELF64_SHDR.size] = elf_probe.ELF64_SHDR.pack(*sec)

    path.write_bytes(blob)
    return text


def make_profile(libgame: Path, text: bytes) -> dict:
    report = elf_probe.inspect_elf(libgame)
    targets = {
        "camera_update": 0x1040,
        "projection_setup": 0x1050,
        "world_stream_update": 0x1060,
        "sector_visibility": 0x1070,
        "lod_test": 0x1080,
        "player_render": 0x1090,
    }
    verification = {}
    for key, rva in targets.items():
        start = rva - 0x1000
        verification[key] = {
            "status": "verified",
            "rva": rva,
            "evidence": [
                {
                    "method": "fixture",
                    "detail": f"verified {key}",
                }
            ],
            "code_prefix_hex": text[start:start + 16].hex(),
        }

    return {
        "fingerprint": {
            "sha256": report["sha256"],
            "text_sha256": report["text"]["sha256"],
            "gnu_build_id": report["elf"]["build_id"],
            "jni_rvas": {
                "implOnDrawFrame": 0x1000,
                "implOnInitialSetup": 0x1010,
                "implOnGamepadAxesChanged": 0x1020,
            },
        },
        "patch_targets_rva": targets,
        "target_verification": verification,
    }


class ProfileVerifyBinaryTests(unittest.TestCase):
    def test_exact_binary_profile_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame = root / "libGame.so"
            profile_path = root / "profile.json"
            text = make_fixture(libgame)
            profile_path.write_text(
                json.dumps(make_profile(libgame, text)),
                encoding="utf-8",
            )

            result = profile_verify_binary.verify_profile(
                libgame,
                profile_path,
            )

        self.assertTrue(result["ok"])
        self.assertTrue(all(result["checks"].values()))
        self.assertTrue(result["targets"]["player_render"]["prefix_match"])

    def test_one_byte_target_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            libgame = root / "libGame.so"
            profile_path = root / "profile.json"
            text = make_fixture(libgame)
            profile = make_profile(libgame, text)
            profile["target_verification"]["camera_update"][
                "code_prefix_hex"
            ] = "ff" + profile["target_verification"]["camera_update"][
                "code_prefix_hex"
            ][2:]
            profile_path.write_text(
                json.dumps(profile),
                encoding="utf-8",
            )

            result = profile_verify_binary.verify_profile(
                libgame,
                profile_path,
            )

        self.assertFalse(result["ok"])
        self.assertFalse(result["targets"]["camera_update"]["prefix_match"])
        self.assertTrue(result["targets"]["projection_setup"]["prefix_match"])


if __name__ == "__main__":
    unittest.main()

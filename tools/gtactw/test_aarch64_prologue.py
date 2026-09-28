#!/usr/bin/env python3
import struct
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aarch64_prologue


def words(*values: int) -> bytes:
    return struct.pack("<" + "I" * len(values), *values)


class Aarch64PrologueTests(unittest.TestCase):
    def test_safe_stack_prologue(self):
        raw = words(
            0xA9BF7BFD,  # stp x29, x30, [sp, #-16]!
            0x910003FD,  # mov x29, sp
            0xD10083FF,  # sub sp, sp, #0x20
            0xF9000BF3,  # str x19, [sp, #0x10]
        )
        report = aarch64_prologue.analyze_bytes(raw, 0x4000)
        self.assertTrue(report["simple_copy_trampoline_safe"])
        self.assertTrue(
            all(
                x["relocatable_for_simple_copy"]
                for x in report["instructions"]
            )
        )

    def test_rejects_pc_relative_adrp(self):
        raw = words(
            0xA9BF7BFD,
            0x90000000,  # adrp x0, ...
            0x910003FD,
            0xD10083FF,
        )
        report = aarch64_prologue.analyze_bytes(raw, 0x5000)
        self.assertFalse(report["simple_copy_trampoline_safe"])
        self.assertEqual(report["instructions"][1]["kind"], "adrp")

    def test_rejects_branches_and_literal_loads(self):
        dangerous = {
            "b": 0x14000000,
            "bl": 0x94000000,
            "b.cond": 0x54000000,
            "cbz/cbnz": 0xB4000000,
            "tbz/tbnz": 0x36000000,
            "literal-load": 0x58000000,
            "ret": 0xD65F03C0,
            "br": 0xD61F0000,
            "blr": 0xD63F0000,
        }
        for expected, insn in dangerous.items():
            with self.subTest(expected=expected):
                kind, safe, _ = aarch64_prologue.classify_instruction(insn)
                self.assertEqual(kind, expected)
                self.assertFalse(safe)

    def test_requires_exactly_16_bytes(self):
        with self.assertRaises(ValueError):
            aarch64_prologue.analyze_bytes(b"\0" * 12, 0x6000)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Read-only binary audit of published Black Ops Zombies Android APK.

No retail assets are exported. Examines APK envelope, ELF class/machine and
embedded Marmalade .s3e metadata. It does NOT imply running game on a device.
"""
import argparse
import hashlib
import json
import re
import struct
import zipfile
from collections import defaultdict
from pathlib import Path

ARM = {40: "EM_ARM (32-bit)", 183: "EM_AARCH64 (64-bit)", 3: "EM_386", 62: "EM_X86_64"}

def detect_elf(buf):
    if len(buf) < 20 or buf[:4] != b"\x7fELF":
        return {"kind": "not_elf"}
    little = buf[5] == 1
    if buf[5] not in (1, 2):
        return {"kind": "bad_elf_endianness"}
    e_machine = struct.unpack("<H" if little else ">H", buf[18:20])[0]
    return {
        "kind": "ELF",
        "class": "ELF32" if buf[4] == 1 else "ELF64" if buf[4] == 2 else "unknown",
        "machine": ARM.get(e_machine, str(e_machine)),
        "e_machine": e_machine,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apk", type=Path)
    ap.add_argument("--out", type=Path, default=Path("boz-apk-audit.json"))
    opts = ap.parse_args()
    zip_path = opts.apk
    if not zipfile.is_zipfile(zip_path):
        raise SystemExit("NOT_AN_APK: ZIP signature invalid")
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    report = {
        "apk_filename": zip_path.name,
        "size_bytes": zip_path.stat().st_size,
        "sha256": digest,
        "native_libraries": [],
        "other_files": {},
        "native_abis": [],
        "embedded_s3e_elf_headers": [],
        "not_verified": [
            "no Pixel Fold or Android device run",
            "no actual gameplay, ADS, maps, sound or co-op test",
            "s3e native executable bitness not proven if compressed or encrypted",
        ],
    }
    abi = defaultdict(list)
    with zipfile.ZipFile(zip_path) as z:
        for f in z.infolist():
            if f.filename.startswith("lib/") and f.filename.endswith(".so"):
                parts = f.filename.split("/")
                if len(parts) != 3:
                    continue
                with z.open(f) as file:
                    header = file.read(64)
                result = {"path": f.filename, "bytes": f.file_size}
                result.update(detect_elf(header))
                report["native_libraries"].append(result)
                abi[parts[1]].append(result)
            elif f.filename.endswith((".s3e", ".dz", ".icf")):
                report["other_files"][f.filename] = {"bytes": f.file_size}
                if f.filename.endswith(".s3e"):
                    # A raw ELF marker would be meaningful; absence proves nothing
                    # because Marmalade compresses/encrypts the executable payload.
                    raw = z.read(f.filename)
                    signatures = []
                    offset = 0
                    while (found := raw.find(b"\x7fELF", offset)) >= 0:
                        signatures.append({"offset": found, **detect_elf(raw[found:found + 64])})
                        offset = found + 4
                        if len(signatures) == 20:
                            break
                    report["embedded_s3e_elf_headers"].extend(signatures)
                    report["other_files"][f.filename]["prefix_hex"] = raw[:24].hex()
    report["native_abis"] = sorted(abi)
    has_arm64 = "arm64-v8a" in abi
    arm64_elf_ok = all(
        x["kind"] == "ELF" and x["class"] == "ELF64" and x["e_machine"] == 183
        for x in abi.get("arm64-v8a", [])
    )
    report["apk_64_bit_native_abi_present"] = has_arm64
    report["apk_arm64_native_elf_headers_valid"] = bool(has_arm64 and arm64_elf_ok)
    report["arm32_abi_present"] = "armeabi-v7a" in abi or "armeabi" in abi
    report["critical_limit"] = (
        "Android ARM64 native wrapper presence does not prove the original "
        "Marmalade boz.s3e executable payload is AArch64."
    )
    report["can_assert_original_game_playable"] = False
    opts.out.parent.mkdir(parents=True, exist_ok=True)
    opts.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print("APK_SHA256=" + digest)
    print("NATIVE_ABIS=" + ",".join(report["native_abis"]))
    print("ARM64_ELF_WRAPPER=" + ("PRESENT_AND_VALID" if report["apk_arm64_native_elf_headers_valid"] else "MISSING_OR_INVALID"))
    print("S3E_PACKED_FILES=" + ",".join(x for x in report["other_files"] if x.endswith(".s3e")))
    print("S3E_RAW_ELF_HEADERS=" + str(len(report["embedded_s3e_elf_headers"])))
    print("ORIGINAL_BOZ_GAMEPLAY_ON_ANDROID_ARM64=UNVERIFIED")
    print("FULL_REPORT=" + str(opts.out))

if __name__ == "__main__":
    main()

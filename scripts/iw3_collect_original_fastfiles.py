#!/usr/bin/env python3
"""Read the owner's multipart original COD4 PC archive, extracting selected FFs.

This is a temporary test-only tool. Do NOT commit, upload, or republish extracted
Activision game assets. Only print file-count/size/hash metadata to CI logs.
"""
from __future__ import annotations
import bisect
import hashlib
import json
from pathlib import Path
import sys
import zipfile

PREFIX = "Call of Duty 4 Modern Warfare/"
NEEDED = (
    "zone/spanish/common.ff",
    "zone/spanish/code_post_gfx.ff",
)
EXPECTED_PART_SIZES = (1887436800, 1887436800, 1887436800, 1359075957)

class SplitReader:
    def __init__(self, paths):
        if len(paths) != 4:
            raise ValueError("Expected four exact original COD4 ZIP parts")
        self.files = [p.open("rb") for p in paths]
        self.limits = [0]
        for p, expected in zip(paths, EXPECTED_PART_SIZES):
            if p.stat().st_size != expected:
                raise ValueError(f"Wrong source-archive part size: {p.name}")
            self.limits.append(self.limits[-1] + expected)
        self.pos = 0

    def seek(self, offset, whence=0):
        if whence == 1: offset += self.pos
        if whence == 2: offset += self.limits[-1]
        if not 0 <= offset <= self.limits[-1]:
            raise ValueError("Seek outside original ZIP archive")
        self.pos = offset
        return offset

    def tell(self):
        return self.pos

    def seekable(self):
        return True

    def readable(self):
        return True

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.limits[-1] - self.pos
        n = min(n, self.limits[-1] - self.pos)
        pieces = []
        while n:
            ix = bisect.bisect_right(self.limits, self.pos)-1
            k = min(n,self.limits[ix+1]-self.pos)
            self.files[ix].seek(self.pos-self.limits[ix])
            chunk=self.files[ix].read(k)
            if not chunk: break
            pieces.append(chunk)
            self.pos += len(chunk)
            n -= len(chunk)
        return b"".join(pieces)

    def close(self):
        for f in self.files: f.close()

def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: iw3_collect_original_fastfiles.py <parts dir> <TEMP output>")
    part_dir = Path(sys.argv[1])
    output = Path(sys.argv[2])
    paths = [part_dir / f"C4-Mocs.zip.part-{i:03d}" for i in range(4)]
    output.mkdir(parents=True,exist_ok=True)
    reader = SplitReader(paths)
    try:
        with zipfile.ZipFile(reader,"r",allowZip64=True) as outer:
            entries = [x for x in outer.infolist() if not x.is_dir()]
            # Validate the real corpus before extraction, not just a decoy ZIP.
            if len(entries)<200:
                raise ValueError("Unexpectedly small COD4 package")
            report = {"outer_entries":len(entries),
                      "original_total_size":reader.limits[-1], "extracted_ff":[]}
            for rel in NEEDED:
                zi = outer.getinfo(PREFIX+rel)
                if zi.file_size < 1024:
                    raise ValueError("Invalid original fastfile: "+rel)
                # Extraction path is fixed by us, not a potentially unsafe ZIP filename.
                p = output/rel
                p.parent.mkdir(parents=True,exist_ok=True)
                dig=hashlib.sha256()
                with outer.open(zi) as src, p.open("wb") as dst:
                    while True:
                        buf=src.read(8*1024*1024)
                        if not buf: break
                        dig.update(buf)
                        dst.write(buf)
                report["extracted_ff"].append({"name":rel,"size":zi.file_size,
                                                "sha256":dig.hexdigest()})
            print(json.dumps(report,indent=2))
            # Intentionally no ZIP contents in the JSON report.
    finally:
        reader.close()

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Extract unchanged BO1 DB_AllocXBlocks from original PC engine.
The source is kept in the ephemeral runner, not published as redistributed code.
"""
import argparse, hashlib, json, re
from pathlib import Path
PIN="102f6992be332610aff587e681e3180b15f395bb"
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--upstream",required=True)
    a.add_argument("--staged",required=True)
    opts=a.parse_args()
    src=(Path(opts.upstream)/"src/database/db_memory.cpp").read_text()
    a1=src.index("const char *g_block_mem_name[7] =")
    a2=src.index("void __cdecl DB_AllocXBlocks(",a1)
    begin=a2
    # Take the complete real original function, no textual rewrites.
    m=re.search(r"\n}\n",src[begin:])
    assert m, "DB_AllocXBlocks body not recovered"
    ending=begin+m.end()
    text=src[a1:ending]
    assert "g_block_mem_type[7]" in text
    assert "buf.data = DB_MemAlloc(" in text
    assert "blocks[blockIndex] = buf;" in text
    assert "for ( blockIndex = 0; blockIndex < 7; ++blockIndex )" in text
    out=Path(opts.staged);out.mkdir(parents=True,exist_ok=True)
    header='#include "bo1_alloc_compat.h"\n// Original BO1 C++ global tables and unchanged allocation function:\n'
    (out/"original_bo1_db_alloc.cpp").write_text(header+text+"\n")
    manifest={"source":"src/database/db_memory.cpp","upstream_sha":PIN,
             "exact_original_body":True,
             "body_sha256":hashlib.sha256(text.encode()).hexdigest(),
             "incomplete_port_warning":"Original BO1 DB_MemAlloc and XAsset type pointer relocation are NOT ported"}
    (out/"alloc-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("REAL_BO1_DB_ALLOCXBLOCKS_EXTRACTED_UNCHANGED=PASS")
if __name__=="__main__":main()

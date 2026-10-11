#!/usr/bin/env python3
"""Extract exact DB_FileExists and DB_FileSize functions from PINNED BO1 engine.
Only stage in ephemeral CI environment; never distribute original source.
"""
import argparse
import hashlib
import json
from pathlib import Path
SOURCE_SHA="102f6992be332610aff587e681e3180b15f395bb"
FUNCTIONS=("DB_FileSize","DB_FileExists")
def extract(src, function):
    import re
    # Whole-line function start prevents picking a call/prototype.
    p=re.compile(r"^(?:int|char) __cdecl "+re.escape(function)+r"\([^\n]*\)\s*\{",re.M)
    m=p.search(src)
    assert m, f"Missing upstream function: {function}"
    # Original code uses column-zero closing brace for functions.
    end=src.find("\n}\n",m.start())
    assert end >=0, f"Bad function end: {function}"
    body=src[m.start():end+2]
    assert body.count("CreateFileA")==1, f"Code changed: {function}"
    assert "return" in body
    return body
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--upstream",required=True)
    p.add_argument("--staged",required=True)
    a=p.parse_args()
    origin=Path(a.upstream)/"src/database/db_registry.cpp"
    src=origin.read_text()
    extracted=[extract(src,f) for f in FUNCTIONS]
    Path(a.staged).mkdir(parents=True,exist_ok=True)
    (Path(a.staged)/"original_bo1_db_file.cpp").write_text(
      '#include "bo1_ff_compat.h"\n'
      "// ORIGINAL BO1 source function bodies below were copied without any changes.\n\n"
      +"\n\n".join(extracted)+"\n")
    manifest={"upstream_sha":SOURCE_SHA,
        "source_file":"src/database/db_registry.cpp",
        "scope":"ONLY two exact original BO1 file discovery functions; other engine source excluded",
        "original_function_bodies_unchanged":True,
        "function_sha256":{name:hashlib.sha256(body.encode()).hexdigest()
            for name,body in zip(FUNCTIONS,extracted)}}
    (Path(a.staged)/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("PINNED_REAL_BO1_DB_FILESOURCE_EXTRACTION=PASS")
if __name__=="__main__":main()

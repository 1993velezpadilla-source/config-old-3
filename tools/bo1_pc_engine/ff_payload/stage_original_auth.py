#!/usr/bin/env python3
"""Extract the *exact* DB_AuthLoad_InflateInit from pinned original BO1 recovered source.

This is the actual authenticated/unsecured fastfile zlib entrypoint called by
DB_LoadXFileInternal. Original function body is never modified or distributed.
"""
import argparse, hashlib, json, re
from pathlib import Path
PIN="102f6992be332610aff587e681e3180b15f395bb"
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--upstream",required=True)
    p.add_argument("--staged",required=True)
    args=p.parse_args()
    original=(Path(args.upstream)/"src/database/db_auth.cpp").read_text()
    names = [
        ("DB_AuthLoad_InflateInit",r"^int __cdecl DB_AuthLoad_InflateInit\(z_stream_s \*stream, bool isSecure\)\s*\{"),
        ("DB_AuthLoad_Inflate",r"^int __cdecl DB_AuthLoad_Inflate\(z_stream_s \*stream, int flush\)\s*\{"),
        ("DB_AuthLoad_InflateEnd",r"^void __cdecl DB_AuthLoad_InflateEnd\(z_stream_s \*stream\)\s*\{"),
    ]
    exacts = []
    for name,pat in names:
        m=re.search(pat,original,re.M)
        assert m, "missing original BO1 auth function: "+name
        end=original.find("\n}\n",m.start())
        assert end>m.start(),"could not isolate "+name
        exacts.append(original[m.start():end+2])
    assert 'inflateInit_(stream, "1.2.3", sizeof(z_stream_s))' in exacts[0]
    assert "Assert_MyHandler" in exacts[0]
    assert "return inflate(stream, flush)" in exacts[1]
    assert "inflateEnd(stream)" in exacts[2]
    out=Path(args.staged);out.mkdir(parents=True,exist_ok=True)
    prelude="""#include <zlib.h>
#ifndef __cdecl
#define __cdecl
#endif
#ifndef __debugbreak
#define __debugbreak() __builtin_trap()
#endif
bool Assert_MyHandler(const char *filename, int line, int type, const char *format, ...);
// Original decompiled Black Ops 1 function, exact text below.
"""
    (out/"original_bo1_db_auth_inflate.cpp").write_text(prelude+"\n\n".join(exacts)+"\n")
    manifest={"upstream_sha":PIN,"source_file":"src/database/db_auth.cpp",
         "functions":[name for name,_ in names],
         "original_body_unchanged":True,
         "function_sha256":{name:hashlib.sha256(body.encode()).hexdigest() for (name,_),body in zip(names,exacts)},
         "scope":"Original engine zlib init, inflate and end, not full BO1 asset parsing"}
    (out/"auth-extraction.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print("EXACT_ORIGINAL_BO1_INFLATE_INIT_DECODE_END_EXTRACTION=PASS")
if __name__=="__main__":main()

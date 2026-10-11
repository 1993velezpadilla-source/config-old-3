#!/usr/bin/env python3
"""Read-only feasibility audit for adapting the real BO1 PC engine to Android.
Never copies the decompiled game engine or retail game files into an artifact.
"""
import argparse
import json
import os
import re
from pathlib import Path

UPSTREAM = "MisaDev4/bo1-zombies-decompiled"
PINNED_COMMIT = "102f6992be332610aff587e681e3180b15f395bb"

def finding(code, description, observed, path, impact):
    return {"id": code, "description": description, "observed": bool(observed),
            "evidence": path, "impact": impact}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True)
    parser.add_argument("--output",required=True)
    parser.add_argument("--cmake-log",default="")
    parser.add_argument("--probe-dir",default="")
    args=parser.parse_args()
    src=Path(args.source)
    cmake=(src/"CMakeLists.txt").read_text(errors="replace")
    setup=(src/"setup.ps1").read_text(errors="replace")
    allcpp=list(src.rglob("*.cpp"))
    allh=list(src.rglob("*.h"))
    gsc=list(src.rglob("*.gsc"))
    csfiles=list(src.rglob("*.csc"))
    windowsfiles=list((src/"src"/"win32").rglob("*")) if (src/"src"/"win32").is_dir() else []
    dxfiles=list((src/"src"/"gfx_d3d").rglob("*.cpp"))
    liblinks=re.findall(r"\b(?:d3d9\.lib|d3d9|d3dx9\.lib|d3dx9d?\.lib|dsound\.lib|xinput\.lib|steam_api\.lib|ws2_32\.lib|binkw32\.lib)\b",cmake,re.I)
    blocking = [
        finding("B01","CMake forces Windows 32-bit target",all(x in cmake for x in ['WIN32','/machine:x86']),"CMakeLists.txt","Requires Android ARM64 build target and ABI cleanups"),
        finding("B02","Renderer and audio depend on DirectX 9 / Windows SDK",
                "d3d9.lib" in cmake and "DXSDK_DIR" in cmake,
                "CMakeLists.txt; src/gfx_d3d/","Requires Android graphics/audio backend, not only a recompile"),
        finding("B03","Windows-specific source and platform code",
                bool(windowsfiles),"src/win32/","Must replace Win32 windowing/input/file/thread APIs"),
        finding("B04","Requires retail PC Black Ops assets",
                "GameDir" in setup and "zone" in setup and "main" in setup,
                "setup.ps1","No maps/textures/audio included; external assets necessary"),
        finding("B05","No existing Android entrypoint or project",
                not (src/"app"/"build.gradle").exists() and not list(src.rglob("AndroidManifest.xml")),
                "project root","Needs Android Activity + NDK lifecycle/input/audio integration"),
        finding("B06","Project uses Windows-only MSVC flags",
                "/MT" in cmake and "/d1trimfile" in cmake,
                "CMakeLists.txt","Requires compiler portability changes"),
    ]
    cmake_log=Path(args.cmake_log).read_text(errors="replace") if args.cmake_log and Path(args.cmake_log).exists() else ""
    probes=[]
    for srcfile in ["src/game/actor_navigation.cpp","src/bgame/bg_misc.cpp",
                    "src/physics/phys_collision.cpp","src/gfx_d3d/r_bsp.cpp"]:
        basename=srcfile.replace("/","_").replace(".cpp",".txt")
        p=Path(args.probe_dir)/basename if args.probe_dir else Path("/nonexistent")
        raw=p.read_text(errors="replace") if p.exists() else ""
        errors=[line.strip() for line in raw.splitlines() if "error:" in line]
        # Keep compiler message only, exclude decompiled source lines and snippets.
        brief=[line.split("error:",1)[-1].strip()[:190] for line in errors[:2]]
        probes.append({"file":srcfile,"result":"ERROR" if errors else ("UNTESTED" if not raw else "NO_ERROR"),
                       "error_messages":brief})
    cmake_errors=[line.strip()[:220] for line in cmake_log.splitlines() if re.search(r"CMake Error|does not support platform|error:|unknown platform",line,re.I)][:10]
    report={
        "scope":"Genuine Black Ops 1 Zombies PC engine -> Android ARM64, NOT Marmalade mobile port",
        "upstream_repository":UPSTREAM,
        "upstream_pinned_commit":PINNED_COMMIT,
        "game_source_copied_into_report":False,
        "retail_assets_included":False,
        "apk_produced":False,
        "source_inventory":{"cpp_count":len(allcpp),"header_count":len(allh),
                            "gsc_scripts":len(gsc),"csc_scripts":len(csfiles),
                            "windows_entries":len(windowsfiles),"directx_cpp_files":len(dxfiles)},
        "build_system":{"generator":"Windows/MSVC x86","linked_windows_libraries":sorted(set(liblinks)),
                        "android_cmake_configure":"FAILED" if cmake_errors else "CHECK_RAW_RUN_LOG",
                        "cmake_errors":cmake_errors},
        "blockers":blocking,
        "android_ndk_cpp_probes":probes,
        "verdict":"NOT_DIRECTLY_ANDROID_ARM64_BUILDABLE",
        "next_verified_work":"Separate engine/platform code. Prove a real upstream engine module compiles for ARM64, then replace platform/render/audio dependencies; never substitute a new FPS.",
        "note":"A GREEN audit means blockers proven, NOT that BO1 runs on Android."
    }
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    (output/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    lines=[
        "# BO1 PC Original Engine — Android ARM64 Feasibility Audit",
        "",
        f"Upstream: {UPSTREAM}, SHA: {PINNED_COMMIT}",
        "",
        "**Status: not directly buildable for Android ARM64. No APK was produced.**",
        "",
        "## Real source inventory",
        "",
        *(f"- {k}: **{v}**" for k,v in report["source_inventory"].items()),
        "",
        "## Blocking original platform dependencies",
        ""
    ]
    lines += [f"- {'FOUND' if f['observed'] else 'NOT FOUND'} — {f['id']}: {f['description']} ({f['evidence']}). {f['impact']}."
              for f in blocking]
    lines += ["", "## Actual Android NDK compile probes", ""]
    for p in probes:
        lines.append(f"- {p['file']}: **{p['result']}**"
                     + (" — "+"; ".join(p["error_messages"]) if p["error_messages"] else ""))
    lines+=["", "## NDK CMake configure diagnostics", ""]
    lines += [f"- {line}" for line in cmake_errors] or ["- No direct diagnostic captured; check job state."]
    lines += ["", "**GREEN here means only that the audit completed. Game APK is NOT ready.**",""]
    (output/"report.md").write_text("\n".join(lines))
    print(json.dumps({"verdict":report["verdict"],"counts":report["source_inventory"],
                      "cmake_errors":cmake_errors,"probes":probes},indent=2))
if __name__=="__main__":
    main()

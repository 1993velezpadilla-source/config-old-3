#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LOCK=HERE/"texture_runtimes.lock.json"
DEFAULT_ROOT=ROOT/".hayuya"/"runtimes"


def load_lock()->dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def platform_key()->str:
    system=platform.system().lower()
    machine=platform.machine().lower()
    if system=="linux" and machine in {"x86_64","amd64"}:
        return "linux-x86_64"
    raise RuntimeError(
        f"no pinned Real-ESRGAN runtime for platform: {system}-{machine}"
    )


def runtime_spec()->tuple[dict,dict]:
    entry=load_lock()["runtimes"]["realesrgan-ncnn-vulkan"]
    key=platform_key()
    asset=entry["assets"].get(key)
    if asset is None:
        raise RuntimeError(f"no runtime asset for {key}")
    return entry,asset


def install_dir(root:Path,entry:dict)->Path:
    return root/"realesrgan-ncnn-vulkan"/entry["version"]


def payload_dir(root:Path,entry:dict,asset:dict)->Path:
    base=install_dir(root,entry)
    archive_root=str(asset.get("archive_root") or "").strip().strip("/")
    return base/archive_root if archive_root else base


def executable_path(root:Path=DEFAULT_ROOT)->Path|None:
    try:
        entry,asset=runtime_spec()
    except RuntimeError:
        return None
    path=payload_dir(root,entry,asset)/asset["executable"]
    return path if path.is_file() else None


def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def download(url:str,target:Path)->None:
    request=urllib.request.Request(
        url,
        headers={"User-Agent":"HAYUYA-texture-runtime/1"},
    )
    with urllib.request.urlopen(request,timeout=120) as response, target.open("wb") as out:
        shutil.copyfileobj(response,out,1024*1024)


def required_model_files(exe:Path)->list[Path]:
    model_dir=exe.parent/"models"
    return [
        model_dir/"realesrgan-x4plus.param",
        model_dir/"realesrgan-x4plus.bin",
    ]


def runtime_complete(exe:Path)->tuple[bool,str|None]:
    missing=[str(path) for path in required_model_files(exe) if not path.is_file()]
    if missing:
        return False,"missing_model_files:"+",".join(missing)
    return True,None


def smoke_test(exe:Path)->tuple[bool,str]:
    try:
        proc=subprocess.run(
            [str(exe),"-h"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        text=(proc.stdout or "")+"\n"+(proc.stderr or "")
        lower=text.lower()
        ok=any(marker in lower for marker in ("usage","realesrgan","input-path"))
        if not ok:
            return False,text.strip()[-2000:]
        complete,detail=runtime_complete(exe)
        if not complete:
            return False,detail or "runtime_incomplete"
        return True,text.strip()[-2000:]
    except Exception as exc:
        return False,f"{type(exc).__name__}:{exc}"


def install(root:Path=DEFAULT_ROOT)->Path:
    entry,asset=runtime_spec()
    dst=install_dir(root,entry)
    exe=payload_dir(root,entry,asset)/asset["executable"]
    if exe.is_file():
        ok,_=smoke_test(exe)
        if ok:
            print(
                f"HAYUYA_TEXTURE_RUNTIME_READY realesrgan-ncnn-vulkan "
                f"version={entry['version']} exe={exe}"
            )
            return exe

    root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hayuya-realesrgan-") as tmp:
        tmp_path=Path(tmp)
        archive=tmp_path/"runtime.zip"
        download(asset["url"],archive)
        actual=sha256(archive)
        expected=str(asset["sha256"]).lower()
        if actual.lower()!=expected:
            raise RuntimeError(
                f"runtime_sha256_mismatch:expected={expected}:actual={actual}"
            )

        extract=tmp_path/"extract"
        extract.mkdir()
        with zipfile.ZipFile(archive) as zf:
            names=zf.namelist()
            archive_root=str(asset.get("archive_root") or "").strip().strip("/")
            prefix=archive_root+"/" if archive_root else ""
            if not names or any(
                name.startswith("/")
                or ".." in PurePosixPath(name.replace("\\","/")).parts
                for name in names
            ):
                raise RuntimeError("unsafe_runtime_archive_paths")
            if prefix and not any(name.startswith(prefix) for name in names):
                raise RuntimeError("runtime_archive_root_missing")
            zf.extractall(extract)

        staged_root=extract/archive_root if archive_root else extract
        staged=staged_root/asset["executable"]
        if not staged.is_file():
            raise RuntimeError("runtime_executable_missing")
        staged.chmod(staged.stat().st_mode|stat.S_IXUSR|stat.S_IXGRP|stat.S_IXOTH)

        if dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.move(str(extract),str(dst))

    exe=payload_dir(root,entry,asset)/asset["executable"]
    ok,detail=smoke_test(exe)
    if not ok:
        shutil.rmtree(dst,ignore_errors=True)
        raise RuntimeError("runtime_smoke_test_failed:"+detail.replace("\n"," ")[:500])

    print(
        f"HAYUYA_TEXTURE_RUNTIME_READY realesrgan-ncnn-vulkan "
        f"version={entry['version']} sha256={asset['sha256']} exe={exe}"
    )
    return exe


def verify(root:Path=DEFAULT_ROOT)->bool:
    entry,asset=runtime_spec()
    exe=executable_path(root)
    if exe is None:
        print("MISSING realesrgan-ncnn-vulkan")
        return False
    ok,detail=smoke_test(exe)
    print(
        f"{'PASS' if ok else 'FAIL'} realesrgan-ncnn-vulkan "
        f"version={entry['version']} exe={exe}"
    )
    if not ok and detail:
        print(detail)
    return ok


def main()->int:
    p=argparse.ArgumentParser(description="Install/verify pinned HAYUYA texture runtimes.")
    p.add_argument("--root",type=Path,default=DEFAULT_ROOT)
    p.add_argument("--install",action="store_true")
    p.add_argument("--verify",action="store_true")
    p.add_argument("--print-env",action="store_true")
    a=p.parse_args()

    if a.install:
        exe=install(a.root)
        if a.print_env:
            print(f"export HAYUYA_REALESRGAN={exe}")
        return 0
    if a.verify:
        return 0 if verify(a.root) else 2

    exe=executable_path(a.root)
    if exe is not None:
        print(str(exe))
        return 0
    return 2


if __name__=="__main__":
    raise SystemExit(main())

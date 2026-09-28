#!/usr/bin/env python3
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import zipfile

TRACKED_EXTS = {
    ".pak", ".ucas", ".utoc", ".uasset", ".uexp", ".ubulk", ".umap",
    ".locres", ".bin", ".json", ".ini", ".cfg", ".txt", ".wav", ".ogg",
    ".wem", ".bnk", ".mp4", ".bk2", ".png", ".jpg", ".jpeg", ".dds",
}

def norm(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")

def summarize(paths, sizes):
    ext_counts = collections.Counter()
    ext_bytes = collections.Counter()
    top_dirs = collections.Counter()
    lower_seen = {}
    case_collisions = []
    basenames = collections.defaultdict(list)
    cohorts = collections.defaultdict(set)

    files = []
    total_bytes = 0
    for raw, size in zip(paths, sizes):
        p = norm(raw)
        if not p or p.endswith("/"):
            continue
        files.append(p)
        total_bytes += int(size)
        suffix = Path(p).suffix.lower()
        ext_counts[suffix or "<none>"] += 1
        ext_bytes[suffix or "<none>"] += int(size)
        top_dirs[p.split("/", 1)[0]] += 1

        low = p.lower()
        prior = lower_seen.get(low)
        if prior is not None and prior != p:
            case_collisions.append([prior, p])
        else:
            lower_seen[low] = p

        basenames[Path(p).name.lower()].append(p)

        if suffix in {".pak", ".utoc", ".ucas"}:
            cohorts[str(Path(p).with_suffix(""))].add(suffix)

    duplicate_basenames = {
        k: v for k, v in basenames.items() if len(v) > 1
    }

    maps = [p for p in files if Path(p).suffix.lower() == ".umap"]
    assets = [p for p in files if Path(p).suffix.lower() == ".uasset"]
    containers = [p for p in files if Path(p).suffix.lower() in {".pak", ".utoc", ".ucas"}]
    audio = [p for p in files if Path(p).suffix.lower() in {".wav", ".ogg", ".wem", ".bnk"}]
    localization = [p for p in files if Path(p).suffix.lower() == ".locres"]

    return {
        "fileCount": len(files),
        "declaredBytes": total_bytes,
        "extensionCounts": dict(sorted(ext_counts.items())),
        "extensionBytes": dict(sorted(ext_bytes.items())),
        "topLevelEntries": dict(top_dirs.most_common()),
        "containerFiles": containers,
        "containerCohorts": {k: sorted(v) for k, v in sorted(cohorts.items())},
        "mapFiles": maps,
        "uassetCount": len(assets),
        "audioFileCount": len(audio),
        "localizationFileCount": len(localization),
        "caseCollisionCount": len(case_collisions),
        "caseCollisionSamples": case_collisions[:50],
        "duplicateBasenameCount": len(duplicate_basenames),
        "duplicateBasenameSamples": dict(list(sorted(duplicate_basenames.items()))[:50]),
        "trackedExtensionCoverage": {
            ext: ext_counts.get(ext, 0) for ext in sorted(TRACKED_EXTS)
        },
    }

def audit_archive(path: Path):
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            sha.update(chunk)

    with zipfile.ZipFile(path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        summary = summarize(
            [i.filename for i in infos],
            [i.file_size for i in infos],
        )
        summary.update({
            "mode": "archive",
            "archive": str(path),
            "archiveBytes": path.stat().st_size,
            "archiveSha256": sha.hexdigest(),
            "compressedPayloadBytes": sum(i.compress_size for i in infos),
        })
        return summary

def audit_root(root: Path):
    files = [p for p in root.rglob("*") if p.is_file()]
    rel = [p.relative_to(root).as_posix() for p in files]
    sizes = [p.stat().st_size for p in files]
    summary = summarize(rel, sizes)
    summary.update({
        "mode": "root",
        "root": str(root),
        "physicalBytes": sum(sizes),
    })
    return summary

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--archive", type=Path)
    g.add_argument("--root", type=Path)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()

    if args.archive:
        report = audit_archive(args.archive)
    else:
        report = audit_root(args.root)

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("XZIEL_VIRGIN_UE_PACKAGE_CENSUS_OK", json.dumps({
        "mode": report["mode"],
        "fileCount": report["fileCount"],
        "declaredBytes": report["declaredBytes"],
        "containers": len(report["containerFiles"]),
        "maps": len(report["mapFiles"]),
        "uassets": report["uassetCount"],
        "audioFiles": report["audioFileCount"],
        "localizationFiles": report["localizationFileCount"],
        "caseCollisions": report["caseCollisionCount"],
    }, sort_keys=True))

if __name__ == "__main__":
    main()

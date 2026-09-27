#!/usr/bin/env python3
"""Run the XZIEL emulator agent against JSONL telemetry.

Examples:
  python3 -m scripts.xziel_bot.agent --source stdin --dry-run
  adb logcat -v raw | python3 -m scripts.xziel_bot.agent --source stdin --prefix XzielBotState
  python3 -m scripts.xziel_bot.agent --source file --input evidence/bot-state.jsonl --adb emulator-5554
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Iterator, TextIO

from .adb_driver import AdbDriver
from .model import Action, Observation
from .policy import NachtPolicy


def iter_jsonl(stream: TextIO, prefix: str = "") -> Iterator[dict]:
    for raw in stream:
        line = raw.strip()
        if not line:
            continue
        if prefix:
            at = line.find(prefix)
            if at < 0:
                continue
            line = line[at + len(prefix):].lstrip(" :|-")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            yield payload


def action_record(obs: Observation, action: Action) -> dict:
    target = action.target_position
    return {
        "timestamp": obs.timestamp,
        "map_id": obs.map_id,
        "round": obs.round_number,
        "slot": obs.player.slot,
        "action": action.kind.value,
        "reason": action.reason,
        "utility": action.utility,
        "duration_ms": action.duration_ms,
        "target_id": action.target_id,
        "target_position": (
            {"x": target.x, "y": target.y, "z": target.z} if target else None
        ),
        "metadata": action.metadata,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="XZIEL/Nacht emulator survival bot")
    parser.add_argument("--source", choices=("stdin", "file"), default="stdin")
    parser.add_argument("--input", help="JSONL file when --source=file")
    parser.add_argument("--prefix", default="", help="optional text before JSON payload, e.g. XzielBotState")
    parser.add_argument("--adb", nargs="?", const="", help="execute actions through adb; optional serial")
    parser.add_argument("--dry-run", action="store_true", help="never send ADB input")
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--max-steps", type=int, default=0)
    parser.add_argument("--decision-log", help="write JSONL decisions here")
    args = parser.parse_args()

    if args.source == "file" and not args.input:
        parser.error("--input is required with --source=file")

    policy = NachtPolicy(seed=args.seed)
    driver = None
    if args.adb is not None:
        driver = AdbDriver(serial=args.adb or None, dry_run=args.dry_run)

    stream: TextIO
    close_stream = False
    if args.source == "file":
        stream = open(args.input, "r", encoding="utf-8")
        close_stream = True
    else:
        stream = sys.stdin

    log_stream: TextIO | None = None
    if args.decision_log:
        path = Path(args.decision_log)
        path.parent.mkdir(parents=True, exist_ok=True)
        log_stream = path.open("a", encoding="utf-8")

    steps = 0
    try:
        for payload in iter_jsonl(stream, args.prefix):
            obs = Observation.from_dict(payload)
            action = policy.decide(obs)
            record = action_record(obs, action)
            print(json.dumps(record, separators=(",", ":"), sort_keys=True), flush=True)
            if log_stream:
                log_stream.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
                log_stream.flush()
            if driver is not None:
                driver.execute(action, obs)
            steps += 1
            if args.max_steps and steps >= args.max_steps:
                break
    finally:
        if close_stream:
            stream.close()
        if log_stream:
            log_stream.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

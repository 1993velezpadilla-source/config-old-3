"""ADB input adapter for the XZIEL/NZ:P Android HUD.

This module intentionally stays dumb: it translates high-level bot Actions into
the same touch controls a human uses. The policy never depends on pixel
coordinates, so the adapter can later be replaced by native XZIEL input.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import subprocess
import time
from typing import Iterable

from .model import Action, ActionKind, Observation, Vec3


# Normalized centers from the shipped XZIEL mobile HUD.
HUD = {
    "joy": (0.170, 0.740),
    "fire": (0.885, 0.585),
    "ads_fire": (0.795, 0.435),
    "ads": (0.695, 0.575),
    "reload": (0.805, 0.785),
    "use": (0.605, 0.675),
    "jump": (0.695, 0.790),
    "knife": (0.915, 0.800),
    "swap": (0.905, 0.300),
    "pause": (0.965, 0.075),
    "crouch": (0.635, 0.875),
    "prone": (0.555, 0.875),
}


@dataclass(frozen=True)
class ScreenSize:
    width: int
    height: int

    def point(self, normalized: tuple[float, float]) -> tuple[int, int]:
        x, y = normalized
        return (
            max(0, min(self.width - 1, int(round(x * self.width)))),
            max(0, min(self.height - 1, int(round(y * self.height)))),
        )


class AdbDriver:
    def __init__(self, serial: str | None = None, dry_run: bool = False):
        self.serial = serial
        self.dry_run = dry_run
        self._size: ScreenSize | None = None

    def _adb_prefix(self) -> list[str]:
        out = ["adb"]
        if self.serial:
            out += ["-s", self.serial]
        return out

    def _run(self, args: Iterable[str], *, capture: bool = False) -> str:
        cmd = self._adb_prefix() + list(args)
        if self.dry_run:
            print("ADB:", " ".join(cmd))
            return ""
        result = subprocess.run(
            cmd,
            check=True,
            text=True,
            capture_output=capture,
        )
        return result.stdout if capture else ""

    def screen_size(self, refresh: bool = False) -> ScreenSize:
        if self._size is not None and not refresh:
            return self._size
        output = self._run(["shell", "wm", "size"], capture=True)
        # Typical output: "Physical size: 1080x2400" or an override plus physical.
        lines = [line.strip() for line in output.splitlines() if "size:" in line.lower()]
        if not lines:
            raise RuntimeError(f"Could not parse adb wm size output: {output!r}")
        token = lines[-1].split(":", 1)[1].strip().split()[0]
        width, height = (int(v) for v in token.split("x", 1))
        # XZIEL is landscape locked. Some emulators report physical portrait size.
        if height > width:
            width, height = height, width
        self._size = ScreenSize(width, height)
        return self._size

    def _tap(self, key: str) -> None:
        x, y = self.screen_size().point(HUD[key])
        self._run(["shell", "input", "tap", str(x), str(y)])

    def _hold(self, key: str, duration_ms: int) -> None:
        x, y = self.screen_size().point(HUD[key])
        duration_ms = max(60, min(int(duration_ms or 160), 5000))
        self._run([
            "shell", "input", "swipe",
            str(x), str(y), str(x), str(y), str(duration_ms),
        ])

    def _swipe_normalized(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        duration_ms: int,
    ) -> None:
        size = self.screen_size()
        x1, y1 = size.point(start)
        x2, y2 = size.point(end)
        self._run([
            "shell", "input", "swipe",
            str(x1), str(y1), str(x2), str(y2),
            str(max(60, min(duration_ms, 5000))),
        ])

    @staticmethod
    def _angle_delta(target: float, current: float) -> float:
        return (target - current + 180.0) % 360.0 - 180.0

    def _look_toward(self, obs: Observation, target: Vec3, *, duration_ms: int = 120) -> None:
        target_yaw = obs.player.position.yaw_to(target)
        delta = self._angle_delta(target_yaw, obs.player.yaw)
        # Right half of the screen is the free-look region. Use several bounded
        # swipes rather than one giant snap so the motion looks/behaves human.
        max_step = 42.0
        steps = max(1, int(math.ceil(abs(delta) / max_step)))
        remaining = delta
        for _ in range(steps):
            step = max(-max_step, min(max_step, remaining))
            # Empirical normalized distance. Final gain is calibrated in the
            # emulator workflow rather than hard-coded into policy decisions.
            dx = max(-0.18, min(0.18, step / 230.0))
            self._swipe_normalized((0.74, 0.52), (0.74 + dx, 0.52), max(60, duration_ms // steps))
            remaining -= step

    def _move_toward(self, obs: Observation, target: Vec3, duration_ms: int) -> None:
        target_yaw = obs.player.position.yaw_to(target)
        delta = math.radians(self._angle_delta(target_yaw, obs.player.yaw))
        # Convert target bearing to joystick forward/right. Screen joystick uses
        # negative y for forward and positive x for strafe-right.
        forward = math.cos(delta)
        strafe = math.sin(delta)
        mag = max(1.0, math.hypot(forward, strafe))
        forward /= mag
        strafe /= mag
        cx, cy = HUD["joy"]
        radius = 0.090
        end = (cx + strafe * radius, cy - forward * radius)
        self._swipe_normalized((cx, cy), end, max(90, duration_ms or 260))

    def execute(self, action: Action, obs: Observation) -> None:
        if action.kind == ActionKind.WAIT:
            if action.duration_ms > 0:
                time.sleep(action.duration_ms / 1000.0)
            return
        if action.kind == ActionKind.MOVE and action.target_position:
            self._move_toward(obs, action.target_position, action.duration_ms)
            return
        if action.kind == ActionKind.LOOK and action.target_position:
            self._look_toward(obs, action.target_position, duration_ms=action.duration_ms or 120)
            return
        if action.kind == ActionKind.FIRE:
            if action.target_position:
                self._look_toward(obs, action.target_position, duration_ms=90)
            key = "ads_fire" if action.metadata.get("ads") else "fire"
            self._hold(key, action.duration_ms or 150)
            return
        if action.kind == ActionKind.ADS:
            self._hold("ads", action.duration_ms or 180)
            return
        if action.kind == ActionKind.RELOAD:
            self._tap("reload")
            return
        if action.kind == ActionKind.USE:
            self._hold("use", action.duration_ms or 550)
            return
        if action.kind == ActionKind.MELEE:
            self._tap("knife")
            return
        if action.kind == ActionKind.SWAP:
            self._tap("swap")
            return
        if action.kind == ActionKind.GRENADE:
            # Grenade button is defined by earlier XZIEL HUD patches but its
            # position can be user-edited; use a named fallback only once a
            # telemetry/UI profile supplies it.
            raise RuntimeError("Grenade action requires a calibrated HUD profile")
        raise RuntimeError(f"Unsupported action: {action.kind}")

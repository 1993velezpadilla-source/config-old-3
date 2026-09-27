"""Shared observation/action model for Xziel emulator agents.

The policy deliberately consumes a small JSON contract instead of engine structs.
That keeps the decision system portable between NZ:P/Vril, XZIEL, recorded
sessions, and a future vision-only adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Iterable


class ActionKind(str, Enum):
    WAIT = "wait"
    MOVE = "move"
    LOOK = "look"
    FIRE = "fire"
    ADS = "ads"
    RELOAD = "reload"
    USE = "use"
    MELEE = "melee"
    SWAP = "swap"
    GRENADE = "grenade"


@dataclass(frozen=True)
class Vec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @classmethod
    def from_any(cls, value: Any) -> "Vec3":
        if isinstance(value, dict):
            return cls(float(value.get("x", 0.0)), float(value.get("y", 0.0)), float(value.get("z", 0.0)))
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            return cls(float(value[0]), float(value[1]), float(value[2] if len(value) > 2 else 0.0))
        return cls()

    def distance2d(self, other: "Vec3") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def yaw_to(self, other: "Vec3") -> float:
        return math.degrees(math.atan2(other.y - self.y, other.x - self.x))


@dataclass(frozen=True)
class WeaponSlot:
    name: str = ""
    magazine: int = 0
    reserve: int = 0
    wall_weapon: bool = False
    ammo_cost: int = 0

    @property
    def total_ammo(self) -> int:
        return max(0, self.magazine) + max(0, self.reserve)


@dataclass(frozen=True)
class Zombie:
    entity_id: int
    position: Vec3
    health: float = 1.0
    targeting_me: bool = False
    visible: bool = True
    state: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Zombie":
        return cls(
            entity_id=int(data.get("id", -1)),
            position=Vec3.from_any(data.get("position")),
            health=float(data.get("health", 1.0)),
            targeting_me=bool(data.get("targeting_me", False)),
            visible=bool(data.get("visible", True)),
            state=str(data.get("state", "")),
        )


@dataclass(frozen=True)
class Interactable:
    entity_id: int
    kind: str
    position: Vec3
    active: bool = True
    cost: int = 0
    weapon: str = ""
    ammo_cost: int = 0
    boards: int = -1
    max_boards: int = -1
    breached: bool = False
    safe_to_use: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Interactable":
        return cls(
            entity_id=int(data.get("id", -1)),
            kind=str(data.get("kind", "")),
            position=Vec3.from_any(data.get("position")),
            active=bool(data.get("active", True)),
            cost=int(data.get("cost", 0)),
            weapon=str(data.get("weapon", "")),
            ammo_cost=int(data.get("ammo_cost", 0)),
            boards=int(data.get("boards", -1)),
            max_boards=int(data.get("max_boards", -1)),
            breached=bool(data.get("breached", False)),
            safe_to_use=bool(data.get("safe_to_use", True)),
        )


@dataclass(frozen=True)
class Teammate:
    slot: int
    position: Vec3
    health: float = 100.0
    downed: bool = False
    bleedout_seconds: float = 999.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Teammate":
        return cls(
            slot=int(data.get("slot", -1)),
            position=Vec3.from_any(data.get("position")),
            health=float(data.get("health", 100.0)),
            downed=bool(data.get("downed", False)),
            bleedout_seconds=float(data.get("bleedout_seconds", 999.0)),
        )


@dataclass(frozen=True)
class PlayerState:
    slot: int = 1
    position: Vec3 = Vec3()
    yaw: float = 0.0
    health: float = 100.0
    max_health: float = 100.0
    downed: bool = False
    points: int = 0
    current_weapon: str = ""
    weapons: tuple[WeaponSlot, ...] = ()
    reloading: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerState":
        slots = tuple(
            WeaponSlot(
                name=str(w.get("name", "")),
                magazine=int(w.get("magazine", 0)),
                reserve=int(w.get("reserve", 0)),
                wall_weapon=bool(w.get("wall_weapon", False)),
                ammo_cost=int(w.get("ammo_cost", 0)),
            )
            for w in data.get("weapons", [])
            if isinstance(w, dict)
        )
        return cls(
            slot=int(data.get("slot", 1)),
            position=Vec3.from_any(data.get("position")),
            yaw=float(data.get("yaw", 0.0)),
            health=float(data.get("health", 100.0)),
            max_health=max(1.0, float(data.get("max_health", 100.0))),
            downed=bool(data.get("downed", False)),
            points=int(data.get("points", 0)),
            current_weapon=str(data.get("current_weapon", "")),
            weapons=slots,
            reloading=bool(data.get("reloading", False)),
        )

    @property
    def health_ratio(self) -> float:
        return max(0.0, min(1.0, self.health / self.max_health))

    def current_slot(self) -> WeaponSlot | None:
        for weapon in self.weapons:
            if weapon.name == self.current_weapon:
                return weapon
        return self.weapons[0] if self.weapons else None


@dataclass(frozen=True)
class Observation:
    timestamp: float
    map_id: str
    round_number: int
    round_phase: str
    player: PlayerState
    zombies: tuple[Zombie, ...] = ()
    interactables: tuple[Interactable, ...] = ()
    teammates: tuple[Teammate, ...] = ()
    claimed_entities: frozenset[int] = frozenset()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Observation":
        return cls(
            timestamp=float(data.get("timestamp", 0.0)),
            map_id=str(data.get("map_id", "ndu")),
            round_number=int(data.get("round", data.get("round_number", 1))),
            round_phase=str(data.get("round_phase", "active")),
            player=PlayerState.from_dict(data.get("player", {})),
            zombies=tuple(Zombie.from_dict(z) for z in data.get("zombies", []) if isinstance(z, dict)),
            interactables=tuple(Interactable.from_dict(i) for i in data.get("interactables", []) if isinstance(i, dict)),
            teammates=tuple(Teammate.from_dict(t) for t in data.get("teammates", []) if isinstance(t, dict)),
            claimed_entities=frozenset(int(v) for v in data.get("claimed_entities", [])),
        )

    def nearby_zombies(self, radius: float) -> list[tuple[Zombie, float]]:
        out: list[tuple[Zombie, float]] = []
        for zombie in self.zombies:
            distance = self.player.position.distance2d(zombie.position)
            if distance <= radius:
                out.append((zombie, distance))
        out.sort(key=lambda item: item[1])
        return out

    def interactables_of_kind(self, *kinds: str) -> Iterable[Interactable]:
        wanted = set(kinds)
        return (item for item in self.interactables if item.active and item.kind in wanted)


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    reason: str
    target_id: int | None = None
    target_position: Vec3 | None = None
    duration_ms: int = 0
    utility: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

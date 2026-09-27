"""Utility-based Nacht survival policy.

The policy intentionally prefers robust, inspectable decisions over opaque ML.
A future imitation/RL policy can implement the same decide(observation) API.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random

from .model import Action, ActionKind, Interactable, Observation, Vec3


DEFAULT_WEAPON_SCORE = {
    "ray_gun": 100, "raygun": 100, "thundergun": 100,
    "mg42": 92, "browning": 91, "rpk": 90, "hk21": 88,
    "dingo": 90, "brm": 87, "48_dredge": 84, "gorgon": 82,
    "ppsh-41": 88, "stg-44": 79, "mp40": 76, "thompson": 75,
    "kn-44": 78, "hvk-30": 79, "m8a7": 72, "kuda": 70,
    "vesper": 68, "vmp": 68, "icr-1": 76, "man-o-war": 80,
    "trenchgun": 68, "haymaker_12": 77, "205_brecci": 70,
    "double_barreled_shotgun": 60, "sawed_off_shotgun": 58,
    "m1a1_carbine": 48, "sheiva": 46, "rk5": 44,
    "kar98k": 30, "springfield": 24, "m1911": 20, "panzerschreck": 28,
}


@dataclass
class PolicyConfig:
    danger_radius: float = 180.0
    panic_radius: float = 92.0
    use_radius: float = 72.0
    repair_safe_radius: float = 220.0
    revive_safe_radius: float = 190.0
    low_ammo_rounds: float = 0.25
    reserve_points_early: int = 1000
    reserve_points_late: int = 1600
    box_cost: int = 950
    min_box_round: int = 4
    decision_hold_ms: int = 260
    reaction_min_ms: int = 110
    reaction_max_ms: int = 260


class NachtPolicy:
    def __init__(self, seed: int = 1337, config: PolicyConfig | None = None):
        self.rng = random.Random(seed)
        self.cfg = config or PolicyConfig()
        self.last_kind: ActionKind | None = None

    def weapon_score(self, name: str) -> int:
        return DEFAULT_WEAPON_SCORE.get(name.lower(), 50)

    def _move_toward(self, obs: Observation, pos: Vec3, reason: str, utility: float, target_id: int | None = None) -> Action:
        return Action(ActionKind.MOVE, reason, target_id, pos, self.cfg.decision_hold_ms, utility)

    def _nearest(self, obs: Observation, kinds: tuple[str, ...], predicate=lambda _: True):
        candidates = []
        for item in obs.interactables_of_kind(*kinds):
            if item.entity_id in obs.claimed_entities or not predicate(item):
                continue
            candidates.append((obs.player.position.distance2d(item.position), item))
        return min(candidates, default=(math.inf, None), key=lambda x: x[0])

    def _safe_for_use(self, obs: Observation, radius: float) -> bool:
        return len(obs.nearby_zombies(radius)) == 0 and obs.player.health_ratio > 0.34

    def decide(self, obs: Observation) -> Action:
        p = obs.player
        if p.downed:
            return Action(ActionKind.WAIT, "downed: preserve inputs for teammate revive", duration_ms=300, utility=1000)

        near_panic = obs.nearby_zombies(self.cfg.panic_radius)
        near_danger = obs.nearby_zombies(self.cfg.danger_radius)

        # 1) Immediate survival. Human-like bots do not stop to shop or repair under pressure.
        if len(near_panic) >= 2 or (p.health_ratio < 0.34 and near_danger):
            nearest, dist = near_panic[0] if near_panic else near_danger[0]
            # Move away from the nearest threat while maintaining fire opportunity.
            dx = p.position.x - nearest.position.x
            dy = p.position.y - nearest.position.y
            mag = max(1.0, math.hypot(dx, dy))
            escape = Vec3(p.position.x + dx / mag * 160.0, p.position.y + dy / mag * 160.0, p.position.z)
            return self._move_toward(obs, escape, f"evade {len(near_danger)} close zombies", 990, nearest.entity_id)

        # 2) Team revive outranks economy when the route is not obviously lethal.
        downed = [t for t in obs.teammates if t.downed]
        if downed and len(obs.nearby_zombies(self.cfg.revive_safe_radius)) <= 1:
            mate = min(downed, key=lambda t: (t.bleedout_seconds, p.position.distance2d(t.position)))
            dist = p.position.distance2d(mate.position)
            if dist <= self.cfg.use_radius:
                return Action(ActionKind.USE, f"revive teammate slot {mate.slot}", target_position=mate.position, duration_ms=1200, utility=960)
            return self._move_toward(obs, mate.position, f"reach downed teammate slot {mate.slot}", 950)

        current = p.current_slot()

        # 3) Reload only if safe enough; otherwise shoot or move.
        if current and current.magazine <= 1 and current.reserve > 0 and not near_danger and not p.reloading:
            return Action(ActionKind.RELOAD, "empty/near-empty magazine with safe reload window", duration_ms=900, utility=900)

        # 4) Fight only a threat the player actually has line-of-sight to.
        # Hidden zombies still influence danger/evade decisions but never aim/fire.
        visible_zombies = [z for z in obs.zombies if z.visible]
        if visible_zombies:
            target = min(visible_zombies, key=lambda z: p.position.distance2d(z.position))
            distance = p.position.distance2d(target.position)
            if distance <= 520:
                reaction = self.rng.randint(self.cfg.reaction_min_ms, self.cfg.reaction_max_ms)
                return Action(
                    ActionKind.FIRE,
                    f"engage nearest zombie at {distance:.0f}u",
                    target_id=target.entity_id,
                    target_position=target.position,
                    duration_ms=reaction,
                    utility=850 if distance < 240 else 760,
                    metadata={"aim_jitter_deg": round(self.rng.uniform(-1.8, 1.8), 3), "ads": distance > 180},
                )

        safe = self._safe_for_use(obs, self.cfg.repair_safe_radius)
        reserve_floor = self.cfg.reserve_points_late if obs.round_number >= 10 else self.cfg.reserve_points_early

        # 5) Refill ammo from a wall gun already owned before gambling the box.
        if current and current.wall_weapon:
            estimated_max = max(current.total_ammo, 1)
            low_ammo = current.reserve <= max(12, int(estimated_max * self.cfg.low_ammo_rounds))
            if low_ammo and current.ammo_cost > 0 and p.points >= current.ammo_cost + 200 and safe:
                dist, wall = self._nearest(
                    obs, ("wall_weapon",),
                    lambda i: i.weapon.lower() == current.name.lower() and (i.ammo_cost or i.cost) <= p.points,
                )
                if wall:
                    if dist <= self.cfg.use_radius:
                        return Action(ActionKind.USE, f"buy wall ammo for {current.name}", wall.entity_id, wall.position, 650, 730)
                    return self._move_toward(obs, wall.position, f"return to {current.name} wall-buy for ammo", 720, wall.entity_id)

        # 6) Repair barriers only when safe; prioritize breached/low-board entry points.
        if safe:
            windows = []
            for item in obs.interactables_of_kind("window", "barricade"):
                if item.entity_id in obs.claimed_entities:
                    continue
                missing = 1
                if item.max_boards > 0 and item.boards >= 0:
                    missing = max(0, item.max_boards - item.boards)
                if item.breached:
                    missing += 3
                if missing > 0:
                    windows.append((-(missing), p.position.distance2d(item.position), item))
            if windows:
                _, dist, window = min(windows)
                if dist <= self.cfg.use_radius:
                    return Action(ActionKind.USE, "repair unsafe entry point between threats", window.entity_id, window.position, 900, 650)
                return self._move_toward(obs, window.position, "move to damaged barricade", 620, window.entity_id)

        # 7) Improve a weak loadout through Mystery Box, but keep a safety reserve.
        best_score = max((self.weapon_score(w.name) for w in p.weapons), default=0)
        if obs.round_number >= self.cfg.min_box_round and best_score < 78 and p.points >= self.cfg.box_cost + reserve_floor and safe:
            dist, box = self._nearest(obs, ("mystery_box",))
            if box:
                if dist <= self.cfg.use_radius:
                    return Action(ActionKind.USE, f"roll Mystery Box; best weapon score={best_score}", box.entity_id, box.position, 650, 560)
                return self._move_toward(obs, box.position, "approach Mystery Box during safe window", 530, box.entity_id)

        # 8) Emergency wall weapon purchase when loadout/ammo is poor.
        total_ammo = sum(w.total_ammo for w in p.weapons)
        if (total_ammo <= 18 or best_score < 45) and safe:
            dist, wall = self._nearest(
                obs, ("wall_weapon",),
                lambda i: i.weapon and i.cost <= p.points and self.weapon_score(i.weapon) > best_score + 8,
            )
            if wall:
                if dist <= self.cfg.use_radius:
                    return Action(ActionKind.USE, f"buy reliable wall weapon {wall.weapon}", wall.entity_id, wall.position, 650, 520)
                return self._move_toward(obs, wall.position, f"approach wall weapon {wall.weapon}", 500, wall.entity_id)

        # 9) Doors are strategic unlocks, not panic actions. Open only with reserve.
        if obs.round_phase in ("between", "cleanup") and p.points >= reserve_floor + 1000:
            dist, door = self._nearest(obs, ("door",), lambda i: i.cost <= p.points - reserve_floor)
            if door:
                if dist <= self.cfg.use_radius:
                    return Action(ActionKind.USE, "open progression door with reserve intact", door.entity_id, door.position, 650, 390)
                return self._move_toward(obs, door.position, "rotate toward strategic unopened door", 360, door.entity_id)

        return Action(ActionKind.WAIT, "hold position; no higher-value action", duration_ms=self.cfg.decision_hold_ms, utility=100)

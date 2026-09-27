from __future__ import annotations

import unittest

from scripts.xziel_bot.model import ActionKind, Observation
from scripts.xziel_bot.policy import NachtPolicy


def obs(
    *,
    points=2000,
    round_number=5,
    phase="active",
    health=100,
    current="thompson",
    weapons=None,
    zombies=None,
    interactables=None,
    teammates=None,
):
    return Observation.from_dict({
        "timestamp": 1.0,
        "map_id": "ndu",
        "round": round_number,
        "round_phase": phase,
        "player": {
            "slot": 2,
            "position": [0, 0, 0],
            "yaw": 0,
            "health": health,
            "max_health": 100,
            "points": points,
            "current_weapon": current,
            "weapons": weapons or [
                {"name": current, "magazine": 20, "reserve": 80, "wall_weapon": True, "ammo_cost": 600}
            ],
        },
        "zombies": zombies or [],
        "interactables": interactables or [],
        "teammates": teammates or [],
    })


class NachtPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = NachtPolicy(seed=7)

    def test_evades_multiple_close_zombies_before_shopping(self):
        state = obs(
            points=5000,
            zombies=[
                {"id": 10, "position": [40, 0, 0]},
                {"id": 11, "position": [55, 25, 0]},
            ],
            interactables=[{"id": 20, "kind": "mystery_box", "position": [10, 10, 0], "cost": 950}],
        )
        action = self.policy.decide(state)
        self.assertEqual(action.kind, ActionKind.MOVE)
        self.assertIn("evade", action.reason)

    def test_revive_outranks_economy_when_safe(self):
        state = obs(
            points=5000,
            teammates=[{"slot": 3, "position": [40, 0, 0], "downed": True, "bleedout_seconds": 8}],
            interactables=[{"id": 20, "kind": "mystery_box", "position": [30, 0, 0], "cost": 950}],
        )
        action = self.policy.decide(state)
        self.assertEqual(action.kind, ActionKind.USE)
        self.assertIn("revive", action.reason)

    def test_reload_when_safe_and_magazine_empty(self):
        state = obs(
            weapons=[{"name": "thompson", "magazine": 0, "reserve": 50, "wall_weapon": True, "ammo_cost": 600}]
        )
        action = self.policy.decide(state)
        self.assertEqual(action.kind, ActionKind.RELOAD)

    def test_owned_wall_weapon_ammo_precedes_box(self):
        state = obs(
            points=4500,
            weapons=[{"name": "thompson", "magazine": 3, "reserve": 8, "wall_weapon": True, "ammo_cost": 600}],
            interactables=[
                {"id": 31, "kind": "wall_weapon", "position": [35, 0, 0], "weapon": "thompson", "cost": 1200, "ammo_cost": 600},
                {"id": 32, "kind": "mystery_box", "position": [20, 0, 0], "cost": 950},
            ],
        )
        action = self.policy.decide(state)
        self.assertEqual(action.kind, ActionKind.USE)
        self.assertEqual(action.target_id, 31)
        self.assertIn("wall ammo", action.reason)

    def test_repairs_breached_window_when_safe(self):
        state = obs(
            interactables=[
                {"id": 41, "kind": "window", "position": [30, 0, 0], "boards": 2, "max_boards": 6, "breached": True}
            ]
        )
        action = self.policy.decide(state)
        self.assertEqual(action.kind, ActionKind.USE)
        self.assertEqual(action.target_id, 41)
        self.assertIn("repair", action.reason)

    def test_does_not_box_while_zombie_is_close(self):
        state = obs(
            points=5000,
            current="kar98k",
            weapons=[{"name": "kar98k", "magazine": 5, "reserve": 25, "wall_weapon": True, "ammo_cost": 300}],
            zombies=[{"id": 50, "position": [140, 0, 0]}],
            interactables=[{"id": 51, "kind": "mystery_box", "position": [20, 0, 0], "cost": 950}],
        )
        action = self.policy.decide(state)
        self.assertNotEqual((action.kind, action.target_id), (ActionKind.USE, 51))

    def test_hidden_zombie_is_not_shot_through_wall(self):
        state = obs(
            zombies=[{"id": 55, "position": [300, 0, 0], "visible": False}],
        )
        action = self.policy.decide(state)
        self.assertNotEqual(action.kind, ActionKind.FIRE)

    def test_visible_zombie_can_be_engaged(self):
        state = obs(
            zombies=[{"id": 56, "position": [300, 0, 0], "visible": True}],
        )
        action = self.policy.decide(state)
        self.assertEqual(action.kind, ActionKind.FIRE)
        self.assertEqual(action.target_id, 56)

    def test_box_during_safe_window_for_weak_loadout(self):
        state = obs(
            points=4000,
            current="kar98k",
            weapons=[{"name": "kar98k", "magazine": 5, "reserve": 30, "wall_weapon": False, "ammo_cost": 0}],
            interactables=[{"id": 61, "kind": "mystery_box", "position": [25, 0, 0], "cost": 950}],
        )
        action = self.policy.decide(state)
        self.assertEqual(action.kind, ActionKind.USE)
        self.assertEqual(action.target_id, 61)

    def test_door_opens_only_between_rounds_with_reserve(self):
        door = {"id": 70, "kind": "door", "position": [20, 0, 0], "cost": 1000}
        active = self.policy.decide(obs(points=4000, phase="active", interactables=[door]))
        between = self.policy.decide(obs(points=4000, phase="between", interactables=[door]))
        self.assertFalse(active.kind == ActionKind.USE and active.target_id == 70)
        self.assertEqual((between.kind, between.target_id), (ActionKind.USE, 70))


if __name__ == "__main__":
    unittest.main()

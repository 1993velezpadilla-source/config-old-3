# Main Nave phase 1/2 — verified source audit

## Confirmed in existing Xogot branch
- `you_wont_win.gd` creates 9 authored benches, each with a `StaticBody3D` / `BoxShape3D` collision, and an altar collision **only when its GLB successfully loads**.
- Benches are at x=±4.75 (source coordinates), rows z=-15,-11,-7,-3,1; left side has only four benches to preserve stair lane.
- Bench collision size is (4.30, 0.78, 0.82) times WORLD_SCALE=0.78. Row-to-row collision gap is (4 - 0.82)*0.78=2.4804 m, comfortably above the player capsule diameter of 0.72 m.
- Player already has jump velocity 6.0, radius 0.36, and touch jump. The collision height is 0.6084 m. **Jump-over still requires live physics validation.**
- **Critical blocker:** `zombie_dummy.gd::_tick_chase` uses a straight-line `_move_toward_flat` and `move_and_slide()`. It does NOT currently route around benches using `NavigationAgent3D`. Colliders alone cannot fix enemy pathfinding.
- The current zombie source builds a 3D monja visual; do not replace until sprite animations and multiplayer behavior are validated.
- Do not claim existing multiplayer is functional solely from source references; test it separately.

## Phase 1 acceptance
1. Headless geometry gate passes (requires church GLBs imported).
2. Physical player walking between each row; no invisible blockers.
3. Player jumps each bench without tunneling or ceiling snag.
4. Zombies route around benches using a valid navigation map (not direct chase).
5. Door, stair and altar routes tested, with 10+ zombies, no stuck loops.
6. Android ARM64 scene smoke and frame timing.

## Phase 2 acceptance
1. Optional 8-direction `AnimatedSprite3D` visual adapter; original monja GLB remains available.
2. Idle/walk/run/attack/hit/death events driven from existing enemy state.
3. Sprite atlas budget and mobile texture import validated.
4. Networked state and visual direction checked with two peers; no claims of multiplayer compatibility until proven.

## CI invocation
`godot --headless --path xogot --script res://ci/main_nave_gate.gd`

No screenshots or APK are produced by this commit. This branch is intentionally unmerged until physics/navigation tests pass.

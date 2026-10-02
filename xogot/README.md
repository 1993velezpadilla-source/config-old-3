# XZOMBIE — Xogot / Godot 4.6 port

This folder is a native Godot 4.6 project intended to open directly in Xogot on iPad/iPhone or Godot 4.6 on desktop.

## Current migration gate

- GDScript only — no C#, C++ modules, GDExtension, Wine, Vril, or Quake dependency in the Xogot path.
- Touch FPS movement and camera look.
- Basic iOS gyro look.
- Main / upper / undercroft traversal from the authored navigation skeleton.
- Large exterior walkable footprint.
- Eight future zombie-window sockets prepared, but **no zombies are spawned yet**.
- Mobile renderer, AgX tone mapping, moon key, warm nave practicals, and fog.
- The detailed church visual is loaded from `assets/church/sanctum_current.glb` when present.
- If the GLB is absent, Xogot still opens a visible walkable fallback generated from `data/nav_skeleton.json`.

## iPad controls

- Left thumb: movement.
- Right-side drag: camera.
- Lower-right tap: jump.
- Gyroscope: subtle aim adjustment when no right-side finger is dragging.
- Sprint: push the movement thumbstick close to full travel.
- Keyboard/gamepad also work for desktop testing.

## Getting the complete map pack

Use the GitHub Actions workflow **Xogot Godot 4.6 Project Pack** on branch `feature/xogot-port-v1`.
It downloads the current Hero church authority, applies the current visual polish, exports a Godot GLB, validates the project with Godot 4.6, and uploads a complete Xogot project artifact.

The generated ZIP can be extracted in Files / Working Copy and opened by selecting this folder's `project.godot` in Xogot.

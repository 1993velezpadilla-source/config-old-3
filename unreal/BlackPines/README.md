# Black Pines Sanatorium — Unreal Engine feasibility

**Status:** UE5.8 project skeleton and editor generator committed. Unreal Engine has NOT been installed, launched, or used to render or package this experiment here. Existing Black Pines Godot and Blender files remain intact.

## Source of truth

The ORIGINAL nine-zone Black Pines layout is stored at xogot/data/black_pines_layout.json. The same original JSON feeds Godot, Blender, and this Unreal proof of concept. Black Ops III Zombies Chronicles was developed in a modified IW/Treyarch engine, NOT Unreal Engine. Cooked .uasset files from unrelated games or projects are not automatically native BO3 maps, editable UE projects, or licensed assets.

## On a Windows PC with Unreal Editor

1. Visit https://www.unrealengine.com/download and install the Epic Games Launcher. Sign in there, never through committed credentials.
2. In the Launcher choose Unreal Engine > Library > Add Engine Version > Unreal Engine 5.8 > Install. Install Android target components for eventual APK exports.
3. Check out branch experiment/unreal-black-pines-feasibility-v1 with its JSON sources. Open unreal/BlackPines/BlackPines.uproject.
4. In the Editor use Tools > Execute Python Script and select unreal/BlackPines/Scripts/generate_level.py (PythonScriptPlugin is enabled in the project).
5. Open map /Game/Maps/BlackPinesSanatorium after generating. It contains nine zone floors, 84 solid wall sections (including true door/window cutouts), nine hero prop collision proxies, labeled gameplay positions, and preview lighting.
6. Generator refuses to overwrite an existing map on a second run. To rebuild, manually back up/delete the level first.

## Gates: do not confuse source tests with a game build

G0: Automated JSON + source syntax/geometry contract on GitHub Actions; requires no UE installation.

G1: Unreal Editor real import, geometry collision/routing, visible screenshot and test play; NOT DONE.

G2: Import licensed original Blender artwork and CC0 hospital props from existing Black Pines pipeline; assess materials, visual fidelity and mobile draw calls; NOT DONE.

G3: Implement native UE FPS movement, editable touch controls, gyro, interaction systems, multiplayer and zombie round director. Godot GDScript DOES NOT auto-convert; NOT DONE.

G4: Package ARM64 Android and test thermal/memory/performance and APK play on actual mobile devices before retiring Godot; NOT DONE.

Do NOT include ripped commercial game map meshes/textures in a public build. The shared manifest explicitly treats test skeleton assets as unsafe for public redistribution. No personal login or Epic passwords are needed in GitHub.

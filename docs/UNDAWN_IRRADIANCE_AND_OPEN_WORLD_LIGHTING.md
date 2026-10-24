# UNDAWN → Xziel Irradiance / Open-World Lighting Study

Research date: 2026-09-21

## Why it matters

LIGHTSPEED's UNDAWN is a mobile/PC open-world survival title built in Unreal Engine. Its GDC technical-art session addresses dynamic indirect lighting under mobile constraints.

## Irradiance approach

Public session material describes a real-time irradiance solution that:
- generates irradiance probes at useful positions;
- processes them into irradiance storage;
- uses that storage to shade indirect lighting for objects;
- avoids depending on full realtime ray tracing on mobile.

## Xziel mapping

This strongly supports our sparse-probe plan.

Use:
- baked/static lightmaps for architecture;
- streamed SH/irradiance probe blocks for dynamic zombies/players/props;
- realtime direct light only where perceptually valuable;
- probe density chosen by room complexity and gameplay importance.

Dynamic events can update a local probe/lighting override rather than forcing full realtime GI.

Examples:
- power turns on/off;
- fire starts;
- mystery-box glow;
- lightning flash;
- ritual/quest event.

## Public references

- GDC 2023: Exploring the Technical Arts in the Development of UNDAWN
  https://www.gdcvault.com/play/1029050/LIGHTSPEED-STUDIOS-Developer-Summit-Exploring
- Level Infinite UNDAWN launch / platform information
  https://www.levelinfinite.com/news/live-the-post-apocalyptic-adventure-in-undawn-now-available-globally/
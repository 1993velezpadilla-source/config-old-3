# Return to Empire → Xziel Horde / Mass-Entity Rendering Study

Research date: 2026-09-21

## Why this matters for Zombies

TiMi's Return to Empire uses Unity DOTS to render and update 1,000+ fully 3D units on mobile. Zombies does not need 1,000 nearby enemies, but the architecture is ideal for large hordes because the expensive part should be presentation, not duplicated gameplay-object overhead.

## One logical entity, multiple render LODs

The team publicly described an initial four-LOD setup becoming roughly six related entities after conversion. They changed the structure so one logical LOD record selects the needed mesh at render time and merged extra root/group entities, reducing this example from about six entities to two.

Benefits:
- less memory;
- less redundant transform synchronization;
- lower CPU update cost;
- lower LOD can render while higher LOD is still streaming;
- pressure can force cheaper LOD without changing simulation state.

## Instance data path

Public implementation details include:
- instance parameter structs aligned using std140-style rules;
- a large preallocated instance buffer;
- multithreaded copies of visible-entity instance data into assigned ranges;
- one buffer submitted for GPU instancing / DrawMeshInstanced-style rendering.

## Xziel presentation ECS

Do not replace QuakeC gameplay with an ECS merely for fashion.

Instead add a presentation-oriented SoA/ECS snapshot:

XzPresentEntity:
- transform;
- render asset ID;
- animation state;
- material variant;
- visibility/importance;
- LOD/cluster state;
- shadow/VFX flags.

Authoritative zombie AI/hit/economy remains in Vril/QuakeC. Presentation extraction writes compact arrays once per frame/tick and jobs process visible subsets.

## Horde scaling

Combine with XzFeaturePlanner:
- close threats: full skeleton/animation/shadows/VFX;
- mid threats: reduced animation rate and cheaper shadows;
- far threats: minimal pose/mesh or impostor;
- offscreen but gameplay-active: no render work.

## Public references

- GDC 2023: Thousands of Soldiers Battle on One Mobile Screen: Applications of Unity's DOTS in Return to Empire
  https://www.gdcvault.com/play/1028877/Thousands-of-Soldiers-Battle-on
- GameRes transcript
  https://www.gameres.com/899537.html
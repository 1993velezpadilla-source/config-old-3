# Ace Racer → Xziel 90-FPS Perceptual Rendering Study

Research date: 2026-09-21

## Core lesson

NetEase's Ace Racer team reached a verified 90-FPS mobile mode by concentrating fidelity on perceptually important surfaces and baking/compressing information that did not need to be recomputed every frame.

## Vehicle/material techniques

Public GDC material describes:
- clearcoat-style dual-layer vehicle shading;
- layered normal treatment for carbon-fiber-like surfaces;
- parallax-corrected IBL for vehicle reflections;
- baked SH/environment lighting information;
- baked AO stored in vertex data where appropriate;
- careful control of high-frequency normal detail and roughness to reduce aliasing.

## Bake what is static

The team emphasizes baking:
- scene lightmaps;
- SH lighting/reference data;
- reflection environment data;
- eye-adaptation information in static situations;
- visibility information.

This is directly relevant to horror maps where most architecture and lighting context are known offline.

## Billboard fitting using differentiable rendering

For trees, Ace Racer used billboard representations and then differentiable rendering to fit billboard textures toward the high-poly reference. Public material describes reducing the representation from four textures to two while keeping a close visual match.

Xziel should use the same philosophy for:
- distant trees;
- rubble silhouettes;
- destroyed-building vistas;
- hanging vegetation;
- unreachable background props.

## Correlation-aware texture compression

Ace Racer's material work also explored PCA because PBR texture channels contain correlated information. Public write-ups describe fitting a higher-dimensional PBR vector into a lower-dimensional representation, with learned/weighted fitting to retain visual similarity.

For Xziel this does not mean blindly using PCA at runtime. The useful lesson is to let the cooker exploit correlation across material channels instead of storing every authored channel independently.

## Xziel additions

XzPerceptualCooker should support:
- high-poly → billboard fitting;
- texture-count reduction;
- vertex-color migration;
- baked adaptation/exposure hints for static zones;
- channel-correlation analysis;
- material-specific perceptual weights.

## Public references

- GDC 2023: Achieving High-Quality 90fps Realism in a Mobile Game, Technically and Visually
  https://www.gdcvault.com/play/1028909/Achieving-High-Quality-90fps-Realism
- GameRes transcript
  https://www.gameres.com/900246.html
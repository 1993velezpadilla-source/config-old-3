# Black Desert Mobile → Xziel Adaptive Quality Product Lesson

Research date: 2026-09-21

## Engine/product context

Pearl Abyss built Black Desert Mobile on proprietary engine technology and has continued extending it across mobile and, in 2026, an official PC launcher.

## Runtime quality control

Official Black Desert Mobile patch notes describe allowing 45/60 FPS options while automatically lowering graphics settings if heat or memory overload occurs on lower-spec devices.

This independently validates XzPerformanceGovernor's core philosophy:
- let a player request a target;
- continuously validate that target against thermal/memory reality;
- degrade presentation automatically before stability collapses.

## Modern feature scaling

2026 official patch notes expose individually scalable options including:
- SSR;
- enhanced shadows;
- enhanced effect rendering;
- view distance;
- character rendering distance;
- object rendering quality;
- character rendering quality;
- depth of field.

These map almost one-to-one to XzFeaturePlanner feature candidates.

## Important lesson

A graphics menu is not enough. The runtime still needs authority to protect:
- stability;
- memory;
- thermals;
- frame pacing.

## Public references

- Pearl Abyss Black Desert Mobile engine statement
  https://www.pearlabyss.com/en-US/Board/Detail?_boardNo=72
- Black Desert Mobile adaptive frame/graphics patch
  https://forum.blackdesertm.com/Board/Detail?boardNo=7&contentNo=611273
- 2026 graphics feature update
  https://www.world.blackdesertm.com/Ocean/News/Detail?boardNo=4428
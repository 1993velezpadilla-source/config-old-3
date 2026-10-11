#pragma once
// Porting bridge for *one original BO1 PC engine translation unit*.
// Applies only in the isolated ARM64 math-module gauntlet; not a replacement engine.
// Windows __cdecl is ignored on Android ARM64; it does not change function behavior.
#ifndef __cdecl
#define __cdecl
#endif
// Windows release build's iassert expands to nothing. Match it in this isolated probe.
#ifndef iassert
#define iassert(condition) ((void)0)
#endif
// The original q_shared.h provides this declaration transitively via com_math.h.
// Supply only the declaration to avoid pulling unrelated Win32/DirectX symbols.
void __cdecl AxisToQuat(const float (*mat)[3], float *quat);

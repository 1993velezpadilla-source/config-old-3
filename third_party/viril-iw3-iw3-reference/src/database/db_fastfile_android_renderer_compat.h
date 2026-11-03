#pragma once

// Declaration-only boundary for compiling the authentic KisakCOD FastFile
// loader on Android. These are renderer service contracts, not implementations:
// the Android object intentionally keeps them unresolved until the original
// renderer backend is ported and linked.
struct IDirect3DVertexBuffer9;
struct IDirect3DIndexBuffer9;

void __cdecl R_DelayLoadImage(XAssetHeader header);
void __cdecl R_FinishStaticVertexBuffer(IDirect3DVertexBuffer9 *buffer);
void __cdecl R_FinishStaticIndexBuffer(IDirect3DIndexBuffer9 *buffer);

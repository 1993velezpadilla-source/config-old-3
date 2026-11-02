#pragma once
#include "r_scene.h"

struct GfxModelSurfaceInfo // Win32 sizeof=0xC; LP64 sizeof=0x10
{                                       // ...
    const struct DObjAnimMat *baseMat;
    uint8_t boneIndex;
    uint8_t boneCount;
    uint16_t gfxEntIndex;
    uint16_t lightingHandle;
    // padding byte
    // padding byte
};
static_assert(sizeof(GfxModelSurfaceInfo) == (sizeof(void *) == 8 ? 16u : 12u));

struct GfxModelSkinnedSurface // Win32 sizeof=0x18; LP64 sizeof=0x28
{                                       // ...
    int skinnedCachedOffset;
    XSurface *xsurf;
    GfxModelSurfaceInfo info;
    //$B667868682928995E3CB40CE466D3989 ___u3;
    union
    {
        GfxPackedVertex *skinnedVert;
        int oldSkinnedCachedOffset;
    };
};
static_assert(sizeof(GfxModelSkinnedSurface) == (sizeof(void *) == 8 ? 40u : 24u));

struct GfxModelRigidSurface // Win32 sizeof=0x38; LP64 sizeof=0x48
{
    GfxModelSkinnedSurface surf;
    GfxScaledPlacement placement;
};
static_assert(sizeof(GfxModelRigidSurface) == (sizeof(void *) == 8 ? 72u : 56u));

struct SkinXModelCmd // sizeof=0x1C
{                                       // ...
    void *modelSurfs;
    const DObjAnimMat *mat;
    int surfacePartBits[4];
    uint16_t surfCount;
    // padding byte
    // padding byte
};

int __cdecl DObjBad(const DObj_s *obj);
void __cdecl R_SkinSceneDObj(
    GfxSceneEntity *sceneEnt,
    GfxSceneEntity *localSceneEnt,
    const DObj_s *obj,
    DObjAnimMat *boneMatrix,
    int waitForCullState);
int  R_SkinSceneDObjModels(
    GfxSceneEntity *sceneEnt,
    const DObj_s *obj,
    DObjAnimMat *boneMatrix);
void __cdecl R_SkinGfxEntityCmd(GfxSceneEntity **data);

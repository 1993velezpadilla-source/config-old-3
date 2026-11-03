#pragma once

// Portable definitions for the original IW3 collision-map data structures.
// These types were historically declared in xanim/xanim.h, which also pulls
// the D3D9 renderer and Miles audio headers into the collision core.
#include <cstdint>
#include <universal/q_shared.h>

struct XModel;

struct cStaticModelWritable
{
    uint16_t nextModelInWorldSector;
};

struct cStaticModel_s
{
    cStaticModelWritable writable;
    XModel *xmodel;
    float origin[3];
    float invScaledAxis[3][3];
    float absmin[3];
    float absmax[3];
};

struct dmaterial_t
{
    char material[64];
    int surfaceFlags;
    int contentFlags;
};

struct cNode_t
{
    cplane_s *plane;
    int16_t children[2];
};

struct cLeafBrushNodeLeaf_t
{
    uint16_t *brushes;
};

struct cLeafBrushNodeChildren_t
{
    float dist;
    float range;
    uint16_t childOffset[2];
};

union cLeafBrushNodeData_t
{
    cLeafBrushNodeLeaf_t leaf;
    cLeafBrushNodeChildren_t children;
};

struct cLeafBrushNode_s
{
    uint8_t axis;
    int16_t leafBrushCount;
    int contents;
    cLeafBrushNodeData_t data;
};

struct CollisionBorder
{
    float distEq[3];
    float zBase;
    float zSlope;
    float start;
    float length;
};

struct CollisionPartition
{
    uint8_t triCount;
    uint8_t borderCount;
    int firstTri;
    CollisionBorder *borders;
};

union CollisionAabbTreeIndex
{
    int firstChildIndex;
    int partitionIndex;
};

struct CollisionAabbTree
{
    float origin[3];
    float halfSize[3];
    uint16_t materialIndex;
    uint16_t childCount;
    CollisionAabbTreeIndex u;
};

struct cbrushside_t
{
    cplane_s *plane;
    uint32_t materialNum;
    int16_t firstAdjacentSideOffset;
    uint8_t edgeCount;
};

struct alignas(16) cbrush_t
{
    float mins[3];
    int contents;
    float maxs[3];
    uint32_t numsides;
    cbrushside_t *sides;
    int16_t axialMaterialNum[2][3];
    uint8_t *baseAdjacentSide;
    int16_t firstAdjacentSideOffsets[2][3];
    uint8_t edgeCount[2][3];
};

// cbrush_t is consumed by SIMD-sensitive collision tracing. Preserve its
// alignment on both Win32 and 64-bit Android while allowing pointer width to vary.
static_assert(alignof(cbrush_t) == 16, "cbrush_t must remain 16-byte aligned");
static_assert(sizeof(cbrush_t) % 16 == 0, "cbrush_t size must preserve alignment");

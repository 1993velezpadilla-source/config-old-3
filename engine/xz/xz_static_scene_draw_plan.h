#ifndef XZ_STATIC_SCENE_DRAW_PLAN_H
#define XZ_STATIC_SCENE_DRAW_PLAN_H

#include "xz_xzscene.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t first_instance;
    uint32_t instance_count;
} XzStaticSceneDrawSpan;

typedef struct {
    uint32_t mesh_count;
    uint32_t instance_count;
    float gameplay_units_per_meter;

    XzStaticSceneDrawSpan *mesh_spans;
    float *instance_matrices;
} XzStaticSceneDrawPlan;

void XzStaticSceneDrawPlan_Init(
    XzStaticSceneDrawPlan *plan);

void XzStaticSceneDrawPlan_Reset(
    XzStaticSceneDrawPlan *plan);

int XzStaticSceneDrawPlan_Build(
    XzStaticSceneDrawPlan *plan,
    const XzXzsceneView *scene);

const XzStaticSceneDrawSpan *
XzStaticSceneDrawPlan_Span(
    const XzStaticSceneDrawPlan *plan,
    uint32_t mesh_index);

const float *
XzStaticSceneDrawPlan_InstanceMatrix(
    const XzStaticSceneDrawPlan *plan,
    uint32_t grouped_instance_index);

int XzStaticSceneDrawPlan_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif

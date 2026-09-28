#ifndef XZ_STATIC_SCENE_LIGHTMAP_DRAW_PLAN_H
#define XZ_STATIC_SCENE_LIGHTMAP_DRAW_PLAN_H

#include "xz_lightmap_binding.h"
#include "xz_xzscene.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t mesh_index;
    uint32_t light_texture[2];
    uint32_t first_grouped_instance;
    uint32_t instance_count;
    uint32_t mapped;
} XzStaticSceneLightmapBatch;

typedef struct {
    uint32_t mesh_count;
    uint32_t instance_count;
    uint32_t batch_count;
    uint32_t mapped_batch_count;
    uint32_t missing_batch_count;
    uint32_t mapped_instance_count;
    uint32_t missing_instance_count;
    float gameplay_units_per_meter;

    XzStaticSceneLightmapBatch *batches;
    uint32_t *mesh_first_batch;
    uint32_t *mesh_batch_count;
    uint32_t *source_instance_indices;
    float *instance_matrices;
} XzStaticSceneLightmapDrawPlan;

void XzStaticSceneLightmapDrawPlan_Init(
    XzStaticSceneLightmapDrawPlan *plan);

void XzStaticSceneLightmapDrawPlan_Reset(
    XzStaticSceneLightmapDrawPlan *plan);

int XzStaticSceneLightmapDrawPlan_Build(
    XzStaticSceneLightmapDrawPlan *plan,
    const XzXzsceneView *scene,
    const XzLightmapBindingView *bindings);

const XzStaticSceneLightmapBatch *
XzStaticSceneLightmapDrawPlan_Batch(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t batch_index);

int XzStaticSceneLightmapDrawPlan_MeshBatches(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t mesh_index,
    uint32_t *first_batch,
    uint32_t *batch_count);

uint32_t XzStaticSceneLightmapDrawPlan_SourceInstance(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t grouped_instance_index);

const float *
XzStaticSceneLightmapDrawPlan_InstanceMatrix(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t grouped_instance_index);

#ifdef __cplusplus
}
#endif

#endif

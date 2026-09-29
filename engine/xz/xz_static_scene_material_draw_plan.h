#ifndef XZ_STATIC_SCENE_MATERIAL_DRAW_PLAN_H
#define XZ_STATIC_SCENE_MATERIAL_DRAW_PLAN_H

#include "xz_material_instance_binding.h"
#include "xz_xzscene.h"

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t mesh_index;
    uint32_t material_set_id;
    uint32_t representative_source_instance;
    uint32_t first_grouped_instance;
    uint32_t instance_count;
} XzStaticSceneMaterialBatch;

typedef struct {
    uint32_t mesh_count;
    uint32_t instance_count;
    uint32_t material_set_count;
    uint32_t batch_count;
    float gameplay_units_per_meter;

    XzStaticSceneMaterialBatch *batches;
    uint32_t *mesh_first_batch;
    uint32_t *mesh_batch_count;
    uint32_t *source_instance_indices;
    float *instance_matrices;
} XzStaticSceneMaterialDrawPlan;

void XzStaticSceneMaterialDrawPlan_Init(
    XzStaticSceneMaterialDrawPlan *plan);

void XzStaticSceneMaterialDrawPlan_Reset(
    XzStaticSceneMaterialDrawPlan *plan);

int XzStaticSceneMaterialDrawPlan_Build(
    XzStaticSceneMaterialDrawPlan *plan,
    const XzXzsceneView *scene,
    const XzMaterialInstanceBindingView *materials);

const XzStaticSceneMaterialBatch *
XzStaticSceneMaterialDrawPlan_Batch(
    const XzStaticSceneMaterialDrawPlan *plan,
    uint32_t batch_index);

int XzStaticSceneMaterialDrawPlan_MeshBatches(
    const XzStaticSceneMaterialDrawPlan *plan,
    uint32_t mesh_index,
    uint32_t *first_batch,
    uint32_t *batch_count);

uint32_t XzStaticSceneMaterialDrawPlan_SourceInstance(
    const XzStaticSceneMaterialDrawPlan *plan,
    uint32_t grouped_instance_index);

const float *
XzStaticSceneMaterialDrawPlan_InstanceMatrix(
    const XzStaticSceneMaterialDrawPlan *plan,
    uint32_t grouped_instance_index);

int XzStaticSceneMaterialDrawPlan_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif

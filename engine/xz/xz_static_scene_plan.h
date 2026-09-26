#ifndef XZ_STATIC_SCENE_PLAN_H
#define XZ_STATIC_SCENE_PLAN_H

#include "xz_xzscene.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_STATIC_SCENE_PLAN_MAX_MESHES 2048u

typedef struct {
    uint32_t instance_count;
} XzStaticSceneMeshPlan;

typedef struct {
    uint32_t mesh_count;
    uint32_t instance_count;
    uint32_t nonempty_mesh_count;
    uint32_t max_instances_per_mesh;
    uint32_t max_instances_mesh_index;
    XzStaticSceneMeshPlan
        meshes[XZ_STATIC_SCENE_PLAN_MAX_MESHES];
    int valid;
} XzStaticSceneDrawPlan;

void XzStaticScenePlan_Init(
    XzStaticSceneDrawPlan *plan);

int XzStaticScenePlan_Build(
    XzStaticSceneDrawPlan *plan,
    const XzXzsceneView *scene);

int XzStaticScenePlan_MatrixToRuntimeGl(
    const float scene_row_major[16],
    float gameplay_units_per_meter,
    float output_column_major[16]);

size_t XzStaticScenePlan_WriteMeshMatrices(
    const XzXzsceneView *scene,
    uint32_t mesh_index,
    float *output_column_major,
    size_t output_matrix_capacity);

int XzStaticScenePlan_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif

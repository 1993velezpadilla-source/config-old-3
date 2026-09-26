#include "xz_static_scene_plan.h"

#include <math.h>
#include <string.h>

void XzStaticScenePlan_Init(
    XzStaticSceneDrawPlan *plan)
{
    if (!plan)
        return;

    memset(plan, 0, sizeof(*plan));
}

int XzStaticScenePlan_Build(
    XzStaticSceneDrawPlan *plan,
    const XzXzsceneView *scene)
{
    uint32_t i;

    if (!plan || !scene ||
        !scene->data ||
        scene->mesh_count == 0u ||
        scene->mesh_count >
            XZ_STATIC_SCENE_PLAN_MAX_MESHES ||
        scene->instance_count == 0u)
        return 0;

    XzStaticScenePlan_Init(plan);
    plan->mesh_count = scene->mesh_count;
    plan->instance_count = scene->instance_count;

    for (i = 0u;
         i < scene->instance_count;
         ++i) {
        XzXzsceneInstance instance;
        XzStaticSceneMeshPlan *mesh;

        if (!XzXzscene_ReadInstance(
                scene,
                i,
                &instance) ||
            instance.mesh_index >=
                scene->mesh_count) {
            XzStaticScenePlan_Init(plan);
            return 0;
        }

        mesh =
            &plan->meshes[
                instance.mesh_index];

        if (mesh->instance_count ==
                UINT32_MAX) {
            XzStaticScenePlan_Init(plan);
            return 0;
        }

        mesh->instance_count++;
    }

    for (i = 0u;
         i < plan->mesh_count;
         ++i) {
        const uint32_t count =
            plan->meshes[i].instance_count;

        if (count == 0u) {
            XzStaticScenePlan_Init(plan);
            return 0;
        }

        plan->nonempty_mesh_count++;

        if (count >
            plan->max_instances_per_mesh) {
            plan->max_instances_per_mesh =
                count;
            plan->max_instances_mesh_index =
                i;
        }
    }

    if (plan->nonempty_mesh_count !=
            plan->mesh_count) {
        XzStaticScenePlan_Init(plan);
        return 0;
    }

    plan->valid = 1;
    return 1;
}

int XzStaticScenePlan_MatrixToRuntimeGl(
    const float scene_row_major[16],
    float gameplay_units_per_meter,
    float output_column_major[16])
{
    unsigned int row;
    unsigned int column;

    if (!scene_row_major ||
        !output_column_major ||
        !isfinite(gameplay_units_per_meter) ||
        gameplay_units_per_meter <= 0.0f)
        return 0;

    for (row = 0u; row < 4u; ++row) {
        for (column = 0u;
             column < 4u;
             ++column) {
            float value =
                scene_row_major[
                    row * 4u + column];

            if (!isfinite(value))
                return 0;

            /*
             * XZSC stores scene transforms in meters. The legacy Vril camera
             * matrices operate in Quake gameplay units. Premultiplying by
             * diag(units, units, units, 1) scales both the mesh basis and its
             * translation before transposing into OpenGL column-major memory.
             */
            if (row < 3u)
                value *=
                    gameplay_units_per_meter;

            output_column_major[
                column * 4u + row] =
                    value;
        }
    }

    if (fabsf(output_column_major[3]) >
            1.0e-5f ||
        fabsf(output_column_major[7]) >
            1.0e-5f ||
        fabsf(output_column_major[11]) >
            1.0e-5f ||
        fabsf(output_column_major[15] -
            1.0f) > 1.0e-5f)
        return 0;

    return 1;
}

size_t XzStaticScenePlan_WriteMeshMatrices(
    const XzXzsceneView *scene,
    uint32_t mesh_index,
    float *output_column_major,
    size_t output_matrix_capacity)
{
    size_t written = 0u;
    uint32_t i;

    if (!scene ||
        !scene->data ||
        mesh_index >= scene->mesh_count)
        return 0u;

    if (output_matrix_capacity > 0u &&
        !output_column_major)
        return 0u;

    for (i = 0u;
         i < scene->instance_count;
         ++i) {
        XzXzsceneInstance instance;

        if (!XzXzscene_ReadInstance(
                scene,
                i,
                &instance))
            return 0u;

        if (instance.mesh_index !=
                mesh_index)
            continue;

        if (output_column_major) {
            float *target;

            if (written >=
                output_matrix_capacity)
                return 0u;

            target =
                output_column_major +
                written * 16u;

            if (!XzStaticScenePlan_MatrixToRuntimeGl(
                    instance.matrix,
                    scene->gameplay_units_per_meter,
                    target))
                return 0u;
        }

        written++;
    }

    return written;
}

int XzStaticScenePlan_SelfTest(void)
{
    const float source[16] = {
        2.0f, 0.0f, 0.0f, 1.5f,
        0.0f, 3.0f, 0.0f, -2.0f,
        0.0f, 0.0f, 4.0f, 0.25f,
        0.0f, 0.0f, 0.0f, 1.0f
    };
    float gl[16];

    if (!XzStaticScenePlan_MatrixToRuntimeGl(
            source,
            10.0f,
            gl))
        return 0;

    /*
     * Column-major OpenGL memory for:
     * diag(10,10,10,1) * source.
     */
    if (fabsf(gl[0] - 20.0f) > 0.0001f ||
        fabsf(gl[5] - 30.0f) > 0.0001f ||
        fabsf(gl[10] - 40.0f) > 0.0001f ||
        fabsf(gl[12] - 15.0f) > 0.0001f ||
        fabsf(gl[13] + 20.0f) > 0.0001f ||
        fabsf(gl[14] - 2.5f) > 0.0001f ||
        fabsf(gl[15] - 1.0f) > 0.0001f)
        return 0;

    return 1;
}

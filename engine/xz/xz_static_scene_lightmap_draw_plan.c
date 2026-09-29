#include "xz_static_scene_lightmap_draw_plan.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint32_t source_instance_index;
    uint32_t mesh_index;
    uint32_t light_texture0;
    uint32_t light_texture1;
    uint32_t mapped;
} XzLightmapSortEntry;

static int XzLightmapEntryCompare(
    const void *left_value,
    const void *right_value)
{
    const XzLightmapSortEntry *left =
        (const XzLightmapSortEntry *)left_value;
    const XzLightmapSortEntry *right =
        (const XzLightmapSortEntry *)right_value;

    if (left->mesh_index < right->mesh_index)
        return -1;
    if (left->mesh_index > right->mesh_index)
        return 1;

    /*
     * Keep baked rows before the unbaked fallback rows for a mesh.
     * The exact ordering is deterministic so the grouped instance VBO
     * and any future parameter texture can share the same index space.
     */
    if (left->mapped > right->mapped)
        return -1;
    if (left->mapped < right->mapped)
        return 1;

    if (left->light_texture0 < right->light_texture0)
        return -1;
    if (left->light_texture0 > right->light_texture0)
        return 1;
    if (left->light_texture1 < right->light_texture1)
        return -1;
    if (left->light_texture1 > right->light_texture1)
        return 1;

    if (left->source_instance_index <
        right->source_instance_index)
        return -1;
    if (left->source_instance_index >
        right->source_instance_index)
        return 1;
    return 0;
}

static int XzSameBatchKey(
    const XzLightmapSortEntry *left,
    const XzLightmapSortEntry *right)
{
    return left->mesh_index == right->mesh_index &&
        left->mapped == right->mapped &&
        left->light_texture0 ==
            right->light_texture0 &&
        left->light_texture1 ==
            right->light_texture1;
}

static int XzValidGameplayScale(float value)
{
    return isfinite(value) &&
        value > 0.0f &&
        value <= 10000.0f;
}

static void XzMatrixMetersRowMajorToRuntimeColumnMajor(
    const float input[16],
    float units_per_meter,
    float output[16])
{
    unsigned int row;
    unsigned int column;

    for (column = 0u; column < 4u; ++column) {
        for (row = 0u; row < 4u; ++row) {
            float value =
                input[row * 4u + column];

            if (row < 3u)
                value *= units_per_meter;

            output[column * 4u + row] =
                value;
        }
    }
}

void XzStaticSceneLightmapDrawPlan_Init(
    XzStaticSceneLightmapDrawPlan *plan)
{
    if (!plan)
        return;

    memset(plan, 0, sizeof(*plan));
}

void XzStaticSceneLightmapDrawPlan_Reset(
    XzStaticSceneLightmapDrawPlan *plan)
{
    if (!plan)
        return;

    free(plan->batches);
    free(plan->mesh_first_batch);
    free(plan->mesh_batch_count);
    free(plan->source_instance_indices);
    free(plan->instance_matrices);
    memset(plan, 0, sizeof(*plan));
}

int XzStaticSceneLightmapDrawPlan_Build(
    XzStaticSceneLightmapDrawPlan *plan,
    const XzXzsceneView *scene,
    const XzLightmapBindingView *bindings)
{
    XzLightmapSortEntry *entries = NULL;
    XzStaticSceneLightmapBatch *batches = NULL;
    uint32_t *mesh_first_batch = NULL;
    uint32_t *mesh_batch_count = NULL;
    uint32_t *source_instance_indices = NULL;
    float *instance_matrices = NULL;
    uint32_t batch_count = 0u;
    uint32_t mapped_batch_count = 0u;
    uint32_t missing_batch_count = 0u;
    uint32_t mapped_instance_count = 0u;
    uint32_t missing_instance_count = 0u;
    uint32_t instance_index;
    uint32_t batch_index;
    uint64_t matrix_floats;

    if (!plan ||
        !scene ||
        !scene->data ||
        !bindings ||
        !bindings->data ||
        scene->mesh_count == 0u ||
        scene->instance_count == 0u ||
        bindings->instance_count !=
            scene->instance_count ||
        !XzValidGameplayScale(
            scene->gameplay_units_per_meter))
        return 0;

    matrix_floats =
        (uint64_t)scene->instance_count * 16u;

    if (matrix_floats >
        (uint64_t)(SIZE_MAX / sizeof(float)))
        return 0;

    entries = (XzLightmapSortEntry *)calloc(
        scene->instance_count,
        sizeof(*entries));
    mesh_first_batch = (uint32_t *)malloc(
        (size_t)scene->mesh_count *
        sizeof(*mesh_first_batch));
    mesh_batch_count = (uint32_t *)calloc(
        scene->mesh_count,
        sizeof(*mesh_batch_count));
    source_instance_indices = (uint32_t *)malloc(
        (size_t)scene->instance_count *
        sizeof(*source_instance_indices));
    instance_matrices = (float *)malloc(
        (size_t)matrix_floats *
        sizeof(*instance_matrices));

    if (!entries ||
        !mesh_first_batch ||
        !mesh_batch_count ||
        !source_instance_indices ||
        !instance_matrices)
        goto fail;

    for (instance_index = 0u;
         instance_index < scene->instance_count;
         ++instance_index) {
        XzXzsceneInstance instance;
        XzLightmapBindingRecord binding;
        XzLightmapSortEntry *entry =
            &entries[instance_index];

        if (!XzXzscene_ReadInstance(
                scene,
                instance_index,
                &instance) ||
            instance.mesh_index >=
                scene->mesh_count ||
            !XzLightmapBinding_Record(
                bindings,
                instance_index,
                &binding))
            goto fail;

        entry->source_instance_index =
            instance_index;
        entry->mesh_index =
            instance.mesh_index;

        if ((binding.flags &
             XZ_XZLB_FLAG_MAPPED) != 0u) {
            if ((binding.flags &
                 XZ_XZLB_FLAG_RUNTIME_READY) == 0u ||
                binding.light_texture[0] >=
                    bindings->texture_count ||
                binding.light_texture[1] >=
                    bindings->texture_count)
                goto fail;

            entry->mapped = 1u;
            entry->light_texture0 =
                binding.light_texture[0];
            entry->light_texture1 =
                binding.light_texture[1];
            mapped_instance_count++;
        } else {
            if (binding.flags != 0u)
                goto fail;

            entry->mapped = 0u;
            entry->light_texture0 =
                XZ_XZLB_NO_TEXTURE;
            entry->light_texture1 =
                XZ_XZLB_NO_TEXTURE;
            missing_instance_count++;
        }
    }

    if (mapped_instance_count !=
            bindings->mapped_count ||
        missing_instance_count !=
            bindings->missing_count ||
        mapped_instance_count +
            missing_instance_count !=
            scene->instance_count)
        goto fail;

    qsort(
        entries,
        scene->instance_count,
        sizeof(*entries),
        XzLightmapEntryCompare);

    batch_count = 1u;
    for (instance_index = 1u;
         instance_index < scene->instance_count;
         ++instance_index) {
        if (!XzSameBatchKey(
                &entries[instance_index - 1u],
                &entries[instance_index]))
            batch_count++;
    }

    batches = (XzStaticSceneLightmapBatch *)calloc(
        batch_count,
        sizeof(*batches));
    if (!batches)
        goto fail;

    for (instance_index = 0u;
         instance_index < scene->mesh_count;
         ++instance_index)
        mesh_first_batch[instance_index] =
            UINT32_MAX;

    batch_index = 0u;
    for (instance_index = 0u;
         instance_index < scene->instance_count;
         ++instance_index) {
        const XzLightmapSortEntry *entry =
            &entries[instance_index];
        XzXzsceneInstance instance;
        XzStaticSceneLightmapBatch *batch;

        if (instance_index == 0u ||
            !XzSameBatchKey(
                &entries[instance_index - 1u],
                entry)) {
            if (instance_index != 0u)
                batch_index++;

            if (batch_index >= batch_count)
                goto fail;

            batch = &batches[batch_index];
            batch->mesh_index =
                entry->mesh_index;
            batch->light_texture[0] =
                entry->light_texture0;
            batch->light_texture[1] =
                entry->light_texture1;
            batch->first_grouped_instance =
                instance_index;
            batch->mapped =
                entry->mapped;

            if (mesh_first_batch[
                    entry->mesh_index] ==
                UINT32_MAX)
                mesh_first_batch[
                    entry->mesh_index] =
                    batch_index;

            if (mesh_batch_count[
                    entry->mesh_index] ==
                UINT32_MAX)
                goto fail;
            mesh_batch_count[
                entry->mesh_index]++;

            if (entry->mapped)
                mapped_batch_count++;
            else
                missing_batch_count++;
        }

        batch = &batches[batch_index];
        if (batch->instance_count ==
            UINT32_MAX)
            goto fail;
        batch->instance_count++;

        source_instance_indices[
            instance_index] =
                entry->source_instance_index;

        if (!XzXzscene_ReadInstance(
                scene,
                entry->source_instance_index,
                &instance) ||
            instance.mesh_index !=
                entry->mesh_index)
            goto fail;

        XzMatrixMetersRowMajorToRuntimeColumnMajor(
            instance.matrix,
            scene->gameplay_units_per_meter,
            instance_matrices +
                (size_t)instance_index * 16u);
    }

    if (batch_index + 1u != batch_count)
        goto fail;

    for (instance_index = 0u;
         instance_index < scene->mesh_count;
         ++instance_index) {
        if (mesh_first_batch[instance_index] ==
                UINT32_MAX ||
            mesh_batch_count[instance_index] == 0u)
            goto fail;
    }

    XzStaticSceneLightmapDrawPlan_Reset(plan);

    plan->mesh_count =
        scene->mesh_count;
    plan->instance_count =
        scene->instance_count;
    plan->batch_count =
        batch_count;
    plan->mapped_batch_count =
        mapped_batch_count;
    plan->missing_batch_count =
        missing_batch_count;
    plan->mapped_instance_count =
        mapped_instance_count;
    plan->missing_instance_count =
        missing_instance_count;
    plan->gameplay_units_per_meter =
        scene->gameplay_units_per_meter;
    plan->batches = batches;
    plan->mesh_first_batch =
        mesh_first_batch;
    plan->mesh_batch_count =
        mesh_batch_count;
    plan->source_instance_indices =
        source_instance_indices;
    plan->instance_matrices =
        instance_matrices;

    free(entries);
    return 1;

fail:
    free(entries);
    free(batches);
    free(mesh_first_batch);
    free(mesh_batch_count);
    free(source_instance_indices);
    free(instance_matrices);
    return 0;
}

const XzStaticSceneLightmapBatch *
XzStaticSceneLightmapDrawPlan_Batch(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t batch_index)
{
    if (!plan ||
        !plan->batches ||
        batch_index >= plan->batch_count)
        return NULL;

    return &plan->batches[batch_index];
}

int XzStaticSceneLightmapDrawPlan_MeshBatches(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t mesh_index,
    uint32_t *first_batch,
    uint32_t *batch_count)
{
    if (!plan ||
        !plan->mesh_first_batch ||
        !plan->mesh_batch_count ||
        mesh_index >= plan->mesh_count ||
        !first_batch ||
        !batch_count)
        return 0;

    *first_batch =
        plan->mesh_first_batch[mesh_index];
    *batch_count =
        plan->mesh_batch_count[mesh_index];
    return *first_batch != UINT32_MAX &&
        *batch_count > 0u;
}

uint32_t XzStaticSceneLightmapDrawPlan_SourceInstance(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t grouped_instance_index)
{
    if (!plan ||
        !plan->source_instance_indices ||
        grouped_instance_index >=
            plan->instance_count)
        return UINT32_MAX;

    return plan->source_instance_indices[
        grouped_instance_index];
}

const float *
XzStaticSceneLightmapDrawPlan_InstanceMatrix(
    const XzStaticSceneLightmapDrawPlan *plan,
    uint32_t grouped_instance_index)
{
    if (!plan ||
        !plan->instance_matrices ||
        grouped_instance_index >=
            plan->instance_count)
        return NULL;

    return plan->instance_matrices +
        (size_t)grouped_instance_index * 16u;
}

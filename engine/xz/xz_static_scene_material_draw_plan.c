#include "xz_static_scene_material_draw_plan.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint32_t source_instance_index;
    uint32_t mesh_index;
    uint32_t material_set_id;
} XzMaterialSortEntry;

typedef struct {
    uint32_t used;
    uint32_t mesh_index;
    uint32_t representative_source_instance;
    uint32_t material_set_id;
    uint64_t hash;
} XzMaterialSetSlot;

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

static uint64_t XzFnv1aU32(
    uint64_t hash,
    uint32_t value)
{
    unsigned int shift;

    for (shift = 0u; shift < 32u; shift += 8u) {
        hash ^=
            (uint64_t)((value >> shift) & 0xffu);
        hash *= UINT64_C(1099511628211);
    }

    return hash;
}

static int XzMaterialSetHash(
    const XzMaterialInstanceBindingView *materials,
    uint32_t instance_index,
    uint32_t mesh_index,
    uint64_t *out_hash)
{
    XzMaterialInstanceRecord record;
    uint64_t hash =
        UINT64_C(1469598103934665603);
    uint32_t submesh_index;

    if (!materials ||
        !out_hash ||
        XzMaterialInstanceBinding_Instance(
            materials,
            instance_index,
            &record) != XZ_XZMI_OK ||
        record.binding_count == 0u)
        return 0;

    hash = XzFnv1aU32(hash, mesh_index);
    hash = XzFnv1aU32(
        hash,
        record.binding_count);

    for (submesh_index = 0u;
         submesh_index < record.binding_count;
         ++submesh_index) {
        uint32_t material;

        if (XzMaterialInstanceBinding_Material(
                materials,
                instance_index,
                submesh_index,
                &material) != XZ_XZMI_OK)
            return 0;

        hash = XzFnv1aU32(hash, material);
    }

    *out_hash = hash;
    return 1;
}

static int XzSameMaterialSet(
    const XzMaterialInstanceBindingView *materials,
    uint32_t left_instance,
    uint32_t right_instance)
{
    XzMaterialInstanceRecord left;
    XzMaterialInstanceRecord right;
    uint32_t submesh_index;

    if (!materials ||
        XzMaterialInstanceBinding_Instance(
            materials,
            left_instance,
            &left) != XZ_XZMI_OK ||
        XzMaterialInstanceBinding_Instance(
            materials,
            right_instance,
            &right) != XZ_XZMI_OK ||
        left.binding_count != right.binding_count)
        return 0;

    for (submesh_index = 0u;
         submesh_index < left.binding_count;
         ++submesh_index) {
        uint32_t left_material;
        uint32_t right_material;

        if (XzMaterialInstanceBinding_Material(
                materials,
                left_instance,
                submesh_index,
                &left_material) != XZ_XZMI_OK ||
            XzMaterialInstanceBinding_Material(
                materials,
                right_instance,
                submesh_index,
                &right_material) != XZ_XZMI_OK ||
            left_material != right_material)
            return 0;
    }

    return 1;
}

static uint32_t XzNextPow2(
    uint32_t value)
{
    uint32_t result = 1u;

    if (value == 0u)
        return 0u;

    while (result < value) {
        if (result > UINT32_MAX / 2u)
            return 0u;
        result <<= 1u;
    }

    return result;
}

static int XzMaterialSortEntryCompare(
    const void *left_value,
    const void *right_value)
{
    const XzMaterialSortEntry *left =
        (const XzMaterialSortEntry *)left_value;
    const XzMaterialSortEntry *right =
        (const XzMaterialSortEntry *)right_value;

    if (left->mesh_index < right->mesh_index)
        return -1;
    if (left->mesh_index > right->mesh_index)
        return 1;

    if (left->material_set_id <
        right->material_set_id)
        return -1;
    if (left->material_set_id >
        right->material_set_id)
        return 1;

    if (left->source_instance_index <
        right->source_instance_index)
        return -1;
    if (left->source_instance_index >
        right->source_instance_index)
        return 1;
    return 0;
}

void XzStaticSceneMaterialDrawPlan_Init(
    XzStaticSceneMaterialDrawPlan *plan)
{
    if (!plan)
        return;

    memset(plan, 0, sizeof(*plan));
}

void XzStaticSceneMaterialDrawPlan_Reset(
    XzStaticSceneMaterialDrawPlan *plan)
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

int XzStaticSceneMaterialDrawPlan_Build(
    XzStaticSceneMaterialDrawPlan *plan,
    const XzXzsceneView *scene,
    const XzMaterialInstanceBindingView *materials)
{
    XzMaterialSortEntry *entries = NULL;
    XzMaterialSetSlot *set_table = NULL;
    XzStaticSceneMaterialBatch *batches = NULL;
    uint32_t *mesh_first_batch = NULL;
    uint32_t *mesh_batch_count = NULL;
    uint32_t *source_instance_indices = NULL;
    float *instance_matrices = NULL;
    uint32_t set_table_count;
    uint32_t material_set_count = 0u;
    uint32_t batch_count = 0u;
    uint32_t instance_index;
    uint32_t batch_index;
    uint64_t matrix_floats;

    if (!plan ||
        !scene ||
        !scene->data ||
        !materials ||
        !materials->data ||
        scene->mesh_count == 0u ||
        scene->instance_count == 0u ||
        materials->instance_count !=
            scene->instance_count ||
        !XzValidGameplayScale(
            scene->gameplay_units_per_meter))
        return 0;

    matrix_floats =
        (uint64_t)scene->instance_count * 16u;

    if (matrix_floats >
        (uint64_t)(SIZE_MAX / sizeof(float)) ||
        scene->instance_count >
            UINT32_MAX / 2u)
        return 0;

    set_table_count =
        XzNextPow2(
            scene->instance_count * 2u);
    if (set_table_count == 0u)
        return 0;

    entries = (XzMaterialSortEntry *)calloc(
        scene->instance_count,
        sizeof(*entries));
    set_table = (XzMaterialSetSlot *)calloc(
        set_table_count,
        sizeof(*set_table));
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
        !set_table ||
        !mesh_first_batch ||
        !mesh_batch_count ||
        !source_instance_indices ||
        !instance_matrices)
        goto fail;

    for (instance_index = 0u;
         instance_index < scene->mesh_count;
         ++instance_index)
        mesh_first_batch[instance_index] =
            UINT32_MAX;

    for (instance_index = 0u;
         instance_index < scene->instance_count;
         ++instance_index) {
        XzXzsceneInstance instance;
        XzMaterialSortEntry *entry =
            &entries[instance_index];
        uint64_t hash;
        uint32_t slot_index;
        uint32_t probes;

        if (!XzXzscene_ReadInstance(
                scene,
                instance_index,
                &instance) ||
            instance.mesh_index >= scene->mesh_count ||
            !XzMaterialSetHash(
                materials,
                instance_index,
                instance.mesh_index,
                &hash))
            goto fail;

        slot_index =
            (uint32_t)hash &
            (set_table_count - 1u);

        for (probes = 0u;
             probes < set_table_count;
             ++probes) {
            XzMaterialSetSlot *slot =
                &set_table[slot_index];

            if (!slot->used) {
                if (material_set_count ==
                    UINT32_MAX)
                    goto fail;

                slot->used = 1u;
                slot->mesh_index =
                    instance.mesh_index;
                slot->representative_source_instance =
                    instance_index;
                slot->material_set_id =
                    material_set_count++;
                slot->hash = hash;

                entry->material_set_id =
                    slot->material_set_id;
                break;
            }

            if (slot->hash == hash &&
                slot->mesh_index ==
                    instance.mesh_index &&
                XzSameMaterialSet(
                    materials,
                    slot->representative_source_instance,
                    instance_index)) {
                entry->material_set_id =
                    slot->material_set_id;
                break;
            }

            slot_index =
                (slot_index + 1u) &
                (set_table_count - 1u);
        }

        if (probes == set_table_count)
            goto fail;

        entry->source_instance_index =
            instance_index;
        entry->mesh_index =
            instance.mesh_index;
    }

    qsort(
        entries,
        scene->instance_count,
        sizeof(*entries),
        XzMaterialSortEntryCompare);

    batch_count = 1u;
    for (instance_index = 1u;
         instance_index < scene->instance_count;
         ++instance_index) {
        if (entries[instance_index - 1u].mesh_index !=
                entries[instance_index].mesh_index ||
            entries[instance_index - 1u].material_set_id !=
                entries[instance_index].material_set_id)
            batch_count++;
    }

    batches = (XzStaticSceneMaterialBatch *)calloc(
        batch_count,
        sizeof(*batches));
    if (!batches)
        goto fail;

    batch_index = 0u;
    for (instance_index = 0u;
         instance_index < scene->instance_count;
         ++instance_index) {
        const XzMaterialSortEntry *entry =
            &entries[instance_index];
        XzStaticSceneMaterialBatch *batch;
        XzXzsceneInstance instance;

        if (instance_index == 0u ||
            entries[instance_index - 1u].mesh_index !=
                entry->mesh_index ||
            entries[instance_index - 1u].material_set_id !=
                entry->material_set_id) {
            if (instance_index != 0u)
                batch_index++;

            if (batch_index >= batch_count)
                goto fail;

            batch = &batches[batch_index];
            batch->mesh_index =
                entry->mesh_index;
            batch->material_set_id =
                entry->material_set_id;
            batch->representative_source_instance =
                entry->source_instance_index;
            batch->first_grouped_instance =
                instance_index;

            if (mesh_first_batch[entry->mesh_index] ==
                UINT32_MAX)
                mesh_first_batch[entry->mesh_index] =
                    batch_index;

            if (mesh_batch_count[entry->mesh_index] ==
                UINT32_MAX)
                goto fail;

            mesh_batch_count[entry->mesh_index]++;
        }

        batch = &batches[batch_index];
        if (batch->instance_count == UINT32_MAX)
            goto fail;
        batch->instance_count++;

        source_instance_indices[instance_index] =
            entry->source_instance_index;

        if (!XzXzscene_ReadInstance(
                scene,
                entry->source_instance_index,
                &instance) ||
            instance.mesh_index != entry->mesh_index)
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

    XzStaticSceneMaterialDrawPlan_Reset(plan);

    plan->mesh_count = scene->mesh_count;
    plan->instance_count = scene->instance_count;
    plan->material_set_count = material_set_count;
    plan->batch_count = batch_count;
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
    free(set_table);
    return 1;

fail:
    free(entries);
    free(set_table);
    free(batches);
    free(mesh_first_batch);
    free(mesh_batch_count);
    free(source_instance_indices);
    free(instance_matrices);
    return 0;
}

const XzStaticSceneMaterialBatch *
XzStaticSceneMaterialDrawPlan_Batch(
    const XzStaticSceneMaterialDrawPlan *plan,
    uint32_t batch_index)
{
    if (!plan ||
        !plan->batches ||
        batch_index >= plan->batch_count)
        return NULL;

    return &plan->batches[batch_index];
}

int XzStaticSceneMaterialDrawPlan_MeshBatches(
    const XzStaticSceneMaterialDrawPlan *plan,
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

uint32_t XzStaticSceneMaterialDrawPlan_SourceInstance(
    const XzStaticSceneMaterialDrawPlan *plan,
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
XzStaticSceneMaterialDrawPlan_InstanceMatrix(
    const XzStaticSceneMaterialDrawPlan *plan,
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

static void XzWriteU32Le(
    unsigned char *p,
    uint32_t value)
{
    p[0] =
        (unsigned char)(value & 0xffu);
    p[1] =
        (unsigned char)((value >> 8) & 0xffu);
    p[2] =
        (unsigned char)((value >> 16) & 0xffu);
    p[3] =
        (unsigned char)((value >> 24) & 0xffu);
}

static void XzWriteF32Le(
    unsigned char *p,
    float value)
{
    uint32_t bits;

    memcpy(&bits, &value, sizeof(bits));
    XzWriteU32Le(p, bits);
}

int XzStaticSceneMaterialDrawPlan_SelfTest(void)
{
    static const char paths[] =
        "xziel/maps/test/meshes/m0000.xzm"
        "xziel/maps/test/meshes/m0001.xzm";

    enum {
        P0 = 32,
        P1 = 32,
        STRINGS = P0 + P1,
        MESHES = 2,
        INSTANCES = 4,
        SCENE_BYTES =
            XZ_XZSC_HEADER_BYTES +
            MESHES *
                XZ_XZSC_MESH_RECORD_BYTES +
            INSTANCES *
                XZ_XZSC_INSTANCE_BYTES +
            STRINGS,
        MATERIALS = 4,
        BINDINGS = 7,
        XZMI_BYTES =
            XZ_XZMI_HEADER_BYTES +
            INSTANCES *
                XZ_XZMI_INSTANCE_RECORD_BYTES +
            BINDINGS *
                XZ_XZMI_BINDING_RECORD_BYTES
    };

    unsigned char scene_data[SCENE_BYTES];
    unsigned char material_data[XZMI_BYTES];
    XzXzsceneView scene;
    XzMaterialInstanceBindingView materials;
    XzStaticSceneMaterialDrawPlan plan;
    size_t mesh_at =
        XZ_XZSC_HEADER_BYTES;
    size_t instance_at =
        mesh_at +
        MESHES *
            XZ_XZSC_MESH_RECORD_BYTES;
    size_t strings_at =
        instance_at +
        INSTANCES *
            XZ_XZSC_INSTANCE_BYTES;
    size_t binding_at =
        XZ_XZMI_HEADER_BYTES +
        INSTANCES *
            XZ_XZMI_INSTANCE_RECORD_BYTES;
    uint32_t i;
    const XzStaticSceneMaterialBatch *batch0;
    const XzStaticSceneMaterialBatch *batch1;
    const XzStaticSceneMaterialBatch *batch2;
    const float *matrix0;
    const float *matrix1;

    memset(scene_data, 0, sizeof(scene_data));
    memcpy(scene_data, "XZSC", 4u);
    XzWriteU32Le(
        scene_data + 4u,
        XZ_XZSC_VERSION);
    XzWriteU32Le(
        scene_data + 8u,
        XZ_XZSC_FLAG_XZIEL_Z_UP |
        XZ_XZSC_FLAG_METERS |
        XZ_XZSC_FLAG_ROW_MAJOR_COLUMN_VECTOR |
        XZ_XZSC_FLAG_XZMS_MESHES);
    XzWriteU32Le(scene_data + 12u, MESHES);
    XzWriteU32Le(scene_data + 16u, INSTANCES);
    XzWriteU32Le(
        scene_data + 20u,
        XZ_XZSC_MESH_RECORD_BYTES);
    XzWriteU32Le(
        scene_data + 24u,
        XZ_XZSC_INSTANCE_BYTES);
    XzWriteU32Le(scene_data + 28u, STRINGS);
    XzWriteF32Le(scene_data + 32u, 10.0f);

    XzWriteU32Le(scene_data + mesh_at + 0u, 0u);
    XzWriteU32Le(scene_data + mesh_at + 4u, P0);
    XzWriteU32Le(
        scene_data + mesh_at +
            XZ_XZSC_MESH_RECORD_BYTES + 0u,
        P0);
    XzWriteU32Le(
        scene_data + mesh_at +
            XZ_XZSC_MESH_RECORD_BYTES + 4u,
        P1);

    for (i = 0u; i < INSTANCES; ++i) {
        unsigned char *record =
            scene_data +
            instance_at +
            i * XZ_XZSC_INSTANCE_BYTES;
        uint32_t matrix_index;
        uint32_t mesh =
            i == 1u ? 1u : 0u;
        float tx = (float)(i + 1u);

        XzWriteU32Le(record, mesh);

        for (matrix_index = 0u;
             matrix_index < 16u;
             ++matrix_index) {
            float value = 0.0f;

            if (matrix_index == 0u ||
                matrix_index == 5u ||
                matrix_index == 10u ||
                matrix_index == 15u)
                value = 1.0f;
            else if (matrix_index == 3u)
                value = tx;

            XzWriteF32Le(
                record +
                    4u +
                    matrix_index * 4u,
                value);
        }
    }

    memcpy(
        scene_data + strings_at,
        paths,
        sizeof(paths) - 1u);

    if (XzXzscene_Parse(
            &scene,
            scene_data,
            sizeof(scene_data)) !=
        XZ_XZSC_OK)
        return 0;

    memset(material_data, 0, sizeof(material_data));
    memcpy(material_data, "XZMI", 4u);
    XzWriteU32Le(
        material_data + 4u,
        XZ_XZMI_VERSION);
    XzWriteU32Le(
        material_data + 8u,
        INSTANCES);
    XzWriteU32Le(
        material_data + 12u,
        MATERIALS);
    XzWriteU32Le(
        material_data + 16u,
        BINDINGS);
    XzWriteU32Le(
        material_data + 20u,
        XZ_XZMI_INSTANCE_RECORD_BYTES);
    XzWriteU32Le(
        material_data + 24u,
        XZ_XZMI_BINDING_RECORD_BYTES);
    XzWriteU32Le(
        material_data + 32u,
        XZ_XZMI_HEADER_BYTES);
    XzWriteU32Le(
        material_data + 36u,
        (uint32_t)binding_at);

    /* Instance 0, mesh 0: [0,1]. */
    XzWriteU32Le(material_data + 48u, 0u);
    XzWriteU32Le(material_data + 52u, 2u);
    /* Instance 1, mesh 1: [2]. */
    XzWriteU32Le(material_data + 56u, 2u);
    XzWriteU32Le(material_data + 60u, 1u);
    /* Instance 2, mesh 0: [0,1] same set as instance 0. */
    XzWriteU32Le(material_data + 64u, 3u);
    XzWriteU32Le(material_data + 68u, 2u);
    /* Instance 3, mesh 0: [0,3] override set. */
    XzWriteU32Le(material_data + 72u, 5u);
    XzWriteU32Le(material_data + 76u, 2u);

    XzWriteU32Le(material_data + binding_at + 0u, 0u);
    XzWriteU32Le(material_data + binding_at + 4u, 1u);
    XzWriteU32Le(material_data + binding_at + 8u, 2u);
    XzWriteU32Le(material_data + binding_at + 12u, 0u);
    XzWriteU32Le(material_data + binding_at + 16u, 1u);
    XzWriteU32Le(material_data + binding_at + 20u, 0u);
    XzWriteU32Le(material_data + binding_at + 24u, 3u);

    if (XzMaterialInstanceBinding_Parse(
            &materials,
            material_data,
            sizeof(material_data)) !=
        XZ_XZMI_OK)
        return 0;

    XzStaticSceneMaterialDrawPlan_Init(&plan);

    if (!XzStaticSceneMaterialDrawPlan_Build(
            &plan,
            &scene,
            &materials))
        return 0;

    if (plan.mesh_count != MESHES ||
        plan.instance_count != INSTANCES ||
        plan.material_set_count != 3u ||
        plan.batch_count != 3u)
        goto fail;

    batch0 =
        XzStaticSceneMaterialDrawPlan_Batch(
            &plan,
            0u);
    batch1 =
        XzStaticSceneMaterialDrawPlan_Batch(
            &plan,
            1u);
    batch2 =
        XzStaticSceneMaterialDrawPlan_Batch(
            &plan,
            2u);

    if (!batch0 || !batch1 || !batch2 ||
        batch0->mesh_index != 0u ||
        batch0->instance_count != 2u ||
        batch0->representative_source_instance != 0u ||
        batch1->mesh_index != 0u ||
        batch1->instance_count != 1u ||
        batch1->representative_source_instance != 3u ||
        batch2->mesh_index != 1u ||
        batch2->instance_count != 1u ||
        batch2->representative_source_instance != 1u)
        goto fail;

    if (XzStaticSceneMaterialDrawPlan_SourceInstance(
            &plan, 0u) != 0u ||
        XzStaticSceneMaterialDrawPlan_SourceInstance(
            &plan, 1u) != 2u ||
        XzStaticSceneMaterialDrawPlan_SourceInstance(
            &plan, 2u) != 3u ||
        XzStaticSceneMaterialDrawPlan_SourceInstance(
            &plan, 3u) != 1u)
        goto fail;

    matrix0 =
        XzStaticSceneMaterialDrawPlan_InstanceMatrix(
            &plan, 0u);
    matrix1 =
        XzStaticSceneMaterialDrawPlan_InstanceMatrix(
            &plan, 1u);

    if (!matrix0 ||
        !matrix1 ||
        fabsf(matrix0[12] - 10.0f) > 0.001f ||
        fabsf(matrix1[12] - 30.0f) > 0.001f)
        goto fail;

    XzStaticSceneMaterialDrawPlan_Reset(&plan);
    return 1;

fail:
    XzStaticSceneMaterialDrawPlan_Reset(&plan);
    return 0;
}

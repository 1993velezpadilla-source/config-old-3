#include "xz_static_scene_draw_plan.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

static int XzValidScale(float value)
{
    return isfinite(value) &&
        value > 0.0f &&
        value <= 10000.0f;
}

static void XzMatrixMetersRowMajorToQuakeColumnMajor(
    const float input[16],
    float units_per_meter,
    float output[16])
{
    unsigned int row;
    unsigned int column;

    /*
     * XZSC stores affine matrices row-major using column vectors:
     *
     *   [ R*S  T ]
     *   [ 0     1 ]
     *
     * Mesh vertices are in meters. The legacy gameplay camera operates in
     * Quake units, so the complete XYZ rows (basis + translation) are scaled
     * by units_per_meter. GLES consumes column-major matrices with transpose
     * disabled, so transpose while packing.
     */
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

void XzStaticSceneDrawPlan_Init(
    XzStaticSceneDrawPlan *plan)
{
    if (!plan)
        return;

    memset(plan, 0, sizeof(*plan));
}

void XzStaticSceneDrawPlan_Reset(
    XzStaticSceneDrawPlan *plan)
{
    if (!plan)
        return;

    free(plan->mesh_spans);
    free(plan->instance_matrices);
    memset(plan, 0, sizeof(*plan));
}

int XzStaticSceneDrawPlan_Build(
    XzStaticSceneDrawPlan *plan,
    const XzXzsceneView *scene)
{
    uint32_t *counts = NULL;
    uint32_t *cursors = NULL;
    XzStaticSceneDrawSpan *spans = NULL;
    float *matrices = NULL;
    uint32_t mesh_index;
    uint32_t instance_index;
    uint64_t matrix_floats;
    uint64_t prefix = 0u;

    if (!plan ||
        !scene ||
        !scene->data ||
        scene->mesh_count == 0u ||
        scene->instance_count == 0u ||
        !XzValidScale(
            scene->gameplay_units_per_meter))
        return 0;

    matrix_floats =
        (uint64_t)scene->instance_count * 16u;

    counts = (uint32_t *)calloc(
        scene->mesh_count,
        sizeof(*counts));
    cursors = (uint32_t *)calloc(
        scene->mesh_count,
        sizeof(*cursors));
    spans = (XzStaticSceneDrawSpan *)calloc(
        scene->mesh_count,
        sizeof(*spans));
    matrices = (float *)malloc(
        (size_t)matrix_floats *
        sizeof(*matrices));

    if (!counts ||
        !cursors ||
        !spans ||
        !matrices)
        goto fail;

    for (instance_index = 0u;
         instance_index < scene->instance_count;
         ++instance_index) {
        XzXzsceneInstance instance;

        if (!XzXzscene_ReadInstance(
                scene,
                instance_index,
                &instance) ||
            instance.mesh_index >=
                scene->mesh_count)
            goto fail;

        if (counts[instance.mesh_index] ==
            UINT32_MAX)
            goto fail;

        counts[instance.mesh_index]++;
    }

    for (mesh_index = 0u;
         mesh_index < scene->mesh_count;
         ++mesh_index) {
        if (counts[mesh_index] == 0u)
            goto fail;

        if (prefix >
            (uint64_t)UINT32_MAX)
            goto fail;

        spans[mesh_index].first_instance =
            (uint32_t)prefix;
        spans[mesh_index].instance_count =
            counts[mesh_index];
        cursors[mesh_index] =
            (uint32_t)prefix;

        prefix += counts[mesh_index];
    }

    if (prefix != scene->instance_count)
        goto fail;

    for (instance_index = 0u;
         instance_index < scene->instance_count;
         ++instance_index) {
        XzXzsceneInstance instance;
        uint32_t destination;

        if (!XzXzscene_ReadInstance(
                scene,
                instance_index,
                &instance))
            goto fail;

        destination =
            cursors[instance.mesh_index]++;

        if (destination >=
            scene->instance_count)
            goto fail;

        XzMatrixMetersRowMajorToQuakeColumnMajor(
            instance.matrix,
            scene->gameplay_units_per_meter,
            matrices +
                (size_t)destination * 16u);
    }

    for (mesh_index = 0u;
         mesh_index < scene->mesh_count;
         ++mesh_index) {
        const uint32_t expected_end =
            spans[mesh_index].first_instance +
            spans[mesh_index].instance_count;

        if (cursors[mesh_index] !=
            expected_end)
            goto fail;
    }

    XzStaticSceneDrawPlan_Reset(plan);

    plan->mesh_count =
        scene->mesh_count;
    plan->instance_count =
        scene->instance_count;
    plan->gameplay_units_per_meter =
        scene->gameplay_units_per_meter;
    plan->mesh_spans = spans;
    plan->instance_matrices = matrices;

    free(counts);
    free(cursors);
    return 1;

fail:
    free(counts);
    free(cursors);
    free(spans);
    free(matrices);
    return 0;
}

const XzStaticSceneDrawSpan *
XzStaticSceneDrawPlan_Span(
    const XzStaticSceneDrawPlan *plan,
    uint32_t mesh_index)
{
    if (!plan ||
        !plan->mesh_spans ||
        mesh_index >= plan->mesh_count)
        return NULL;

    return &plan->mesh_spans[mesh_index];
}

const float *
XzStaticSceneDrawPlan_InstanceMatrix(
    const XzStaticSceneDrawPlan *plan,
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

int XzStaticSceneDrawPlan_SelfTest(void)
{
    static const char paths[] =
        "xziel/maps/test/meshes/m0000.xzm"
        "xziel/maps/test/meshes/m0001.xzm";

    enum {
        P0 = 32,
        P1 = 32,
        STRINGS = P0 + P1,
        MESHES = 2,
        INSTANCES = 3,
        BYTES =
            XZ_XZSC_HEADER_BYTES +
            MESHES *
                XZ_XZSC_MESH_RECORD_BYTES +
            INSTANCES *
                XZ_XZSC_INSTANCE_BYTES +
            STRINGS
    };

    unsigned char data[BYTES];
    XzXzsceneView scene;
    XzStaticSceneDrawPlan plan;
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
    unsigned int i;
    const XzStaticSceneDrawSpan *span0;
    const XzStaticSceneDrawSpan *span1;
    const float *m0;
    const float *m2;

    memset(data, 0, sizeof(data));
    memcpy(data, "XZSC", 4u);
    XzWriteU32Le(data + 4u, XZ_XZSC_VERSION);
    XzWriteU32Le(
        data + 8u,
        XZ_XZSC_FLAG_XZIEL_Z_UP |
        XZ_XZSC_FLAG_METERS |
        XZ_XZSC_FLAG_ROW_MAJOR_COLUMN_VECTOR |
        XZ_XZSC_FLAG_XZMS_MESHES);
    XzWriteU32Le(data + 12u, MESHES);
    XzWriteU32Le(data + 16u, INSTANCES);
    XzWriteU32Le(
        data + 20u,
        XZ_XZSC_MESH_RECORD_BYTES);
    XzWriteU32Le(
        data + 24u,
        XZ_XZSC_INSTANCE_BYTES);
    XzWriteU32Le(data + 28u, STRINGS);
    XzWriteF32Le(data + 32u, 10.0f);
    XzWriteU32Le(data + 36u, 0u);

    XzWriteU32Le(data + mesh_at + 0u, 0u);
    XzWriteU32Le(data + mesh_at + 4u, P0);
    XzWriteU32Le(
        data + mesh_at +
            XZ_XZSC_MESH_RECORD_BYTES + 0u,
        P0);
    XzWriteU32Le(
        data + mesh_at +
            XZ_XZSC_MESH_RECORD_BYTES + 4u,
        P1);

    /*
     * Instance order: mesh 1 @ tx=2, mesh 0 @ tx=1,
     * mesh 1 @ tx=3. Build() must regroup as [mesh0][mesh1,mesh1].
     */
    for (i = 0u; i < INSTANCES; ++i) {
        unsigned char *record =
            data +
            instance_at +
            i * XZ_XZSC_INSTANCE_BYTES;
        unsigned int matrix_index;
        uint32_t mesh =
            i == 1u ? 0u : 1u;
        float tx =
            i == 0u ? 2.0f :
            (i == 1u ? 1.0f : 3.0f);

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
        data + strings_at,
        paths,
        sizeof(paths) - 1u);

    if (XzXzscene_Parse(
            &scene,
            data,
            sizeof(data)) !=
        XZ_XZSC_OK)
        return 0;

    XzStaticSceneDrawPlan_Init(&plan);

    if (!XzStaticSceneDrawPlan_Build(
            &plan,
            &scene))
        return 0;

    if (plan.mesh_count != 2u ||
        plan.instance_count != 3u ||
        fabsf(
            plan.gameplay_units_per_meter -
            10.0f) > 0.001f)
        goto fail;

    span0 =
        XzStaticSceneDrawPlan_Span(
            &plan, 0u);
    span1 =
        XzStaticSceneDrawPlan_Span(
            &plan, 1u);

    if (!span0 ||
        !span1 ||
        span0->first_instance != 0u ||
        span0->instance_count != 1u ||
        span1->first_instance != 1u ||
        span1->instance_count != 2u)
        goto fail;

    m0 =
        XzStaticSceneDrawPlan_InstanceMatrix(
            &plan, 0u);
    m2 =
        XzStaticSceneDrawPlan_InstanceMatrix(
            &plan, 2u);

    if (!m0 || !m2)
        goto fail;

    /*
     * Local 1m basis becomes 10 Quake units.
     * Translation 1m becomes x=10 for the grouped mesh0 instance.
     * Column-major translation is [12..14].
     */
    if (fabsf(m0[0] - 10.0f) > 0.001f ||
        fabsf(m0[5] - 10.0f) > 0.001f ||
        fabsf(m0[10] - 10.0f) > 0.001f ||
        fabsf(m0[12] - 10.0f) > 0.001f ||
        fabsf(m0[15] - 1.0f) > 0.001f)
        goto fail;

    /* Last grouped mesh1 instance was source tx=3m -> 30 Quake units. */
    if (fabsf(m2[12] - 30.0f) > 0.001f)
        goto fail;

    XzStaticSceneDrawPlan_Reset(&plan);
    return 1;

fail:
    XzStaticSceneDrawPlan_Reset(&plan);
    return 0;
}

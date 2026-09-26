#include "xz_static_scene_draw_plan.h"
#include "xz_xzscene.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

static int TestRealFile(const char *path)
{
    FILE *file;
    long length;
    unsigned char *data;
    XzXzsceneView scene;
    XzStaticSceneDrawPlan plan;
    uint32_t mesh_index;
    uint64_t grouped_total = 0u;
    uint32_t min_instances = 0xffffffffu;
    uint32_t max_instances = 0u;

    file = fopen(path, "rb");
    if (!file)
        return 0;

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return 0;
    }

    length = ftell(file);
    if (length <= 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 0;
    }

    data = (unsigned char *)malloc(
        (size_t)length);
    if (!data) {
        fclose(file);
        return 0;
    }

    if (fread(
            data,
            1,
            (size_t)length,
            file) != (size_t)length) {
        fclose(file);
        free(data);
        return 0;
    }

    fclose(file);

    if (XzXzscene_Parse(
            &scene,
            data,
            (size_t)length) !=
        XZ_XZSC_OK) {
        free(data);
        return 0;
    }

    XzStaticSceneDrawPlan_Init(&plan);

    if (!XzStaticSceneDrawPlan_Build(
            &plan,
            &scene)) {
        free(data);
        return 0;
    }

    if (plan.mesh_count != 492u ||
        plan.instance_count != 10791u ||
        fabsf(
            plan.gameplay_units_per_meter -
            39.3700787402f) > 0.001f) {
        XzStaticSceneDrawPlan_Reset(&plan);
        free(data);
        return 0;
    }

    for (mesh_index = 0u;
         mesh_index < plan.mesh_count;
         ++mesh_index) {
        const XzStaticSceneDrawSpan *span =
            XzStaticSceneDrawPlan_Span(
                &plan,
                mesh_index);

        if (!span ||
            span->instance_count == 0u) {
            XzStaticSceneDrawPlan_Reset(&plan);
            free(data);
            return 0;
        }

        grouped_total +=
            span->instance_count;

        if (span->instance_count <
            min_instances)
            min_instances =
                span->instance_count;

        if (span->instance_count >
            max_instances)
            max_instances =
                span->instance_count;
    }

    if (grouped_total != 10791u) {
        XzStaticSceneDrawPlan_Reset(&plan);
        free(data);
        return 0;
    }

    printf(
        "XZIEL_NACHT_DRAWPLAN_FILE_OK "
        "meshes=%u instances=%u minPerMesh=%u maxPerMesh=%u\n",
        plan.mesh_count,
        plan.instance_count,
        min_instances,
        max_instances);

    XzStaticSceneDrawPlan_Reset(&plan);
    free(data);
    return 1;
}

int main(int argc, char **argv)
{
    if (!XzStaticSceneDrawPlan_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_STATIC_SCENE_DRAWPLAN_SELFTEST_FAIL\n");
        return 1;
    }

    if (argc == 2 &&
        !TestRealFile(argv[1])) {
        fprintf(
            stderr,
            "XZIEL_STATIC_SCENE_DRAWPLAN_FILE_FAIL\n");
        return 2;
    }

    printf(
        "XZIEL_STATIC_SCENE_DRAWPLAN_TEST_OK "
        "grouping=PASS meter_to_quake=PASS column_major=PASS\n");

    return 0;
}

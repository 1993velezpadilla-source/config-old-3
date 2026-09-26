#include "xz_static_scene_plan.h"
#include "xz_xzscene.h"

#include <stdio.h>
#include <stdlib.h>

static unsigned char *ReadFile(
    const char *path,
    size_t *bytes)
{
    FILE *file;
    long length;
    unsigned char *data;

    *bytes = 0u;
    file = fopen(path, "rb");
    if (!file)
        return NULL;

    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return NULL;
    }

    length = ftell(file);
    if (length <= 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return NULL;
    }

    data = (unsigned char *)malloc(
        (size_t)length);
    if (!data) {
        fclose(file);
        return NULL;
    }

    if (fread(
            data,
            1u,
            (size_t)length,
            file) != (size_t)length) {
        free(data);
        fclose(file);
        return NULL;
    }

    fclose(file);
    *bytes = (size_t)length;
    return data;
}

int main(int argc, char **argv)
{
    unsigned char *data;
    size_t bytes;
    XzXzsceneView scene;
    XzStaticSceneDrawPlan plan;
    uint32_t mesh_index;
    uint64_t counted = 0u;

    if (!XzStaticScenePlan_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_STATIC_SCENE_PLAN_SELFTEST_FAIL\n");
        return 1;
    }

    if (argc != 2) {
        fprintf(
            stderr,
            "usage: %s scene.xzsc\n",
            argv[0]);
        return 2;
    }

    data = ReadFile(argv[1], &bytes);
    if (!data)
        return 3;

    if (XzXzscene_Parse(
            &scene,
            data,
            bytes) != XZ_XZSC_OK) {
        free(data);
        return 4;
    }

    if (!XzStaticScenePlan_Build(
            &plan,
            &scene)) {
        free(data);
        return 5;
    }

    if (plan.mesh_count != 492u ||
        plan.instance_count != 10791u ||
        plan.nonempty_mesh_count != 492u ||
        !plan.valid) {
        free(data);
        return 6;
    }

    for (mesh_index = 0u;
         mesh_index < plan.mesh_count;
         ++mesh_index) {
        size_t actual =
            XzStaticScenePlan_WriteMeshMatrices(
                &scene,
                mesh_index,
                NULL,
                0u);

        if (actual !=
            plan.meshes[
                mesh_index].instance_count) {
            free(data);
            return 7;
        }

        counted +=
            (uint64_t)actual;
    }

    if (counted != 10791u) {
        free(data);
        return 8;
    }

    printf(
        "XZIEL_STATIC_SCENE_PLAN_OK "
        "meshes=%u instances=%u maxMesh=%u maxInstances=%u\n",
        plan.mesh_count,
        plan.instance_count,
        plan.max_instances_mesh_index,
        plan.max_instances_per_mesh);

    free(data);
    return 0;
}

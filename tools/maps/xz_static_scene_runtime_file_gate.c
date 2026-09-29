#include "xz_static_scene_runtime.h"

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

static char g_vfs_root[1024];

int COM_OpenFile(char *filename, int *handle)
{
    char path[2048];
    struct stat st;
    int fd;

    if (!filename || !handle ||
        snprintf(
            path,
            sizeof(path),
            "%s/%s",
            g_vfs_root,
            filename) <= 0 ||
        strlen(path) >= sizeof(path) - 1u) {
        if (handle)
            *handle = -1;
        return -1;
    }

    fd = open(path, O_RDONLY);
    if (fd < 0) {
        *handle = -1;
        return -1;
    }

    if (fstat(fd, &st) != 0 ||
        st.st_size < 0 ||
        st.st_size > 0x7fffffffLL) {
        close(fd);
        *handle = -1;
        return -1;
    }

    *handle = fd;
    return (int)st.st_size;
}

void COM_CloseFile(int handle)
{
    if (handle >= 0)
        close(handle);
}

int Sys_FileRead(int handle, void *dest, int count)
{
    ssize_t got;

    if (handle < 0 || !dest || count < 0)
        return -1;

    do {
        got = read(handle, dest, (size_t)count);
    } while (got < 0 && errno == EINTR);

    if (got < 0 || got > 0x7fffffffL)
        return -1;
    return (int)got;
}

void Sys_FileSeek(int handle, int position)
{
    if (handle >= 0 && position >= 0)
        (void)lseek(handle, (off_t)position, SEEK_SET);
}

static int ParseU32(const char *text, uint32_t *value)
{
    char *end = NULL;
    unsigned long parsed;

    if (!text || !value || !text[0])
        return 0;

    errno = 0;
    parsed = strtoul(text, &end, 10);
    if (errno != 0 || !end || *end != '\0' ||
        parsed > 0xfffffffful)
        return 0;

    *value = (uint32_t)parsed;
    return 1;
}

int main(int argc, char **argv)
{
    XzStaticSceneRuntimeState state;
    XzStaticSceneStatus status;
    uint32_t expected_meshes;
    uint32_t expected_instances;

    if (argc != 5 ||
        strlen(argv[1]) >= sizeof(g_vfs_root) ||
        !ParseU32(argv[3], &expected_meshes) ||
        !ParseU32(argv[4], &expected_instances) ||
        expected_meshes == 0u ||
        expected_instances == 0u) {
        fprintf(
            stderr,
            "usage: %s <vfs-root> <map-id> <expected-meshes> <expected-instances>\n",
            argv[0]);
        return 2;
    }

    snprintf(
        g_vfs_root,
        sizeof(g_vfs_root),
        "%s",
        argv[1]);

    XzStaticSceneRuntime_Init(&state);
    status =
        XzStaticSceneRuntime_LoadMap(
            &state,
            argv[2]);

    if (status != XZ_STATIC_SCENE_READY) {
        fprintf(
            stderr,
            "XZIEL_STATIC_SCENE_RUNTIME_FILE_GATE_FAIL status=%s error=%s\n",
            XzStaticSceneRuntime_StatusName(status),
            state.error);
        XzStaticSceneRuntime_Shutdown(&state);
        return 3;
    }

    if (state.scene.mesh_count != expected_meshes ||
        state.mesh_resource_count != expected_meshes ||
        state.mesh_files_validated != expected_meshes ||
        state.scene.instance_count != expected_instances ||
        state.mesh_bytes_validated == 0u ||
        state.vertex_count == 0u ||
        state.index_count == 0u ||
        state.submesh_count == 0u) {
        fprintf(
            stderr,
            "XZIEL_STATIC_SCENE_RUNTIME_FILE_GATE_FAIL counts "
            "sceneMeshes=%u resources=%u validated=%u instances=%u "
            "meshBytes=%llu vertices=%llu indices=%llu submeshes=%llu\n",
            state.scene.mesh_count,
            state.mesh_resource_count,
            state.mesh_files_validated,
            state.scene.instance_count,
            (unsigned long long)state.mesh_bytes_validated,
            (unsigned long long)state.vertex_count,
            (unsigned long long)state.index_count,
            (unsigned long long)state.submesh_count);
        XzStaticSceneRuntime_Shutdown(&state);
        return 4;
    }

    /*
     * Material/environment packs are deliberately absent in this geometry
     * gate. A generic non-Nacht map must still load geometry without
     * pretending optional presentation lanes already exist.
     */
    if (state.material_data ||
        state.pbr_material_data ||
        state.normal_material_data ||
        state.environment_data ||
        state.height_fog_data ||
        state.reflection_data) {
        fprintf(
            stderr,
            "XZIEL_STATIC_SCENE_RUNTIME_FILE_GATE_FAIL unexpected_optional_pack\n");
        XzStaticSceneRuntime_Shutdown(&state);
        return 5;
    }

    printf(
        "XZIEL_STATIC_SCENE_RUNTIME_FILE_GATE_GREEN "
        "meshes=%u instances=%u meshBytes=%llu vertices=%llu "
        "indices=%llu submeshes=%llu\n",
        state.scene.mesh_count,
        state.scene.instance_count,
        (unsigned long long)state.mesh_bytes_validated,
        (unsigned long long)state.vertex_count,
        (unsigned long long)state.index_count,
        (unsigned long long)state.submesh_count);

    XzStaticSceneRuntime_Shutdown(&state);
    return 0;
}

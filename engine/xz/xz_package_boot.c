#include "xz_package_boot.h"

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern int COM_OpenFile(char *filename, int *handle);
extern void COM_CloseFile(int handle);
extern int Sys_FileRead(int handle, void *dest, int count);

static const char *const xz_package_boot_family_names[
    XZ_PACKAGE_BOOT_FAMILY_COUNT] = {
    "world_geometry",
    "collision",
    "navigation_pathing",
    "materials_textures",
    "static_models_props",
    "animated_models_rigs",
    "animations",
    "weapons_equipment",
    "pack_a_punch_variants",
    "audio_sfx",
    "ambient_music_vo",
    "vfx_particles",
    "lighting_postfx",
    "gameplay_scripts",
    "interactables",
    "perks_wunderfizz",
    "powerups",
    "gobblegum",
    "mystery_box",
    "spawns_rounds_ai",
    "hud_ui_prompts",
    "multiplayer_replication",
    "platform_packaging",
    "soak_release_quality"
};

static uint32_t XzPackageBoot_AllFamiliesMask(void)
{
    return (1u << XZ_PACKAGE_BOOT_FAMILY_COUNT) - 1u;
}

static void XzPackageBoot_SetError(
    XzPackageBootState *state,
    const char *error)
{
    if (!state)
        return;

    if (!error)
        error = "unknown";

    snprintf(
        state->error,
        sizeof(state->error),
        "%s",
        error);
}

static int XzPackageBoot_FamilyIndex(const char *name)
{
    unsigned int i;

    if (!name || !name[0])
        return -1;

    for (i = 0u; i < XZ_PACKAGE_BOOT_FAMILY_COUNT; ++i) {
        if (strcmp(name, xz_package_boot_family_names[i]) == 0)
            return (int)i;
    }

    return -1;
}

static int XzPackageBoot_SafePath(const char *path)
{
    const unsigned char *p;

    if (!path || !path[0] || path[0] == '/')
        return 0;

    if (strlen(path) >= XZ_PACKAGE_BOOT_MAX_PATH)
        return 0;

    if (strstr(path, "../") ||
        strstr(path, "/..") ||
        strstr(path, "\\") ||
        strchr(path, '|'))
        return 0;

    for (p = (const unsigned char *)path; *p; ++p) {
        if (*p < 0x20u || *p == 0x7fu)
            return 0;
    }

    return 1;
}

static int XzPackageBoot_VisibleVfs(const char *path)
{
    char mutable_path[XZ_PACKAGE_BOOT_MAX_PATH];
    int handle = -1;
    int bytes;

    if (!XzPackageBoot_SafePath(path))
        return 0;

    snprintf(mutable_path, sizeof(mutable_path), "%s", path);
    bytes = COM_OpenFile(mutable_path, &handle);

    if (handle >= 0)
        COM_CloseFile(handle);

    return handle >= 0 && bytes > 0;
}

static char *XzPackageBoot_NextField(char **cursor)
{
    char *start;
    char *sep;

    if (!cursor || !*cursor)
        return NULL;

    start = *cursor;
    sep = strchr(start, '|');
    if (sep) {
        *sep = '\0';
        *cursor = sep + 1;
    } else {
        *cursor = NULL;
    }

    return start;
}

static int XzPackageBoot_ParseUnsigned(
    const char *text,
    unsigned int *value)
{
    char *end = NULL;
    unsigned long parsed;

    if (!text || !text[0] || !value)
        return 0;

    parsed = strtoul(text, &end, 10);
    if (!end || *end != '\0' || parsed > 0xfffffffful)
        return 0;

    *value = (unsigned int)parsed;
    return 1;
}

static int XzPackageBoot_ParsePlan(
    XzPackageBootState *state,
    char *data,
    size_t size,
    int check_vfs)
{
    char *line;
    char *save = NULL;
    unsigned int header_families = 0u;
    unsigned int header_artifacts = 0u;
    uint32_t seen_family_mask = 0u;
    uint32_t family_failed_mask = 0u;
    unsigned int line_number = 0u;

    if (!state || !data || size == 0u)
        return 0;

    data[size] = '\0';

    line = strtok_r(data, "\n", &save);
    while (line) {
        char *cursor;
        char *kind;

        line_number++;
        while (*line && isspace((unsigned char)line[strlen(line) - 1u]))
            line[strlen(line) - 1u] = '\0';

        if (!line[0] || line[0] == '#') {
            line = strtok_r(NULL, "\n", &save);
            continue;
        }

        cursor = line;
        kind = XzPackageBoot_NextField(&cursor);
        if (!kind) {
            XzPackageBoot_SetError(state, "malformed_line");
            return 0;
        }

        if (line_number == 1u) {
            char *families = XzPackageBoot_NextField(&cursor);
            char *artifacts = XzPackageBoot_NextField(&cursor);

            if (strcmp(kind, "XZBP1") != 0 ||
                !families ||
                !artifacts ||
                cursor != NULL ||
                !XzPackageBoot_ParseUnsigned(
                    families, &header_families) ||
                !XzPackageBoot_ParseUnsigned(
                    artifacts, &header_artifacts) ||
                header_families != XZ_PACKAGE_BOOT_FAMILY_COUNT ||
                header_artifacts == 0u) {
                XzPackageBoot_SetError(state, "invalid_header");
                return 0;
            }

            state->plan_present = 1;
            line = strtok_r(NULL, "\n", &save);
            continue;
        }

        if (strcmp(kind, "F") == 0) {
            char *phase_text = XzPackageBoot_NextField(&cursor);
            char *family_name = XzPackageBoot_NextField(&cursor);
            char *count_text = XzPackageBoot_NextField(&cursor);
            unsigned int phase;
            unsigned int count;
            int family;

            if (!phase_text || !family_name || !count_text || cursor != NULL ||
                !XzPackageBoot_ParseUnsigned(phase_text, &phase) ||
                !XzPackageBoot_ParseUnsigned(count_text, &count) ||
                phase > 7u || count == 0u) {
                XzPackageBoot_SetError(state, "invalid_family_row");
                return 0;
            }

            family = XzPackageBoot_FamilyIndex(family_name);
            if (family < 0 ||
                (seen_family_mask & (1u << (unsigned int)family)) != 0u) {
                XzPackageBoot_SetError(state, "unknown_or_duplicate_family");
                return 0;
            }

            seen_family_mask |= 1u << (unsigned int)family;
            state->family_phase[family] = (uint8_t)phase;
            state->family_declared[family] = count;
            state->declared_artifacts += count;

        } else if (strcmp(kind, "A") == 0) {
            char *family_name = XzPackageBoot_NextField(&cursor);
            char *path = XzPackageBoot_NextField(&cursor);
            int family;

            if (!family_name || !path || cursor != NULL ||
                !XzPackageBoot_SafePath(path)) {
                XzPackageBoot_SetError(state, "invalid_artifact_row");
                return 0;
            }

            family = XzPackageBoot_FamilyIndex(family_name);
            if (family < 0 ||
                (seen_family_mask & (1u << (unsigned int)family)) == 0u) {
                XzPackageBoot_SetError(state, "artifact_before_family");
                return 0;
            }

            if (state->family_visible[family] >=
                state->family_declared[family]) {
                XzPackageBoot_SetError(state, "artifact_count_overflow");
                return 0;
            }

            if (!check_vfs || XzPackageBoot_VisibleVfs(path)) {
                state->family_visible[family]++;
                state->visible_artifacts++;
            } else {
                state->missing_artifacts++;
                family_failed_mask |=
                    1u << (unsigned int)family;
            }

        } else {
            XzPackageBoot_SetError(state, "unknown_row_kind");
            return 0;
        }

        line = strtok_r(NULL, "\n", &save);
    }

    if (!state->plan_present ||
        seen_family_mask != XzPackageBoot_AllFamiliesMask() ||
        state->declared_artifacts != header_artifacts) {
        XzPackageBoot_SetError(state, "coverage_mismatch");
        return 0;
    }

    {
        unsigned int family;
        for (family = 0u;
             family < XZ_PACKAGE_BOOT_FAMILY_COUNT;
             ++family) {
            if (state->family_visible[family] ==
                state->family_declared[family]) {
                state->visible_family_mask |= 1u << family;
            } else {
                family_failed_mask |= 1u << family;
            }
        }
    }

    state->required_family_mask = XzPackageBoot_AllFamiliesMask();
    state->failed_family_mask = family_failed_mask;
    state->ready =
        state->missing_artifacts == 0u &&
        state->visible_artifacts == state->declared_artifacts &&
        state->visible_family_mask == state->required_family_mask &&
        state->failed_family_mask == 0u;

    if (!state->ready)
        XzPackageBoot_SetError(state, "preflight_incomplete");

    return state->ready;
}

void XzPackageBoot_Init(XzPackageBootState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
    state->required_family_mask = XzPackageBoot_AllFamiliesMask();
}

int XzPackageBoot_LoadAndPreflightVfs(
    XzPackageBootState *state,
    const char *plan_path)
{
    char mutable_path[XZ_PACKAGE_BOOT_MAX_PATH];
    unsigned char *data = NULL;
    int handle = -1;
    int bytes;
    int read_bytes;
    int ok;

    if (!state)
        return 0;

    XzPackageBoot_Init(state);

    if (!plan_path || !XzPackageBoot_SafePath(plan_path)) {
        XzPackageBoot_SetError(state, "unsafe_plan_path");
        return 0;
    }

    snprintf(mutable_path, sizeof(mutable_path), "%s", plan_path);
    bytes = COM_OpenFile(mutable_path, &handle);
    if (handle < 0 || bytes <= 0 ||
        (unsigned int)bytes > XZ_PACKAGE_BOOT_MAX_PLAN_BYTES) {
        if (handle >= 0)
            COM_CloseFile(handle);
        XzPackageBoot_SetError(state, "plan_not_visible");
        return 0;
    }

    data = (unsigned char *)malloc((size_t)bytes + 1u);
    if (!data) {
        COM_CloseFile(handle);
        XzPackageBoot_SetError(state, "plan_alloc_failed");
        return 0;
    }

    read_bytes = Sys_FileRead(handle, data, bytes);
    COM_CloseFile(handle);

    if (read_bytes != bytes) {
        free(data);
        XzPackageBoot_SetError(state, "plan_read_failed");
        return 0;
    }

    ok = XzPackageBoot_ParsePlan(
        state,
        (char *)data,
        (size_t)bytes,
        1);

    free(data);
    return ok;
}

int XzPackageBoot_IsReady(
    const XzPackageBootState *state)
{
    return state ? state->ready : 0;
}

const char *XzPackageBoot_FamilyName(
    XzPackageBootFamily family)
{
    if ((unsigned int)family >= XZ_PACKAGE_BOOT_FAMILY_COUNT)
        return "unknown";

    return xz_package_boot_family_names[(unsigned int)family];
}

int XzPackageBoot_SelfTest(void)
{
    XzPackageBootState state;
    char plan[8192];
    size_t used = 0u;
    unsigned int family;

    XzPackageBoot_Init(&state);

    used += (size_t)snprintf(
        plan + used,
        sizeof(plan) - used,
        "XZBP1|24|24\n");

    for (family = 0u;
         family < XZ_PACKAGE_BOOT_FAMILY_COUNT;
         ++family) {
        used += (size_t)snprintf(
            plan + used,
            sizeof(plan) - used,
            "F|%u|%s|1\nA|%s|test/%u.bin\n",
            family < 3u ? 1u :
            family < 7u ? 2u :
            family < 13u ? 3u :
            family < 20u ? 4u :
            family < 22u ? 5u : 6u,
            xz_package_boot_family_names[family],
            xz_package_boot_family_names[family],
            family);

        if (used >= sizeof(plan))
            return 0;
    }

    if (!XzPackageBoot_ParsePlan(
            &state,
            plan,
            strlen(plan),
            0))
        return 0;

    return state.ready &&
           state.declared_artifacts == 24u &&
           state.visible_artifacts == 24u &&
           state.visible_family_mask ==
               XzPackageBoot_AllFamiliesMask();
}

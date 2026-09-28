#include "xz_source_adapter_registry.h"

#include <string.h>

static const char *const xz_source_kind_names[
    XZ_SOURCE_KIND_COUNT] = {
    "world_geometry",
    "material_texture_shader",
    "lighting_environment",
    "collision_physics",
    "navigation",
    "animation_rig",
    "audio",
    "fx_particles",
    "hud_ui",
    "cinematic_media_camera",
    "input_haptics",
    "spawn_gameplay",
    "script_gameplay",
    "data_curves"
};

static int XzSourceAdapterRegistry_ValidKind(
    XzSourceAssetKind kind)
{
    return (unsigned int)kind <
        XZ_SOURCE_KIND_COUNT;
}

static uint32_t XzSourceAdapterRegistry_Bit(
    XzSourceAssetKind kind)
{
    return 1u << (unsigned int)kind;
}

static void XzSourceAdapterRegistry_Invalidate(
    XzSourceAdapterRegistry *registry)
{
    if (!registry)
        return;

    registry->finalized = 0;
    registry->ready = 0;
}

void XzSourceAdapterRegistry_Init(
    XzSourceAdapterRegistry *registry)
{
    if (!registry)
        return;

    memset(registry, 0, sizeof(*registry));
    registry->generation = 1u;
}

void XzSourceAdapterRegistry_NewGeneration(
    XzSourceAdapterRegistry *registry)
{
    uint32_t generation;
    unsigned int i;

    if (!registry)
        return;

    generation = registry->generation + 1u;
    if (generation == 0u)
        generation = 1u;

    for (i = 0u; i < XZ_SOURCE_KIND_COUNT; ++i) {
        registry->kinds[i].required_exports = 0u;
        registry->kinds[i].converted_exports = 0u;
        registry->kinds[i].verified_exports = 0u;
        registry->kinds[i].failed = 0u;
    }

    registry->required_kind_mask = 0u;
    registry->failed_kind_mask = 0u;
    registry->required_exports = 0u;
    registry->converted_exports = 0u;
    registry->verified_exports = 0u;
    registry->generation = generation;
    registry->finalized = 0;
    registry->ready = 0;
}

int XzSourceAdapterRegistry_Require(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    uint64_t export_count)
{
    XzSourceAdapterSpec *spec;

    if (!registry ||
        !XzSourceAdapterRegistry_ValidKind(kind) ||
        export_count == 0u)
        return 0;

    spec = &registry->kinds[(unsigned int)kind];

    if (UINT64_MAX - spec->required_exports <
            export_count ||
        UINT64_MAX - registry->required_exports <
            export_count)
        return 0;

    spec->required_exports += export_count;
    registry->required_exports += export_count;
    registry->required_kind_mask |=
        XzSourceAdapterRegistry_Bit(kind);

    XzSourceAdapterRegistry_Invalidate(registry);
    return 1;
}

int XzSourceAdapterRegistry_RegisterSupport(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    int parser_registered,
    int converter_registered,
    int native_validator_registered)
{
    XzSourceAdapterSpec *spec;
    uint32_t bit;

    if (!registry ||
        !XzSourceAdapterRegistry_ValidKind(kind))
        return 0;

    spec = &registry->kinds[(unsigned int)kind];
    bit = XzSourceAdapterRegistry_Bit(kind);

    spec->parser_registered =
        parser_registered ? 1u : 0u;
    spec->converter_registered =
        converter_registered ? 1u : 0u;
    spec->native_validator_registered =
        native_validator_registered ? 1u : 0u;

    if (spec->parser_registered &&
        spec->converter_registered &&
        spec->native_validator_registered) {
        registry->supported_kind_mask |= bit;
    } else {
        registry->supported_kind_mask &= ~bit;
    }

    XzSourceAdapterRegistry_Invalidate(registry);
    return 1;
}

int XzSourceAdapterRegistry_SetProgress(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    uint64_t converted_exports,
    uint64_t verified_exports)
{
    XzSourceAdapterSpec *spec;

    if (!registry ||
        !XzSourceAdapterRegistry_ValidKind(kind))
        return 0;

    spec = &registry->kinds[(unsigned int)kind];

    if (spec->required_exports == 0u ||
        converted_exports > spec->required_exports ||
        verified_exports > converted_exports)
        return 0;

    spec->converted_exports = converted_exports;
    spec->verified_exports = verified_exports;

    XzSourceAdapterRegistry_Invalidate(registry);
    return 1;
}

int XzSourceAdapterRegistry_SetFailed(
    XzSourceAdapterRegistry *registry,
    XzSourceAssetKind kind,
    int failed)
{
    if (!registry ||
        !XzSourceAdapterRegistry_ValidKind(kind))
        return 0;

    registry->kinds[(unsigned int)kind].failed =
        failed ? 1u : 0u;

    XzSourceAdapterRegistry_Invalidate(registry);
    return 1;
}

int XzSourceAdapterRegistry_Finalize(
    XzSourceAdapterRegistry *registry)
{
    unsigned int i;

    if (!registry)
        return 0;

    registry->failed_kind_mask = 0u;
    registry->converted_exports = 0u;
    registry->verified_exports = 0u;

    for (i = 0u; i < XZ_SOURCE_KIND_COUNT; ++i) {
        XzSourceAdapterSpec *spec =
            &registry->kinds[i];
        uint32_t bit = 1u << i;

        if (spec->required_exports == 0u)
            continue;

        if (UINT64_MAX - registry->converted_exports <
                spec->converted_exports ||
            UINT64_MAX - registry->verified_exports <
                spec->verified_exports) {
            registry->failed_kind_mask |= bit;
            continue;
        }

        registry->converted_exports +=
            spec->converted_exports;
        registry->verified_exports +=
            spec->verified_exports;

        if ((registry->supported_kind_mask & bit) == 0u ||
            spec->failed ||
            spec->converted_exports !=
                spec->required_exports ||
            spec->verified_exports !=
                spec->required_exports) {
            registry->failed_kind_mask |= bit;
        }
    }

    registry->finalized = 1;
    registry->ready =
        registry->required_kind_mask != 0u &&
        registry->failed_kind_mask == 0u &&
        (registry->supported_kind_mask &
         registry->required_kind_mask) ==
            registry->required_kind_mask &&
        registry->converted_exports ==
            registry->required_exports &&
        registry->verified_exports ==
            registry->required_exports;

    return registry->ready;
}

int XzSourceAdapterRegistry_IsReady(
    const XzSourceAdapterRegistry *registry)
{
    return registry &&
           registry->finalized &&
           registry->ready;
}

const char *XzSourceAdapterRegistry_KindName(
    XzSourceAssetKind kind)
{
    if (!XzSourceAdapterRegistry_ValidKind(kind))
        return "unknown";

    return xz_source_kind_names[
        (unsigned int)kind];
}

int XzSourceAdapterRegistry_SelfTest(void)
{
    XzSourceAdapterRegistry registry;
    int ok = 0;

    XzSourceAdapterRegistry_Init(&registry);

    if (!XzSourceAdapterRegistry_RegisterSupport(
            &registry,
            XZ_SOURCE_WORLD_GEOMETRY,
            1,
            1,
            1) ||
        !XzSourceAdapterRegistry_RegisterSupport(
            &registry,
            XZ_SOURCE_AUDIO,
            1,
            1,
            1))
        return 0;

    if (!XzSourceAdapterRegistry_Require(
            &registry,
            XZ_SOURCE_WORLD_GEOMETRY,
            100u) ||
        !XzSourceAdapterRegistry_Require(
            &registry,
            XZ_SOURCE_AUDIO,
            25u))
        return 0;

    if (!XzSourceAdapterRegistry_SetProgress(
            &registry,
            XZ_SOURCE_WORLD_GEOMETRY,
            100u,
            100u) ||
        !XzSourceAdapterRegistry_SetProgress(
            &registry,
            XZ_SOURCE_AUDIO,
            25u,
            25u))
        return 0;

    if (!XzSourceAdapterRegistry_Finalize(
            &registry) ||
        !XzSourceAdapterRegistry_IsReady(
            &registry))
        return 0;

    if (!XzSourceAdapterRegistry_RegisterSupport(
            &registry,
            XZ_SOURCE_AUDIO,
            1,
            1,
            0))
        return 0;

    if (XzSourceAdapterRegistry_Finalize(
            &registry))
        return 0;

    if ((registry.failed_kind_mask &
         XzSourceAdapterRegistry_Bit(
             XZ_SOURCE_AUDIO)) == 0u)
        return 0;

    XzSourceAdapterRegistry_NewGeneration(
        &registry);

    if (registry.ready ||
        registry.required_kind_mask != 0u ||
        registry.required_exports != 0u)
        return 0;

    ok = 1;
    return ok;
}

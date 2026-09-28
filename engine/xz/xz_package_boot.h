#ifndef XZ_PACKAGE_BOOT_H
#define XZ_PACKAGE_BOOT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_PACKAGE_BOOT_FAMILY_COUNT 24u
#define XZ_PACKAGE_BOOT_MAX_PLAN_BYTES (2u * 1024u * 1024u)
#define XZ_PACKAGE_BOOT_MAX_PATH 512u

typedef enum XzPackageBootFamily {
    XZ_PACKAGE_BOOT_WORLD_GEOMETRY = 0,
    XZ_PACKAGE_BOOT_COLLISION,
    XZ_PACKAGE_BOOT_NAVIGATION_PATHING,
    XZ_PACKAGE_BOOT_MATERIALS_TEXTURES,
    XZ_PACKAGE_BOOT_STATIC_MODELS_PROPS,
    XZ_PACKAGE_BOOT_ANIMATED_MODELS_RIGS,
    XZ_PACKAGE_BOOT_ANIMATIONS,
    XZ_PACKAGE_BOOT_WEAPONS_EQUIPMENT,
    XZ_PACKAGE_BOOT_PACK_A_PUNCH_VARIANTS,
    XZ_PACKAGE_BOOT_AUDIO_SFX,
    XZ_PACKAGE_BOOT_AMBIENT_MUSIC_VO,
    XZ_PACKAGE_BOOT_VFX_PARTICLES,
    XZ_PACKAGE_BOOT_LIGHTING_POSTFX,
    XZ_PACKAGE_BOOT_GAMEPLAY_SCRIPTS,
    XZ_PACKAGE_BOOT_INTERACTABLES,
    XZ_PACKAGE_BOOT_PERKS_WUNDERFIZZ,
    XZ_PACKAGE_BOOT_POWERUPS,
    XZ_PACKAGE_BOOT_GOBBLEGUM,
    XZ_PACKAGE_BOOT_MYSTERY_BOX,
    XZ_PACKAGE_BOOT_SPAWNS_ROUNDS_AI,
    XZ_PACKAGE_BOOT_HUD_UI_PROMPTS,
    XZ_PACKAGE_BOOT_MULTIPLAYER_REPLICATION,
    XZ_PACKAGE_BOOT_PLATFORM_PACKAGING,
    XZ_PACKAGE_BOOT_SOAK_RELEASE_QUALITY
} XzPackageBootFamily;

typedef struct XzPackageBootState {
    uint32_t required_family_mask;
    uint32_t visible_family_mask;
    uint32_t failed_family_mask;
    uint32_t declared_artifacts;
    uint32_t visible_artifacts;
    uint32_t missing_artifacts;
    uint32_t family_declared[XZ_PACKAGE_BOOT_FAMILY_COUNT];
    uint32_t family_visible[XZ_PACKAGE_BOOT_FAMILY_COUNT];
    uint8_t family_phase[XZ_PACKAGE_BOOT_FAMILY_COUNT];
    int plan_present;
    int ready;
    char error[128];
} XzPackageBootState;

void XzPackageBoot_Init(XzPackageBootState *state);

int XzPackageBoot_LoadAndPreflightVfs(
    XzPackageBootState *state,
    const char *plan_path);

int XzPackageBoot_IsReady(
    const XzPackageBootState *state);

const char *XzPackageBoot_FamilyName(
    XzPackageBootFamily family);

int XzPackageBoot_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif

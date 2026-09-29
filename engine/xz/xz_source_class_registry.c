#include "xz_source_class_registry.h"

#include <ctype.h>
#include <stddef.h>
#include <string.h>

static int XzSourceClass_StartsWith(
    const char *value,
    const char *prefix)
{
    size_t n;

    if (!value || !prefix)
        return 0;

    n = strlen(prefix);
    return strncmp(value, prefix, n) == 0;
}

static int XzSourceClass_EndsWith(
    const char *value,
    const char *suffix)
{
    size_t value_len;
    size_t suffix_len;

    if (!value || !suffix)
        return 0;

    value_len = strlen(value);
    suffix_len = strlen(suffix);
    if (suffix_len > value_len)
        return 0;

    return strcmp(value + value_len - suffix_len, suffix) == 0;
}

static int XzSourceClass_ContainsFolded(
    const char *value,
    const char *needle)
{
    const unsigned char *start;
    size_t needle_len;
    size_t i;

    if (!value || !needle || !needle[0])
        return 0;

    needle_len = strlen(needle);
    for (start = (const unsigned char *)value; *start; ++start) {
        for (i = 0u; i < needle_len; ++i) {
            unsigned char vc = start[i];
            unsigned char nc = (unsigned char)needle[i];

            if (vc == 0u)
                break;
            if (tolower(vc) != tolower(nc))
                break;
        }
        if (i == needle_len)
            return 1;
    }

    return 0;
}

static int XzSourceClass_IsAny(
    const char *value,
    const char *const *names,
    size_t count)
{
    size_t i;

    for (i = 0u; i < count; ++i) {
        if (strcmp(value, names[i]) == 0)
            return 1;
    }

    return 0;
}

static int XzSourceClass_IsIgnorable(
    const char *class_name)
{
    static const char *const names[] = {
        "BookMark",
        "BookMark2D"
    };

    return class_name &&
           XzSourceClass_IsAny(
               class_name,
               names,
               sizeof(names) / sizeof(names[0]));
}

static XzPackageBootFamily XzSourceClass_ClassifyGenerated(
    const char *class_name)
{
    if (XzSourceClass_ContainsFolded(class_name, "packapunch") ||
        XzSourceClass_ContainsFolded(class_name, "pack_a_punch") ||
        XzSourceClass_ContainsFolded(class_name, "pap_"))
        return XZ_PACKAGE_BOOT_PACK_A_PUNCH_VARIANTS;

    if (XzSourceClass_ContainsFolded(class_name, "mysterybox") ||
        XzSourceClass_ContainsFolded(class_name, "mystery_box") ||
        XzSourceClass_ContainsFolded(class_name, "gunbox"))
        return XZ_PACKAGE_BOOT_MYSTERY_BOX;

    if (XzSourceClass_ContainsFolded(class_name, "gobblegum") ||
        XzSourceClass_ContainsFolded(class_name, "gobble_gum"))
        return XZ_PACKAGE_BOOT_GOBBLEGUM;

    if (XzSourceClass_ContainsFolded(class_name, "wunderfizz") ||
        XzSourceClass_ContainsFolded(class_name, "perkbottle") ||
        XzSourceClass_ContainsFolded(class_name, "perk_") ||
        XzSourceClass_ContainsFolded(class_name, "perkplacement") ||
        XzSourceClass_ContainsFolded(class_name, "whoswho") ||
        XzSourceClass_ContainsFolded(class_name, "vulture"))
        return XZ_PACKAGE_BOOT_PERKS_WUNDERFIZZ;

    if (XzSourceClass_ContainsFolded(class_name, "powerup") ||
        XzSourceClass_ContainsFolded(class_name, "power_up") ||
        XzSourceClass_ContainsFolded(class_name, "instakill") ||
        XzSourceClass_ContainsFolded(class_name, "maxammo") ||
        XzSourceClass_ContainsFolded(class_name, "doublepoints") ||
        XzSourceClass_ContainsFolded(class_name, "firesale") ||
        XzSourceClass_ContainsFolded(class_name, "nuke"))
        return XZ_PACKAGE_BOOT_POWERUPS;

    if (XzSourceClass_ContainsFolded(class_name, "zombie") ||
        XzSourceClass_ContainsFolded(class_name, "dogspawner") ||
        XzSourceClass_ContainsFolded(class_name, "spawner") ||
        XzSourceClass_ContainsFolded(class_name, "spawnpoint") ||
        XzSourceClass_ContainsFolded(class_name, "spawn_point") ||
        XzSourceClass_ContainsFolded(class_name, "round") ||
        XzSourceClass_ContainsFolded(class_name, "zone"))
        return XZ_PACKAGE_BOOT_SPAWNS_ROUNDS_AI;

    if (XzSourceClass_ContainsFolded(class_name, "wallbuy") ||
        XzSourceClass_ContainsFolded(class_name, "buyable") ||
        XzSourceClass_ContainsFolded(class_name, "barricade") ||
        XzSourceClass_ContainsFolded(class_name, "door") ||
        XzSourceClass_ContainsFolded(class_name, "trap") ||
        XzSourceClass_ContainsFolded(class_name, "teleport") ||
        XzSourceClass_ContainsFolded(class_name, "interact"))
        return XZ_PACKAGE_BOOT_INTERACTABLES;

    if (XzSourceClass_ContainsFolded(class_name, "weapon") ||
        XzSourceClass_ContainsFolded(class_name, "grenade") ||
        XzSourceClass_ContainsFolded(class_name, "_nade") ||
        XzSourceClass_ContainsFolded(class_name, "ammo") ||
        XzSourceClass_ContainsFolded(class_name, "projectile"))
        return XZ_PACKAGE_BOOT_WEAPONS_EQUIPMENT;

    if (XzSourceClass_ContainsFolded(class_name, "widget") ||
        XzSourceClass_ContainsFolded(class_name, "hud") ||
        XzSourceClass_ContainsFolded(class_name, "chalk") ||
        XzSourceClass_ContainsFolded(class_name, "icon"))
        return XZ_PACKAGE_BOOT_HUD_UI_PROMPTS;

    if (XzSourceClass_ContainsFolded(class_name, "music") ||
        XzSourceClass_ContainsFolded(class_name, "song") ||
        XzSourceClass_ContainsFolded(class_name, "radio") ||
        XzSourceClass_ContainsFolded(class_name, "voice") ||
        XzSourceClass_ContainsFolded(class_name, "vox"))
        return XZ_PACKAGE_BOOT_AMBIENT_MUSIC_VO;

    return XZ_PACKAGE_BOOT_GAMEPLAY_SCRIPTS;
}

int XzSourceClass_Classify(
    const char *class_name,
    XzPackageBootFamily *out_family)
{
    static const char *const world_names[] = {
        "Actor", "BrushComponent", "InstancedFoliageActor", "Landscape",
        "LandscapeComponent", "LandscapeGizmoActiveActor", "Level", "Model",
        "ModelComponent", "World", "WorldSettings"
    };
    static const char *const collision_names[] = {
        "BodySetup", "BlockingVolume", "BoxComponent", "CapsuleComponent",
        "DrawSphereComponent", "PhysicalMaterial", "PhysicsAsset",
        "PhysicsConstraintComponent", "PhysicsConstraintTemplate",
        "SkeletalBodySetup", "SphereComponent", "TriggerBox"
    };
    static const char *const script_names[] = {
        "BlueprintGeneratedClass", "ComponentDelegateBinding", "DataTable",
        "Function", "InheritableComponentHandler", "ScriptStruct",
        "SimpleConstructionScript", "TimelineComponent", "TimelineTemplate",
        "UserDefinedEnum", "UserDefinedStruct"
    };
    static const char *const interactable_names[] = {
        "ArrowComponent", "BillboardComponent", "CameraComponent",
        "CharacterMovementComponent", "ChildActorComponent",
        "ProjectileMovementComponent", "RotatingMovementComponent",
        "SceneComponent"
    };
    XzPackageBootFamily family;

    if (!class_name || !class_name[0] || !out_family)
        return 0;

    if (XzSourceClass_EndsWith(class_name, "_C")) {
        *out_family = XzSourceClass_ClassifyGenerated(class_name);
        return 1;
    }

    if (XzSourceClass_IsAny(
            class_name,
            world_names,
            sizeof(world_names) / sizeof(world_names[0])) ||
        XzSourceClass_StartsWith(class_name, "Landscape")) {
        family = XZ_PACKAGE_BOOT_WORLD_GEOMETRY;
    } else if (XzSourceClass_StartsWith(class_name, "StaticMesh")) {
        family = XZ_PACKAGE_BOOT_STATIC_MODELS_PROPS;
    } else if (XzSourceClass_StartsWith(class_name, "Texture") ||
               XzSourceClass_StartsWith(class_name, "Material") ||
               XzSourceClass_StartsWith(class_name, "ShadowMapTexture") ||
               XzSourceClass_StartsWith(class_name, "LightMapTexture") ||
               strcmp(class_name, "MapBuildDataRegistry") == 0) {
        family = XZ_PACKAGE_BOOT_MATERIALS_TEXTURES;
    } else if (XzSourceClass_IsAny(
                   class_name,
                   collision_names,
                   sizeof(collision_names) / sizeof(collision_names[0]))) {
        family = XZ_PACKAGE_BOOT_COLLISION;
    } else if (XzSourceClass_StartsWith(class_name, "Nav") ||
               XzSourceClass_StartsWith(class_name, "Navigation") ||
               XzSourceClass_StartsWith(class_name, "RecastNavMesh")) {
        family = XZ_PACKAGE_BOOT_NAVIGATION_PATHING;
    } else if (XzSourceClass_StartsWith(class_name, "SkeletalMesh") ||
               XzSourceClass_StartsWith(class_name, "Skeleton") ||
               XzSourceClass_StartsWith(class_name, "IK") ||
               XzSourceClass_StartsWith(class_name, "Retarget")) {
        family = XZ_PACKAGE_BOOT_ANIMATED_MODELS_RIGS;
    } else if (XzSourceClass_StartsWith(class_name, "Anim") ||
               XzSourceClass_StartsWith(class_name, "BlendSpace")) {
        family = XZ_PACKAGE_BOOT_ANIMATIONS;
    } else if (XzSourceClass_StartsWith(class_name, "Sound") ||
               XzSourceClass_StartsWith(class_name, "Audio") ||
               strcmp(class_name, "AmbientSound") == 0) {
        family = XZ_PACKAGE_BOOT_AUDIO_SFX;
    } else if (XzSourceClass_StartsWith(class_name, "Particle") ||
               XzSourceClass_StartsWith(class_name, "Niagara") ||
               XzSourceClass_StartsWith(class_name, "Distribution") ||
               XzSourceClass_StartsWith(class_name, "Emitter") ||
               XzSourceClass_StartsWith(class_name, "VectorField")) {
        family = XZ_PACKAGE_BOOT_VFX_PARTICLES;
    } else if (XzSourceClass_StartsWith(class_name, "PointLight") ||
               XzSourceClass_StartsWith(class_name, "SpotLight") ||
               XzSourceClass_StartsWith(class_name, "RectLight") ||
               XzSourceClass_StartsWith(class_name, "DirectionalLight") ||
               XzSourceClass_StartsWith(class_name, "SkyLight") ||
               XzSourceClass_StartsWith(class_name, "SkyAtmosphere") ||
               XzSourceClass_StartsWith(class_name, "ExponentialHeightFog") ||
               XzSourceClass_StartsWith(class_name, "VolumetricCloud") ||
               XzSourceClass_StartsWith(class_name, "PostProcess") ||
               XzSourceClass_StartsWith(class_name, "Decal") ||
               XzSourceClass_StartsWith(class_name, "SphereReflectionCapture") ||
               XzSourceClass_StartsWith(class_name, "PrecomputedVisibility") ||
               XzSourceClass_StartsWith(class_name, "SceneCapture") ||
               strcmp(class_name, "LightmassImportanceVolume") == 0) {
        family = XZ_PACKAGE_BOOT_LIGHTING_POSTFX;
    } else if (XzSourceClass_StartsWith(class_name, "Widget") ||
               XzSourceClass_StartsWith(class_name, "Text") ||
               XzSourceClass_StartsWith(class_name, "CanvasPanel") ||
               XzSourceClass_StartsWith(class_name, "HorizontalBox") ||
               XzSourceClass_StartsWith(class_name, "VerticalBox") ||
               XzSourceClass_StartsWith(class_name, "Border") ||
               XzSourceClass_StartsWith(class_name, "Button") ||
               XzSourceClass_StartsWith(class_name, "CheckBox") ||
               XzSourceClass_StartsWith(class_name, "ComboBox") ||
               strcmp(class_name, "Image") == 0 ||
               XzSourceClass_StartsWith(class_name, "ProgressBar") ||
               XzSourceClass_StartsWith(class_name, "RichTextBlock") ||
               XzSourceClass_StartsWith(class_name, "Slider") ||
               XzSourceClass_StartsWith(class_name, "BackgroundBlur") ||
               XzSourceClass_StartsWith(class_name, "PanelSlot") ||
               XzSourceClass_StartsWith(class_name, "Font")) {
        family = XZ_PACKAGE_BOOT_HUD_UI_PROMPTS;
    } else if (XzSourceClass_IsAny(
                   class_name,
                   script_names,
                   sizeof(script_names) / sizeof(script_names[0])) ||
               XzSourceClass_StartsWith(class_name, "SCS_") ||
               XzSourceClass_StartsWith(class_name, "Input") ||
               XzSourceClass_StartsWith(class_name, "Curve") ||
               XzSourceClass_StartsWith(class_name, "MovieScene") ||
               XzSourceClass_StartsWith(class_name, "LevelSequence") ||
               XzSourceClass_StartsWith(class_name, "Media") ||
               XzSourceClass_StartsWith(class_name, "ImgMediaSource") ||
               strcmp(class_name, "Pavlov_GameLogic") == 0) {
        family = XZ_PACKAGE_BOOT_GAMEPLAY_SCRIPTS;
    } else if (XzSourceClass_IsAny(
                   class_name,
                   interactable_names,
                   sizeof(interactable_names) / sizeof(interactable_names[0])) ||
               XzSourceClass_StartsWith(class_name, "Pavlov_") ||
               XzSourceClass_StartsWith(class_name, "VR") ||
               XzSourceClass_StartsWith(class_name, "TwoHandGrip") ||
               XzSourceClass_StartsWith(class_name, "HapticFeedback")) {
        family = XZ_PACKAGE_BOOT_INTERACTABLES;
    } else if (strcmp(class_name, "PlayerStart") == 0) {
        family = XZ_PACKAGE_BOOT_SPAWNS_ROUNDS_AI;
    } else {
        return 0;
    }

    *out_family = family;
    return 1;
}

void XzSourceClassCoverage_Init(
    XzSourceClassCoverage *coverage)
{
    if (!coverage)
        return;

    memset(coverage, 0, sizeof(*coverage));
}

int XzSourceClassCoverage_Record(
    XzSourceClassCoverage *coverage,
    const char *class_name)
{
    XzPackageBootFamily family;

    if (!coverage || !class_name || !class_name[0])
        return 0;

    coverage->source_class_count++;
    coverage->ready = 0;

    if (XzSourceClass_IsIgnorable(class_name)) {
        coverage->ignored_class_count++;
        return 1;
    }

    if (!XzSourceClass_Classify(class_name, &family)) {
        coverage->unclassified_class_count++;
        if (!coverage->first_unclassified[0]) {
            size_t n = strlen(class_name);
            if (n >= sizeof(coverage->first_unclassified))
                n = sizeof(coverage->first_unclassified) - 1u;
            memcpy(coverage->first_unclassified, class_name, n);
            coverage->first_unclassified[n] = '\0';
        }
        return 0;
    }

    coverage->classified_class_count++;
    coverage->family_class_count[(unsigned int)family]++;
    coverage->family_mask |= 1u << (unsigned int)family;
    return 1;
}

int XzSourceClassCoverage_Finalize(
    XzSourceClassCoverage *coverage)
{
    if (!coverage)
        return 0;

    coverage->ready =
        coverage->source_class_count > 0u &&
        coverage->classified_class_count +
            coverage->ignored_class_count ==
            coverage->source_class_count &&
        coverage->unclassified_class_count == 0u;

    return coverage->ready;
}

int XzSourceClassRegistry_SelfTest(void)
{
    XzSourceClassCoverage coverage;
    XzPackageBootFamily family;

    if (!XzSourceClass_Classify("StaticMeshActor", &family) ||
        family != XZ_PACKAGE_BOOT_STATIC_MODELS_PROPS)
        return 0;

    if (!XzSourceClass_Classify("SoundWave", &family) ||
        family != XZ_PACKAGE_BOOT_AUDIO_SFX)
        return 0;

    if (!XzSourceClass_Classify("SomeZombieSpawner_C", &family) ||
        family != XZ_PACKAGE_BOOT_SPAWNS_ROUNDS_AI)
        return 0;

    if (!XzSourceClass_Classify("SomeMysteryBox_C", &family) ||
        family != XZ_PACKAGE_BOOT_MYSTERY_BOX)
        return 0;

    if (!XzSourceClass_Classify("Pavlov_GameLogic", &family) ||
        family != XZ_PACKAGE_BOOT_GAMEPLAY_SCRIPTS)
        return 0;

    if (XzSourceClass_Classify("UnknownNativeRuntimeThing", &family))
        return 0;

    XzSourceClassCoverage_Init(&coverage);
    if (!XzSourceClassCoverage_Record(&coverage, "Texture2D") ||
        !XzSourceClassCoverage_Record(&coverage, "AnimSequence") ||
        !XzSourceClassCoverage_Record(&coverage, "GenericBlueprint_C") ||
        !XzSourceClassCoverage_Record(&coverage, "BookMark") ||
        !XzSourceClassCoverage_Finalize(&coverage))
        return 0;

    if (!coverage.ready ||
        coverage.classified_class_count != 3u ||
        coverage.ignored_class_count != 1u ||
        coverage.unclassified_class_count != 0u)
        return 0;

    XzSourceClassCoverage_Init(&coverage);
    if (!XzSourceClassCoverage_Record(&coverage, "StaticMesh"))
        return 0;
    if (XzSourceClassCoverage_Record(
            &coverage,
            "UnknownNativeRuntimeThing"))
        return 0;
    if (XzSourceClassCoverage_Finalize(&coverage))
        return 0;

    return coverage.unclassified_class_count == 1u &&
           strcmp(
               coverage.first_unclassified,
               "UnknownNativeRuntimeThing") == 0;
}

#include "xz_source_native_registry.h"

#include <string.h>

static const XzSourceNativeAdapter g_adapters[] = {
    {
        "StaticMesh",
        XZ_SOURCE_WORLD_GEOMETRY,
        XZ_NATIVE_PAYLOAD_XZMS,
        "XZMS",
        ".xzm"
    },
    {
        "Texture2D",
        XZ_SOURCE_MATERIAL_TEXTURE_SHADER,
        XZ_NATIVE_PAYLOAD_XZTX,
        "XZTX",
        ".xzt"
    },
    {
        "LightMapTexture2D",
        XZ_SOURCE_MATERIAL_TEXTURE_SHADER,
        XZ_NATIVE_PAYLOAD_XZTX,
        "XZTX",
        ".xzt"
    },
    {
        "SoundWave",
        XZ_SOURCE_AUDIO,
        XZ_NATIVE_PAYLOAD_XZAW,
        "XZAW",
        ".xaw"
    },
    {
        "SkeletalMesh",
        XZ_SOURCE_ANIMATION_RIG,
        XZ_NATIVE_PAYLOAD_XZSK,
        "XZSK",
        ".xsk"
    },
    {
        "AnimSequence",
        XZ_SOURCE_ANIMATION_RIG,
        XZ_NATIVE_PAYLOAD_XZAN,
        "XZAN",
        ".xan"
    }
};

static const char *const g_type_names[
    XZ_NATIVE_PAYLOAD_TYPE_COUNT] = {
    "none",
    "xzms",
    "xztx",
    "xzaw",
    "xzsk",
    "xzan"
};

const XzSourceNativeAdapter *XzSourceNativeRegistry_Find(
    const char *source_class)
{
    unsigned int i;

    if (!source_class || !source_class[0])
        return NULL;

    for (i = 0u;
         i < sizeof(g_adapters) / sizeof(g_adapters[0]);
         ++i) {
        if (strcmp(
                source_class,
                g_adapters[i].source_class) == 0)
            return &g_adapters[i];
    }

    return NULL;
}

const char *XzSourceNativeRegistry_TypeName(
    XzNativePayloadType type)
{
    if ((unsigned int)type >=
        XZ_NATIVE_PAYLOAD_TYPE_COUNT)
        return "unknown";

    return g_type_names[
        (unsigned int)type];
}

int XzSourceNativeRegistry_SelfTest(void)
{
    const XzSourceNativeAdapter *adapter;

    adapter =
        XzSourceNativeRegistry_Find(
            "StaticMesh");
    if (!adapter ||
        adapter->native_type !=
            XZ_NATIVE_PAYLOAD_XZMS ||
        adapter->source_kind !=
            XZ_SOURCE_WORLD_GEOMETRY ||
        strcmp(adapter->magic, "XZMS") != 0)
        return 0;

    adapter =
        XzSourceNativeRegistry_Find(
            "Texture2D");
    if (!adapter ||
        adapter->native_type !=
            XZ_NATIVE_PAYLOAD_XZTX ||
        adapter->source_kind !=
            XZ_SOURCE_MATERIAL_TEXTURE_SHADER)
        return 0;

    adapter =
        XzSourceNativeRegistry_Find(
            "LightMapTexture2D");
    if (!adapter ||
        adapter->native_type !=
            XZ_NATIVE_PAYLOAD_XZTX)
        return 0;

    adapter =
        XzSourceNativeRegistry_Find(
            "SoundWave");
    if (!adapter ||
        adapter->native_type !=
            XZ_NATIVE_PAYLOAD_XZAW ||
        adapter->source_kind !=
            XZ_SOURCE_AUDIO)
        return 0;

    adapter =
        XzSourceNativeRegistry_Find(
            "SkeletalMesh");
    if (!adapter ||
        adapter->native_type !=
            XZ_NATIVE_PAYLOAD_XZSK ||
        adapter->source_kind !=
            XZ_SOURCE_ANIMATION_RIG)
        return 0;

    adapter =
        XzSourceNativeRegistry_Find(
            "AnimSequence");
    if (!adapter ||
        adapter->native_type !=
            XZ_NATIVE_PAYLOAD_XZAN)
        return 0;

    if (XzSourceNativeRegistry_Find(
            "Material") != NULL)
        return 0;

    return 1;
}

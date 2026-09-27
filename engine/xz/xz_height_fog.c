#include "xz_height_fog.h"

#include <math.h>
#include <string.h>

static uint32_t XzHeightFog_ReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzHeightFog_ReadF32Le(
    const unsigned char *p)
{
    uint32_t bits =
        XzHeightFog_ReadU32Le(p);
    float value;

    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzHeightFog_FiniteColor(
    const float color[3])
{
    return color &&
           isfinite(color[0]) &&
           isfinite(color[1]) &&
           isfinite(color[2]) &&
           color[0] >= 0.0f &&
           color[1] >= 0.0f &&
           color[2] >= 0.0f;
}

XzHeightFogStatus XzHeightFog_Parse(
    XzHeightFogView *view,
    const unsigned char *data,
    size_t bytes)
{
    uint32_t flags;
    float values[XZ_HEIGHT_FOG_FLOAT_COUNT];
    uint32_t i;
    const uint32_t known_flags =
        XZ_HEIGHT_FOG_FLAG_VOLUMETRIC |
        XZ_HEIGHT_FOG_FLAG_CUBEMAP |
        XZ_HEIGHT_FOG_FLAG_SECOND_FOG;

    if (!view || !data)
        return XZ_HEIGHT_FOG_NULL;

    memset(view, 0, sizeof(*view));

    if (bytes != XZ_HEIGHT_FOG_BYTES)
        return XZ_HEIGHT_FOG_BAD_SIZE;

    if (data[0] != 'X' ||
        data[1] != 'Z' ||
        data[2] != 'F' ||
        data[3] != 'G')
        return XZ_HEIGHT_FOG_BAD_MAGIC;

    if (XzHeightFog_ReadU32Le(data + 4u) !=
            XZ_HEIGHT_FOG_VERSION)
        return XZ_HEIGHT_FOG_BAD_VERSION;

    flags = XzHeightFog_ReadU32Le(data + 8u);
    if ((flags & ~known_flags) != 0u)
        return XZ_HEIGHT_FOG_BAD_FLAGS;

    for (i = 0u;
         i < XZ_HEIGHT_FOG_FLOAT_COUNT;
         ++i) {
        values[i] =
            XzHeightFog_ReadF32Le(
                data +
                XZ_HEIGHT_FOG_HEADER_BYTES +
                (size_t)i * 4u);
        if (!isfinite(values[i]))
            return XZ_HEIGHT_FOG_BAD_VALUE;
    }

    view->flags = flags;
    view->fog_height_meters = values[0];
    view->density = values[1];
    view->height_falloff = values[2];
    view->max_opacity = values[3];
    view->start_distance_meters = values[4];
    view->cutoff_distance_meters = values[5];
    view->fog_color_linear[0] = values[6];
    view->fog_color_linear[1] = values[7];
    view->fog_color_linear[2] = values[8];

    view->second_density = values[9];
    view->second_height_falloff = values[10];
    view->second_height_meters = values[11];

    view->directional_exponent = values[12];
    view->directional_start_distance_meters =
        values[13];
    view->directional_color_linear[0] = values[14];
    view->directional_color_linear[1] = values[15];
    view->directional_color_linear[2] = values[16];

    view->volumetric_distance_meters = values[17];

    if (view->density < 0.0f ||
        view->density > 10.0f ||
        view->height_falloff < 0.0f ||
        view->height_falloff > 2.0f ||
        view->max_opacity < 0.0f ||
        view->max_opacity > 1.0f ||
        view->start_distance_meters < 0.0f ||
        view->cutoff_distance_meters < 0.0f ||
        view->second_density < 0.0f ||
        view->second_height_falloff < 0.0f ||
        view->directional_exponent <= 0.0f ||
        view->directional_start_distance_meters < 0.0f ||
        view->volumetric_distance_meters < 0.0f ||
        !XzHeightFog_FiniteColor(
            view->fog_color_linear) ||
        !XzHeightFog_FiniteColor(
            view->directional_color_linear))
        return XZ_HEIGHT_FOG_BAD_VALUE;

    if ((flags & XZ_HEIGHT_FOG_FLAG_VOLUMETRIC) == 0u &&
        view->volumetric_distance_meters < 0.0f)
        return XZ_HEIGHT_FOG_BAD_VALUE;

    return XZ_HEIGHT_FOG_OK;
}

const char *XzHeightFog_StatusName(
    XzHeightFogStatus status)
{
    switch (status) {
    case XZ_HEIGHT_FOG_OK:
        return "OK";
    case XZ_HEIGHT_FOG_NULL:
        return "NULL";
    case XZ_HEIGHT_FOG_BAD_SIZE:
        return "BAD_SIZE";
    case XZ_HEIGHT_FOG_BAD_MAGIC:
        return "BAD_MAGIC";
    case XZ_HEIGHT_FOG_BAD_VERSION:
        return "BAD_VERSION";
    case XZ_HEIGHT_FOG_BAD_FLAGS:
        return "BAD_FLAGS";
    case XZ_HEIGHT_FOG_BAD_VALUE:
        return "BAD_VALUE";
    default:
        return "UNKNOWN";
    }
}

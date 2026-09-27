#include "xz_environment.h"

#include <math.h>
#include <string.h>

static uint32_t XzEnvReadU32Le(
    const unsigned char *p)
{
    return ((uint32_t)p[0]) |
           ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) |
           ((uint32_t)p[3] << 24);
}

static float XzEnvReadF32Le(
    const unsigned char *p)
{
    uint32_t bits = XzEnvReadU32Le(p);
    float value;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int XzEnvFinite3(
    const float v[3])
{
    return isfinite(v[0]) &&
           isfinite(v[1]) &&
           isfinite(v[2]);
}

int XzEnvironment_ReadLight(
    const XzEnvironmentView *view,
    uint32_t index,
    XzEnvironmentLight *light)
{
    const unsigned char *p;

    if (!view ||
        !view->data ||
        !light ||
        index >= view->light_count)
        return 0;

    p = view->data +
        view->lights_offset +
        (size_t)index *
            XZ_ENV_LIGHT_BYTES;

    memset(light, 0, sizeof(*light));

    light->type = XzEnvReadU32Le(p + 0u);
    light->flags = XzEnvReadU32Le(p + 4u);

    light->position[0] = XzEnvReadF32Le(p + 8u);
    light->position[1] = XzEnvReadF32Le(p + 12u);
    light->position[2] = XzEnvReadF32Le(p + 16u);

    light->rotation[0] = XzEnvReadF32Le(p + 20u);
    light->rotation[1] = XzEnvReadF32Le(p + 24u);
    light->rotation[2] = XzEnvReadF32Le(p + 28u);

    light->color[0] = XzEnvReadF32Le(p + 32u);
    light->color[1] = XzEnvReadF32Le(p + 36u);
    light->color[2] = XzEnvReadF32Le(p + 40u);

    light->intensity = XzEnvReadF32Le(p + 44u);
    light->radius_meters = XzEnvReadF32Le(p + 48u);
    light->inner_cone_degrees = XzEnvReadF32Le(p + 52u);
    light->outer_cone_degrees = XzEnvReadF32Le(p + 56u);
    light->units = XzEnvReadU32Le(p + 60u);

    if (light->type < XZ_ENV_LIGHT_POINT ||
        light->type > XZ_ENV_LIGHT_SKY ||
        (light->flags & ~((1u << 7) - 1u)) != 0u ||
        !XzEnvFinite3(light->position) ||
        !XzEnvFinite3(light->rotation) ||
        !XzEnvFinite3(light->color) ||
        !isfinite(light->intensity) ||
        !isfinite(light->radius_meters) ||
        light->radius_meters < 0.0f ||
        !isfinite(light->inner_cone_degrees) ||
        !isfinite(light->outer_cone_degrees))
        return 0;

    if (light->type == XZ_ENV_LIGHT_SPOT) {
        if ((light->flags & XZ_ENV_HAS_CONE) == 0u ||
            light->inner_cone_degrees < 0.0f ||
            light->outer_cone_degrees <=
                light->inner_cone_degrees ||
            light->outer_cone_degrees >= 90.0f)
            return 0;
    } else if ((light->flags & XZ_ENV_HAS_CONE) != 0u) {
        return 0;
    }

    return 1;
}

XzEnvironmentStatus XzEnvironment_Parse(
    XzEnvironmentView *view,
    const unsigned char *data,
    size_t bytes)
{
    uint32_t lights;
    uint32_t points;
    uint32_t spots;
    uint32_t directional;
    uint32_t sky;
    uint64_t expected;
    uint32_t actual_points = 0u;
    uint32_t actual_spots = 0u;
    uint32_t actual_directional = 0u;
    uint32_t actual_sky = 0u;
    uint32_t i;

    if (!view || !data)
        return XZ_ENV_NULL;

    memset(view, 0, sizeof(*view));

    if (bytes < XZ_ENV_HEADER_BYTES)
        return XZ_ENV_TOO_SMALL;

    if (data[0] != 'X' ||
        data[1] != 'Z' ||
        data[2] != 'E' ||
        data[3] != 'N')
        return XZ_ENV_BAD_MAGIC;

    if (XzEnvReadU32Le(data + 4u) !=
            XZ_ENV_VERSION)
        return XZ_ENV_BAD_VERSION;

    lights = XzEnvReadU32Le(data + 8u);
    points = XzEnvReadU32Le(data + 12u);
    spots = XzEnvReadU32Le(data + 16u);
    directional = XzEnvReadU32Le(data + 20u);
    sky = XzEnvReadU32Le(data + 24u);

    if (lights == 0u ||
        points + spots + directional + sky != lights)
        return XZ_ENV_BAD_COUNTS;

    expected =
        (uint64_t)XZ_ENV_HEADER_BYTES +
        (uint64_t)lights *
            (uint64_t)XZ_ENV_LIGHT_BYTES;

    if (expected != (uint64_t)bytes)
        return XZ_ENV_BAD_SIZE;

    view->data = data;
    view->bytes = bytes;
    view->light_count = lights;
    view->point_count = points;
    view->spot_count = spots;
    view->directional_count = directional;
    view->sky_count = sky;
    view->lights_offset = XZ_ENV_HEADER_BYTES;

    for (i = 0u; i < lights; ++i) {
        XzEnvironmentLight light;

        if (!XzEnvironment_ReadLight(
                view,
                i,
                &light)) {
            memset(view, 0, sizeof(*view));
            return XZ_ENV_BAD_LIGHT;
        }

        switch (light.type) {
        case XZ_ENV_LIGHT_POINT:
            actual_points++;
            break;
        case XZ_ENV_LIGHT_SPOT:
            actual_spots++;
            break;
        case XZ_ENV_LIGHT_DIRECTIONAL:
            actual_directional++;
            break;
        case XZ_ENV_LIGHT_SKY:
            actual_sky++;
            break;
        default:
            memset(view, 0, sizeof(*view));
            return XZ_ENV_BAD_LIGHT;
        }
    }

    if (actual_points != points ||
        actual_spots != spots ||
        actual_directional != directional ||
        actual_sky != sky) {
        memset(view, 0, sizeof(*view));
        return XZ_ENV_BAD_COUNTS;
    }

    return XZ_ENV_OK;
}

const char *XzEnvironment_StatusName(
    XzEnvironmentStatus status)
{
    switch (status) {
    case XZ_ENV_OK:
        return "OK";
    case XZ_ENV_NULL:
        return "NULL";
    case XZ_ENV_TOO_SMALL:
        return "TOO_SMALL";
    case XZ_ENV_BAD_MAGIC:
        return "BAD_MAGIC";
    case XZ_ENV_BAD_VERSION:
        return "BAD_VERSION";
    case XZ_ENV_BAD_COUNTS:
        return "BAD_COUNTS";
    case XZ_ENV_BAD_SIZE:
        return "BAD_SIZE";
    case XZ_ENV_BAD_LIGHT:
        return "BAD_LIGHT";
    default:
        return "UNKNOWN";
    }
}

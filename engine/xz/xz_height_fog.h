#ifndef XZ_HEIGHT_FOG_H
#define XZ_HEIGHT_FOG_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_HEIGHT_FOG_MAGIC_BYTES 4u
#define XZ_HEIGHT_FOG_VERSION 1u
#define XZ_HEIGHT_FOG_HEADER_BYTES 12u
#define XZ_HEIGHT_FOG_FLOAT_COUNT 20u
#define XZ_HEIGHT_FOG_BYTES 92u

enum {
    XZ_HEIGHT_FOG_FLAG_VOLUMETRIC = 1u << 0,
    XZ_HEIGHT_FOG_FLAG_CUBEMAP = 1u << 1,
    XZ_HEIGHT_FOG_FLAG_SECOND_FOG = 1u << 2
};

typedef enum {
    XZ_HEIGHT_FOG_OK = 0,
    XZ_HEIGHT_FOG_NULL,
    XZ_HEIGHT_FOG_BAD_SIZE,
    XZ_HEIGHT_FOG_BAD_MAGIC,
    XZ_HEIGHT_FOG_BAD_VERSION,
    XZ_HEIGHT_FOG_BAD_FLAGS,
    XZ_HEIGHT_FOG_BAD_VALUE
} XzHeightFogStatus;

typedef struct {
    uint32_t flags;

    float fog_height_meters;
    float density;
    float height_falloff;
    float max_opacity;
    float start_distance_meters;
    float cutoff_distance_meters;
    float fog_color_linear[3];

    float second_density;
    float second_height_falloff;
    float second_height_meters;

    float directional_exponent;
    float directional_start_distance_meters;
    float directional_color_linear[3];

    float volumetric_distance_meters;
} XzHeightFogView;

XzHeightFogStatus XzHeightFog_Parse(
    XzHeightFogView *view,
    const unsigned char *data,
    size_t bytes);

const char *XzHeightFog_StatusName(
    XzHeightFogStatus status);

#ifdef __cplusplus
}
#endif

#endif

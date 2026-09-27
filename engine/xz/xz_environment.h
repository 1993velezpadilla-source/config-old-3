#ifndef XZ_ENVIRONMENT_H
#define XZ_ENVIRONMENT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_ENV_MAGIC_BYTES 4u
#define XZ_ENV_VERSION 1u
#define XZ_ENV_HEADER_BYTES 28u
#define XZ_ENV_LIGHT_BYTES 56u

enum {
    XZ_ENV_LIGHT_POINT = 1u,
    XZ_ENV_LIGHT_SPOT = 2u,
    XZ_ENV_LIGHT_DIRECTIONAL = 3u,
    XZ_ENV_LIGHT_SKY = 4u
};

enum {
    XZ_ENV_HAS_POSITION = 1u << 0,
    XZ_ENV_HAS_ROTATION = 1u << 1,
    XZ_ENV_HAS_COLOR = 1u << 2,
    XZ_ENV_HAS_INTENSITY = 1u << 3,
    XZ_ENV_HAS_RADIUS = 1u << 4,
    XZ_ENV_HAS_UNITS = 1u << 5
};

typedef enum {
    XZ_ENV_OK = 0,
    XZ_ENV_NULL,
    XZ_ENV_TOO_SMALL,
    XZ_ENV_BAD_MAGIC,
    XZ_ENV_BAD_VERSION,
    XZ_ENV_BAD_COUNTS,
    XZ_ENV_BAD_SIZE,
    XZ_ENV_BAD_LIGHT
} XzEnvironmentStatus;

typedef struct {
    const unsigned char *data;
    size_t bytes;
    uint32_t light_count;
    uint32_t point_count;
    uint32_t spot_count;
    uint32_t directional_count;
    uint32_t sky_count;
    size_t lights_offset;
} XzEnvironmentView;

typedef struct {
    uint32_t type;
    uint32_t flags;
    float position[3];
    float rotation[3];
    float color[3];
    float intensity;
    float radius_meters;
    uint32_t units;
} XzEnvironmentLight;

XzEnvironmentStatus XzEnvironment_Parse(
    XzEnvironmentView *view,
    const unsigned char *data,
    size_t bytes);

int XzEnvironment_ReadLight(
    const XzEnvironmentView *view,
    uint32_t index,
    XzEnvironmentLight *light);

const char *XzEnvironment_StatusName(
    XzEnvironmentStatus status);

#ifdef __cplusplus
}
#endif

#endif

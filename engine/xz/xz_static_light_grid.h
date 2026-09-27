#ifndef XZ_STATIC_LIGHT_GRID_H
#define XZ_STATIC_LIGHT_GRID_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_STATIC_LIGHT_GRID_CAPACITY 96u
#define XZ_STATIC_LIGHT_GRID_STRIDE \
    (XZ_STATIC_LIGHT_GRID_CAPACITY + 1u)
#define XZ_STATIC_LIGHT_GRID_MAX_CELLS 262144u

typedef struct {
    float position[3];
    float radius;
} XzStaticLightSphere;

typedef struct {
    float minimum[3];
    float cell_size;
    uint32_t dimensions[3];
    uint32_t cell_count;
    uint32_t max_lights_per_cell;
    unsigned char *cells;
    size_t cell_bytes;
} XzStaticLightGrid;

void XzStaticLightGrid_Init(
    XzStaticLightGrid *grid);

void XzStaticLightGrid_Reset(
    XzStaticLightGrid *grid);

int XzStaticLightGrid_Build(
    XzStaticLightGrid *grid,
    const float scene_minimum[3],
    const float scene_maximum[3],
    float cell_size,
    const XzStaticLightSphere *lights,
    uint32_t light_count);

int XzStaticLightGrid_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif

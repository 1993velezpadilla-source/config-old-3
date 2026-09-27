#include "xz_static_light_grid.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

static int XzFinite3(
    const float value[3])
{
    return
        value &&
        isfinite(value[0]) &&
        isfinite(value[1]) &&
        isfinite(value[2]);
}

static float XzAxisDistanceToCell(
    float value,
    float minimum,
    float maximum)
{
    if (value < minimum)
        return minimum - value;
    if (value > maximum)
        return value - maximum;
    return 0.0f;
}

void XzStaticLightGrid_Init(
    XzStaticLightGrid *grid)
{
    if (!grid)
        return;

    memset(grid, 0, sizeof(*grid));
}

void XzStaticLightGrid_Reset(
    XzStaticLightGrid *grid)
{
    if (!grid)
        return;

    free(grid->cells);
    memset(grid, 0, sizeof(*grid));
}

int XzStaticLightGrid_Build(
    XzStaticLightGrid *grid,
    const float scene_minimum[3],
    const float scene_maximum[3],
    float cell_size,
    const XzStaticLightSphere *lights,
    uint32_t light_count)
{
    float minimum[3];
    float maximum[3];
    uint32_t dimensions[3];
    uint64_t cell_count_64 = 1u;
    uint64_t cell_bytes_64;
    unsigned char *cells = NULL;
    uint32_t x;
    uint32_t y;
    uint32_t z;
    uint32_t max_lights = 0u;
    unsigned int axis;

    if (!grid ||
        !scene_minimum ||
        !scene_maximum ||
        !lights ||
        light_count == 0u ||
        light_count > 255u ||
        !XzFinite3(scene_minimum) ||
        !XzFinite3(scene_maximum) ||
        !isfinite(cell_size) ||
        cell_size <= 0.0f)
        return 0;

    for (axis = 0u; axis < 3u; ++axis) {
        float extent;

        if (scene_maximum[axis] <
            scene_minimum[axis])
            return 0;

        /*
         * Align to cell boundaries and add one full guard cell on both
         * sides. Mesh AABBs transformed from local bounds are conservative,
         * so every rasterized static-scene fragment must land inside this
         * padded grid.
         */
        minimum[axis] =
            floorf(
                scene_minimum[axis] /
                cell_size) *
            cell_size -
            cell_size;

        maximum[axis] =
            ceilf(
                scene_maximum[axis] /
                cell_size) *
            cell_size +
            cell_size;

        extent =
            maximum[axis] -
            minimum[axis];

        if (!isfinite(extent) ||
            extent <= 0.0f)
            return 0;

        dimensions[axis] =
            (uint32_t)ceilf(
                extent / cell_size);

        if (dimensions[axis] == 0u)
            return 0;

        cell_count_64 *=
            (uint64_t)dimensions[axis];

        if (cell_count_64 >
            XZ_STATIC_LIGHT_GRID_MAX_CELLS)
            return 0;
    }

    cell_bytes_64 =
        cell_count_64 *
        (uint64_t)XZ_STATIC_LIGHT_GRID_STRIDE;

    if (cell_bytes_64 == 0u ||
        cell_bytes_64 > (uint64_t)SIZE_MAX)
        return 0;

    cells = (unsigned char *)calloc(
        (size_t)cell_bytes_64,
        1u);
    if (!cells)
        return 0;

    for (z = 0u;
         z < dimensions[2];
         ++z) {
        const float cell_z0 =
            minimum[2] +
            (float)z * cell_size;
        const float cell_z1 =
            cell_z0 + cell_size;

        for (y = 0u;
             y < dimensions[1];
             ++y) {
            const float cell_y0 =
                minimum[1] +
                (float)y * cell_size;
            const float cell_y1 =
                cell_y0 + cell_size;

            for (x = 0u;
                 x < dimensions[0];
                 ++x) {
                const float cell_x0 =
                    minimum[0] +
                    (float)x * cell_size;
                const float cell_x1 =
                    cell_x0 + cell_size;
                const uint32_t cell_index =
                    x +
                    dimensions[0] *
                        (y +
                         dimensions[1] * z);
                unsigned char *record =
                    cells +
                    (size_t)cell_index *
                        XZ_STATIC_LIGHT_GRID_STRIDE;
                uint32_t count = 0u;
                uint32_t light_index;

                for (light_index = 0u;
                     light_index < light_count;
                     ++light_index) {
                    const XzStaticLightSphere *light =
                        &lights[light_index];
                    float dx;
                    float dy;
                    float dz;
                    float distance_sq;
                    float radius_sq;

                    if (!XzFinite3(
                            light->position) ||
                        !isfinite(light->radius) ||
                        light->radius <= 0.0f) {
                        free(cells);
                        return 0;
                    }

                    dx = XzAxisDistanceToCell(
                        light->position[0],
                        cell_x0,
                        cell_x1);
                    dy = XzAxisDistanceToCell(
                        light->position[1],
                        cell_y0,
                        cell_y1);
                    dz = XzAxisDistanceToCell(
                        light->position[2],
                        cell_z0,
                        cell_z1);

                    distance_sq =
                        dx * dx +
                        dy * dy +
                        dz * dz;
                    radius_sq =
                        light->radius *
                        light->radius;

                    if (distance_sq >
                        radius_sq)
                        continue;

                    if (count >=
                        XZ_STATIC_LIGHT_GRID_CAPACITY) {
                        free(cells);
                        return 0;
                    }

                    record[1u + count] =
                        (unsigned char)light_index;
                    count++;
                }

                record[0] =
                    (unsigned char)count;

                if (count > max_lights)
                    max_lights = count;
            }
        }
    }

    XzStaticLightGrid_Reset(grid);

    for (axis = 0u; axis < 3u; ++axis) {
        grid->minimum[axis] =
            minimum[axis];
        grid->dimensions[axis] =
            dimensions[axis];
    }

    grid->cell_size = cell_size;
    grid->cell_count =
        (uint32_t)cell_count_64;
    grid->max_lights_per_cell =
        max_lights;
    grid->cells = cells;
    grid->cell_bytes =
        (size_t)cell_bytes_64;

    return 1;
}

int XzStaticLightGrid_SelfTest(void)
{
    XzStaticLightGrid grid;
    XzStaticLightSphere lights[2];
    const float scene_minimum[3] = {
        0.0f, 0.0f, 0.0f
    };
    const float scene_maximum[3] = {
        8.0f, 4.0f, 4.0f
    };
    uint32_t cell_index;
    const unsigned char *record;

    memset(lights, 0, sizeof(lights));

    lights[0].position[0] = 1.0f;
    lights[0].position[1] = 1.0f;
    lights[0].position[2] = 1.0f;
    lights[0].radius = 2.0f;

    lights[1].position[0] = 7.0f;
    lights[1].position[1] = 1.0f;
    lights[1].position[2] = 1.0f;
    lights[1].radius = 2.0f;

    XzStaticLightGrid_Init(&grid);

    if (!XzStaticLightGrid_Build(
            &grid,
            scene_minimum,
            scene_maximum,
            4.0f,
            lights,
            2u))
        return 0;

    if (!grid.cells ||
        grid.cell_count == 0u ||
        grid.max_lights_per_cell == 0u ||
        grid.max_lights_per_cell > 2u)
        goto fail;

    /*
     * Scene minimum 0 aligns to 0 then receives a 4-unit guard cell,
     * so world cell [0,4] is x index 1. Both test spheres touch it.
     */
    cell_index =
        1u +
        grid.dimensions[0] *
            (1u +
             grid.dimensions[1] * 1u);

    if (cell_index >= grid.cell_count)
        goto fail;

    record =
        grid.cells +
        (size_t)cell_index *
            XZ_STATIC_LIGHT_GRID_STRIDE;

    if (record[0] != 2u ||
        record[1] != 0u ||
        record[2] != 1u)
        goto fail;

    XzStaticLightGrid_Reset(&grid);
    return 1;

fail:
    XzStaticLightGrid_Reset(&grid);
    return 0;
}

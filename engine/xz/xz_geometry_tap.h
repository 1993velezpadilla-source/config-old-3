#ifndef XZ_GEOMETRY_TAP_H
#define XZ_GEOMETRY_TAP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define XZ_GEOMETRY_MAX_BATCHES 2048u
#define XZ_GEOMETRY_MAX_VERTICES 131072u
#define XZ_GEOMETRY_MAX_INDICES 262144u

typedef enum {
    XZ_GEOMETRY_ALIAS = 0,
    XZ_GEOMETRY_SURFACE,
    XZ_GEOMETRY_SPRITE,
    XZ_GEOMETRY_EFFECT,
    XZ_GEOMETRY_SPECIAL
} XzGeometryKind;

typedef enum {
    XZ_GEOMETRY_SPECIAL_NONE = 0,
    XZ_GEOMETRY_SPECIAL_SKY,
    XZ_GEOMETRY_SPECIAL_WATER
} XzGeometrySpecialKind;

typedef enum {
    XZ_GEOMETRY_TRIANGLES = 0,
    XZ_GEOMETRY_TRIANGLE_FAN,
    XZ_GEOMETRY_TRIANGLE_STRIP
} XzGeometryPrimitive;

typedef struct {
    float position[3];
    float uv[2];
} XzGeometryVertex;

/* Exact captured fixed-function state at the corresponding source draw call.
 * Numeric enum values are preserved verbatim so the GLES3 replay can map
 * blend/depth/alpha semantics without linking the tap core to GL headers. */
typedef struct {
    float color[4];
    unsigned int blend_enabled;
    unsigned int blend_src;
    unsigned int blend_dst;
    unsigned int depth_test_enabled;
    unsigned int depth_write;
    unsigned int depth_func;
    unsigned int alpha_test_enabled;
    unsigned int alpha_func;
    float alpha_ref;
    unsigned int texture_env_mode;
    unsigned int texture_enabled;

    unsigned int fog_enabled;
    float fog_start;
    float fog_end;
    float fog_color[4];

    float depth_range[2];
    unsigned int cull_enabled;
    unsigned int cull_face;
    unsigned int front_face;

    unsigned int polygon_offset_enabled;
    float polygon_offset_factor;
    float polygon_offset_units;
} XzGeometryRenderState;

typedef struct {
    unsigned int first_vertex;
    unsigned int vertex_count;
    unsigned int first_index;
    unsigned int index_count;
    XzGeometryKind kind;
    XzGeometrySpecialKind special_kind;
    int texture_id;
    XzGeometryRenderState state;
    float modelview[16];
    float projection[16];
} XzGeometryBatch;

typedef struct {
    uint64_t generation;
    XzGeometryBatch batches[XZ_GEOMETRY_MAX_BATCHES];
    XzGeometryVertex vertices[XZ_GEOMETRY_MAX_VERTICES];
    uint32_t indices[XZ_GEOMETRY_MAX_INDICES];

    unsigned int batch_count;
    unsigned int vertex_count;
    unsigned int index_count;

    unsigned int alias_batches;
    unsigned int surface_batches;
    unsigned int sprite_batches;
    unsigned int effect_batches;
    unsigned int shadow_batches;
    unsigned int special_batches;
    unsigned int sky_batches;
    unsigned int water_batches;

    unsigned int dropped_batches;
    unsigned int dropped_vertices;
    unsigned int dropped_indices;
} XzGeometryFrame;

void XzGeometryTap_Init(void);
void XzGeometryTap_BeginFrame(uint64_t generation);
void XzGeometryTap_CommitFrame(void);

int XzGeometryTap_CaptureAlias(
    const void *vertices,
    unsigned int vertex_count,
    unsigned int vertex_stride,
    unsigned int xyz_offset,
    unsigned int uv_offset,
    const uint16_t *indices,
    unsigned int index_count,
    int texture_id,
    const XzGeometryRenderState *state,
    const float modelview[16],
    const float projection[16]);

int XzGeometryTap_CaptureSurfaceFan(
    const float *source,
    unsigned int count,
    unsigned int stride_floats,
    unsigned int position_offset,
    unsigned int texture_offset,
    int texture_id,
    const XzGeometryRenderState *state,
    const float modelview[16],
    const float projection[16]);

int XzGeometryTap_CaptureSpriteQuad(
    const float positions[12],
    const float uvs[8],
    int texture_id,
    const XzGeometryRenderState *state,
    const float modelview[16],
    const float projection[16]);

int XzGeometryTap_CapturePrimitive(
    const float *source,
    unsigned int count,
    unsigned int stride_floats,
    unsigned int position_offset,
    unsigned int texture_offset,
    XzGeometryPrimitive primitive,
    int texture_id,
    const XzGeometryRenderState *state,
    const float modelview[16],
    const float projection[16]);

int XzGeometryTap_CaptureShadowPrimitive(
    const float *source,
    unsigned int count,
    unsigned int stride_floats,
    unsigned int position_offset,
    unsigned int texture_offset,
    XzGeometryPrimitive primitive,
    const XzGeometryRenderState *state,
    const float modelview[16],
    const float projection[16]);

int XzGeometryTap_CaptureSpecialFan(
    const float *source,
    unsigned int count,
    unsigned int stride_floats,
    unsigned int position_offset,
    unsigned int texture_offset,
    int texture_id,
    XzGeometrySpecialKind special_kind,
    const XzGeometryRenderState *state,
    const float modelview[16],
    const float projection[16]);

const XzGeometryFrame *XzGeometryTap_GetReadFrame(void);
const XzGeometryFrame *XzGeometryTap_GetWriteFrame(void);
int XzGeometryTap_SelfTest(void);

#ifdef __cplusplus
}
#endif

#endif

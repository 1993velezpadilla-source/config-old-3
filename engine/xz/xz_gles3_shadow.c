#include "xz_gles3_shadow.h"
#include "xz_gles3_resource_plan.h"
#include "xz_pass_targets.h"
#include "xz_pass_inputs.h"
#include "xz_texture_tap.h"
#include "xz_static_scene_draw_plan.h"
#include "xz_static_scene_material_draw_plan.h"
#include "xz_static_scene_lightmap_draw_plan.h"
#include "xz_xztx_gpu_format.h"

#include <EGL/egl.h>
#include <GLES3/gl3.h>

#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef EGL_OPENGL_ES3_BIT_KHR
#define EGL_OPENGL_ES3_BIT_KHR 0x00000040
#endif

#ifndef GL_COMPRESSED_RGBA_S3TC_DXT5_EXT
#define GL_COMPRESSED_RGBA_S3TC_DXT5_EXT 0x83F3
#endif

#define XZ_STATIC_LIGHTMAP_INSTANCE_FLOATS 24u
#define XZ_SHADOW_WIDTH 64
#define XZ_SHADOW_HEIGHT 64
#define XZ_VERTEX_FLOATS 7u
#define XZ_VERTICES_PER_PACKET 3u
#define XZ_G3_RESOURCE_PROXY_MAX 128u
#define XZ_STATIC_LOCAL_LIGHT_SOURCE_MAX 163u
#define XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX 64u
#define XZ_STATIC_GAMEPLAY_UNITS_PER_METER 39.3700787402f
#define XZ_STATIC_CENTIMETERS_PER_GAMEPLAY_UNIT 2.54f
#define XZ_STATIC_PI 3.14159265358979323846f

enum {
    XZ_STATIC_LIGHT_UNIT_UNKNOWN = 0u,
    XZ_STATIC_LIGHT_UNIT_CANDELAS = 1u,
    XZ_STATIC_LIGHT_UNIT_LUMENS = 2u,
    XZ_STATIC_LIGHT_UNIT_UNITLESS = 3u,
    XZ_STATIC_LIGHT_UNIT_EV100 = 4u
};

enum {
    XZ_G3_STAGE_NONE = 0u,
    XZ_G3_STAGE_READBACK = 1u,
    XZ_G3_STAGE_USE_PROGRAM = 2u,
    XZ_G3_STAGE_BIND_VERTEX_ARRAY = 3u,
    XZ_G3_STAGE_BIND_BUFFER = 4u,
    XZ_G3_STAGE_BUFFER_UPLOAD = 5u,
    XZ_G3_STAGE_DRAW = 6u,
    XZ_G3_STAGE_FINISH = 7u,
    XZ_G3_STAGE_UNBIND = 8u
};

typedef GLuint (*XzGlCreateShaderFn)(GLenum);
typedef void (*XzGlShaderSourceFn)(
    GLuint, GLsizei, const GLchar *const *, const GLint *);
typedef void (*XzGlCompileShaderFn)(GLuint);
typedef void (*XzGlGetShaderivFn)(GLuint, GLenum, GLint *);
typedef void (*XzGlDeleteShaderFn)(GLuint);
typedef GLuint (*XzGlCreateProgramFn)(void);
typedef void (*XzGlAttachShaderFn)(GLuint, GLuint);
typedef void (*XzGlLinkProgramFn)(GLuint);
typedef void (*XzGlGetProgramivFn)(GLuint, GLenum, GLint *);
typedef void (*XzGlDeleteProgramFn)(GLuint);
typedef void (*XzGlGenBuffersFn)(GLsizei, GLuint *);
typedef void (*XzGlDeleteBuffersFn)(GLsizei, const GLuint *);
typedef void (*XzGlBindBufferFn)(GLenum, GLuint);
typedef void (*XzGlBufferDataFn)(
    GLenum, GLsizeiptr, const void *, GLenum);
typedef void (*XzGlBufferSubDataFn)(
    GLenum, GLintptr, GLsizeiptr, const void *);
typedef void (*XzGlGenTexturesFn)(GLsizei, GLuint *);
typedef void (*XzGlDeleteTexturesFn)(GLsizei, const GLuint *);
typedef void (*XzGlBindTextureFn)(GLenum, GLuint);
typedef void (*XzGlTexParameteriFn)(GLenum, GLenum, GLint);
typedef void (*XzGlTexImage2DFn)(
    GLenum, GLint, GLint, GLsizei, GLsizei, GLint,
    GLenum, GLenum, const void *);
typedef void (*XzGlCompressedTexImage2DFn)(
    GLenum, GLint, GLenum, GLsizei, GLsizei, GLint,
    GLsizei, const void *);
typedef void (*XzGlGenRenderbuffersFn)(GLsizei, GLuint *);
typedef void (*XzGlDeleteRenderbuffersFn)(GLsizei, const GLuint *);
typedef void (*XzGlBindRenderbufferFn)(GLenum, GLuint);
typedef void (*XzGlRenderbufferStorageFn)(
    GLenum, GLenum, GLsizei, GLsizei);
typedef void (*XzGlGenFramebuffersFn)(GLsizei, GLuint *);
typedef void (*XzGlDeleteFramebuffersFn)(GLsizei, const GLuint *);
typedef void (*XzGlBindFramebufferFn)(GLenum, GLuint);
typedef void (*XzGlFramebufferTexture2DFn)(
    GLenum, GLenum, GLenum, GLuint, GLint);
typedef void (*XzGlFramebufferRenderbufferFn)(
    GLenum, GLenum, GLenum, GLuint);
typedef GLenum (*XzGlCheckFramebufferStatusFn)(GLenum);
typedef void (*XzGlGenVertexArraysFn)(GLsizei, GLuint *);
typedef void (*XzGlDeleteVertexArraysFn)(GLsizei, const GLuint *);
typedef void (*XzGlBindVertexArrayFn)(GLuint);
typedef void (*XzGlEnableVertexAttribArrayFn)(GLuint);
typedef void (*XzGlVertexAttribPointerFn)(
    GLuint, GLint, GLenum, GLboolean, GLsizei, const void *);
typedef void (*XzGlVertexAttribDivisorFn)(GLuint, GLuint);
typedef void (*XzGlUseProgramFn)(GLuint);
typedef void (*XzGlActiveTextureFn)(GLenum);
typedef GLint (*XzGlGetUniformLocationFn)(GLuint, const GLchar *);
typedef void (*XzGlUniform1iFn)(GLint, GLint);
typedef void (*XzGlUniform1fFn)(GLint, GLfloat);
typedef void (*XzGlUniform3fvFn)(GLint, GLsizei, const GLfloat *);
typedef void (*XzGlUniform4fvFn)(GLint, GLsizei, const GLfloat *);
typedef void (*XzGlUniformMatrix4fvFn)(
    GLint, GLsizei, GLboolean, const GLfloat *);
typedef void (*XzGlViewportFn)(GLint, GLint, GLsizei, GLsizei);
typedef void (*XzGlClearColorFn)(GLfloat, GLfloat, GLfloat, GLfloat);
typedef void (*XzGlClearFn)(GLbitfield);
typedef void (*XzGlEnableFn)(GLenum);
typedef void (*XzGlDisableFn)(GLenum);
typedef void (*XzGlBlendFuncFn)(GLenum, GLenum);
typedef void (*XzGlDepthMaskFn)(GLboolean);
typedef void (*XzGlDepthFuncFn)(GLenum);
typedef void (*XzGlDepthRangefFn)(GLfloat, GLfloat);
typedef void (*XzGlCullFaceFn)(GLenum);
typedef void (*XzGlFrontFaceFn)(GLenum);
typedef void (*XzGlPolygonOffsetFn)(GLfloat, GLfloat);
typedef void (*XzGlDrawArraysFn)(GLenum, GLint, GLsizei);
typedef void (*XzGlDrawElementsFn)(
    GLenum, GLsizei, GLenum, const void *);
typedef void (*XzGlDrawElementsInstancedFn)(
    GLenum, GLsizei, GLenum, const void *, GLsizei);
typedef void (*XzGlReadPixelsFn)(
    GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *);
typedef void (*XzGlFinishFn)(void);
typedef GLenum (*XzGlGetErrorFn)(void);
typedef const GLubyte *(*XzGlGetStringFn)(GLenum);

typedef struct {
    void *library;

    XzGlCreateShaderFn CreateShader;
    XzGlShaderSourceFn ShaderSource;
    XzGlCompileShaderFn CompileShader;
    XzGlGetShaderivFn GetShaderiv;
    XzGlDeleteShaderFn DeleteShader;
    XzGlCreateProgramFn CreateProgram;
    XzGlAttachShaderFn AttachShader;
    XzGlLinkProgramFn LinkProgram;
    XzGlGetProgramivFn GetProgramiv;
    XzGlDeleteProgramFn DeleteProgram;

    XzGlGenBuffersFn GenBuffers;
    XzGlDeleteBuffersFn DeleteBuffers;
    XzGlBindBufferFn BindBuffer;
    XzGlBufferDataFn BufferData;
    XzGlBufferSubDataFn BufferSubData;

    XzGlGenTexturesFn GenTextures;
    XzGlDeleteTexturesFn DeleteTextures;
    XzGlBindTextureFn BindTexture;
    XzGlTexParameteriFn TexParameteri;
    XzGlTexImage2DFn TexImage2D;
    XzGlCompressedTexImage2DFn CompressedTexImage2D;

    XzGlGenRenderbuffersFn GenRenderbuffers;
    XzGlDeleteRenderbuffersFn DeleteRenderbuffers;
    XzGlBindRenderbufferFn BindRenderbuffer;
    XzGlRenderbufferStorageFn RenderbufferStorage;

    XzGlGenFramebuffersFn GenFramebuffers;
    XzGlDeleteFramebuffersFn DeleteFramebuffers;
    XzGlBindFramebufferFn BindFramebuffer;
    XzGlFramebufferTexture2DFn FramebufferTexture2D;
    XzGlFramebufferRenderbufferFn FramebufferRenderbuffer;
    XzGlCheckFramebufferStatusFn CheckFramebufferStatus;

    XzGlGenVertexArraysFn GenVertexArrays;
    XzGlDeleteVertexArraysFn DeleteVertexArrays;
    XzGlBindVertexArrayFn BindVertexArray;
    XzGlEnableVertexAttribArrayFn EnableVertexAttribArray;
    XzGlVertexAttribPointerFn VertexAttribPointer;
    XzGlVertexAttribDivisorFn VertexAttribDivisor;

    XzGlUseProgramFn UseProgram;
    XzGlActiveTextureFn ActiveTexture;
    XzGlGetUniformLocationFn GetUniformLocation;
    XzGlUniform1iFn Uniform1i;
    XzGlUniform1fFn Uniform1f;
    XzGlUniform3fvFn Uniform3fv;
    XzGlUniform4fvFn Uniform4fv;
    XzGlUniformMatrix4fvFn UniformMatrix4fv;
    XzGlViewportFn Viewport;
    XzGlClearColorFn ClearColor;
    XzGlClearFn Clear;
    XzGlEnableFn Enable;
    XzGlDisableFn Disable;
    XzGlBlendFuncFn BlendFunc;
    XzGlDepthMaskFn DepthMask;
    XzGlDepthFuncFn DepthFunc;
    XzGlDepthRangefFn DepthRangef;
    XzGlCullFaceFn CullFace;
    XzGlFrontFaceFn FrontFace;
    XzGlPolygonOffsetFn PolygonOffset;
    XzGlDrawArraysFn DrawArrays;
    XzGlDrawElementsFn DrawElements;
    XzGlDrawElementsInstancedFn DrawElementsInstanced;
    XzGlReadPixelsFn ReadPixels;
    XzGlFinishFn Finish;
    XzGlGetErrorFn GetError;
    XzGlGetStringFn GetString;
} XzNativeGles3Api;

typedef struct {
    XzGpuHandle handle;
    XzGles3ResourceSpec spec;
    GLuint object;
    int alive;
} XzGles3PhysicalResource;

typedef struct {
    unsigned int legacy_id;
    unsigned int width;
    unsigned int height;
    uint64_t revision;
    GLuint object;
    int alive;
} XzGles3RealTexture;

typedef struct {
    GLuint vbo;
    GLuint ibo;
    GLuint vao;
    uint32_t vertex_count;
    uint32_t index_count;
    uint32_t submesh_count;
    XzXzmeshSubmesh *submeshes;
    uint64_t gpu_bytes;
    float bounds_min[3];
    float bounds_max[3];
    int alive;
} XzGles3StaticMesh;

typedef struct {
    GLuint object;
    uint32_t width;
    uint32_t height;
    uint32_t flags;
    uint64_t gpu_bytes;
    int alive;
} XzGles3StaticTexture;

enum {
    XZ_NATIVE_SHADING_DEFAULT_LIT = 0u,
    XZ_NATIVE_SHADING_UNLIT = 1u
};

enum {
    XZ_NATIVE_BLEND_OPAQUE = 0u,
    XZ_NATIVE_BLEND_MASKED = 1u,
    XZ_NATIVE_BLEND_TRANSLUCENT = 2u
};

typedef struct {
    uint32_t canonical_texture[4];
    uint32_t inferred_diffuse;
    float roughness;
    float metallic;
    float specular;
    float emissive;
    float opacity;
    float opacity_mask_clip;
    uint32_t pbr_flags;
    uint32_t shading_mode;
    uint32_t blend_mode;
    uint32_t two_sided;
    uint32_t disable_depth_test;
    uint32_t is_masked;
} XzGles3NativeMaterial;

typedef struct {
    float position_game[3];
    float radius_game;
    float inv_radius_cm;
    float color_brightness[3];
    float direction[3];
    float cos_outer;
    float inv_cos_difference;
    uint32_t type;
} XzGles3StaticLocalLight;

typedef struct {
    int ready;

    EGLDisplay display;
    EGLConfig config;
    EGLSurface surface;
    EGLContext context;

    EGLConfig visible_config;
    EGLContext visible_context;
    int visible_context_owned;
    GLuint visible_vao;
    GLuint visible_fbo;
    GLuint visible_color;
    GLuint visible_depth;
    unsigned int visible_width;
    unsigned int visible_height;

    GLuint program;
    GLuint fullscreen_program;
    GLint fullscreen_input_count_loc;
    GLuint vbo;
    GLuint vao;

    GLuint real_program;
    GLint real_modelview_loc;
    GLint real_projection_loc;
    GLint real_texture_loc;
    GLint real_texture_enabled_loc;
    GLint real_color_loc;
    GLint real_texenv_modulate_loc;
    GLint real_alpha_test_loc;
    GLint real_alpha_func_loc;
    GLint real_alpha_ref_loc;
    GLint real_fog_enabled_loc;
    GLint real_fog_start_loc;
    GLint real_fog_end_loc;
    GLint real_fog_color_loc;
    GLuint real_vbo;
    GLuint real_ibo;
    GLuint real_vao;
    GLuint real_fallback_texture;
    XzGles3RealTexture real_textures[XZ_TEXTURE_MAX_ENTRIES];

    GLuint static_program;
    GLint static_view_loc;
    GLint static_projection_loc;
    GLint static_texture_loc;
    GLint static_texture_enabled_loc;
    GLint static_normal_texture_loc;
    GLint static_normal_texture_enabled_loc;
    GLint static_ambient_weight_loc;
    GLint static_directional_weight_loc;
    GLint static_directional_color_loc;
    GLint static_directional_direction_loc;
    GLint static_local_light_count_loc;
    GLint static_local_pos_inv_radius_loc;
    GLint static_local_color_cone_loc;
    GLint static_local_dir_cos_outer_loc;
    GLint static_camera_pos_loc;
    GLint static_fog_primary_loc;
    GLint static_fog_color_min_loc;
    GLint static_fog_cutoff_loc;
    GLint static_pbr_params_loc;
    GLint static_pbr_flags_loc;
    GLint static_material_shading_mode_loc;
    GLint static_material_blend_mode_loc;
    GLint static_material_opacity_loc;
    GLint static_opacity_mask_clip_loc;
    GLint static_reflection_texture_loc;
    GLint static_reflection_params_loc;
    GLint static_reflection_sphere_loc;
    GLint static_reflection_offset_loc;
    GLint static_lightmap_texture_loc;
    GLint static_lightmap_enabled_loc;
    float static_ambient_weight;
    float static_directional_weight;
    float static_directional_color[3];
    float static_directional_direction[3];
    float static_fog_primary[4];
    float static_fog_color_min[4];
    float static_fog_cutoff_cm;
    XzGles3StaticLocalLight
        static_local_lights[XZ_STATIC_LOCAL_LIGHT_SOURCE_MAX];
    uint32_t static_local_light_count;
    GLuint static_instance_vbo;
    GLuint static_lightmap_instance_vbo;
    XzStaticSceneDrawPlan static_draw_plan;
    int static_draw_plan_ready;
    XzStaticSceneMaterialDrawPlan static_material_draw_plan;
    int static_material_draw_plan_ready;
    XzStaticSceneLightmapDrawPlan static_lightmap_draw_plan;
    int static_lightmap_draw_plan_ready;

    XzGles3StaticMesh *static_meshes;
    uint32_t static_mesh_count;
    XzGles3StaticTexture *static_textures;
    uint32_t static_texture_count;
    uint32_t *static_material_bindings;
    uint32_t static_material_binding_count;
    XzGles3StaticTexture *static_normal_textures;
    uint32_t static_normal_texture_count;
    uint32_t *static_normal_bindings;
    uint32_t static_normal_binding_count;
    XzPbrMaterialBinding *static_pbr_bindings;
    uint32_t static_pbr_binding_count;
    XzGles3StaticTexture *static_lightmap_textures;
    uint32_t static_lightmap_texture_count;
    XzGles3NativeMaterial *static_native_materials;
    uint32_t static_native_material_count;
    uint32_t *static_material_batch_offsets;
    uint32_t *static_material_batch_materials;
    uint32_t static_material_batch_binding_count;
    int static_native_material_ready;
    GLuint static_reflection_cubemap;

    GLuint scratch_fbo;

    XzGles3PhysicalResource
        physical[XZ_GPU_MAX_RESOURCES];

    XzNativeGles3Api gl;
} XzGles3ShadowInternal;

static XzGles3ShadowInternal xz_shadow;

static void XzDrainErrors(
    XzGles3ShadowState *state);

static void XzDrainErrors(
    XzGles3ShadowState *state);

static float XzAbsFloat(float value)
{
    return value < 0.0f ? -value : value;
}

static unsigned int XzAbsByteDiff(
    unsigned char a,
    unsigned char b)
{
    return a > b
        ? (unsigned int)(a - b)
        : (unsigned int)(b - a);
}

static int XzRangeStringEquals(
    const XzMaterialLibraryView *library,
    uint32_t offset,
    uint32_t bytes,
    const char *literal)
{
    const char *text;
    size_t literal_bytes;

    if (!library || !literal ||
        !XzMaterialLibrary_String(
            library,
            offset,
            bytes,
            &text))
        return 0;

    literal_bytes = strlen(literal);
    return literal_bytes == (size_t)bytes &&
        memcmp(text, literal, bytes) == 0;
}

static unsigned char XzAsciiLower(unsigned char value)
{
    if (value >= (unsigned char)'A' &&
        value <= (unsigned char)'Z')
        return (unsigned char)(
            value - (unsigned char)'A' +
            (unsigned char)'a');
    return value;
}

static int XzRangeStringContainsNoCase(
    const XzMaterialLibraryView *library,
    uint32_t offset,
    uint32_t bytes,
    const char *needle)
{
    const char *text;
    size_t needle_bytes;
    uint32_t i;

    if (!library || !needle ||
        !XzMaterialLibrary_String(
            library,
            offset,
            bytes,
            &text))
        return 0;

    needle_bytes = strlen(needle);
    if (needle_bytes == 0u ||
        needle_bytes > (size_t)bytes)
        return 0;

    for (i = 0u;
         (size_t)i + needle_bytes <= (size_t)bytes;
         ++i) {
        size_t j;
        int match = 1;
        for (j = 0u; j < needle_bytes; ++j) {
            if (XzAsciiLower(
                    (unsigned char)text[i + (uint32_t)j]) !=
                XzAsciiLower(
                    (unsigned char)needle[j])) {
                match = 0;
                break;
            }
        }
        if (match)
            return 1;
    }

    return 0;
}

static int XzNativeBindingRejectsDiffuse(
    const XzMaterialLibraryView *library,
    const XzMaterialLibraryTextureBinding *binding)
{
    static const char *tokens[] = {
        "normal", "nml", "spec", "rough", "rgh",
        "metallic", "opacity", "alpha", "height",
        "displace", "ambientocclusion", "occlusion",
        "_ao", "emiss", "emission", "glow"
    };
    size_t i;

    if (!library || !binding)
        return 1;

    for (i = 0u; i < sizeof(tokens) / sizeof(tokens[0]); ++i) {
        if (XzRangeStringContainsNoCase(
                library,
                binding->name_offset,
                binding->name_bytes,
                tokens[i]))
            return 1;
    }

    return 0;
}

static int XzNativeBindingLooksDiffuse(
    const XzMaterialLibraryView *library,
    const XzMaterialLibraryTextureBinding *binding)
{
    static const char *tokens[] = {
        "diffuse", "albedo", "basecolor", "base_color",
        "color", "colour", "_col", "col_", "_c-rgb",
        "_c-r", "_c_rgb", "_co_", "_co"
    };
    size_t i;

    if (!library || !binding)
        return 0;

    for (i = 0u; i < sizeof(tokens) / sizeof(tokens[0]); ++i) {
        if (XzRangeStringContainsNoCase(
                library,
                binding->name_offset,
                binding->name_bytes,
                tokens[i]))
            return 1;
    }

    return 0;
}

/*
 * Some cooked UE materials use source texture parameter names as their only
 * semantic label (for example "..._col" or "..._c-rgb") and therefore arrive
 * without a canonical diffuse slot even though the exact source texture is in
 * XZML/XZTX. Recover only from already-authored bindings. Prefer explicit
 * color-like names and otherwise accept a single sRGB candidate; never choose
 * obvious normal/specular/roughness/emissive/data maps.
 */
static uint32_t XzInferDiffuseTexture(
    const XzMaterialLibraryView *library,
    const XzMaterialLibraryMaterial *material)
{
    uint32_t binding_offset;
    uint32_t best_texture = XZ_XZML_NO_TEXTURE;
    int best_score = -1;
    unsigned int eligible_count = 0u;
    uint32_t sole_texture = XZ_XZML_NO_TEXTURE;

    if (!library || !material ||
        !xz_shadow.static_textures)
        return XZ_XZML_NO_TEXTURE;

    for (binding_offset = 0u;
         binding_offset < material->texture_binding_count;
         ++binding_offset) {
        XzMaterialLibraryTextureBinding binding;
        XzGles3StaticTexture *texture;
        int score;

        if (XzMaterialLibrary_TextureBinding(
                library,
                material->first_texture_binding +
                    binding_offset,
                &binding) != XZ_XZML_OK ||
            binding.texture_asset_index >=
                xz_shadow.static_texture_count)
            continue;

        texture =
            &xz_shadow.static_textures[
                binding.texture_asset_index];

        if (!texture->alive ||
            (texture->flags & XZ_XZTX_FLAG_SRGB) == 0u ||
            XzNativeBindingRejectsDiffuse(
                library,
                &binding))
            continue;

        eligible_count++;
        sole_texture =
            binding.texture_asset_index;

        score =
            XzNativeBindingLooksDiffuse(
                library,
                &binding)
                ? 100
                : 10;

        if (score > best_score) {
            best_score = score;
            best_texture =
                binding.texture_asset_index;
        }
    }

    if (best_score >= 100)
        return best_texture;

    if (eligible_count == 1u)
        return sole_texture;

    return XZ_XZML_NO_TEXTURE;
}

static int XzNativeMaterialDecode(
    const XzStaticSceneRuntimeState *scene,
    uint32_t material_index,
    XzGles3NativeMaterial *out)
{
    const XzMaterialLibraryView *library;
    XzMaterialLibraryMaterial source;
    uint32_t scalar_offset;
    uint32_t switch_offset;

    if (!scene || !out)
        return 0;

    library =
        XzStaticSceneRuntime_MaterialLibrary(
            scene);
    if (!library ||
        XzStaticSceneRuntime_Material(
            scene,
            material_index,
            &source) == 0)
        return 0;

    memset(out, 0, sizeof(*out));
    memcpy(
        out->canonical_texture,
        source.canonical_texture,
        sizeof(out->canonical_texture));

    if (out->canonical_texture[0] ==
            XZ_XZML_NO_TEXTURE) {
        uint32_t inferred =
            XzInferDiffuseTexture(
                library,
                &source);
        if (inferred != XZ_XZML_NO_TEXTURE) {
            out->canonical_texture[0] =
                inferred;
            out->inferred_diffuse = 1u;
        }
    }

    out->roughness = 0.75f;
    out->metallic = 0.0f;
    out->specular = 0.5f;
    out->emissive = 0.0f;
    out->opacity = 1.0f;
    out->opacity_mask_clip = 0.333f;
    out->shading_mode =
        XZ_NATIVE_SHADING_DEFAULT_LIT;
    out->blend_mode =
        XZ_NATIVE_BLEND_OPAQUE;

    if (XzRangeStringEquals(
            library,
            source.shading_model_offset,
            source.shading_model_bytes,
            "MSM_Unlit")) {
        out->shading_mode =
            XZ_NATIVE_SHADING_UNLIT;
    } else if (!XzRangeStringEquals(
                   library,
                   source.shading_model_offset,
                   source.shading_model_bytes,
                   "MSM_DefaultLit")) {
        return 0;
    }

    if (XzRangeStringEquals(
            library,
            source.blend_mode_offset,
            source.blend_mode_bytes,
            "BLEND_Masked")) {
        out->blend_mode =
            XZ_NATIVE_BLEND_MASKED;
    } else if (XzRangeStringEquals(
                   library,
                   source.blend_mode_offset,
                   source.blend_mode_bytes,
                   "BLEND_Translucent")) {
        out->blend_mode =
            XZ_NATIVE_BLEND_TRANSLUCENT;
    } else if (!XzRangeStringEquals(
                   library,
                   source.blend_mode_offset,
                   source.blend_mode_bytes,
                   "BLEND_Opaque")) {
        return 0;
    }

    for (scalar_offset = 0u;
         scalar_offset < source.scalar_count;
         ++scalar_offset) {
        XzMaterialLibraryScalar scalar;

        if (XzMaterialLibrary_Scalar(
                library,
                source.first_scalar +
                    scalar_offset,
                &scalar) != XZ_XZML_OK)
            return 0;

        if (XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Roughness") ||
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Roughness3") ||
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Roughness4")) {
            out->roughness = scalar.value;
            out->pbr_flags |=
                XZ_PBR_FLAG_ROUGHNESS;
        } else if (
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Metallic") ||
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Metallic2")) {
            out->metallic = scalar.value;
            out->pbr_flags |=
                XZ_PBR_FLAG_METALLIC;
        } else if (
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Specular") ||
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Specular3")) {
            out->specular = scalar.value;
            out->pbr_flags |=
                XZ_PBR_FLAG_SPECULAR;
        } else if (
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Emissive") ||
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "EmissiveIntensity")) {
            out->emissive = scalar.value;
            out->pbr_flags |=
                XZ_PBR_FLAG_EMISSIVE;
        } else if (
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "Opacity")) {
            out->opacity =
                scalar.value < 0.0f
                    ? 0.0f
                    : (scalar.value > 1.0f
                        ? 1.0f
                        : scalar.value);
        } else if (
            XzRangeStringEquals(
                library,
                scalar.name_offset,
                scalar.name_bytes,
                "__XZ_OpacityMaskClipValue")) {
            out->opacity_mask_clip =
                scalar.value < 0.0f
                    ? 0.0f
                    : (scalar.value > 1.0f
                        ? 1.0f
                        : scalar.value);
        }
    }

    for (switch_offset = 0u;
         switch_offset < source.switch_count;
         ++switch_offset) {
        XzMaterialLibrarySwitch value;

        if (XzMaterialLibrary_Switch(
                library,
                source.first_switch +
                    switch_offset,
                &value) != XZ_XZML_OK ||
            value.value > 1u)
            return 0;

        if (XzRangeStringEquals(
                library,
                value.name_offset,
                value.name_bytes,
                "__XZ_TwoSided")) {
            out->two_sided = value.value;
        } else if (
            XzRangeStringEquals(
                library,
                value.name_offset,
                value.name_bytes,
                "__XZ_DisableDepthTest")) {
            out->disable_depth_test = value.value;
        } else if (
            XzRangeStringEquals(
                library,
                value.name_offset,
                value.name_bytes,
                "__XZ_IsMasked")) {
            out->is_masked = value.value;
        }
    }

    /*
     * BlendMode is the authoritative render state. UE's cooked bIsMasked
     * cache is preserved for diagnostics but is not equivalent to
     * BLEND_Masked in this source corpus.
     */

    /*
     * Unlit is a real UE shading model, not a weakly-lit PBR material.
     * Preserve stored parameters for diagnostics, but do not enable the
     * Cook-Torrance branch for it.
     */
    if (out->shading_mode ==
            XZ_NATIVE_SHADING_UNLIT)
        out->pbr_flags = 0u;

    return
        isfinite(out->roughness) &&
        isfinite(out->metallic) &&
        isfinite(out->specular) &&
        isfinite(out->emissive) &&
        isfinite(out->opacity) &&
        isfinite(out->opacity_mask_clip);
}

static int XzPrepareNativeMaterials(
    const XzStaticSceneRuntimeState *scene,
    XzGles3ShadowState *state)
{
    const XzMaterialLibraryView *library;
    uint32_t material_index;

    if (!scene || !state)
        return 0;

    library =
        XzStaticSceneRuntime_MaterialLibrary(scene);

    if (!library)
        return 1;

    if (!scene->material_library_data ||
        !state->static_scene_material_ready ||
        xz_shadow.static_texture_count !=
            library->texture_asset_count ||
        library->material_count == 0u)
        return 0;

    xz_shadow.static_native_materials =
        (XzGles3NativeMaterial *)calloc(
            library->material_count,
            sizeof(*xz_shadow.static_native_materials));

    if (!xz_shadow.static_native_materials)
        return 0;

    xz_shadow.static_native_material_count =
        library->material_count;

    state->static_scene_inferred_diffuse_materials = 0u;

    for (material_index = 0u;
         material_index < library->material_count;
         ++material_index) {
        if (!XzNativeMaterialDecode(
                scene,
                material_index,
                &xz_shadow.static_native_materials[
                    material_index]))
            return 0;

        if (xz_shadow.static_native_materials[
                material_index].inferred_diffuse)
            state->static_scene_inferred_diffuse_materials++;
    }

    xz_shadow.static_native_material_ready = 1;

    state->static_scene_xzml_materials =
        library->material_count;
    state->static_scene_xztx_gpu_textures =
        xz_shadow.static_texture_count;
    state->static_scene_xztx_astc_textures =
        xz_shadow.static_texture_count;
    state->static_scene_xztx_gpu_bytes =
        state->static_scene_gpu_texture_bytes;
    state->static_scene_xzml_gpu_ready =
        state->static_scene_xztx_gpu_textures ==
            library->texture_asset_count &&
        state->static_scene_xzml_materials ==
            library->material_count;

    return state->static_scene_xzml_gpu_ready;
}

static int XzBuildNativeMaterialBatchBindings(
    const XzStaticSceneRuntimeState *scene)
{
    uint32_t batch_index;
    uint64_t total = 0u;

    if (!scene ||
        !xz_shadow.static_material_draw_plan_ready ||
        !xz_shadow.static_native_material_ready ||
        xz_shadow.static_material_draw_plan.batch_count == 0u)
        return 0;

    xz_shadow.static_material_batch_offsets =
        (uint32_t *)calloc(
            (size_t)xz_shadow
                .static_material_draw_plan.batch_count + 1u,
            sizeof(uint32_t));
    if (!xz_shadow.static_material_batch_offsets)
        return 0;

    for (batch_index = 0u;
         batch_index <
            xz_shadow.static_material_draw_plan.batch_count;
         ++batch_index) {
        const XzStaticSceneMaterialBatch *batch =
            XzStaticSceneMaterialDrawPlan_Batch(
                &xz_shadow.static_material_draw_plan,
                batch_index);
        const XzStaticMeshResource *mesh;

        if (!batch ||
            batch->mesh_index >=
                scene->mesh_resource_count)
            return 0;

        mesh =
            XzStaticSceneRuntime_Mesh(
                scene,
                batch->mesh_index);
        if (!mesh ||
            mesh->mesh.submesh_count == 0u)
            return 0;

        if (total > UINT32_MAX)
            return 0;

        xz_shadow.static_material_batch_offsets[
            batch_index] =
                (uint32_t)total;

        total +=
            (uint64_t)mesh->mesh.submesh_count;

        if (total > UINT32_MAX)
            return 0;
    }

    xz_shadow.static_material_batch_offsets[
        xz_shadow.static_material_draw_plan.batch_count] =
            (uint32_t)total;

    if (total == 0u ||
        total >
            (uint64_t)(SIZE_MAX /
                sizeof(uint32_t)))
        return 0;

    xz_shadow.static_material_batch_materials =
        (uint32_t *)malloc(
            (size_t)total * sizeof(uint32_t));
    if (!xz_shadow.static_material_batch_materials)
        return 0;

    xz_shadow.static_material_batch_binding_count =
        (uint32_t)total;

    for (batch_index = 0u;
         batch_index <
            xz_shadow.static_material_draw_plan.batch_count;
         ++batch_index) {
        const XzStaticSceneMaterialBatch *batch =
            XzStaticSceneMaterialDrawPlan_Batch(
                &xz_shadow.static_material_draw_plan,
                batch_index);
        const XzStaticMeshResource *mesh =
            XzStaticSceneRuntime_Mesh(
                scene,
                batch->mesh_index);
        uint32_t submesh_index;
        const uint32_t first =
            xz_shadow.static_material_batch_offsets[
                batch_index];

        for (submesh_index = 0u;
             submesh_index <
                mesh->mesh.submesh_count;
             ++submesh_index) {
            uint32_t material_index;

            if (!XzStaticSceneRuntime_InstanceMaterial(
                    scene,
                    batch->representative_source_instance,
                    submesh_index,
                    &material_index) ||
                material_index >=
                    xz_shadow.static_native_material_count)
                return 0;

            xz_shadow.static_material_batch_materials[
                first + submesh_index] =
                    material_index;
        }
    }

    return 1;
}

static GLenum XzSafeBlendFactor(unsigned int value, GLenum fallback)
{
    switch ((GLenum)value) {
    case GL_ZERO:
    case GL_ONE:
    case GL_SRC_COLOR:
    case GL_ONE_MINUS_SRC_COLOR:
    case GL_DST_COLOR:
    case GL_ONE_MINUS_DST_COLOR:
    case GL_SRC_ALPHA:
    case GL_ONE_MINUS_SRC_ALPHA:
    case GL_DST_ALPHA:
    case GL_ONE_MINUS_DST_ALPHA:
    case GL_CONSTANT_COLOR:
    case GL_ONE_MINUS_CONSTANT_COLOR:
    case GL_CONSTANT_ALPHA:
    case GL_ONE_MINUS_CONSTANT_ALPHA:
    case GL_SRC_ALPHA_SATURATE:
        return (GLenum)value;
    default:
        return fallback;
    }
}

static GLenum XzSafeDepthFunc(unsigned int value)
{
    switch ((GLenum)value) {
    case GL_NEVER:
    case GL_LESS:
    case GL_EQUAL:
    case GL_LEQUAL:
    case GL_GREATER:
    case GL_NOTEQUAL:
    case GL_GEQUAL:
    case GL_ALWAYS:
        return (GLenum)value;
    default:
        return GL_LEQUAL;
    }
}

static int XzAlphaFuncCode(unsigned int value)
{
    switch ((GLenum)value) {
    case GL_NEVER: return 0;
    case GL_LESS: return 1;
    case GL_EQUAL: return 2;
    case GL_LEQUAL: return 3;
    case GL_GREATER: return 4;
    case GL_NOTEQUAL: return 5;
    case GL_GEQUAL: return 6;
    case GL_ALWAYS: return 7;
    default: return 7;
    }
}

static GLenum XzSafeCullFace(unsigned int value)
{
    switch ((GLenum)value) {
    case GL_FRONT:
    case GL_BACK:
    case GL_FRONT_AND_BACK:
        return (GLenum)value;
    default:
        return GL_BACK;
    }
}

static GLenum XzSafeFrontFace(unsigned int value)
{
    return value == (unsigned int)GL_CW ? GL_CW : GL_CCW;
}

static float XzClamp01(float value)
{
    if (value < 0.0f) return 0.0f;
    if (value > 1.0f) return 1.0f;
    return value;
}

static float XzSrgbToLinear(float value)
{
    value = XzClamp01(value);
    if (value <= 0.04045f)
        return value / 12.92f;
    return powf(
        (value + 0.055f) / 1.055f,
        2.4f);
}

static void XzColorTemperature(
    float temperature_kelvin,
    float rgb[3])
{
    float t = temperature_kelvin;
    float u;
    float v;
    float denominator;
    float x;
    float y;
    float z;
    float X;
    float Y = 1.0f;
    float Z;

    if (t < 1000.0f)
        t = 1000.0f;
    if (t > 15000.0f)
        t = 15000.0f;

    u =
        (0.860117757f +
         1.54118254e-4f * t +
         1.28641212e-7f * t * t) /
        (1.0f +
         8.42420235e-4f * t +
         7.08145163e-7f * t * t);

    v =
        (0.317398726f +
         4.22806245e-5f * t +
         4.20481691e-8f * t * t) /
        (1.0f -
         2.89741816e-5f * t +
         1.61456053e-7f * t * t);

    denominator =
        2.0f * u -
        8.0f * v +
        4.0f;

    x = 3.0f * u / denominator;
    y = 2.0f * v / denominator;
    z = 1.0f - x - y;

    X = Y / y * x;
    Z = Y / y * z;

    rgb[0] =
        3.2404542f * X -
        1.5371385f * Y -
        0.4985314f * Z;
    rgb[1] =
        -0.9692660f * X +
        1.8760108f * Y +
        0.0415560f * Z;
    rgb[2] =
        0.0556434f * X -
        0.2040259f * Y +
        1.0572252f * Z;
}

static float XzStaticLocalBrightness(
    const XzEnvironmentLight *light,
    float cos_outer)
{
    float intensity;

    if (!light ||
        !isfinite(light->intensity) ||
        light->intensity < 0.0f)
        return -1.0f;

    intensity = light->intensity;

    if ((light->behavior_flags &
         XZ_ENV_BEHAVIOR_INVERSE_SQUARED) == 0u)
        return -1.0f;

    switch (light->units) {
    case XZ_STATIC_LIGHT_UNIT_CANDELAS:
        return intensity * 10000.0f;

    case XZ_STATIC_LIGHT_UNIT_LUMENS:
        if (light->type == XZ_ENV_LIGHT_SPOT) {
            float denominator =
                2.0f *
                XZ_STATIC_PI *
                (1.0f - cos_outer);
            if (!isfinite(denominator) ||
                denominator <= 1.0e-8f)
                return -1.0f;
            return
                intensity *
                10000.0f /
                denominator;
        }
        return
            intensity *
            10000.0f /
            (4.0f * XZ_STATIC_PI);

    case XZ_STATIC_LIGHT_UNIT_UNITLESS:
        return intensity * 16.0f;

    default:
        return -1.0f;
    }
}

static int XzStaticScenePrepareLocalLights(
    const XzStaticSceneRuntimeState *scene)
{
    const XzEnvironmentView *environment;
    uint32_t i;
    uint32_t count = 0u;

    if (!scene)
        return 0;

    /*
     * Zero local lights is a valid generic scene state. Clear previous-map
     * light state before probing the optional environment payload so a map
     * without authored point/spot lights can still draw with its global
     * fallback/unlit material semantics. Nacht keeps its strict parity gate.
     */
    memset(
        xz_shadow.static_local_lights,
        0,
        sizeof(xz_shadow.static_local_lights));
    xz_shadow.static_local_light_count = 0u;

    environment =
        XzStaticSceneRuntime_Environment(scene);
    if (!environment)
        return strcmp(
            scene->map_id,
            "xziel_nacht_bo3") != 0;

    for (i = 0u;
         i < environment->light_count;
         ++i) {
        XzEnvironmentLight source;
        XzGles3StaticLocalLight *dest;
        float pitch;
        float yaw;
        float cp;
        float inner_radians = 0.0f;
        float outer_radians = 0.0f;
        float cos_inner = 1.0f;
        float cos_outer = -1.0f;
        float brightness;
        float temperature[3] = {
            1.0f, 1.0f, 1.0f
        };
        uint32_t channel;

        if (!XzStaticSceneRuntime_EnvironmentLight(
                scene, i, &source))
            return 0;

        if (source.type != XZ_ENV_LIGHT_POINT &&
            source.type != XZ_ENV_LIGHT_SPOT)
            continue;

        if (count >=
            XZ_STATIC_LOCAL_LIGHT_SOURCE_MAX)
            return 0;

        if ((source.flags &
             (XZ_ENV_HAS_POSITION |
              XZ_ENV_HAS_ROTATION |
              XZ_ENV_HAS_COLOR |
              XZ_ENV_HAS_INTENSITY |
              XZ_ENV_HAS_RADIUS |
              XZ_ENV_HAS_UNITS)) !=
                (XZ_ENV_HAS_POSITION |
                 XZ_ENV_HAS_ROTATION |
                 XZ_ENV_HAS_COLOR |
                 XZ_ENV_HAS_INTENSITY |
                 XZ_ENV_HAS_RADIUS |
                 XZ_ENV_HAS_UNITS) ||
            !isfinite(source.radius_meters) ||
            source.radius_meters <= 0.0f)
            return 0;

        dest =
            &xz_shadow.static_local_lights[count];

        dest->position_game[0] =
            source.position[0] *
            XZ_STATIC_GAMEPLAY_UNITS_PER_METER;
        dest->position_game[1] =
            source.position[1] *
            XZ_STATIC_GAMEPLAY_UNITS_PER_METER;
        dest->position_game[2] =
            source.position[2] *
            XZ_STATIC_GAMEPLAY_UNITS_PER_METER;
        dest->radius_game =
            source.radius_meters *
            XZ_STATIC_GAMEPLAY_UNITS_PER_METER;
        dest->inv_radius_cm =
            1.0f /
            (source.radius_meters * 100.0f);
        dest->type = source.type;

        pitch =
            source.rotation[0] *
            0.01745329251994329577f;
        yaw =
            source.rotation[1] *
            0.01745329251994329577f;
        cp = cosf(pitch);

        dest->direction[0] =
            cp * cosf(yaw);
        dest->direction[1] =
            -(cp * sinf(yaw));
        dest->direction[2] =
            sinf(pitch);

        if (source.type == XZ_ENV_LIGHT_SPOT) {
            if ((source.flags &
                 (XZ_ENV_HAS_INNER_CONE |
                  XZ_ENV_HAS_OUTER_CONE)) !=
                    (XZ_ENV_HAS_INNER_CONE |
                     XZ_ENV_HAS_OUTER_CONE))
                return 0;

            inner_radians =
                XzClamp01(
                    source.inner_cone_degrees /
                    89.0f) *
                89.0f *
                0.01745329251994329577f;

            outer_radians =
                source.outer_cone_degrees *
                0.01745329251994329577f;

            if (outer_radians <
                inner_radians + 0.001f)
                outer_radians =
                    inner_radians + 0.001f;

            if (outer_radians >
                89.0f *
                    0.01745329251994329577f +
                    0.001f)
                outer_radians =
                    89.0f *
                        0.01745329251994329577f +
                    0.001f;

            cos_inner = cosf(inner_radians);
            cos_outer = cosf(outer_radians);

            if (cos_inner <= cos_outer)
                return 0;

            dest->cos_outer = cos_outer;
            dest->inv_cos_difference =
                1.0f /
                (cos_inner - cos_outer);
        } else {
            dest->cos_outer = -1.0f;
            dest->inv_cos_difference = 0.0f;
        }

        brightness =
            XzStaticLocalBrightness(
                &source,
                cos_outer);
        if (!isfinite(brightness) ||
            brightness < 0.0f)
            return 0;

        if ((source.behavior_flags &
             XZ_ENV_BEHAVIOR_USE_TEMPERATURE) != 0u) {
            if ((source.flags &
                 XZ_ENV_HAS_TEMPERATURE) == 0u ||
                !isfinite(source.temperature_kelvin))
                return 0;

            XzColorTemperature(
                source.temperature_kelvin,
                temperature);
        }

        for (channel = 0u;
             channel < 3u;
             ++channel) {
            if (!isfinite(source.color[channel]))
                return 0;

            dest->color_brightness[channel] =
                XzSrgbToLinear(
                    source.color[channel]) *
                temperature[channel] *
                brightness;

            if (!isfinite(
                    dest->color_brightness[channel]))
                return 0;
        }

        count++;
    }

    xz_shadow.static_local_light_count =
        count;

    if (strcmp(
            scene->map_id,
            "xziel_nacht_bo3") == 0 &&
        count !=
            XZ_STATIC_LOCAL_LIGHT_SOURCE_MAX)
        return 0;

    return 1;
}

static int XzStaticScenePrepareHeightFog(
    const XzStaticSceneRuntimeState *scene,
    XzGles3ShadowState *state)
{
    const XzHeightFogView *fog;

    if (!scene || !state)
        return 0;

    fog =
        XzStaticSceneRuntime_HeightFog(scene);

    if (!fog) {
        xz_shadow.static_fog_primary[0] = 0.0f;
        xz_shadow.static_fog_primary[1] = 0.0f;
        xz_shadow.static_fog_primary[2] = 0.0f;
        xz_shadow.static_fog_primary[3] = 0.0f;
        xz_shadow.static_fog_color_min[0] = 0.0f;
        xz_shadow.static_fog_color_min[1] = 0.0f;
        xz_shadow.static_fog_color_min[2] = 0.0f;
        xz_shadow.static_fog_color_min[3] = 1.0f;
        xz_shadow.static_fog_cutoff_cm = 0.0f;
        state->static_scene_height_fog_ready = 0;
        state->static_scene_directional_fog_enabled = 0;
        state->static_scene_fog_density = 0.0f;
        state->static_scene_fog_height_falloff = 0.0f;
        state->static_scene_fog_max_opacity = 0.0f;
        state->static_scene_fog_start_meters = 0.0f;
        return strcmp(
            scene->map_id,
            "xziel_nacht_bo3") != 0;
    }

    if (!isfinite(fog->fog_height_meters) ||
        !isfinite(fog->density) ||
        !isfinite(fog->height_falloff) ||
        !isfinite(fog->max_opacity) ||
        !isfinite(fog->start_distance_meters) ||
        !isfinite(fog->cutoff_distance_meters) ||
        fog->density < 0.0f ||
        fog->height_falloff < 0.0f ||
        fog->max_opacity < 0.0f ||
        fog->max_opacity > 1.0f ||
        fog->start_distance_meters < 0.0f ||
        fog->cutoff_distance_meters < 0.0f)
        return 0;

    if ((fog->flags &
         (XZ_HEIGHT_FOG_FLAG_VOLUMETRIC |
          XZ_HEIGHT_FOG_FLAG_CUBEMAP |
          XZ_HEIGHT_FOG_FLAG_SECOND_FOG)) != 0u)
        return 0;

    xz_shadow.static_fog_primary[0] =
        fog->density / 1000.0f;
    xz_shadow.static_fog_primary[1] =
        fog->height_falloff / 1000.0f;
    xz_shadow.static_fog_primary[2] =
        fog->fog_height_meters * 100.0f;
    xz_shadow.static_fog_primary[3] =
        fog->start_distance_meters * 100.0f;

    xz_shadow.static_fog_color_min[0] =
        fog->fog_color_linear[0];
    xz_shadow.static_fog_color_min[1] =
        fog->fog_color_linear[1];
    xz_shadow.static_fog_color_min[2] =
        fog->fog_color_linear[2];
    xz_shadow.static_fog_color_min[3] =
        1.0f - fog->max_opacity;

    xz_shadow.static_fog_cutoff_cm =
        fog->cutoff_distance_meters * 100.0f;

    if (!isfinite(xz_shadow.static_fog_primary[0]) ||
        !isfinite(xz_shadow.static_fog_primary[1]) ||
        !isfinite(xz_shadow.static_fog_primary[2]) ||
        !isfinite(xz_shadow.static_fog_primary[3]) ||
        !isfinite(xz_shadow.static_fog_color_min[0]) ||
        !isfinite(xz_shadow.static_fog_color_min[1]) ||
        !isfinite(xz_shadow.static_fog_color_min[2]) ||
        !isfinite(xz_shadow.static_fog_color_min[3]) ||
        !isfinite(xz_shadow.static_fog_cutoff_cm))
        return 0;

    /*
     * Nacht's two DirectionalLight components do not serialize
     * bUsedAsAtmosphereSunLight. UE4's default is false, so the map does not
     * enable directional fog inscattering. Preserve that distinction instead
     * of borrowing the ordinary directional-light shader state.
     */
    state->static_scene_directional_fog_enabled = 0;
    state->static_scene_fog_density =
        fog->density;
    state->static_scene_fog_height_falloff =
        fog->height_falloff;
    state->static_scene_fog_max_opacity =
        fog->max_opacity;
    state->static_scene_fog_start_meters =
        fog->start_distance_meters;
    state->static_scene_height_fog_ready = 1;

    return 1;
}

static int XzStaticCameraOrigin(
    const float modelview[16],
    float origin[3])
{
    float x;
    float y;
    float z;

    if (!modelview || !origin)
        return 0;

    x = -(
        modelview[0] * modelview[12] +
        modelview[1] * modelview[13] +
        modelview[2] * modelview[14]);
    y = -(
        modelview[4] * modelview[12] +
        modelview[5] * modelview[13] +
        modelview[6] * modelview[14]);
    z = -(
        modelview[8] * modelview[12] +
        modelview[9] * modelview[13] +
        modelview[10] * modelview[14]);

    if (!isfinite(x) ||
        !isfinite(y) ||
        !isfinite(z))
        return 0;

    origin[0] = x;
    origin[1] = y;
    origin[2] = z;
    return 1;
}

static uint32_t XzStaticSelectLocalLights(
    const float camera_origin[3],
    float positions[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX * 4u],
    float colors[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX * 4u],
    float directions[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX * 4u],
    XzGles3ShadowState *state)
{
    uint32_t selected[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX];
    float scores[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX];
    uint32_t selected_count = 0u;
    uint32_t affecting_count = 0u;
    uint32_t selected_affecting = 0u;
    uint32_t i;

    if (!camera_origin ||
        !positions ||
        !colors ||
        !directions ||
        !state)
        return 0u;

    for (i = 0u;
         i < xz_shadow.static_local_light_count;
         ++i) {
        const XzGles3StaticLocalLight *light =
            &xz_shadow.static_local_lights[i];
        float dx =
            light->position_game[0] -
            camera_origin[0];
        float dy =
            light->position_game[1] -
            camera_origin[1];
        float dz =
            light->position_game[2] -
            camera_origin[2];
        float distance_sq =
            dx * dx + dy * dy + dz * dz;
        float radius_sq =
            light->radius_game *
            light->radius_game;
        float score;
        uint32_t insert_at;
        uint32_t j;

        if (!isfinite(distance_sq) ||
            radius_sq <= 0.0f)
            continue;

        score =
            distance_sq /
            radius_sq;

        if (distance_sq <= radius_sq)
            affecting_count++;

        insert_at = selected_count;
        for (j = 0u;
             j < selected_count;
             ++j) {
            if (score < scores[j]) {
                insert_at = j;
                break;
            }
        }

        if (insert_at >=
                XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX &&
            selected_count >=
                XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX)
            continue;

        if (selected_count <
            XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX)
            selected_count++;

        if (insert_at >= selected_count)
            insert_at = selected_count - 1u;

        for (j = selected_count - 1u;
             j > insert_at;
             --j) {
            selected[j] =
                selected[j - 1u];
            scores[j] =
                scores[j - 1u];
        }

        selected[insert_at] = i;
        scores[insert_at] = score;
    }

    for (i = 0u;
         i < selected_count;
         ++i) {
        const XzGles3StaticLocalLight *light =
            &xz_shadow.static_local_lights[
                selected[i]];
        uint32_t base = i * 4u;

        positions[base + 0u] =
            light->position_game[0];
        positions[base + 1u] =
            light->position_game[1];
        positions[base + 2u] =
            light->position_game[2];
        positions[base + 3u] =
            light->type ==
                XZ_ENV_LIGHT_SPOT
                ? -light->inv_radius_cm
                : light->inv_radius_cm;

        colors[base + 0u] =
            light->color_brightness[0];
        colors[base + 1u] =
            light->color_brightness[1];
        colors[base + 2u] =
            light->color_brightness[2];
        colors[base + 3u] =
            light->inv_cos_difference;

        directions[base + 0u] =
            light->direction[0];
        directions[base + 1u] =
            light->direction[1];
        directions[base + 2u] =
            light->direction[2];
        directions[base + 3u] =
            light->cos_outer;

        if (scores[i] <= 1.0f)
            selected_affecting++;
    }

    state->static_scene_local_light_active =
        selected_count;
    state->
        static_scene_local_light_camera_affecting =
            affecting_count;
    state->
        static_scene_local_light_dropped_affecting =
            affecting_count > selected_affecting
                ? affecting_count -
                    selected_affecting
                : 0u;

    return selected_count;
}

static int XzStaticSceneSourceLighting(
    const XzStaticSceneRuntimeState *scene,
    float *ambient_weight,
    float *directional_weight,
    float directional_color[3],
    float directional_direction[3])
{
    const XzEnvironmentView *environment;
    XzEnvironmentLight sky;
    XzEnvironmentLight directional;
    float sky_intensity = -1.0f;
    float directional_intensity = -1.0f;
    float pitch;
    float yaw;
    float cp;
    float length;
    uint32_t i;
    int have_sky = 0;
    int have_directional = 0;

    if (!scene ||
        !ambient_weight ||
        !directional_weight ||
        !directional_color ||
        !directional_direction)
        return 0;

    environment =
        XzStaticSceneRuntime_Environment(scene);
    if (!environment ||
        environment->light_count == 0u)
        return 0;

    memset(&sky, 0, sizeof(sky));
    memset(&directional, 0, sizeof(directional));

    for (i = 0u;
         i < environment->light_count;
         ++i) {
        XzEnvironmentLight light;

        if (!XzStaticSceneRuntime_EnvironmentLight(
                scene, i, &light))
            return 0;

        if (light.type == XZ_ENV_LIGHT_SKY &&
            (light.flags & XZ_ENV_HAS_INTENSITY) != 0u &&
            isfinite(light.intensity) &&
            light.intensity > 0.0f &&
            light.intensity > sky_intensity) {
            sky = light;
            sky_intensity = light.intensity;
            have_sky = 1;
        }

        if (light.type == XZ_ENV_LIGHT_DIRECTIONAL &&
            (light.flags &
             (XZ_ENV_HAS_ROTATION |
              XZ_ENV_HAS_COLOR |
              XZ_ENV_HAS_INTENSITY)) ==
                (XZ_ENV_HAS_ROTATION |
                 XZ_ENV_HAS_COLOR |
                 XZ_ENV_HAS_INTENSITY) &&
            isfinite(light.intensity) &&
            light.intensity > 0.0f &&
            light.intensity > directional_intensity) {
            directional = light;
            directional_intensity =
                light.intensity;
            have_directional = 1;
        }
    }

    if (!have_sky || !have_directional)
        return 0;

    /*
     * Preserve authored UE/Pavlov global-light intensities.  The old path
     * normalized Sky + Directional to 1.0, which imposed a flat neutral
     * baseline across Nacht and washed out authored darkness.
     *
     * uAmbientWeight now carries SkyLight intensity.  The shader derives
     * diffuse sky energy from the exact reflection-capture average brightness.
     * uDirectionalWeight carries the authored DirectionalLight intensity.
     */
    *ambient_weight = sky_intensity;
    *directional_weight = directional_intensity;

    for (i = 0u; i < 3u; ++i) {
        if (!isfinite(directional.color[i]))
            return 0;
        directional_color[i] =
            XzSrgbToLinear(
                directional.color[i]);
    }

    pitch =
        directional.rotation[0] *
        0.01745329251994329577f;
    yaw =
        directional.rotation[1] *
        0.01745329251994329577f;
    cp = cosf(pitch);

    /*
     * UE forward is
     * (cp*cos(yaw), cp*sin(yaw), sin(pitch)).
     * XZIEL flips UE Y; Lambert wants surface->light,
     * the opposite of DirectionalLight travel.
     */
    directional_direction[0] =
        -(cp * cosf(yaw));
    directional_direction[1] =
        cp * sinf(yaw);
    directional_direction[2] =
        -sinf(pitch);

    length = sqrtf(
        directional_direction[0] *
            directional_direction[0] +
        directional_direction[1] *
            directional_direction[1] +
        directional_direction[2] *
            directional_direction[2]);

    if (!isfinite(length) ||
        length <= 1.0e-8f)
        return 0;

    for (i = 0u; i < 3u; ++i)
        directional_direction[i] /= length;

    return
        isfinite(*ambient_weight) &&
        isfinite(*directional_weight);
}

static int XzLoadApi(XzNativeGles3Api *api)
{
#define XZ_GL_LOAD(field, symbol)                                      \
    do {                                                               \
        *(void **)(&api->field) = dlsym(api->library, symbol);         \
        if (!api->field)                                               \
            return 0;                                                  \
    } while (0)

    memset(api, 0, sizeof(*api));

    api->library = dlopen(
        "libGLESv2.so",
        RTLD_NOW | RTLD_LOCAL);
    if (!api->library)
        return 0;

    XZ_GL_LOAD(CreateShader, "glCreateShader");
    XZ_GL_LOAD(ShaderSource, "glShaderSource");
    XZ_GL_LOAD(CompileShader, "glCompileShader");
    XZ_GL_LOAD(GetShaderiv, "glGetShaderiv");
    XZ_GL_LOAD(DeleteShader, "glDeleteShader");
    XZ_GL_LOAD(CreateProgram, "glCreateProgram");
    XZ_GL_LOAD(AttachShader, "glAttachShader");
    XZ_GL_LOAD(LinkProgram, "glLinkProgram");
    XZ_GL_LOAD(GetProgramiv, "glGetProgramiv");
    XZ_GL_LOAD(DeleteProgram, "glDeleteProgram");

    XZ_GL_LOAD(GenBuffers, "glGenBuffers");
    XZ_GL_LOAD(DeleteBuffers, "glDeleteBuffers");
    XZ_GL_LOAD(BindBuffer, "glBindBuffer");
    XZ_GL_LOAD(BufferData, "glBufferData");
    XZ_GL_LOAD(BufferSubData, "glBufferSubData");

    XZ_GL_LOAD(GenTextures, "glGenTextures");
    XZ_GL_LOAD(DeleteTextures, "glDeleteTextures");
    XZ_GL_LOAD(BindTexture, "glBindTexture");
    XZ_GL_LOAD(TexParameteri, "glTexParameteri");
    XZ_GL_LOAD(TexImage2D, "glTexImage2D");
    XZ_GL_LOAD(
        CompressedTexImage2D,
        "glCompressedTexImage2D");

    XZ_GL_LOAD(GenRenderbuffers, "glGenRenderbuffers");
    XZ_GL_LOAD(DeleteRenderbuffers, "glDeleteRenderbuffers");
    XZ_GL_LOAD(BindRenderbuffer, "glBindRenderbuffer");
    XZ_GL_LOAD(RenderbufferStorage, "glRenderbufferStorage");

    XZ_GL_LOAD(GenFramebuffers, "glGenFramebuffers");
    XZ_GL_LOAD(DeleteFramebuffers, "glDeleteFramebuffers");
    XZ_GL_LOAD(BindFramebuffer, "glBindFramebuffer");
    XZ_GL_LOAD(FramebufferTexture2D, "glFramebufferTexture2D");
    XZ_GL_LOAD(FramebufferRenderbuffer, "glFramebufferRenderbuffer");
    XZ_GL_LOAD(CheckFramebufferStatus, "glCheckFramebufferStatus");

    XZ_GL_LOAD(GenVertexArrays, "glGenVertexArrays");
    XZ_GL_LOAD(DeleteVertexArrays, "glDeleteVertexArrays");
    XZ_GL_LOAD(BindVertexArray, "glBindVertexArray");
    XZ_GL_LOAD(
        EnableVertexAttribArray,
        "glEnableVertexAttribArray");
    XZ_GL_LOAD(
        VertexAttribPointer,
        "glVertexAttribPointer");
    XZ_GL_LOAD(
        VertexAttribDivisor,
        "glVertexAttribDivisor");

    XZ_GL_LOAD(UseProgram, "glUseProgram");
    XZ_GL_LOAD(ActiveTexture, "glActiveTexture");
    XZ_GL_LOAD(GetUniformLocation, "glGetUniformLocation");
    XZ_GL_LOAD(Uniform1i, "glUniform1i");
    XZ_GL_LOAD(Uniform1f, "glUniform1f");
    XZ_GL_LOAD(Uniform3fv, "glUniform3fv");
    XZ_GL_LOAD(Uniform4fv, "glUniform4fv");
    XZ_GL_LOAD(UniformMatrix4fv, "glUniformMatrix4fv");
    XZ_GL_LOAD(Viewport, "glViewport");
    XZ_GL_LOAD(ClearColor, "glClearColor");
    XZ_GL_LOAD(Clear, "glClear");
    XZ_GL_LOAD(Enable, "glEnable");
    XZ_GL_LOAD(Disable, "glDisable");
    XZ_GL_LOAD(BlendFunc, "glBlendFunc");
    XZ_GL_LOAD(DepthMask, "glDepthMask");
    XZ_GL_LOAD(DepthFunc, "glDepthFunc");
    XZ_GL_LOAD(DepthRangef, "glDepthRangef");
    XZ_GL_LOAD(CullFace, "glCullFace");
    XZ_GL_LOAD(FrontFace, "glFrontFace");
    XZ_GL_LOAD(PolygonOffset, "glPolygonOffset");
    XZ_GL_LOAD(DrawArrays, "glDrawArrays");
    XZ_GL_LOAD(DrawElements, "glDrawElements");
    XZ_GL_LOAD(
        DrawElementsInstanced,
        "glDrawElementsInstanced");
    XZ_GL_LOAD(ReadPixels, "glReadPixels");
    XZ_GL_LOAD(Finish, "glFinish");
    XZ_GL_LOAD(GetError, "glGetError");
    XZ_GL_LOAD(GetString, "glGetString");

#undef XZ_GL_LOAD
    return 1;
}

static void XzUnloadApi(XzNativeGles3Api *api)
{
    if (!api)
        return;

    if (api->library)
        dlclose(api->library);

    memset(api, 0, sizeof(*api));
}

static int XzCompileShader(
    XzNativeGles3Api *gl,
    GLenum type,
    const char *source,
    GLuint *shader_out)
{
    GLuint shader;
    GLint ok = 0;

    shader = gl->CreateShader(type);
    if (!shader)
        return 0;

    gl->ShaderSource(shader, 1, &source, NULL);
    gl->CompileShader(shader);
    gl->GetShaderiv(
        shader,
        GL_COMPILE_STATUS,
        &ok);

    if (!ok) {
        gl->DeleteShader(shader);
        return 0;
    }

    *shader_out = shader;
    return 1;
}

static int XzCreateProgramAndBuffer(void)
{
    static const char *vs_source =
        "#version 300 es\n"
        "layout(location=0) in vec2 aPos;\n"
        "layout(location=1) in float aWeight;\n"
        "layout(location=2) in vec4 aColor;\n"
        "out vec4 vColor;\n"
        "void main(){\n"
        "  gl_Position=vec4(aPos,0.0,1.0);\n"
        "  gl_PointSize=1.0+3.0*aWeight;\n"
        "  vColor=vec4(aColor.rgb*(0.85+0.15*aWeight),aColor.a);\n"
        "}\n";

    static const char *fs_source =
        "#version 300 es\n"
        "precision highp float;\n"
        "in vec4 vColor;\n"
        "out vec4 outColor;\n"
        "void main(){\n"
        "  outColor=vColor;\n"
        "}\n";

    XzNativeGles3Api *gl = &xz_shadow.gl;
    GLuint vs = 0u;
    GLuint fs = 0u;
    GLint linked = 0;

    if (!XzCompileShader(
            gl, GL_VERTEX_SHADER, vs_source, &vs))
        return 0;

    if (!XzCompileShader(
            gl, GL_FRAGMENT_SHADER, fs_source, &fs)) {
        gl->DeleteShader(vs);
        return 0;
    }

    xz_shadow.program = gl->CreateProgram();
    if (!xz_shadow.program) {
        gl->DeleteShader(vs);
        gl->DeleteShader(fs);
        return 0;
    }

    gl->AttachShader(xz_shadow.program, vs);
    gl->AttachShader(xz_shadow.program, fs);
    gl->LinkProgram(xz_shadow.program);
    gl->GetProgramiv(
        xz_shadow.program,
        GL_LINK_STATUS,
        &linked);

    gl->DeleteShader(vs);
    gl->DeleteShader(fs);

    if (!linked)
        return 0;

    gl->GenVertexArrays(1, &xz_shadow.vao);
    gl->BindVertexArray(xz_shadow.vao);

    gl->GenBuffers(1, &xz_shadow.vbo);
    gl->BindBuffer(GL_ARRAY_BUFFER, xz_shadow.vbo);
    gl->BufferData(
        GL_ARRAY_BUFFER,
        (GLsizeiptr)(
            XZ_RENDER_MAX_PACKETS *
            XZ_VERTICES_PER_PACKET *
            XZ_VERTEX_FLOATS *
            sizeof(float)),
        NULL,
        GL_STREAM_DRAW);

    gl->EnableVertexAttribArray(0u);
    gl->VertexAttribPointer(
        0u,
        2,
        GL_FLOAT,
        GL_FALSE,
        (GLsizei)(XZ_VERTEX_FLOATS * sizeof(float)),
        (const void *)0);

    gl->EnableVertexAttribArray(1u);
    gl->VertexAttribPointer(
        1u,
        1,
        GL_FLOAT,
        GL_FALSE,
        (GLsizei)(XZ_VERTEX_FLOATS * sizeof(float)),
        (const void *)(uintptr_t)(2u * sizeof(float)));

    gl->EnableVertexAttribArray(2u);
    gl->VertexAttribPointer(
        2u,
        4,
        GL_FLOAT,
        GL_FALSE,
        (GLsizei)(XZ_VERTEX_FLOATS * sizeof(float)),
        (const void *)(uintptr_t)(3u * sizeof(float)));

    gl->BindVertexArray(0u);
    gl->BindBuffer(GL_ARRAY_BUFFER, 0u);

    gl->GenFramebuffers(1, &xz_shadow.scratch_fbo);
    if (!xz_shadow.scratch_fbo)
        return 0;

    return gl->GetError() == GL_NO_ERROR;
}

static int XzCreateRealGeometryProgram(void)
{
    static const char *vs_source =
        "#version 300 es\n"
        "layout(location=0) in vec3 aPos;\n"
        "layout(location=1) in vec2 aUV;\n"
        "uniform mat4 uModelView;\n"
        "uniform mat4 uProjection;\n"
        "out vec2 vUV;\n"
        "out float vFogCoord;\n"
        "void main(){\n"
        "  vec4 eye=uModelView*vec4(aPos,1.0);\n"
        "  gl_Position=uProjection*eye;\n"
        "  vUV=aUV;\n"
        "  vFogCoord=abs(eye.z);\n"
        "}\n";

    static const char *fs_source =
        "#version 300 es\n"
        "precision mediump float;\n"
        "in vec2 vUV;\n"
        "uniform sampler2D uTexture;\n"
        "uniform int uTextureEnabled;\n"
        "uniform vec4 uColor;\n"
        "uniform int uTexEnvModulate;\n"
        "uniform int uAlphaTest;\n"
        "uniform int uAlphaFunc;\n"
        "uniform float uAlphaRef;\n"
        "uniform int uFogEnabled;\n"
        "uniform float uFogStart;\n"
        "uniform float uFogEnd;\n"
        "uniform vec4 uFogColor;\n"
        "in float vFogCoord;\n"
        "out vec4 outColor;\n"
        "void main(){\n"
        "  vec4 texel=(uTextureEnabled!=0)?texture(uTexture,vUV):vec4(1.0);\n"
        "  vec4 c=(uTextureEnabled!=0)?((uTexEnvModulate!=0)?texel*uColor:texel):uColor;\n"
        "  if(uAlphaTest!=0){\n"
        "    bool pass=true;\n"
        "    if(uAlphaFunc==0) pass=false;\n"
        "    else if(uAlphaFunc==1) pass=c.a<uAlphaRef;\n"
        "    else if(uAlphaFunc==2) pass=abs(c.a-uAlphaRef)<0.0001;\n"
        "    else if(uAlphaFunc==3) pass=c.a<=uAlphaRef;\n"
        "    else if(uAlphaFunc==4) pass=c.a>uAlphaRef;\n"
        "    else if(uAlphaFunc==5) pass=abs(c.a-uAlphaRef)>=0.0001;\n"
        "    else if(uAlphaFunc==6) pass=c.a>=uAlphaRef;\n"
        "    if(!pass) discard;\n"
        "  }\n"
        "  if(uFogEnabled!=0 && uFogEnd>uFogStart){\n"
        "    float f=clamp((uFogEnd-vFogCoord)/(uFogEnd-uFogStart),0.0,1.0);\n"
        "    c.rgb=mix(uFogColor.rgb,c.rgb,f);\n"
        "  }\n"
        "  outColor=c;\n"
        "}\n";

    XzNativeGles3Api *gl = &xz_shadow.gl;
    GLuint vs = 0u;
    GLuint fs = 0u;
    GLint linked = 0;

    if (!XzCompileShader(
            gl, GL_VERTEX_SHADER, vs_source, &vs))
        return 0;

    if (!XzCompileShader(
            gl, GL_FRAGMENT_SHADER, fs_source, &fs)) {
        gl->DeleteShader(vs);
        return 0;
    }

    xz_shadow.real_program = gl->CreateProgram();
    if (!xz_shadow.real_program) {
        gl->DeleteShader(vs);
        gl->DeleteShader(fs);
        return 0;
    }

    gl->AttachShader(xz_shadow.real_program, vs);
    gl->AttachShader(xz_shadow.real_program, fs);
    gl->LinkProgram(xz_shadow.real_program);
    gl->GetProgramiv(
        xz_shadow.real_program,
        GL_LINK_STATUS,
        &linked);

    gl->DeleteShader(vs);
    gl->DeleteShader(fs);

    if (!linked)
        return 0;

    xz_shadow.real_modelview_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uModelView");
    xz_shadow.real_projection_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uProjection");
    xz_shadow.real_texture_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uTexture");
    xz_shadow.real_texture_enabled_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uTextureEnabled");
    xz_shadow.real_color_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uColor");
    xz_shadow.real_texenv_modulate_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uTexEnvModulate");
    xz_shadow.real_alpha_test_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uAlphaTest");
    xz_shadow.real_alpha_func_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uAlphaFunc");
    xz_shadow.real_alpha_ref_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uAlphaRef");
    xz_shadow.real_fog_enabled_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uFogEnabled");
    xz_shadow.real_fog_start_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uFogStart");
    xz_shadow.real_fog_end_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uFogEnd");
    xz_shadow.real_fog_color_loc =
        gl->GetUniformLocation(
            xz_shadow.real_program,
            "uFogColor");

    if (xz_shadow.real_modelview_loc < 0 ||
        xz_shadow.real_projection_loc < 0 ||
        xz_shadow.real_texture_loc < 0 ||
        xz_shadow.real_texture_enabled_loc < 0 ||
        xz_shadow.real_color_loc < 0 ||
        xz_shadow.real_texenv_modulate_loc < 0 ||
        xz_shadow.real_alpha_test_loc < 0 ||
        xz_shadow.real_alpha_func_loc < 0 ||
        xz_shadow.real_alpha_ref_loc < 0 ||
        xz_shadow.real_fog_enabled_loc < 0 ||
        xz_shadow.real_fog_start_loc < 0 ||
        xz_shadow.real_fog_end_loc < 0 ||
        xz_shadow.real_fog_color_loc < 0)
        return 0;

    gl->UseProgram(xz_shadow.real_program);
    gl->Uniform1i(xz_shadow.real_texture_loc, 0);
    gl->UseProgram(0u);

    gl->GenVertexArrays(1, &xz_shadow.real_vao);
    gl->BindVertexArray(xz_shadow.real_vao);

    gl->GenBuffers(1, &xz_shadow.real_vbo);
    gl->BindBuffer(
        GL_ARRAY_BUFFER,
        xz_shadow.real_vbo);
    gl->BufferData(
        GL_ARRAY_BUFFER,
        (GLsizeiptr)(
            XZ_GEOMETRY_MAX_VERTICES *
            sizeof(XzGeometryVertex)),
        NULL,
        GL_STREAM_DRAW);

    gl->GenBuffers(1, &xz_shadow.real_ibo);
    gl->BindBuffer(
        GL_ELEMENT_ARRAY_BUFFER,
        xz_shadow.real_ibo);
    gl->BufferData(
        GL_ELEMENT_ARRAY_BUFFER,
        (GLsizeiptr)(
            XZ_GEOMETRY_MAX_INDICES *
            sizeof(uint32_t)),
        NULL,
        GL_STREAM_DRAW);

    gl->EnableVertexAttribArray(0u);
    gl->VertexAttribPointer(
        0u,
        3,
        GL_FLOAT,
        GL_FALSE,
        (GLsizei)sizeof(XzGeometryVertex),
        (const void *)0);

    gl->EnableVertexAttribArray(1u);
    gl->VertexAttribPointer(
        1u,
        2,
        GL_FLOAT,
        GL_FALSE,
        (GLsizei)sizeof(XzGeometryVertex),
        (const void *)(uintptr_t)(
            3u * sizeof(float)));

    gl->BindVertexArray(0u);
    gl->BindBuffer(GL_ARRAY_BUFFER, 0u);
    gl->BindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0u);

    {
        static const unsigned char fallback_rgba[4] = {
            255u, 0u, 255u, 255u
        };

        gl->GenTextures(
            1, &xz_shadow.real_fallback_texture);
        if (!xz_shadow.real_fallback_texture)
            return 0;

        gl->ActiveTexture(GL_TEXTURE0);
        gl->BindTexture(
            GL_TEXTURE_2D,
            xz_shadow.real_fallback_texture);
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MIN_FILTER,
            GL_NEAREST);
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_NEAREST);
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_S,
            GL_REPEAT);
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_T,
            GL_REPEAT);
        gl->TexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            1,
            1,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            fallback_rgba);
        gl->BindTexture(GL_TEXTURE_2D, 0u);
    }

    return gl->GetError() == GL_NO_ERROR;
}


static int XzCreateStaticSceneProgram(void)
{
    static const char *vs_source =
        "#version 300 es\n"
        "layout(location=0) in vec3 aPos;\n"
        "layout(location=1) in vec4 aUV01;\n"
        "layout(location=2) in vec3 aNormal;\n"
        "layout(location=3) in vec4 aUV23;\n"
        "layout(location=4) in vec4 aTangent;\n"
        "layout(location=5) in mat4 aModel;\n"
        "layout(location=9) in vec4 aLightmapCoord;\n"
        "layout(location=10) in vec4 aLightmapScale0;\n"
        "layout(location=11) in vec4 aLightmapAdd0;\n"
        "layout(location=12) in vec4 aLightmapScale1;\n"
        "layout(location=13) in vec4 aLightmapAdd1;\n"
        "layout(location=14) in vec4 aLightmapMeta;\n"
        "uniform mat4 uView;\n"
        "uniform mat4 uProjection;\n"
        "out vec3 vNormal;\n"
        "out vec3 vWorldPos;\n"
        "out vec2 vUV;\n"
        "out vec4 vTangent;\n"
        "out vec2 vLightmapUV0;\n"
        "out vec2 vLightmapUV1;\n"
        "flat out vec4 vLightmapScale0;\n"
        "flat out vec4 vLightmapAdd0;\n"
        "flat out vec4 vLightmapScale1;\n"
        "flat out vec4 vLightmapAdd1;\n"
        "flat out float vLightmapEnabled;\n"
        "void main(){\n"
        "  vec4 world=aModel*vec4(aPos,1.0);\n"
        "  gl_Position=uProjection*uView*world;\n"
        "  mat3 model3=mat3(aModel);\n"
        "  mat3 normalMatrix=transpose(inverse(model3));\n"
        "  vNormal=normalize(normalMatrix*aNormal);\n"
        "  vec3 tangentWorld=model3*aTangent.xyz;\n"
        "  tangentWorld-=vNormal*dot(vNormal,tangentWorld);\n"
        "  float tangentLen2=dot(tangentWorld,tangentWorld);\n"
        "  if(tangentLen2>1.0e-8) tangentWorld*=inversesqrt(tangentLen2);\n"
        "  else tangentWorld=vec3(0.0);\n"
        "  float mirrorSign=determinant(model3)<0.0?-1.0:1.0;\n"
        "  vTangent=vec4(tangentWorld,aTangent.w*mirrorSign);\n"
        "  vWorldPos=world.xyz;\n"
        "  vec2 aUV=aUV01.xy;\n"
        "  vec2 aUV1=aUV01.zw;\n"
        "  vec2 aUV2=aUV23.xy;\n"
        "  vec2 aUV3=aUV23.zw;\n"
        "  vUV=aUV;\n"
        "  int lmChannel=int(floor(aLightmapMeta.x+0.5));\n"
        "  vec2 lmUV=aUV;\n"
        "  if(lmChannel==1) lmUV=aUV1;\n"
        "  else if(lmChannel==2) lmUV=aUV2;\n"
        "  else if(lmChannel==3) lmUV=aUV3;\n"
        "  vec2 ueUV=vec2(lmUV.x,1.0-lmUV.y);\n"
        "  vec2 packedUV=ueUV*aLightmapCoord.xy+aLightmapCoord.zw;\n"
        "  vLightmapUV0=vec2(packedUV.x,1.0-packedUV.y*0.5);\n"
        "  vLightmapUV1=vec2(packedUV.x,1.0-(packedUV.y*0.5+0.5));\n"
        "  vLightmapScale0=aLightmapScale0;\n"
        "  vLightmapAdd0=aLightmapAdd0;\n"
        "  vLightmapScale1=aLightmapScale1;\n"
        "  vLightmapAdd1=aLightmapAdd1;\n"
        "  vLightmapEnabled=aLightmapMeta.y;\n"
        "}\n";

    static const char *fs_source =
        "#version 300 es\n"
        "precision highp float;\n"
        "in vec3 vNormal;\n"
        "in vec3 vWorldPos;\n"
        "in vec2 vUV;\n"
        "in vec4 vTangent;\n"
        "in vec2 vLightmapUV0;\n"
        "in vec2 vLightmapUV1;\n"
        "flat in vec4 vLightmapScale0;\n"
        "flat in vec4 vLightmapAdd0;\n"
        "flat in vec4 vLightmapScale1;\n"
        "flat in vec4 vLightmapAdd1;\n"
        "flat in float vLightmapEnabled;\n"
        "uniform sampler2D uLightmapHQ;\n"
        "uniform int uHasLightmap;\n"
        "uniform sampler2D uBaseColor;\n"
        "uniform int uHasBaseColor;\n"
        "uniform sampler2D uNormalMap;\n"
        "uniform int uHasNormalMap;\n"
        "uniform float uAmbientWeight;\n"
        "uniform float uDirectionalWeight;\n"
        "uniform vec3 uDirectionalColor;\n"
        "uniform vec3 uDirectionalDirection;\n"
        "uniform int uLocalLightCount;\n"
        "uniform vec4 uLocalPosInvRadius[64];\n"
        "uniform vec4 uLocalColorCone[64];\n"
        "uniform vec4 uLocalDirCosOuter[64];\n"
        "uniform vec3 uCameraPosGame;\n"
        "uniform vec4 uFogPrimary;\n"
        "uniform vec4 uFogColorMin;\n"
        "uniform float uFogCutoffCm;\n"
        "uniform vec4 uPbrParams;\n"
        "uniform int uPbrFlags;\n"
        "uniform int uMaterialShadingMode;\n"
        "uniform int uMaterialBlendMode;\n"
        "uniform float uMaterialOpacity;\n"
        "uniform float uOpacityMaskClip;\n"
        "uniform samplerCube uReflectionCapture;\n"
        "uniform vec4 uReflectionParams;\n"
        "uniform vec4 uReflectionSphere;\n"
        "uniform vec3 uReflectionCaptureOffset;\n"
        "out vec4 outColor;\n"
        "float ueLinearToSrgb1(float x){\n"
        "  x=max(x,0.0);\n"
        "  return x<=0.0031308?12.92*x:1.055*pow(x,1.0/2.4)-0.055;\n"
        "}\n"
        "vec3 ueLinearToSrgb(vec3 v){\n"
        "  return vec3(ueLinearToSrgb1(v.r),ueLinearToSrgb1(v.g),ueLinearToSrgb1(v.b));\n"
        "}\n"
        "float ueLog10(float x){\n"
        "  return log2(max(x,1.0e-10))*0.301029995664;\n"
        "}\n"
        "vec3 ueLog10v(vec3 v){\n"
        "  return vec3(ueLog10(v.r),ueLog10(v.g),ueLog10(v.b));\n"
        "}\n"
        "vec3 ueSrgbToAp1(vec3 c){\n"
        "  return vec3(\n"
        "    dot(vec3(0.6131914784,0.3395120888,0.0473663312),c),\n"
        "    dot(vec3(0.0702069045,0.9163358171,0.0134500113),c),\n"
        "    dot(vec3(0.0206188714,0.1095672943,0.8696067475),c));\n"
        "}\n"
        "vec3 ueAp1ToSrgb(vec3 c){\n"
        "  return vec3(\n"
        "    dot(vec3(1.7050515455,-0.6217906804,-0.0832583971),c),\n"
        "    dot(vec3(-0.1302571442,1.1408028901,-0.0105485284),c),\n"
        "    dot(vec3(-0.0240032750,-0.1289687693,1.1529717079),c));\n"
        "}\n"
        "vec3 ueAp1ToAp0(vec3 c){\n"
        "  return vec3(\n"
        "    dot(vec3(0.6954522414,0.1406786965,0.1638690622),c),\n"
        "    dot(vec3(0.0447945634,0.8596711185,0.0955343182),c),\n"
        "    dot(vec3(-0.0055258826,0.0040252103,1.0015006723),c));\n"
        "}\n"
        "vec3 ueAp0ToAp1(vec3 c){\n"
        "  return vec3(\n"
        "    dot(vec3(1.4514393161,-0.2365107469,-0.2149285693),c),\n"
        "    dot(vec3(-0.0765537734,1.1762296998,-0.0996759264),c),\n"
        "    dot(vec3(0.0083161484,-0.0060324498,0.9977163014),c));\n"
        "}\n"
        "vec3 ueExpandAp1(vec3 c){\n"
        "  return vec3(\n"
        "    dot(vec3(1.3704127095,-0.3292913010,-0.0636827679),c),\n"
        "    dot(vec3(-0.0834341865,1.0970909835,-0.0108615725),c),\n"
        "    dot(vec3(-0.0257932582,-0.0986256403,1.2036942940),c));\n"
        "}\n"
        "vec3 ueBlueCorrectAp1(vec3 c){\n"
        "  return vec3(\n"
        "    dot(vec3(0.9386393778,0.0000000001,0.0613606221),c),\n"
        "    dot(vec3(0.0,0.8307941330,0.1692058671),c),\n"
        "    c.b);\n"
        "}\n"
        "vec3 ueBlueCorrectInvAp1(vec3 c){\n"
        "  return vec3(\n"
        "    dot(vec3(1.0653748755,0.0000014467,-0.0653710053),c),\n"
        "    dot(vec3(-0.0000003456,1.2036635245,-0.2036677199),c),\n"
        "    dot(vec3(0.0000000198,0.0000000212,0.9999996001),c));\n"
        "}\n"
        "float ueRgbSaturation(vec3 rgb){\n"
        "  float mn=min(min(rgb.r,rgb.g),rgb.b);\n"
        "  float mx=max(max(rgb.r,rgb.g),rgb.b);\n"
        "  return (max(mx,1.0e-10)-max(mn,1.0e-10))/max(mx,1.0e-2);\n"
        "}\n"
        "float ueRgbYc(vec3 rgb){\n"
        "  float r=rgb.r; float g=rgb.g; float b=rgb.b;\n"
        "  float chroma=sqrt(max(b*(b-g)+g*(g-r)+r*(r-b),0.0));\n"
        "  return (b+g+r+1.75*chroma)/3.0;\n"
        "}\n"
        "float ueSigmoidShaper(float x){\n"
        "  float t=max(1.0-abs(0.5*x),0.0);\n"
        "  return 0.5*(1.0+sign(x)*(1.0-t*t));\n"
        "}\n"
        "float ueGlowFwd(float yc,float gain,float mid){\n"
        "  if(yc<=0.666666666667*mid) return gain;\n"
        "  if(yc>=2.0*mid) return 0.0;\n"
        "  return gain*(mid/yc-0.5);\n"
        "}\n"
        "float ueRgbHue(vec3 rgb){\n"
        "  if(rgb.r==rgb.g && rgb.g==rgb.b) return 0.0;\n"
        "  float h=57.2957795131*atan(sqrt(3.0)*(rgb.g-rgb.b),2.0*rgb.r-rgb.g-rgb.b);\n"
        "  if(h<0.0) h+=360.0;\n"
        "  return clamp(h,0.0,360.0);\n"
        "}\n"
        "float ueCenterHue(float hue,float center){\n"
        "  float h=hue-center;\n"
        "  if(h<-180.0) h+=360.0; else if(h>180.0) h-=360.0;\n"
        "  return h;\n"
        "}\n"
        "vec3 ueFilmToneMapAp1(vec3 linearAp1){\n"
        "  const float FilmSlope=0.88;\n"
        "  const float FilmToe=0.55;\n"
        "  const float FilmShoulder=0.26;\n"
        "  const float FilmBlackClip=0.0;\n"
        "  const float FilmWhiteClip=0.04;\n"
        "  const vec3 AP1_RGB2Y=vec3(0.2722287168,0.6740817658,0.0536895174);\n"
        "  vec3 colorAp0=ueAp1ToAp0(linearAp1);\n"
        "  float saturation=ueRgbSaturation(colorAp0);\n"
        "  float ycIn=ueRgbYc(colorAp0);\n"
        "  float sig=ueSigmoidShaper((saturation-0.4)/0.2);\n"
        "  colorAp0*=1.0+ueGlowFwd(ycIn,0.05*sig,0.08);\n"
        "  float centeredHue=ueCenterHue(ueRgbHue(colorAp0),0.0);\n"
        "  float hueBase=clamp(1.0-abs(2.0*centeredHue/135.0),0.0,1.0);\n"
        "  float hueSmooth=hueBase*hueBase*(3.0-2.0*hueBase);\n"
        "  float hueWeight=hueSmooth*hueSmooth;\n"
        "  colorAp0.r+=hueWeight*saturation*(0.03-colorAp0.r)*0.18;\n"
        "  vec3 working=max(ueAp0ToAp1(colorAp0),vec3(0.0));\n"
        "  working=mix(vec3(dot(working,AP1_RGB2Y)),working,0.96);\n"
        "  float toeScale=1.0+FilmBlackClip-FilmToe;\n"
        "  float shoulderScale=1.0+FilmWhiteClip-FilmShoulder;\n"
        "  float bt=(0.18+FilmBlackClip)/toeScale-1.0;\n"
        "  float toeMatch=ueLog10(0.18)-0.5*log((1.0+bt)/(1.0-bt))*(toeScale/FilmSlope);\n"
        "  float straightMatch=(1.0-FilmToe)/FilmSlope-toeMatch;\n"
        "  float shoulderMatch=FilmShoulder/FilmSlope-straightMatch;\n"
        "  vec3 logColor=ueLog10v(working);\n"
        "  vec3 straightColor=FilmSlope*(logColor+vec3(straightMatch));\n"
        "  vec3 toeColor=vec3(-FilmBlackClip)+(2.0*toeScale)/(vec3(1.0)+exp((-2.0*FilmSlope/toeScale)*(logColor-vec3(toeMatch))));\n"
        "  vec3 shoulderColor=vec3(1.0+FilmWhiteClip)-(2.0*shoulderScale)/(vec3(1.0)+exp((2.0*FilmSlope/shoulderScale)*(logColor-vec3(shoulderMatch))));\n"
        "  toeColor=mix(toeColor,straightColor,step(vec3(toeMatch),logColor));\n"
        "  shoulderColor=mix(straightColor,shoulderColor,step(vec3(shoulderMatch),logColor));\n"
        "  vec3 t=clamp((logColor-vec3(toeMatch))/(shoulderMatch-toeMatch),0.0,1.0);\n"
        "  if(shoulderMatch<toeMatch) t=vec3(1.0)-t;\n"
        "  t=(vec3(3.0)-2.0*t)*t*t;\n"
        "  vec3 tone=mix(toeColor,shoulderColor,t);\n"
        "  tone=mix(vec3(dot(tone,AP1_RGB2Y)),tone,0.93);\n"
        "  return max(tone,vec3(0.0));\n"
        "}\n"
        "vec3 ueDefaultFilmicTonemap(vec3 linearSrgb){\n"
        "  const vec3 AP1_RGB2Y=vec3(0.2722287168,0.6740817658,0.0536895174);\n"
        "  vec3 colorAp1=ueSrgbToAp1(max(linearSrgb,vec3(0.0)));\n"
        "  float luma=max(dot(colorAp1,AP1_RGB2Y),1.0e-6);\n"
        "  vec3 chroma=colorAp1/luma;\n"
        "  float chromaDist=dot(chroma-vec3(1.0),chroma-vec3(1.0));\n"
        "  float expandAmount=(1.0-exp2(-4.0*chromaDist))*(1.0-exp2(-4.0*luma*luma));\n"
        "  colorAp1=mix(colorAp1,ueExpandAp1(colorAp1),expandAmount);\n"
        "  colorAp1=mix(colorAp1,ueBlueCorrectAp1(colorAp1),0.6);\n"
        "  colorAp1=ueFilmToneMapAp1(colorAp1);\n"
        "  colorAp1=mix(colorAp1,ueBlueCorrectInvAp1(colorAp1),0.6);\n"
        "  vec3 filmLinear=max(ueAp1ToSrgb(colorAp1),vec3(0.0));\n"
        "  return clamp(ueLinearToSrgb(filmLinear)/1.05,0.0,1.0);\n"
        "}\n"
        "vec3 uePavlovLegacyTonemap(vec3 linearSrgb){\n"
        "  const float FilmContrast=0.03;\n"
        "  const float FilmDynamicRange=4.0;\n"
        "  const float FilmToeAmount=1.0;\n"
        "  const float FilmHealAmount=0.18;\n"
        "  float inContrast=clamp(FilmContrast,0.0,1.0)+1.0;\n"
        "  float inDynamicRange=exp2(clamp(FilmDynamicRange,1.0,4.0));\n"
        "  float inToe=(1.0-clamp(FilmToeAmount,0.0,1.0))*0.18;\n"
        "  inToe=clamp(inToe,0.18/8.0,0.18*(15.0/16.0));\n"
        "  float inHeal=1.0-(max(1.0/32.0,1.0-clamp(FilmHealAmount,0.0,1.0))*(1.0-0.18));\n"
        "  float filmLineOffset=0.18-0.18*inContrast;\n"
        "  float filmXAtY0=-filmLineOffset/inContrast;\n"
        "  float filmXAtY1=(1.0-filmLineOffset)/inContrast;\n"
        "  float filmXS=filmXAtY1-filmXAtY0;\n"
        "  float filmHiX=filmXAtY0+inHeal*filmXS;\n"
        "  float filmHiY=filmHiX*inContrast+filmLineOffset;\n"
        "  float filmLoX=filmXAtY0+inToe*filmXS;\n"
        "  float filmLoY=filmLoX*inContrast+filmLineOffset;\n"
        "  float filmHeal=inDynamicRange-filmHiX;\n"
        "  float filmSlope=(filmHiY-filmLoY)/(filmHiX-filmLoX);\n"
        "  float filmHiYS=1.0-filmHiY;\n"
        "  float filmLoYS=filmLoY;\n"
        "  float filmHiG=(-filmHiYS+filmSlope*filmHeal)/(filmSlope*filmHeal);\n"
        "  float filmLoG=(-filmLoYS+filmSlope*filmLoX)/(filmSlope*filmLoX);\n"
        "  float ch1=filmHiYS/filmHiG;\n"
        "  float ch2=-filmHiX*ch1;\n"
        "  float ch3=filmHiYS/(filmSlope*filmHiG)-filmHiX;\n"
        "  float cd1=filmLoG!=0.0?-filmLoYS/filmLoG:0.0;\n"
        "  float cd2=filmLoG!=0.0?filmLoYS/(filmSlope*filmLoG):1.0;\n"
        "  float cm0=filmLoG!=0.0?filmLoX:0.0;\n"
        "  float cd3=filmLoG!=0.0?filmLoY-filmLoX*filmSlope:0.0;\n"
        "  vec3 matrixColor=max(linearSrgb,vec3(0.0));\n"
        "  vec3 matrixColorD=max(vec3(0.0),vec3(cm0)-matrixColor);\n"
        "  vec3 matrixColorH=max(matrixColor,vec3(filmHiX));\n"
        "  vec3 matrixColorM=clamp(matrixColor,vec3(cm0),vec3(filmHiX));\n"
        "  vec3 curveColor=(matrixColorH*ch1+vec3(ch2))/(matrixColorH+vec3(ch3));\n"
        "  curveColor+=matrixColorM*filmSlope;\n"
        "  curveColor+=(matrixColorD*cd1)/(matrixColorD+vec3(cd2))+vec3(cd3);\n"
        "  curveColor-=vec3(0.002);\n"
        "  return clamp(ueLinearToSrgb(max(curveColor,vec3(0.0)))/1.05,0.0,1.0);\n"
        "}\n"
        "vec3 surfaceNormal(vec3 geometricNormal){\n"
        "  if(uHasNormalMap==0) return geometricNormal;\n"
        "  vec3 mapN=texture(uNormalMap,vUV).xyz*2.0-1.0;\n"
        "  mapN.y=-mapN.y;\n"
        "  float mapLen2=dot(mapN,mapN);\n"
        "  if(mapLen2<1.0e-6) return geometricNormal;\n"
        "  mapN*=inversesqrt(mapLen2);\n"
        "  vec3 tangentRaw=vTangent.xyz;\n"
        "  float tangentLen2=dot(tangentRaw,tangentRaw);\n"
        "  float tangentSign=vTangent.w>=0.0?1.0:-1.0;\n"
        "  if(tangentLen2<1.0e-8){\n"
        "    vec3 dp1=dFdx(vWorldPos);\n"
        "    vec3 dp2=dFdy(vWorldPos);\n"
        "    vec2 duv1=dFdx(vUV);\n"
        "    vec2 duv2=dFdy(vUV);\n"
        "    float det=duv1.x*duv2.y-duv1.y*duv2.x;\n"
        "    if(abs(det)<1.0e-8) return geometricNormal;\n"
        "    tangentRaw=dp1*duv2.y-dp2*duv1.y;\n"
        "    tangentSign=det<0.0?-1.0:1.0;\n"
        "  }\n"
        "  tangentRaw-=geometricNormal*dot(geometricNormal,tangentRaw);\n"
        "  tangentLen2=dot(tangentRaw,tangentRaw);\n"
        "  if(tangentLen2<1.0e-8) return geometricNormal;\n"
        "  vec3 T=tangentRaw*inversesqrt(tangentLen2);\n"
        "  vec3 B=normalize(cross(geometricNormal,T))*tangentSign;\n"
        "  return normalize(mat3(T,B,geometricNormal)*mapN);\n"
        "}\n"
        "vec3 fresnelSchlick(float cosTheta,vec3 f0){\n"
        "  float x=clamp(1.0-cosTheta,0.0,1.0);\n"
        "  float x2=x*x;\n"
        "  float x5=x2*x2*x;\n"
        "  return f0+(vec3(1.0)-f0)*x5;\n"
        "}\n"
        "float distributionGGX(vec3 N,vec3 H,float roughness){\n"
        "  float a=roughness*roughness;\n"
        "  float a2=a*a;\n"
        "  float ndh=max(dot(N,H),0.0);\n"
        "  float ndh2=ndh*ndh;\n"
        "  float denom=ndh2*(a2-1.0)+1.0;\n"
        "  return a2/max(3.14159265359*denom*denom,1.0e-6);\n"
        "}\n"
        "float geometrySchlickGGX(float ndv,float roughness){\n"
        "  float r=roughness+1.0;\n"
        "  float k=(r*r)*0.125;\n"
        "  return ndv/max(ndv*(1.0-k)+k,1.0e-6);\n"
        "}\n"
        "float geometrySmith(vec3 N,vec3 V,vec3 L,float roughness){\n"
        "  float ndv=max(dot(N,V),0.0);\n"
        "  float ndl=max(dot(N,L),0.0);\n"
        "  return geometrySchlickGGX(ndv,roughness)*geometrySchlickGGX(ndl,roughness);\n"
        "}\n"
        "vec3 cookTorranceSpec(vec3 N,vec3 V,vec3 L,float roughness,vec3 f0){\n"
        "  float ndv=max(dot(N,V),0.0);\n"
        "  float ndl=max(dot(N,L),0.0);\n"
        "  vec3 halfRaw=V+L;\n"
        "  float halfLen2=dot(halfRaw,halfRaw);\n"
        "  if(ndv<=0.0||ndl<=0.0||halfLen2<=1.0e-6) return vec3(0.0);\n"
        "  vec3 H=halfRaw*inversesqrt(halfLen2);\n"
        "  float D=distributionGGX(N,H,roughness);\n"
        "  float G=geometrySmith(N,V,L,roughness);\n"
        "  vec3 F=fresnelSchlick(max(dot(H,V),0.0),f0);\n"
        "  return (D*G*F)/max(4.0*ndv*ndl,1.0e-4);\n"
        "}\n"
        "float ueReflectionMip(float roughness){\n"
        "  float levelFrom1x1=1.0-1.2*log2(max(roughness,1.0e-4));\n"
        "  return clamp(uReflectionParams.x-1.0-levelFrom1x1,0.0,uReflectionParams.x);\n"
        "}\n"
        "vec3 ueEnvBRDFApprox(vec3 f0,float roughness,float ndv){\n"
        "  const vec4 c0=vec4(-1.0,-0.0275,-0.572,0.022);\n"
        "  const vec4 c1=vec4(1.0,0.0425,1.04,-0.04);\n"
        "  vec4 r=roughness*c0+c1;\n"
        "  float a004=min(r.x*r.x,exp2(-9.28*ndv))*r.x+r.y;\n"
        "  vec2 ab=vec2(-1.04,1.04)*a004+r.zw;\n"
        "  ab.y*=clamp(50.0*f0.g,0.0,1.0);\n"
        "  return f0*ab.x+vec3(ab.y);\n"
        "}\n"
        "vec4 ueSphereReflectionVector(vec3 reflectionVector,vec3 worldPos){\n"
        "  float radius=uReflectionSphere.w;\n"
        "  if(radius<=0.0) return vec4(reflectionVector,1.0);\n"
        "  vec3 localPosition=worldPos-uReflectionSphere.xyz;\n"
        "  float localPositionSqr=dot(localPosition,localPosition);\n"
        "  float radiusSqr=radius*radius;\n"
        "  if(localPositionSqr>=radiusSqr) return vec4(reflectionVector,0.0);\n"
        "  float normalizedDistance=clamp(sqrt(localPositionSqr)/radius,0.0,1.0);\n"
        "  float quadraticY=dot(reflectionVector,localPosition);\n"
        "  float determinant=quadraticY*quadraticY-(localPositionSqr-radiusSqr);\n"
        "  vec3 projected=reflectionVector;\n"
        "  float distanceAlpha=0.0;\n"
        "  if(determinant>=0.0){\n"
        "    float farIntersection=sqrt(determinant)-quadraticY;\n"
        "    vec3 localIntersection=localPosition+farIntersection*reflectionVector;\n"
        "    projected=localIntersection-uReflectionCaptureOffset;\n"
        "    float x=clamp(2.5*normalizedDistance-1.5,0.0,1.0);\n"
        "    distanceAlpha=1.0-x*x*(3.0-2.0*x);\n"
        "  }\n"
        "  return vec4(projected,distanceAlpha);\n"
        "}\n"
        "vec3 ueReflectionIBL(vec3 N,vec3 V,float roughness,vec3 f0){\n"
        "  if(uReflectionParams.w<0.5) return vec3(0.0);\n"
        "  vec3 R=reflect(-V,N);\n"
        "  vec4 projected=ueSphereReflectionVector(R,vWorldPos);\n"
        "  if(projected.w<=0.0) return vec3(0.0);\n"
        "  vec3 ueR=normalize(vec3(projected.x,-projected.y,projected.z));\n"
        "  float mip=ueReflectionMip(roughness);\n"
        "  vec3 radiance=textureLod(uReflectionCapture,ueR,mip).rgb*uReflectionParams.y*projected.w;\n"
        "  float ndv=max(dot(N,V),0.0);\n"
        "  return radiance*ueEnvBRDFApprox(f0,roughness,ndv);\n"
        "}\n"
        "float ueFogTransmission(vec3 worldPosGame){\n"
        "  vec3 rayCm=(worldPosGame-uCameraPosGame)*2.54;\n"
        "  float originalLength=length(rayCm);\n"
        "  if(originalLength<=1.0e-5 || originalLength<=uFogPrimary.w || uFogPrimary.x<=0.0) return 1.0;\n"
        "  float cameraZ=uCameraPosGame.z*2.54;\n"
        "  float rayLength=originalLength;\n"
        "  float rayDirectionZ=rayCm.z;\n"
        "  float collapsedPower=clamp(-uFogPrimary.y*(cameraZ-uFogPrimary.z),-125.0,126.0);\n"
        "  float rayOriginTerms=uFogPrimary.x*exp2(collapsedPower);\n"
        "  if(uFogPrimary.w>0.0){\n"
        "    float excludeT=clamp(uFogPrimary.w/originalLength,0.0,1.0);\n"
        "    float exclusionZ=cameraZ+excludeT*rayCm.z;\n"
        "    rayLength=(1.0-excludeT)*originalLength;\n"
        "    rayDirectionZ=(1.0-excludeT)*rayCm.z;\n"
        "    float exponent=max(-127.0,uFogPrimary.y*(exclusionZ-uFogPrimary.z));\n"
        "    rayOriginTerms=uFogPrimary.x*exp2(-exponent);\n"
        "  }\n"
        "  float falloff=max(-127.0,uFogPrimary.y*rayDirectionZ);\n"
        "  float lineIntegral=(abs(falloff)>0.01)\n"
        "    ?(1.0-exp2(-falloff))/falloff\n"
        "    :(0.69314718056-0.24022650696*falloff);\n"
        "  float shared=rayOriginTerms*lineIntegral;\n"
        "  float transmission=max(clamp(exp2(-(shared*rayLength)),0.0,1.0),uFogColorMin.a);\n"
        "  if(uFogCutoffCm>0.0 && originalLength>uFogCutoffCm) transmission=1.0;\n"
        "  return transmission;\n"
        "}\n"
        "vec3 ueDecodeHQLightmap(vec3 worldNormal){\n"
        "  vec4 lm0=texture(uLightmapHQ,vLightmapUV0);\n"
        "  vec4 lm1=texture(uLightmapHQ,vLightmapUV1);\n"
        "  float logL=lm0.a+lm1.a*(1.0/255.0)-(0.5/255.0);\n"
        "  logL=logL*vLightmapScale0.w+vLightmapAdd0.w;\n"
        "  vec3 uvw=lm0.rgb*lm0.rgb*vLightmapScale0.rgb+vLightmapAdd0.rgb;\n"
        "  float L=max(exp2(logL)-0.01858136,0.0);\n"
        "  vec4 sh=lm1*vLightmapScale1+vLightmapAdd1;\n"
        "  vec3 ueNormal=normalize(vec3(worldNormal.x,-worldNormal.y,worldNormal.z));\n"
        "  float directionality=max(dot(sh,vec4(ueNormal.yzx,1.0)),0.0);\n"
        "  return max(uvw*(L*directionality),vec3(0.0));\n"
        "}\n"
        "void main(){\n"
        "  vec3 n=surfaceNormal(normalize(vNormal));\n"
        "  float uvTone=0.92+0.08*clamp(vUV.y,0.0,1.0);\n"
        "  vec4 texel=uHasBaseColor!=0?texture(uBaseColor,vUV):vec4(0.56,0.54,0.50,1.0);\n"
        "  float materialAlpha=clamp(texel.a*uMaterialOpacity,0.0,1.0);\n"
        "  if(uMaterialBlendMode<0){ if(uHasBaseColor!=0 && texel.a<0.04) discard; }\n"
        "  else if(uMaterialBlendMode==1 && materialAlpha<uOpacityMaskClip) discard;\n"
        "  else if(uMaterialBlendMode==0) materialAlpha=1.0;\n"
        "  vec3 albedo=texel.rgb*(uMaterialShadingMode<0?uvTone:1.0);\n"
        "  int pbrEnabled=uPbrFlags!=0?1:0;\n"
        "  float roughness=clamp(uPbrParams.x,0.04,1.0);\n"
        "  float metallic=clamp(uPbrParams.y,0.0,1.0);\n"
        "  float specular=clamp(uPbrParams.z,0.0,1.0);\n"
        "  float emissive=max(uPbrParams.w,0.0);\n"
        "  vec3 viewRaw=uCameraPosGame-vWorldPos;\n"
        "  float viewLen2=dot(viewRaw,viewRaw);\n"
        "  vec3 V=viewLen2>1.0e-8?viewRaw*inversesqrt(viewLen2):n;\n"
        "  vec3 f0=mix(vec3(0.08*specular),albedo,metallic);\n"
        "  vec3 Ld=normalize(uDirectionalDirection);\n"
        "  float ndl=max(dot(n,Ld),0.0);\n"
        "  float skyDiffuse=uAmbientWeight*uReflectionParams.z*uReflectionParams.w;\n"
        "  vec3 dynamicLight=vec3(skyDiffuse)+uDirectionalColor*(uDirectionalWeight*ndl);\n"
        "  vec3 localLight=vec3(0.0);\n"
        "  vec3 localSpec=vec3(0.0);\n"
        "  for(int i=0;i<64;++i){\n"
        "    if(i>=uLocalLightCount) break;\n"
        "    vec4 pr=uLocalPosInvRadius[i];\n"
        "    vec3 toLightGame=pr.xyz-vWorldPos;\n"
        "    float gameD2=max(dot(toLightGame,toLightGame),1.0e-8);\n"
        "    vec3 L=toLightGame*inversesqrt(gameD2);\n"
        "    vec3 toLightCm=toLightGame*2.54;\n"
        "    float d2=max(dot(toLightCm,toLightCm),1.0e-4);\n"
        "    float invR=abs(pr.w);\n"
        "    float q=d2*invR*invR;\n"
        "    float radiusMask=clamp(1.0-q*q,0.0,1.0);\n"
        "    radiusMask*=radiusMask;\n"
        "    float spot=1.0;\n"
        "    if(pr.w<0.0){\n"
        "      vec4 dc=uLocalDirCosOuter[i];\n"
        "      float cone=dot(-L,normalize(dc.xyz));\n"
        "      spot=clamp((cone-dc.w)*uLocalColorCone[i].w,0.0,1.0);\n"
        "      spot*=spot;\n"
        "    }\n"
        "    float localNdl=max(dot(n,L),0.0);\n"
        "    float attenuation=(1.0/(d2+1.0))*radiusMask*spot;\n"
        "    vec3 radiance=uLocalColorCone[i].rgb*attenuation;\n"
        "    localLight+=radiance*(localNdl*0.31830988618);\n"
        "    if(pbrEnabled!=0 && localNdl>0.0){\n"
        "      localSpec+=cookTorranceSpec(n,V,L,roughness,f0)*radiance*localNdl;\n"
        "    }\n"
        "  }\n"
        "  dynamicLight+=localLight;\n"
        "  vec3 lit;\n"
        "  if(uMaterialShadingMode==1){\n"
        "    lit=albedo;\n"
        "  }else{\n"
        "    vec3 diffuseLight=(uHasLightmap!=0&&vLightmapEnabled>0.5)?ueDecodeHQLightmap(n):dynamicLight;\n"
        "    lit=albedo*diffuseLight;\n"
        "    if(pbrEnabled!=0){\n"
        "      vec3 diffuse=albedo*diffuseLight*(1.0-metallic);\n"
        "      vec3 directRadiance=uDirectionalColor*uDirectionalWeight;\n"
        "      vec3 directSpec=cookTorranceSpec(n,V,Ld,roughness,f0)*directRadiance*ndl;\n"
        "      lit=diffuse+directSpec+localSpec+albedo*emissive;\n"
        "    }\n"
        "    lit+=ueReflectionIBL(n,V,roughness,f0);\n"
        "  }\n"
        "  float fogT=ueFogTransmission(vWorldPos);\n"
        "  vec3 fogged=lit*fogT+uFogColorMin.rgb*(1.0-fogT);\n"
        "  outColor=vec4(uePavlovLegacyTonemap(fogged),materialAlpha);\n"
        "}\n";

    XzNativeGles3Api *gl = &xz_shadow.gl;
    GLuint vs = 0u;
    GLuint fs = 0u;
    GLint linked = 0;

    if (!XzCompileShader(
            gl, GL_VERTEX_SHADER, vs_source, &vs))
        return 0;

    if (!XzCompileShader(
            gl, GL_FRAGMENT_SHADER, fs_source, &fs)) {
        gl->DeleteShader(vs);
        return 0;
    }

    xz_shadow.static_program =
        gl->CreateProgram();
    if (!xz_shadow.static_program) {
        gl->DeleteShader(vs);
        gl->DeleteShader(fs);
        return 0;
    }

    gl->AttachShader(
        xz_shadow.static_program, vs);
    gl->AttachShader(
        xz_shadow.static_program, fs);
    gl->LinkProgram(
        xz_shadow.static_program);
    gl->GetProgramiv(
        xz_shadow.static_program,
        GL_LINK_STATUS,
        &linked);

    gl->DeleteShader(vs);
    gl->DeleteShader(fs);

    if (!linked)
        return 0;

    xz_shadow.static_view_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uView");
    xz_shadow.static_projection_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uProjection");
    xz_shadow.static_texture_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uBaseColor");
    xz_shadow.static_texture_enabled_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uHasBaseColor");
    xz_shadow.static_normal_texture_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uNormalMap");
    xz_shadow.static_normal_texture_enabled_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uHasNormalMap");
    xz_shadow.static_ambient_weight_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uAmbientWeight");
    xz_shadow.static_directional_weight_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uDirectionalWeight");
    xz_shadow.static_directional_color_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uDirectionalColor");
    xz_shadow.static_directional_direction_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uDirectionalDirection");
    xz_shadow.static_local_light_count_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uLocalLightCount");
    xz_shadow.static_local_pos_inv_radius_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uLocalPosInvRadius[0]");
    xz_shadow.static_local_color_cone_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uLocalColorCone[0]");
    xz_shadow.static_local_dir_cos_outer_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uLocalDirCosOuter[0]");
    xz_shadow.static_camera_pos_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uCameraPosGame");
    xz_shadow.static_fog_primary_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uFogPrimary");
    xz_shadow.static_fog_color_min_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uFogColorMin");
    xz_shadow.static_fog_cutoff_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uFogCutoffCm");
    xz_shadow.static_pbr_params_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uPbrParams");
    xz_shadow.static_pbr_flags_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uPbrFlags");
    xz_shadow.static_material_shading_mode_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uMaterialShadingMode");
    xz_shadow.static_material_blend_mode_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uMaterialBlendMode");
    xz_shadow.static_material_opacity_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uMaterialOpacity");
    xz_shadow.static_opacity_mask_clip_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uOpacityMaskClip");
    xz_shadow.static_reflection_texture_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uReflectionCapture");
    xz_shadow.static_reflection_params_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uReflectionParams");
    xz_shadow.static_reflection_sphere_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uReflectionSphere");
    xz_shadow.static_reflection_offset_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uReflectionCaptureOffset");
    xz_shadow.static_lightmap_texture_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uLightmapHQ");
    xz_shadow.static_lightmap_enabled_loc =
        gl->GetUniformLocation(
            xz_shadow.static_program,
            "uHasLightmap");

    if (xz_shadow.static_view_loc < 0 ||
        xz_shadow.static_projection_loc < 0 ||
        xz_shadow.static_texture_loc < 0 ||
        xz_shadow.static_texture_enabled_loc < 0 ||
        xz_shadow.static_normal_texture_loc < 0 ||
        xz_shadow.static_normal_texture_enabled_loc < 0 ||
        xz_shadow.static_ambient_weight_loc < 0 ||
        xz_shadow.static_directional_weight_loc < 0 ||
        xz_shadow.static_directional_color_loc < 0 ||
        xz_shadow.static_directional_direction_loc < 0 ||
        xz_shadow.static_local_light_count_loc < 0 ||
        xz_shadow.static_local_pos_inv_radius_loc < 0 ||
        xz_shadow.static_local_color_cone_loc < 0 ||
        xz_shadow.static_local_dir_cos_outer_loc < 0 ||
        xz_shadow.static_camera_pos_loc < 0 ||
        xz_shadow.static_fog_primary_loc < 0 ||
        xz_shadow.static_fog_color_min_loc < 0 ||
        xz_shadow.static_fog_cutoff_loc < 0 ||
        xz_shadow.static_pbr_params_loc < 0 ||
        xz_shadow.static_pbr_flags_loc < 0 ||
        xz_shadow.static_material_shading_mode_loc < 0 ||
        xz_shadow.static_material_blend_mode_loc < 0 ||
        xz_shadow.static_material_opacity_loc < 0 ||
        xz_shadow.static_opacity_mask_clip_loc < 0 ||
        xz_shadow.static_reflection_texture_loc < 0 ||
        xz_shadow.static_reflection_params_loc < 0 ||
        xz_shadow.static_reflection_sphere_loc < 0 ||
        xz_shadow.static_reflection_offset_loc < 0 ||
        xz_shadow.static_lightmap_texture_loc < 0 ||
        xz_shadow.static_lightmap_enabled_loc < 0)
        return 0;

    gl->UseProgram(xz_shadow.static_program);
    gl->Uniform1i(
        xz_shadow.static_texture_loc,
        0);
    gl->Uniform1i(
        xz_shadow.static_normal_texture_loc,
        1);
    gl->Uniform1i(
        xz_shadow.static_reflection_texture_loc,
        2);
    gl->Uniform1i(
        xz_shadow.static_lightmap_texture_loc,
        3);
    gl->Uniform1i(
        xz_shadow.static_material_shading_mode_loc,
        -1);
    gl->Uniform1i(
        xz_shadow.static_material_blend_mode_loc,
        -1);
    gl->Uniform1f(
        xz_shadow.static_material_opacity_loc,
        1.0f);
    gl->Uniform1f(
        xz_shadow.static_opacity_mask_clip_loc,
        0.333f);
    gl->UseProgram(0u);

    return gl->GetError() == GL_NO_ERROR;
}

static XzGles3RealTexture *XzFindRealTexture(
    unsigned int legacy_id)
{
    unsigned int i;

    for (i = 0u; i < XZ_TEXTURE_MAX_ENTRIES; ++i) {
        if (xz_shadow.real_textures[i].alive &&
            xz_shadow.real_textures[i].legacy_id ==
                legacy_id)
            return &xz_shadow.real_textures[i];
    }

    return NULL;
}

static XzGles3RealTexture *XzFindFreeRealTexture(void)
{
    unsigned int i;

    for (i = 0u; i < XZ_TEXTURE_MAX_ENTRIES; ++i) {
        if (!xz_shadow.real_textures[i].alive)
            return &xz_shadow.real_textures[i];
    }

    return NULL;
}

static int XzBindRealTexture(
    XzGles3ShadowState *state,
    int legacy_texture_id,
    int *has_real_texture)
{
    XzNativeGles3Api *gl = &xz_shadow.gl;
    XzTextureSnapshot snapshot;
    XzGles3RealTexture *cached;
    GLenum error;
    int created = 0;

    if (has_real_texture)
        *has_real_texture = 0;

    gl->ActiveTexture(GL_TEXTURE0);

    if (legacy_texture_id <= 0 ||
        !XzTextureTap_Resolve(
            (unsigned int)legacy_texture_id,
            &snapshot)) {
        state->real_texture_misses++;
        gl->BindTexture(
            GL_TEXTURE_2D,
            xz_shadow.real_fallback_texture);
        return gl->GetError() == GL_NO_ERROR;
    }

    cached = XzFindRealTexture(snapshot.legacy_id);
    if (!cached) {
        cached = XzFindFreeRealTexture();
        if (!cached) {
            state->real_texture_failures++;
            return 0;
        }

        memset(cached, 0, sizeof(*cached));
        gl->GenTextures(1, &cached->object);
        if (!cached->object) {
            state->real_texture_failures++;
            return 0;
        }

        cached->legacy_id = snapshot.legacy_id;
        cached->alive = 1;
        created = 1;
    }

    gl->BindTexture(GL_TEXTURE_2D, cached->object);

    if (created ||
        cached->revision != snapshot.revision ||
        cached->width != snapshot.width ||
        cached->height != snapshot.height) {
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MIN_FILTER,
            GL_LINEAR);
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_LINEAR);
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_S,
            GL_REPEAT);
        gl->TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_T,
            GL_REPEAT);
        gl->TexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            (GLsizei)snapshot.width,
            (GLsizei)snapshot.height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            snapshot.rgba);

        error = gl->GetError();
        if (error != GL_NO_ERROR) {
            state->real_texture_failures++;
            if (created) {
                gl->DeleteTextures(
                    1, &cached->object);
                memset(cached, 0, sizeof(*cached));
            }
            if (state->last_gl_error == 0u)
                state->last_gl_error =
                    (unsigned int)error;
            return 0;
        }

        cached->width = snapshot.width;
        cached->height = snapshot.height;
        cached->revision = snapshot.revision;

        state->real_texture_uploads++;
        state->real_texture_bytes +=
            (uint64_t)snapshot.bytes;
    }

    state->real_texture_binds++;
    if (has_real_texture)
        *has_real_texture = 1;

    return 1;
}

static void XzDestroyRealTextures(void)
{
    XzNativeGles3Api *gl = &xz_shadow.gl;
    unsigned int i;

    for (i = 0u; i < XZ_TEXTURE_MAX_ENTRIES; ++i) {
        XzGles3RealTexture *cached =
            &xz_shadow.real_textures[i];

        if (cached->alive && cached->object)
            gl->DeleteTextures(1, &cached->object);

        memset(cached, 0, sizeof(*cached));
    }

    if (xz_shadow.real_fallback_texture) {
        gl->DeleteTextures(
            1, &xz_shadow.real_fallback_texture);
        xz_shadow.real_fallback_texture = 0u;
    }
}

static int XzDrawRealGeometry(
    XzGles3ShadowState *state,
    const XzGeometryFrame *geometry,
    int skip_world_batches)
{
    XzNativeGles3Api *gl = &xz_shadow.gl;
    unsigned int i;
    unsigned int kind_mask = 0u;
    /* A visible gameplay world is not eligible for takeover until both
     * alias geometry (view/world models) and BSP surfaces are live. Optional
     * classes are required only when the current frame actually contains them. */
    unsigned int required_kind_mask = 0x3u;
    unsigned int texture_kind_mask = 0u;
    unsigned int required_texture_kind_mask = 0x3u;
    unsigned int texture_misses = 0u;
    unsigned int texture_batches = 0u;
    unsigned int drops;

    if (!state || !geometry ||
        geometry->batch_count == 0u ||
        geometry->vertex_count == 0u ||
        geometry->index_count == 0u)
        return 0;

    drops =
        geometry->dropped_batches +
        geometry->dropped_vertices +
        geometry->dropped_indices;

    state->last_geometry_batches =
        geometry->batch_count;
    state->last_geometry_vertices =
        geometry->vertex_count;
    state->last_geometry_indices =
        geometry->index_count;
    state->last_geometry_drops = drops;
    state->last_effect_batches = geometry->effect_batches;
    state->last_special_batches = geometry->special_batches;
    state->last_sky_batches = geometry->sky_batches;
    state->last_water_batches = geometry->water_batches;

    if (drops != 0u) {
        state->real_geometry_failures++;
        state->real_geometry_ready = 0;
        return 0;
    }

    if (geometry->vertex_count >
            XZ_GEOMETRY_MAX_VERTICES ||
        geometry->index_count >
            XZ_GEOMETRY_MAX_INDICES ||
        geometry->batch_count >
            XZ_GEOMETRY_MAX_BATCHES) {
        state->real_geometry_failures++;
        state->real_geometry_ready = 0;
        return 0;
    }

    state->last_texture_batches = 0u;
    state->last_texture_misses = 0u;
    state->last_material_state_batches = 0u;
    state->last_blended_batches = 0u;
    state->last_lightmap_batches = 0u;
    state->last_alpha_test_batches = 0u;
    state->last_modulate_batches = 0u;
    /*
     * Once the static scene owns world surfaces, this pass only draws the
     * remaining dynamic overlay batches. Material/raster parity for the
     * world was already proven by the full legacy capture before takeover,
     * so do not erase that evidence merely because those world batches are
     * intentionally skipped. Any real draw/texture/geometry failure below
     * still fails the frame and prevents a clean visible-present cutover.
     */
    if (!skip_world_batches)
        state->real_material_state_ready = 0;
    state->last_fog_batches = 0u;
    state->last_cull_batches = 0u;
    state->last_depth_range_batches = 0u;
    state->last_polygon_offset_batches = 0u;
    if (!skip_world_batches)
        state->real_raster_state_ready = 0;

    gl->UseProgram(xz_shadow.real_program);
    gl->Uniform1i(xz_shadow.real_texture_loc, 0);
    gl->BindVertexArray(xz_shadow.real_vao);

    gl->BindBuffer(
        GL_ARRAY_BUFFER,
        xz_shadow.real_vbo);
    gl->BufferSubData(
        GL_ARRAY_BUFFER,
        0,
        (GLsizeiptr)(
            geometry->vertex_count *
            sizeof(XzGeometryVertex)),
        geometry->vertices);

    gl->BindBuffer(
        GL_ELEMENT_ARRAY_BUFFER,
        xz_shadow.real_ibo);
    gl->BufferSubData(
        GL_ELEMENT_ARRAY_BUFFER,
        0,
        (GLsizeiptr)(
            geometry->index_count *
            sizeof(uint32_t)),
        geometry->indices);

    if (gl->GetError() != GL_NO_ERROR) {
        state->real_geometry_failures++;
        state->real_geometry_ready = 0;
        return 0;
    }

    gl->Enable(GL_DEPTH_TEST);
    gl->Disable(GL_BLEND);
    gl->DepthMask(GL_TRUE);
    gl->DepthFunc(GL_LEQUAL);

    for (i = 0u; i < geometry->batch_count; ++i) {
        const XzGeometryBatch *batch =
            &geometry->batches[i];

        if (skip_world_batches &&
            (batch->kind == XZ_GEOMETRY_SURFACE ||
             batch->kind == XZ_GEOMETRY_SPECIAL))
            continue;

        if (batch->kind == XZ_GEOMETRY_SPRITE)
            required_kind_mask |= 4u;
        else if (batch->kind == XZ_GEOMETRY_EFFECT)
            required_kind_mask |= 8u;
        else if (batch->kind == XZ_GEOMETRY_SPECIAL)
            required_kind_mask |= 16u;

        if (batch->vertex_count == 0u ||
            batch->index_count == 0u ||
            batch->first_vertex +
                batch->vertex_count >
                geometry->vertex_count ||
            batch->first_index +
                batch->index_count >
                geometry->index_count) {
            state->real_geometry_failures++;
            state->real_geometry_ready = 0;
            return 0;
        }

        gl->UniformMatrix4fv(
            xz_shadow.real_modelview_loc,
            1,
            GL_FALSE,
            batch->modelview);
        gl->UniformMatrix4fv(
            xz_shadow.real_projection_loc,
            1,
            GL_FALSE,
            batch->projection);
        gl->Uniform1i(
            xz_shadow.real_texture_enabled_loc,
            batch->state.texture_enabled ? 1 : 0);
        gl->Uniform4fv(
            xz_shadow.real_color_loc,
            1,
            batch->state.color);
        gl->Uniform1i(
            xz_shadow.real_texenv_modulate_loc,
            batch->state.texture_env_mode == 0x2100u ? 1 : 0);
        gl->Uniform1i(
            xz_shadow.real_alpha_test_loc,
            batch->state.alpha_test_enabled ? 1 : 0);
        gl->Uniform1i(
            xz_shadow.real_alpha_func_loc,
            XzAlphaFuncCode(batch->state.alpha_func));
        gl->Uniform1f(
            xz_shadow.real_alpha_ref_loc,
            batch->state.alpha_ref);
        gl->Uniform1i(
            xz_shadow.real_fog_enabled_loc,
            batch->state.fog_enabled ? 1 : 0);
        gl->Uniform1f(
            xz_shadow.real_fog_start_loc,
            batch->state.fog_start);
        gl->Uniform1f(
            xz_shadow.real_fog_end_loc,
            batch->state.fog_end);
        gl->Uniform4fv(
            xz_shadow.real_fog_color_loc,
            1,
            batch->state.fog_color);

        {
            int has_real_texture = 0;

            if (batch->state.texture_enabled) {
                texture_batches++;
                if (batch->kind == XZ_GEOMETRY_SPRITE)
                    required_texture_kind_mask |= 4u;

                if (!XzBindRealTexture(
                        state,
                        batch->texture_id,
                        &has_real_texture)) {
                    state->real_geometry_failures++;
                    state->real_geometry_ready = 0;
                    state->real_textures_ready = 0;
                    return 0;
                }

                if (has_real_texture) {
                    if (batch->kind == XZ_GEOMETRY_ALIAS)
                        texture_kind_mask |= 1u;
                    else if (batch->kind == XZ_GEOMETRY_SURFACE)
                        texture_kind_mask |= 2u;
                    else if (batch->kind == XZ_GEOMETRY_SPRITE)
                        texture_kind_mask |= 4u;
                } else {
                    texture_misses++;
                }
            } else {
                gl->ActiveTexture(GL_TEXTURE0);
                gl->BindTexture(
                    GL_TEXTURE_2D,
                    xz_shadow.real_fallback_texture);
            }
        }

        if (batch->state.blend_enabled) {
            gl->Enable(GL_BLEND);
            gl->BlendFunc(
                XzSafeBlendFactor(
                    batch->state.blend_src,
                    GL_SRC_ALPHA),
                XzSafeBlendFactor(
                    batch->state.blend_dst,
                    GL_ONE_MINUS_SRC_ALPHA));
            state->last_blended_batches++;
        } else {
            gl->Disable(GL_BLEND);
        }

        if (batch->state.depth_test_enabled)
            gl->Enable(GL_DEPTH_TEST);
        else
            gl->Disable(GL_DEPTH_TEST);

        gl->DepthMask(
            batch->state.depth_write ? GL_TRUE : GL_FALSE);
        gl->DepthFunc(
            XzSafeDepthFunc(batch->state.depth_func));
        gl->DepthRangef(
            XzClamp01(batch->state.depth_range[0]),
            XzClamp01(batch->state.depth_range[1]));

        if (batch->state.cull_enabled) {
            gl->Enable(GL_CULL_FACE);
            gl->CullFace(
                XzSafeCullFace(batch->state.cull_face));
            gl->FrontFace(
                XzSafeFrontFace(batch->state.front_face));
            state->last_cull_batches++;
        } else {
            gl->Disable(GL_CULL_FACE);
        }

        if (batch->state.polygon_offset_enabled) {
            gl->Enable(GL_POLYGON_OFFSET_FILL);
            gl->PolygonOffset(
                batch->state.polygon_offset_factor,
                batch->state.polygon_offset_units);
            state->last_polygon_offset_batches++;
        } else {
            gl->Disable(GL_POLYGON_OFFSET_FILL);
        }

        if (batch->state.fog_enabled &&
            batch->state.fog_end > batch->state.fog_start)
            state->last_fog_batches++;
        if (XzAbsFloat(batch->state.depth_range[0]) > 0.0001f ||
            XzAbsFloat(batch->state.depth_range[1] - 1.0f) > 0.0001f)
            state->last_depth_range_batches++;

        state->last_material_state_batches++;
        if (batch->state.alpha_test_enabled)
            state->last_alpha_test_batches++;
        if (batch->state.texture_env_mode == 0x2100u)
            state->last_modulate_batches++;
        if (batch->state.blend_enabled &&
            batch->state.blend_src == (unsigned int)GL_DST_COLOR &&
            batch->state.blend_dst == (unsigned int)GL_SRC_COLOR &&
            batch->state.depth_func == (unsigned int)GL_EQUAL)
            state->last_lightmap_batches++;

        gl->DrawElements(
            GL_TRIANGLES,
            (GLsizei)batch->index_count,
            GL_UNSIGNED_INT,
            (const void *)(uintptr_t)(
                batch->first_index *
                sizeof(uint32_t)));

        if (gl->GetError() != GL_NO_ERROR) {
            state->real_geometry_failures++;
            state->real_geometry_ready = 0;
            return 0;
        }

        if (batch->kind == XZ_GEOMETRY_ALIAS)
            kind_mask |= 1u;
        else if (batch->kind == XZ_GEOMETRY_SURFACE)
            kind_mask |= 2u;
        else if (batch->kind == XZ_GEOMETRY_SPRITE)
            kind_mask |= 4u;
        else if (batch->kind == XZ_GEOMETRY_EFFECT)
            kind_mask |= 8u;
        else if (batch->kind == XZ_GEOMETRY_SPECIAL)
            kind_mask |= 16u;

        state->real_geometry_draw_calls++;
    }

    gl->DepthMask(GL_TRUE);
    gl->DepthFunc(GL_LEQUAL);
    gl->DepthRangef(0.0f, 1.0f);
    gl->Disable(GL_BLEND);
    gl->Disable(GL_CULL_FACE);
    gl->Disable(GL_POLYGON_OFFSET_FILL);
    gl->Disable(GL_DEPTH_TEST);

    if (skip_world_batches) {
        state->last_texture_batches =
            texture_batches;
        state->last_texture_misses =
            texture_misses;
        return 1;
    }

    state->real_geometry_submissions++;
    state->real_geometry_vertices +=
        geometry->vertex_count;
    state->real_geometry_indices +=
        geometry->index_count;
    state->real_geometry_kind_mask |= kind_mask;

    state->real_geometry_ready =
        state->real_geometry_failures == 0u &&
        (kind_mask & required_kind_mask) == required_kind_mask;
    if (geometry->effect_batches > 0u &&
        state->real_geometry_failures == 0u &&
        (kind_mask & 0x8u) == 0x8u)
        state->real_effects_ready = 1;
    if (geometry->sky_batches > 0u &&
        state->real_geometry_failures == 0u &&
        (kind_mask & 0x10u) == 0x10u)
        state->real_sky_ready = 1;
    if (geometry->water_batches > 0u &&
        state->real_geometry_failures == 0u &&
        (kind_mask & 0x10u) == 0x10u)
        state->real_water_ready = 1;

    state->last_texture_batches =
        texture_batches;
    state->last_texture_misses =
        texture_misses;
    state->real_texture_kind_mask |=
        texture_kind_mask;
    state->real_textures_ready =
        state->real_texture_failures == 0u &&
        texture_misses == 0u &&
        (texture_batches == 0u ||
         required_texture_kind_mask == 0u ||
         (texture_kind_mask & required_texture_kind_mask) ==
            required_texture_kind_mask);

    state->real_material_state_ready =
        state->real_geometry_failures == 0u &&
        state->last_material_state_batches == geometry->batch_count &&
        state->last_lightmap_batches > 0u;

    state->real_raster_state_ready =
        state->real_geometry_failures == 0u &&
        state->last_material_state_batches == geometry->batch_count;

    if (state->real_geometry_ready &&
        state->real_textures_ready &&
        state->real_material_state_ready &&
        state->real_raster_state_ready &&
        geometry->surface_batches > 0u &&
        geometry->batch_count >= 8u) {
        if (state->real_scene_ready_streak < 1000000u)
            state->real_scene_ready_streak++;
    } else {
        state->real_scene_ready_streak = 0u;
    }

    return 1;
}

static int XzCreateFullscreenProgram(void)
{
    static const char *vs_source =
        "#version 300 es\n"
        "out vec2 vUV;\n"
        "void main(){\n"
        "  vec2 p;\n"
        "  if(gl_VertexID==0) p=vec2(-1.0,-1.0);\n"
        "  else if(gl_VertexID==1) p=vec2(3.0,-1.0);\n"
        "  else p=vec2(-1.0,3.0);\n"
        "  gl_Position=vec4(p,0.0,1.0);\n"
        "  vUV=p*0.5+0.5;\n"
        "}\n";

    static const char *fs_source =
        "#version 300 es\n"
        "precision mediump float;\n"
        "in vec2 vUV;\n"
        "uniform sampler2D uInput0;\n"
        "uniform sampler2D uInput1;\n"
        "uniform int uInputCount;\n"
        "out vec4 outColor;\n"
        "void main(){\n"
        "  vec4 c=texture(uInput0,vUV);\n"
        "  if(uInputCount>1){\n"
        "    float d=texture(uInput1,vUV).r;\n"
        "    c.rgb*=0.75+0.25*d;\n"
        "  }\n"
        "  outColor=c;\n"
        "}\n";

    XzNativeGles3Api *gl = &xz_shadow.gl;
    GLuint vs = 0u;
    GLuint fs = 0u;
    GLint linked = 0;
    GLint input0;
    GLint input1;

    if (!XzCompileShader(
            gl, GL_VERTEX_SHADER, vs_source, &vs))
        return 0;

    if (!XzCompileShader(
            gl, GL_FRAGMENT_SHADER, fs_source, &fs)) {
        gl->DeleteShader(vs);
        return 0;
    }

    xz_shadow.fullscreen_program =
        gl->CreateProgram();
    if (!xz_shadow.fullscreen_program) {
        gl->DeleteShader(vs);
        gl->DeleteShader(fs);
        return 0;
    }

    gl->AttachShader(
        xz_shadow.fullscreen_program, vs);
    gl->AttachShader(
        xz_shadow.fullscreen_program, fs);
    gl->LinkProgram(
        xz_shadow.fullscreen_program);
    gl->GetProgramiv(
        xz_shadow.fullscreen_program,
        GL_LINK_STATUS,
        &linked);

    gl->DeleteShader(vs);
    gl->DeleteShader(fs);

    if (!linked)
        return 0;

    input0 = gl->GetUniformLocation(
        xz_shadow.fullscreen_program,
        "uInput0");
    input1 = gl->GetUniformLocation(
        xz_shadow.fullscreen_program,
        "uInput1");
    xz_shadow.fullscreen_input_count_loc =
        gl->GetUniformLocation(
            xz_shadow.fullscreen_program,
            "uInputCount");

    if (input0 < 0 || input1 < 0 ||
        xz_shadow.fullscreen_input_count_loc < 0)
        return 0;

    gl->UseProgram(
        xz_shadow.fullscreen_program);
    gl->Uniform1i(input0, 0);
    gl->Uniform1i(input1, 1);
    gl->UseProgram(0u);

    return gl->GetError() == GL_NO_ERROR;
}

static int XzMakeShadowCurrent(
    EGLDisplay *previous_display,
    EGLSurface *previous_draw,
    EGLSurface *previous_read,
    EGLContext *previous_context)
{
    *previous_display = eglGetCurrentDisplay();
    *previous_draw = eglGetCurrentSurface(EGL_DRAW);
    *previous_read = eglGetCurrentSurface(EGL_READ);
    *previous_context = eglGetCurrentContext();

    return eglMakeCurrent(
        xz_shadow.display,
        xz_shadow.surface,
        xz_shadow.surface,
        xz_shadow.context) ? 1 : 0;
}

static int XzRestorePrevious(
    EGLDisplay previous_display,
    EGLSurface previous_draw,
    EGLSurface previous_read,
    EGLContext previous_context)
{
    if (previous_display != EGL_NO_DISPLAY &&
        previous_context != EGL_NO_CONTEXT) {
        return eglMakeCurrent(
            previous_display,
            previous_draw,
            previous_read,
            previous_context) ? 1 : 0;
    }

    return eglMakeCurrent(
        xz_shadow.display,
        EGL_NO_SURFACE,
        EGL_NO_SURFACE,
        EGL_NO_CONTEXT) ? 1 : 0;
}


static int XzGlHasExtensionToken(
    const char *extensions,
    const char *wanted)
{
    const char *at;
    size_t wanted_bytes;

    if (!extensions || !wanted || !wanted[0])
        return 0;

    wanted_bytes = strlen(wanted);
    at = extensions;

    while ((at = strstr(at, wanted)) != NULL) {
        const char before =
            at == extensions ? ' ' : at[-1];
        const char after =
            at[wanted_bytes];

        if ((before == ' ' || before == '\t' || before == '\n') &&
            (after == '\0' || after == ' ' ||
             after == '\t' || after == '\n'))
            return 1;

        at += wanted_bytes;
    }

    return 0;
}

static int XzGlVersionAtLeast32(
    const char *version)
{
    int major = 0;
    int minor = 0;

    if (!version)
        return 0;

    if (sscanf(
            version,
            "OpenGL ES %d.%d",
            &major,
            &minor) != 2)
        return 0;

    return major > 3 ||
        (major == 3 && minor >= 2);
}

static int XzStaticAstcSupported(void)
{
    const char *version;
    const char *extensions;

    if (!xz_shadow.gl.GetString)
        return 0;

    version =
        (const char *)xz_shadow.gl.GetString(
            GL_VERSION);
    extensions =
        (const char *)xz_shadow.gl.GetString(
            GL_EXTENSIONS);

    if (XzGlVersionAtLeast32(version))
        return 1;

    return
        XzGlHasExtensionToken(
            extensions,
            "GL_KHR_texture_compression_astc_ldr") ||
        XzGlHasExtensionToken(
            extensions,
            "GL_KHR_texture_compression_astc_hdr");
}

static int XzUploadStaticNativeMaterialTextures(
    const XzStaticSceneRuntimeState *scene,
    XzGles3ShadowState *state)
{
    const XzMaterialLibraryView *library;
    const XzMaterialInstanceBindingView *instances;
    uint32_t texture_index;
    uint64_t gpu_bytes = 0u;

    if (!scene || !state)
        return 0;

    library =
        XzStaticSceneRuntime_MaterialLibrary(scene);
    instances =
        XzStaticSceneRuntime_MaterialInstances(scene);

    if (!library)
        return 1;

    if (!instances ||
        library->material_count == 0u ||
        library->texture_asset_count == 0u ||
        instances->material_count !=
            library->material_count ||
        xz_shadow.static_textures ||
        xz_shadow.static_texture_count != 0u ||
        !xz_shadow.gl.CompressedTexImage2D ||
        !XzStaticAstcSupported())
        return 0;

    xz_shadow.static_textures =
        (XzGles3StaticTexture *)calloc(
            library->texture_asset_count,
            sizeof(*xz_shadow.static_textures));
    if (!xz_shadow.static_textures)
        return 0;

    xz_shadow.static_texture_count =
        library->texture_asset_count;

    for (texture_index = 0u;
         texture_index < library->texture_asset_count;
         ++texture_index) {
        XzStaticNativeTextureResource source;
        state->static_scene_upload_failure_texture_index =
            texture_index;
        XzXztxGpuFormat format;
        XzXztxGpuStatus gpu_status;
        XzGles3StaticTexture *dest =
            &xz_shadow.static_textures[texture_index];
        uint64_t expected_payload = 0u;
        uint32_t mip_index;

        memset(&source, 0, sizeof(source));

        if (!XzStaticSceneRuntime_LoadMaterialTexture(
                scene,
                texture_index,
                &source))
            goto fail;

        gpu_status =
            XzXztxGpuFormat_Resolve(
                &source.texture,
                &format);
        if (gpu_status != XZ_XZTX_GPU_OK)
            goto fail_source;

        gpu_status =
            XzXztxGpuFormat_ValidatePayload(
                &source.texture,
                &format,
                &expected_payload);
        if (gpu_status != XZ_XZTX_GPU_OK ||
            expected_payload == 0u)
            goto fail_source;

        xz_shadow.gl.GenTextures(
            1,
            &dest->object);
        if (!dest->object)
            goto fail_source;

        xz_shadow.gl.ActiveTexture(GL_TEXTURE0);
        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D,
            dest->object);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MIN_FILTER,
            source.texture.mip_count > 1u
                ? GL_LINEAR_MIPMAP_LINEAR
                : GL_LINEAR);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_LINEAR);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_S,
            GL_REPEAT);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_T,
            GL_REPEAT);

        for (mip_index = 0u;
             mip_index < source.texture.mip_count;
             ++mip_index) {
            XzXztextureMip mip;
            state->static_scene_upload_failure_mip_index =
                mip_index;
            size_t mip_bytes = 0u;
            const void *payload =
                XzXztexture_MipData(
                    &source.texture,
                    mip_index,
                    &mip_bytes);

            if (!payload ||
                !XzXztexture_Mip(
                    &source.texture,
                    mip_index,
                    &mip) ||
                mip.depth != 1u ||
                mip_bytes !=
                    (size_t)mip.payload_bytes ||
                mip.payload_bytes >
                    (uint32_t)INT32_MAX)
                goto fail_source;

            xz_shadow.gl.CompressedTexImage2D(
                GL_TEXTURE_2D,
                (GLint)mip_index,
                (GLenum)format.gl_internal_format,
                (GLsizei)mip.width,
                (GLsizei)mip.height,
                0,
                (GLsizei)mip.payload_bytes,
                payload);

            if (xz_shadow.gl.GetError() !=
                    GL_NO_ERROR)
                goto fail_source;
        }

        dest->width =
            source.texture.width;
        dest->height =
            source.texture.height;
        dest->flags =
            source.texture.flags;
        dest->gpu_bytes =
            expected_payload;
        dest->alive = 1;
        gpu_bytes += expected_payload;

        XzStaticSceneRuntime_ReleaseMaterialTexture(
            &source);
        continue;

fail_source:
        XzStaticSceneRuntime_ReleaseMaterialTexture(
            &source);
        goto fail;
    }

    xz_shadow.gl.BindTexture(
        GL_TEXTURE_2D,
        0u);
    xz_shadow.gl.ActiveTexture(GL_TEXTURE0);

    state->static_scene_upload_failure_texture_index =
        0xffffffffu;
    state->static_scene_upload_failure_mip_index =
        0xffffffffu;
    state->static_scene_gpu_texture_bytes =
        gpu_bytes;
    state->static_scene_gpu_textures =
        library->texture_asset_count;
    state->static_scene_material_bindings =
        instances->binding_count;
    state->static_scene_material_mapped_bindings =
        instances->binding_count;
    state->static_scene_material_ready =
        state->static_scene_gpu_textures ==
            library->texture_asset_count &&
        state->static_scene_material_bindings > 0u &&
        instances->material_count ==
            library->material_count;

    return state->static_scene_material_ready;

fail:
    xz_shadow.gl.BindTexture(
        GL_TEXTURE_2D,
        0u);
    xz_shadow.gl.ActiveTexture(GL_TEXTURE0);
    return 0;
}


static int XzUploadStaticReflection(
    const XzStaticSceneRuntimeState *scene,
    XzGles3ShadowState *state)
{
    const XzReflectionCaptureView *capture;
    size_t offset = 0u;
    uint32_t mip;

    if (!scene || !state)
        return 0;

    capture =
        XzStaticSceneRuntime_ReflectionCapture(scene);

    if (!capture)
        return strcmp(
            scene->map_id,
            "xziel_nacht_bo3") != 0;

    if (!capture->payload ||
        capture->cubemap_size == 0u ||
        capture->mip_count == 0u ||
        capture->face_count != 6u ||
        capture->pixel_format !=
            XZ_REFLECTION_FORMAT_RGBA16F ||
        capture->bytes_per_texel != 8u)
        return 0;

    xz_shadow.gl.GenTextures(
        1,
        &xz_shadow.static_reflection_cubemap);
    if (!xz_shadow.static_reflection_cubemap)
        return 0;

    xz_shadow.gl.ActiveTexture(GL_TEXTURE2);
    xz_shadow.gl.BindTexture(
        GL_TEXTURE_CUBE_MAP,
        xz_shadow.static_reflection_cubemap);
    xz_shadow.gl.TexParameteri(
        GL_TEXTURE_CUBE_MAP,
        GL_TEXTURE_MIN_FILTER,
        GL_LINEAR_MIPMAP_LINEAR);
    xz_shadow.gl.TexParameteri(
        GL_TEXTURE_CUBE_MAP,
        GL_TEXTURE_MAG_FILTER,
        GL_LINEAR);
    xz_shadow.gl.TexParameteri(
        GL_TEXTURE_CUBE_MAP,
        GL_TEXTURE_WRAP_S,
        GL_CLAMP_TO_EDGE);
    xz_shadow.gl.TexParameteri(
        GL_TEXTURE_CUBE_MAP,
        GL_TEXTURE_WRAP_T,
        GL_CLAMP_TO_EDGE);
    xz_shadow.gl.TexParameteri(
        GL_TEXTURE_CUBE_MAP,
        GL_TEXTURE_WRAP_R,
        GL_CLAMP_TO_EDGE);

    for (mip = 0u;
         mip < capture->mip_count;
         ++mip) {
        uint32_t edge =
            capture->cubemap_size >> mip;
        size_t face_bytes =
            (size_t)edge *
            (size_t)edge *
            (size_t)capture->bytes_per_texel;
        uint32_t face;

        if (edge == 0u ||
            face_bytes == 0u)
            return 0;

        for (face = 0u;
             face < capture->face_count;
             ++face) {
            size_t face_offset =
                offset +
                (size_t)face * face_bytes;

            if (face_offset >
                    capture->payload_bytes ||
                face_bytes >
                    capture->payload_bytes -
                        face_offset)
                return 0;

            xz_shadow.gl.TexImage2D(
                GL_TEXTURE_CUBE_MAP_POSITIVE_X +
                    (GLenum)face,
                (GLint)mip,
                GL_RGBA16F,
                (GLsizei)edge,
                (GLsizei)edge,
                0,
                GL_RGBA,
                GL_HALF_FLOAT,
                capture->payload + face_offset);
        }

        offset +=
            face_bytes *
            (size_t)capture->face_count;

        if (xz_shadow.gl.GetError() !=
                GL_NO_ERROR)
            return 0;
    }

    xz_shadow.gl.BindTexture(
        GL_TEXTURE_CUBE_MAP,
        0u);
    xz_shadow.gl.ActiveTexture(GL_TEXTURE0);

    if (offset != capture->payload_bytes ||
        xz_shadow.gl.GetError() != GL_NO_ERROR)
        return 0;

    state->static_scene_reflection_gpu_bytes =
        (uint64_t)capture->payload_bytes;
    state->static_scene_reflection_size =
        capture->cubemap_size;
    state->static_scene_reflection_mips =
        capture->mip_count;
    state->static_scene_reflection_average_brightness =
        capture->average_brightness;
    state->static_scene_reflection_brightness =
        capture->brightness;

    if (capture->asset_version >= 2u &&
        capture->shape ==
            XZ_REFLECTION_SHAPE_SPHERE &&
        capture->influence_radius_meters > 0.0f) {
        uint32_t axis;
        for (axis = 0u; axis < 3u; ++axis) {
            state->static_scene_reflection_position_meters[axis] =
                capture->capture_position_meters[axis];
            state->static_scene_reflection_offset_meters[axis] =
                capture->capture_offset_meters[axis];
        }
        state->static_scene_reflection_radius_meters =
            capture->influence_radius_meters;
        state->static_scene_reflection_sphere_ready = 1;
    }

    state->static_scene_reflection_ready = 1;
    return 1;
}



static unsigned char XzBcExpand5(uint32_t value)
{
    return (unsigned char)((value << 3u) | (value >> 2u));
}

static unsigned char XzBcExpand6(uint32_t value)
{
    return (unsigned char)((value << 2u) | (value >> 4u));
}

static int XzDecodeBc3Rgba8(
    const unsigned char *source,
    size_t source_bytes,
    uint32_t width,
    uint32_t height,
    unsigned char *rgba,
    size_t rgba_bytes)
{
    const uint32_t blocks_x =
        (width + 3u) / 4u;
    const uint32_t blocks_y =
        (height + 3u) / 4u;
    const uint64_t expected_source =
        (uint64_t)blocks_x *
        (uint64_t)blocks_y *
        16u;
    const uint64_t expected_rgba =
        (uint64_t)width *
        (uint64_t)height *
        4u;
    uint32_t by;

    if (!source ||
        !rgba ||
        width == 0u ||
        height == 0u ||
        expected_source > source_bytes ||
        expected_rgba > rgba_bytes)
        return 0;

    for (by = 0u; by < blocks_y; ++by) {
        uint32_t bx;

        for (bx = 0u; bx < blocks_x; ++bx) {
            const unsigned char *block =
                source +
                ((size_t)by * blocks_x + bx) * 16u;
            unsigned char alpha[8];
            unsigned char color[4][3];
            uint64_t alpha_bits = 0u;
            uint32_t color_bits;
            uint16_t c0;
            uint16_t c1;
            uint32_t i;

            alpha[0] = block[0];
            alpha[1] = block[1];

            if (alpha[0] > alpha[1]) {
                alpha[2] = (unsigned char)(
                    (6u * alpha[0] + 1u * alpha[1]) / 7u);
                alpha[3] = (unsigned char)(
                    (5u * alpha[0] + 2u * alpha[1]) / 7u);
                alpha[4] = (unsigned char)(
                    (4u * alpha[0] + 3u * alpha[1]) / 7u);
                alpha[5] = (unsigned char)(
                    (3u * alpha[0] + 4u * alpha[1]) / 7u);
                alpha[6] = (unsigned char)(
                    (2u * alpha[0] + 5u * alpha[1]) / 7u);
                alpha[7] = (unsigned char)(
                    (1u * alpha[0] + 6u * alpha[1]) / 7u);
            } else {
                alpha[2] = (unsigned char)(
                    (4u * alpha[0] + 1u * alpha[1]) / 5u);
                alpha[3] = (unsigned char)(
                    (3u * alpha[0] + 2u * alpha[1]) / 5u);
                alpha[4] = (unsigned char)(
                    (2u * alpha[0] + 3u * alpha[1]) / 5u);
                alpha[5] = (unsigned char)(
                    (1u * alpha[0] + 4u * alpha[1]) / 5u);
                alpha[6] = 0u;
                alpha[7] = 255u;
            }

            for (i = 0u; i < 6u; ++i)
                alpha_bits |=
                    (uint64_t)block[2u + i] <<
                    (8u * i);

            c0 =
                (uint16_t)(
                    (uint16_t)block[8] |
                    ((uint16_t)block[9] << 8u));
            c1 =
                (uint16_t)(
                    (uint16_t)block[10] |
                    ((uint16_t)block[11] << 8u));

            color[0][0] =
                XzBcExpand5((c0 >> 11u) & 31u);
            color[0][1] =
                XzBcExpand6((c0 >> 5u) & 63u);
            color[0][2] =
                XzBcExpand5(c0 & 31u);
            color[1][0] =
                XzBcExpand5((c1 >> 11u) & 31u);
            color[1][1] =
                XzBcExpand6((c1 >> 5u) & 63u);
            color[1][2] =
                XzBcExpand5(c1 & 31u);

            for (i = 0u; i < 3u; ++i) {
                color[2][i] = (unsigned char)(
                    (2u * color[0][i] +
                     color[1][i]) / 3u);
                color[3][i] = (unsigned char)(
                    (color[0][i] +
                     2u * color[1][i]) / 3u);
            }

            color_bits =
                ((uint32_t)block[12]) |
                ((uint32_t)block[13] << 8u) |
                ((uint32_t)block[14] << 16u) |
                ((uint32_t)block[15] << 24u);

            for (i = 0u; i < 16u; ++i) {
                const uint32_t local_x =
                    i & 3u;
                const uint32_t local_y =
                    i >> 2u;
                const uint32_t x =
                    bx * 4u + local_x;
                const uint32_t y =
                    by * 4u + local_y;
                const uint32_t color_index =
                    (color_bits >> (2u * i)) & 3u;
                const uint32_t alpha_index =
                    (uint32_t)(
                        (alpha_bits >> (3u * i)) &
                        7u);

                if (x < width && y < height) {
                    unsigned char *pixel =
                        rgba +
                        ((size_t)y * width + x) * 4u;
                    pixel[0] =
                        color[color_index][0];
                    pixel[1] =
                        color[color_index][1];
                    pixel[2] =
                        color[color_index][2];
                    pixel[3] =
                        alpha[alpha_index];
                }
            }
        }
    }

    return 1;
}

static int XzUploadStaticHQLightmaps(
    const XzStaticSceneRuntimeState *scene,
    XzGles3ShadowState *state)
{
    const XzLightmapTextureView *lightmaps =
        XzStaticSceneRuntime_Lightmaps(scene);
    unsigned char *used = NULL;
    unsigned char *compressed = NULL;
    unsigned char *rgba = NULL;
    size_t compressed_bytes = 0u;
    size_t rgba_bytes = 0u;
    uint32_t texture_index;
    uint32_t batch_index;
    uint32_t uploaded = 0u;
    uint64_t uploaded_bytes = 0u;

    if (state) {
        state->static_scene_lightmap_upload_stage = 1u;
        state->static_scene_lightmap_upload_texture_index = 0xffffffffu;
        state->static_scene_lightmap_upload_mip = 0xffffffffu;
        state->static_scene_lightmap_upload_width = 0u;
        state->static_scene_lightmap_upload_height = 0u;
        state->static_scene_lightmap_upload_gl_error = GL_NO_ERROR;
        state->static_scene_lightmap_upload_reason = 0u;
        state->static_scene_lightmap_upload_read_status = 0u;
        state->static_scene_lightmap_upload_mip_bytes = 0u;
        state->static_scene_lightmap_upload_decoded_bytes = 0u;
    }

    if (!scene ||
        !state ||
        !lightmaps ||
        !lightmaps->file_open ||
        !xz_shadow.static_lightmap_draw_plan_ready ||
        !xz_shadow.static_lightmap_draw_plan.batches ||
        lightmaps->texture_count == 0u)
        return 0;

    used = (unsigned char *)calloc(
        lightmaps->texture_count,
        1u);
    xz_shadow.static_lightmap_textures =
        (XzGles3StaticTexture *)calloc(
            lightmaps->texture_count,
            sizeof(*xz_shadow.static_lightmap_textures));
    if (!used ||
        !xz_shadow.static_lightmap_textures)
        goto fail;

    xz_shadow.static_lightmap_texture_count =
        lightmaps->texture_count;
    state->static_scene_lightmap_upload_stage = 2u;

    for (batch_index = 0u;
         batch_index <
            xz_shadow.static_lightmap_draw_plan.batch_count;
         ++batch_index) {
        const XzStaticSceneLightmapBatch *batch =
            XzStaticSceneLightmapDrawPlan_Batch(
                &xz_shadow.static_lightmap_draw_plan,
                batch_index);

        if (!batch)
            goto fail;
        if (!batch->mapped)
            continue;
        if (batch->light_texture[0] >=
            lightmaps->texture_count)
            goto fail;

        used[batch->light_texture[0]] = 1u;
    }

    state->static_scene_lightmap_upload_stage = 3u;

    for (texture_index = 0u;
         texture_index < lightmaps->texture_count;
         ++texture_index) {
        XzLightmapTextureRecord texture;
        XzGles3StaticTexture *dest;
        uint32_t start_mip = 0u;
        uint32_t relative_mip;
        uint32_t gpu_level = 0u;

        if (!used[texture_index])
            continue;

        state->static_scene_lightmap_upload_stage = 4u;
        state->static_scene_lightmap_upload_texture_index =
            texture_index;
        state->static_scene_lightmap_upload_mip = 0xffffffffu;
        state->static_scene_lightmap_upload_width = 0u;
        state->static_scene_lightmap_upload_height = 0u;

        if (!XzLightmapTexture_Texture(
                lightmaps,
                texture_index,
                &texture) ||
            texture.format != XZ_XZLT_FORMAT_BC3 ||
            texture.width == 0u ||
            texture.height == 0u ||
            texture.mip_count == 0u)
            goto fail;

        while (start_mip + 1u <
                   texture.mip_count &&
               ((texture.width >> start_mip) > 512u ||
                (texture.height >> start_mip) > 512u))
            start_mip++;

        dest =
            &xz_shadow.static_lightmap_textures[
                texture_index];

        xz_shadow.gl.GenTextures(
            1,
            &dest->object);
        if (!dest->object)
            goto fail;

        xz_shadow.gl.ActiveTexture(GL_TEXTURE3);
        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D,
            dest->object);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MIN_FILTER,
            GL_LINEAR_MIPMAP_LINEAR);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_LINEAR);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_S,
            GL_CLAMP_TO_EDGE);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_T,
            GL_CLAMP_TO_EDGE);

        dest->gpu_bytes = 0u;

        for (relative_mip = start_mip;
             relative_mip < texture.mip_count;
             ++relative_mip, ++gpu_level) {
            XzLightmapMipRecord mip;
            XzLightmapTextureStatus read_status;
            const uint64_t decoded_bytes =
                (uint64_t)(
                    (texture.width >> relative_mip)
                        ? (texture.width >> relative_mip)
                        : 1u) *
                (uint64_t)(
                    (texture.height >> relative_mip)
                        ? (texture.height >> relative_mip)
                        : 1u) *
                4u;
            uint32_t expected_width =
                texture.width >> relative_mip;
            uint32_t expected_height =
                texture.height >> relative_mip;

            if (expected_width == 0u)
                expected_width = 1u;
            if (expected_height == 0u)
                expected_height = 1u;

            state->static_scene_lightmap_upload_stage = 5u;
            state->static_scene_lightmap_upload_texture_index =
                texture_index;
            state->static_scene_lightmap_upload_mip =
                relative_mip;
            state->static_scene_lightmap_upload_width =
                expected_width;
            state->static_scene_lightmap_upload_height =
                expected_height;
            state->static_scene_lightmap_upload_reason = 0u;
            state->static_scene_lightmap_upload_read_status = 0u;
            state->static_scene_lightmap_upload_mip_bytes = 0u;
            state->static_scene_lightmap_upload_decoded_bytes =
                decoded_bytes;

            if (!XzLightmapTexture_Mip(
                    lightmaps,
                    texture.first_mip +
                        relative_mip,
                    &mip)) {
                state->static_scene_lightmap_upload_reason = 1u;
                goto fail;
            }

            state->static_scene_lightmap_upload_mip_bytes =
                mip.bytes;

            /*
             * BC-compressed mip tails can retain block-aligned physical
             * dimensions (minimum 4x4) even after the logical GLES mip has
             * reached 2x2 or 1x1. The payload is still one valid BC3 block.
             * Validate that the stored record covers the logical mip, but
             * decode/upload only the logical dimensions so GLES receives a
             * complete halving mip chain.
             */
            if (mip.bytes == 0u ||
                mip.width < expected_width ||
                mip.height < expected_height ||
                mip.width >
                    (expected_width < 4u ? 4u : expected_width) ||
                mip.height >
                    (expected_height < 4u ? 4u : expected_height) ||
                decoded_bytes > SIZE_MAX) {
                state->static_scene_lightmap_upload_reason = 2u;
                goto fail;
            }

            if ((size_t)mip.bytes >
                compressed_bytes) {
                unsigned char *grown =
                    (unsigned char *)realloc(
                        compressed,
                        (size_t)mip.bytes);
                if (!grown) {
                    state->static_scene_lightmap_upload_reason = 3u;
                    goto fail;
                }
                compressed = grown;
                compressed_bytes =
                    (size_t)mip.bytes;
            }

            if ((size_t)decoded_bytes >
                rgba_bytes) {
                unsigned char *grown =
                    (unsigned char *)realloc(
                        rgba,
                        (size_t)decoded_bytes);
                if (!grown) {
                    state->static_scene_lightmap_upload_reason = 4u;
                    goto fail;
                }
                rgba = grown;
                rgba_bytes =
                    (size_t)decoded_bytes;
            }

            read_status =
                XzLightmapTexture_ReadMip(
                    (XzLightmapTextureView *)lightmaps,
                    texture_index,
                    relative_mip,
                    compressed,
                    compressed_bytes,
                    NULL);
            state->static_scene_lightmap_upload_read_status =
                (unsigned int)read_status;
            if (read_status != XZ_XZLT_OK) {
                state->static_scene_lightmap_upload_reason = 5u;
                goto fail;
            }

            if (!XzDecodeBc3Rgba8(
                    compressed,
                    (size_t)mip.bytes,
                    expected_width,
                    expected_height,
                    rgba,
                    (size_t)decoded_bytes)) {
                state->static_scene_lightmap_upload_reason = 6u;
                goto fail;
            }

            state->static_scene_lightmap_upload_stage = 6u;

            xz_shadow.gl.TexImage2D(
                GL_TEXTURE_2D,
                (GLint)gpu_level,
                GL_RGBA8,
                (GLsizei)expected_width,
                (GLsizei)expected_height,
                0,
                GL_RGBA,
                GL_UNSIGNED_BYTE,
                rgba);

            {
                const GLenum upload_error =
                    xz_shadow.gl.GetError();
                state->static_scene_lightmap_upload_stage = 7u;
                state->static_scene_lightmap_upload_gl_error =
                    (unsigned int)upload_error;
                if (upload_error != GL_NO_ERROR)
                    goto fail;
            }

            dest->gpu_bytes +=
                decoded_bytes;
            uploaded_bytes +=
                decoded_bytes;

            if (gpu_level == 0u) {
                dest->width = expected_width;
                dest->height = expected_height;
            }
        }

        dest->alive = 1;
        uploaded++;
    }

    state->static_scene_lightmap_upload_stage = 8u;

    xz_shadow.gl.BindTexture(
        GL_TEXTURE_2D,
        0u);
    xz_shadow.gl.ActiveTexture(GL_TEXTURE0);

    free(compressed);
    free(rgba);
    free(used);

    state->static_scene_gpu_lightmap_textures =
        uploaded;
    state->static_scene_gpu_lightmap_bytes =
        uploaded_bytes;
    state->static_scene_lightmap_shader_ready =
        uploaded == 87u &&
        uploaded_bytes == 120323980u;

    {
        const GLenum final_error =
            xz_shadow.gl.GetError();
        state->static_scene_lightmap_upload_gl_error =
            (unsigned int)final_error;
        if (state->static_scene_lightmap_shader_ready &&
            final_error == GL_NO_ERROR) {
            state->static_scene_lightmap_upload_stage = 9u;
            return 1;
        }
    }

fail:
    if (state &&
        state->static_scene_lightmap_upload_gl_error ==
            GL_NO_ERROR) {
        state->static_scene_lightmap_upload_gl_error =
            (unsigned int)xz_shadow.gl.GetError();
    }
    free(compressed);
    free(rgba);
    free(used);
    xz_shadow.gl.ActiveTexture(GL_TEXTURE0);
    return 0;
}

static int XzBuildStaticLightmapInstanceVbo(
    const XzStaticSceneRuntimeState *scene)
{
    const XzLightmapBindingView *bindings =
        XzStaticSceneRuntime_LightmapBindings(scene);
    float *params = NULL;
    uint64_t float_count;
    uint32_t grouped_index;

    if (!scene ||
        !bindings ||
        !bindings->data ||
        !xz_shadow.static_lightmap_draw_plan_ready ||
        xz_shadow.static_lightmap_draw_plan.instance_count !=
            bindings->instance_count)
        return 0;

    float_count =
        (uint64_t)bindings->instance_count *
        XZ_STATIC_LIGHTMAP_INSTANCE_FLOATS;
    if (float_count >
        (uint64_t)(SIZE_MAX / sizeof(float)))
        return 0;

    params = (float *)calloc(
        (size_t)float_count,
        sizeof(float));
    if (!params)
        return 0;

    for (grouped_index = 0u;
         grouped_index < bindings->instance_count;
         ++grouped_index) {
        const uint32_t source_index =
            XzStaticSceneLightmapDrawPlan_SourceInstance(
                &xz_shadow.static_lightmap_draw_plan,
                grouped_index);
        XzLightmapBindingRecord binding;
        float *out =
            params +
            (size_t)grouped_index *
                XZ_STATIC_LIGHTMAP_INSTANCE_FLOATS;
        unsigned int i;

        if (source_index == UINT32_MAX ||
            !XzLightmapBinding_Record(
                bindings,
                source_index,
                &binding))
            goto fail;

        if ((binding.flags &
             XZ_XZLB_FLAG_MAPPED) != 0u) {
            out[0] =
                binding.lightmap_coordinate_scale[0];
            out[1] =
                binding.lightmap_coordinate_scale[1];
            out[2] =
                binding.lightmap_coordinate_bias[0];
            out[3] =
                binding.lightmap_coordinate_bias[1];

            for (i = 0u; i < 4u; ++i) {
                out[4u + i] =
                    binding.lightmap_scale_vectors[i];
                out[8u + i] =
                    binding.lightmap_add_vectors[i];
                out[12u + i] =
                    binding.lightmap_scale_vectors[4u + i];
                out[16u + i] =
                    binding.lightmap_add_vectors[4u + i];
            }

            out[20] =
                (float)binding.uv_channel;
            out[21] = 1.0f;
        } else {
            out[20] = 0.0f;
            out[21] = 0.0f;
        }
    }

    xz_shadow.gl.GenBuffers(
        1,
        &xz_shadow.static_lightmap_instance_vbo);
    if (!xz_shadow.static_lightmap_instance_vbo)
        goto fail;

    xz_shadow.gl.BindBuffer(
        GL_ARRAY_BUFFER,
        xz_shadow.static_lightmap_instance_vbo);
    xz_shadow.gl.BufferData(
        GL_ARRAY_BUFFER,
        (GLsizeiptr)(
            float_count *
            sizeof(float)),
        params,
        GL_STATIC_DRAW);

    free(params);
    return
        xz_shadow.gl.GetError() ==
            GL_NO_ERROR;

fail:
    free(params);
    return 0;
}

static int XzBindStaticMatrixInstanceRange(
    XzGles3StaticMesh *mesh,
    uint32_t first_grouped_instance)
{
    uint32_t column;

    if (!mesh ||
        !mesh->vao ||
        !xz_shadow.static_instance_vbo)
        return 0;

    xz_shadow.gl.BindVertexArray(
        mesh->vao);

    xz_shadow.gl.BindBuffer(
        GL_ARRAY_BUFFER,
        xz_shadow.static_instance_vbo);

    for (column = 0u;
         column < 4u;
         ++column) {
        const GLuint location =
            (GLuint)(5u + column);
        const uintptr_t byte_offset =
            (uintptr_t)(
                ((uint64_t)first_grouped_instance *
                     16u +
                 (uint64_t)column * 4u) *
                sizeof(float));

        xz_shadow.gl.EnableVertexAttribArray(
            location);
        xz_shadow.gl.VertexAttribPointer(
            location,
            4,
            GL_FLOAT,
            GL_FALSE,
            (GLsizei)(16u * sizeof(float)),
            (const void *)byte_offset);
        xz_shadow.gl.VertexAttribDivisor(
            location,
            1u);
    }

    return
        xz_shadow.gl.GetError() ==
            GL_NO_ERROR;
}

static int XzBindStaticInstanceRange(
    XzGles3StaticMesh *mesh,
    uint32_t first_grouped_instance)
{
    uint32_t slot;

    if (!xz_shadow.static_lightmap_instance_vbo ||
        !XzBindStaticMatrixInstanceRange(
            mesh,
            first_grouped_instance))
        return 0;

    xz_shadow.gl.BindBuffer(
        GL_ARRAY_BUFFER,
        xz_shadow.static_lightmap_instance_vbo);

    for (slot = 0u;
         slot < 6u;
         ++slot) {
        const GLuint location =
            (GLuint)(9u + slot);
        const uintptr_t byte_offset =
            (uintptr_t)(
                ((uint64_t)first_grouped_instance *
                     XZ_STATIC_LIGHTMAP_INSTANCE_FLOATS +
                 (uint64_t)slot * 4u) *
                sizeof(float));

        xz_shadow.gl.EnableVertexAttribArray(
            location);
        xz_shadow.gl.VertexAttribPointer(
            location,
            4,
            GL_FLOAT,
            GL_FALSE,
            (GLsizei)(
                XZ_STATIC_LIGHTMAP_INSTANCE_FLOATS *
                sizeof(float)),
            (const void *)byte_offset);
        xz_shadow.gl.VertexAttribDivisor(
            location,
            1u);
    }

    return
        xz_shadow.gl.GetError() ==
            GL_NO_ERROR;
}

static void XzDestroyStaticSceneCurrent(
    XzGles3ShadowState *state)
{
    uint32_t i;

    if (xz_shadow.static_reflection_cubemap) {
        xz_shadow.gl.DeleteTextures(
            1,
            &xz_shadow.static_reflection_cubemap);
        xz_shadow.static_reflection_cubemap = 0u;
    }

    if (xz_shadow.static_lightmap_textures) {
        for (i = 0u;
             i < xz_shadow.static_lightmap_texture_count;
             ++i) {
            if (xz_shadow.static_lightmap_textures[i].object)
                xz_shadow.gl.DeleteTextures(
                    1,
                    &xz_shadow.static_lightmap_textures[i].object);
        }
        free(xz_shadow.static_lightmap_textures);
    }
    xz_shadow.static_lightmap_textures = NULL;
    xz_shadow.static_lightmap_texture_count = 0u;

    free(xz_shadow.static_native_materials);
    xz_shadow.static_native_materials = NULL;
    xz_shadow.static_native_material_count = 0u;

    free(xz_shadow.static_material_batch_offsets);
    xz_shadow.static_material_batch_offsets = NULL;
    free(xz_shadow.static_material_batch_materials);
    xz_shadow.static_material_batch_materials = NULL;
    xz_shadow.static_material_batch_binding_count = 0u;
    xz_shadow.static_native_material_ready = 0;

    if (xz_shadow.static_textures) {
        for (i = 0u;
             i < xz_shadow.static_texture_count;
             ++i) {
            if (xz_shadow.static_textures[i].alive &&
                xz_shadow.static_textures[i].object)
                xz_shadow.gl.DeleteTextures(
                    1,
                    &xz_shadow.static_textures[i].object);
        }
        free(xz_shadow.static_textures);
    }

    xz_shadow.static_textures = NULL;
    xz_shadow.static_texture_count = 0u;

    free(xz_shadow.static_material_bindings);
    xz_shadow.static_material_bindings = NULL;
    xz_shadow.static_material_binding_count = 0u;

    if (xz_shadow.static_normal_textures) {
        for (i = 0u;
             i < xz_shadow.static_normal_texture_count;
             ++i) {
            if (xz_shadow.static_normal_textures[i].alive &&
                xz_shadow.static_normal_textures[i].object)
                xz_shadow.gl.DeleteTextures(
                    1,
                    &xz_shadow.static_normal_textures[i].object);
        }
        free(xz_shadow.static_normal_textures);
    }

    xz_shadow.static_normal_textures = NULL;
    xz_shadow.static_normal_texture_count = 0u;

    free(xz_shadow.static_normal_bindings);
    xz_shadow.static_normal_bindings = NULL;
    xz_shadow.static_normal_binding_count = 0u;

    free(xz_shadow.static_pbr_bindings);
    xz_shadow.static_pbr_bindings = NULL;
    xz_shadow.static_pbr_binding_count = 0u;

    if (xz_shadow.static_meshes) {
        for (i = 0u;
             i < xz_shadow.static_mesh_count;
             ++i) {
            XzGles3StaticMesh *mesh =
                &xz_shadow.static_meshes[i];

            if (mesh->vao)
                xz_shadow.gl.DeleteVertexArrays(
                    1, &mesh->vao);
            if (mesh->vbo)
                xz_shadow.gl.DeleteBuffers(
                    1, &mesh->vbo);
            if (mesh->ibo)
                xz_shadow.gl.DeleteBuffers(
                    1, &mesh->ibo);
            free(mesh->submeshes);
            mesh->submeshes = NULL;
        }

        free(xz_shadow.static_meshes);
    }

    xz_shadow.static_meshes = NULL;
    xz_shadow.static_mesh_count = 0u;

    if (xz_shadow.static_instance_vbo) {
        xz_shadow.gl.DeleteBuffers(
            1, &xz_shadow.static_instance_vbo);
        xz_shadow.static_instance_vbo = 0u;
    }
    if (xz_shadow.static_lightmap_instance_vbo) {
        xz_shadow.gl.DeleteBuffers(
            1, &xz_shadow.static_lightmap_instance_vbo);
        xz_shadow.static_lightmap_instance_vbo = 0u;
    }

    XzStaticSceneDrawPlan_Reset(
        &xz_shadow.static_draw_plan);
    xz_shadow.static_draw_plan_ready = 0;
    XzStaticSceneMaterialDrawPlan_Reset(
        &xz_shadow.static_material_draw_plan);
    xz_shadow.static_material_draw_plan_ready = 0;
    XzStaticSceneLightmapDrawPlan_Reset(
        &xz_shadow.static_lightmap_draw_plan);
    xz_shadow.static_lightmap_draw_plan_ready = 0;

    if (state) {
        state->static_scene_gpu_bytes = 0u;
        state->static_scene_gpu_vertices = 0u;
        state->static_scene_gpu_indices = 0u;
        state->static_scene_gpu_meshes = 0u;
        state->static_scene_gpu_submeshes = 0u;
        state->static_scene_gpu_multi_uv_meshes = 0u;
        state->static_scene_multi_uv_ready = 0;
        state->static_scene_material_set_count = 0u;
        state->static_scene_material_batch_count = 0u;
        state->static_scene_material_batch_ready = 0;
        state->static_scene_xzml_materials = 0u;
        state->static_scene_xztx_gpu_textures = 0u;
        state->static_scene_xztx_astc_textures = 0u;
        state->static_scene_inferred_diffuse_materials = 0u;
        state->static_scene_xztx_gpu_bytes = 0u;
        state->static_scene_xzml_gpu_ready = 0;
        state->static_scene_lightmap_batch_count = 0u;
        state->static_scene_lightmap_mapped_batches = 0u;
        state->static_scene_lightmap_missing_batches = 0u;
        state->static_scene_lightmap_batch_ready = 0;
        state->static_scene_gpu_lightmap_bytes = 0u;
        state->static_scene_gpu_lightmap_textures = 0u;
        state->static_scene_last_baked_lightmap_draw_calls = 0u;
        state->static_scene_lightmap_shader_ready = 0;
        state->static_scene_gpu_texture_bytes = 0u;
        state->static_scene_gpu_textures = 0u;
        state->static_scene_material_bindings = 0u;
        state->static_scene_material_mapped_bindings = 0u;
        state->static_scene_material_ready = 0;
        state->static_scene_gpu_normal_texture_bytes = 0u;
        state->static_scene_gpu_normal_textures = 0u;
        state->static_scene_normal_bindings = 0u;
        state->static_scene_normal_mapped_bindings = 0u;
        state->static_scene_last_normal_bindings = 0u;
        state->static_scene_normal_ready = 0;
        state->static_scene_pbr_bindings = 0u;
        state->static_scene_pbr_authored_bindings = 0u;
        state->static_scene_last_pbr_bindings = 0u;
        state->static_scene_pbr_ready = 0;
        state->static_scene_specular_response_ready = 0;
        state->static_scene_last_specular_local_lights = 0u;
        state->static_scene_reflection_ready = 0;
        state->static_scene_reflection_gpu_bytes = 0u;
        state->static_scene_reflection_size = 0u;
        state->static_scene_reflection_mips = 0u;
        state->static_scene_reflection_average_brightness = 0.0f;
        state->static_scene_reflection_brightness = 0.0f;
        state->static_scene_reflection_position_meters[0] = 0.0f;
        state->static_scene_reflection_position_meters[1] = 0.0f;
        state->static_scene_reflection_position_meters[2] = 0.0f;
        state->static_scene_reflection_radius_meters = 0.0f;
        state->static_scene_reflection_offset_meters[0] = 0.0f;
        state->static_scene_reflection_offset_meters[1] = 0.0f;
        state->static_scene_reflection_offset_meters[2] = 0.0f;
        state->static_scene_reflection_sphere_ready = 0;
        state->static_scene_reflection_ibl_ready = 0;
        state->static_scene_tonemap_ready = 0;
        state->static_scene_auto_exposure_enabled = 0;
        state->static_scene_tonemapper_film_enabled = 0;
        state->static_scene_legacy_film_contrast = 0.0f;
        state->static_scene_legacy_film_dynamic_range = 0.0f;
        state->static_scene_legacy_film_toe_amount = 0.0f;
        state->static_scene_legacy_film_heal_amount = 0.0f;
        state->static_scene_exposure_multiplier = 0.0f;
        state->static_scene_lighting_ready = 0;
        state->static_scene_local_light_count = 0u;
        state->static_scene_local_light_active = 0u;
        state->static_scene_local_light_camera_affecting = 0u;
        state->static_scene_local_light_dropped_affecting = 0u;
        state->static_scene_local_lighting_ready = 0;
        state->static_scene_height_fog_ready = 0;
        state->static_scene_directional_fog_enabled = 0;
        state->static_scene_fog_density = 0.0f;
        state->static_scene_fog_height_falloff = 0.0f;
        state->static_scene_fog_max_opacity = 0.0f;
        state->static_scene_fog_start_meters = 0.0f;
        state->static_scene_gpu_ready = 0;
        state->static_scene_last_draw_calls = 0u;
        state->static_scene_last_instances = 0u;
        state->static_scene_last_textured_draw_calls = 0u;
        state->static_scene_last_untextured_draw_calls = 0u;
        state->static_scene_frame_ready = 0;
    }
}

void XzGles3Shadow_ReleaseStaticScene(
    XzGles3ShadowState *state)
{
    EGLDisplay previous_display;
    EGLSurface previous_draw;
    EGLSurface previous_read;
    EGLContext previous_context;

    if (!state || !state->initialized ||
        !xz_shadow.ready)
        return;

    if (!XzMakeShadowCurrent(
            &previous_display,
            &previous_draw,
            &previous_read,
            &previous_context)) {
        state->static_scene_upload_failures++;
        state->static_scene_gpu_ready = 0;
        return;
    }

    XzDestroyStaticSceneCurrent(state);

    if (!XzRestorePrevious(
            previous_display,
            previous_draw,
            previous_read,
            previous_context)) {
        state->restore_failures++;
        state->restore_ok = 0;
    }
}

int XzGles3Shadow_UploadStaticScene(
    XzGles3ShadowState *state,
    const XzStaticSceneRuntimeState *scene)
{
    EGLDisplay previous_display;
    EGLSurface previous_draw;
    EGLSurface previous_read;
    EGLContext previous_context;
    XzGles3StaticMesh *gpu_meshes = NULL;
    uint64_t gpu_bytes = 0u;
    uint64_t vertices = 0u;
    uint64_t indices = 0u;
    uint64_t submeshes = 0u;
    uint32_t multi_uv_meshes = 0u;
    uint32_t mesh_index;
    uint32_t material_binding_index;
    unsigned int failure_stage = 0u;
    GLenum failure_gl_error = GL_NO_ERROR;
    int restored = 0;

    if (!state || !scene ||
        !state->initialized ||
        !state->available ||
        !xz_shadow.ready ||
        scene->status != XZ_STATIC_SCENE_READY ||
        XzStaticSceneRuntime_MeshCount(scene) == 0u)
        return 0;

    state->static_scene_upload_attempts++;
    state->static_scene_upload_failure_stage = 0u;
    state->static_scene_upload_failure_gl_error = 0u;
    state->static_scene_upload_failure_texture_index = 0xffffffffu;
    state->static_scene_upload_failure_mip_index = 0xffffffffu;
    state->static_scene_astc_supported = 0u;
    memset(
        state->static_scene_camera_origin,
        0,
        sizeof(state->static_scene_camera_origin));
    state->static_scene_camera_probe_count = 0u;
    state->static_scene_camera_probe_inside_count = 0u;
    memset(
        state->static_scene_camera_probe_mesh,
        0,
        sizeof(state->static_scene_camera_probe_mesh));
    memset(
        state->static_scene_camera_probe_instance,
        0,
        sizeof(state->static_scene_camera_probe_instance));
    memset(
        state->static_scene_camera_probe_inside,
        0,
        sizeof(state->static_scene_camera_probe_inside));
    memset(
        state->static_scene_camera_probe_distance,
        0,
        sizeof(state->static_scene_camera_probe_distance));
    memset(
        state->static_scene_camera_probe_bounds_min,
        0,
        sizeof(state->static_scene_camera_probe_bounds_min));
    memset(
        state->static_scene_camera_probe_bounds_max,
        0,
        sizeof(state->static_scene_camera_probe_bounds_max));

    if (!XzMakeShadowCurrent(
            &previous_display,
            &previous_draw,
            &previous_read,
            &previous_context)) {
        state->static_scene_upload_failures++;
        state->static_scene_gpu_ready = 0;
        return 0;
    }

    XzDrainErrors(state);
    XzDestroyStaticSceneCurrent(state);
    state->static_scene_astc_supported =
        XzStaticAstcSupported() ? 1u : 0u;

    failure_stage = 10u; /* source lighting */
    if (XzStaticSceneSourceLighting(
            scene,
            &xz_shadow.static_ambient_weight,
            &xz_shadow.static_directional_weight,
            xz_shadow.static_directional_color,
            xz_shadow.static_directional_direction)) {
        state->static_scene_lighting_ready = 1;
    } else if (strcmp(
                   scene->map_id,
                   "xziel_nacht_bo3") == 0) {
        goto fail;
    } else {
        xz_shadow.static_ambient_weight = 1.0f;
        xz_shadow.static_directional_weight = 0.0f;
        xz_shadow.static_directional_color[0] = 1.0f;
        xz_shadow.static_directional_color[1] = 1.0f;
        xz_shadow.static_directional_color[2] = 1.0f;
        xz_shadow.static_directional_direction[0] = 0.0f;
        xz_shadow.static_directional_direction[1] = 0.0f;
        xz_shadow.static_directional_direction[2] = 1.0f;
    }

    failure_stage = 20u; /* local lights */
    if (XzStaticScenePrepareLocalLights(scene)) {
        state->static_scene_local_light_count =
            xz_shadow.static_local_light_count;
        state->static_scene_local_lighting_ready = 1;
    } else if (strcmp(
                   scene->map_id,
                   "xziel_nacht_bo3") == 0) {
        goto fail;
    }

    failure_stage = 30u; /* height fog */
    if (!XzStaticScenePrepareHeightFog(
            scene,
            state) &&
        strcmp(
            scene->map_id,
            "xziel_nacht_bo3") == 0)
        goto fail;

    failure_stage = 40u; /* reflection */
    if (!XzUploadStaticReflection(
            scene,
            state))
        goto fail;

    if (strcmp(
            scene->map_id,
            "xziel_nacht_bo3") == 0 &&
        !state->static_scene_reflection_ready)
        goto fail;

    failure_stage = 50u; /* mesh GPU upload */
    gpu_meshes = (XzGles3StaticMesh *)calloc(
        (size_t)scene->mesh_resource_count,
        sizeof(*gpu_meshes));
    if (!gpu_meshes)
        goto fail;

    for (mesh_index = 0u;
         mesh_index < scene->mesh_resource_count;
         ++mesh_index) {
        const XzStaticMeshResource *source =
            XzStaticSceneRuntime_Mesh(
                scene, mesh_index);
        XzGles3StaticMesh *dest =
            &gpu_meshes[mesh_index];
        uint64_t vertex_bytes;
        uint64_t index_bytes;
        uint32_t submesh_index;

        failure_stage =
            500000u + mesh_index * 100u + 1u;
        if (!source ||
            !source->data ||
            (source->mesh.vertex_stride !=
                 XZ_XZMS_VERTEX_BYTES_V1 &&
             source->mesh.vertex_stride !=
                 XZ_XZMS_VERTEX_BYTES_V2 &&
             source->mesh.vertex_stride !=
                 XZ_XZMS_VERTEX_BYTES_V3 &&
             source->mesh.vertex_stride !=
                 XZ_XZMS_VERTEX_BYTES_V4) ||
            source->mesh.vertex_count == 0u ||
            source->mesh.index_count == 0u ||
            source->mesh.submesh_count == 0u)
            goto fail;

        failure_stage =
            500000u + mesh_index * 100u + 2u;
        dest->submeshes =
            (XzXzmeshSubmesh *)calloc(
                source->mesh.submesh_count,
                sizeof(*dest->submeshes));
        if (!dest->submeshes)
            goto fail;

        for (submesh_index = 0u;
             submesh_index <
                source->mesh.submesh_count;
             ++submesh_index) {
            failure_stage =
                500000u + mesh_index * 100u + 3u;
            if (!XzXzmesh_ReadSubmesh(
                    &source->mesh,
                    submesh_index,
                    &dest->submeshes[submesh_index]))
                goto fail;
        }

        failure_stage =
            500000u + mesh_index * 100u + 4u;
        vertex_bytes =
            (uint64_t)source->mesh.vertex_count *
            (uint64_t)source->mesh.vertex_stride;
        index_bytes =
            (uint64_t)source->mesh.index_count *
            (uint64_t)sizeof(uint32_t);

        if (vertex_bytes > (uint64_t)INT32_MAX ||
            index_bytes > (uint64_t)INT32_MAX)
            goto fail;

        failure_stage =
            500000u + mesh_index * 100u + 5u;
        xz_shadow.gl.GenVertexArrays(
            1, &dest->vao);
        xz_shadow.gl.GenBuffers(
            1, &dest->vbo);
        xz_shadow.gl.GenBuffers(
            1, &dest->ibo);

        if (!dest->vao ||
            !dest->vbo ||
            !dest->ibo)
            goto fail;

        failure_stage =
            500000u + mesh_index * 100u + 6u;
        xz_shadow.gl.BindVertexArray(
            dest->vao);

        xz_shadow.gl.BindBuffer(
            GL_ARRAY_BUFFER,
            dest->vbo);
        xz_shadow.gl.BufferData(
            GL_ARRAY_BUFFER,
            (GLsizeiptr)vertex_bytes,
            source->data +
                source->mesh.vertex_offset,
            GL_STATIC_DRAW);

        xz_shadow.gl.BindBuffer(
            GL_ELEMENT_ARRAY_BUFFER,
            dest->ibo);
        xz_shadow.gl.BufferData(
            GL_ELEMENT_ARRAY_BUFFER,
            (GLsizeiptr)index_bytes,
            source->data +
                source->mesh.index_offset,
            GL_STATIC_DRAW);

        /*
         * XZMS v4 preserves UV0..UV7. The current static shader consumes
         * UV0..UV3 as two packed vec4 attributes plus the authored tangent;
         * UV4..UV7 remain preserved in the source vertex payload for systems
         * that opt into those channels without changing the mesh format.
         *
         *   0 position.xyz
         *   1 uv0.xy + uv1.xy
         *   2 normal.xyz
         *   3 uv2.xy + uv3.xy
         *   4 tangent.xyzw
         *   5..8 instanced model matrix
         *   9..14 instanced lightmap data
         */
        xz_shadow.gl.EnableVertexAttribArray(0u);
        xz_shadow.gl.VertexAttribPointer(
            0u, 3, GL_FLOAT, GL_FALSE,
            (GLsizei)source->mesh.vertex_stride,
            (const void *)0);

        xz_shadow.gl.EnableVertexAttribArray(2u);
        xz_shadow.gl.VertexAttribPointer(
            2u, 3, GL_FLOAT, GL_FALSE,
            (GLsizei)source->mesh.vertex_stride,
            (const void *)(uintptr_t)12u);

        xz_shadow.gl.EnableVertexAttribArray(1u);
        if (source->mesh.version >= XZ_XZMS_VERSION) {
            xz_shadow.gl.VertexAttribPointer(
                1u, 4, GL_FLOAT, GL_FALSE,
                (GLsizei)source->mesh.vertex_stride,
                (const void *)(uintptr_t)40u);
            xz_shadow.gl.EnableVertexAttribArray(3u);
            xz_shadow.gl.VertexAttribPointer(
                3u, 4, GL_FLOAT, GL_FALSE,
                (GLsizei)source->mesh.vertex_stride,
                (const void *)(uintptr_t)56u);
            xz_shadow.gl.EnableVertexAttribArray(4u);
            xz_shadow.gl.VertexAttribPointer(
                4u, 4, GL_FLOAT, GL_FALSE,
                (GLsizei)source->mesh.vertex_stride,
                (const void *)(uintptr_t)24u);
            multi_uv_meshes++;
        } else if (source->mesh.version >= XZ_XZMS_VERSION_V2) {
            xz_shadow.gl.VertexAttribPointer(
                1u, 4, GL_FLOAT, GL_FALSE,
                (GLsizei)source->mesh.vertex_stride,
                (const void *)(uintptr_t)24u);
            xz_shadow.gl.EnableVertexAttribArray(3u);
            xz_shadow.gl.VertexAttribPointer(
                3u, 4, GL_FLOAT, GL_FALSE,
                (GLsizei)source->mesh.vertex_stride,
                (const void *)(uintptr_t)40u);
            multi_uv_meshes++;
        } else {
            xz_shadow.gl.VertexAttribPointer(
                1u, 2, GL_FLOAT, GL_FALSE,
                (GLsizei)source->mesh.vertex_stride,
                (const void *)(uintptr_t)24u);
        }

        failure_stage =
            500000u + mesh_index * 100u + 7u;
        if (xz_shadow.gl.GetError() !=
                GL_NO_ERROR)
            goto fail;

        dest->vertex_count =
            source->mesh.vertex_count;
        dest->index_count =
            source->mesh.index_count;
        dest->submesh_count =
            source->mesh.submesh_count;
        dest->gpu_bytes =
            vertex_bytes + index_bytes;
        memcpy(
            dest->bounds_min,
            source->mesh.bounds_min,
            sizeof(dest->bounds_min));
        memcpy(
            dest->bounds_max,
            source->mesh.bounds_max,
            sizeof(dest->bounds_max));
        dest->alive = 1;

        gpu_bytes += dest->gpu_bytes;
        vertices += dest->vertex_count;
        indices += dest->index_count;
        submeshes += dest->submesh_count;
    }

    if (scene->material_data &&
        scene->material_texture_count > 0u &&
        scene->material_binding_count > 0u) {
        uint32_t texture_index;
        uint32_t mapped_bindings = 0u;
        uint64_t texture_bytes_total = 0u;

        if (scene->material_binding_count !=
                (uint32_t)submeshes)
            goto fail;

        xz_shadow.static_textures =
            (XzGles3StaticTexture *)calloc(
                scene->material_texture_count,
                sizeof(*xz_shadow.static_textures));
        if (!xz_shadow.static_textures)
            goto fail;

        xz_shadow.static_texture_count =
            scene->material_texture_count;

        for (texture_index = 0u;
             texture_index <
                scene->material_texture_count;
             ++texture_index) {
            XzStaticTextureView source_texture;
            GLint internal_format;
            XzGles3StaticTexture *dest_texture =
                &xz_shadow.static_textures[
                    texture_index];

            if (!XzStaticSceneRuntime_Texture(
                    scene,
                    texture_index,
                    &source_texture) ||
                source_texture.width == 0u ||
                source_texture.height == 0u ||
                source_texture.rgba_bytes !=
                    (size_t)source_texture.width *
                    (size_t)source_texture.height *
                    4u)
                goto fail;

            internal_format =
                (source_texture.flags &
                    XZ_STATIC_TEXTURE_FLAG_SRGB) != 0u
                    ? GL_SRGB8_ALPHA8
                    : GL_RGBA8;

            xz_shadow.gl.GenTextures(
                1,
                &dest_texture->object);
            if (!dest_texture->object)
                goto fail;

            xz_shadow.gl.ActiveTexture(GL_TEXTURE0);
            xz_shadow.gl.BindTexture(
                GL_TEXTURE_2D,
                dest_texture->object);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_MIN_FILTER,
                GL_LINEAR);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_MAG_FILTER,
                GL_LINEAR);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_WRAP_S,
                GL_REPEAT);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_WRAP_T,
                GL_REPEAT);
            {
                unsigned char *upload_rgba =
                    (unsigned char *)malloc(
                        source_texture.rgba_bytes);
                if (!upload_rgba)
                    goto fail;
                if (!XzStaticSceneRuntime_ReadTexture(
                        scene,
                        texture_index,
                        upload_rgba,
                        source_texture.rgba_bytes)) {
                    free(upload_rgba);
                    goto fail;
                }

                xz_shadow.gl.TexImage2D(
                    GL_TEXTURE_2D,
                    0,
                    internal_format,
                    (GLsizei)source_texture.width,
                    (GLsizei)source_texture.height,
                    0,
                    GL_RGBA,
                    GL_UNSIGNED_BYTE,
                    upload_rgba);
                free(upload_rgba);
            }

            if (xz_shadow.gl.GetError() !=
                    GL_NO_ERROR)
                goto fail;

            dest_texture->width =
                source_texture.width;
            dest_texture->height =
                source_texture.height;
            dest_texture->gpu_bytes =
                (uint64_t)source_texture.rgba_bytes;
            dest_texture->alive = 1;
            texture_bytes_total +=
                dest_texture->gpu_bytes;
        }

        xz_shadow.static_material_bindings =
            (uint32_t *)calloc(
                scene->material_binding_count,
                sizeof(uint32_t));
        if (!xz_shadow.static_material_bindings)
            goto fail;

        xz_shadow.static_material_binding_count =
            scene->material_binding_count;

        for (material_binding_index = 0u;
             material_binding_index <
                scene->material_binding_count;
             ++material_binding_index) {
            uint32_t texture_index_value;

            if (!XzStaticSceneRuntime_MaterialBinding(
                    scene,
                    material_binding_index,
                    &texture_index_value))
                goto fail;

            xz_shadow.static_material_bindings[
                material_binding_index] =
                    texture_index_value;

            if (texture_index_value !=
                    XZ_STATIC_MATERIAL_NO_TEXTURE)
                mapped_bindings++;
        }

        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D,
            0u);

        state->static_scene_gpu_texture_bytes =
            texture_bytes_total;
        state->static_scene_gpu_textures =
            scene->material_texture_count;
        state->static_scene_material_bindings =
            scene->material_binding_count;
        state->static_scene_material_mapped_bindings =
            mapped_bindings;
        state->static_scene_material_ready =
            state->static_scene_gpu_textures > 0u &&
            state->static_scene_material_bindings ==
                (unsigned int)submeshes &&
            mapped_bindings > 0u;
    }

    failure_stage = 70u; /* native XZTX upload */
    if (scene->material_library_data) {
        if (!XzUploadStaticNativeMaterialTextures(
                scene,
                state))
            goto fail;
    }

    failure_stage = 80u; /* legacy normal material upload */
    if (scene->normal_material_data &&
        scene->normal_texture_count > 0u &&
        scene->normal_binding_count > 0u) {
        uint32_t texture_index;
        uint32_t mapped_bindings = 0u;
        uint64_t texture_bytes_total = 0u;

        if (scene->normal_binding_count !=
                (uint32_t)submeshes)
            goto fail;

        xz_shadow.static_normal_textures =
            (XzGles3StaticTexture *)calloc(
                scene->normal_texture_count,
                sizeof(*xz_shadow.static_normal_textures));
        if (!xz_shadow.static_normal_textures)
            goto fail;

        xz_shadow.static_normal_texture_count =
            scene->normal_texture_count;

        for (texture_index = 0u;
             texture_index <
                scene->normal_texture_count;
             ++texture_index) {
            XzStaticTextureView source_texture;
            XzGles3StaticTexture *dest_texture =
                &xz_shadow.static_normal_textures[
                    texture_index];

            if (!XzStaticSceneRuntime_NormalTexture(
                    scene,
                    texture_index,
                    &source_texture) ||
                source_texture.width == 0u ||
                source_texture.height == 0u ||
                source_texture.rgba_bytes !=
                    (size_t)source_texture.width *
                    (size_t)source_texture.height *
                    4u)
                goto fail;

            xz_shadow.gl.GenTextures(
                1,
                &dest_texture->object);
            if (!dest_texture->object)
                goto fail;

            xz_shadow.gl.ActiveTexture(GL_TEXTURE1);
            xz_shadow.gl.BindTexture(
                GL_TEXTURE_2D,
                dest_texture->object);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_MIN_FILTER,
                GL_LINEAR);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_MAG_FILTER,
                GL_LINEAR);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_WRAP_S,
                GL_REPEAT);
            xz_shadow.gl.TexParameteri(
                GL_TEXTURE_2D,
                GL_TEXTURE_WRAP_T,
                GL_REPEAT);
            {
                unsigned char *upload_rgba =
                    (unsigned char *)malloc(
                        source_texture.rgba_bytes);
                if (!upload_rgba)
                    goto fail;
                if (!XzStaticSceneRuntime_ReadNormalTexture(
                        scene,
                        texture_index,
                        upload_rgba,
                        source_texture.rgba_bytes)) {
                    free(upload_rgba);
                    goto fail;
                }

                xz_shadow.gl.TexImage2D(
                    GL_TEXTURE_2D,
                    0,
                    GL_RGBA8,
                    (GLsizei)source_texture.width,
                    (GLsizei)source_texture.height,
                    0,
                    GL_RGBA,
                    GL_UNSIGNED_BYTE,
                    upload_rgba);
                free(upload_rgba);
            }

            if (xz_shadow.gl.GetError() !=
                    GL_NO_ERROR)
                goto fail;

            dest_texture->width =
                source_texture.width;
            dest_texture->height =
                source_texture.height;
            dest_texture->gpu_bytes =
                (uint64_t)source_texture.rgba_bytes;
            dest_texture->alive = 1;
            texture_bytes_total +=
                dest_texture->gpu_bytes;
        }

        xz_shadow.static_normal_bindings =
            (uint32_t *)calloc(
                scene->normal_binding_count,
                sizeof(uint32_t));
        if (!xz_shadow.static_normal_bindings)
            goto fail;

        xz_shadow.static_normal_binding_count =
            scene->normal_binding_count;

        for (material_binding_index = 0u;
             material_binding_index <
                scene->normal_binding_count;
             ++material_binding_index) {
            uint32_t texture_index_value;

            if (!XzStaticSceneRuntime_NormalBinding(
                    scene,
                    material_binding_index,
                    &texture_index_value))
                goto fail;

            xz_shadow.static_normal_bindings[
                material_binding_index] =
                    texture_index_value;

            if (texture_index_value !=
                    XZ_STATIC_MATERIAL_NO_TEXTURE)
                mapped_bindings++;
        }

        xz_shadow.gl.ActiveTexture(GL_TEXTURE1);
        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D,
            0u);
        xz_shadow.gl.ActiveTexture(GL_TEXTURE0);

        state->static_scene_gpu_normal_texture_bytes =
            texture_bytes_total;
        state->static_scene_gpu_normal_textures =
            scene->normal_texture_count;
        state->static_scene_normal_bindings =
            scene->normal_binding_count;
        state->static_scene_normal_mapped_bindings =
            mapped_bindings;
        state->static_scene_normal_ready =
            state->static_scene_gpu_normal_textures > 0u &&
            state->static_scene_normal_bindings ==
                (unsigned int)submeshes &&
            mapped_bindings > 0u;
    }

    failure_stage = 90u; /* PBR bindings */
    if (scene->pbr_material_data &&
        scene->pbr_material.binding_count > 0u) {
        uint32_t pbr_index;
        uint32_t authored_bindings = 0u;

        if (scene->pbr_material.binding_count !=
                (uint32_t)submeshes ||
            scene->pbr_material.binding_count !=
                scene->material_binding_count)
            goto fail;

        xz_shadow.static_pbr_bindings =
            (XzPbrMaterialBinding *)calloc(
                scene->pbr_material.binding_count,
                sizeof(*xz_shadow.static_pbr_bindings));
        if (!xz_shadow.static_pbr_bindings)
            goto fail;

        xz_shadow.static_pbr_binding_count =
            scene->pbr_material.binding_count;

        for (pbr_index = 0u;
             pbr_index <
                scene->pbr_material.binding_count;
             ++pbr_index) {
            XzPbrMaterialBinding binding;

            if (!XzStaticSceneRuntime_PbrBinding(
                    scene,
                    pbr_index,
                    &binding))
                goto fail;

            xz_shadow.static_pbr_bindings[pbr_index] =
                binding;
            if (binding.flags != 0u)
                authored_bindings++;
        }

        state->static_scene_pbr_bindings =
            xz_shadow.static_pbr_binding_count;
        state->static_scene_pbr_authored_bindings =
            authored_bindings;
        state->static_scene_pbr_ready =
            state->static_scene_pbr_bindings ==
                (unsigned int)submeshes;
    }

    state->static_scene_reflection_ibl_ready =
        state->static_scene_reflection_ready &&
        state->static_scene_pbr_ready &&
        (strcmp(
             scene->map_id,
             "xziel_nacht_bo3") != 0 ||
         state->static_scene_reflection_sphere_ready);

    /*
     * Pavlov-Legacy project renderer settings:
     *   r.DefaultFeature.AutoExposure=False
     *   r.TonemapperFilm=0
     * The map census contains no post-process override, so Nacht inherits
     * the UE4 legacy film-stock defaults below with fixed exposure 1.0.
     */
    state->static_scene_tonemap_ready = 1;
    state->static_scene_auto_exposure_enabled = 0;
    state->static_scene_tonemapper_film_enabled = 0;
    state->static_scene_legacy_film_contrast = 0.03f;
    state->static_scene_legacy_film_dynamic_range = 4.0f;
    state->static_scene_legacy_film_toe_amount = 1.0f;
    state->static_scene_legacy_film_heal_amount = 0.18f;
    state->static_scene_exposure_multiplier = 1.0f;

    if (strcmp(
            scene->map_id,
            "xziel_nacht_bo3") == 0 &&
        (!state->static_scene_reflection_sphere_ready ||
         !state->static_scene_reflection_ibl_ready ||
         !state->static_scene_tonemap_ready))
        goto fail;

    state->static_scene_specular_response_ready =
        state->static_scene_pbr_ready &&
        state->static_scene_pbr_authored_bindings > 0u &&
        state->static_scene_lighting_ready &&
        state->static_scene_local_lighting_ready &&
        state->static_scene_local_light_count ==
            XZ_STATIC_LOCAL_LIGHT_SOURCE_MAX;

    if (strcmp(
            scene->map_id,
            "xziel_nacht_bo3") == 0 &&
        !state->static_scene_specular_response_ready)
        goto fail;

    failure_stage = 100u; /* scene draw plan */
    if (!XzStaticSceneDrawPlan_Build(
            &xz_shadow.static_draw_plan,
            XzStaticSceneRuntime_Scene(scene)) ||
        xz_shadow.static_draw_plan.mesh_count !=
            scene->mesh_resource_count ||
        xz_shadow.static_draw_plan.instance_count !=
            scene->scene.instance_count)
        goto fail;

    failure_stage = 110u; /* material batching/native binding */
    {
        const XzMaterialInstanceBindingView *material_instances =
            XzStaticSceneRuntime_MaterialInstances(scene);

        if (material_instances) {
            if (!XzStaticSceneMaterialDrawPlan_Build(
                    &xz_shadow.static_material_draw_plan,
                    XzStaticSceneRuntime_Scene(scene),
                    material_instances) ||
                xz_shadow.static_material_draw_plan.mesh_count !=
                    scene->mesh_resource_count ||
                xz_shadow.static_material_draw_plan.instance_count !=
                    scene->scene.instance_count ||
                xz_shadow.static_material_draw_plan.batch_count == 0u ||
                xz_shadow.static_material_draw_plan.material_set_count == 0u)
                goto fail;

            state->static_scene_material_set_count =
                xz_shadow.static_material_draw_plan.material_set_count;
            state->static_scene_material_batch_count =
                xz_shadow.static_material_draw_plan.batch_count;
            state->static_scene_material_batch_ready = 1;
            xz_shadow.static_material_draw_plan_ready = 1;

            if (XzStaticSceneRuntime_MaterialLibrary(scene)) {
                if (!XzPrepareNativeMaterials(
                        scene,
                        state) ||
                    !XzBuildNativeMaterialBatchBindings(
                        scene))
                    goto fail;
            }
        } else if (
            XzStaticSceneRuntime_MaterialLibrary(scene)) {
            goto fail;
        }
    }

    failure_stage = 120u; /* Nacht-only baked lightmaps */
    if (strcmp(
            scene->map_id,
            "xziel_nacht_bo3") == 0) {
        const XzLightmapBindingView *lightmap_bindings =
            XzStaticSceneRuntime_LightmapBindings(scene);

        if (!lightmap_bindings ||
            !XzStaticSceneLightmapDrawPlan_Build(
                &xz_shadow.static_lightmap_draw_plan,
                XzStaticSceneRuntime_Scene(scene),
                lightmap_bindings))
            goto fail;

        state->static_scene_lightmap_batch_count =
            xz_shadow.static_lightmap_draw_plan.batch_count;
        state->static_scene_lightmap_mapped_batches =
            xz_shadow.static_lightmap_draw_plan.mapped_batch_count;
        state->static_scene_lightmap_missing_batches =
            xz_shadow.static_lightmap_draw_plan.missing_batch_count;
        state->static_scene_lightmap_batch_ready =
            xz_shadow.static_lightmap_draw_plan.mesh_count ==
                scene->mesh_resource_count &&
            xz_shadow.static_lightmap_draw_plan.instance_count ==
                scene->scene.instance_count &&
            xz_shadow.static_lightmap_draw_plan.mapped_instance_count ==
                10787u &&
            xz_shadow.static_lightmap_draw_plan.missing_instance_count ==
                4u &&
            xz_shadow.static_lightmap_draw_plan.mapped_batch_count >
                0u &&
            xz_shadow.static_lightmap_draw_plan.batch_count >=
                xz_shadow.static_lightmap_draw_plan.mapped_batch_count;

        if (!state->static_scene_lightmap_batch_ready)
            goto fail;

        xz_shadow.static_lightmap_draw_plan_ready = 1;

        if (!XzBuildStaticLightmapInstanceVbo(scene) ||
            !XzUploadStaticHQLightmaps(
                scene,
                state))
            goto fail;
    }

    failure_stage = 130u; /* instance VBO */
    xz_shadow.gl.GenBuffers(
        1, &xz_shadow.static_instance_vbo);
    if (!xz_shadow.static_instance_vbo)
        goto fail;

    xz_shadow.gl.BindBuffer(
        GL_ARRAY_BUFFER,
        xz_shadow.static_instance_vbo);
    xz_shadow.gl.BufferData(
        GL_ARRAY_BUFFER,
        (GLsizeiptr)(
            (uint64_t)xz_shadow.static_draw_plan.instance_count *
            16u * sizeof(float)),
        xz_shadow.static_lightmap_draw_plan_ready
            ? xz_shadow.static_lightmap_draw_plan.instance_matrices
            : (xz_shadow.static_material_draw_plan_ready
                ? xz_shadow.static_material_draw_plan.instance_matrices
                : xz_shadow.static_draw_plan.instance_matrices),
        GL_STATIC_DRAW);

    failure_stage = 140u; /* instance attributes */
    for (mesh_index = 0u;
         mesh_index < scene->mesh_resource_count;
         ++mesh_index) {
        const XzStaticSceneDrawSpan *span =
            XzStaticSceneDrawPlan_Span(
                &xz_shadow.static_draw_plan,
                mesh_index);
        XzGles3StaticMesh *dest =
            &gpu_meshes[mesh_index];
        uint32_t column;

        if (!span ||
            span->instance_count == 0u ||
            !dest->alive)
            goto fail;

        xz_shadow.gl.BindVertexArray(
            dest->vao);
        xz_shadow.gl.BindBuffer(
            GL_ARRAY_BUFFER,
            xz_shadow.static_instance_vbo);

        for (column = 0u;
             column < 4u;
             ++column) {
            /*
             * Locations 1..4 carry packed UVs, normal and authored tangent.
             * Keep the instanced mat4 at 5..8; lightmap data stays at 9..14.
             */
            const GLuint location =
                (GLuint)(5u + column);
            const uintptr_t byte_offset =
                (uintptr_t)(
                    ((uint64_t)span->first_instance * 16u +
                     (uint64_t)column * 4u) *
                    sizeof(float));

            xz_shadow.gl.EnableVertexAttribArray(
                location);
            xz_shadow.gl.VertexAttribPointer(
                location,
                4,
                GL_FLOAT,
                GL_FALSE,
                (GLsizei)(16u * sizeof(float)),
                (const void *)byte_offset);
            xz_shadow.gl.VertexAttribDivisor(
                location, 1u);
        }
    }

    xz_shadow.static_draw_plan_ready = 1;

    xz_shadow.gl.BindVertexArray(0u);
    xz_shadow.gl.BindBuffer(
        GL_ARRAY_BUFFER, 0u);
    xz_shadow.gl.BindBuffer(
        GL_ELEMENT_ARRAY_BUFFER, 0u);

    if (xz_shadow.gl.GetError() != GL_NO_ERROR)
        goto fail;

    xz_shadow.static_meshes = gpu_meshes;
    xz_shadow.static_mesh_count =
        scene->mesh_resource_count;
    gpu_meshes = NULL;

    state->static_scene_gpu_bytes =
        gpu_bytes;
    state->static_scene_gpu_vertices =
        vertices;
    state->static_scene_gpu_indices =
        indices;
    state->static_scene_gpu_meshes =
        xz_shadow.static_mesh_count;
    state->static_scene_gpu_submeshes =
        (unsigned int)submeshes;
    state->static_scene_gpu_multi_uv_meshes =
        multi_uv_meshes;
    state->static_scene_multi_uv_ready =
        multi_uv_meshes ==
            scene->mesh_resource_count &&
        scene->mesh_resource_count > 0u;
    failure_stage = 150u; /* final readiness */
    state->static_scene_gpu_ready =
        state->static_scene_gpu_meshes ==
            scene->mesh_resource_count &&
        state->static_scene_gpu_vertices ==
            scene->vertex_count &&
        state->static_scene_gpu_indices ==
            scene->index_count &&
        state->static_scene_gpu_submeshes ==
            scene->submesh_count &&
        xz_shadow.static_draw_plan_ready &&
        xz_shadow.static_instance_vbo != 0u &&
        (!scene->material_library_data ||
         (state->static_scene_material_ready &&
          state->static_scene_material_batch_ready &&
          state->static_scene_xzml_gpu_ready &&
          xz_shadow.static_material_draw_plan_ready &&
          xz_shadow.static_native_material_ready &&
          xz_shadow.static_material_batch_binding_count > 0u &&
          xz_shadow.static_texture_count ==
              scene->material_library.texture_asset_count)) &&
        (strcmp(
             scene->map_id,
             "xziel_nacht_bo3") != 0 ||
         (state->static_scene_multi_uv_ready &&
          state->static_scene_lightmap_batch_ready &&
          state->static_scene_lightmap_shader_ready &&
          xz_shadow.static_lightmap_instance_vbo != 0u &&
          state->static_scene_material_ready &&
          state->static_scene_normal_ready &&
          state->static_scene_pbr_ready &&
          state->static_scene_specular_response_ready &&
          state->static_scene_tonemap_ready &&
          state->static_scene_lighting_ready &&
          state->static_scene_local_lighting_ready &&
          state->static_scene_local_light_count ==
              XZ_STATIC_LOCAL_LIGHT_SOURCE_MAX &&
          state->static_scene_height_fog_ready &&
          !state->static_scene_directional_fog_enabled));

    if (!state->static_scene_gpu_ready)
        goto fail_current_owned;

    restored = XzRestorePrevious(
        previous_display,
        previous_draw,
        previous_read,
        previous_context);

    if (!restored) {
        state->restore_failures++;
        state->restore_ok = 0;
        state->static_scene_upload_failures++;
        state->static_scene_gpu_ready = 0;
        return 0;
    }

    state->restore_ok = 1;
    state->static_scene_upload_successes++;
    return 1;

fail:
    failure_gl_error = xz_shadow.gl.GetError();
    if (gpu_meshes) {
        /*
         * Temporarily publish so the single cleanup path can delete objects
         * already created before the failure.
         */
        xz_shadow.static_meshes = gpu_meshes;
        xz_shadow.static_mesh_count =
            scene->mesh_resource_count;
        gpu_meshes = NULL;
    }

fail_current_owned:
    XzDestroyStaticSceneCurrent(state);
    xz_shadow.gl.BindVertexArray(0u);
    xz_shadow.gl.BindBuffer(
        GL_ARRAY_BUFFER, 0u);
    xz_shadow.gl.BindBuffer(
        GL_ELEMENT_ARRAY_BUFFER, 0u);

    if (!XzRestorePrevious(
            previous_display,
            previous_draw,
            previous_read,
            previous_context)) {
        state->restore_failures++;
        state->restore_ok = 0;
    }

    state->static_scene_upload_failures++;
    state->static_scene_upload_failure_stage = failure_stage;
    state->static_scene_upload_failure_gl_error =
        (unsigned int)failure_gl_error;
    state->static_scene_gpu_ready = 0;
    return 0;
}


static const XzGeometryBatch *XzStaticSceneCamera(
    const XzGeometryFrame *geometry)
{
    unsigned int i;

    if (!geometry)
        return NULL;

    for (i = 0u;
         i < geometry->batch_count;
         ++i) {
        if (geometry->batches[i].kind ==
                XZ_GEOMETRY_SURFACE)
            return &geometry->batches[i];
    }

    return geometry->batch_count > 0u
        ? &geometry->batches[0]
        : NULL;
}


static void XzTransformStaticBounds(
    const float matrix[16],
    const float local_min[3],
    const float local_max[3],
    float world_min[3],
    float world_max[3])
{
    unsigned int corner;

    world_min[0] = world_min[1] = world_min[2] = 1.0e30f;
    world_max[0] = world_max[1] = world_max[2] = -1.0e30f;

    for (corner = 0u; corner < 8u; ++corner) {
        const float x =
            (corner & 1u) ? local_max[0] : local_min[0];
        const float y =
            (corner & 2u) ? local_max[1] : local_min[1];
        const float z =
            (corner & 4u) ? local_max[2] : local_min[2];
        const float p[3] = {
            matrix[0] * x +
                matrix[4] * y +
                matrix[8] * z +
                matrix[12],
            matrix[1] * x +
                matrix[5] * y +
                matrix[9] * z +
                matrix[13],
            matrix[2] * x +
                matrix[6] * y +
                matrix[10] * z +
                matrix[14]
        };
        unsigned int axis;

        for (axis = 0u; axis < 3u; ++axis) {
            if (p[axis] < world_min[axis])
                world_min[axis] = p[axis];
            if (p[axis] > world_max[axis])
                world_max[axis] = p[axis];
        }
    }
}

static float XzPointStaticBoundsDistance(
    const float point[3],
    const float world_min[3],
    const float world_max[3],
    int *inside)
{
    float squared = 0.0f;
    unsigned int axis;
    int contained = 1;

    for (axis = 0u; axis < 3u; ++axis) {
        float delta = 0.0f;

        if (point[axis] < world_min[axis]) {
            delta = world_min[axis] - point[axis];
            contained = 0;
        } else if (point[axis] > world_max[axis]) {
            delta = point[axis] - world_max[axis];
            contained = 0;
        }

        squared += delta * delta;
    }

    if (inside)
        *inside = contained;

    return sqrtf(squared);
}

static void XzProbeStaticSceneCamera(
    XzGles3ShadowState *state,
    const float camera_origin[3])
{
    uint32_t mesh_index;

    if (!state ||
        !camera_origin ||
        !xz_shadow.static_draw_plan_ready ||
        !xz_shadow.static_meshes)
        return;

    memcpy(
        state->static_scene_camera_origin,
        camera_origin,
        sizeof(state->static_scene_camera_origin));
    state->static_scene_camera_probe_count = 0u;
    state->static_scene_camera_probe_inside_count = 0u;

    for (mesh_index = 0u;
         mesh_index < xz_shadow.static_mesh_count;
         ++mesh_index) {
        const XzGles3StaticMesh *mesh =
            &xz_shadow.static_meshes[mesh_index];
        const XzStaticSceneDrawSpan *span =
            XzStaticSceneDrawPlan_Span(
                &xz_shadow.static_draw_plan,
                mesh_index);
        uint32_t local_instance;

        if (!mesh->alive ||
            !span)
            continue;

        for (local_instance = 0u;
             local_instance < span->instance_count;
             ++local_instance) {
            const uint32_t grouped_instance =
                span->first_instance + local_instance;
            const float *matrix =
                XzStaticSceneDrawPlan_InstanceMatrix(
                    &xz_shadow.static_draw_plan,
                    grouped_instance);
            float world_min[3];
            float world_max[3];
            float distance;
            int inside = 0;
            unsigned int slot =
                XZ_STATIC_CAMERA_PROBE_MAX;
            unsigned int i;

            if (!matrix)
                continue;

            XzTransformStaticBounds(
                matrix,
                mesh->bounds_min,
                mesh->bounds_max,
                world_min,
                world_max);
            distance =
                XzPointStaticBoundsDistance(
                    camera_origin,
                    world_min,
                    world_max,
                    &inside);

            if (inside)
                state->
                    static_scene_camera_probe_inside_count++;

            for (i = 0u;
                 i < state->
                    static_scene_camera_probe_count;
                 ++i) {
                if (distance <
                    state->
                        static_scene_camera_probe_distance[i]) {
                    slot = i;
                    break;
                }
            }

            if (slot == XZ_STATIC_CAMERA_PROBE_MAX &&
                state->
                    static_scene_camera_probe_count <
                    XZ_STATIC_CAMERA_PROBE_MAX) {
                slot =
                    state->
                        static_scene_camera_probe_count;
            }

            if (slot < XZ_STATIC_CAMERA_PROBE_MAX) {
                unsigned int move_from =
                    state->
                        static_scene_camera_probe_count <
                            XZ_STATIC_CAMERA_PROBE_MAX
                        ? state->
                            static_scene_camera_probe_count
                        : XZ_STATIC_CAMERA_PROBE_MAX - 1u;

                while (move_from > slot) {
                    const unsigned int from =
                        move_from - 1u;
                    unsigned int axis;

                    state->
                        static_scene_camera_probe_mesh[move_from] =
                        state->
                            static_scene_camera_probe_mesh[from];
                    state->
                        static_scene_camera_probe_instance[move_from] =
                        state->
                            static_scene_camera_probe_instance[from];
                    state->
                        static_scene_camera_probe_inside[move_from] =
                        state->
                            static_scene_camera_probe_inside[from];
                    state->
                        static_scene_camera_probe_distance[move_from] =
                        state->
                            static_scene_camera_probe_distance[from];

                    for (axis = 0u; axis < 3u; ++axis) {
                        state->
                            static_scene_camera_probe_bounds_min[move_from][axis] =
                            state->
                                static_scene_camera_probe_bounds_min[from][axis];
                        state->
                            static_scene_camera_probe_bounds_max[move_from][axis] =
                            state->
                                static_scene_camera_probe_bounds_max[from][axis];
                    }

                    move_from--;
                }

                state->
                    static_scene_camera_probe_mesh[slot] =
                    mesh_index;
                state->
                    static_scene_camera_probe_instance[slot] =
                    grouped_instance;
                state->
                    static_scene_camera_probe_inside[slot] =
                    inside ? 1u : 0u;
                state->
                    static_scene_camera_probe_distance[slot] =
                    distance;
                memcpy(
                    state->
                        static_scene_camera_probe_bounds_min[slot],
                    world_min,
                    sizeof(world_min));
                memcpy(
                    state->
                        static_scene_camera_probe_bounds_max[slot],
                    world_max,
                    sizeof(world_max));

                if (state->
                        static_scene_camera_probe_count <
                    XZ_STATIC_CAMERA_PROBE_MAX) {
                    state->
                        static_scene_camera_probe_count++;
                }
            }
        }
    }
}

static int XzDrawStaticScene(
    XzGles3ShadowState *state,
    const XzGeometryFrame *geometry)
{
    XzNativeGles3Api *gl = &xz_shadow.gl;
    const XzGeometryBatch *camera;
    uint32_t mesh_index;
    uint32_t binding_cursor = 0u;
    uint32_t normal_cursor = 0u;
    uint32_t pbr_cursor = 0u;
    unsigned int draw_calls = 0u;
    unsigned int expected_draw_calls = 0u;
    unsigned int baked_lightmap_draw_calls = 0u;
    unsigned int normal_applied = 0u;
    unsigned int textured_draw_calls = 0u;
    unsigned int untextured_draw_calls = 0u;
    float camera_origin[3];
    float local_positions[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX * 4u];
    float local_colors[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX * 4u];
    float local_directions[
        XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX * 4u];
    uint32_t active_local_lights;

    if (!state ||
        !state->static_scene_gpu_ready ||
        !xz_shadow.static_program ||
        !xz_shadow.static_draw_plan_ready ||
        !xz_shadow.static_meshes ||
        !xz_shadow.static_instance_vbo ||
        (state->static_scene_lightmap_shader_ready &&
         (!xz_shadow.static_lightmap_draw_plan_ready ||
          !xz_shadow.static_lightmap_instance_vbo)))
        return 0;

    camera = XzStaticSceneCamera(geometry);
    if (!camera ||
        !XzStaticCameraOrigin(
            camera->modelview,
            camera_origin))
        return 0;

    active_local_lights =
        XzStaticSelectLocalLights(
            camera_origin,
            local_positions,
            local_colors,
            local_directions,
            state);

    if (!state->static_scene_local_lighting_ready ||
        active_local_lights >
            XZ_STATIC_LOCAL_LIGHT_ACTIVE_MAX ||
        state->
            static_scene_local_light_dropped_affecting != 0u)
        return 0;

    state->static_scene_draw_attempts++;
    if (state->static_scene_draw_attempts == 1u)
        XzProbeStaticSceneCamera(
            state,
            camera_origin);
    state->static_scene_frame_ready = 0;
    state->static_scene_last_draw_calls = 0u;
    state->static_scene_last_instances = 0u;
    state->static_scene_last_textured_draw_calls = 0u;
    state->static_scene_last_untextured_draw_calls = 0u;
    state->static_scene_last_normal_bindings = 0u;
    state->static_scene_last_pbr_bindings = 0u;
    state->static_scene_last_specular_local_lights = 0u;
    state->static_scene_last_baked_lightmap_draw_calls = 0u;

    if (state->static_scene_specular_response_ready)
        state->static_scene_last_specular_local_lights =
            active_local_lights;

    gl->UseProgram(xz_shadow.static_program);
    gl->Uniform1i(
        xz_shadow.static_texture_loc,
        0);
    gl->Uniform1i(
        xz_shadow.static_normal_texture_loc,
        1);
    gl->Uniform1i(
        xz_shadow.static_reflection_texture_loc,
        2);
    gl->Uniform1i(
        xz_shadow.static_lightmap_texture_loc,
        3);
    gl->Uniform1i(
        xz_shadow.static_lightmap_enabled_loc,
        0);
    {
        float reflection_params[4] = {
            state->static_scene_reflection_mips > 0u
                ? (float)(
                    state->static_scene_reflection_mips - 1u)
                : 0.0f,
            state->static_scene_reflection_brightness,
            state->static_scene_reflection_average_brightness,
            state->static_scene_reflection_ibl_ready
                ? 1.0f : 0.0f
        };
        gl->Uniform4fv(
            xz_shadow.static_reflection_params_loc,
            1,
            reflection_params);
    }
    {
        float reflection_sphere[4] = {
            state->static_scene_reflection_position_meters[0] *
                XZ_STATIC_GAMEPLAY_UNITS_PER_METER,
            state->static_scene_reflection_position_meters[1] *
                XZ_STATIC_GAMEPLAY_UNITS_PER_METER,
            state->static_scene_reflection_position_meters[2] *
                XZ_STATIC_GAMEPLAY_UNITS_PER_METER,
            state->static_scene_reflection_radius_meters *
                XZ_STATIC_GAMEPLAY_UNITS_PER_METER
        };
        float reflection_offset[3] = {
            state->static_scene_reflection_offset_meters[0] *
                XZ_STATIC_GAMEPLAY_UNITS_PER_METER,
            state->static_scene_reflection_offset_meters[1] *
                XZ_STATIC_GAMEPLAY_UNITS_PER_METER,
            state->static_scene_reflection_offset_meters[2] *
                XZ_STATIC_GAMEPLAY_UNITS_PER_METER
        };
        gl->Uniform4fv(
            xz_shadow.static_reflection_sphere_loc,
            1,
            reflection_sphere);
        gl->Uniform3fv(
            xz_shadow.static_reflection_offset_loc,
            1,
            reflection_offset);
    }
    gl->ActiveTexture(GL_TEXTURE2);
    gl->BindTexture(
        GL_TEXTURE_CUBE_MAP,
        xz_shadow.static_reflection_cubemap);
    gl->ActiveTexture(GL_TEXTURE0);
    gl->UniformMatrix4fv(
        xz_shadow.static_view_loc,
        1,
        GL_FALSE,
        camera->modelview);
    gl->UniformMatrix4fv(
        xz_shadow.static_projection_loc,
        1,
        GL_FALSE,
        camera->projection);
    gl->Uniform1f(
        xz_shadow.static_ambient_weight_loc,
        xz_shadow.static_ambient_weight);
    gl->Uniform1f(
        xz_shadow.static_directional_weight_loc,
        xz_shadow.static_directional_weight);
    gl->Uniform3fv(
        xz_shadow.static_directional_color_loc,
        1,
        xz_shadow.static_directional_color);
    gl->Uniform3fv(
        xz_shadow.static_directional_direction_loc,
        1,
        xz_shadow.static_directional_direction);
    gl->Uniform3fv(
        xz_shadow.static_camera_pos_loc,
        1,
        camera_origin);
    gl->Uniform4fv(
        xz_shadow.static_fog_primary_loc,
        1,
        xz_shadow.static_fog_primary);
    gl->Uniform4fv(
        xz_shadow.static_fog_color_min_loc,
        1,
        xz_shadow.static_fog_color_min);
    gl->Uniform1f(
        xz_shadow.static_fog_cutoff_loc,
        xz_shadow.static_fog_cutoff_cm);
    gl->Uniform1i(
        xz_shadow.static_local_light_count_loc,
        (GLint)active_local_lights);
    if (active_local_lights > 0u) {
        gl->Uniform4fv(
            xz_shadow.static_local_pos_inv_radius_loc,
            (GLsizei)active_local_lights,
            local_positions);
        gl->Uniform4fv(
            xz_shadow.static_local_color_cone_loc,
            (GLsizei)active_local_lights,
            local_colors);
        gl->Uniform4fv(
            xz_shadow.static_local_dir_cos_outer_loc,
            (GLsizei)active_local_lights,
            local_directions);
    }

    gl->Enable(GL_DEPTH_TEST);
    gl->DepthMask(GL_TRUE);
    gl->DepthFunc(GL_LEQUAL);
    gl->DepthRangef(0.0f, 1.0f);
    gl->Disable(GL_BLEND);
    gl->Disable(GL_CULL_FACE);
    gl->Disable(GL_POLYGON_OFFSET_FILL);

    for (mesh_index = 0u;
         mesh_index < xz_shadow.static_mesh_count;
         ++mesh_index) {
        XzGles3StaticMesh *mesh =
            &xz_shadow.static_meshes[mesh_index];
        const XzStaticSceneDrawSpan *span =
            XzStaticSceneDrawPlan_Span(
                &xz_shadow.static_draw_plan,
                mesh_index);
        uint32_t first_lightmap_batch = 0u;
        uint32_t lightmap_batch_count = 0u;
        uint32_t first_material_batch = 0u;
        uint32_t material_batch_count = 0u;
        uint32_t submesh_index;
        const int use_baked_lightmap =
            state->static_scene_lightmap_shader_ready;
        const int use_material_batches =
            !use_baked_lightmap &&
            xz_shadow.static_material_draw_plan_ready;
        const int use_native_materials =
            use_material_batches &&
            state->static_scene_xzml_gpu_ready;

        if (!mesh->alive ||
            !mesh->vao ||
            !mesh->submeshes ||
            !span ||
            span->instance_count == 0u)
            goto fail;

        if (use_baked_lightmap) {
            if (!XzStaticSceneLightmapDrawPlan_MeshBatches(
                    &xz_shadow.static_lightmap_draw_plan,
                    mesh_index,
                    &first_lightmap_batch,
                    &lightmap_batch_count) ||
                lightmap_batch_count == 0u)
                goto fail;

            expected_draw_calls +=
                mesh->submesh_count *
                lightmap_batch_count;
        } else if (use_material_batches) {
            if (!XzStaticSceneMaterialDrawPlan_MeshBatches(
                    &xz_shadow.static_material_draw_plan,
                    mesh_index,
                    &first_material_batch,
                    &material_batch_count) ||
                material_batch_count == 0u)
                goto fail;

            expected_draw_calls +=
                mesh->submesh_count *
                material_batch_count;
        } else {
            expected_draw_calls +=
                mesh->submesh_count;
        }

        gl->BindVertexArray(mesh->vao);

        for (submesh_index = 0u;
             submesh_index < mesh->submesh_count;
             ++submesh_index) {
            const XzXzmeshSubmesh *submesh =
                &mesh->submeshes[submesh_index];

            uint32_t texture_index =
                XZ_STATIC_MATERIAL_NO_TEXTURE;
            uint32_t normal_texture_index =
                XZ_STATIC_MATERIAL_NO_TEXTURE;
            XzPbrMaterialBinding pbr_binding = {
                0u, 0.75f, 0.0f, 0.5f, 0.0f
            };
            float pbr_params[4] = {
                0.75f, 0.0f, 0.5f, 0.0f
            };
            int has_texture = 0;
            int has_normal = 0;

            if (submesh->index_count == 0u ||
                submesh->first_index +
                    submesh->index_count >
                    mesh->index_count)
                goto fail;

            gl->ActiveTexture(GL_TEXTURE0);

            if (state->static_scene_material_ready &&
                !use_native_materials) {
                if (binding_cursor >=
                        xz_shadow.static_material_binding_count)
                    goto fail;

                texture_index =
                    xz_shadow.static_material_bindings[
                        binding_cursor];

                if (texture_index !=
                        XZ_STATIC_MATERIAL_NO_TEXTURE) {
                    if (texture_index >=
                            xz_shadow.static_texture_count ||
                        !xz_shadow.static_textures[
                            texture_index].alive ||
                        !xz_shadow.static_textures[
                            texture_index].object)
                        goto fail;

                    gl->BindTexture(
                        GL_TEXTURE_2D,
                        xz_shadow.static_textures[
                            texture_index].object);
                    has_texture = 1;
                } else {
                    gl->BindTexture(
                        GL_TEXTURE_2D,
                        0u);
                }

                binding_cursor++;
            } else {
                gl->BindTexture(
                    GL_TEXTURE_2D,
                    0u);
            }

            if (state->static_scene_normal_ready &&
                !use_native_materials) {
                if (normal_cursor >=
                        xz_shadow.static_normal_binding_count)
                    goto fail;

                normal_texture_index =
                    xz_shadow.static_normal_bindings[
                        normal_cursor++];

                gl->ActiveTexture(GL_TEXTURE1);
                if (normal_texture_index !=
                        XZ_STATIC_MATERIAL_NO_TEXTURE) {
                    if (normal_texture_index >=
                            xz_shadow.static_normal_texture_count ||
                        !xz_shadow.static_normal_textures[
                            normal_texture_index].alive ||
                        !xz_shadow.static_normal_textures[
                            normal_texture_index].object)
                        goto fail;

                    gl->BindTexture(
                        GL_TEXTURE_2D,
                        xz_shadow.static_normal_textures[
                            normal_texture_index].object);
                    has_normal = 1;
                    normal_applied++;
                } else {
                    gl->BindTexture(
                        GL_TEXTURE_2D,
                        0u);
                }
                gl->ActiveTexture(GL_TEXTURE0);
            }

            if (state->static_scene_pbr_ready &&
                !use_native_materials) {
                if (pbr_cursor >=
                        xz_shadow.static_pbr_binding_count)
                    goto fail;

                pbr_binding =
                    xz_shadow.static_pbr_bindings[
                        pbr_cursor++];
                pbr_params[0] = pbr_binding.roughness;
                pbr_params[1] = pbr_binding.metallic;
                pbr_params[2] = pbr_binding.specular;
                pbr_params[3] = pbr_binding.emissive;
            }

            gl->Uniform1i(
                xz_shadow.static_texture_enabled_loc,
                has_texture);
            gl->Uniform1i(
                xz_shadow.static_normal_texture_enabled_loc,
                has_normal);
            gl->Uniform4fv(
                xz_shadow.static_pbr_params_loc,
                1,
                pbr_params);
            gl->Uniform1i(
                xz_shadow.static_pbr_flags_loc,
                (GLint)pbr_binding.flags);
            gl->Uniform1i(
                xz_shadow.static_material_shading_mode_loc,
                -1);
            gl->Uniform1i(
                xz_shadow.static_material_blend_mode_loc,
                -1);
            gl->Uniform1f(
                xz_shadow.static_material_opacity_loc,
                1.0f);
            gl->Uniform1f(
                xz_shadow.static_opacity_mask_clip_loc,
                0.333f);

            if (use_baked_lightmap) {
                uint32_t lightmap_batch_offset;

                for (lightmap_batch_offset = 0u;
                     lightmap_batch_offset <
                        lightmap_batch_count;
                     ++lightmap_batch_offset) {
                    const XzStaticSceneLightmapBatch *batch =
                        XzStaticSceneLightmapDrawPlan_Batch(
                            &xz_shadow.static_lightmap_draw_plan,
                            first_lightmap_batch +
                                lightmap_batch_offset);
                    int has_lightmap = 0;

                    if (!batch ||
                        batch->mesh_index != mesh_index ||
                        batch->instance_count == 0u ||
                        !XzBindStaticInstanceRange(
                            mesh,
                            batch->first_grouped_instance))
                        goto fail;

                    gl->ActiveTexture(GL_TEXTURE3);
                    if (batch->mapped) {
                        const uint32_t lightmap_texture_index =
                            batch->light_texture[0];

                        if (lightmap_texture_index >=
                                xz_shadow.static_lightmap_texture_count ||
                            !xz_shadow.static_lightmap_textures ||
                            !xz_shadow.static_lightmap_textures[
                                lightmap_texture_index].alive ||
                            !xz_shadow.static_lightmap_textures[
                                lightmap_texture_index].object)
                            goto fail;

                        gl->BindTexture(
                            GL_TEXTURE_2D,
                            xz_shadow.static_lightmap_textures[
                                lightmap_texture_index].object);
                        has_lightmap = 1;
                        baked_lightmap_draw_calls++;
                    } else {
                        gl->BindTexture(
                            GL_TEXTURE_2D,
                            0u);
                    }

                    gl->Uniform1i(
                        xz_shadow.static_lightmap_enabled_loc,
                        has_lightmap);
                    gl->ActiveTexture(GL_TEXTURE0);

                    if (has_texture)
                        textured_draw_calls++;
                    else
                        untextured_draw_calls++;

                    gl->DrawElementsInstanced(
                        GL_TRIANGLES,
                        (GLsizei)submesh->index_count,
                        GL_UNSIGNED_INT,
                        (const void *)(uintptr_t)(
                            (uint64_t)submesh->first_index *
                            sizeof(uint32_t)),
                        (GLsizei)batch->instance_count);
                    draw_calls++;
                }
            } else if (use_material_batches) {
                uint32_t material_batch_offset;

                gl->Uniform1i(
                    xz_shadow.static_lightmap_enabled_loc,
                    0);

                for (material_batch_offset = 0u;
                     material_batch_offset <
                        material_batch_count;
                     ++material_batch_offset) {
                    const XzStaticSceneMaterialBatch *batch =
                        XzStaticSceneMaterialDrawPlan_Batch(
                            &xz_shadow.static_material_draw_plan,
                            first_material_batch +
                                material_batch_offset);

                    if (!batch ||
                        batch->mesh_index != mesh_index ||
                        batch->instance_count == 0u ||
                        !XzBindStaticMatrixInstanceRange(
                            mesh,
                            batch->first_grouped_instance))
                        goto fail;

                    if (use_native_materials) {
                        const uint32_t global_batch =
                            first_material_batch +
                            material_batch_offset;
                        uint32_t binding_offset;
                        uint32_t material_index;
                        const XzGles3NativeMaterial *material;

                        if (!xz_shadow.static_native_material_ready ||
                            !xz_shadow.static_native_materials ||
                            !xz_shadow.static_material_batch_offsets ||
                            !xz_shadow.static_material_batch_materials ||
                            global_batch >=
                                xz_shadow.static_material_draw_plan.batch_count)
                            goto fail;

                        binding_offset =
                            xz_shadow.static_material_batch_offsets[
                                global_batch];

                        if ((uint64_t)binding_offset +
                                (uint64_t)submesh_index >=
                            (uint64_t)xz_shadow
                                .static_material_batch_binding_count)
                            goto fail;

                        material_index =
                            xz_shadow.static_material_batch_materials[
                                binding_offset +
                                    submesh_index];

                        if (material_index >=
                                xz_shadow.static_native_material_count)
                            goto fail;

                        material =
                            &xz_shadow.static_native_materials[
                                material_index];

                        has_texture = 0;
                        has_normal = 0;
                        texture_index =
                            material->canonical_texture[0];
                        normal_texture_index =
                            material->canonical_texture[1];

                        gl->ActiveTexture(GL_TEXTURE0);
                        if (texture_index !=
                                XZ_XZML_NO_TEXTURE) {
                            if (texture_index >=
                                    xz_shadow.static_texture_count ||
                                !xz_shadow.static_textures ||
                                !xz_shadow.static_textures[
                                    texture_index].alive ||
                                !xz_shadow.static_textures[
                                    texture_index].object)
                                goto fail;

                            gl->BindTexture(
                                GL_TEXTURE_2D,
                                xz_shadow.static_textures[
                                    texture_index].object);
                            has_texture = 1;
                        } else {
                            gl->BindTexture(
                                GL_TEXTURE_2D,
                                0u);
                        }

                        gl->ActiveTexture(GL_TEXTURE1);
                        if (normal_texture_index !=
                                XZ_XZML_NO_TEXTURE &&
                            material->shading_mode !=
                                XZ_NATIVE_SHADING_UNLIT) {
                            if (normal_texture_index >=
                                    xz_shadow.static_texture_count ||
                                !xz_shadow.static_textures ||
                                !xz_shadow.static_textures[
                                    normal_texture_index].alive ||
                                !xz_shadow.static_textures[
                                    normal_texture_index].object)
                                goto fail;

                            gl->BindTexture(
                                GL_TEXTURE_2D,
                                xz_shadow.static_textures[
                                    normal_texture_index].object);
                            has_normal = 1;
                            normal_applied++;
                        } else {
                            gl->BindTexture(
                                GL_TEXTURE_2D,
                                0u);
                        }

                        pbr_params[0] = material->roughness;
                        pbr_params[1] = material->metallic;
                        pbr_params[2] = material->specular;
                        pbr_params[3] = material->emissive;

                        gl->ActiveTexture(GL_TEXTURE0);
                        gl->Uniform1i(
                            xz_shadow.static_texture_enabled_loc,
                            has_texture);
                        gl->Uniform1i(
                            xz_shadow.static_normal_texture_enabled_loc,
                            has_normal);
                        gl->Uniform4fv(
                            xz_shadow.static_pbr_params_loc,
                            1,
                            pbr_params);
                        gl->Uniform1i(
                            xz_shadow.static_pbr_flags_loc,
                            (GLint)material->pbr_flags);
                        gl->Uniform1i(
                            xz_shadow.static_material_shading_mode_loc,
                            (GLint)material->shading_mode);
                        gl->Uniform1i(
                            xz_shadow.static_material_blend_mode_loc,
                            (GLint)material->blend_mode);
                        gl->Uniform1f(
                            xz_shadow.static_material_opacity_loc,
                            material->opacity);
                        gl->Uniform1f(
                            xz_shadow.static_opacity_mask_clip_loc,
                            material->opacity_mask_clip);

                        if (material->disable_depth_test)
                            gl->Disable(GL_DEPTH_TEST);
                        else
                            gl->Enable(GL_DEPTH_TEST);

                        if (material->blend_mode ==
                                XZ_NATIVE_BLEND_TRANSLUCENT) {
                            gl->Enable(GL_BLEND);
                            gl->BlendFunc(
                                GL_SRC_ALPHA,
                                GL_ONE_MINUS_SRC_ALPHA);
                            gl->DepthMask(GL_FALSE);
                        } else {
                            gl->Disable(GL_BLEND);
                            gl->DepthMask(GL_TRUE);
                        }

                        if (material->two_sided) {
                            gl->Disable(GL_CULL_FACE);
                        } else {
                            gl->Enable(GL_CULL_FACE);
                            gl->CullFace(GL_BACK);
                            /*
                             * UE source triangles are clockwise relative to
                             * authored outward normals. XZMS mirrors Y and
                             * swaps B/C, preserving that source front-face
                             * orientation exactly.
                             */
                            gl->FrontFace(GL_CW);
                        }
                    }

                    if (has_texture)
                        textured_draw_calls++;
                    else
                        untextured_draw_calls++;

                    gl->DrawElementsInstanced(
                        GL_TRIANGLES,
                        (GLsizei)submesh->index_count,
                        GL_UNSIGNED_INT,
                        (const void *)(uintptr_t)(
                            (uint64_t)submesh->first_index *
                            sizeof(uint32_t)),
                        (GLsizei)batch->instance_count);
                    draw_calls++;
                }
            } else {
                gl->Uniform1i(
                    xz_shadow.static_lightmap_enabled_loc,
                    0);

                if (has_texture)
                    textured_draw_calls++;
                else
                    untextured_draw_calls++;

                gl->DrawElementsInstanced(
                    GL_TRIANGLES,
                    (GLsizei)submesh->index_count,
                    GL_UNSIGNED_INT,
                    (const void *)(uintptr_t)(
                        (uint64_t)submesh->first_index *
                        sizeof(uint32_t)),
                    (GLsizei)span->instance_count);
                draw_calls++;
            }
        }
    }

    gl->Enable(GL_DEPTH_TEST);
    gl->DepthMask(GL_TRUE);
    gl->Disable(GL_BLEND);
    gl->Disable(GL_CULL_FACE);
    gl->FrontFace(GL_CCW);

    if (gl->GetError() != GL_NO_ERROR)
        goto fail;

    gl->BindVertexArray(0u);
    gl->UseProgram(0u);

    state->static_scene_last_draw_calls =
        draw_calls;
    state->static_scene_last_instances =
        state->static_scene_lightmap_shader_ready
            ? xz_shadow.static_lightmap_draw_plan.instance_count
            : (xz_shadow.static_material_draw_plan_ready
                ? xz_shadow.static_material_draw_plan.instance_count
                : xz_shadow.static_draw_plan.instance_count);
    state->static_scene_last_baked_lightmap_draw_calls =
        baked_lightmap_draw_calls;
    state->static_scene_last_textured_draw_calls =
        textured_draw_calls;
    state->static_scene_last_untextured_draw_calls =
        untextured_draw_calls;
    state->static_scene_last_normal_bindings =
        normal_applied;
    state->static_scene_last_pbr_bindings =
        pbr_cursor;
    state->static_scene_frame_ready =
        expected_draw_calls > 0u &&
        draw_calls == expected_draw_calls &&
        state->static_scene_last_instances ==
            xz_shadow.static_draw_plan.instance_count &&
        (!state->static_scene_lightmap_shader_ready ||
         baked_lightmap_draw_calls > 0u) &&
        (!state->static_scene_material_ready ||
         state->static_scene_xzml_gpu_ready ||
         binding_cursor ==
            xz_shadow.static_material_binding_count) &&
        (!state->static_scene_normal_ready ||
         normal_cursor ==
            xz_shadow.static_normal_binding_count) &&
        (!state->static_scene_pbr_ready ||
         pbr_cursor ==
            xz_shadow.static_pbr_binding_count) &&
        (!state->static_scene_specular_response_ready ||
         state->static_scene_last_specular_local_lights ==
            active_local_lights);

    if (!state->static_scene_frame_ready)
        goto fail_no_state_reset;

    state->static_scene_draw_successes++;
    return 1;

fail:
    gl->BindVertexArray(0u);
    gl->UseProgram(0u);
    XzDrainErrors(state);

fail_no_state_reset:
    state->static_scene_frame_ready = 0;
    state->static_scene_draw_failures++;
    return 0;
}

static int XzCreateVisibleContext(
    EGLSurface window_draw,
    EGLSurface window_read,
    EGLContext legacy_context)
{
    EGLint config_id = 0;
    EGLint count = 0;
    const EGLint context_attribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3,
        EGL_NONE
    };
    EGLint config_attribs[3];

    if (window_draw == EGL_NO_SURFACE ||
        legacy_context == EGL_NO_CONTEXT)
        return 0;

    xz_shadow.visible_context = EGL_NO_CONTEXT;
    xz_shadow.visible_context_owned = 0;
    xz_shadow.visible_vao = 0u;

    if (eglQueryContext(
            xz_shadow.display,
            legacy_context,
            EGL_CONFIG_ID,
            &config_id)) {
        config_attribs[0] = EGL_CONFIG_ID;
        config_attribs[1] = config_id;
        config_attribs[2] = EGL_NONE;

        if (eglChooseConfig(
                xz_shadow.display,
                config_attribs,
                &xz_shadow.visible_config,
                1,
                &count) &&
            count >= 1) {
            xz_shadow.visible_context = eglCreateContext(
                xz_shadow.display,
                xz_shadow.visible_config,
                xz_shadow.context,
                context_attribs);
        }
    }

    if (xz_shadow.visible_context != EGL_NO_CONTEXT) {
        xz_shadow.visible_context_owned = 1;

        if (eglMakeCurrent(
                xz_shadow.display,
                window_draw,
                window_read,
                xz_shadow.visible_context)) {
            xz_shadow.gl.GenVertexArrays(
                1, &xz_shadow.visible_vao);

            if (xz_shadow.visible_vao &&
                eglMakeCurrent(
                    xz_shadow.display,
                    xz_shadow.surface,
                    xz_shadow.surface,
                    xz_shadow.context))
                return 1;
        }

        eglMakeCurrent(
            xz_shadow.display,
            xz_shadow.surface,
            xz_shadow.surface,
            xz_shadow.context);
        eglDestroyContext(
            xz_shadow.display,
            xz_shadow.visible_context);
        xz_shadow.visible_context = EGL_NO_CONTEXT;
        xz_shadow.visible_context_owned = 0;
        xz_shadow.visible_vao = 0u;
    }

    /*
     * Some Android EGL stacks reject context sharing across configs even
     * though the ES3 pbuffer context itself is window-surface compatible.
     * Test that path explicitly before giving up.
     */
    if (eglMakeCurrent(
            xz_shadow.display,
            window_draw,
            window_read,
            xz_shadow.context)) {
        xz_shadow.visible_context =
            xz_shadow.context;
        xz_shadow.visible_context_owned = 0;
        xz_shadow.visible_vao = xz_shadow.vao;

        if (eglMakeCurrent(
                xz_shadow.display,
                xz_shadow.surface,
                xz_shadow.surface,
                xz_shadow.context))
            return 1;
    }

    xz_shadow.visible_context = EGL_NO_CONTEXT;
    xz_shadow.visible_vao = 0u;
    eglMakeCurrent(
        xz_shadow.display,
        xz_shadow.surface,
        xz_shadow.surface,
        xz_shadow.context);
    return 0;
}

static void XzDestroyVisibleTargets(void)
{
    XzNativeGles3Api *gl = &xz_shadow.gl;

    if (xz_shadow.visible_fbo)
        gl->DeleteFramebuffers(
            1, &xz_shadow.visible_fbo);
    if (xz_shadow.visible_color)
        gl->DeleteTextures(
            1, &xz_shadow.visible_color);
    if (xz_shadow.visible_depth)
        gl->DeleteTextures(
            1, &xz_shadow.visible_depth);

    xz_shadow.visible_fbo = 0u;
    xz_shadow.visible_color = 0u;
    xz_shadow.visible_depth = 0u;
    xz_shadow.visible_width = 0u;
    xz_shadow.visible_height = 0u;
}

static int XzEnsureVisibleTargets(
    unsigned int width,
    unsigned int height)
{
    XzNativeGles3Api *gl = &xz_shadow.gl;
    GLenum status;

    if (width == 0u || height == 0u)
        return 0;

    if (xz_shadow.visible_fbo &&
        xz_shadow.visible_color &&
        xz_shadow.visible_depth &&
        xz_shadow.visible_width == width &&
        xz_shadow.visible_height == height)
        return 1;

    XzDestroyVisibleTargets();

    gl->GenTextures(1, &xz_shadow.visible_color);
    gl->BindTexture(
        GL_TEXTURE_2D,
        xz_shadow.visible_color);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_MIN_FILTER,
        GL_LINEAR);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_MAG_FILTER,
        GL_LINEAR);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_WRAP_S,
        GL_CLAMP_TO_EDGE);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_WRAP_T,
        GL_CLAMP_TO_EDGE);
    gl->TexImage2D(
        GL_TEXTURE_2D,
        0,
        GL_RGBA8,
        (GLsizei)width,
        (GLsizei)height,
        0,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        NULL);

    gl->GenTextures(1, &xz_shadow.visible_depth);
    gl->BindTexture(
        GL_TEXTURE_2D,
        xz_shadow.visible_depth);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_MIN_FILTER,
        GL_NEAREST);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_MAG_FILTER,
        GL_NEAREST);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_WRAP_S,
        GL_CLAMP_TO_EDGE);
    gl->TexParameteri(
        GL_TEXTURE_2D,
        GL_TEXTURE_WRAP_T,
        GL_CLAMP_TO_EDGE);
    gl->TexImage2D(
        GL_TEXTURE_2D,
        0,
        GL_DEPTH_COMPONENT24,
        (GLsizei)width,
        (GLsizei)height,
        0,
        GL_DEPTH_COMPONENT,
        GL_UNSIGNED_INT,
        NULL);

    gl->GenFramebuffers(
        1, &xz_shadow.visible_fbo);
    gl->BindFramebuffer(
        GL_FRAMEBUFFER,
        xz_shadow.visible_fbo);
    gl->FramebufferTexture2D(
        GL_FRAMEBUFFER,
        GL_COLOR_ATTACHMENT0,
        GL_TEXTURE_2D,
        xz_shadow.visible_color,
        0);
    gl->FramebufferTexture2D(
        GL_FRAMEBUFFER,
        GL_DEPTH_ATTACHMENT,
        GL_TEXTURE_2D,
        xz_shadow.visible_depth,
        0);

    status = gl->CheckFramebufferStatus(
        GL_FRAMEBUFFER);
    gl->BindFramebuffer(GL_FRAMEBUFFER, 0u);
    gl->BindTexture(GL_TEXTURE_2D, 0u);

    if (status != GL_FRAMEBUFFER_COMPLETE ||
        gl->GetError() != GL_NO_ERROR) {
        XzDestroyVisibleTargets();
        return 0;
    }

    xz_shadow.visible_width = width;
    xz_shadow.visible_height = height;
    return 1;
}

static void XzEncodePlanColor(
    uint32_t hash,
    unsigned char rgba[4])
{
    rgba[0] = (unsigned char)(hash & 0xffu);
    rgba[1] = (unsigned char)((hash >> 8) & 0xffu);
    rgba[2] = (unsigned char)((hash >> 16) & 0xffu);
    rgba[3] = 255u;
}

static int XzReadbackMatches(
    const unsigned char expected[4],
    const unsigned char actual[4])
{
    return XzAbsByteDiff(expected[0], actual[0]) <= 2u &&
           XzAbsByteDiff(expected[1], actual[1]) <= 2u &&
           XzAbsByteDiff(expected[2], actual[2]) <= 2u &&
           XzAbsByteDiff(expected[3], actual[3]) <= 2u;
}

static void XzDrainErrors(
    XzGles3ShadowState *state)
{
    GLenum error;

    do {
        error = xz_shadow.gl.GetError();
        if (error != GL_NO_ERROR)
            state->preexisting_errors++;
    } while (error != GL_NO_ERROR);
}

static GLenum XzCaptureError(
    XzGles3ShadowState *state,
    unsigned int stage)
{
    GLenum error = xz_shadow.gl.GetError();

    if (error != GL_NO_ERROR &&
        state->last_error_stage == XZ_G3_STAGE_NONE) {
        state->last_gl_error = (unsigned int)error;
        state->last_error_stage = stage;
    }

    return error;
}

static int XzTextureFormat(
    uint32_t logical_format,
    GLint *internal_format,
    GLenum *format,
    GLenum *type)
{
    if (!internal_format || !format || !type)
        return 0;

    switch ((XzRgFormat)logical_format) {
    case XZ_RG_FORMAT_RGBA16F:
        *internal_format = GL_RGBA16F;
        *format = GL_RGBA;
        *type = GL_HALF_FLOAT;
        return 1;

    case XZ_RG_FORMAT_RG16F:
        *internal_format = GL_RG16F;
        *format = GL_RG;
        *type = GL_HALF_FLOAT;
        return 1;

    case XZ_RG_FORMAT_RGBA8:
    case XZ_RG_FORMAT_UNKNOWN:
        *internal_format = GL_RGBA8;
        *format = GL_RGBA;
        *type = GL_UNSIGNED_BYTE;
        return 1;

    case XZ_RG_FORMAT_DEPTH16:
    case XZ_RG_FORMAT_DEPTH24:
    default:
        return 0;
    }
}

static GLenum XzDepthInternalFormat(
    uint32_t logical_format)
{
    return logical_format == XZ_RG_FORMAT_DEPTH16
        ? GL_DEPTH_COMPONENT16
        : GL_DEPTH_COMPONENT24;
}

static void XzDestroyPhysicalResource(
    XzGles3ShadowState *state,
    unsigned int index)
{
    XzGles3PhysicalResource *resource;

    if (!state || index >= XZ_GPU_MAX_RESOURCES)
        return;

    resource = &xz_shadow.physical[index];
    if (!resource->alive)
        return;

    if (resource->object != 0u) {
        if (resource->spec.kind ==
                XZ_G3_RESOURCE_TEXTURE_2D ||
            resource->spec.kind ==
                XZ_G3_RESOURCE_DEPTH_TEXTURE) {
            xz_shadow.gl.DeleteTextures(
                1, &resource->object);
        }

        if (state->physical_gl_objects > 0u)
            state->physical_gl_objects--;
    }

    if (state->physical_alive > 0u)
        state->physical_alive--;

    if (state->physical_bytes >=
        resource->spec.physical_bytes)
        state->physical_bytes -=
            resource->spec.physical_bytes;
    else
        state->physical_bytes = 0u;

    state->physical_destroys++;
    memset(resource, 0, sizeof(*resource));
}

static int XzBindPhysicalResource(
    XzGles3ShadowState *state,
    XzGles3PhysicalResource *resource,
    int for_write)
{
    GLenum error;

    if (!state || !resource || !resource->alive)
        return 0;

    switch (resource->spec.kind) {
    case XZ_G3_RESOURCE_TEXTURE_2D:
    case XZ_G3_RESOURCE_DEPTH_TEXTURE:
        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D,
            resource->object);
        break;

    case XZ_G3_RESOURCE_EXTERNAL_SURFACE:
        break;

    case XZ_G3_RESOURCE_INVALID:
    default:
        state->physical_failures++;
        return 0;
    }

    error = xz_shadow.gl.GetError();
    if (error != GL_NO_ERROR) {
        state->physical_failures++;
        if (state->last_gl_error == 0u)
            state->last_gl_error =
                (unsigned int)error;
        return 0;
    }

    if (for_write)
        state->physical_write_binds++;
    else
        state->physical_read_binds++;

    return 1;
}

static int XzEnsurePhysicalResource(
    XzGles3ShadowState *state,
    XzGpuResourcePool *pool,
    XzGpuHandle handle,
    int for_write)
{
    const XzGpuResourceDesc *desc;
    XzGles3PhysicalResource *resource;
    XzGles3ResourceSpec spec;
    unsigned int index;
    GLuint object = 0u;
    GLenum error;

    if (!state || !pool ||
        handle == XZ_GPU_INVALID_HANDLE) {
        if (state)
            state->physical_failures++;
        return 0;
    }

    index = XzGpuHandle_Index(handle);
    if (index >= XZ_GPU_MAX_RESOURCES) {
        state->physical_failures++;
        return 0;
    }

    desc = XzGpuResource_Resolve(pool, handle);
    if (!desc) {
        state->physical_failures++;
        return 0;
    }

    resource = &xz_shadow.physical[index];

    if (resource->alive &&
        resource->handle == handle) {
        state->physical_reuses++;
        return XzBindPhysicalResource(
            state, resource, for_write);
    }

    if (resource->alive)
        XzDestroyPhysicalResource(state, index);

    if (!XzGles3ResourcePlan_Build(
            desc,
            state->resource_proxy_max > 0u
                ? state->resource_proxy_max
                : XZ_G3_RESOURCE_PROXY_MAX,
            &spec)) {
        state->physical_failures++;
        return 0;
    }

    if (spec.kind == XZ_G3_RESOURCE_TEXTURE_2D) {
        GLint internal_format;
        GLenum format;
        GLenum type;

        if (!XzTextureFormat(
                spec.logical_format,
                &internal_format,
                &format,
                &type)) {
            state->physical_failures++;
            return 0;
        }

        xz_shadow.gl.GenTextures(1, &object);
        if (!object) {
            state->physical_failures++;
            return 0;
        }

        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D, object);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MIN_FILTER,
            GL_NEAREST);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_NEAREST);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_S,
            GL_CLAMP_TO_EDGE);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_T,
            GL_CLAMP_TO_EDGE);
        xz_shadow.gl.TexImage2D(
            GL_TEXTURE_2D,
            0,
            internal_format,
            (GLsizei)spec.physical_width,
            (GLsizei)spec.physical_height,
            0,
            format,
            type,
            NULL);
    } else if (
        spec.kind ==
        XZ_G3_RESOURCE_DEPTH_TEXTURE) {
        GLenum depth_type =
            spec.logical_format ==
                XZ_RG_FORMAT_DEPTH16
                ? GL_UNSIGNED_SHORT
                : GL_UNSIGNED_INT;

        xz_shadow.gl.GenTextures(1, &object);
        if (!object) {
            state->physical_failures++;
            return 0;
        }

        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D, object);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MIN_FILTER,
            GL_NEAREST);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_MAG_FILTER,
            GL_NEAREST);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_S,
            GL_CLAMP_TO_EDGE);
        xz_shadow.gl.TexParameteri(
            GL_TEXTURE_2D,
            GL_TEXTURE_WRAP_T,
            GL_CLAMP_TO_EDGE);
        xz_shadow.gl.TexImage2D(
            GL_TEXTURE_2D,
            0,
            (GLint)XzDepthInternalFormat(
                spec.logical_format),
            (GLsizei)spec.physical_width,
            (GLsizei)spec.physical_height,
            0,
            GL_DEPTH_COMPONENT,
            depth_type,
            NULL);
    } else if (
        spec.kind !=
        XZ_G3_RESOURCE_EXTERNAL_SURFACE) {
        state->physical_failures++;
        return 0;
    }

    error = xz_shadow.gl.GetError();
    if (error != GL_NO_ERROR) {
        if (object != 0u) {
            if (spec.kind ==
                    XZ_G3_RESOURCE_TEXTURE_2D ||
                spec.kind ==
                    XZ_G3_RESOURCE_DEPTH_TEXTURE)
                xz_shadow.gl.DeleteTextures(
                    1, &object);
        }

        state->physical_failures++;
        if (state->last_gl_error == 0u)
            state->last_gl_error =
                (unsigned int)error;
        return 0;
    }

    memset(resource, 0, sizeof(*resource));
    resource->handle = handle;
    resource->spec = spec;
    resource->object = object;
    resource->alive = 1;

    state->physical_alive++;
    if (object != 0u)
        state->physical_gl_objects++;
    state->physical_creates++;
    state->physical_bytes += spec.physical_bytes;

    return XzBindPhysicalResource(
        state, resource, for_write);
}

static void XzDestroyAllPhysicalResources(
    XzGles3ShadowState *state)
{
    unsigned int i;

    if (!state)
        return;

    for (i = 0u; i < XZ_GPU_MAX_RESOURCES; ++i)
        XzDestroyPhysicalResource(state, i);
}

static XzGles3PhysicalResource *XzPhysicalForHandle(
    XzGpuHandle handle)
{
    unsigned int index;

    if (handle == XZ_GPU_INVALID_HANDLE)
        return NULL;

    index = XzGpuHandle_Index(handle);
    if (index >= XZ_GPU_MAX_RESOURCES)
        return NULL;

    if (!xz_shadow.physical[index].alive ||
        xz_shadow.physical[index].handle != handle)
        return NULL;

    return &xz_shadow.physical[index];
}

static int XzBindPassTarget(
    XzGles3ShadowState *state,
    const XzPassTarget *target)
{
    XzGles3PhysicalResource *color = NULL;
    XzGles3PhysicalResource *depth = NULL;
    XzGles3PhysicalResource *external = NULL;
    unsigned int width = XZ_SHADOW_WIDTH;
    unsigned int height = XZ_SHADOW_HEIGHT;
    GLbitfield clear_mask = 0u;
    GLenum status;
    GLenum error;

    if (!state || !target)
        return 0;

    if (target->external != XZ_GPU_INVALID_HANDLE) {
        external = XzPhysicalForHandle(target->external);
        if (!external ||
            external->spec.kind !=
                XZ_G3_RESOURCE_EXTERNAL_SURFACE) {
            state->framebuffer_failures++;
            return 0;
        }

        xz_shadow.gl.BindFramebuffer(
            GL_FRAMEBUFFER, 0u);
        xz_shadow.gl.Viewport(
            0, 0, XZ_SHADOW_WIDTH, XZ_SHADOW_HEIGHT);
        xz_shadow.gl.ClearColor(
            0.015f, 0.020f, 0.025f, 1.0f);
        xz_shadow.gl.Clear(GL_COLOR_BUFFER_BIT);

        state->framebuffer_binds++;
        state->framebuffer_external_passes++;

        error = xz_shadow.gl.GetError();
        if (error != GL_NO_ERROR) {
            state->framebuffer_failures++;
            return 0;
        }

        return 1;
    }

    if (target->color != XZ_GPU_INVALID_HANDLE) {
        color = XzPhysicalForHandle(target->color);
        if (!color ||
            color->spec.kind !=
                XZ_G3_RESOURCE_TEXTURE_2D) {
            state->framebuffer_failures++;
            return 0;
        }
        width = color->spec.physical_width;
        height = color->spec.physical_height;
        clear_mask |= GL_COLOR_BUFFER_BIT;
    }

    if (target->depth != XZ_GPU_INVALID_HANDLE) {
        depth = XzPhysicalForHandle(target->depth);
        if (!depth ||
            depth->spec.kind !=
                XZ_G3_RESOURCE_DEPTH_TEXTURE) {
            state->framebuffer_failures++;
            return 0;
        }

        if (!color) {
            width = depth->spec.physical_width;
            height = depth->spec.physical_height;
        } else {
            if (depth->spec.physical_width < width)
                width = depth->spec.physical_width;
            if (depth->spec.physical_height < height)
                height = depth->spec.physical_height;
        }

        clear_mask |= GL_DEPTH_BUFFER_BIT;
    }

    if (!color && !depth) {
        state->framebuffer_failures++;
        return 0;
    }

    xz_shadow.gl.BindFramebuffer(
        GL_FRAMEBUFFER,
        xz_shadow.scratch_fbo);

    xz_shadow.gl.FramebufferTexture2D(
        GL_FRAMEBUFFER,
        GL_COLOR_ATTACHMENT0,
        GL_TEXTURE_2D,
        color ? color->object : 0u,
        0);

    xz_shadow.gl.FramebufferTexture2D(
        GL_FRAMEBUFFER,
        GL_DEPTH_ATTACHMENT,
        GL_TEXTURE_2D,
        depth ? depth->object : 0u,
        0);

    state->framebuffer_binds++;
    if (color)
        state->framebuffer_color_attachments++;
    if (depth)
        state->framebuffer_depth_attachments++;

    status = xz_shadow.gl.CheckFramebufferStatus(
        GL_FRAMEBUFFER);
    state->framebuffer_checks++;

    if (status != GL_FRAMEBUFFER_COMPLETE) {
        state->framebuffer_failures++;
        return 0;
    }

    xz_shadow.gl.Viewport(
        0, 0, (GLsizei)width, (GLsizei)height);
    xz_shadow.gl.ClearColor(
        0.010f, 0.015f, 0.020f, 1.0f);
    xz_shadow.gl.Clear(clear_mask);

    error = xz_shadow.gl.GetError();
    if (error != GL_NO_ERROR) {
        state->framebuffer_failures++;
        return 0;
    }

    return 1;
}

static int XzDrawSampledPass(
    XzGles3ShadowState *state,
    const XzPassInput *input)
{
    unsigned int i;
    GLenum error;

    if (!state || !input || input->count == 0u)
        return 0;

    if (input->count > 2u) {
        state->sampled_failures++;
        return 0;
    }

    for (i = 0u; i < input->count; ++i) {
        XzGles3PhysicalResource *resource =
            XzPhysicalForHandle(input->handles[i]);

        if (!resource ||
            (resource->spec.kind !=
                 XZ_G3_RESOURCE_TEXTURE_2D &&
             resource->spec.kind !=
                 XZ_G3_RESOURCE_DEPTH_TEXTURE)) {
            state->sampled_failures++;
            return 0;
        }

        xz_shadow.gl.ActiveTexture(
            GL_TEXTURE0 + (GLenum)i);
        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D,
            resource->object);
        state->sampled_input_binds++;
    }

    xz_shadow.gl.UseProgram(
        xz_shadow.fullscreen_program);
    xz_shadow.gl.Uniform1i(
        xz_shadow.fullscreen_input_count_loc,
        (GLint)input->count);
    xz_shadow.gl.BindVertexArray(xz_shadow.vao);
    xz_shadow.gl.DrawArrays(
        GL_TRIANGLES, 0, 3);

    error = xz_shadow.gl.GetError();
    if (error != GL_NO_ERROR) {
        state->sampled_failures++;
        if (state->last_gl_error == 0u)
            state->last_gl_error =
                (unsigned int)error;
        return 0;
    }

    for (i = 0u; i < input->count; ++i) {
        xz_shadow.gl.ActiveTexture(
            GL_TEXTURE0 + (GLenum)i);
        xz_shadow.gl.BindTexture(
            GL_TEXTURE_2D, 0u);
    }
    xz_shadow.gl.ActiveTexture(GL_TEXTURE0);

    state->sampled_passes++;
    state->sampled_draws++;
    if (input->count > state->sampled_max_inputs)
        state->sampled_max_inputs = input->count;

    return 1;
}

void XzGles3Shadow_InitState(
    XzGles3ShadowState *state)
{
    if (!state)
        return;

    memset(state, 0, sizeof(*state));
    state->restore_ok = 1;
    state->quality_scale = 1.0f;
    state->resource_proxy_max =
        XZ_G3_RESOURCE_PROXY_MAX;
}

int XzGles3Shadow_SetQualityScale(
    XzGles3ShadowState *state,
    float scale)
{
    unsigned int proxy;

    if (!state)
        return 0;

    if (scale < 0.50f)
        scale = 0.50f;
    if (scale > 1.0f)
        scale = 1.0f;

    proxy = (unsigned int)(
        (float)XZ_G3_RESOURCE_PROXY_MAX *
        scale + 0.5f);

    if (proxy < 64u)
        proxy = 64u;
    if (proxy > XZ_G3_RESOURCE_PROXY_MAX)
        proxy = XZ_G3_RESOURCE_PROXY_MAX;

    if (state->quality_scale == scale &&
        state->resource_proxy_max == proxy)
        return 0;

    state->quality_scale = scale;
    state->resource_proxy_max = proxy;
    state->quality_scale_updates++;
    return 1;
}

int XzGles3Shadow_Init(
    XzGles3ShadowState *state,
    unsigned int submit_stride)
{
    EGLDisplay previous_display;
    EGLSurface previous_draw;
    EGLSurface previous_read;
    EGLContext previous_context;
    EGLint egl_major = 0;
    EGLint egl_minor = 0;
    EGLint config_count = 0;

    const EGLint config_attribs[] = {
        EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
        EGL_RENDERABLE_TYPE, EGL_OPENGL_ES3_BIT_KHR,
        EGL_RED_SIZE, 8,
        EGL_GREEN_SIZE, 8,
        EGL_BLUE_SIZE, 8,
        EGL_ALPHA_SIZE, 8,
        EGL_NONE
    };
    const EGLint surface_attribs[] = {
        EGL_WIDTH, XZ_SHADOW_WIDTH,
        EGL_HEIGHT, XZ_SHADOW_HEIGHT,
        EGL_NONE
    };
    const EGLint context_attribs[] = {
        EGL_CONTEXT_CLIENT_VERSION, 3,
        EGL_NONE
    };

    if (!state)
        return 0;

    XzGles3Shadow_InitState(state);
    memset(&xz_shadow, 0, sizeof(xz_shadow));
    XzStaticSceneDrawPlan_Init(
        &xz_shadow.static_draw_plan);
    XzStaticSceneMaterialDrawPlan_Init(
        &xz_shadow.static_material_draw_plan);
    XzStaticSceneLightmapDrawPlan_Init(
        &xz_shadow.static_lightmap_draw_plan);

    state->submit_stride =
        submit_stride > 0u ? submit_stride : 8u;

    previous_display = eglGetCurrentDisplay();
    previous_draw = eglGetCurrentSurface(EGL_DRAW);
    previous_read = eglGetCurrentSurface(EGL_READ);
    previous_context = eglGetCurrentContext();

    xz_shadow.display = previous_display;
    if (xz_shadow.display == EGL_NO_DISPLAY)
        xz_shadow.display =
            eglGetDisplay(EGL_DEFAULT_DISPLAY);

    if (xz_shadow.display == EGL_NO_DISPLAY)
        goto fail;

    if (!eglInitialize(
            xz_shadow.display,
            &egl_major,
            &egl_minor))
        goto fail;

    if (!eglBindAPI(EGL_OPENGL_ES_API))
        goto fail;

    if (!eglChooseConfig(
            xz_shadow.display,
            config_attribs,
            &xz_shadow.config,
            1,
            &config_count) ||
        config_count < 1)
        goto fail;

    xz_shadow.surface = eglCreatePbufferSurface(
        xz_shadow.display,
        xz_shadow.config,
        surface_attribs);
    if (xz_shadow.surface == EGL_NO_SURFACE)
        goto fail;

    xz_shadow.context = eglCreateContext(
        xz_shadow.display,
        xz_shadow.config,
        EGL_NO_CONTEXT,
        context_attribs);
    if (xz_shadow.context == EGL_NO_CONTEXT)
        goto fail;

    if (!eglMakeCurrent(
            xz_shadow.display,
            xz_shadow.surface,
            xz_shadow.surface,
            xz_shadow.context))
        goto fail;

    if (!XzLoadApi(&xz_shadow.gl))
        goto fail_current;

    if (!XzCreateProgramAndBuffer())
        goto fail_current;

    if (!XzCreateRealGeometryProgram())
        goto fail_current;

    if (!XzCreateStaticSceneProgram())
        goto fail_current;

    if (!XzCreateFullscreenProgram())
        goto fail_current;

    state->visible_context_ready =
        XzCreateVisibleContext(
            previous_draw,
            previous_read,
            previous_context);

    xz_shadow.gl.Viewport(
        0, 0, XZ_SHADOW_WIDTH, XZ_SHADOW_HEIGHT);

    if (!XzRestorePrevious(
            previous_display,
            previous_draw,
            previous_read,
            previous_context))
        goto fail_restore;

    xz_shadow.ready = 1;
    state->initialized = 1;
    state->available = 1;
    state->shader_ok = 1;
    state->restore_ok = 1;
    return 1;

fail_current:
    XzUnloadApi(&xz_shadow.gl);

fail_restore:
    if (previous_display != EGL_NO_DISPLAY &&
        previous_context != EGL_NO_CONTEXT) {
        eglMakeCurrent(
            previous_display,
            previous_draw,
            previous_read,
            previous_context);
    }

fail:
    if (xz_shadow.visible_context_owned &&
        xz_shadow.visible_context != EGL_NO_CONTEXT)
        eglDestroyContext(
            xz_shadow.display,
            xz_shadow.visible_context);
    if (xz_shadow.context != EGL_NO_CONTEXT)
        eglDestroyContext(
            xz_shadow.display,
            xz_shadow.context);
    if (xz_shadow.surface != EGL_NO_SURFACE)
        eglDestroySurface(
            xz_shadow.display,
            xz_shadow.surface);

    memset(&xz_shadow, 0, sizeof(xz_shadow));
    state->failures++;
    state->restore_ok = 0;
    return 0;
}

static int XzGles3Shadow_SubmitInternal(
    XzGles3ShadowState *state,
    const XzCommandStream *commands,
    const XzRenderPlan *plan,
    XzGpuResourcePool *resources,
    const XzGeometryFrame *geometry)
{
    float vertices[
        XZ_RENDER_MAX_PACKETS *
        XZ_VERTICES_PER_PACKET *
        XZ_VERTEX_FLOATS];
    EGLDisplay previous_display;
    EGLSurface previous_draw;
    EGLSurface previous_read;
    EGLContext previous_context;
    unsigned int i;
    unsigned char expected[4];
    unsigned char readback[4] = {0u, 0u, 0u, 0u};
    int had_gl_error = 0;
    int readback_ok;
    int command_ok = 1;
    int saw_draw = 0;
    XzPassTargetPlan target_plan;
    XzPassInputPlan input_plan;
    const XzPassTarget *current_target = NULL;
    const XzPassInput *current_input = NULL;
    unsigned int target_cursor = 0u;
    int target_bound = 0;
    XzNativeGles3Api *gl;

    if (!state || !plan ||
        !state->initialized ||
        !state->available ||
        !xz_shadow.ready)
        return 0;

    state->submit_attempts++;

    if (!XzRenderPlan_Validate(plan)) {
        state->failures++;
        return 0;
    }

    if (commands &&
        !XzCommandStream_Validate(commands)) {
        state->command_failures++;
        state->failures++;
        return 0;
    }

    if (commands && !resources) {
        state->command_failures++;
        state->physical_failures++;
        state->failures++;
        return 0;
    }

    if (plan->generation == 0u ||
        (plan->generation % state->submit_stride) != 0u) {
        state->skipped_frames++;
        return 1;
    }

    memset(&target_plan, 0, sizeof(target_plan));
    memset(&input_plan, 0, sizeof(input_plan));

    if (commands &&
        !XzPassTargetPlan_Build(
            &target_plan,
            commands,
            resources)) {
        state->target_plan_failures++;
        state->command_failures++;
        state->failures++;
        return 0;
    }

    if (commands &&
        !XzPassInputPlan_Build(
            &input_plan,
            commands,
            resources)) {
        state->sampled_failures++;
        state->command_failures++;
        state->failures++;
        return 0;
    }

    if (!XzMakeShadowCurrent(
            &previous_display,
            &previous_draw,
            &previous_read,
            &previous_context)) {
        state->failures++;
        state->restore_ok = 0;
        return 0;
    }

    gl = &xz_shadow.gl;
    state->last_gl_error = 0u;
    state->last_error_stage = XZ_G3_STAGE_NONE;
    XzDrainErrors(state);

    for (i = 0u; i < plan->packet_count; ++i) {
        const XzRenderPacket *packet =
            &plan->packets[i];
        const float x =
            packet->origin[0] /
            (512.0f + XzAbsFloat(packet->origin[0]));
        const float y =
            packet->origin[1] /
            (512.0f + XzAbsFloat(packet->origin[1]));
        const float weight =
            (float)packet->priority_class / 3.0f;
        const float delta =
            0.004f + 0.004f * weight;
        const unsigned int base =
            i * XZ_VERTICES_PER_PACKET *
            XZ_VERTEX_FLOATS;

        vertices[base + 0u] = x;
        vertices[base + 1u] = y + delta;
        vertices[base + 2u] = weight;
        vertices[base + 3u] = packet->lit_rgba[0];
        vertices[base + 4u] = packet->lit_rgba[1];
        vertices[base + 5u] = packet->lit_rgba[2];
        vertices[base + 6u] = packet->lit_rgba[3];

        vertices[base + 7u] = x - delta;
        vertices[base + 8u] = y - delta;
        vertices[base + 9u] = weight;
        vertices[base + 10u] = packet->lit_rgba[0];
        vertices[base + 11u] = packet->lit_rgba[1];
        vertices[base + 12u] = packet->lit_rgba[2];
        vertices[base + 13u] = packet->lit_rgba[3];

        vertices[base + 14u] = x + delta;
        vertices[base + 15u] = y - delta;
        vertices[base + 16u] = weight;
        vertices[base + 17u] = packet->lit_rgba[0];
        vertices[base + 18u] = packet->lit_rgba[1];
        vertices[base + 19u] = packet->lit_rgba[2];
        vertices[base + 20u] = packet->lit_rgba[3];

        state->material_packets++;
        state->material_vertices += XZ_VERTICES_PER_PACKET;
        if (packet->contributing_lights > 0u)
            state->material_lit_packets++;
        state->last_material_flags = packet->material_flags;
    }

    XzEncodePlanColor(
        commands ? commands->content_hash
                 : plan->content_hash,
        expected);

    gl->BindFramebuffer(GL_FRAMEBUFFER, 0u);
    gl->Viewport(
        0, 0, XZ_SHADOW_WIDTH, XZ_SHADOW_HEIGHT);
    gl->ClearColor(
        (float)expected[0] / 255.0f,
        (float)expected[1] / 255.0f,
        (float)expected[2] / 255.0f,
        1.0f);
    gl->Clear(GL_COLOR_BUFFER_BIT);

    gl->ReadPixels(
        0,
        0,
        1,
        1,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        readback);

    if (XzCaptureError(
            state,
            XZ_G3_STAGE_READBACK) != GL_NO_ERROR)
        had_gl_error = 1;

    readback_ok =
        XzReadbackMatches(expected, readback);

    if (!readback_ok) {
        state->readback_failures++;
        state->failures++;
    }

    gl->UseProgram(xz_shadow.program);
    if (XzCaptureError(
            state,
            XZ_G3_STAGE_USE_PROGRAM) != GL_NO_ERROR)
        had_gl_error = 1;

    gl->BindVertexArray(xz_shadow.vao);
    if (XzCaptureError(
            state,
            XZ_G3_STAGE_BIND_VERTEX_ARRAY) != GL_NO_ERROR)
        had_gl_error = 1;

    gl->BindBuffer(
        GL_ARRAY_BUFFER,
        xz_shadow.vbo);
    if (XzCaptureError(
            state,
            XZ_G3_STAGE_BIND_BUFFER) != GL_NO_ERROR)
        had_gl_error = 1;

    if (commands) {
        state->command_stream_submissions++;
        state->last_command_hash =
            commands->content_hash;

        for (i = 0u; i < commands->count; ++i) {
            const XzCommand *command =
                &commands->commands[i];

            state->commands_executed++;

            switch (command->op) {
            case XZ_CMD_BEGIN_PASS:
                state->passes_executed++;

                if (target_cursor >= target_plan.count ||
                    target_plan.passes[target_cursor].pass_index !=
                        command->a) {
                    command_ok = 0;
                    break;
                }

                current_target =
                    &target_plan.passes[target_cursor];
                current_input =
                    XzPassInputPlan_Find(
                        &input_plan,
                        command->a);
                if (!current_input) {
                    command_ok = 0;
                    break;
                }
                target_bound = 0;
                break;

            case XZ_CMD_RESOURCE_READ:
                state->resource_read_commands++;
                if (command->b != XzGpuHandle_Index(
                        (XzGpuHandle)command->c) ||
                    !XzEnsurePhysicalResource(
                        state,
                        resources,
                        (XzGpuHandle)command->c,
                        0)) {
                    command_ok = 0;
                }
                break;

            case XZ_CMD_RESOURCE_WRITE:
                state->resource_write_commands++;
                if (command->b != XzGpuHandle_Index(
                        (XzGpuHandle)command->c) ||
                    !XzEnsurePhysicalResource(
                        state,
                        resources,
                        (XzGpuHandle)command->c,
                        1)) {
                    command_ok = 0;
                }
                break;

            case XZ_CMD_DRAW_PACKETS:
                state->draw_commands++;

                if (commands && !target_bound) {
                    if (!current_target ||
                        !XzBindPassTarget(
                            state,
                            current_target)) {
                        command_ok = 0;
                        break;
                    }
                    target_bound = 1;
                }

                if (saw_draw ||
                    command->a != plan->packet_count ||
                    command->value64 !=
                        (uint64_t)plan->content_hash) {
                    command_ok = 0;
                    break;
                }

                saw_draw = 1;

                if (geometry &&
                    geometry->batch_count > 0u) {
                    if (!XzDrawRealGeometry(
                            state,
                            geometry,
                            0)) {
                        command_ok = 0;
                        break;
                    }
                    state->draw_calls++;
                } else if (plan->packet_count > 0u) {
                    gl->UseProgram(xz_shadow.program);
                    gl->BindVertexArray(xz_shadow.vao);
                    gl->BindBuffer(
                        GL_ARRAY_BUFFER,
                        xz_shadow.vbo);

                    gl->BufferSubData(
                        GL_ARRAY_BUFFER,
                        0,
                        (GLsizeiptr)(
                            plan->packet_count *
                            XZ_VERTICES_PER_PACKET *
                            XZ_VERTEX_FLOATS *
                            sizeof(float)),
                        vertices);

                    if (XzCaptureError(
                            state,
                            XZ_G3_STAGE_BUFFER_UPLOAD) !=
                        GL_NO_ERROR)
                        had_gl_error = 1;

                    gl->DrawArrays(
                        GL_TRIANGLES,
                        0,
                        (GLsizei)(
                            plan->packet_count *
                            XZ_VERTICES_PER_PACKET));

                    if (XzCaptureError(
                            state,
                            XZ_G3_STAGE_DRAW) !=
                        GL_NO_ERROR)
                        had_gl_error = 1;

                    state->draw_calls++;
                }
                break;

            case XZ_CMD_END_PASS:
                if (!current_target ||
                    command->a !=
                        current_target->pass_index) {
                    command_ok = 0;
                    break;
                }

                if (!target_bound) {
                    if (!XzBindPassTarget(
                            state,
                            current_target)) {
                        command_ok = 0;
                        break;
                    }
                    target_bound = 1;
                }

                if (current_input->count > 0u) {
                    if (!XzDrawSampledPass(
                            state,
                            current_input)) {
                        command_ok = 0;
                        break;
                    }
                }

                target_cursor++;
                current_target = NULL;
                current_input = NULL;
                target_bound = 0;
                break;

            case XZ_CMD_BEGIN_FRAME:
            case XZ_CMD_END_FRAME:
                break;

            case XZ_CMD_NOP:
            default:
                command_ok = 0;
                break;
            }

            if (!command_ok)
                break;
        }

        if (plan->packet_count > 0u &&
            !saw_draw)
            command_ok = 0;

        if (target_cursor != target_plan.count ||
            current_target != NULL ||
            current_input != NULL)
            command_ok = 0;
    } else if (plan->packet_count > 0u) {
        gl->BufferSubData(
            GL_ARRAY_BUFFER,
            0,
            (GLsizeiptr)(
                plan->packet_count *
                XZ_VERTICES_PER_PACKET *
                XZ_VERTEX_FLOATS *
                sizeof(float)),
            vertices);

        if (XzCaptureError(
                state,
                XZ_G3_STAGE_BUFFER_UPLOAD) != GL_NO_ERROR)
            had_gl_error = 1;

        gl->DrawArrays(
            GL_TRIANGLES,
            0,
            (GLsizei)(
                plan->packet_count *
                XZ_VERTICES_PER_PACKET));

        if (XzCaptureError(
                state,
                XZ_G3_STAGE_DRAW) != GL_NO_ERROR)
            had_gl_error = 1;

        state->draw_calls++;
    }

    gl->BindFramebuffer(GL_FRAMEBUFFER, 0u);
    gl->Viewport(
        0, 0, XZ_SHADOW_WIDTH, XZ_SHADOW_HEIGHT);

    gl->Finish();
    if (XzCaptureError(
            state,
            XZ_G3_STAGE_FINISH) != GL_NO_ERROR)
        had_gl_error = 1;

    gl->BindVertexArray(0u);
    gl->BindBuffer(GL_ARRAY_BUFFER, 0u);

    if (XzCaptureError(
            state,
            XZ_G3_STAGE_UNBIND) != GL_NO_ERROR)
        had_gl_error = 1;

    state->last_packet_count = plan->packet_count;
    state->last_plan_hash = plan->content_hash;
    memcpy(
        state->last_expected_rgba,
        expected,
        sizeof(expected));
    memcpy(
        state->last_readback_rgba,
        readback,
        sizeof(readback));

    if (!command_ok) {
        state->command_failures++;
        state->failures++;
    }

    if (had_gl_error)
        state->failures++;

    if (!XzRestorePrevious(
            previous_display,
            previous_draw,
            previous_read,
            previous_context)) {
        state->restore_failures++;
        state->failures++;
        state->restore_ok = 0;
        return 0;
    }

    state->restore_ok = 1;
    state->submitted_frames++;
    state->submitted_packets += plan->packet_count;

    return !had_gl_error &&
           readback_ok &&
           command_ok;
}

int XzGles3Shadow_Submit(
    XzGles3ShadowState *state,
    const XzRenderPlan *plan)
{
    return XzGles3Shadow_SubmitInternal(
        state, NULL, plan, NULL, NULL);
}

int XzGles3Shadow_SubmitCommands(
    XzGles3ShadowState *state,
    const XzCommandStream *commands,
    const XzRenderPlan *plan,
    XzGpuResourcePool *resources,
    const XzGeometryFrame *geometry)
{
    return XzGles3Shadow_SubmitInternal(
        state, commands, plan, resources, geometry);
}

static int XzDumpFramebufferPpm(
    XzNativeGles3Api *gl,
    unsigned int width,
    unsigned int height,
    const char *path)
{
    unsigned char *rgba = NULL;
    unsigned char *row = NULL;
    FILE *file = NULL;
    size_t pixel_count;
    size_t rgba_bytes;
    size_t row_bytes;
    unsigned int y;
    unsigned int x;
    int ok = 0;

    if (!gl || !gl->ReadPixels ||
        !path || !path[0] ||
        width == 0u || height == 0u)
        return 0;

    pixel_count = (size_t)width * (size_t)height;
    if (pixel_count > ((size_t)-1) / 4u)
        return 0;

    rgba_bytes = pixel_count * 4u;
    row_bytes = (size_t)width * 3u;

    rgba = (unsigned char *)malloc(rgba_bytes);
    row = (unsigned char *)malloc(row_bytes);
    if (!rgba || !row)
        goto cleanup;

    gl->ReadPixels(
        0, 0,
        (GLsizei)width,
        (GLsizei)height,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        rgba);

    if (gl->GetError() != GL_NO_ERROR)
        goto cleanup;

    file = fopen(path, "wb");
    if (!file)
        goto cleanup;

    if (fprintf(file, "P6\n%u %u\n255\n", width, height) <= 0)
        goto cleanup;

    /*
     * OpenGL readback is bottom-up. PPM viewers expect the first row to be
     * the top of the image, so flip vertically while dropping alpha.
     */
    for (y = 0u; y < height; ++y) {
        const unsigned int source_y =
            height - 1u - y;
        const unsigned char *src =
            rgba +
            (size_t)source_y *
            (size_t)width * 4u;

        for (x = 0u; x < width; ++x) {
            row[(size_t)x * 3u + 0u] =
                src[(size_t)x * 4u + 0u];
            row[(size_t)x * 3u + 1u] =
                src[(size_t)x * 4u + 1u];
            row[(size_t)x * 3u + 2u] =
                src[(size_t)x * 4u + 2u];
        }

        if (fwrite(row, 1u, row_bytes, file) != row_bytes)
            goto cleanup;
    }

    ok = 1;

cleanup:
    if (file)
        fclose(file);
    free(row);
    free(rgba);
    return ok;
}

static int XzMeasureFramebufferMeanRgba(
    XzNativeGles3Api *gl,
    unsigned int width,
    unsigned int height,
    unsigned int out_rgba[4])
{
    unsigned char *pixels;
    size_t pixel_count;
    size_t byte_count;
    size_t i;
    uint64_t sums[4] = { 0u, 0u, 0u, 0u };

    if (!gl || !gl->ReadPixels ||
        !out_rgba ||
        width == 0u || height == 0u)
        return 0;

    pixel_count = (size_t)width * (size_t)height;
    if (pixel_count == 0u ||
        pixel_count > ((size_t)-1) / 4u)
        return 0;

    byte_count = pixel_count * 4u;
    pixels = (unsigned char *)malloc(byte_count);
    if (!pixels)
        return 0;

    gl->ReadPixels(
        0, 0,
        (GLsizei)width,
        (GLsizei)height,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        pixels);

    if (gl->GetError() != GL_NO_ERROR) {
        free(pixels);
        return 0;
    }

    for (i = 0u; i < pixel_count; ++i) {
        const unsigned char *p = pixels + i * 4u;
        sums[0] += p[0];
        sums[1] += p[1];
        sums[2] += p[2];
        sums[3] += p[3];
    }

    out_rgba[0] = (unsigned int)(sums[0] / pixel_count);
    out_rgba[1] = (unsigned int)(sums[1] / pixel_count);
    out_rgba[2] = (unsigned int)(sums[2] / pixel_count);
    out_rgba[3] = (unsigned int)(sums[3] / pixel_count);

    free(pixels);
    return 1;
}

static unsigned int XzCountNonBlackPixels(
    XzNativeGles3Api *gl,
    unsigned int width,
    unsigned int height,
    int *ok)
{
    unsigned char *pixels;
    size_t pixel_count;
    size_t byte_count;
    size_t i;
    unsigned int nonblack = 0u;

    if (ok)
        *ok = 0;

    if (!gl || !gl->ReadPixels ||
        width == 0u || height == 0u)
        return 0u;

    pixel_count = (size_t)width * (size_t)height;
    if (pixel_count > ((size_t)-1) / 4u)
        return 0u;

    byte_count = pixel_count * 4u;
    pixels = (unsigned char *)malloc(byte_count);
    if (!pixels)
        return 0u;

    gl->ReadPixels(
        0, 0,
        (GLsizei)width,
        (GLsizei)height,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        pixels);

    if (gl->GetError() != GL_NO_ERROR) {
        free(pixels);
        return 0u;
    }

    for (i = 0u; i < pixel_count; ++i) {
        const unsigned char *p = pixels + i * 4u;

        /*
         * The diagnostic clear is roughly RGB 3/4/5. Treat values above 16
         * as real rendered color so readback proves useful pixels, not merely
         * a successful draw call against an empty/off-camera scene.
         */
        if (p[0] > 16u ||
            p[1] > 16u ||
            p[2] > 16u)
            nonblack++;
    }

    free(pixels);
    if (ok)
        *ok = 1;
    return nonblack;
}

int XzGles3Shadow_CompositeVisibleWorld(
    XzGles3ShadowState *state,
    const XzGeometryFrame *geometry,
    unsigned int render_width,
    unsigned int render_height)
{
    XzNativeGles3Api *gl = &xz_shadow.gl;
    EGLDisplay previous_display;
    EGLSurface previous_draw;
    EGLSurface previous_read;
    EGLContext previous_context;
    EGLint surface_width = 0;
    EGLint surface_height = 0;
    GLenum error = GL_NO_ERROR;
    int shadow_current = 0;
    int visible_current = 0;
    int restored = 0;
    int draw_ok = 0;
    int static_world_drawn = 0;

    if (!state || !geometry ||
        !state->initialized ||
        !state->available ||
        !xz_shadow.ready ||
        !state->visible_context_ready ||
        xz_shadow.visible_context == EGL_NO_CONTEXT ||
        !state->real_geometry_ready ||
        !state->real_textures_ready ||
        state->real_scene_ready_streak < 4u ||
        geometry->surface_batches == 0u ||
        geometry->batch_count < 8u ||
        geometry->vertex_count == 0u ||
        geometry->index_count == 0u ||
        geometry->dropped_batches != 0u ||
        geometry->dropped_vertices != 0u ||
        geometry->dropped_indices != 0u)
        return 0;

    if (render_width < 64u)
        render_width = 64u;
    if (render_height < 64u)
        render_height = 64u;

    state->visible_present_attempts++;

    if (!XzMakeShadowCurrent(
            &previous_display,
            &previous_draw,
            &previous_read,
            &previous_context)) {
        state->visible_present_failures++;
        state->visible_present_streak = 0u;
        state->visible_present_ready = 0;
        return 0;
    }
    shadow_current = 1;

    if (previous_display == EGL_NO_DISPLAY ||
        previous_draw == EGL_NO_SURFACE ||
        previous_context == EGL_NO_CONTEXT)
        goto fail;

    XzDrainErrors(state);

    if (!XzEnsureVisibleTargets(
            render_width,
            render_height))
        goto fail;

    gl->BindFramebuffer(
        GL_FRAMEBUFFER,
        xz_shadow.visible_fbo);
    gl->Viewport(
        0,
        0,
        (GLsizei)render_width,
        (GLsizei)render_height);
    gl->ClearColor(
        0.010f, 0.015f, 0.020f, 1.0f);
    gl->Clear(
        GL_COLOR_BUFFER_BIT |
        GL_DEPTH_BUFFER_BIT);

    if (gl->GetError() != GL_NO_ERROR)
        goto fail;

    if (state->static_scene_gpu_ready)
        static_world_drawn =
            XzDrawStaticScene(
                state,
                geometry);

    if (static_world_drawn &&
        state->static_scene_draw_successes == 1u &&
        state->static_scene_readback_width == 0u) {
        int readback_ok = 0;

        state->static_scene_fbo_nonblack_pixels =
            XzCountNonBlackPixels(
                gl,
                render_width,
                render_height,
                &readback_ok);

        if (readback_ok) {
            (void)XzDumpFramebufferPpm(
                gl,
                render_width,
                render_height,
                "/data/data/com.xziel.engine/files/"
                "nzp-runtime/static-scene-fbo.ppm");
        }

        state->static_scene_readback_width =
            readback_ok ? render_width : 0u;
        state->static_scene_readback_height =
            readback_ok ? render_height : 0u;

        if (!readback_ok)
            state->readback_failures++;
    }

    if (!XzDrawRealGeometry(
            state,
            geometry,
            static_world_drawn ? 1 : 0) ||
        state->last_geometry_drops != 0u ||
        state->last_texture_misses != 0u)
        goto fail;

    gl->Finish();
    error = gl->GetError();
    if (error != GL_NO_ERROR)
        goto fail;

    if (!eglMakeCurrent(
            xz_shadow.display,
            previous_draw,
            previous_read,
            xz_shadow.visible_context))
        goto fail;
    visible_current = 1;
    shadow_current = 0;

    if (!eglQuerySurface(
            xz_shadow.display,
            previous_draw,
            EGL_WIDTH,
            &surface_width) ||
        !eglQuerySurface(
            xz_shadow.display,
            previous_draw,
            EGL_HEIGHT,
            &surface_height) ||
        surface_width <= 0 ||
        surface_height <= 0) {
        surface_width = (EGLint)render_width;
        surface_height = (EGLint)render_height;
    }

    gl->BindFramebuffer(GL_FRAMEBUFFER, 0u);
    gl->Viewport(
        0, 0,
        (GLsizei)surface_width,
        (GLsizei)surface_height);
    gl->Disable(GL_DEPTH_TEST);
    gl->Disable(GL_BLEND);
    gl->DepthMask(GL_TRUE);
    gl->UseProgram(
        xz_shadow.fullscreen_program);
    gl->Uniform1i(
        xz_shadow.fullscreen_input_count_loc,
        1);
    gl->ActiveTexture(GL_TEXTURE0);
    gl->BindTexture(
        GL_TEXTURE_2D,
        xz_shadow.visible_color);
    gl->BindVertexArray(
        xz_shadow.visible_vao);
    gl->DrawArrays(
        GL_TRIANGLES, 0, 3);
    gl->Finish();

    if (state->static_scene_draw_successes == 1u &&
        state->static_scene_readback_width != 0u &&
        state->static_scene_surface_nonblack_pixels == 0u) {
        int readback_ok = 0;

        state->static_scene_surface_nonblack_pixels =
            XzCountNonBlackPixels(
                gl,
                (unsigned int)surface_width,
                (unsigned int)surface_height,
                &readback_ok);

        if (!readback_ok)
            state->readback_failures++;
    }

    error = gl->GetError();
    if (error == GL_NO_ERROR)
        draw_ok = 1;

    gl->BindVertexArray(0u);
    gl->BindTexture(GL_TEXTURE_2D, 0u);
    gl->UseProgram(0u);

    restored = XzRestorePrevious(
        previous_display,
        previous_draw,
        previous_read,
        previous_context);
    visible_current = 0;

    if (restored &&
        state->static_scene_draw_successes == 1u &&
        state->static_scene_readback_width != 0u &&
        state->static_scene_postrestore_nonblack_pixels == 0u) {
        int readback_ok = 0;

        XzDrainErrors(state);
        gl->BindFramebuffer(GL_FRAMEBUFFER, 0u);
        state->static_scene_postrestore_nonblack_pixels =
            XzCountNonBlackPixels(
                gl,
                (unsigned int)surface_width,
                (unsigned int)surface_height,
                &readback_ok);

        if (!readback_ok) {
            state->readback_failures++;
        } else if (!XzMeasureFramebufferMeanRgba(
                       gl,
                       (unsigned int)surface_width,
                       (unsigned int)surface_height,
                       state->static_scene_postrestore_mean_rgba)) {
            state->readback_failures++;
        }
    }

    if (!restored) {
        state->restore_failures++;
        state->restore_ok = 0;
        draw_ok = 0;
    } else {
        state->restore_ok = 1;
    }

    if (!draw_ok)
        goto fail_after_restore;

    state->visible_render_width = render_width;
    state->visible_render_height = render_height;
    state->visible_surface_width =
        (unsigned int)surface_width;
    state->visible_surface_height =
        (unsigned int)surface_height;
    state->visible_present_draw_calls++;
    state->visible_present_successes++;
    state->visible_present_streak++;

    state->visible_present_ready =
        state->visible_present_streak >= 2u &&
        state->last_texture_misses == 0u &&
        state->last_geometry_drops == 0u;

    return 1;

fail:
    if (visible_current || shadow_current) {
        if (!XzRestorePrevious(
                previous_display,
                previous_draw,
                previous_read,
                previous_context)) {
            state->restore_failures++;
            state->restore_ok = 0;
        } else {
            state->restore_ok = 1;
        }
    }

fail_after_restore:
    if (error != GL_NO_ERROR &&
        state->last_gl_error == 0u)
        state->last_gl_error =
            (unsigned int)error;

    state->visible_present_failures++;
    state->visible_present_streak = 0u;
    state->visible_present_ready = 0;
    return 0;
}

int XzGles3Shadow_AuditCurrentFramebuffer(
    XzGles3ShadowState *state,
    unsigned int width,
    unsigned int height,
    unsigned int out_rgba[4])
{
    XzNativeGles3Api *gl = &xz_shadow.gl;

    if (!state ||
        !state->initialized ||
        !state->available ||
        !xz_shadow.ready ||
        !out_rgba ||
        width == 0u ||
        height == 0u)
        return 0;

    XzDrainErrors(state);

    if (!XzMeasureFramebufferMeanRgba(
            gl,
            width,
            height,
            out_rgba))
        return 0;

    return gl->GetError() == GL_NO_ERROR;
}

void XzGles3Shadow_Shutdown(
    XzGles3ShadowState *state)
{
    EGLDisplay previous_display;
    EGLSurface previous_draw;
    EGLSurface previous_read;
    EGLContext previous_context;

    if (!state || !state->initialized)
        return;

    if (xz_shadow.ready &&
        XzMakeShadowCurrent(
            &previous_display,
            &previous_draw,
            &previous_read,
            &previous_context)) {
        XzDestroyAllPhysicalResources(state);
        XzDestroyStaticSceneCurrent(state);
        XzDestroyRealTextures();
        XzDestroyVisibleTargets();

        if (xz_shadow.gl.DeleteFramebuffers &&
            xz_shadow.scratch_fbo)
            xz_shadow.gl.DeleteFramebuffers(
                1, &xz_shadow.scratch_fbo);

        if (xz_shadow.gl.DeleteBuffers &&
            xz_shadow.vbo)
            xz_shadow.gl.DeleteBuffers(
                1, &xz_shadow.vbo);
        if (xz_shadow.gl.DeleteBuffers &&
            xz_shadow.real_vbo)
            xz_shadow.gl.DeleteBuffers(
                1, &xz_shadow.real_vbo);
        if (xz_shadow.gl.DeleteBuffers &&
            xz_shadow.real_ibo)
            xz_shadow.gl.DeleteBuffers(
                1, &xz_shadow.real_ibo);
        if (xz_shadow.gl.DeleteVertexArrays &&
            xz_shadow.vao)
            xz_shadow.gl.DeleteVertexArrays(
                1, &xz_shadow.vao);
        if (xz_shadow.gl.DeleteVertexArrays &&
            xz_shadow.real_vao)
            xz_shadow.gl.DeleteVertexArrays(
                1, &xz_shadow.real_vao);
        if (xz_shadow.gl.DeleteProgram &&
            xz_shadow.program)
            xz_shadow.gl.DeleteProgram(
                xz_shadow.program);
        if (xz_shadow.gl.DeleteProgram &&
            xz_shadow.real_program)
            xz_shadow.gl.DeleteProgram(
                xz_shadow.real_program);
        if (xz_shadow.gl.DeleteProgram &&
            xz_shadow.static_program)
            xz_shadow.gl.DeleteProgram(
                xz_shadow.static_program);
        if (xz_shadow.gl.DeleteProgram &&
            xz_shadow.fullscreen_program)
            xz_shadow.gl.DeleteProgram(
                xz_shadow.fullscreen_program);

        XzRestorePrevious(
            previous_display,
            previous_draw,
            previous_read,
            previous_context);
    }

    XzUnloadApi(&xz_shadow.gl);

    if (xz_shadow.visible_context_owned &&
        xz_shadow.visible_context != EGL_NO_CONTEXT)
        eglDestroyContext(
            xz_shadow.display,
            xz_shadow.visible_context);
    if (xz_shadow.context != EGL_NO_CONTEXT)
        eglDestroyContext(
            xz_shadow.display,
            xz_shadow.context);
    if (xz_shadow.surface != EGL_NO_SURFACE)
        eglDestroySurface(
            xz_shadow.display,
            xz_shadow.surface);

    memset(&xz_shadow, 0, sizeof(xz_shadow));
    state->initialized = 0;
    state->available = 0;
}

/* VIRIL IW3 experimental gl4es/GLES2 first-person 3D gun geometry.
 *
 * GPL-3.0 source. Compatible with portable IWVM v1 generated from user-
 * supplied glTF 2.0 GLB; never embeds any Call of Duty game data here.
 *
 * IWVM v1 is static rest-pose mesh geometry + UV only. CoD4 skeletal
 * XAnim, skinning, materials, exact hand attachment, muzzle/shell tags
 * and all official behaviors are NOT implemented by this module.
 */
#include "../../../nzportable_def.h"
#include <stdint.h>
#include <math.h>
#ifdef __ANDROID__
#include <android/log.h>
#endif

#define IWVM_MAX_VERTICES 65535u
#define IWVM_MAX_INDICES 360000u

typedef struct {
    float xyz[3];
    float uv[2];
} iwvm_vertex_t;

typedef struct {
    char name[160];
    iwvm_vertex_t *vertices;
    uint16_t *indices;
    uint32_t vertex_count;
    uint32_t index_count;
    int attempted;
} iwvm_mesh_t;

typedef char iwvm_vertex_stride_check[(sizeof(iwvm_vertex_t)==20) ? 1 : -1];

static iwvm_mesh_t iwvm_mesh;
static int iwvm_reported_draw;

extern void R_RotateForEntity(entity_t *e, unsigned char scale);
extern cvar_t gl_cull;

static void IWVM_ResetGeometry(void)
{
    free(iwvm_mesh.vertices);
    free(iwvm_mesh.indices);
    iwvm_mesh.vertices = NULL;
    iwvm_mesh.indices = NULL;
    iwvm_mesh.vertex_count = 0;
    iwvm_mesh.index_count = 0;
    iwvm_reported_draw = 0;
}

static uint32_t IWVM_Read32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1]<<8) |
           ((uint32_t)p[2]<<16) | ((uint32_t)p[3]<<24);
}

static uint16_t IWVM_Read16(const uint8_t *p)
{
    return (uint16_t)(p[0] | (p[1]<<8));
}

static int IWVM_BuildPath(const char *quake_mdl, char *output, size_t cap)
{
    const char *begin, *end, *dot;
    char stem[80];
    size_t n, i;
    if (!quake_mdl || !cap)
        return 0;
    /* The selected existing Vril weapon controls the source mapping.
     * e.g. models/weapons/mp40/v_mp40.mdl -> models/iw3/v_mp40.iwvm.
     * A local conversion/packaging tool explicitly assigns which original
     * IW3 XModel should override the currently equipped NZ:P gun. */
    begin = strrchr(quake_mdl, '/');
    begin = begin ? begin + 1 : quake_mdl;
    dot = strrchr(begin, '.');
    end = dot ? dot : begin + strlen(begin);
    n = (size_t)(end - begin);
    if (n < 3 || n >= sizeof(stem) || begin[0] != 'v' || begin[1] != '_')
        return 0;
    for (i=0; i<n; ++i) {
        char ch=begin[i];
        if (!((ch>='a'&&ch<='z') || (ch>='A'&&ch<='Z') ||
              (ch>='0'&&ch<='9') || ch=='_'))
            return 0;
        stem[i]=ch;
    }
    stem[n]=0;
    return snprintf(output,cap,"models/iw3/%s.iwvm",stem)>0 &&
           strlen(output)<cap;
}

static int IWVM_Load(const char *path)
{
    FILE *f=NULL;
    uint8_t hdr[16];
    long length;
    uint32_t count, n_indices, i;
    uint64_t expected;
    int ok=0;

    IWVM_ResetGeometry();
    length=COM_FOpenFile((char *)path,&f);
    if (length<=0 || !f)
        return 0;
    if (length<16 || fread(hdr,1,16,f)!=16)
        goto cleanup;
    if (memcmp(hdr,"IWVM",4)!=0 || IWVM_Read32(hdr+4)!=1)
        goto cleanup;
    count=IWVM_Read32(hdr+8);
    n_indices=IWVM_Read32(hdr+12);
    if (!count || count>IWVM_MAX_VERTICES ||
        !n_indices || n_indices>IWVM_MAX_INDICES || n_indices%3)
        goto cleanup;
    expected=16ull+20ull*count+2ull*n_indices;
    if (expected!=(uint64_t)length)
        goto cleanup;
    iwvm_mesh.vertices=(iwvm_vertex_t *)malloc(sizeof(iwvm_vertex_t)*count);
    iwvm_mesh.indices=(uint16_t *)malloc(sizeof(uint16_t)*n_indices);
    if (!iwvm_mesh.vertices || !iwvm_mesh.indices)
        goto cleanup;
    if (fread(iwvm_mesh.vertices,sizeof(iwvm_vertex_t),count,f)!=count ||
        fread(iwvm_mesh.indices,sizeof(uint16_t),n_indices,f)!=n_indices)
        goto cleanup;
    /* All Android-supported targets are little endian (ARM64 and x86_64);
     * reject any NaNs/infinite values to prevent invalid GLES commands. */
    for (i=0; i<count; ++i) {
        int k;
        const float *v=(const float*)&iwvm_mesh.vertices[i];
        for (k=0;k<5;++k)
            if (!isfinite(v[k]) || fabsf(v[k])>1e7f) goto cleanup;
    }
    for (i=0;i<n_indices;++i)
        if (IWVM_Read16((const uint8_t*)&iwvm_mesh.indices[i])>=count)
            goto cleanup;
    iwvm_mesh.vertex_count=count;
    iwvm_mesh.index_count=n_indices;
    ok=1;
cleanup:
    fclose(f);
    if (!ok)
        IWVM_ResetGeometry();
    return ok;
}

/* Returns 1 when an optional properly converted IW3 viewmodel was actually
 * submitted as 3D geometry, 0 when the untouched Vril MDL must be drawn. */
int IW3_WeaponMesh_Draw(entity_t *view)
{
    char path[160];
    if (!view || !view->model || !IWVM_BuildPath(view->model->name,path,sizeof(path)))
        return 0;
    if (strcmp(path,iwvm_mesh.name)!=0) {
        IWVM_ResetGeometry();
        snprintf(iwvm_mesh.name,sizeof(iwvm_mesh.name),"%s",path);
        iwvm_mesh.attempted=0;
    }
    if (!iwvm_mesh.attempted) {
        int loaded;
        iwvm_mesh.attempted=1;
        loaded=IWVM_Load(path);
#ifdef __ANDROID__
        __android_log_print(ANDROID_LOG_INFO,"VIRIL_IW3",
            "IW3_MESH_LOAD_REQUEST view=%s target=%s loaded=%d",
            view->model->name,path,loaded);
#endif
    }
    if (!iwvm_mesh.vertex_count)
        return 0;
    /* World/view GL projection and clipped viewmodel depth range are
     * inherited from Vril's existing R_DrawViewModel, never IW3 Direct3D. */
    glPushMatrix();
    R_RotateForEntity(view,view->scale);
    glEnable(GL_DEPTH_TEST);
    glDisable(GL_TEXTURE_2D); /* geometry proof only: skins pending */
    glDisable(GL_ALPHA_TEST);
    glDisable(GL_BLEND);
    glDisable(GL_CULL_FACE);
    glColor4f(0.82f,0.82f,0.82f,1.f);
    glEnableClientState(GL_VERTEX_ARRAY);
    glVertexPointer(3,GL_FLOAT,sizeof(iwvm_vertex_t),&iwvm_mesh.vertices[0].xyz[0]);
    glDrawElements(GL_TRIANGLES,iwvm_mesh.index_count,GL_UNSIGNED_SHORT,iwvm_mesh.indices);
#ifdef __ANDROID__
    if (!iwvm_reported_draw) {
        __android_log_print(ANDROID_LOG_INFO,"VIRIL_IW3",
            "IW3_NATIVE_MESH_DRAW submitted model=%s vertices=%u triangles=%u",
            iwvm_mesh.name,(unsigned)iwvm_mesh.vertex_count,
            (unsigned)(iwvm_mesh.index_count/3));
        iwvm_reported_draw = 1;
    }
#endif
    glDisableClientState(GL_VERTEX_ARRAY);
    glColor4f(1,1,1,1);
    if (gl_cull.value)
        glEnable(GL_CULL_FACE);
    glEnable(GL_TEXTURE_2D);
    glEnable(GL_ALPHA_TEST);
    glPopMatrix();
    return 1;
}

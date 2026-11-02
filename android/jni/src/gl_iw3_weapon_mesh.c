/* VIRIL IW3 experimental gl4es/GLES2 first-person 3D gun geometry.
 *
 * GPL-3.0 source. Compatible with portable IWVM v1 generated from user-
 * supplied glTF 2.0 GLB; never embeds any Call of Duty game data here.
 *
 * IWVM v1 is static rest-pose mesh geometry + UVs. Optional IWVT v1
 * uploads ONE RGBA base-color texture, when privately supplied.
 * Multi-material, skeletal XAnim, hand rigging and original CoD4
 * gameplay behavior are NOT YET implemented.
 */
#include "../../../nzportable_def.h"
#include <stdint.h>
#include <math.h>
#ifdef __ANDROID__
#include <android/log.h>
#endif

#define IWVM_MAX_VERTICES 65535u
#define IWVM_MAX_INDICES 360000u
#define IWVM_MAX_JOINTS 255u

/* Native IWSK v1 preserves real original CoD4 GLB skin, not playback yet.
 * Public source contains only binary format, no proprietary bone names. */
typedef struct {
    char name[64];
    int32_t parent;
    float local_bind[16];
    float inverse_bind[16];
} iwsk_joint_t;
typedef struct {
    uint8_t bone[4];
    float weight[4];
} iwsk_influence_t;
typedef char iwsk_bone_stride_check[(sizeof(iwsk_joint_t)==196) ? 1 : -1];
typedef char iwsk_weight_stride_check[(sizeof(iwsk_influence_t)==20) ? 1 : -1];


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
static GLuint iwvm_color_texture;
static int iwvm_color_attempted;
static iwsk_joint_t *iwsk_joints;
static iwsk_influence_t *iwsk_weights;
static uint32_t iwsk_joint_count;
static int iwsk_attempted;
/* Optional private IWSF baked from genuine original IW3 XAnim v17. */
static float *iwsk_frame_matrices;
static iwvm_vertex_t *iwvm_skinned_vertices;
static uint32_t iwsk_frame_count;
static float iwsk_frame_rate;
static int iwsk_frames_attempted;
static int iwsk_logged_motion;
/* Explicit, reversible first-person calibration for user-provided original
 * IW3 XModels. All values default to identity so a correct model is never
 * silently rotated or resized. Local X points forward, Y left, Z up.
 * The forward-axis rotation is the gun-roll correction (9->12 o'clock).
 * This is a developer calibration layer, not verified CoD4 1:1 pose. */
static cvar_t iw3_vm_roll = {"iw3_vm_roll", "0"};
static cvar_t iw3_vm_scale = {"iw3_vm_scale", "1"};
/* Original OAT GLB meshes are centered at X ~0, behind Vril near clip.
 * 12 units moves the genuine gun in front of the FPS near plane. */
static cvar_t iw3_vm_forward = {"iw3_vm_forward", "12"};
static cvar_t iw3_vm_right = {"iw3_vm_right", "0"};
static cvar_t iw3_vm_up = {"iw3_vm_up", "0"};
/* Applies ONLY when a user-supplied original IWSF animation is present. */
static cvar_t iw3_vm_anim_preview = {"iw3_vm_anim_preview", "1"};
static cvar_t iw3_vm_anim_speed = {"iw3_vm_anim_speed", "1"};

void IW3_WeaponMesh_RegisterCvars(void)
{
    Cvar_RegisterVariable(&iw3_vm_roll);
    Cvar_RegisterVariable(&iw3_vm_scale);
    Cvar_RegisterVariable(&iw3_vm_forward);
    Cvar_RegisterVariable(&iw3_vm_right);
    Cvar_RegisterVariable(&iw3_vm_up);
    Cvar_RegisterVariable(&iw3_vm_anim_preview);
    Cvar_RegisterVariable(&iw3_vm_anim_speed);
}

static float IWVM_Bounded(float value, float lo, float hi, float fallback)
{
    if (!isfinite(value)) return fallback;
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}


extern void R_RotateForEntity(entity_t *e, unsigned char scale);
extern cvar_t gl_cull;

static void IWVM_ResetGeometry(void)
{
    free(iwvm_mesh.vertices);
    free(iwvm_mesh.indices);
    free(iwsk_joints);
    free(iwsk_weights);
    free(iwsk_frame_matrices);
    free(iwvm_skinned_vertices);
    iwsk_frame_matrices=NULL;
    iwvm_skinned_vertices=NULL;
    iwsk_frame_count=0;
    iwsk_frame_rate=0.f;
    iwsk_frames_attempted=0;
    iwsk_logged_motion=0;
    iwsk_joints = NULL;
    iwsk_weights = NULL;
    iwsk_joint_count = 0;
    iwsk_attempted = 0;
    if (iwvm_color_texture) {
        glDeleteTextures(1, &iwvm_color_texture);
        iwvm_color_texture = 0;
    }
    iwvm_color_attempted = 0;
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
#ifdef __ANDROID__
    {
        float low[3] = {1e30f,1e30f,1e30f};
        float high[3] = {-1e30f,-1e30f,-1e30f};
        for (i=0;i<count;++i) {
            int k;
            for(k=0;k<3;++k) {
                const float p=iwvm_mesh.vertices[i].xyz[k];
                if(p<low[k]) low[k]=p;
                if(p>high[k]) high[k]=p;
            }
        }
        __android_log_print(ANDROID_LOG_INFO,"VIRIL_IW3",
          "IW3_MESH_BOUNDS model=%s min=%.3f,%.3f,%.3f max=%.3f,%.3f,%.3f",
          path,low[0],low[1],low[2],high[0],high[1],high[2]);
    }
#endif
    ok=1;
cleanup:
    fclose(f);
    if (!ok)
        IWVM_ResetGeometry();
    return ok;
}

/* Native optional rig transport; one real joint set from the original
 * CoD4 GLB. Invalid/missing data safely preserves existing static IWVM.
 * Actual GL skinning or XAnim pose playback will use these same arrays in
 * the next dedicated implementation and is NOT claimed here. */
static void IWSK_TryLoad(const char *mesh_path)
{
    char rig_path[160];
    char *suffix;
    FILE *f = NULL;
    uint8_t header[20];
    iwsk_joint_t *bones = NULL;
    iwsk_influence_t *weights = NULL;
    uint32_t joints,vertices,i;
    uint64_t expected;
    long file_length;
    int ok=0;
    if (iwsk_attempted) return;
    iwsk_attempted=1;
    if (snprintf(rig_path,sizeof(rig_path),"%s",mesh_path) >=
        (int)sizeof(rig_path)) return;
    suffix=strrchr(rig_path,'.');
    if (!suffix || strcmp(suffix,".iwvm")!=0) return;
    strcpy(suffix,".iwsk");
    file_length=COM_FOpenFile(rig_path,&f);
    if (file_length<20 || !f) return;
    if (fread(header,1,sizeof(header),f)!=sizeof(header) ||
        memcmp(header,"IWSK",4)!=0 ||
        IWVM_Read32(header+4)!=1 || IWVM_Read32(header+16)!=0)
        goto cleanup;
    vertices=IWVM_Read32(header+8);
    joints=IWVM_Read32(header+12);
    if (vertices!=iwvm_mesh.vertex_count || !joints ||
        joints>IWVM_MAX_JOINTS) goto cleanup;
    expected=20ull+196ull*joints+20ull*vertices;
    if (expected!=(uint64_t)file_length) goto cleanup;
    bones=(iwsk_joint_t*)malloc(sizeof(*bones)*joints);
    weights=(iwsk_influence_t*)malloc(sizeof(*weights)*vertices);
    if (!bones || !weights) goto cleanup;
    if (fread(bones,sizeof(*bones),joints,f)!=joints ||
        fread(weights,sizeof(*weights),vertices,f)!=vertices)
        goto cleanup;
    for(i=0;i<joints;++i) {
        int k;
        if (!memchr(bones[i].name,0,sizeof(bones[i].name))) goto cleanup;
        if (bones[i].parent>=0 &&
            (uint32_t)bones[i].parent>=joints) goto cleanup;
        if (bones[i].parent==(int32_t)i) goto cleanup;
        for(k=0;k<16;++k)
            if(!isfinite(bones[i].local_bind[k]) ||
               !isfinite(bones[i].inverse_bind[k])) goto cleanup;
    }
    for(i=0;i<vertices;++i) {
        int k;
        float sum=0.f;
        for(k=0;k<4;++k) {
            if(weights[i].bone[k]>=joints ||
               !isfinite(weights[i].weight[k]) ||
               weights[i].weight[k]<0.f || weights[i].weight[k]>1.f)
                goto cleanup;
            sum+=weights[i].weight[k];
        }
        if(fabsf(sum-1.f)>0.02f) goto cleanup;
    }
    iwsk_joints=bones;
    iwsk_weights=weights;
    iwsk_joint_count=joints;
    bones=NULL;
    weights=NULL;
    ok=1;
#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_INFO,"VIRIL_IW3",
        "IW3_ORIGINAL_SKIN_DATA_LOADED file=%s joints=%u weighted_vertices=%u animated=0",
        rig_path,(unsigned)joints,(unsigned)vertices);
#endif
cleanup:
    if(f) fclose(f);
    free(bones);
    free(weights);
#ifdef __ANDROID__
    if(!ok)
        __android_log_print(ANDROID_LOG_ERROR,"VIRIL_IW3",
           "IW3_ORIGINAL_SKIN_DATA_INVALID file=%s",rig_path);
#endif
}

/* Original XAnim frame matrices, privately baked against the source GLB
 * bind pose. Fixed-size, bounded CPU skinning for an experimental preview.
 * XAnim->bone blending is DELTA-on-bind; not yet official CoD4 state graph. */
static void IWSF_TryLoad(const char *mesh_path)
{
    char path[160];
    char *suffix;
    FILE *f=NULL;
    uint8_t header[20];
    uint32_t frames,joints,i;
    uint64_t needed;
    long len;
    float fps;
    float *matrices=NULL;
    iwvm_vertex_t *skinned=NULL;
    if(iwsk_frames_attempted) return;
    iwsk_frames_attempted=1;
    if(!iwsk_joint_count || !iwsk_weights) return;
    if(snprintf(path,sizeof(path),"%s",mesh_path)>=(int)sizeof(path))
        return;
    suffix=strrchr(path,'.');
    if(!suffix || strcmp(suffix,".iwvm")!=0) return;
    strcpy(suffix,".iwsf");
    len=COM_FOpenFile(path,&f);
    if(len<20 || !f) return;
    if(fread(header,1,sizeof(header),f)!=sizeof(header) ||
       memcmp(header,"IWSF",4)!=0 || IWVM_Read32(header+4)!=1)
        goto cleanup;
    frames=IWVM_Read32(header+8);
    joints=IWVM_Read32(header+12);
    memcpy(&fps,header+16,sizeof(fps));
    if(frames<2 || frames>600 || joints!=iwsk_joint_count ||
       !isfinite(fps) || fps<1.f || fps>300.f)
        goto cleanup;
    needed=20ull+(uint64_t)frames*joints*16ull*sizeof(float);
    if(needed!=(uint64_t)len || needed>64ull*1024*1024)
        goto cleanup;
    matrices=(float *)malloc((size_t)needed-20u);
    skinned=(iwvm_vertex_t *)malloc((size_t)iwvm_mesh.vertex_count*sizeof(*skinned));
    if(!matrices || !skinned ||
       fread(matrices,1,(size_t)needed-20u,f)!=(size_t)needed-20u)
        goto cleanup;
    for(i=0;i<frames*joints*16u;++i) {
        if(!isfinite(matrices[i]) || fabsf(matrices[i])>1000000.f)
            goto cleanup;
    }
    /* F0 must be original rest pose. Reject wrong skeleton / transform. */
    for(i=0;i<joints;++i) {
        uint32_t j;
        const float *m=matrices+i*16u;
        for(j=0;j<16u;++j) {
            const float id=(j==0u || j==5u || j==10u || j==15u)?1.f:0.f;
            if(fabsf(m[j]-id)>0.08f) goto cleanup;
        }
    }
    iwsk_frame_matrices=matrices;
    iwvm_skinned_vertices=skinned;
    iwsk_frame_count=frames;
    iwsk_frame_rate=fps;
    matrices=NULL;
    skinned=NULL;
#ifdef __ANDROID__
    __android_log_print(ANDROID_LOG_INFO,"VIRIL_IW3",
       "IW3_ORIGINAL_XANIM_PREVIEW_LOADED file=%s frames=%u joints=%u fps=%.3f exact_graph=0",
       path,(unsigned)frames,(unsigned)joints,fps);
#endif
cleanup:
    if(f) fclose(f);
    free(matrices);
    free(skinned);
}

static const iwvm_vertex_t *IWSF_SkinFrame(void)
{
    uint32_t frame,i;
    float clock,rate;
    if(!iwsk_frame_matrices || !iwvm_skinned_vertices ||
       !iwsk_weights || iwsk_frame_count<2 || iwsk_joint_count==0 ||
       iw3_vm_anim_preview.value<0.5f)
        return iwvm_mesh.vertices;
    rate=iwsk_frame_rate*IWVM_Bounded(iw3_vm_anim_speed.value,0.05f,4.f,1.f);
    clock=(float)cl.time*rate;
    if(!isfinite(clock)) return iwvm_mesh.vertices;
    frame=(uint32_t)fmodf(fabsf(clock),(float)iwsk_frame_count);
    for(i=0;i<iwvm_mesh.vertex_count;++i) {
        uint32_t k;
        const iwvm_vertex_t *original=&iwvm_mesh.vertices[i];
        iwvm_vertex_t *dst=&iwvm_skinned_vertices[i];
        const iwsk_influence_t *w=&iwsk_weights[i];
        float xyz[3]={0.f,0.f,0.f};
        for(k=0;k<4u;++k) {
            const float weight=w->weight[k];
            const uint32_t b=w->bone[k];
            const float *m;
            uint32_t axis;
            if(weight<=0.f) continue;
            if(b>=iwsk_joint_count) return iwvm_mesh.vertices;
            m=iwsk_frame_matrices+((frame*iwsk_joint_count+b)*16u);
            for(axis=0;axis<3u;++axis)
                xyz[axis]+=weight*(m[axis]*original->xyz[0]+
                   m[4u+axis]*original->xyz[1]+
                   m[8u+axis]*original->xyz[2]+m[12u+axis]);
        }
        if(!isfinite(xyz[0]) || !isfinite(xyz[1]) || !isfinite(xyz[2]))
            return iwvm_mesh.vertices;
        dst->xyz[0]=xyz[0];
        dst->xyz[1]=xyz[1];
        dst->xyz[2]=xyz[2];
        dst->uv[0]=original->uv[0];
        dst->uv[1]=original->uv[1];
    }
#ifdef __ANDROID__
    if(!iwsk_logged_motion) {
        iwsk_logged_motion=1;
        __android_log_print(ANDROID_LOG_INFO,"VIRIL_IW3",
          "IW3_ORIGINAL_XANIM_SKELETAL_FRAME rendered=1 source=original_IW3 frame=%u weighted_vertices=%u exact_official=0",
          (unsigned)frame,(unsigned)iwvm_mesh.vertex_count);
    }
#endif
    return iwvm_skinned_vertices;
}

/* Optional RGBA color map. Private packer writes an IWVT file with the same
 * gun stem as IWVM in the NZ:P gamedir. Missing IWVT leaves flat geometry. */
static void IWVT_TryLoad(const char *mesh_path)
{
    FILE *f = NULL;
    uint8_t header[16];
    uint8_t *pixels = NULL;
    char texture_path[160];
    char *suffix;
    long length;
    uint32_t w, h;
    uint64_t bytes;
    GLint old_texture = 0;
    GLenum err;
    GLuint texture = 0;
    if (iwvm_color_attempted)
        return;
    iwvm_color_attempted = 1;
    if (snprintf(texture_path, sizeof(texture_path), "%s", mesh_path) >=
        (int)sizeof(texture_path)) return;
    suffix = strrchr(texture_path, '.');
    if (!suffix || strcmp(suffix, ".iwvm") != 0) return;
    strcpy(suffix, ".iwvt");
    length = COM_FOpenFile(texture_path, &f);
    if (length < 16 || !f) return;
    if (fread(header, 1, 16, f) != 16 ||
        memcmp(header, "IWVT", 4) != 0 || IWVM_Read32(header + 4) != 1)
        goto cleanup;
    w = IWVM_Read32(header + 8);
    h = IWVM_Read32(header + 12);
    if (!w || !h || w > 4096 || h > 4096) goto cleanup;
    bytes = 4ull * w * h;
    if (bytes + 16ull != (uint64_t)length || bytes > 64ull*1024*1024)
        goto cleanup;
    pixels = (uint8_t *)malloc((size_t)bytes);
    if (!pixels || fread(pixels, 1, (size_t)bytes, f) != (size_t)bytes)
        goto cleanup;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &old_texture);
    glGenTextures(1, &texture);
    if (!texture) goto cleanup;
    glBindTexture(GL_TEXTURE_2D, texture);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, (GLsizei)w, (GLsizei)h,
                 0, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    err = glGetError();
    glBindTexture(GL_TEXTURE_2D, (GLuint)old_texture);
    if (err != GL_NO_ERROR) {
        glDeleteTextures(1, &texture);
        texture = 0;
    } else {
        iwvm_color_texture = texture;
#ifdef __ANDROID__
        __android_log_print(ANDROID_LOG_INFO, "VIRIL_IW3",
            "IW3_COLOR_TEXTURE loaded=%s width=%u height=%u glerr=0",
            texture_path, (unsigned)w, (unsigned)h);
#endif
    }
cleanup:
    if (f) fclose(f);
    free(pixels);
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
    IWVT_TryLoad(path);
    IWSK_TryLoad(path);
    IWSF_TryLoad(path);
    const iwvm_vertex_t *draw_vertices=IWSF_SkinFrame();
    /* World/view GL projection and clipped viewmodel depth range are
     * inherited from Vril's existing R_DrawViewModel, never IW3 Direct3D. */
    GLint old_texture = 0;
    const GLboolean texture_was_enabled = glIsEnabled(GL_TEXTURE_2D);
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &old_texture);
    glPushMatrix();
    R_RotateForEntity(view,view->scale);
    /* Quake forward model basis: X forward, Y left, Z up. Keep controls
     * specific to optional IW3 geometry; original NZ:P MDL unchanged. */
    glTranslatef(
        IWVM_Bounded(iw3_vm_forward.value, -40.f, 40.f, 0.f),
        -IWVM_Bounded(iw3_vm_right.value, -40.f, 40.f, 0.f),
        IWVM_Bounded(iw3_vm_up.value, -40.f, 40.f, 0.f));
    glRotatef(IWVM_Bounded(iw3_vm_roll.value, -180.f, 180.f, 0.f),
              1.f, 0.f, 0.f);
    {
        const float sc=IWVM_Bounded(iw3_vm_scale.value, 0.05f, 5.f, 1.f);
        glScalef(sc, sc, sc);
    }
    glEnable(GL_DEPTH_TEST);
    if (iwvm_color_texture) {
        glEnable(GL_TEXTURE_2D);
        glBindTexture(GL_TEXTURE_2D, iwvm_color_texture);
        glEnableClientState(GL_TEXTURE_COORD_ARRAY);
        glTexCoordPointer(2,GL_FLOAT,sizeof(iwvm_vertex_t),&draw_vertices[0].uv[0]);
    } else {
        glDisable(GL_TEXTURE_2D);
    }
    glDisable(GL_ALPHA_TEST);
    glDisable(GL_BLEND);
    glDisable(GL_CULL_FACE);
    /* Preserve original COD4 base-color texels without 18% grey tint.
     * The flat untextured fallback remains subdued. */
    if (iwvm_color_texture)
        glColor4f(1.f,1.f,1.f,1.f);
    else
        glColor4f(0.82f,0.82f,0.82f,1.f);
    glEnableClientState(GL_VERTEX_ARRAY);
    glVertexPointer(3,GL_FLOAT,sizeof(iwvm_vertex_t),&draw_vertices[0].xyz[0]);
    glDrawElements(GL_TRIANGLES,iwvm_mesh.index_count,GL_UNSIGNED_SHORT,iwvm_mesh.indices);
#ifdef __ANDROID__
    if (!iwvm_reported_draw) {
        const GLenum iwvm_draw_error = glGetError();
        __android_log_print(iwvm_draw_error == GL_NO_ERROR ?
            ANDROID_LOG_INFO : ANDROID_LOG_ERROR, "VIRIL_IW3",
            "IW3_NATIVE_MESH_DRAW submitted model=%s vertices=%u triangles=%u glerr=%u",
            iwvm_mesh.name,(unsigned)iwvm_mesh.vertex_count,
            (unsigned)(iwvm_mesh.index_count/3),(unsigned)iwvm_draw_error);
        iwvm_reported_draw = 1;
    }
#endif
    glDisableClientState(GL_VERTEX_ARRAY);
    if (iwvm_color_texture)
        glDisableClientState(GL_TEXTURE_COORD_ARRAY);
    glBindTexture(GL_TEXTURE_2D, (GLuint)old_texture);
    if (!texture_was_enabled)
        glDisable(GL_TEXTURE_2D);
    glColor4f(1,1,1,1);
    if (gl_cull.value)
        glEnable(GL_CULL_FACE);
    if (texture_was_enabled)
        glEnable(GL_TEXTURE_2D);
    glEnable(GL_ALPHA_TEST);
    glPopMatrix();
    return 1;
}

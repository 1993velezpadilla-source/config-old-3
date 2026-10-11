#!/usr/bin/env python3
"""Isolate Sanctum-only XZSM OpenGL state from NZ:P weapon/viewmodel passes.

Dead Cell remains on stock renderer path. On Sanctum, the legacy staticmesh
pass changes culling/winding, alpha/blending, fog, lighting, depth flags and
texture mode. Without restoring the previous state, subsequent Quake alias
models (especially first-person guns) can be partially culled or misrendered.

This does not assert that all Sanctum weapon defects are solved. A real Android
same-weapon A/B screenshot gate is still required.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_xziel_xzsm_viewmodel_state.py <vril-root>")
p=Path(sys.argv[1])/"source/platform/sdl/gl/gl_xziel_staticmesh.c"
s=p.read_text(encoding="utf8")

before="""    glEnable(GL_TEXTURE_2D);
    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
    glDisable(GL_BLEND);
    glDisable(GL_ALPHA_TEST);"""
after="""    /* Save GL state before architecture pass. Alias gun models are drawn
     * later in this frame; they must never inherit XZSM's cull/texture state.
     * GL4ES fixed-function path: explicit glGet + restore (no glPushAttrib). */
    GLboolean had_texture = glIsEnabled(GL_TEXTURE_2D);
    GLboolean had_depth = glIsEnabled(GL_DEPTH_TEST);
    GLboolean had_blend = glIsEnabled(GL_BLEND);
    GLboolean had_alpha = glIsEnabled(GL_ALPHA_TEST);
    GLboolean had_cull = glIsEnabled(GL_CULL_FACE);
#ifdef GL_FOG
    GLboolean had_fog = glIsEnabled(GL_FOG);
#endif
#ifdef GL_LIGHTING
    GLboolean had_lighting = glIsEnabled(GL_LIGHTING);
#endif
    GLboolean had_depth_writes = GL_TRUE;
    GLint prev_cull_mode = GL_BACK;
    GLint prev_front_face = GL_CCW;
    GLint prev_depth_func = GL_LEQUAL;
    GLint prev_texenv_mode = GL_MODULATE;
    glGetBooleanv(GL_DEPTH_WRITEMASK, &had_depth_writes);
    glGetIntegerv(GL_CULL_FACE_MODE, &prev_cull_mode);
    glGetIntegerv(GL_FRONT_FACE, &prev_front_face);
    glGetIntegerv(GL_DEPTH_FUNC, &prev_depth_func);
    glGetTexEnviv(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, &prev_texenv_mode);

    glEnable(GL_TEXTURE_2D);
    glEnable(GL_DEPTH_TEST);
    glDepthMask(GL_TRUE);
    glDisable(GL_BLEND);
    glDisable(GL_ALPHA_TEST);"""
assert s.count(before)==1,"Could not find start of renderer draw state"
s=s.replace(before,after,1)

before="""    if (gl_cull.value)
        glEnable(GL_CULL_FACE);
    glColor4f(1, 1, 1, 1);
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE);
}"""
after="""    /* Full restoration before R_DrawEntities/R_DrawViewModel.
     * Do NOT infer the next pass's state from gl_cull: use the values
     * actually present before the XZSM architecture pass. */
    glCullFace((GLenum)prev_cull_mode);
    glFrontFace((GLenum)prev_front_face);
    glDepthFunc((GLenum)prev_depth_func);
    glDepthMask(had_depth_writes);
    glTexEnvf(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, (GLfloat)prev_texenv_mode);
    if (had_cull) glEnable(GL_CULL_FACE); else glDisable(GL_CULL_FACE);
    if (had_texture) glEnable(GL_TEXTURE_2D); else glDisable(GL_TEXTURE_2D);
    if (had_depth) glEnable(GL_DEPTH_TEST); else glDisable(GL_DEPTH_TEST);
    if (had_blend) glEnable(GL_BLEND); else glDisable(GL_BLEND);
    if (had_alpha) glEnable(GL_ALPHA_TEST); else glDisable(GL_ALPHA_TEST);
#ifdef GL_FOG
    if (had_fog) glEnable(GL_FOG); else glDisable(GL_FOG);
#endif
#ifdef GL_LIGHTING
    if (had_lighting) glEnable(GL_LIGHTING); else glDisable(GL_LIGHTING);
#endif
    glColor4f(1, 1, 1, 1);
}"""
assert s.count(before)==1,"Could not find end of renderer draw state"
s=s.replace(before,after,1)
assert 'glGetTexEnviv(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE' in s
assert 'glFrontFace((GLenum)prev_front_face);' in s
assert 'glDepthMask(had_depth_writes);' in s
assert 'R_DrawViewModel' not in s # render handoff is in gl_rmain
p.write_text(s,encoding="utf8")
print("XZIEL_XZSM_VIEWMODEL_GL_STATE_GUARD_INSTALLED")

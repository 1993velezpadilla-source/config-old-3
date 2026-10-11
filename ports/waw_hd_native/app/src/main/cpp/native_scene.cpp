// Native 3D arena proving movement, raycast, waves and multi-touch on Android.
// Fully original prototype; NOT original iPad game, map or source code.
#include "gameplay.h"
#include <GLES2/gl2.h>
#include <android/log.h>
#include <jni.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {
using native_demo::Game;
using native_demo::kPi;
constexpr size_t kMaxVertices = 50000;

struct V3 { float x, y, z; };
struct RGB { float r, g, b; };
struct Vertex { GLfloat x, y, z, r, g, b; };
struct Mat4 { float m[16]; };

std::array<Vertex, kMaxVertices> verts{};
GLsizei nVerts = 0;
GLuint shaderProgram = 0;
GLint positionLoc = -1, colorLoc = -1, matrixLoc = -1, alphaLoc = -1;
int screenW = 1, screenH = 1;
int leftPointer = -1, lookPointer = -1, firePointer = -1, adsPointer = -1, sprintPointer = -1;
float lookX = 0, lookY = 0;
int64_t lastMillis = -1;
Game game;
bool gameInitialized = false;

constexpr const char* kVertexShader = R"(
    attribute vec3 aPosition;
    attribute vec3 aColor;
    varying vec3 color;
    uniform mat4 uMatrix;
    void main() {
        color = aColor;
        gl_Position = uMatrix * vec4(aPosition, 1.0);
    }
)";
constexpr const char* kFragmentShader = R"(
    precision mediump float;
    varying vec3 color;
    uniform float uAlpha;
    void main() {
        gl_FragColor = vec4(color, uAlpha);
    }
)";

GLuint compile(GLenum stage, const char* source) {
    GLuint shader = glCreateShader(stage);
    glShaderSource(shader, 1, &source, nullptr);
    glCompileShader(shader);
    GLint ok = GL_FALSE;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        char info[1024] = {};
        glGetShaderInfoLog(shader, sizeof(info), nullptr, info);
        __android_log_print(ANDROID_LOG_ERROR, "WAW_NATIVE", "Shader: %s", info);
        glDeleteShader(shader);
        return 0;
    }
    return shader;
}
Mat4 identity() {
    return {{1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1}};
}
Mat4 multiply(const Mat4& a, const Mat4& b) {
    Mat4 r{};
    for (int col = 0; col < 4; ++col)
        for (int row = 0; row < 4; ++row)
            for (int k = 0; k < 4; ++k)
                r.m[col*4 + row] += a.m[k*4 + row] * b.m[col*4 + k];
    return r;
}
Mat4 perspective(float fovRadians, float aspect, float nearPlane, float farPlane) {
    const float f = 1.0f / std::tan(fovRadians / 2.0f);
    Mat4 r{};
    r.m[0] = f / aspect;
    r.m[5] = f;
    r.m[10] = (farPlane + nearPlane) / (nearPlane - farPlane);
    r.m[11] = -1;
    r.m[14] = (2 * nearPlane * farPlane) / (nearPlane - farPlane);
    return r;
}
Mat4 camera() {
    const float sy = std::sin(game.yaw), cy = std::cos(game.yaw);
    const float sp = std::sin(game.pitch), cp = std::cos(game.pitch);
    const V3 forward{sy*cp, sp, -cy*cp};
    const V3 right{cy, 0.0f, sy};
    const V3 up{-sy*sp, cp, cy*sp};
    const float eyeY = 1.60f + (game.moving ? 0.028f * std::sin(game.time*11) : 0.0f);
    Mat4 view{{
        right.x, up.x, -forward.x, 0.0f,
        right.y, up.y, -forward.y, 0.0f,
        right.z, up.z, -forward.z, 0.0f,
        -(right.x*game.px + right.y*eyeY + right.z*game.pz),
        -(up.x*game.px + up.y*eyeY + up.z*game.pz),
        (forward.x*game.px + forward.y*eyeY + forward.z*game.pz),
        1.0f
    }};
    const float fov = game.ads ? 53.0f : 78.0f;
    Mat4 proj = perspective(fov*kPi/180.0f,
                            static_cast<float>(screenW)/static_cast<float>(screenH),
                            0.06f, 110.0f);
    return multiply(proj, view);
}
void triangle(V3 a, V3 b, V3 c, RGB color) {
    if (nVerts+3 > static_cast<GLsizei>(verts.size())) return;
    verts[static_cast<size_t>(nVerts++)] = {a.x,a.y,a.z,color.r,color.g,color.b};
    verts[static_cast<size_t>(nVerts++)] = {b.x,b.y,b.z,color.r,color.g,color.b};
    verts[static_cast<size_t>(nVerts++)] = {c.x,c.y,c.z,color.r,color.g,color.b};
}
void quad(V3 a, V3 b, V3 c, V3 d, RGB color) {
    triangle(a,b,c,color);
    triangle(a,c,d,color);
}
void box(float x1, float y1, float z1, float x2, float y2, float z2, RGB c) {
    const RGB dim{c.r*.70f,c.g*.70f,c.b*.70f};
    const RGB side{c.r*.82f,c.g*.82f,c.b*.82f};
    const RGB top{std::min(1.0f,c.r*1.12f),
                  std::min(1.0f,c.g*1.12f),
                  std::min(1.0f,c.b*1.12f)};
    quad({x1,y1,z1},{x2,y1,z1},{x2,y2,z1},{x1,y2,z1},c);
    quad({x2,y1,z2},{x1,y1,z2},{x1,y2,z2},{x2,y2,z2},dim);
    quad({x1,y1,z2},{x1,y1,z1},{x1,y2,z1},{x1,y2,z2},side);
    quad({x2,y1,z1},{x2,y1,z2},{x2,y2,z2},{x2,y2,z1},side);
    quad({x1,y2,z1},{x2,y2,z1},{x2,y2,z2},{x1,y2,z2},top);
    quad({x1,y1,z2},{x2,y1,z2},{x2,y1,z1},{x1,y1,z1},dim);
}
void drawArena() {
    // Entirely geometric, low-poly test room; not the Nacht map.
    for (int x = -10; x < 10; x += 2)
        for (int z = -20; z < 10; z += 2) {
            const float v = ((x/2+z/2)&1) ? 0.128f : 0.115f;
            quad({static_cast<float>(x),-.08f,static_cast<float>(z)},
                 {static_cast<float>(x+2),-.08f,static_cast<float>(z)},
                 {static_cast<float>(x+2),-.08f,static_cast<float>(z+2)},
                 {static_cast<float>(x),-.08f,static_cast<float>(z+2)},
                 {v,v*1.04f,v*.98f});
        }
    box(-10,3.70f,-20,10,3.82f,10,{.09f,.095f,.105f});
    box(-10,0,-20,-9.80f,3.7f,10,{.235f,.26f,.275f});
    box(9.80f,0,-20,10,3.7f,10,{.205f,.235f,.25f});
    box(-10,0,-20,10,3.7f,-19.8f,{.18f,.205f,.235f});
    box(-10,0,9.80f,10,3.7f,10,{.19f,.21f,.24f});

    for (int i = 0; i < 6; ++i) {
        const float z = -17.5f + static_cast<float>(i)*4.4f;
        // Low-poly windows inset into the corridor walls.
        box(-9.79f,1.15f,z,-9.75f,2.85f,z+2.0f,{.018f,.025f,.045f});
        box(9.75f,1.15f,z,9.79f,2.85f,z+2.0f,{.018f,.025f,.045f});
        for (int j=1; j<=2; ++j) {
            const float at = z + .67f*static_cast<float>(j);
            box(-9.74f,1.15f,at,-9.71f,2.85f,at+.08f,{.30f,.30f,.29f});
            box(9.71f,1.15f,at,9.74f,2.85f,at+.08f,{.30f,.30f,.29f});
        }
        box(-9.72f,1.92f,z,-9.68f,2.05f,z+2.0f,{.30f,.30f,.29f});
        box(9.68f,1.92f,z,9.72f,2.05f,z+2.0f,{.30f,.30f,.29f});
    }
    for (float z = -16.0f; z <= 6.0f; z += 5.5f) {
        box(-8.85f,0,z,-8.18f,3.70f,z+.68f,{.33f,.34f,.36f});
        box(8.18f,0,z,8.85f,3.70f,z+.68f,{.30f,.32f,.34f});
        box(-8.18f,3.18f,z,8.18f,3.65f,z+.50f,{.27f,.275f,.28f});
    }
    box(-7.5f,0.0f,-7.4f,-5.7f,1.25f,-5.5f,{.27f,.20f,.145f});
    box(5.5f,0.0f,-13.4f,7.7f,1.55f,-11.1f,{.25f,.18f,.13f});
    box(-1.5f,0.0f,-18.7f,1.5f,1.2f,-18.0f,{.17f,.14f,.12f});
    // Red emergency wall lights on each side.
    for (float z=-15.0f; z<8.0f; z+=7.0f) {
        box(-9.7f,2.75f,z,-9.56f,3.03f,z+.38f,{.72f,.055f,.036f});
        box(9.56f,2.75f,z,9.7f,3.03f,z+.38f,{.72f,.055f,.036f});
    }
}
void drawEnemy(const native_demo::Enemy& e, int index) {
    const float x=e.x, z=e.z;
    const float bob = .045f * std::sin(game.time*4.5f + static_cast<float>(index)*1.5f);
    const float swing = .12f * std::sin(game.time*3.0f + static_cast<float>(index));
    const RGB shirt{.30f,.39f,.32f}, skin{.53f,.51f,.43f}, trousers{.22f,.25f,.24f};
    box(x-.27f,.95f+bob,z-.18f,x+.27f,1.69f+bob,z+.18f,shirt);
    box(x-.21f,1.71f+bob,z-.19f,x+.21f,2.10f+bob,z+.19f,skin);
    box(x-.20f,.06f,z-.13f,x-.035f,.93f+bob+swing,z+.12f,trousers);
    box(x+.035f,.06f,z-.13f,x+.20f,.93f+bob-swing,z+.12f,trousers);
    box(x-.43f,.85f+bob,z-.12f,x-.28f,1.53f+bob,z+.13f,skin);
    box(x+.28f,.85f+bob,z-.12f,x+.43f,1.53f+bob,z+.13f,skin);
    box(x-.16f,1.92f+bob,z+.192f,x-.06f,1.98f+bob,z+.215f,{.97f,.11f,.07f});
    box(x+.06f,1.92f+bob,z+.192f,x+.16f,1.98f+bob,z+.215f,{.97f,.11f,.07f});
}
void flush(const Mat4& matrix, float alpha) {
    if (!shaderProgram || nVerts <= 0) return;
    glUseProgram(shaderProgram);
    glUniformMatrix4fv(matrixLoc,1,GL_FALSE,matrix.m);
    glUniform1f(alphaLoc,alpha);
    glBindBuffer(GL_ARRAY_BUFFER,0);
    glVertexAttribPointer(static_cast<GLuint>(positionLoc),3,GL_FLOAT,GL_FALSE,
                          sizeof(Vertex),verts.data());
    glVertexAttribPointer(static_cast<GLuint>(colorLoc),3,GL_FLOAT,GL_FALSE,
                          sizeof(Vertex),&verts[0].r);
    glEnableVertexAttribArray(static_cast<GLuint>(positionLoc));
    glEnableVertexAttribArray(static_cast<GLuint>(colorLoc));
    glDrawArrays(GL_TRIANGLES,0,nVerts);
    glDisableVertexAttribArray(static_cast<GLuint>(positionLoc));
    glDisableVertexAttribArray(static_cast<GLuint>(colorLoc));
}
void rect(float x1,float y1,float x2,float y2,RGB c) {
    auto clip=[](float x,float y)->V3{return {2.0f*x-1.0f,1.0f-2.0f*y,0};};
    quad(clip(x1,y1),clip(x2,y1),clip(x2,y2),clip(x1,y2),c);
}
void circle(float cx,float cy,float radiusH,RGB c) {
    constexpr int segments=24;
    const float rw=radiusH*static_cast<float>(screenH)/static_cast<float>(screenW);
    auto clip=[](float x,float y)->V3{return {2.0f*x-1.0f,1.0f-2.0f*y,0};};
    for(int i=0;i<segments;++i) {
        const float a=2*kPi*static_cast<float>(i)/segments;
        const float b=2*kPi*static_cast<float>(i+1)/segments;
        triangle(clip(cx,cy),
                 clip(cx+rw*std::cos(a),cy+radiusH*std::sin(a)),
                 clip(cx+rw*std::cos(b),cy+radiusH*std::sin(b)),c);
    }
}
struct Glyph { char c; uint8_t p[7]; };
constexpr Glyph font[]={
{'A',{14,17,17,31,17,17,17}}, {'B',{30,17,17,30,17,17,30}},
{'C',{14,17,16,16,16,17,14}}, {'D',{30,17,17,17,17,17,30}},
{'E',{31,16,16,30,16,16,31}}, {'F',{31,16,16,30,16,16,16}},
{'G',{14,17,16,23,17,17,14}}, {'H',{17,17,17,31,17,17,17}},
{'I',{14,4,4,4,4,4,14}}, {'J',{7,2,2,2,18,18,12}},
{'K',{17,18,20,24,20,18,17}}, {'L',{16,16,16,16,16,16,31}},
{'M',{17,27,21,21,17,17,17}}, {'N',{17,25,21,19,17,17,17}},
{'O',{14,17,17,17,17,17,14}}, {'P',{30,17,17,30,16,16,16}},
{'Q',{14,17,17,17,21,18,13}}, {'R',{30,17,17,30,20,18,17}},
{'S',{15,16,16,14,1,1,30}}, {'T',{31,4,4,4,4,4,4}},
{'U',{17,17,17,17,17,17,14}}, {'V',{17,17,17,17,10,10,4}},
{'W',{17,17,17,21,21,21,10}}, {'X',{17,17,10,4,10,17,17}},
{'Y',{17,17,10,4,4,4,4}}, {'Z',{31,1,2,4,8,16,31}},
{'0',{14,17,19,21,25,17,14}}, {'1',{4,12,4,4,4,4,14}},
{'2',{14,17,1,2,4,8,31}}, {'3',{30,1,1,14,1,1,30}},
{'4',{2,6,10,18,31,2,2}}, {'5',{31,16,16,30,1,1,30}},
{'6',{14,16,16,30,17,17,14}}, {'7',{31,1,2,4,8,8,8}},
{'8',{14,17,17,14,17,17,14}}, {'9',{14,17,17,15,1,1,14}},
{'/',{1,1,2,4,8,16,16}}, {':',{0,4,4,0,4,4,0}},
{'-',{0,0,0,31,0,0,0}}, {' ',{0,0,0,0,0,0,0}},
{'!',{4,4,4,4,4,0,4}}
};
const Glyph* lookup(char c) {
    for(const auto& glyph:font) if(glyph.c==c) return &glyph;
    return &font[sizeof(font)/sizeof(font[0])-1];
}
void text(float x,float y,const char* msg,float scale,RGB color={.92f,.95f,.95f}) {
    for(const char* p=msg;*p;++p) {
        if(x+5*scale > screenW-2.0f) break;
        const Glyph* g=lookup(*p);
        for(int row=0;row<7;++row) for(int col=0;col<5;++col) {
            if ((g->p[row] & (1u<<(4-col))) == 0) continue;
            const float xx=(x+static_cast<float>(col)*scale)/static_cast<float>(screenW);
            const float yy=(y+static_cast<float>(row)*scale)/static_cast<float>(screenH);
            rect(xx,yy,xx+scale/static_cast<float>(screenW),
                 yy+scale/static_cast<float>(screenH),color);
        }
        x += 6*scale;
    }
}
void hud() {
    glDisable(GL_DEPTH_TEST);
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA);
    nVerts=0;
    const RGB neutral{.16f,.48f,.57f};
    const RGB active{.26f,.68f,.78f};
    circle(.15f,.79f,.125f,game.moving?active:neutral);
    circle(.88f,.79f,.11f,firePointer>=0?RGB{.87f,.23f,.19f}:RGB{.48f,.16f,.14f});
    circle(.88f,.28f,.079f,game.ads?active:neutral);
    circle(.69f,.79f,.075f,game.reloading?RGB{.52f,.42f,.18f}:neutral);
    circle(.13f,.45f,.073f,game.sprint?active:neutral);
    rect(.491f,.474f,.509f,.479f,{1,1,1});
    rect(.498f,.457f,.502f,.497f,{1,1,1});
    if(game.lastShot >= 0 && game.time-game.lastShot<.10f) {
        circle(.5f,.5f,.015f,{.95f,.72f,.22f});
    }
    if(game.dead) rect(0.0f,.33f,1.0f,.67f,{.24f,.03f,.04f});
    flush(identity(),.53f);

    nVerts=0;
    const float size=std::clamp(static_cast<float>(screenH)/340.0f,2.0f,4.4f);
    char line[128];
    std::snprintf(line,sizeof(line),"WAVE %d  HP %d  KILLS %d",game.wave,game.health,game.kills);
    text(18,15,line,size);
    text(.45f*screenW,15,"V03 NATIVE FPS TEST",size*.92f,{.25f,.91f,.38f});
    std::snprintf(line,sizeof(line),"AMMO %d/%d",game.ammo,game.reserve);
    text(18,26+8*size,line,size,{.91f,.78f,.40f});
    if(game.reloading) text(18,38+16*size,"RELOADING",size,{1,.62f,.32f});
    if(game.enemiesAlive==0 && !game.dead)
        text(18,38+16*size,"NEXT WAVE",size,{1,.62f,.32f});
    text(.88f*screenW-3.0f*size,.79f*screenH-3.0f*size,"FIRE",size*.78f);
    text(.88f*screenW-2.8f*size,.28f*screenH-3.0f*size,"ADS",size*.72f);
    text(.69f*screenW-3.0f*size,.79f*screenH-3.0f*size,"RLD",size*.78f);
    text(.13f*screenW-3.0f*size,.45f*screenH-3.0f*size,"RUN",size*.72f);
    text(18,screenH-15.0f*size,"ARM64 NATIVE DEMO - NO ORIGINAL ASSETS",size*.65f);
    if(game.dead) {
        text(.27f*screenW,.40f*screenH,"YOU DIED",size*1.3f,{1,.70f,.70f});
        text(.25f*screenW,.52f*screenH,"TAP TO RESTART",size*1.0f);
    }
    flush(identity(),1.0f);
    glDisable(GL_BLEND);
    glEnable(GL_DEPTH_TEST);
}
void moveStick(float x,float y,float width,float height) {
    const float radius=.135f*height;
    game.joystickX=std::clamp((x-.15f*width)/radius,-1.0f,1.0f);
    game.joystickY=std::clamp((.79f*height-y)/radius,-1.0f,1.0f);
    game.moving=true;
}
void onTouch(int action,int id,float x,float y,int w,int h) {
    const float width=static_cast<float>(std::max(w,1));
    const float height=static_cast<float>(std::max(h,1));
    if(action==0 || action==5) { // DOWN or POINTER_DOWN
        if(game.dead) { game.reset(); lastMillis=-1; return; }
        if(x<width*.36f && y>height*.57f && leftPointer<0) {
            leftPointer=id; moveStick(x,y,width,height);
        } else if(x<width*.32f && y<height*.54f && y>height*.27f && sprintPointer<0) {
            sprintPointer=id; game.sprint=true;
        } else if(x>width*.80f && y>height*.65f && firePointer<0) {
            firePointer=id; game.fire();
        } else if(x>width*.77f && y<height*.43f && adsPointer<0) {
            adsPointer=id; game.ads=true;
        } else if(x>width*.60f && x<width*.80f && y>height*.67f) {
            game.startReload();
        } else if(x>width*.34f && lookPointer<0) {
            lookPointer=id; lookX=x; lookY=y;
        }
    } else if(action==2) { // MOVE (every active pointer)
        if(id==leftPointer) moveStick(x,y,width,height);
        if(id==lookPointer) {
            const float sensitivity=game.ads?1.7f:3.0f;
            game.yaw += (x-lookX)/width*sensitivity;
            game.pitch=std::clamp(game.pitch-(y-lookY)/height*sensitivity,-1.10f,1.10f);
            lookX=x; lookY=y;
        }
    } else if(action==1 || action==3 || action==6) { // UP, CANCEL, POINTER_UP
        if(id==leftPointer) {
            leftPointer=-1; game.joystickX=game.joystickY=0; game.moving=false;
        }
        if(id==lookPointer) lookPointer=-1;
        if(id==firePointer) firePointer=-1;
        if(id==adsPointer) { adsPointer=-1; game.ads=false; }
        if(id==sprintPointer) { sprintPointer=-1; game.sprint=false; }
    }
}
} // namespace

extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeInit(JNIEnv*,jclass) {
    if(!gameInitialized) { game.reset(); gameInitialized=true; }
    lastMillis=-1;
    const GLuint v=compile(GL_VERTEX_SHADER,kVertexShader);
    const GLuint f=compile(GL_FRAGMENT_SHADER,kFragmentShader);
    if(!v || !f) {
        if(v) glDeleteShader(v);
        if(f) glDeleteShader(f);
        shaderProgram=0;
        return;
    }
    shaderProgram=glCreateProgram();
    glAttachShader(shaderProgram,v);
    glAttachShader(shaderProgram,f);
    glBindAttribLocation(shaderProgram,0,"aPosition");
    glBindAttribLocation(shaderProgram,1,"aColor");
    glLinkProgram(shaderProgram);
    GLint linked=0;
    glGetProgramiv(shaderProgram,GL_LINK_STATUS,&linked);
    glDeleteShader(v); glDeleteShader(f);
    if(!linked) {
        char info[1024]={};
        glGetProgramInfoLog(shaderProgram,sizeof(info),nullptr,info);
        __android_log_print(ANDROID_LOG_ERROR,"WAW_NATIVE","Link: %s",info);
        glDeleteProgram(shaderProgram); shaderProgram=0; return;
    }
    positionLoc=glGetAttribLocation(shaderProgram,"aPosition");
    colorLoc=glGetAttribLocation(shaderProgram,"aColor");
    matrixLoc=glGetUniformLocation(shaderProgram,"uMatrix");
    alphaLoc=glGetUniformLocation(shaderProgram,"uAlpha");
    glDisable(GL_CULL_FACE);
    glEnable(GL_DEPTH_TEST);
    glDepthFunc(GL_LEQUAL);
    glClearDepthf(1.0f);
    glDisable(GL_BLEND);
}
extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeResize(JNIEnv*,jclass,jint w,jint h) {
    screenW=std::max(static_cast<int>(w),1);
    screenH=std::max(static_cast<int>(h),1);
    glViewport(0,0,screenW,screenH);
}
extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeTouch(
    JNIEnv*,jclass,jint action,jint pointerId,jfloat x,jfloat y,jint w,jint h) {
    onTouch(action,pointerId,x,y,w,h);
}
extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeFrame(JNIEnv*,jclass,jlong uptimeMillis) {
    const int64_t now=static_cast<int64_t>(uptimeMillis);
    const float dt=lastMillis<0?0.0f:std::clamp((now-lastMillis)/1000.0f,0.0f,.05f);
    lastMillis=now;
    game.update(dt);
    if(firePointer>=0) game.fire();

    glViewport(0,0,screenW,screenH);
    glClearColor(.018f,.022f,.033f,1.0f);
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT);
    if(!shaderProgram) return;

    nVerts=0;
    drawArena();
    for(int i=0;i<game.enemyCount;++i) {
        const auto& e=game.enemies[static_cast<size_t>(i)];
        if(e.active) drawEnemy(e,i);
    }
    glEnable(GL_DEPTH_TEST);
    flush(camera(),1.0f);
    hud();
}

// Independently written Android GLES2 native bootstrap.
// Absolutely no iOS executable, touchHLE, copyrighted art or game code.
#include <jni.h>
#include <GLES2/gl2.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace {
constexpr float kPi = 3.14159265358979323846f;
constexpr std::size_t kMaxVerts = 1024;

struct Vertex {
    GLfloat x, y, r, g, b;
};

GLuint program = 0;
GLint locPos = -1;
GLint locColor = -1;
int screenW = 1;
int screenH = 1;
std::array<Vertex, kMaxVerts> verts{};
GLsizei count = 0;
float yaw = 0.0f;
float movement = 0.0f;
float lastTouchX = 0.0f;
bool looking = false;
bool walking = false;
std::int64_t lastShotMs = -10000;

constexpr const char* vs = R"(
    attribute vec2 aPos;
    attribute vec3 aColor;
    varying vec3 vColor;
    void main() {
        gl_Position = vec4(aPos, 0.0, 1.0);
        vColor = aColor;
    }
)";
constexpr const char* fs = R"(
    precision mediump float;
    varying vec3 vColor;
    void main() { gl_FragColor = vec4(vColor, 1.0); }
)";

GLuint shader(GLenum kind, const char* source) {
    GLuint id = glCreateShader(kind);
    glShaderSource(id, 1, &source, nullptr);
    glCompileShader(id);
    GLint ok = GL_FALSE;
    glGetShaderiv(id, GL_COMPILE_STATUS, &ok);
    if (!ok) {
        glDeleteShader(id);
        return 0;
    }
    return id;
}

void tri(float ax, float ay, float bx, float by, float cx, float cy,
         float r, float g, float b) {
    if (count + 3 > static_cast<GLsizei>(verts.size())) return;
    verts[static_cast<std::size_t>(count++)] = {ax, ay, r, g, b};
    verts[static_cast<std::size_t>(count++)] = {bx, by, r, g, b};
    verts[static_cast<std::size_t>(count++)] = {cx, cy, r, g, b};
}

void quad(float x1, float y1, float x2, float y2,
          float r, float g, float b) {
    tri(x1, y1, x2, y1, x2, y2, r, g, b);
    tri(x1, y1, x2, y2, x1, y2, r, g, b);
}

void diamond(float x, float y, float radius, float r, float g, float b) {
    constexpr int sides = 20;
    for (int i = 0; i < sides; ++i) {
        const float a = static_cast<float>(i) * (2.0f * kPi / sides);
        const float c = static_cast<float>(i + 1) * (2.0f * kPi / sides);
        tri(x, y,
            x + radius * std::cos(a), y + radius * std::sin(a),
            x + radius * std::cos(c), y + radius * std::sin(c),
            r, g, b);
    }
}
} // namespace

extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeInit(JNIEnv*, jclass) {
    // GLSurfaceView can recreate its EGL context, so always rebuild GL objects.
    const GLuint vertex = shader(GL_VERTEX_SHADER, vs);
    const GLuint fragment = shader(GL_FRAGMENT_SHADER, fs);
    if (!vertex || !fragment) return;
    program = glCreateProgram();
    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glBindAttribLocation(program, 0, "aPos");
    glBindAttribLocation(program, 1, "aColor");
    glLinkProgram(program);
    GLint linked = GL_FALSE;
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    glDeleteShader(vertex);
    glDeleteShader(fragment);
    if (!linked) {
        glDeleteProgram(program);
        program = 0;
        return;
    }
    locPos = glGetAttribLocation(program, "aPos");
    locColor = glGetAttribLocation(program, "aColor");
    glDisable(GL_DEPTH_TEST);
}

extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeResize(JNIEnv*, jclass,
                                                             jint w, jint h) {
    screenW = std::max(static_cast<int>(w), 1);
    screenH = std::max(static_cast<int>(h), 1);
    glViewport(0, 0, screenW, screenH);
}

extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeTouch(
        JNIEnv*, jclass, jint action, jfloat x, jfloat y, jint w, jint h) {
    const float width = std::max(static_cast<float>(w), 1.0f);
    const float height = std::max(static_cast<float>(h), 1.0f);
    if (action == 0 || action == 5) { // ACTION_DOWN / ACTION_POINTER_DOWN
        lastTouchX = x;
        if (x >= width * 0.50f) {
            looking = true;
            lastShotMs = -1; // populated from frame clock on next render
        } else {
            walking = true;
            movement = (0.50f - y / height) * 2.0f;
        }
    } else if (action == 2) { // ACTION_MOVE
        if (looking) {
            yaw = std::clamp(yaw + (x - lastTouchX) / width, -0.8f, 0.8f);
            lastTouchX = x;
        }
        if (walking) {
            movement = (0.50f - y / height) * 2.0f;
        }
    } else if (action == 1 || action == 3 || action == 6) { // UP / CANCEL / POINTER_UP
        looking = false;
        walking = false;
        movement = 0.0f;
    }
}

extern "C" JNIEXPORT void JNICALL
Java_org_zombies_wawhd_nativeport_MainActivity_nativeFrame(JNIEnv*, jclass,
                                                             jlong uptime) {
    const std::int64_t now = static_cast<std::int64_t>(uptime);
    if (lastShotMs == -1) lastShotMs = now;
    const bool flash = now - lastShotMs >= 0 && now - lastShotMs < 150;
    count = 0;
    const float offset = yaw * 0.35f;
    const float wave = 0.025f * std::sin(static_cast<float>(now % 2000) * 0.003f);
    const float bob = movement * wave;

    // Purely procedural test drawing: an abstract corridor, distant test target,
    // crosshair and two touch zones. THIS IS NOT NACHT OR GAMEPLAY.
    quad(-1.0f, -1.0f, 1.0f, -0.27f + bob, 0.105f, 0.125f, 0.135f);
    quad(-1.0f, 0.62f + bob, 1.0f, 1.0f, 0.070f, 0.075f, 0.090f);
    tri(-1.0f, -1.0f, -0.31f + offset, -0.31f + bob, -0.31f + offset, 0.60f + bob,
        0.19f, 0.22f, 0.24f);
    tri(-1.0f, -1.0f, -0.31f + offset, 0.60f + bob, -1.0f, 1.0f,
        0.19f, 0.22f, 0.24f);
    tri(1.0f, -1.0f, 0.31f + offset, -0.31f + bob, 0.31f + offset, 0.60f + bob,
        0.155f, 0.19f, 0.20f);
    tri(1.0f, -1.0f, 0.31f + offset, 0.60f + bob, 1.0f, 1.0f,
        0.155f, 0.19f, 0.20f);
    quad(-0.31f + offset, -0.31f + bob, 0.31f + offset, 0.60f + bob,
         0.024f, 0.028f, 0.038f);
    diamond(offset, 0.09f + bob, 0.095f, flash ? 1.0f : 0.67f, 0.07f, 0.065f);
    quad(-0.033f, -0.004f, 0.033f, 0.004f, 0.90f, 0.90f, 0.90f);
    quad(-0.004f, -0.035f, 0.004f, 0.035f, 0.90f, 0.90f, 0.90f);
    // On-screen translucent joystick placeholders, genuinely touch-responsive.
    diamond(-0.79f, -0.69f, 0.14f, walking ? 0.23f : 0.11f, 0.37f, 0.42f);
    diamond(0.79f, -0.69f, 0.13f, looking ? 0.35f : 0.19f, 0.27f, 0.36f);

    glClearColor(flash ? 0.24f : 0.025f, 0.032f, 0.041f, 1.0f);
    glClear(GL_COLOR_BUFFER_BIT);
    if (program == 0 || count <= 0 || locPos < 0 || locColor < 0) return;
    glUseProgram(program);
    glVertexAttribPointer(static_cast<GLuint>(locPos), 2, GL_FLOAT, GL_FALSE,
                          sizeof(Vertex), verts.data());
    glVertexAttribPointer(static_cast<GLuint>(locColor), 3, GL_FLOAT, GL_FALSE,
                          sizeof(Vertex), &verts[0].r);
    glEnableVertexAttribArray(static_cast<GLuint>(locPos));
    glEnableVertexAttribArray(static_cast<GLuint>(locColor));
    glDrawArrays(GL_TRIANGLES, 0, count);
    glDisableVertexAttribArray(static_cast<GLuint>(locPos));
    glDisableVertexAttribArray(static_cast<GLuint>(locColor));
}

// Authentic KisakCOD IW3 R_ChangeStreamSource -> GLES3 vertex-buffer boundary.
// D3D stream slots are tracked separately: GL_ARRAY_BUFFER binding is global and
// is NOT equivalent to a D3D stream slot. A future original vertex-declaration
// bridge must consume these slots to configure glVertexAttribPointer on a VAO.
// No fabricated mesh, vertex attributes, shader, or VBO are created here.
#if defined(__ANDROID__)
#include "r_android_vertex_stream.h"
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <cstddef>
#include <limits>
#include <unordered_map>

namespace {
struct Buffer { GLuint id; std::size_t bytes; };
struct Stream { const void *handle; std::size_t offset; std::size_t stride; };
std::unordered_map<const void *, Buffer> buffers;
Stream streams[2] = {};
EGLDisplay ownerDisplay = EGL_NO_DISPLAY;
EGLContext ownerContext = EGL_NO_CONTEXT;

bool HasOwner()
{
    const EGLDisplay d = eglGetCurrentDisplay();
    const EGLContext c = eglGetCurrentContext();
    return d != EGL_NO_DISPLAY && c != EGL_NO_CONTEXT
        && (ownerContext == EGL_NO_CONTEXT
            || (ownerDisplay == d && ownerContext == c));
}
bool AdoptOwner()
{
    if (!HasOwner()) return false;
    if (ownerContext == EGL_NO_CONTEXT) {
        ownerDisplay = eglGetCurrentDisplay();
        ownerContext = eglGetCurrentContext();
    }
    return true;
}
// GL_ARRAY_BUFFER is only temporarily bound for size verification. Preserve
// caller state even on GL errors; do not pretend this configures a vertex VAO.
bool ValidateBuffer(GLuint id, std::size_t requiredBytes)
{
    if (!id || !requiredBytes || glGetError() != GL_NO_ERROR
        || glIsBuffer(id) != GL_TRUE)
        return false;
    GLint previous = 0;
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &previous);
    if (glGetError() != GL_NO_ERROR) return false;
    glBindBuffer(GL_ARRAY_BUFFER, id);
    if (glGetError() != GL_NO_ERROR) {
        glBindBuffer(GL_ARRAY_BUFFER, static_cast<GLuint>(previous));
        glGetError();
        return false;
    }
    GLint size = -1;
    glGetBufferParameteriv(GL_ARRAY_BUFFER, GL_BUFFER_SIZE, &size);
    const bool valid = glGetError() == GL_NO_ERROR
        && size >= 0 && static_cast<std::size_t>(size) >= requiredBytes;
    glBindBuffer(GL_ARRAY_BUFFER, static_cast<GLuint>(previous));
    return glGetError() == GL_NO_ERROR && valid;
}
}

bool R_AndroidGlesRegisterVertexBuffer(const void *handle, unsigned int id,
                                        std::size_t byteCount)
{
    if (!handle || !AdoptOwner() || buffers.find(handle) != buffers.end()
        || !ValidateBuffer(id, byteCount))
        return false;
    return buffers.emplace(handle, Buffer{id, byteCount}).second;
}

bool R_AndroidGlesUnregisterVertexBuffer(const void *handle)
{
    if (!handle || !HasOwner()) return false;
    auto found = buffers.find(handle);
    if (found == buffers.end()) return false;
    for (auto &stream : streams)
        if (stream.handle == handle) stream = {};
    buffers.erase(found); // GL object remains owned by original resource allocator.
    return true;
}

bool R_AndroidGlesChangeStreamSource(unsigned int streamIndex,
                                     const void *handle,
                                     std::size_t byteOffset, std::size_t stride)
{
    if (streamIndex >= 2 || !AdoptOwner()) return false;
    if (!handle) {
        if (byteOffset || stride) return false;
        streams[streamIndex] = {};
        return true;
    }
    auto found = buffers.find(handle);
    if (found == buffers.end() || !stride
        || byteOffset >= found->second.bytes
        || stride > found->second.bytes - byteOffset
        || !ValidateBuffer(found->second.id, found->second.bytes))
        return false;
    streams[streamIndex] = {handle, byteOffset, stride};
    return true;
}

bool R_AndroidGlesGetStreamSource(unsigned int streamIndex, unsigned int *id,
                                  std::size_t *offset, std::size_t *stride)
{
    if (streamIndex >= 2 || !id || !offset || !stride || !HasOwner())
        return false;
    const Stream &stream = streams[streamIndex];
    if (!stream.handle) return false;
    auto found = buffers.find(stream.handle);
    if (found == buffers.end() || !ValidateBuffer(found->second.id, found->second.bytes))
        return false;
    *id = found->second.id;
    *offset = stream.offset;
    *stride = stream.stride;
    return true;
}

void R_AndroidGlesInvalidateVertexStreams()
{
    // Only the owning EGL lifecycle may call this after detaching the context.
    // GL objects are never deleted here.
    buffers.clear();
    streams[0] = {};
    streams[1] = {};
    ownerDisplay = EGL_NO_DISPLAY;
    ownerContext = EGL_NO_CONTEXT;
}
#endif

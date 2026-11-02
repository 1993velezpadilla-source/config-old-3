// Original KisakCOD IW3 indexed-triangle command -> GLES3 boundary.
// No fabricated mesh, shader, vertex layout, or GL buffer is created here.
#if defined(__ANDROID__)
#include "r_android_indexed_draw.h"
#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <cstdint>
#include <limits>
#include <unordered_map>

namespace {
struct IndexBuffer { GLuint id; std::size_t indices; };
std::unordered_map<const void *, IndexBuffer> buffers;
const void *boundHandle = nullptr;
EGLDisplay ownerDisplay = EGL_NO_DISPLAY;
EGLContext ownerContext = EGL_NO_CONTEXT;

bool HasOwner()
{
    const EGLDisplay display = eglGetCurrentDisplay();
    const EGLContext context = eglGetCurrentContext();
    return display != EGL_NO_DISPLAY && context != EGL_NO_CONTEXT
        && (ownerContext == EGL_NO_CONTEXT
            || (ownerDisplay == display && ownerContext == context));
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
}

bool R_AndroidGlesRegisterIndexBuffer(const void *handle, unsigned int id,
                                      std::size_t indexCount)
{
    if (!handle || !id || !indexCount || !AdoptOwner()
        || glGetError() != GL_NO_ERROR || glIsBuffer(id) != GL_TRUE
        || buffers.find(handle) != buffers.end())
        return false;
    return buffers.emplace(handle, IndexBuffer{id, indexCount}).second;
}

bool R_AndroidGlesUnregisterIndexBuffer(const void *handle)
{
    if (!handle || !HasOwner()) return false;
    const auto found = buffers.find(handle);
    if (found == buffers.end()) return false;
    if (boundHandle == handle) boundHandle = nullptr;
    buffers.erase(found);
    return true; // The real image/buffer owner releases the GL object.
}

bool R_AndroidGlesBindIndexBuffer(const void *handle)
{
    if (!AdoptOwner() || glGetError() != GL_NO_ERROR) return false;
    GLuint id = 0;
    if (handle) {
        const auto found = buffers.find(handle);
        if (found == buffers.end() || glIsBuffer(found->second.id) != GL_TRUE)
            return false;
        id = found->second.id;
    }
    GLint previous = 0;
    glGetIntegerv(GL_ELEMENT_ARRAY_BUFFER_BINDING, &previous);
    if (glGetError() != GL_NO_ERROR) return false;
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, id);
    if (glGetError() != GL_NO_ERROR) {
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, static_cast<GLuint>(previous));
        glGetError();
        return false;
    }
    boundHandle = handle;
    return true;
}

bool R_AndroidGlesDrawIndexed(int baseIndex, int triangleCount, int vertexCount)
{
    if (!HasOwner() || !boundHandle || baseIndex < 0 || triangleCount <= 0
        || vertexCount <= 0 || glGetError() != GL_NO_ERROR
        || triangleCount > std::numeric_limits<GLsizei>::max() / 3)
        return false;
    const auto found = buffers.find(boundHandle);
    if (found == buffers.end()) return false;
    const std::size_t count = static_cast<std::size_t>(triangleCount) * 3;
    const std::size_t start = static_cast<std::size_t>(baseIndex);
    if (start > found->second.indices || count > found->second.indices - start
        || start > std::numeric_limits<std::uintptr_t>::max() / sizeof(std::uint16_t))
        return false;
    GLint currentBuffer = 0, program = 0, vao = 0, sizeBytes = 0;
    GLint enabled = 0, vertexBuffer = 0;
    glGetIntegerv(GL_ELEMENT_ARRAY_BUFFER_BINDING, &currentBuffer);
    glGetIntegerv(GL_CURRENT_PROGRAM, &program);
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vao);
    if (currentBuffer != static_cast<GLint>(found->second.id)
        || !program || !vao || glIsBuffer(found->second.id) != GL_TRUE)
        return false;
    glGetBufferParameteriv(GL_ELEMENT_ARRAY_BUFFER, GL_BUFFER_SIZE, &sizeBytes);
    glGetVertexAttribiv(0, GL_VERTEX_ATTRIB_ARRAY_ENABLED, &enabled);
    glGetVertexAttribiv(0, GL_VERTEX_ATTRIB_ARRAY_BUFFER_BINDING, &vertexBuffer);
    if (glGetError() != GL_NO_ERROR || !enabled || !vertexBuffer
        || sizeBytes < 0 || static_cast<std::size_t>(sizeBytes) / 2 < start + count)
        return false;
    const std::uintptr_t byteOffset = start * sizeof(std::uint16_t);
    glDrawElements(GL_TRIANGLES, static_cast<GLsizei>(count), GL_UNSIGNED_SHORT,
                   reinterpret_cast<const void *>(byteOffset));
    return glGetError() == GL_NO_ERROR;
}

void R_AndroidGlesInvalidateIndexBuffers()
{
    // Called when original EGL context is destroyed; never delete buffers
    // owned by the original IW3 resource allocator.
    buffers.clear();
    boundHandle = nullptr;
    ownerDisplay = EGL_NO_DISPLAY;
    ownerContext = EGL_NO_CONTEXT;
}
#endif

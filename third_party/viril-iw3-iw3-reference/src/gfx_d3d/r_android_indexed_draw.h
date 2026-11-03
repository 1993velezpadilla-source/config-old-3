#pragma once
// Original IW3 index-buffer identity -> genuine GLES3 element-array buffer.
// This is a partial backend seam, NOT a complete renderer or gameplay.
#if defined(__ANDROID__)
#include <cstddef>
bool R_AndroidGlesRegisterIndexBuffer(const void *originalHandle,
                                      unsigned int glBuffer, std::size_t indexCount);
bool R_AndroidGlesUnregisterIndexBuffer(const void *originalHandle);
bool R_AndroidGlesBindIndexBuffer(const void *originalHandle);
bool R_AndroidGlesDrawIndexed(int baseIndex, int triangleCount, int vertexCount);
void R_AndroidGlesInvalidateIndexBuffers();
#endif

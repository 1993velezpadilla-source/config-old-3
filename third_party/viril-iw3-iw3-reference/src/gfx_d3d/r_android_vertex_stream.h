#pragma once
// Original IW3 D3D vertex stream identity -> existing GLES3 VBO registration.
// This boundary does NOT create a VBO, VAO, vertex declaration, or shader.
#if defined(__ANDROID__)
#include <cstddef>
bool R_AndroidGlesRegisterVertexBuffer(const void *originalHandle,
                                        unsigned int glBuffer, std::size_t byteCount);
bool R_AndroidGlesUnregisterVertexBuffer(const void *originalHandle);
bool R_AndroidGlesChangeStreamSource(unsigned int streamIndex,
                                     const void *originalHandle,
                                     std::size_t byteOffset, std::size_t stride);
bool R_AndroidGlesGetStreamSource(unsigned int streamIndex, unsigned int *glBuffer,
                                  std::size_t *byteOffset, std::size_t *stride);
void R_AndroidGlesInvalidateVertexStreams();
#endif

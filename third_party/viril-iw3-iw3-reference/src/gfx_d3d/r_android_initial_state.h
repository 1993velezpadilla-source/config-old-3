#pragma once
// Authentic IW3 R_SetInitialContextState -> Android GLES3 initial state.
// Does not initialize a renderer, create geometry, or execute a frame.
#if defined(__ANDROID__)
bool R_AndroidGlesSetInitialContextState();
#endif

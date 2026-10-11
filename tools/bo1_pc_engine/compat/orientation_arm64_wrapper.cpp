// Tiny exported entrypoint to prove the actual BO1 source can be linked into
// a genuine arm64-v8a shared library. Contains no invented renderer or game.
#include <universal/com_math_anglevectors.h>
extern "C" __attribute__((visibility("default"))) void bo1_original_angle_vectors(
    const float angles[3], float forward[3], float right[3], float up[3]) {
    AngleVectors(angles, forward, right, up);
}

#include "../android/jni/src/iw3_weapon_pose.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>

static int close_enough(float a, float b) { return fabsf(a-b) < 0.0001f; }

int main(void) {
    iw3_weapon_pose_t p = {
        "models/weapons/iw3/test.mdl",
        { 2.0f, 3.0f, 4.0f },
        { 5.0f, 6.0f, 7.0f },
        { 1.0f, 1.0f, 1.0f },
        { 8.0f, 9.0f, 10.0f },
        1.5f, 0.4f
    };
    const float basis[3][3] = {{1,0,0},{0,1,0},{0,0,1}};
    float xyz[3], pyr[3];
    assert(IW3_WeaponFindPose(0) == 0);
    assert(IW3_WeaponFindPose("models/weapons/iw3/absent.mdl") == 0);
    IW3_WeaponPoseDelta(&p, basis, 0, 1, 0, xyz, pyr);
    assert(close_enough(xyz[0],2) && close_enough(xyz[1],3) && close_enough(xyz[2],4));
    assert(close_enough(pyr[0],5) && close_enough(pyr[1],6) && close_enough(pyr[2],7));
    IW3_WeaponPoseDelta(&p, basis, 0, 1, 1, xyz, pyr);
    assert(close_enough(xyz[0],0) && close_enough(xyz[1],0) && close_enough(xyz[2],0));
    assert(close_enough(pyr[0],1.5f));
    IW3_WeaponPoseDelta(&p, basis, 1, 0, 0, xyz, pyr);
    assert(close_enough(xyz[0],1) && close_enough(xyz[1],1) && close_enough(xyz[2],1));
    IW3_WeaponPoseDelta(&p, basis, 2, 0, 0, xyz, pyr);
    assert(close_enough(xyz[0],8) && close_enough(xyz[1],9) && close_enough(xyz[2],10));
    IW3_WeaponPoseDelta(&p, basis, -1, 1, 0, xyz, pyr);
    assert(close_enough(xyz[0],0) && close_enough(xyz[1],0));
    IW3_WeaponPoseDelta(&p, basis, 0, INFINITY, NAN, xyz, pyr);
    assert(close_enough(xyz[0],0) && close_enough(pyr[0],0));
    puts("IW3 portable weapon pose native C: ALL TESTS OK");
    return 0;
}

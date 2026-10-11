// Host test calls the ORIGINAL upstream BO1 implementation compiled from its source.
// Does not replace or reimplement the gameplay function.
#include <universal/com_math_anglevectors.h>
#include <cmath>
#include <cstdio>

static bool near(float v, float expected) { return std::fabs(v - expected) < .0002f; }
static bool axis_near(const float *v, float x, float y, float z) {
    return near(v[0],x) && near(v[1],y) && near(v[2],z);
}
int main() {
    float angles[3] = {0,0,0}, forward[3]{}, right[3]{}, up[3]{}, axis[3][3]{};
    AngleVectors(angles,forward,right,up);
    if (!axis_near(forward,1,0,0) || !axis_near(right,0,-1,0) || !axis_near(up,0,0,1)) return 11;
    AnglesToAxis(angles,axis);
    if (!axis_near(axis[0],1,0,0) || !axis_near(axis[1],0,1,0)) return 12;
    angles[1]=90.0f;
    AngleVectors(angles,forward,right,up);
    if (!axis_near(forward,0,1,0) || !axis_near(right,1,0,0) || !axis_near(up,0,0,1)) return 13;
    angles[0]=90.0f; angles[1]=0;
    AngleVectors(angles,forward,right,up);
    if (!axis_near(forward,0,0,-1)) return 14;
    std::puts("BO1_UPSTREAM_ANGLEVECTORS_RUNTIME_TEST=PASS");
    std::puts("BO1_UPSTREAM_ANGLESTOAXIS_RUNTIME_TEST=PASS");
    return 0;
}

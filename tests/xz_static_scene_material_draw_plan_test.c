#include "xz_static_scene_material_draw_plan.h"

#include <stdio.h>

int main(void)
{
    if (!XzStaticSceneMaterialDrawPlan_SelfTest()) {
        fprintf(
            stderr,
            "XZIEL_STATIC_SCENE_MATERIAL_DRAW_PLAN_FAIL\n");
        return 1;
    }

    puts("XZIEL_STATIC_SCENE_MATERIAL_DRAW_PLAN_GREEN");
    return 0;
}

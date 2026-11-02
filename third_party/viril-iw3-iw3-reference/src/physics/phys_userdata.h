#pragma once

#include <cstdint>

// Original IW3 physics pool payload; pointers follow the native ABI.
struct dxBody;

enum physStuckState_t : std::int32_t
{                                       // ...
    PHYS_OBJ_STATE_POSSIBLY_STUCK = 0x0,
    PHYS_OBJ_STATE_STUCK = 0x1,
    PHYS_OBJ_STATE_FREE = 0x2,
};

struct PhysObjUserData // sizeof=0x70
{                                       // ...
    float translation[3];
    dxBody *body;
    float savedPos[3];
    float savedRot[3][3];
    int sndClass;
    float friction;
    float bounce;
    physStuckState_t state;
    float contactCentroid[3];
    int timeLastAsleep;
    float awakeTooLongLastPos[3];
    bool hasDisplayedAwakeTooLongWarning;
    bool debugContacts;
    // padding byte
    // padding byte
};

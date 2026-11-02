#pragma once

// Shared single-player client state. Keep this record independent of the
// dedicated-server and Direct3D client headers so game code can include the
// real gclient_s layout on portable platforms.
#include <game/enthandle.h>
#include <bgame/bg_local.h>

enum clientConnected_t : __int32
{
    CON_DISCONNECTED = 0x0,
    CON_CONNECTING = 0x1,
    CON_CONNECTED = 0x2,
};

struct clientPersistent_t
{
    clientConnected_t connected;
    usercmd_s cmd;
    usercmd_s oldcmd;
    int maxHealth;
    float moveSpeedScaleMultiplier;
};

struct gclient_s
{
    playerState_s ps;
    clientPersistent_t pers;
    int noclip;
    int ufo;
    int bFrozen;
    int buttons;
    int oldbuttons;
    int latched_buttons;
    int buttonsSinceLastFrame;
    float fGunPitch;
    float fGunYaw;
    float fGunXOfs;
    float fGunYOfs;
    float fGunZOfs;
    int damage_blood;
    float damage_from[3];
    int damage_fromWorld;
    int respawnTime;
    float currentAimSpreadScale;
    gentity_s *pHitHitEnt;
    EntHandle pLookatEnt;
    float prevLinkedInvQuat[4];
    bool prevLinkAnglesSet;
    bool link_rotationMovesEyePos;
    bool link_doCollision;
    bool link_useTagAnglesForViewAngles;
    bool linkAnglesLocked;
    float linkAnglesFrac;
    float linkAnglesMinClamp[2];
    float linkAnglesMaxClamp[2];
    int inControlTime;
    int lastTouchTime;
    EntHandle useHoldEntity;
    int useHoldTime;
    int useButtonDone;
    int bDisableAutoPickup;
    int invulnerableExpireTime;
    bool invulnerableActivated;
    bool invulnerableEnabled;
    bool playerMoved;
    float playerLOSCheckPos[2];
    float playerLOSCheckDir[2];
    int playerLOSPosTime;
    int playerADSTargetTime;
    unsigned int lastWeapon;
    bool previouslyFiring;
    bool previouslyUsingNightVision;
    int groundTiltEntNum;
};

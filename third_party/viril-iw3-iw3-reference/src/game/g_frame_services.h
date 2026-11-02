#pragma once
#include "g_runframe.h"
void __cdecl Actor_DumpEventListners();
void __cdecl AimTarget_ClearTargetList();
void __cdecl ClientEndFrame(gentity_s *ent);
void DebugDumpAnims();
void __cdecl G_CheckReloadStatus();
void __cdecl G_ClientDoPerFrameNotifies(gentity_s *ent);
int __cdecl G_DObjUpdateServerTime(gentity_s *ent, int bNotify);
void __cdecl G_DrawEntityBBoxes();
void __cdecl G_DrawGrenadeHints();
void __cdecl G_DrawVehiclePaths();
gentity_s *G_GetPlayerVehicle(const gentity_s *player);
void __cdecl G_ProcessCommandNotifies();
void __cdecl G_RunFrameForEntity(gentity_s *ent);
void __cdecl G_UpdateActorCorpses();
void __cdecl G_UpdatePlayer(gentity_s *ent);
void __cdecl G_UpdatePlayerTriggers(gentity_s *ent);
void __cdecl HudElem_UpdateClient(gclient_s *client);
int __cdecl NotifyTriggers();
void __cdecl Path_DrawDebug();
void __cdecl Path_RunBadPlaces();
void __cdecl SV_DObjInitServerTime(gentity_s *ent, float dtime);
void __cdecl SV_ResetSkeletonCache();
void __cdecl Scr_IncTime();
void __cdecl Scr_RunCurrentThreads();
void Scr_SetRecordScriptPlace(int on);
void __cdecl ShowEntityInfo();

// Original SP string registry and dvars, defined in their original modules.
const char *SL_ConvertToString(uint32_t stringValue);
extern const dvar_t *g_recordScriptPlace;
extern const dvar_t *g_dumpAnimsCommands;
extern const dvar_t *g_listEntity;
extern const dvar_t *g_dumpAIEventListeners;

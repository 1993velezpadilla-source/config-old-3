#pragma once

#ifndef KISAK_SP 
#error This file is for SinglePlayer only 
#endif

// These public SP APIs use pointer-only engine types; owning layouts remain in their original headers.
struct client_t;
struct gentity_s;
struct usercmd_s;

// sv_init
void __cdecl TRACK_sv_init();
void __cdecl SV_GetConfigstring(unsigned int index, char *buffer, int bufferSize);
unsigned int __cdecl SV_GetConfigstringConst(unsigned int index);
void __cdecl SV_InitReliableCommandsForClient(client_t *cl);
void __cdecl SV_FreeReliableCommandsForClient(client_t *cl);
void __cdecl SV_AddReliableCommand(client_t *cl, int index, const char *cmd);
void __cdecl SV_Startup();
void __cdecl SV_ClearServer();
void __cdecl SV_StartMap(int randomSeed);
void __cdecl SV_Settle();
int __cdecl SV_SaveImmediately(const char *levelName);
void __cdecl SV_LoadLevelAssets(const char *mapname);
bool __cdecl SV_Loaded();
void __cdecl SV_Init();
void __cdecl SV_Shutdown(const char *finalmsg);
void __cdecl SV_SetConfigstring(unsigned int index, const char *val);
void SV_SaveSystemInfo();
void __cdecl SV_SpawnServer(const char *server, int savegame);

// Shared client/game translation units consume these SP server services.
// Their definitions and canonical declarations remain in server/server.h.
gentity_s *__cdecl SV_GetEntityState(int entnum);
int __cdecl SV_WaitServerSnapshot();
void __cdecl SV_RecordClientCommand(const char *s);
void __cdecl SV_ExecuteClientCommand(const char *s);
void __cdecl SV_RecordClientThink(usercmd_s *cmd);
void __cdecl SV_ClientThink(usercmd_s *cmd);
void __cdecl SV_TrackPlayerDied();
void __cdecl SV_AddToPlayerScore(int amount);

extern const dvar_t *sv_clientFrameRateFix;
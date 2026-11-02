#ifndef KISAK_SP
#error This file is for SinglePlayer only
#endif

// The original complete IW3 SP frame. Dependencies remain real engine APIs;
// this file supplies no actor, script, render, weapon or platform substitutes.
#include <universal/q_shared.h>
#include "g_runframe.h"
#include "g_frame_services.h"
#include <universal/profile.h>

int __cdecl G_RunFrame(ServerFrameExtent extent, int timeCap)
{
    int currentIndex; // r5
    int num_entities; // r11
    gentity_s *i; // r30
    int number; // r4
    const char *v7; // r3
    int v8; // r29
    gentity_s *v9; // r30
    int v10; // r29
    int j; // r11
    int v12; // r11
    gentity_s *k; // r30
    int inuse; // r11
    bool checkAnimChange; // r11
    int v19; // r3
    gentity_s *vehEnt; // r3
    gentity_s *v21; // r30
    int currentEntityThink; // r5
    int v23; // r11
    gentity_s *m; // r30
    int v25; // r4
    const char *v26; // r3
    int maxclients; // r11
    int v28; // r29
    gclient_s **p_client; // r30
    const float *v30; // r6
    int v31; // r5
    int v32; // r4
    int v33; // r3
    __int64 v34; // r8
    int v35; // r6
    int v36; // r5
    const float *v37; // r4
    int v38; // r3
    int v39; // r30
    unsigned __int16 *p_classname; // r31
    const char *v41; // r3

    iassert(extent == SV_FRAME_DO_ALL);
    iassert(!timeCap);

    {
        PROF_SCOPED("update player");
        G_UpdatePlayer(level.gentities);
        G_UpdatePlayerTriggers(level.gentities);
        G_CheckReloadStatus();
        iassert(!level.actorPredictDepth);
        level.currentIndex = 1;
    }
    {
        PROF_SCOPED("update anim1");
        currentIndex = level.currentIndex;
        num_entities = level.num_entities;
        for (i = &g_entities[level.currentIndex]; currentIndex < num_entities; ++i)
        {
            if (i->r.inuse)
            {
                number = i->s.number;
                if (number != currentIndex)
                {
                    v7 = va(
                        "s.number = %i, level.currentIndex = %i, classname = %s",
                        number,
                        currentIndex,
                        SL_ConvertToString(i->classname));
                    MyAssertHandler(
                        "c:\\trees\\cod3\\cod3src\\src\\game\\g_main.cpp",
                        2643,
                        0,
                        "%s\n\t%s",
                        "ent->s.number == level.currentIndex",
                        v7);
                }
                SV_DObjInitServerTime(i, 0.05f);
                currentIndex = ++level.currentIndex;
                num_entities = level.num_entities;
            }
            else
            {
                level.currentIndex = ++currentIndex;
            }
        }
    }
    {
        PROF_SCOPED("script threads1");
        memset(level.entTriggerIndex, 0, sizeof(level.entTriggerIndex));
        level.triggerIndex = 0;
        iassert(level.currentTriggerListSize == 0);
        Com_Memcpy(level.currentTriggerList, level.pendingTriggerList, 12 * level.pendingTriggerListSize);
        level.currentTriggerListSize = level.pendingTriggerListSize;
        level.pendingTriggerListSize = 0;
        do
        {
            v8 = NotifyTriggers();
            G_ProcessCommandNotifies();
            Scr_RunCurrentThreads();
        } while (v8);
        iassert(level.currentTriggerListSize == 0);
        v9 = g_entities;
        v10 = 0;
        level.currentIndex = 1;
        level.checkAnimChange = 0;
        for (j = level.maxclients; v10 < j; ++v9)
        {
            if (v9->r.inuse)
            {
                G_ClientDoPerFrameNotifies(v9);
                j = level.maxclients;
            }
            ++v10;
        }
    }
    {
        PROF_SCOPED("update anim2");
        v12 = level.currentIndex;
        for (k = &g_entities[level.currentIndex]; v12 < level.num_entities; level.currentIndex = v12)
        {
            if (k->r.inuse)
            {
                do
                {
                    if ((k->flags & 0x1000) != 0)
                        break;
                    if (!G_DObjUpdateServerTime(k, 1))
                        break;
                    Scr_RunCurrentThreads();
                    inuse = k->r.inuse;
                    level.checkAnimChange = 1;
                } while (inuse);
                v12 = level.currentIndex;
            }
            ++v12;
            ++k;
        }
        if (level.checkAnimChange)
        {
            do
            {
                checkAnimChange = 0;
                level.currentIndex = 1;
                level.checkAnimChange = 0;
                if (level.num_entities > 1)
                {
                    // Portable entity traversal: the original reverse-engineered
                    // Win32 code walked r.inuse with a hard-coded 628-byte stride,
                    // recovered gentity_s with -168 bytes, and loaded flags from
                    // a 136-byte offset. These addresses are WRONG for 64-bit
                    // pointers. Access the SAME ORIGINAL IW3 fields by type,
                    // letting the compiler select sizeof(gentity_s) and offsets.
                    gentity_s *animEnt = &g_entities[1];
                    do
                    {
                        if (animEnt->r.inuse)
                        {
                            do
                            {
                                const unsigned int animFlags = static_cast<unsigned int>(animEnt->flags);
                                if ((animFlags & FL_REPEAT_ANIM_UPDATE) == 0 ||
                                    (animFlags & FL_NO_AUTO_ANIM_UPDATE) != 0)
                                    break;
                                if (!G_DObjUpdateServerTime(animEnt, 1))
                                {
                                    checkAnimChange = level.checkAnimChange;
                                    break;
                                }
                                Scr_RunCurrentThreads();
                                checkAnimChange = 1;
                                const bool stillInUse = animEnt->r.inuse != 0;
                                level.checkAnimChange = 1;
                                if (!stillInUse)
                                    break;
                            } while (true);
                        }
                        ++animEnt;
                        ++level.currentIndex;
                    } while (level.currentIndex < level.num_entities);
                }
            } while (checkAnimChange);
        }
    }
    {
        PROF_SCOPED("script threads2");
        if (g_recordScriptPlace->current.enabled || (v19 = 0, g_dumpAnimsCommands->current.integer > 0))
            v19 = 1;
        Scr_SetRecordScriptPlace(v19);
        Scr_IncTime();
        SV_ResetSkeletonCache();
    }
    {
        PROF_SCOPED("bad places");
        Path_RunBadPlaces();
    }
    {
        PROF_SCOPED("update player");
        G_UpdatePlayer(level.gentities);
        AimTarget_ClearTargetList();
        vehEnt = G_GetPlayerVehicle(level.gentities);
        v21 = vehEnt;
        if (vehEnt)
        {
            if (!vehEnt->r.inuse)
                MyAssertHandler("c:\\trees\\cod3\\cod3src\\src\\game\\g_main.cpp", 2811, 0, "%s", "vehEnt->r.inuse");
            G_RunFrameForEntity(v21);
        }
    }
    iassert(level.currentEntityThink == -1);
    level.currentEntityThink = 0;
    {
        PROF_SCOPED("update ents");
        currentEntityThink = level.currentEntityThink;
        v23 = level.num_entities;
        for (m = &g_entities[level.currentEntityThink]; currentEntityThink < v23; ++m)
        {
            if (m->r.inuse)
            {
                v25 = m->s.number;
                if (v25 != currentEntityThink)
                {
                    v26 = va(
                        "s.number = %i, level.currentEntityThink = %i, classname = %s",
                        v25,
                        currentEntityThink,
                        SL_ConvertToString(m->classname));
                    MyAssertHandler(
                        "c:\\trees\\cod3\\cod3src\\src\\game\\g_main.cpp",
                        2844,
                        0,
                        "%s\n\t%s",
                        "ent->s.number == level.currentEntityThink",
                        v26);
                }
                G_RunFrameForEntity(m);
                currentEntityThink = ++level.currentEntityThink;
                v23 = level.num_entities;
            }
            else
            {
                level.currentEntityThink = ++currentEntityThink;
            }
        }
    }
    level.currentEntityThink = -1;
    if (level.actorPredictDepth)
        Com_Error(ERR_DROP, "unmatching beginPrediction and endPrediction");

    {
        PROF_SCOPED("update client");

        for (int i = 0; i < level.maxclients; i++)
        {
            gentity_s *ent = &g_entities[i];

            if (ent->r.inuse)
            {
                HudElem_UpdateClient(ent->client);
                ClientEndFrame(ent);
            }
        }
        //maxclients = level.maxclients;
        //v28 = 0;
        //if (level.maxclients > 0)
        //{
        //    p_client = &g_entities[0].client;
        //    do
        //    {
        //        if (*((_BYTE *)p_client - 88))
        //        {
        //            HudElem_UpdateClient(*p_client);
        //            ClientEndFrame((gentity_s *)(p_client - 64));
        //            maxclients = level.maxclients;
        //        }
        //        ++v28;
        //        p_client += 157;
        //    } while (v28 < maxclients);
        //}
    }
    {
        PROF_SCOPED("update corpses");
        G_UpdateActorCorpses();
    }
    Path_DrawDebug();
    G_DrawVehiclePaths();
    G_DrawEntityBBoxes();
    G_DrawGrenadeHints();
    if (g_listEntity->current.enabled)
    {
        for (v39 = 0; v39 < MAX_GENTITIES; ++v39)
        {
            v41 = SL_ConvertToString(g_entities[v39].classname);
            Com_Printf(CON_CHANNEL_SERVER, "%4i: %s\n", v39, v41);
        }
        Dvar_SetBool(g_listEntity, 0);
    }
    ShowEntityInfo();
    DebugDumpAnims();
    if (g_dumpAIEventListeners->current.enabled)
    {
        Actor_DumpEventListners();
        Dvar_SetBool(g_dumpAIEventListeners, 0);
    }
    return 1;
}

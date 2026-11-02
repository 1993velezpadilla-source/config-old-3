#include <universal/q_shared.h>
#include "files.h"
#include <universal/assertive.h>
#include <universal/com_files.h>
#include "qcommon.h"
#include <database/database.h>
#include "cmd.h"
#include <sound/snd_public.h>

int fs_numServerReferencedIwds;
// Avoid the POSIX basename() identifier exported by Android/Linux libc.
char fs_mapBaseName[64];
const char *fs_serverReferencedIwdNames[1024];
int fs_serverReferencedIwds[1024];

// KISAKTODO header-ify
extern int fs_fakeChkSum;

char *__cdecl FS_GetMapBaseName(char *mapname)
{
    // A map path can originate from external game data. The original
    // decompilation indexed mapname[length - 3] even for short strings and
    // copied an unbounded map basename into this 64-byte static buffer.
    iassert( mapname );
    if (!mapname)
    {
        fs_mapBaseName[0] = 0;
        return fs_mapBaseName;
    }
    if (!I_strnicmp(mapname, "maps/mp/", 8))
        mapname += 8;

    const size_t mapLength = strlen(mapname);
    size_t baseLength = mapLength;
    if (mapLength >= 3 && !I_stricmp(mapname + mapLength - 3, "bsp"))
    {
        // The IW3 .d3dbsp suffix is seven bytes. A shorter BSP-like name
        // cannot be stripped safely and must not underflow the length.
        if (mapLength < 7)
        {
            fs_mapBaseName[0] = 0;
            return fs_mapBaseName;
        }
        baseLength = mapLength - 7;
    }
    if (baseLength >= sizeof(fs_mapBaseName))
    {
        // Do not silently truncate a map identifier to a different name.
        fs_mapBaseName[0] = 0;
        return fs_mapBaseName;
    }
    memcpy(fs_mapBaseName, mapname, baseLength);
    fs_mapBaseName[baseLength] = 0;
    for (size_t i = 0; i < baseLength; ++i)
    {
        if (fs_mapBaseName[i] == '%')
            fs_mapBaseName[i] = '_';
    }
    return fs_mapBaseName;
}

BOOL __cdecl FS_serverPak(const char *pak)
{
    char szFile[68];

    // Server-provided IWD names are not guaranteed to fit the original
    // decompiled 68-byte stack buffer. Reject an overlong name rather than
    // overwriting adjacent stack data during the pure-server comparison.
    if (!pak)
        return 0;
    size_t length = 0;
    while (length < sizeof(szFile) && pak[length])
        ++length;
    if (length == sizeof(szFile))
        return 0;
    memcpy(szFile, pak, length + 1);
    I_strlwr(szFile);
    return strstr(szFile, "_svr_") != 0;
}

int __cdecl FS_iwIwd(char *iwd, char *base)
{
    if (!iwd || !base)
        return 0;

    // Keep the original standard main/iw_00..24 comparisons intact.
    for (int i = 0; i < 25; ++i)
    {
        const char *standardName = va("%s/iw_%02d", base, i);
        if (!FS_FilenameCompare(iwd, standardName))
            return 1;
    }

    const char *localized = strstr(iwd, "localized_");
    if (!localized)
        return 0;

    char szFile[68];
    size_t length = 0;
    while (length < sizeof(szFile) && iwd[length])
        ++length;
    if (length == sizeof(szFile))
        return 0;

    // A localized path must fit in the original stack buffer, including
    // the terminating NUL. Check before copying or writing the prefix end.
    const size_t prefixLength = static_cast<size_t>(localized - iwd) + sizeof("localized_") - 1;
    if (prefixLength > length || prefixLength >= sizeof(szFile))
        return 0;
    memcpy(szFile, iwd, length + 1);
    szFile[prefixLength] = '\0';
    const char *localizedPrefix = va("%s/localized_", base);
    if (FS_FilenameCompare(szFile, localizedPrefix))
        return 0;

    const char *suffix = localized + sizeof("localized_") - 1;
    const size_t suffixLength = strlen(suffix);
    if (suffixLength >= sizeof(szFile))
        return 0;
    memcpy(szFile, suffix, suffixLength + 1);
    I_strlwr(szFile);
    for (int i = 0; i < 25; ++i)
    {
        const char *pattern = va("_iw%02d", i);
        if (strstr(szFile, pattern))
            return 1;
    }
    return 0;
}

int __cdecl FS_CompareIwds(char *needediwds, int len, int dlstring)
{
    char *v4; // eax
    const char *v5; // [esp+8h] [ebp-20h]
    const char *string; // [esp+Ch] [ebp-1Ch]
    const char *v7; // end of fs_gameDirVar string
    int haveiwd; // [esp+1Ch] [ebp-Ch]
    searchpath_s *j; // [esp+20h] [ebp-8h]
    int i; // [esp+24h] [ebp-4h]

    if (!fs_numServerReferencedIwds)
        return 0;
    *needediwds = 0;
    string = fs_gameDirVar->current.string;
    v5 = string + 1;
    v7 = &string[strlen(string) + 1];
    for (i = 0; i < fs_numServerReferencedIwds; ++i)
    {
        haveiwd = 0;
        if ((const char *)v7 == v5 || !FS_serverPak(fs_serverReferencedIwdNames[i]))
        {
            for (j = fs_searchpaths; j; j = j->next)
            {
                if (j->iwd && j->iwd->checksum == fs_serverReferencedIwds[i])
                {
                    haveiwd = 1;
                    break;
                }
            }
            if (!haveiwd && fs_serverReferencedIwdNames[i] && *fs_serverReferencedIwdNames[i])
            {
                if ((const char *)v7 == v5
                    || I_strnicmp(fs_serverReferencedIwdNames[i], fs_gameDirVar->current.string, static_cast<int>(v7 - v5))
                    || FS_iwIwd((char *)fs_serverReferencedIwdNames[i], (char*)"main"))
                {
                    I_strncpyz(needediwds, (char *)fs_serverReferencedIwdNames[i], len);
                    I_strncat(needediwds, len, ".iwd");
                    return 2;
                }
                if (dlstring)
                {
                    I_strncat(needediwds, len, "@");
                    I_strncat(needediwds, len, (char *)fs_serverReferencedIwdNames[i]);
                    I_strncat(needediwds, len, ".iwd");
                    I_strncat(needediwds, len, "@");
                    I_strncat(needediwds, len, (char *)fs_serverReferencedIwdNames[i]);
                    I_strncat(needediwds, len, ".iwd");
                }
                else
                {
                    I_strncat(needediwds, len, (char *)fs_serverReferencedIwdNames[i]);
                    I_strncat(needediwds, len, ".iwd");
                    v4 = va("%s.iwd", fs_serverReferencedIwdNames[i]);
                    if (FS_SV_FileExists(v4))
                        I_strncat(needediwds, len, " (local file exists with wrong checksum)");
                    I_strncat(needediwds, len, "\n");
                }
            }
        }
    }
    if (!*needediwds)
        return 0;
    Com_Printf(CON_CHANNEL_FILES, "Need iwds: %s\n", needediwds);
    return 1;
}

int fs_numServerReferencedFFs;
const char *fs_serverReferencedFFNames[32];
int fs_serverReferencedFFCheckSums[32];
int __cdecl FS_CompareFFs(char *neededFFs, int len, int dlstring)
{
    int v4; // eax
    const char *v5; // [esp+18h] [ebp-28h]
    const char *string; // [esp+1Ch] [ebp-24h]
    const char *v7; // end of fs_gameDirVar string
    char *ffName; // [esp+2Ch] [ebp-14h]
    const char *ffNamea; // [esp+2Ch] [ebp-14h]
    int fileSize; // [esp+30h] [ebp-10h]
    int i; // [esp+3Ch] [ebp-4h]

    if (!fs_numServerReferencedFFs)
        return 0;
    *neededFFs = 0;
    string = fs_gameDirVar->current.string;
    v5 = string + 1;
    v7 = &string[strlen(string) + 1];
    for (i = 0; i < fs_numServerReferencedFFs; ++i)
    {
        if (I_strncmp(fs_serverReferencedFFNames[i], "mods", 4)
            || (ffName = strchr((char *)fs_serverReferencedFFNames[i] + 5, 47)) == 0
            || strlen(ffName) <= 1)
        {
            v4 = DB_FileSize(fs_serverReferencedFFNames[i], 0);
        }
        else
        {
            ffNamea = ffName + 1;
            iassert( ffName[0] );
            v4 = DB_FileSize(ffNamea, 1);
        }
        fileSize = v4;
        if (v4 != fs_serverReferencedFFCheckSums[i] && fs_serverReferencedFFNames[i] && *fs_serverReferencedFFNames[i])
        {
            if ((const char *)v7 == v5
                || I_strnicmp(fs_serverReferencedFFNames[i], fs_gameDirVar->current.string, static_cast<int>(v7 - v5)))
            {
                I_strncpyz(neededFFs, (char *)fs_serverReferencedFFNames[i], len);
                I_strncat(neededFFs, len, ".ff");
                return 2;
            }
            if (dlstring)
            {
                I_strncat(neededFFs, len, "@");
                I_strncat(neededFFs, len, (char *)fs_serverReferencedFFNames[i]);
                I_strncat(neededFFs, len, ".ff");
                I_strncat(neededFFs, len, "@");
                I_strncat(neededFFs, len, (char *)fs_serverReferencedFFNames[i]);
                I_strncat(neededFFs, len, ".ff");
            }
            else
            {
                I_strncat(neededFFs, len, (char *)fs_serverReferencedFFNames[i]);
                I_strncat(neededFFs, len, ".ff");
                if (fileSize)
                    I_strncat(neededFFs, len, " (local file exists with wrong filesize)");
                I_strncat(neededFFs, len, "\n");
            }
        }
    }
    if (!*neededFFs)
        return 0;
    Com_Printf(CON_CHANNEL_FILES, "Need FFs: %s\n", neededFFs);
    return 1;
}

FS_SERVER_COMPARE_RESULT __cdecl FS_CompareWithServerFiles(char *neededFiles, int len, int dlstring)
{
    FS_SERVER_COMPARE_RESULT iwdCompareResult; // [esp+10h] [ebp-Ch]
    int neededIWDStrLen; // [esp+14h] [ebp-8h]
    FS_SERVER_COMPARE_RESULT ffCompareResult; // [esp+18h] [ebp-4h]

    *neededFiles = 0;
    iwdCompareResult = (FS_SERVER_COMPARE_RESULT)FS_CompareIwds(neededFiles, len, dlstring);
    if (iwdCompareResult == NOT_DOWNLOADABLE)
        return (FS_SERVER_COMPARE_RESULT)2;
    neededIWDStrLen = strlen(neededFiles);
    iassert( len >= neededIWDStrLen );
    ffCompareResult = (FS_SERVER_COMPARE_RESULT)FS_CompareFFs(&neededFiles[neededIWDStrLen], len - neededIWDStrLen, dlstring);
    if (ffCompareResult == NOT_DOWNLOADABLE)
        return (FS_SERVER_COMPARE_RESULT)2;
    return (FS_SERVER_COMPARE_RESULT)(iwdCompareResult == NEED_DOWNLOAD || ffCompareResult == NEED_DOWNLOAD);
}

void __cdecl FS_ShutdownServerFileReferences(int *numFiles, const char **fileNames)
{
    int i; // [esp+0h] [ebp-4h]

    for (i = 0; i < *numFiles; ++i)
    {
        if (fileNames[i])
        {
            FreeString(fileNames[i]);
            fileNames[i] = 0;
        }
    }
    *numFiles = 0;
}

void __cdecl FS_ShutdownServerReferencedIwds()
{
    FS_ShutdownServerFileReferences(&fs_numServerReferencedIwds, fs_serverReferencedIwdNames);
}

int __cdecl FS_ServerSetReferencedFiles(
    char *fileSums,
    char *fileNames,
    int maxFiles,
    int *fs_sums,
    const char **fs_names)
{
    const char *v5; // eax
    char *v6; // eax
    int c; // [esp+0h] [ebp-Ch]
    int d; // [esp+4h] [ebp-8h]
    int i; // [esp+8h] [ebp-4h]
    int ia; // [esp+8h] [ebp-4h]

    iassert( fileSums );
    iassert( fileNames );
    iassert( maxFiles );
    iassert( fs_sums );
    Cmd_TokenizeString(fileSums);
    c = Cmd_Argc();
    if (c > maxFiles)
        c = maxFiles;
    for (i = 0; i < c; ++i)
    {
        v5 = Cmd_Argv(i);
        fs_sums[i] = atoi(v5);
    }
    Cmd_EndTokenizedString();
    if (fileNames && *fileNames)
    {
        Cmd_TokenizeString(fileNames);
        d = Cmd_Argc();
        if (d > maxFiles)
            d = maxFiles;
        if (c != d)
            Com_Error(ERR_DROP, "file sum/name mismatch");
        for (ia = 0; ia < d; ++ia)
        {
            v6 = (char *)Cmd_Argv(ia);
            fs_names[ia] = CopyString(v6);
        }
        Cmd_EndTokenizedString();
    }
    else if (c)
    {
        Com_Error(ERR_DROP, "file sum/name mismatch");
    }
    return c;
}

void __cdecl FS_ServerSetReferencedIwds(char *iwdSums, char *iwdNames)
{
    FS_ShutdownServerReferencedIwds();
    fs_numServerReferencedIwds = FS_ServerSetReferencedFiles(
        iwdSums,
        iwdNames,
        1024,
        fs_serverReferencedIwds,
        fs_serverReferencedIwdNames);
}

void __cdecl FS_ShutdownServerReferencedFFs()
{
    FS_ShutdownServerFileReferences(&fs_numServerReferencedFFs, fs_serverReferencedFFNames);
}

void __cdecl FS_ServerSetReferencedFFs(char *FFSums, char *FFNames)
{
    FS_ShutdownServerReferencedFFs();
    fs_numServerReferencedFFs = FS_ServerSetReferencedFiles(
        FFSums,
        FFNames,
        static_cast<int>(sizeof(fs_serverReferencedFFCheckSums) / sizeof(fs_serverReferencedFFCheckSums[0])),
        fs_serverReferencedFFCheckSums,
        fs_serverReferencedFFNames);
}

void __cdecl FS_ShutdownServerIwdNames()
{
    FS_ShutdownServerFileReferences(&fs_numServerIwds, fs_serverIwdNames);
}

void __cdecl FS_PureServerSetLoadedIwds(char *iwdSums, char *iwdNames)
{
    const char *v2; // eax
    int v3; // eax
    const char *v4; // eax
    const char *v5; // eax
    int i; // [esp+0h] [ebp-2014h]
    int v7; // [esp+4h] [ebp-2010h]
    int v8; // [esp+8h] [ebp-200Ch]
    int src[1025]; // [esp+Ch] [ebp-2008h] BYREF
    int argIndex; // [esp+1010h] [ebp-1004h]
    const char *s0[1024]; // [esp+1014h] [ebp-1000h] BYREF

    iassert( iwdSums );
    iassert( iwdNames );
    Cmd_TokenizeString(iwdSums);
    v7 = Cmd_Argc();
    if (v7 > 1024)
        v7 = 1024;
    for (argIndex = 0; argIndex < v7; ++argIndex)
    {
        v2 = Cmd_Argv(argIndex);
        v3 = atoi(v2);
        src[argIndex] = v3;
    }
    Cmd_EndTokenizedString();
    Cmd_TokenizeString(iwdNames);
    v8 = Cmd_Argc();
    if (v8 > 1024)
        v8 = 1024;
    for (argIndex = 0; argIndex < v8; ++argIndex)
    {
        v4 = Cmd_Argv(argIndex);
        v5 = CopyString(v4);
        s0[argIndex] = v5;
    }
    Cmd_EndTokenizedString();
    if (v7 != v8)
        Com_Error(ERR_DROP, "iwd sum/name mismatch");
    if (v7 == fs_numServerIwds)
    {
        argIndex = 0;
    LABEL_19:
        if (argIndex >= v7)
        {
            for (argIndex = 0; argIndex < v8; ++argIndex)
                FreeString(s0[argIndex]);
            return;
        }
        for (i = 0; i < fs_numServerIwds; ++i)
        {
            if (src[argIndex] == fs_serverIwds[i] && !I_stricmp(s0[argIndex], fs_serverIwdNames[i]))
            {
                ++argIndex;
                goto LABEL_19;
            }
        }
    }
    SND_StopSounds(SND_STOP_STREAMED);
    FS_ShutdownServerIwdNames();
    fs_numServerIwds = v7;
    if (v7)
    {
        Com_DPrintf(CON_CHANNEL_FILES, "Connected to a pure server.\n");
        // Checksums are 32-bit, but IWD names are pointers (64-bit on Android ARM64).
        // A decompiled Win32 byte count copied only half of the name pointers.
        Com_Memcpy(fs_serverIwds, src, sizeof(fs_serverIwds[0]) * fs_numServerIwds);
        Com_Memcpy(fs_serverIwdNames, s0, sizeof(fs_serverIwdNames[0]) * fs_numServerIwds);
        fs_fakeChkSum = 0;
    }
}
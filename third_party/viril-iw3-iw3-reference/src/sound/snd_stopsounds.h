#pragma once

#include <cstdint>

// Shared enum values used by original sound shutdown and filesystem shutdown.
// The numeric values are unchanged from snd_public.h.
enum snd_stopsounds_arg_t : __int32
{
    SND_STOP_ALL = 0x0,
    SND_KEEP_REVERB = 0x1,
    SND_KEEP_MUSIC = 0x2,
    SND_KEEP_AMBIENT = 0x4,
    SND_KEEP_MUSIC_AND_AMBIENT = 0x6,
    SND_STOP_STREAMED = 0x8,
    SND_KEEP_CHANNEL_VOLUMES = 0x10,
};

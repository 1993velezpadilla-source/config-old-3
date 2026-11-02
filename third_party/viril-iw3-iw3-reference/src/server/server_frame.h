#pragma once
#include <cstdint>

enum ServerFrameExtent : std::int32_t
{
    SV_FRAME_DO_ALL = 0x0,
    SV_FRAME_DO_SMOOTHING = 0x1,
};

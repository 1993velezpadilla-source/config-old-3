#include "xziel/intrinsic_ad_map.hpp"

#include <cassert>
#include <bit>
#include <cstddef>
#include <cstdint>
#include <vector>

namespace {

void u32(
    std::vector<std::byte>& out,
    std::uint32_t value) {
    for (std::uint32_t shift = 0U;
         shift < 32U;
         shift += 8U) {
        out.push_back(
            static_cast<std::byte>(
                (value >> shift) & 0xFFU));
    }
}

void u64(
    std::vector<std::byte>& out,
    std::uint64_t value) {
    u32(
        out,
        static_cast<std::uint32_t>(
            value & 0xFFFFFFFFULL));
    u32(
        out,
        static_cast<std::uint32_t>(
            value >> 32U));
}

void f32(
    std::vector<std::byte>& out,
    float value) {
    u32(
        out,
        std::bit_cast<std::uint32_t>(
            value));
}

void fixedPath(
    std::vector<std::byte>& out,
    const char* text) {
    std::size_t length = 0U;
    while (text[length] != '\0') {
        ++length;
    }

    assert(
        length <
        xziel::kIntrinsicAdAssetPathBytes);

    for (std::size_t i = 0U;
         i < xziel::kIntrinsicAdAssetPathBytes;
         ++i) {
        out.push_back(
            static_cast<std::byte>(
                i < length
                    ? static_cast<
                          unsigned char>(
                          text[i])
                    : 0U));
    }
}

std::vector<std::byte> goodMap() {
    std::vector<std::byte> out;
    out.push_back(std::byte{'X'});
    out.push_back(std::byte{'Z'});
    out.push_back(std::byte{'A'});
    out.push_back(std::byte{'D'});
    u32(out, xziel::kIntrinsicAdMapVersion);
    u32(out, 1U);
    u32(out, 1U);

    u64(out, 1001U);
    fixedPath(
        out,
        "ads/church/frame_01_dummy.ktx2");
    f32(out, -8.69f);
    f32(out, -7.50f);
    f32(out, 3.40f);
    f32(out, 1.0f);
    f32(out, 0.0f);
    f32(out, 0.0f);
    f32(out, 1.8f);
    f32(out, 1.2f);
    f32(out, 20.0f);
    f32(out, 0.25f);
    f32(out, 0.0008f);
    f32(out, 1.0f);
    f32(out, 30.0f);
    u32(out, 3U);
    u32(out, xziel::IntrinsicAdMapSurfaceImage);

    u64(out, 2001U);
    u64(out, 7001U);
    fixedPath(
        out,
        "ads/church/radio_dummy.wav");
    f32(out, 5.90f);
    f32(out, -11.30f);
    f32(out, 1.15f);
    f32(out, 1.0f);
    f32(out, 12.0f);
    f32(out, 0.60f);
    f32(out, 1.0f);
    f32(out, 45.0f);
    u32(out, 3U);

    return out;
}

} // namespace

int main() {
    auto bytes = goodMap();

    xziel::IntrinsicAdMap map{};
    const auto parsed =
        xziel::parseIntrinsicAdMapXzad(
            bytes,
            map);

    assert(parsed.success);
    assert(
        parsed.error ==
        xziel::IntrinsicAdMapParseError::None);
    assert(map.surfaceCount == 1U);
    assert(map.audioEmitterCount == 1U);

    const auto& surface = map.surfaces[0];
    assert(surface.placementId == 1001U);
    assert(
        xziel::intrinsicAdAssetPath(
            surface.sourceTextureAssetPath) ==
        "ads/church/frame_01_dummy.ktx2");
    assert(surface.normal[0] == 1.0f);

    const auto definition =
        xziel::makeAdSurfaceDefinition(
            surface);
    assert(definition.placementId == 1001U);
    assert(definition.meshId != 0U);
    assert(definition.allowImage);
    assert(!definition.allowVideo);

    const auto& audio =
        map.audioEmitters[0];
    assert(audio.placementId == 2001U);
    assert(audio.emitterId == 7001U);

    const auto audioDefinition =
        xziel::makeAdAudioEmitterDefinition(
            audio);
    assert(
        audioDefinition.maximumDistanceMeters ==
        12.0f);
    assert(audioDefinition.maximumGain == 0.60f);

    auto badMagic = bytes;
    badMagic[0] = std::byte{'N'};
    xziel::IntrinsicAdMap badMap{};
    const auto bad =
        xziel::parseIntrinsicAdMapXzad(
            badMagic,
            badMap);
    assert(!bad.success);
    assert(
        bad.error ==
        xziel::IntrinsicAdMapParseError::
            InvalidMagic);

    auto trailing = bytes;
    trailing.push_back(std::byte{0});
    const auto trailingResult =
        xziel::parseIntrinsicAdMapXzad(
            trailing,
            badMap);
    assert(!trailingResult.success);
    assert(
        trailingResult.error ==
        xziel::IntrinsicAdMapParseError::
            TrailingData);

    assert(
        xziel::intrinsicAdAssetId(
            "ads/church/frame_01_dummy.ktx2") ==
        xziel::intrinsicAdAssetId(
            "ads/church/frame_01_dummy.ktx2"));

    return 0;
}

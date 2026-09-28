#include "Etc.h"

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

constexpr uint32_t kXzltVersionBc = 1u;
constexpr uint32_t kXzltVersionEtc2 = 2u;
constexpr uint32_t kHeaderBytes = 32u;
constexpr uint32_t kTextureRecordBytes = 24u;
constexpr uint32_t kMipRecordBytes = 16u;
constexpr uint32_t kFormatBc1 = 1u;
constexpr uint32_t kFormatBc3 = 2u;
constexpr uint32_t kFormatEtc2Rgba8 = 3u;

uint32_t read_u32(const std::vector<unsigned char>& bytes, size_t at)
{
    if (at + 4u > bytes.size())
        throw std::runtime_error("read_u32 out of range");
    return
        static_cast<uint32_t>(bytes[at + 0u]) |
        (static_cast<uint32_t>(bytes[at + 1u]) << 8u) |
        (static_cast<uint32_t>(bytes[at + 2u]) << 16u) |
        (static_cast<uint32_t>(bytes[at + 3u]) << 24u);
}

void write_u32(std::vector<unsigned char>& bytes, size_t at, uint32_t value)
{
    if (at + 4u > bytes.size())
        throw std::runtime_error("write_u32 out of range");
    bytes[at + 0u] = static_cast<unsigned char>(value & 0xffu);
    bytes[at + 1u] = static_cast<unsigned char>((value >> 8u) & 0xffu);
    bytes[at + 2u] = static_cast<unsigned char>((value >> 16u) & 0xffu);
    bytes[at + 3u] = static_cast<unsigned char>((value >> 24u) & 0xffu);
}

uint16_t read_u16(const unsigned char* p)
{
    return static_cast<uint16_t>(
        static_cast<uint16_t>(p[0]) |
        (static_cast<uint16_t>(p[1]) << 8u));
}

void decode_565(uint16_t value, unsigned char rgb[3])
{
    const unsigned int r = (value >> 11u) & 31u;
    const unsigned int g = (value >> 5u) & 63u;
    const unsigned int b = value & 31u;
    rgb[0] = static_cast<unsigned char>((r << 3u) | (r >> 2u));
    rgb[1] = static_cast<unsigned char>((g << 2u) | (g >> 4u));
    rgb[2] = static_cast<unsigned char>((b << 3u) | (b >> 2u));
}

void decode_bc3_block(
    const unsigned char* block,
    unsigned char rgba[16][4])
{
    unsigned char alpha[8];
    alpha[0] = block[0];
    alpha[1] = block[1];

    if (alpha[0] > alpha[1]) {
        alpha[2] = static_cast<unsigned char>((6u * alpha[0] + 1u * alpha[1]) / 7u);
        alpha[3] = static_cast<unsigned char>((5u * alpha[0] + 2u * alpha[1]) / 7u);
        alpha[4] = static_cast<unsigned char>((4u * alpha[0] + 3u * alpha[1]) / 7u);
        alpha[5] = static_cast<unsigned char>((3u * alpha[0] + 4u * alpha[1]) / 7u);
        alpha[6] = static_cast<unsigned char>((2u * alpha[0] + 5u * alpha[1]) / 7u);
        alpha[7] = static_cast<unsigned char>((1u * alpha[0] + 6u * alpha[1]) / 7u);
    } else {
        alpha[2] = static_cast<unsigned char>((4u * alpha[0] + 1u * alpha[1]) / 5u);
        alpha[3] = static_cast<unsigned char>((3u * alpha[0] + 2u * alpha[1]) / 5u);
        alpha[4] = static_cast<unsigned char>((2u * alpha[0] + 3u * alpha[1]) / 5u);
        alpha[5] = static_cast<unsigned char>((1u * alpha[0] + 4u * alpha[1]) / 5u);
        alpha[6] = 0u;
        alpha[7] = 255u;
    }

    uint64_t alpha_bits = 0u;
    for (unsigned int i = 0u; i < 6u; ++i)
        alpha_bits |= static_cast<uint64_t>(block[2u + i]) << (8u * i);

    unsigned char colors[4][3];
    decode_565(read_u16(block + 8u), colors[0]);
    decode_565(read_u16(block + 10u), colors[1]);
    for (unsigned int c = 0u; c < 3u; ++c) {
        colors[2][c] = static_cast<unsigned char>(
            (2u * colors[0][c] + colors[1][c]) / 3u);
        colors[3][c] = static_cast<unsigned char>(
            (colors[0][c] + 2u * colors[1][c]) / 3u);
    }

    const uint32_t color_bits =
        static_cast<uint32_t>(block[12]) |
        (static_cast<uint32_t>(block[13]) << 8u) |
        (static_cast<uint32_t>(block[14]) << 16u) |
        (static_cast<uint32_t>(block[15]) << 24u);

    for (unsigned int pixel = 0u; pixel < 16u; ++pixel) {
        const unsigned int ai =
            static_cast<unsigned int>((alpha_bits >> (3u * pixel)) & 7u);
        const unsigned int ci =
            static_cast<unsigned int>((color_bits >> (2u * pixel)) & 3u);
        rgba[pixel][0] = colors[ci][0];
        rgba[pixel][1] = colors[ci][1];
        rgba[pixel][2] = colors[ci][2];
        rgba[pixel][3] = alpha[ai];
    }
}

std::vector<float> decode_bc3_image(
    const unsigned char* data,
    size_t data_bytes,
    uint32_t width,
    uint32_t height)
{
    const uint32_t blocks_x = (width + 3u) / 4u;
    const uint32_t blocks_y = (height + 3u) / 4u;
    const uint64_t expected =
        static_cast<uint64_t>(blocks_x) *
        static_cast<uint64_t>(blocks_y) *
        16u;

    if (expected != data_bytes)
        throw std::runtime_error("BC3 mip byte count mismatch");

    const uint64_t pixel_count =
        static_cast<uint64_t>(width) *
        static_cast<uint64_t>(height);
    if (pixel_count > static_cast<uint64_t>(SIZE_MAX / (4u * sizeof(float))))
        throw std::runtime_error("BC3 decode size overflow");

    std::vector<float> rgba(
        static_cast<size_t>(pixel_count) * 4u,
        0.0f);

    size_t block_offset = 0u;
    for (uint32_t by = 0u; by < blocks_y; ++by) {
        for (uint32_t bx = 0u; bx < blocks_x; ++bx) {
            unsigned char block_rgba[16][4];
            decode_bc3_block(data + block_offset, block_rgba);
            block_offset += 16u;

            for (uint32_t py = 0u; py < 4u; ++py) {
                const uint32_t y = by * 4u + py;
                if (y >= height)
                    continue;
                for (uint32_t px = 0u; px < 4u; ++px) {
                    const uint32_t x = bx * 4u + px;
                    if (x >= width)
                        continue;
                    const unsigned int source_pixel = py * 4u + px;
                    const size_t out =
                        (static_cast<size_t>(y) * width + x) * 4u;
                    for (unsigned int c = 0u; c < 4u; ++c)
                        rgba[out + c] =
                            static_cast<float>(block_rgba[source_pixel][c]) /
                            255.0f;
                }
            }
        }
    }

    return rgba;
}

std::vector<unsigned char> read_file(const std::string& path)
{
    std::ifstream stream(path, std::ios::binary);
    if (!stream)
        throw std::runtime_error("could not open input " + path);
    stream.seekg(0, std::ios::end);
    const std::streamoff size = stream.tellg();
    stream.seekg(0, std::ios::beg);
    if (size <= 0)
        throw std::runtime_error("empty input " + path);
    std::vector<unsigned char> bytes(static_cast<size_t>(size));
    stream.read(
        reinterpret_cast<char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    if (!stream)
        throw std::runtime_error("short read " + path);
    return bytes;
}

void write_file(
    const std::string& path,
    const std::vector<unsigned char>& bytes)
{
    std::ofstream stream(path, std::ios::binary | std::ios::trunc);
    if (!stream)
        throw std::runtime_error("could not create output " + path);
    stream.write(
        reinterpret_cast<const char*>(bytes.data()),
        static_cast<std::streamsize>(bytes.size()));
    if (!stream)
        throw std::runtime_error("short write " + path);
}

} // namespace

int main(int argc, char** argv)
{
    try {
        if (argc < 4 || argc > 5) {
            std::cerr
                << "usage: xz_transcode_xzlt_etc2 <source.xzlt> <output.xzlt> <report.json> [effort]\n";
            return 2;
        }

        const std::string source_path = argv[1];
        const std::string output_path = argv[2];
        const std::string report_path = argv[3];
        const float effort =
            argc == 5 ? std::stof(argv[4]) : 80.0f;
        if (!(effort >= 0.0f && effort <= 100.0f))
            throw std::runtime_error("effort must be in [0,100]");

        std::vector<unsigned char> source =
            read_file(source_path);
        std::vector<unsigned char> output = source;

        if (source.size() < kHeaderBytes ||
            source[0] != 'X' ||
            source[1] != 'Z' ||
            source[2] != 'L' ||
            source[3] != 'T')
            throw std::runtime_error("invalid XZLT magic");

        const uint32_t version = read_u32(source, 4u);
        const uint32_t texture_count = read_u32(source, 8u);
        const uint32_t mip_count = read_u32(source, 12u);
        const uint32_t texture_record_bytes = read_u32(source, 16u);
        const uint32_t mip_record_bytes = read_u32(source, 20u);
        const uint32_t texture_table_offset = read_u32(source, 24u);
        const uint32_t mip_table_offset = read_u32(source, 28u);

        if (version != kXzltVersionBc ||
            texture_record_bytes != kTextureRecordBytes ||
            mip_record_bytes != kMipRecordBytes ||
            texture_table_offset != kHeaderBytes)
            throw std::runtime_error("unsupported XZLT source layout");

        const uint64_t payload_offset64 =
            static_cast<uint64_t>(mip_table_offset) +
            static_cast<uint64_t>(mip_count) * kMipRecordBytes;
        if (payload_offset64 > source.size())
            throw std::runtime_error("XZLT payload offset out of range");
        const size_t payload_offset =
            static_cast<size_t>(payload_offset64);

        write_u32(output, 4u, kXzltVersionEtc2);

        const unsigned int jobs =
            std::max(1u, std::thread::hardware_concurrency());

        uint32_t bc1_textures = 0u;
        uint32_t bc3_textures = 0u;
        uint32_t etc2_textures = 0u;
        uint32_t transcoded_mips = 0u;
        uint64_t transcoded_bytes = 0u;
        uint64_t total_encode_ms = 0u;

        for (uint32_t texture_index = 0u;
             texture_index < texture_count;
             ++texture_index) {
            const size_t texture_at =
                static_cast<size_t>(texture_table_offset) +
                static_cast<size_t>(texture_index) *
                    kTextureRecordBytes;
            if (texture_at + kTextureRecordBytes > source.size())
                throw std::runtime_error("texture record out of range");

            const uint32_t format = read_u32(source, texture_at + 0u);
            const uint32_t first_mip = read_u32(source, texture_at + 12u);
            const uint32_t texture_mips = read_u32(source, texture_at + 16u);

            if (format == kFormatBc1) {
                ++bc1_textures;
                continue;
            }
            if (format != kFormatBc3)
                throw std::runtime_error("unexpected source lightmap format");
            ++bc3_textures;

            write_u32(output, texture_at + 0u, kFormatEtc2Rgba8);

            for (uint32_t relative_mip = 0u;
                 relative_mip < texture_mips;
                 ++relative_mip) {
                const uint32_t absolute_mip =
                    first_mip + relative_mip;
                if (absolute_mip >= mip_count)
                    throw std::runtime_error("mip index out of range");

                const size_t mip_at =
                    static_cast<size_t>(mip_table_offset) +
                    static_cast<size_t>(absolute_mip) *
                        kMipRecordBytes;
                const uint32_t payload_relative =
                    read_u32(source, mip_at + 0u);
                const uint32_t mip_bytes =
                    read_u32(source, mip_at + 4u);
                const uint32_t width =
                    read_u32(source, mip_at + 8u);
                const uint32_t height =
                    read_u32(source, mip_at + 12u);

                const uint64_t source_at64 =
                    static_cast<uint64_t>(payload_offset) +
                    static_cast<uint64_t>(payload_relative);
                const uint64_t source_end64 =
                    source_at64 + mip_bytes;
                if (source_end64 > source.size())
                    throw std::runtime_error("mip payload out of range");

                const unsigned char* compressed =
                    source.data() + static_cast<size_t>(source_at64);
                std::vector<float> rgba =
                    decode_bc3_image(
                        compressed,
                        mip_bytes,
                        width,
                        height);

                unsigned char* encoded = nullptr;
                unsigned int encoded_bytes = 0u;
                unsigned int extended_width = 0u;
                unsigned int extended_height = 0u;
                int encode_ms = 0;

                Etc::Encode(
                    rgba.data(),
                    width,
                    height,
                    Etc::Image::Format::RGBA8,
                    Etc::NUMERIC,
                    effort,
                    jobs,
                    jobs,
                    &encoded,
                    &encoded_bytes,
                    &extended_width,
                    &extended_height,
                    &encode_ms,
                    false);

                if (!encoded)
                    throw std::runtime_error("Etc2Comp returned null payload");

                const uint32_t expected_blocks_x = (width + 3u) / 4u;
                const uint32_t expected_blocks_y = (height + 3u) / 4u;
                const uint64_t expected_bytes =
                    static_cast<uint64_t>(expected_blocks_x) *
                    static_cast<uint64_t>(expected_blocks_y) *
                    16u;

                if (encoded_bytes != mip_bytes ||
                    expected_bytes != mip_bytes ||
                    extended_width != expected_blocks_x * 4u ||
                    extended_height != expected_blocks_y * 4u) {
                    delete[] encoded;
                    throw std::runtime_error("ETC2 RGBA8 payload shape drift");
                }

                std::memcpy(
                    output.data() + static_cast<size_t>(source_at64),
                    encoded,
                    encoded_bytes);
                delete[] encoded;

                ++transcoded_mips;
                transcoded_bytes += encoded_bytes;
                if (encode_ms > 0)
                    total_encode_ms += static_cast<uint64_t>(encode_ms);
            }

            ++etc2_textures;

            std::cout
                << "XZIEL_XZLT_ETC2_TEXTURE "
                << (texture_index + 1u)
                << "/" << texture_count
                << " mips=" << texture_mips
                << "\n";
        }

        if (bc1_textures != 94u ||
            bc3_textures != 94u ||
            etc2_textures != 94u)
            throw std::runtime_error("Nacht lightmap format census drift");

        write_file(output_path, output);

        std::ofstream report(report_path, std::ios::trunc);
        if (!report)
            throw std::runtime_error("could not create report");
        report
            << "{\n"
            << "  \"schemaVersion\": 1,\n"
            << "  \"format\": \"XZLT_MOBILE_ETC2\",\n"
            << "  \"sourceVersion\": " << version << ",\n"
            << "  \"version\": " << kXzltVersionEtc2 << ",\n"
            << "  \"textureCount\": " << texture_count << ",\n"
            << "  \"mipCount\": " << mip_count << ",\n"
            << "  \"bc1TextureCount\": " << bc1_textures << ",\n"
            << "  \"sourceBc3TextureCount\": " << bc3_textures << ",\n"
            << "  \"etc2Rgba8TextureCount\": " << etc2_textures << ",\n"
            << "  \"transcodedMipCount\": " << transcoded_mips << ",\n"
            << "  \"transcodedBytes\": " << transcoded_bytes << ",\n"
            << "  \"fileBytes\": " << output.size() << ",\n"
            << "  \"offsetsPreserved\": true,\n"
            << "  \"mipDimensionsPreserved\": true,\n"
            << "  \"bc1PayloadPreserved\": true,\n"
            << "  \"errorMetric\": \"NUMERIC\",\n"
            << "  \"effort\": " << std::fixed << std::setprecision(1)
            << effort << ",\n"
            << "  \"jobs\": " << jobs << ",\n"
            << "  \"encodeMilliseconds\": " << total_encode_ms << "\n"
            << "}\n";

        std::cout
            << "XZIEL_NACHT_XZLT_ETC2_GREEN"
            << " textures=" << texture_count
            << " bc1=" << bc1_textures
            << " etc2Rgba8=" << etc2_textures
            << " transcodedMips=" << transcoded_mips
            << " bytes=" << output.size()
            << " effort=" << effort
            << " jobs=" << jobs
            << "\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr
            << "XZIEL_NACHT_XZLT_ETC2_FAIL "
            << e.what() << "\n";
        return 1;
    }
}

#pragma once
// Read-only bounded BO1 .ff stream preflight, NOT a game archive importer.
// Runs the EXACT recovered DB_AuthLoad_InflateInit/Inflate/InflateEnd functions.
#include "bo1_ff_header_probe.h"
#include <cstdint>
#ifdef __cplusplus
extern "C" {
#endif

struct BO1FFPrefixReport {
    BO1XFileHeaderInfo file;
    std::uint32_t payload_bytes_tested;
    std::uint32_t deflated_input_bytes_consumed;
    std::uint32_t first_stream_finished; // 1 only after zlib checksum and exact EOF
    std::uint64_t payload_prefix_fnv1a64;
    // On-disk XAssetList starts immediately after the 36-byte XFile header.
    // The source layout is 16 bytes with 32-bit serialized fields;
    // never reinterpret these as 64-bit native pointers.
    std::uint32_t asset_list_header_plausible;
    std::uint32_t script_string_count;
    std::uint32_t serialized_script_string_pointer;
    std::uint32_t asset_count;
    std::uint32_t serialized_asset_pointer;
};
// Test at most 131072 bytes of decompressed payload, never emit game data.
// Returns BO1_FF_HEADER_OK or a BO1FastfileProbeResult error code.
// This does not parse XAssets, authentication, models, scripts or map geometry.
__attribute__((visibility("default")))
int bo1_original_ff_payload_prefix_probe(
        const char* zone_name, std::uint32_t max_payload_bytes, BO1FFPrefixReport* output);

// Full unsecure XFile integrity: original BO1 zlib decoder, 4 KiB chunks,
// Adler32 + declared byte count + exact EOF, no retained asset bytes.
// Caller must supply a budget <=512 MiB. NOT an XAsset or map loader.
__attribute__((visibility("default")))
int bo1_original_ff_full_stream_integrity_probe(
        const char* zone_name, std::uint32_t max_payload_bytes, BO1FFPrefixReport* output);

#ifdef __cplusplus
}
#endif

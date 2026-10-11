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
    std::uint32_t first_stream_finished;
    std::uint64_t payload_prefix_fnv1a64;
};
// Test at most 131072 bytes of decompressed payload, never emit game data.
// Returns BO1_FF_HEADER_OK or a BO1FastfileProbeResult error code.
// This does not parse XAssets, authentication, models, scripts or map geometry.
__attribute__((visibility("default")))
int bo1_original_ff_payload_prefix_probe(
        const char* zone_name, std::uint32_t max_payload_bytes, BO1FFPrefixReport* output);

#ifdef __cplusplus
}
#endif

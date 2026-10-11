// Host test of the ACTUAL recovered BO1 decompression entrypoints, using
// synthetic XFile v473 archives. No Activision game data is included.
#include "bo1_ff_stream_probe.h"
#include "bo1_ff_compat.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <zlib.h>
namespace fs=std::filesystem;
static void u32(std::vector<unsigned char>& v,std::uint32_t x) {
    for(int n=0;n<4;++n)v.push_back(static_cast<unsigned char>(x>>(n*8)));
}
static std::vector<unsigned char> make_payload(std::size_t n) {
    std::vector<unsigned char> v(n);
    std::uint32_t x=0xb18ffde1u;
    for(auto &b:v) { x^=x<<13; x^=x>>17; x^=x<<5; b=static_cast<unsigned char>(x); }
    return v;
}
static std::vector<unsigned char> archive(const std::vector<unsigned char>& payload,
                                         const char* magic="IWffu100",
                                         std::uint32_t version=473,
                                         std::uint32_t claimed_size=0) {
    std::vector<unsigned char> v(magic,magic+8);
    u32(v,version);
    std::vector<unsigned char> xfile;
    u32(xfile,claimed_size ? claimed_size : static_cast<std::uint32_t>(payload.size()));
    u32(xfile,0);
    for(int i=0;i<7;++i) u32(xfile,i==0?4096:0);
    xfile.insert(xfile.end(),payload.begin(),payload.end());
    uLongf compressed_len=compressBound(static_cast<uLong>(xfile.size()));
    std::vector<unsigned char> compressed(compressed_len);
    if(compress2(compressed.data(),&compressed_len,xfile.data(),xfile.size(),
                 Z_BEST_SPEED)!=Z_OK) std::abort();
    v.insert(v.end(),compressed.begin(),compressed.begin()+compressed_len);
    return v;
}
static void put(const fs::path& p,const std::vector<unsigned char>& bytes) {
    fs::create_directories(p.parent_path());
    std::ofstream o(p,std::ios::binary|std::ios::trunc);
    o.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());
    if(!o.good()) std::abort();
}
static std::uint64_t fnv(const std::vector<unsigned char>& v,std::size_t n) {
    std::uint64_t h=14695981039346656037ull;
    for(std::size_t i=0;i<n;++i){ h^=v[i]; h*=1099511628211ull; }
    return h;
}
int main() {
    char d[]="/tmp/bo1_stream_XXXXXX";
    char* root=::mkdtemp(d);
    if(!root) return 1;
    fs::path p=fs::path(root)/"zone/english/zombie_theater.ff";
    if(bo1_ff_root_configure(root,"english")!=0) return 2;
    BO1FFPrefixReport out{};
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",32768,&out)!=BO1_FF_MISSING) return 3;
    auto data=make_payload(1024*1024+37);
    put(p,archive(data));
    // The random synthetic payload makes compression exceed the previous
    // 256KiB header-only cap, proving stream refills and multi-chunk output.
    if(fs::file_size(p)<262144) return 4;
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",65536,&out)!=BO1_FF_HEADER_OK) return 5;
    if(out.file.version!=473||out.file.size!=data.size()
       ||out.file.block_size[0]!=4096||out.payload_bytes_tested!=65536
       ||out.deflated_input_bytes_consumed<=65536
       ||out.payload_prefix_fnv1a64!=fnv(data,65536)) return 6;
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",131072,&out)!=BO1_FF_HEADER_OK) return 7;
    if(out.payload_prefix_fnv1a64!=fnv(data,131072) || out.first_stream_finished!=0) return 8;
    if(bo1_original_ff_full_stream_integrity_probe("zombie_theater",2097152,&out)!=BO1_FF_HEADER_OK) return 25;
    if(out.first_stream_finished!=1 || out.payload_bytes_tested!=data.size() ||
       out.payload_prefix_fnv1a64!=fnv(data,data.size())) return 26;
    if(bo1_original_ff_full_stream_integrity_probe("zombie_theater",131072,&out)!=BO1_FF_FULL_STREAM_LIMIT) return 27;
    if(bo1_original_ff_full_stream_integrity_probe("zombie_theater",536870913u,&out)!=BO1_FF_IO_ERROR) return 28;
    auto damaged=archive(data);
    damaged.push_back(0x7f);
    put(p,damaged);
    if(bo1_original_ff_full_stream_integrity_probe("zombie_theater",2097152,&out)!=BO1_FF_DEFLATE_ERROR) return 29;
    damaged=archive(data);
    damaged.resize(damaged.size()-2); // missing Adler32 checksum
    put(p,damaged);
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",131072,&out)!=BO1_FF_HEADER_OK) return 30;
    if(bo1_original_ff_full_stream_integrity_probe("zombie_theater",2097152,&out)!=BO1_FF_DEFLATE_ERROR) return 31;
    damaged=archive(data,"IWffu100",473,static_cast<std::uint32_t>(data.size()-1));
    put(p,damaged);
    if(bo1_original_ff_full_stream_integrity_probe("zombie_theater",2097152,&out)!=BO1_FF_DEFLATE_ERROR) return 32;
    put(p,archive(data));
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",131073,&out)!=BO1_FF_IO_ERROR) return 9;
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",0,&out)!=BO1_FF_IO_ERROR) return 10;
    if(bo1_original_ff_payload_prefix_probe("../escape",128,&out)!=BO1_FF_MISSING) return 11;
    auto small=make_payload(103);
    put(p,archive(small));
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",1024,&out)!=BO1_FF_HEADER_OK) return 12;
    if(out.payload_bytes_tested!=103||out.payload_prefix_fnv1a64!=fnv(small,small.size())) return 13;
    put(p,archive(data,"IWff0100"));
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",128,&out)!=BO1_FF_SECURE_NOT_SUPPORTED) return 14;
    put(p,archive(data,"IWffu100",472));
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",128,&out)!=BO1_FF_BAD_VERSION) return 15;
    put(p,archive(data,"BADMAGIC"));
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",128,&out)!=BO1_FF_BAD_MAGIC) return 16;
    put(p,archive(small,"IWffu100",473,1000));
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",1000,&out)!=BO1_FF_DEFLATE_ERROR) return 17;
    auto trunc=archive(data);
    trunc.resize(13);
    put(p,trunc);
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",128,&out)!=BO1_FF_IO_ERROR) return 18;
    trunc=archive(data);
    trunc.resize(trunc.size()/3);
    put(p,trunc);
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",131072,&out)!=BO1_FF_HEADER_OK) return 19;
    // Partial prefix is valid even when the *rest* of the archive is absent.
    if(out.payload_prefix_fnv1a64!=fnv(data,131072)) return 20;
    auto corrupt=archive(small);
    corrupt[12]=0; // invalid deflate header
    put(p,corrupt);
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",128,&out)!=BO1_FF_DEFLATE_ERROR) return 21;
    // Check original 32-bit serialized XAssetList layout without dereferencing pointers.
    auto metadata=make_payload(1024);
    auto le32=[&](std::size_t offset,std::uint32_t value) {
        for(unsigned b=0;b<4;++b) metadata[offset+b]=(unsigned char)(value>>(b*8u));
    };
    le32(0,185); le32(4,0xffffffffu);
    le32(8,1485); le32(12,0xfffffffeu);
    put(p,archive(metadata));
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",128,&out)!=BO1_FF_HEADER_OK) return 22;
    if(out.asset_list_header_plausible!=1 || out.script_string_count!=185 ||
       out.serialized_script_string_pointer!=0xffffffffu ||
       out.asset_count!=1485 ||
       out.serialized_asset_pointer!=0xfffffffeu) return 23;
    // First 8 bytes cannot be mistaken for complete 16-byte XAssetList.
    if(bo1_original_ff_payload_prefix_probe("zombie_theater",8,&out)!=BO1_FF_HEADER_OK ||
       out.asset_list_header_plausible!=0) return 24;
    fs::remove_all(root);
    std::puts("ORIGINAL_BO1_FULL_XFILE_ZLIB_ADLER32_AND_EXACT_EOF=PASS");
    std::puts("ORIGINAL_BO1_FULL_STREAM_BUDGET_TRUNCATION_TRAILING_GUARDS=PASS");
    std::puts("ORIGINAL_BO1_XASSETLIST_WIRE32_METADATA_PARSE=PASS");
    std::puts("ORIGINAL_BO1_ZLIB_INIT_INFLATE_END_STREAMING=PASS");
    std::puts("ORIGINAL_BO1_DEFLATED_XFILE_PAYLOAD_PREFIX_128K_VERIFIED=PASS");
    std::puts("ORIGINAL_BO1_FF_STREAM_ERRORS_AND_OUTPUT_CAP_GUARDS=PASS");
    std::puts("NOT_TESTED_WITH_RETAIL_KINO_FF=true");
    return 0;
}

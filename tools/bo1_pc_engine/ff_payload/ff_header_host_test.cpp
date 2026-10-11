// Synthetic fastfile HEADERS ONLY; no original game archives distributed.
// Actual original BO1 DB_FileExists/DB_FileSize and DB_AuthLoad_InflateInit are
// linked into this test without modifications to their function bodies.
#include "bo1_ff_header_probe.h"
#include "bo1_ff_compat.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <zlib.h>
namespace fs=std::filesystem;
static void write32(std::vector<unsigned char>& v,std::uint32_t n) {
    for(int s=0;s<32;s+=8) v.push_back((unsigned char)(n>>s));
}
static std::vector<unsigned char> fake(const char *magic="IWffu100",
                                      std::uint32_t version=473,
                                      std::uint32_t size=1234,
                                      std::uint32_t block=128) {
    std::vector<unsigned char> file(magic,magic+8);
    write32(file,version);
    std::vector<unsigned char> plain;
    write32(plain,size);
    write32(plain,512);
    for(int i=0;i<7;++i) write32(plain,i==0?block:0);
    // Add a few trailing fake bytes: preflight must stop at first 36-byte XFile.
    for(int i=0;i<300;++i) plain.push_back((unsigned char)i);
    std::vector<unsigned char> packed(compressBound(static_cast<uLong>(plain.size())));
    uLongf packed_len=packed.size();
    if(compress2(packed.data(),&packed_len,plain.data(),plain.size(),Z_BEST_COMPRESSION)!=Z_OK) std::abort();
    file.insert(file.end(),packed.begin(),packed.begin()+packed_len);
    return file;
}
static void write(const fs::path& p,const std::vector<unsigned char>& bytes) {
    fs::create_directories(p.parent_path());
    std::ofstream f(p,std::ios::binary|std::ios::trunc);
    f.write(reinterpret_cast<const char*>(bytes.data()),bytes.size());
    if(!f.good()) std::abort();
}
int main() {
    char d[]="/tmp/bo1_ff_header_XXXXXX";
    char* root=mkdtemp(d);
    if(!root) return 1;
    fs::path path=fs::path(root)/"zone/english/zombie_theater.ff";
    if(bo1_ff_root_configure(root,"english")!=0) return 2;
    BO1XFileHeaderInfo meta{};
    // Existing file lookup is the real original BO1 function.
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_MISSING) return 3;
    write(path,fake());
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_HEADER_OK) return 4;
    if(meta.version!=473 || meta.size!=1234 || meta.external_size!=512 || meta.block_size[0]!=128) return 5;
    write(path,fake("BADMAGIC"));
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_BAD_MAGIC) return 6;
    write(path,fake("IWffu100",474));
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_BAD_VERSION) return 7;
    write(path,fake("IWff0100"));
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_SECURE_NOT_SUPPORTED) return 8;
    auto bad=fake();
    for(size_t i=12;i<bad.size();++i) bad[i]=0;
    write(path,bad);
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_DEFLATE_ERROR) return 9;
    bad=fake();bad.resize(16);
    write(path,bad);
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_DEFLATE_ERROR) return 10;
    write(path,fake("IWffu100",473,0,128));
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_INVALID_XFILE_LAYOUT) return 11;
    write(path,fake("IWffu100",473,123,0));
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_INVALID_XFILE_LAYOUT) return 12;
    write(path,fake());
    if(bo1_original_fastfile_header_probe("../escape",&meta)!=BO1_FF_MISSING) return 13;
    fs::remove(path);
    fs::create_symlink("/etc/passwd",path);
    if(bo1_original_fastfile_header_probe("zombie_theater",&meta)!=BO1_FF_MISSING) return 14;
    fs::remove_all(root);
    std::puts("ORIGINAL_BO1_IWffu100_V473_DEFLATED_XFILE_HEADER_READ=PASS");
    std::puts("ORIGINAL_BO1_DB_AUTH_INFLATE_INIT_CALLED=PASS");
    std::puts("FF_HEADER_TRUNCATION_CORRUPTION_AUTH_AND_PATH_GUARDS=PASS");
    std::puts("THIS_IS_A_PRELOAD_HEADER_CHECK_NOT_A_KINO_MAP_RUN=true");
    return 0;
}

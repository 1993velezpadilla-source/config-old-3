// Authentic Black Ops 1 FF header preflight:
//  - BO1 DB_FileExists & DB_FileSize copied as exact original functions via staging.
//  - BO1 DB_AuthLoad_InflateInit copied as exact original function via staging.
//  - Original DB_LoadXFileInternal controls the format contract:
//      "IWffu100" / "IWff0100", version=473, 36-byte deflated XFile.
//  - This source is ONLY portable POSIX file IO and bounded preflight.
// Not the complete BO1 archive decoder and not a runnable map/game.
#include "bo1_ff_header_probe.h"
#include "bo1_ff_compat.h"
#include <algorithm>
#include <array>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <sys/stat.h>
#include <unistd.h>
#include <zlib.h>

#ifndef O_NOFOLLOW
#define O_NOFOLLOW 0
#endif
// Defined by real original src/database/db_auth.cpp, with exact function body
int DB_AuthLoad_InflateInit(z_stream_s *stream, bool isSecure);

// Original assertion handler is not linked in this isolated preflight. Secure
// .ff archives are rejected explicitly before invoking the original initializer.
bool Assert_MyHandler(const char *, int, int, const char *, ...) { return true; }

static std::uint32_t get_le32(const unsigned char *p) {
    return (std::uint32_t)p[0] | ((std::uint32_t)p[1] << 8u) |
           ((std::uint32_t)p[2] << 16u) | ((std::uint32_t)p[3] << 24u);
}

extern "C" int bo1_original_fastfile_header_probe(
        const char *zoneName, BO1XFileHeaderInfo *out) {
    if (!zoneName || !out) return BO1_FF_IO_ERROR;
    std::memset(out, 0, sizeof *out);
    // Original engine's public functions + our POSIX-only path bridge.
    if (!bo1_original_zone_exists(zoneName)) return BO1_FF_MISSING;
    if (bo1_original_zone_size(zoneName) < 12 + 2) return BO1_FF_IO_ERROR;
    char path[1024]{};
    DB_BuildOSPath_FromSource(zoneName, FFD_DEFAULT, sizeof path, path);
    if (!path[0]) return BO1_FF_IO_ERROR;
    const int fd=::open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if (fd<0) return BO1_FF_IO_ERROR;
    struct stat st{};
    if (::fstat(fd,&st)!=0 || !S_ISREG(st.st_mode) || st.st_size<14) {
        ::close(fd);return BO1_FF_IO_ERROR;
    }
    // Read at most 256 KiB of a potentially multi-GB game's initial data.
    // Never inflate an untrusted entire fastfile into RAM during preflight.
    constexpr size_t kInputLimit=256*1024;
    std::array<unsigned char,12+kInputLimit> bytes{};
    const size_t goal=std::min<std::uint64_t>(sizeof bytes,static_cast<std::uint64_t>(st.st_size));
    size_t count=0;
    while (count<goal) {
        ssize_t n=::pread(fd,bytes.data()+count,goal-count,static_cast<off_t>(count));
        if(n<0&&errno==EINTR) continue;
        if(n<=0) break;
        count+=static_cast<size_t>(n);
    }
    ::close(fd);
    if(count<14) return BO1_FF_IO_ERROR;
    // Real BO1 DB_LoadXFileInternal checks exact 8-byte magic; it rejects
    // authenticated fastfiles because that version of the recovered engine's
    // secure authentication path is not implemented.
    const bool unsecure=std::memcmp(bytes.data(),"IWffu100",8)==0;
    const bool secure=std::memcmp(bytes.data(),"IWff0100",8)==0;
    if(!unsecure && !secure) return BO1_FF_BAD_MAGIC;
    if (get_le32(bytes.data()+8)!=473) return BO1_FF_BAD_VERSION;
    if(secure) return BO1_FF_SECURE_NOT_SUPPORTED;
    z_stream_s stream{};
    stream.next_in=bytes.data()+12;
    stream.avail_in=static_cast<uInt>(count-12);
    std::array<unsigned char,36> raw{};
    stream.next_out=raw.data();
    stream.avail_out=static_cast<uInt>(raw.size());
    // Exactly original BO1 zlib init function, not an invented file codec.
    if(DB_AuthLoad_InflateInit(&stream,false)!=Z_OK) return BO1_FF_DEFLATE_ERROR;
    int rc=Z_OK;
    while (stream.avail_out && stream.avail_in) {
        rc=inflate(&stream,Z_NO_FLUSH);
        if(rc!=Z_OK&&rc!=Z_STREAM_END) break;
        if(rc==Z_STREAM_END) break;
    }
    const bool complete=stream.avail_out==0;
    inflateEnd(&stream);
    if(!complete || (rc!=Z_OK&&rc!=Z_STREAM_END)) return BO1_FF_DEFLATE_ERROR;
    // Original recovered XFile layout is 9 little-endian uint32 values.
    static_assert(sizeof(BO1XFileHeaderInfo)==36,
                  "Expected original BO1 XFile metadata layout");
    out->version=473;
    out->size=get_le32(raw.data());
    out->external_size=get_le32(raw.data()+4);
    std::uint64_t allocated=0;
    for(size_t i=0;i<7;++i) {
        out->block_size[i]=get_le32(raw.data()+8+4*i);
        allocated+=out->block_size[i];
    }
    // Sanity bounds only; real parsing and allocator constraints are separate.
    if(!out->size || out->size>0x7fffffffu ||
       out->external_size>0x7fffffffu || allocated>0x7fffffffu ||
       allocated==0) {
        std::memset(out,0,sizeof *out);
        return BO1_FF_INVALID_XFILE_LAYOUT;
    }
    return BO1_FF_HEADER_OK;
}

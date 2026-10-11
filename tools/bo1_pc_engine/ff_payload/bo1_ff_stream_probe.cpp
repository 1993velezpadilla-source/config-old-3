// Isolated platform boundary for genuine BO1 PC FF v473 zlib stream.
// Original game functions linked from pinned src/database/db_auth.cpp:
//
//   DB_AuthLoad_InflateInit
//   DB_AuthLoad_Inflate
//   DB_AuthLoad_InflateEnd
//
// Reads at most 128 KiB of DECOMPRESSED data after the XFile header and
// returns metrics only; it never persists or redistributes protected assets.
#include "bo1_ff_stream_probe.h"
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

int DB_AuthLoad_InflateInit(z_stream_s *stream,bool is_secure);
int DB_AuthLoad_Inflate(z_stream_s *stream,int flush);
void DB_AuthLoad_InflateEnd(z_stream_s *stream);

namespace {
static constexpr std::uint64_t kFnvInitial=14695981039346656037ull;
static constexpr std::uint64_t kFnvPrime=1099511628211ull;
std::uint32_t read_u32(const unsigned char* p) {
    return std::uint32_t(p[0]) | (std::uint32_t(p[1])<<8u)
           | (std::uint32_t(p[2])<<16u) | (std::uint32_t(p[3])<<24u);
}
class Stream {
    int fd_=-1;
    z_stream_s zip_{};
    bool zinit_=false;
    std::uint64_t offset_=12;
    std::array<unsigned char,4096> in_{};
public:
    explicit Stream(int fd):fd_(fd) {}
    Stream(const Stream&)=delete;
    Stream& operator=(const Stream&)=delete;
    ~Stream() {
        if(zinit_) DB_AuthLoad_InflateEnd(&zip_);
        if(fd_>=0) ::close(fd_);
    }
    bool init() {
        if(DB_AuthLoad_InflateInit(&zip_,false)!=Z_OK) return false;
        zinit_=true;
        return true;
    }
    // Consume exactly n bytes of decompressed stream; with bounded input reads.
    // Reject premature EOF, zlib errors and attempts to advance past stream end.
    bool take(unsigned char* data,std::size_t n) {
        if(!data) return false;
        while(n) {
            if(zip_.avail_in==0) {
                ssize_t count;
                do { count=::pread(fd_,in_.data(),in_.size(),static_cast<off_t>(offset_)); }
                while(count<0 && errno==EINTR);
                if(count<=0) return false;
                offset_+=static_cast<std::uint64_t>(count);
                zip_.next_in=in_.data();
                zip_.avail_in=static_cast<uInt>(count);
            }
            const auto chunk=std::min<std::size_t>(n,4096);
            zip_.next_out=data;
            zip_.avail_out=static_cast<uInt>(chunk);
            const auto before_in=zip_.avail_in;
            int result=DB_AuthLoad_Inflate(&zip_,Z_NO_FLUSH);
            const auto produced=chunk-zip_.avail_out;
            if(result!=Z_OK && result!=Z_STREAM_END) return false;
            if(!produced) {
                if(result==Z_STREAM_END || before_in==zip_.avail_in) return false;
                continue;
            }
            data+=produced;
            n-=produced;
            if(result==Z_STREAM_END && n!=0) return false;
        }
        return true;
    }
    std::uint32_t consumed() const { return static_cast<std::uint32_t>(
        std::min<std::uint64_t>(zip_.total_in,std::numeric_limits<std::uint32_t>::max())); }
    bool stream_finished() const { return zip_.avail_out>0 && zip_.total_in>0; }
};
bool valid_header(const BO1XFileHeaderInfo &header) {
    std::uint64_t blocks=0;
    for(unsigned i=0;i<7;++i) blocks+=header.block_size[i];
    return header.size>0 && header.size<=0x7fffffff
           && header.external_size<=0x7fffffff
           && blocks>0 && blocks<=0x7fffffff;
}
}

extern "C" int bo1_original_ff_payload_prefix_probe(
        const char* zone_name,std::uint32_t max_payload_bytes,BO1FFPrefixReport* out) {
    if(!out || !zone_name) return BO1_FF_IO_ERROR;
    std::memset(out,0,sizeof *out);
    if(max_payload_bytes==0 || max_payload_bytes>131072) return BO1_FF_IO_ERROR;
    // Call unchanged upstream Black Ops zone lookup before opening.
    if(!bo1_original_zone_exists(zone_name)) return BO1_FF_MISSING;
    if(bo1_original_zone_size(zone_name)<14) return BO1_FF_IO_ERROR;
    char path[1024]{};
    DB_BuildOSPath_FromSource(zone_name,FFD_DEFAULT,sizeof path,path);
    if(!path[0]) return BO1_FF_IO_ERROR;
    int fd=::open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0) return BO1_FF_IO_ERROR;
    Stream stream(fd);
    std::array<unsigned char,12> begin{};
    ssize_t n;
    do { n=::pread(fd,begin.data(),begin.size(),0); }
    while(n<0 && errno==EINTR);
    if(n!=static_cast<ssize_t>(begin.size())) return BO1_FF_IO_ERROR;
    const bool unsecure=std::memcmp(begin.data(),"IWffu100",8)==0;
    const bool secure=std::memcmp(begin.data(),"IWff0100",8)==0;
    if(!unsecure && !secure) return BO1_FF_BAD_MAGIC;
    if(read_u32(begin.data()+8)!=473) return BO1_FF_BAD_VERSION;
    if(secure) return BO1_FF_SECURE_NOT_SUPPORTED;
    if(!stream.init()) return BO1_FF_DEFLATE_ERROR;
    std::array<unsigned char,36> raw{};
    if(!stream.take(raw.data(),raw.size())) return BO1_FF_DEFLATE_ERROR;
    BO1XFileHeaderInfo x{};
    x.version=473;
    x.size=read_u32(raw.data());
    x.external_size=read_u32(raw.data()+4);
    for(unsigned i=0;i<7;++i)x.block_size[i]=read_u32(raw.data()+8+4*i);
    if(!valid_header(x)) return BO1_FF_INVALID_XFILE_LAYOUT;
    std::uint32_t want=std::min(max_payload_bytes,x.size);
    std::uint64_t digest=kFnvInitial;
    std::array<unsigned char,4096> buffer{};
    std::uint32_t got=0;
    while(got<want) {
        const std::size_t batch=std::min<std::size_t>(buffer.size(),want-got);
        if(!stream.take(buffer.data(),batch)) return BO1_FF_DEFLATE_ERROR;
        for(std::size_t i=0;i<batch;++i) {
            digest^=buffer[i];
            digest*=kFnvPrime;
        }
        got+=static_cast<std::uint32_t>(batch);
    }
    out->file=x;
    out->payload_bytes_tested=got;
    out->deflated_input_bytes_consumed=stream.consumed();
    out->first_stream_finished=0; // deliberately do not assert full stream consumed
    out->payload_prefix_fnv1a64=digest;
    return BO1_FF_HEADER_OK;
}

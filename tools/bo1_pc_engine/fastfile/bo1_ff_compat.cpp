// This is only a platform boundary (Windows file API -> POSIX) for original BO1 functions.
// Game behavior DB_FileExists and DB_FileSize is extracted unchanged at CI time.
// Does not parse FF contents and cannot run any BO1 map.
#include "bo1_ff_compat.h"
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <mutex>
#include <new>
#include <string>
#include <sys/stat.h>
#include <unistd.h>

namespace {
struct Handle { int fd; };
std::mutex config_mutex;
std::string root;
std::string language="english";
std::atomic<int> invalid_names{0};
bool valid_part(const char* part, size_t maximum=63) {
    if(!part) return false;
    size_t n=std::strlen(part);
    if(n==0||n>maximum) return false;
    for(size_t i=0;i<n;++i) {
        char c=part[i];
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||
             (c>='0'&&c<='9')||c=='_'||c=='-')) return false;
    }
    return true;
}
std::string make_path(const char* zoneName, FF_DIR source, bool usermap) {
    if(!valid_part(zoneName)) { invalid_names.fetch_add(1); return {}; }
    std::lock_guard<std::mutex> lock(config_mutex);
    if(root.empty()) return {};
    std::string zone=zoneName;
    if(usermap||source==FFD_USER_MAP)
        return root+"/usermaps/"+zone+"/"+zone+".ff";
    if(source==FFD_MOD_DIR) return {}; // refuse unknown game mod root
    if(source!=FFD_DEFAULT) return {};
    // Mirrors DB_BuildOSPath_FromSource: try the Common first, then localized zone.
    // Android is case sensitive; probe both historically plausible directory cases.
    const std::string base=root+"/zone/";
    for(const auto &folder: {std::string("Common"),std::string("common"),language}) {
        const auto p=base+folder+"/"+zone+".ff";
        struct stat st{};
        if(::stat(p.c_str(),&st)==0&&S_ISREG(st.st_mode)) return p;
    }
    return base+language+"/"+zone+".ff";
}
void emit_path(const std::string& path, unsigned int max_len, char* out) {
    if(!out || max_len==0) return;
    if(path.empty() || path.size()+1 > static_cast<size_t>(max_len)) { out[0]='\0'; return; }
    std::memcpy(out,path.c_str(),path.size()+1);
}
bool valid_root(const char* p) {
    if(!p || p[0]!='/') return false;
    const size_t n=std::strlen(p);
    if(n<2 || n>512) return false;
    for(const char *c=p;*c;++c) if(*c=='\n'||*c=='\r'||*c=='\0') return false;
    return true;
}
}
extern "C" int bo1_ff_root_configure(const char* game_root, const char* locale) {
    if(!valid_root(game_root)||!valid_part(locale,24)) return -1;
    std::lock_guard<std::mutex> lock(config_mutex);
    root=game_root;
    language=locale;
    while(root.size()>1 && root.back()=='/') root.pop_back();
    return 0;
}
void DB_BuildOSPath_FromSource(const char *zoneName, FF_DIR source, unsigned int length, char *filename) {
    emit_path(make_path(zoneName,source,false),length,filename);
}
void DB_BuildOSPath_ForUsermap(const char *zoneName, unsigned int length, char *filename) {
    emit_path(make_path(zoneName,FFD_USER_MAP,true),length,filename);
}
void *CreateFileA(const char *path, unsigned int access, unsigned int, void *,
                  unsigned int creation, unsigned int, void *) {
    // Only support read-only OPEN_EXISTING as the original BO1 functions use.
    if(!path||!*path||access!=0x80000000u||creation!=3) return reinterpret_cast<void*>(-1);
    const int fd=::open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0) return reinterpret_cast<void*>(-1);
    const auto h=new(std::nothrow) Handle{fd};
    if(!h) {::close(fd);return reinterpret_cast<void*>(-1);}
    return h;
}
unsigned int GetFileSize(void *raw, void*) {
    if(!raw||raw==reinterpret_cast<void*>(-1)) return UINT32_MAX;
    auto *h=static_cast<Handle*>(raw);
    struct stat st{};
    if(::fstat(h->fd,&st)!=0||!S_ISREG(st.st_mode)||st.st_size<0
       ||static_cast<std::uint64_t>(st.st_size)>INT32_MAX) return UINT32_MAX;
    return static_cast<unsigned int>(st.st_size);
}
int CloseHandle(void *raw) {
    if(!raw||raw==reinterpret_cast<void*>(-1)) return 0;
    auto *h=static_cast<Handle*>(raw);
    int ok=::close(h->fd)==0;
    delete h;
    return ok;
}
extern "C" int bo1_original_zone_exists(const char *name) {
    return name && DB_FileExists(name,FFD_DEFAULT) ? 1:0;
}
extern "C" int bo1_original_zone_size(const char *name) {
    return name?DB_FileSize(name,FFD_DEFAULT):0;
}

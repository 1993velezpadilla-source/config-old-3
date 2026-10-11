#include "bo1_ff_compat.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
namespace fs=std::filesystem;
static void write_file(const fs::path&p,size_t length) {
    fs::create_directories(p.parent_path());
    std::ofstream o(p,std::ios::binary|std::ios::trunc);
    for(size_t i=0;i<length;i++)o.put(char(i%251));
}
int main() {
    char d[]="/tmp/bo1ffXXXXXX";
    const char* root=mkdtemp(d);
    if(!root) return 1;
    fs::path base(root);
    // No proprietary BO1 map data: synthetic placeholder bytes only.
    write_file(base/"zone/english/zombie_theater.ff",157);
    write_file(base/"zone/english/common_zombie.ff",211);
    if(bo1_ff_root_configure(root,"english")!=0) return 2;
    if(bo1_original_zone_exists("zombie_theater")!=1) return 3;
    if(bo1_original_zone_size("zombie_theater")!=157) return 4;
    if(bo1_original_zone_size("common_zombie")!=211) return 5;
    if(bo1_original_zone_exists("not_existing")!=0) return 6;
    if(bo1_original_zone_exists("../escape")!=0) return 7;
    if(bo1_original_zone_exists("/absolute")!=0) return 8;
    if(bo1_original_zone_exists("bad\\backslash")!=0) return 9;
    write_file(base/"zone/Common/zombie_theater.ff",333);
    if(bo1_original_zone_size("zombie_theater")!=333) return 10;
    fs::remove(base/"zone/Common/zombie_theater.ff");
    fs::create_symlink("/etc/passwd",base/"zone/Common/zombie_theater.ff");
    if(bo1_original_zone_exists("zombie_theater")!=0) return 11; // precedence but no symlink following
    fs::remove(base/"zone/Common/zombie_theater.ff");
    write_file(base/"usermaps/custom/custom.ff",177);
    if(DB_FileSize("custom",FFD_USER_MAP)!=177) return 12;
    fs::remove_all(base);
    std::puts("EXACT_ORIGINAL_BO1_DB_FILEEXISTS_HOST_TEST=PASS");
    std::puts("EXACT_ORIGINAL_BO1_DB_FILESIZE_HOST_TEST=PASS");
    std::puts("BO1_FASTFILE_PATH_TRAVERSAL_GUARD=PASS");
    return 0;
}

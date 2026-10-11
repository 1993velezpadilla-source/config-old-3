// New POSIX memory boundary for authentic original BO1 DB_AllocXBlocks.
// Neither the original source allocator itself (PMem/Z_Malloc) nor the
// entire XAsset relocator are ported. This is bounded preflight only.
#include "bo1_alloc_compat.h"
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
namespace {
constexpr unsigned int kBlockMax=16u*1024u*1024u;
std::atomic<unsigned int> gAllocFailure{0};
}
unsigned char *DB_MemAlloc(unsigned int size,unsigned int, unsigned int,
                          const char*,int) {
    if (size==0||size>kBlockMax){gAllocFailure.fetch_add(1);return nullptr;}
    void* memory=nullptr;
    if(posix_memalign(&memory,4096,size)!=0){gAllocFailure.fetch_add(1);return nullptr;}
    std::memset(memory,0,size);
    return static_cast<unsigned char*>(memory);
}
int PMem_GetOverAllocatedSize(){return 0;}
void Com_Error(int,const char *format,...){
    va_list ap;
    va_start(ap,format);
    std::fprintf(stderr,"BO1 native allocator fatal: ");
    std::vfprintf(stderr,format,ap);
    std::fprintf(stderr,"\n");
    va_end(ap);
    std::abort();
}
void Com_Printf(int,const char*,...){}
// Native smoke exercises the real original allocator with synthetic
// seven-zone block sizes and validates independent 64-bit pointers.
extern "C" int bo1_original_xblock_allocation_smoke(){
    unsigned int sizes[7]={128,0,257,0,4096,0,33};
    XBlock blocks[7]{};
    DB_AllocXBlocks(sizes,"bo1_android_synthetic_only",blocks,0,0);
    int valid=1;
    for(int i=0;i<7;++i){
        if(sizes[i]) {
            if(!blocks[i].data||blocks[i].size!=sizes[i]||
               reinterpret_cast<std::uintptr_t>(blocks[i].data)%4096!=0) valid=0;
            else {
                for(unsigned j=0;j<sizes[i];++j)
                    if(blocks[i].data[j]!=0){valid=0;break;}
                blocks[i].data[sizes[i]-1]=(unsigned char)(i+1);
                if(blocks[i].data[sizes[i]-1]!=(unsigned char)(i+1)) valid=0;
            }
        } else if(blocks[i].data || blocks[i].size){valid=0;}
    }
    for(auto &block:blocks){std::free(block.data);block.data=nullptr;block.size=0;}
    if(gAllocFailure.load()!=0) valid=0;
    return valid?0:1;
}

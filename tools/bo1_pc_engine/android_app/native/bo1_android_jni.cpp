// Thin Android entrypoint. It calls actual original recovered BO1 C++
// orientation, packed color decoding, XFile path and zlib stream functions.
// No invented zombie gameplay, renderer, scripts or game assets are included.
#include <jni.h>
#include <cmath>
#include <iomanip>
#include <sstream>
#include <string>
#include "bo1_ff_stream_probe.h"
#include "bo1_ff_compat.h"
#include "bo1_alloc_compat.h"

extern "C" void bo1_original_angle_vectors(
    const float angles[3], float forward[3], float right[3], float up[3]);
extern "C" void bo1_original_unpack_rgba(
    const unsigned char src[4], float dst[4]);

namespace {
jstring as_java(JNIEnv *env, const std::string &message) {
    return env->NewStringUTF(message.c_str());
}
bool approximately(float a,float b) { return std::fabs(a-b)<0.0002f; }
std::string name_for_result(int result) {
    switch(result) {
    case BO1_FF_HEADER_OK: return "HEADER + PAYLOAD PREFIX PARSED";
    case BO1_FF_MISSING: return "FILE NOT FOUND";
    case BO1_FF_IO_ERROR: return "FILE ACCESS / TRUNCATED";
    case BO1_FF_BAD_MAGIC: return "UNSUPPORTED MAGIC";
    case BO1_FF_BAD_VERSION: return "WRONG ORIGINAL FASTFILE VERSION";
    case BO1_FF_SECURE_NOT_SUPPORTED: return "ORIGINAL AUTHENTICATED FF: NOT SUPPORTED";
    case BO1_FF_DEFLATE_ERROR: return "ORIGINAL STREAM DEFLATE FAILED";
    case BO1_FF_INVALID_XFILE_LAYOUT: return "ORIGINAL XFILE HEADER UNSUPPORTED";
    default: return "UNKNOWN FILE ERROR";
    }
}
}
extern "C" JNIEXPORT jstring JNICALL
Java_com_bubblegum_bo1native_MainActivity_nativeSelfTest(
        JNIEnv *env, jclass) {
    const float angles[3]={0.f,90.f,0.f};
    float forward[3]{}, right[3]{}, up[3]{};
    bo1_original_angle_vectors(angles,forward,right,up);
    const bool original_camera =
        approximately(forward[0],0.f) &&
        approximately(forward[1],1.f) &&
        approximately(forward[2],0.f);
    const unsigned char bytes[4]={255,0,128,255};
    float decoded[4]{};
    bo1_original_unpack_rgba(bytes,decoded);
    const bool original_material =
        approximately(decoded[0],1.f) &&
        approximately(decoded[1],0.f) &&
        approximately(decoded[2],128.f/255.f) &&
        approximately(decoded[3],1.f);
    const bool original_memory = bo1_original_xblock_allocation_smoke()==0;
    std::ostringstream out;
    out<<"NATIVE BO1 C++ RUNTIME / ARM64\n";
    out<<"ORIGINAL CAMERA ANGLE: "<<(original_camera?"PASS":"FAIL")<<"\n";
    out<<"ORIGINAL TEXTURE COLOR: "<<(original_material?"PASS":"FAIL")<<"\n";
    out<<"ORIGINAL 7-ZONE BLOCK MEMORY: "<<(original_memory?"PASS":"FAIL")<<"\n";
    out<<"Native library loaded: YES\n";
    out<<"Original full game engine: NOT PORTED\n";
    out<<"Kino map executable: NO\n";
    out<<"No emulator, no fake FPS scene.\n";
    return as_java(env,out.str());
}
extern "C" JNIEXPORT jstring JNICALL
Java_com_bubblegum_bo1native_MainActivity_nativeProbeFile(
        JNIEnv *env,jclass,jstring jroot,jstring jzone) {
    if(!jroot||!jzone) return as_java(env,"NULL PATH REJECTED");
    const char *root=env->GetStringUTFChars(jroot,nullptr);
    if(!root) return nullptr;
    const char *zone=env->GetStringUTFChars(jzone,nullptr);
    if(!zone) {env->ReleaseStringUTFChars(jroot,root);return nullptr;}
    std::string filename(zone);
    int configured=bo1_ff_root_configure(root,"english");
    BO1FFPrefixReport metrics{};
    int result=configured==0
        ? bo1_original_ff_payload_prefix_probe(zone,65536,&metrics)
        : BO1_FF_IO_ERROR;
    env->ReleaseStringUTFChars(jzone,zone);
    env->ReleaseStringUTFChars(jroot,root);
    std::ostringstream out;
    out<<"ORIGINAL BO1 FASTFILE STREAM\n";
    out<<"Zone: "<<filename<<"\n";
    out<<"Result: "<<name_for_result(result)<<" ("<<result<<")\n";
    if(result==BO1_FF_HEADER_OK) {
        out<<"XFile version: "<<metrics.file.version<<"\n";
        out<<"Declared stream size: "<<metrics.file.size<<"\n";
        out<<"External bytes: "<<metrics.file.external_size<<"\n";
        out<<"Decoded prefix bytes: "<<metrics.payload_bytes_tested<<"\n";
        out<<"Deflated bytes consumed: "<<metrics.deflated_input_bytes_consumed<<"\n";
        out<<"Prefix hash FNV-1a: "<<std::hex<<metrics.payload_prefix_fnv1a64<<std::dec<<"\n";
        out<<"Data decoded only; XAssets NOT LOADED.\n";
    } else if(result==BO1_FF_SECURE_NOT_SUPPORTED) {
        out<<"The recovered upstream loader rejects this authenticated FF variant.\n";
        out<<"It is not a normal zlib-only file. A real authenticated asset loader is still required.\n";
    }
    out<<"No retail game files transmitted or embedded in APK.\n";
    return as_java(env,out.str());
}

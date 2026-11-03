#pragma once

// ABI-only declarations used to compile original shared IW3 data structures
// on Android. These declarations do not implement D3D9 or a renderer.
// Windows builds continue to include the real Direct3D 9 SDK headers.
#include <cstdint>
#include <type_traits>

struct IDirect3D9;
struct IDirect3DDevice9;
struct IDirect3DSwapChain9;
struct IDirect3DVertexBuffer9;
struct IDirect3DIndexBuffer9;
struct IDirect3DBaseTexture9;
struct IDirect3DTexture9;
struct IDirect3DVolumeTexture9;
struct IDirect3DCubeTexture9;
struct IDirect3DQuery9;
struct IDirect3DSurface9;
struct IDirect3DVertexDeclaration9;
struct IDirect3DVertexShader9;
struct IDirect3DPixelShader9;
struct _D3DCAPS9;
struct _D3DPRESENT_PARAMETERS_;

struct HWND__;
struct HINSTANCE__;
typedef HWND__ *HWND;
typedef int32_t HRESULT;

// D3D9's serialized/runtime data structures store these enums as 32-bit ints.
// Values below are the native D3D9 SDK values used by the original image code.
enum _D3DFORMAT : int
{
    D3DFMT_UNKNOWN = 0,
    D3DFMT_D24S8 = 75,
    D3DFMT_D24X8 = 77,
    D3DFMT_D16 = 80,
};

enum _D3DCUBEMAP_FACES : int
{
    D3DCUBEMAP_FACE_POSITIVE_X = 0,
    D3DCUBEMAP_FACE_NEGATIVE_X = 1,
    D3DCUBEMAP_FACE_POSITIVE_Y = 2,
    D3DCUBEMAP_FACE_NEGATIVE_Y = 3,
    D3DCUBEMAP_FACE_POSITIVE_Z = 4,
    D3DCUBEMAP_FACE_NEGATIVE_Z = 5,
};

enum _D3DMULTISAMPLE_TYPE : int
{
    D3DMULTISAMPLE_NONE = 0,
    D3DMULTISAMPLE_NONMASKABLE = 1,
    D3DMULTISAMPLE_2_SAMPLES = 2,
    D3DMULTISAMPLE_3_SAMPLES = 3,
    D3DMULTISAMPLE_4_SAMPLES = 4,
    D3DMULTISAMPLE_5_SAMPLES = 5,
    D3DMULTISAMPLE_6_SAMPLES = 6,
    D3DMULTISAMPLE_7_SAMPLES = 7,
    D3DMULTISAMPLE_8_SAMPLES = 8,
    D3DMULTISAMPLE_9_SAMPLES = 9,
    D3DMULTISAMPLE_10_SAMPLES = 10,
    D3DMULTISAMPLE_11_SAMPLES = 11,
    D3DMULTISAMPLE_12_SAMPLES = 12,
    D3DMULTISAMPLE_13_SAMPLES = 13,
    D3DMULTISAMPLE_14_SAMPLES = 14,
    D3DMULTISAMPLE_15_SAMPLES = 15,
    D3DMULTISAMPLE_16_SAMPLES = 16,
};

enum _D3DTEXTUREFILTERTYPE : int
{
    D3DTEXF_NONE = 0,
    D3DTEXF_POINT = 1,
    D3DTEXF_LINEAR = 2,
    D3DTEXF_ANISOTROPIC = 3,
    D3DTEXF_PYRAMIDALQUAD = 6,
    D3DTEXF_GAUSSIANQUAD = 7,
    D3DTEXF_CONVOLUTIONMONO = 8,
};

struct _D3DDISPLAYMODE
{
    uint32_t Width;
    uint32_t Height;
    uint32_t RefreshRate;
    _D3DFORMAT Format;
};

static_assert(sizeof(_D3DFORMAT) == sizeof(int),
              "D3D9 format field must retain the original 32-bit ABI");
static_assert(sizeof(_D3DCUBEMAP_FACES) == sizeof(int),
              "D3D9 cubemap face must retain the original 32-bit ABI");
static_assert(sizeof(_D3DDISPLAYMODE) == 16,
              "D3D9 display mode must retain its 16-byte ABI");

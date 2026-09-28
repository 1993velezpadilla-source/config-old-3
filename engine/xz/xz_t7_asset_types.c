#include "xz_t7_asset_types.h"

static const char *const names[XZ_T7_FULL_TYPE_COUNT] = {
    [0x00] = "physpreset",
    [0x01] = "physconstraints",
    [0x02] = "destructibledef",
    [0x03] = "xanimparts",
    [0x04] = "xmodel",
    [0x05] = "xmodelmesh",
    [0x06] = "material",
    [0x07] = "compute_shader_set",
    [0x08] = "technique_set",
    [0x09] = "image",
    [0x0A] = "sound",
    [0x0B] = "sound_patch",
    [0x0C] = "clipmap",
    [0x0D] = "comworld",
    [0x0E] = "gameworld",
    [0x0F] = "map_ents",
    [0x10] = "gfxworld",
    [0x11] = "light_def",
    [0x12] = "lensflare_def",
    [0x13] = "ui_map",
    [0x14] = "font",
    [0x15] = "fonticon",
    [0x16] = "localize_entry",
    [0x17] = "weapon",
    [0x18] = "weapondef",
    [0x19] = "weapon_variant",
    [0x1A] = "weapon_full",
    [0x1B] = "cgmedia",
    [0x1C] = "playersounds",
    [0x1D] = "playerfx",
    [0x1E] = "sharedweaponsounds",
    [0x1F] = "attachment",
    [0x20] = "attachment_unique",
    [0x21] = "weapon_camo",
    [0x22] = "customization_table",
    [0x23] = "customization_table_fe_images",
    [0x24] = "customization_table_color",
    [0x25] = "snddriver_globals",
    [0x26] = "fx",
    [0x27] = "tagfx",
    [0x28] = "new_lensflare_def",
    [0x29] = "impact_fx",
    [0x2A] = "impact_sound",
    [0x2B] = "player_character",
    [0x2C] = "aitype",
    [0x2D] = "character",
    [0x2E] = "xmodelalias",
    [0x2F] = "rawfile",
    [0x30] = "stringtable",
    [0x31] = "structured_table",
    [0x32] = "leaderboard",
    [0x33] = "ddl",
    [0x34] = "glasses",
    [0x35] = "texturelist",
    [0x36] = "scriptparsetree",
    [0x37] = "keyvaluepairs",
    [0x38] = "vehicledef",
    [0x39] = "addon_map_ents",
    [0x3A] = "tracer",
    [0x3B] = "slug",
    [0x3C] = "surfacefx_table",
    [0x3D] = "surfacesounddef",
    [0x3E] = "footstep_table",
    [0x3F] = "entityfximpacts",
    [0x40] = "entitysoundimpacts",
    [0x41] = "zbarrier",
    [0x42] = "vehiclefxdef",
    [0x43] = "vehiclesounddef",
    [0x44] = "typeinfo",
    [0x45] = "scriptbundle",
    [0x46] = "scriptbundlelist",
    [0x47] = "rumble",
    [0x48] = "bulletpenetration",
    [0x49] = "locdmgtable",
    [0x4A] = "aimtable",
    [0x4B] = "animselectortableset",
    [0x4C] = "animmappingtable",
    [0x4D] = "animstatemachine",
    [0x4E] = "behaviortree",
    [0x4F] = "behaviorstatemachine",
    [0x50] = "ttf",
    [0x51] = "sanim",
    [0x52] = "light_description",
    [0x53] = "shellshock",
    [0x54] = "xcam",
    [0x55] = "bg_cache",
    [0x56] = "texture_combo",
    [0x57] = "flametable",
    [0x58] = "bitfield",
    [0x59] = "attachment_cosmetic_variant",
    [0x5A] = "maptable",
    [0x5B] = "maptable_loading_images",
    [0x5C] = "medal",
    [0x5D] = "medaltable",
    [0x5E] = "objective",
    [0x5F] = "objective_list",
    [0x60] = "umbra_tome",
    [0x61] = "navmesh",
    [0x62] = "navvolume",
    [0x63] = "binaryhtml",
    [0x64] = "laser",
    [0x65] = "beam",
    [0x66] = "streamer_hint",
    [0x67] = "runtime_type_count_sentinel",
    [0x68] = "string_or_depend",
    [0x69] = "assetlist",
    [0x6A] = "report",
    [0x6B] = "reserved_6b"
};

const char *XzT7AssetType_Name(XzT7AssetType type)
{
    unsigned int i = (unsigned int)type;
    if (i >= XZ_T7_FULL_TYPE_COUNT)
        return "unknown";
    return names[i];
}

int XzT7AssetType_IsRuntimeType(XzT7AssetType type)
{
    return (unsigned int)type < XZ_T7_RUNTIME_TYPE_COUNT;
}

XzPackageBootFamily XzT7AssetType_Family(XzT7AssetType type)
{
    switch (type) {
    case XZ_T7_PHYSPRESET:
    case XZ_T7_PHYSCONSTRAINTS:
    case XZ_T7_CLIPMAP:
    case XZ_T7_GAMEWORLD:
        return XZ_PACKAGE_BOOT_COLLISION;

    case XZ_T7_NAVMESH:
    case XZ_T7_NAVVOLUME:
        return XZ_PACKAGE_BOOT_NAVIGATION_PATHING;

    case XZ_T7_COMWORLD:
    case XZ_T7_GFXWORLD:
    case XZ_T7_MAP_ENTS:
    case XZ_T7_ADDON_MAP_ENTS:
    case XZ_T7_UMBRA_TOME:
        return XZ_PACKAGE_BOOT_WORLD_GEOMETRY;

    case XZ_T7_XMODEL:
    case XZ_T7_XMODELMESH:
    case XZ_T7_XMODELALIAS:
    case XZ_T7_DESTRUCTIBLEDEF:
    case XZ_T7_ZBARRIER:
        return XZ_PACKAGE_BOOT_STATIC_MODELS_PROPS;

    case XZ_T7_MATERIAL:
    case XZ_T7_COMPUTE_SHADER_SET:
    case XZ_T7_TECHNIQUE_SET:
    case XZ_T7_IMAGE:
    case XZ_T7_TEXTURELIST:
    case XZ_T7_TEXTURE_COMBO:
        return XZ_PACKAGE_BOOT_MATERIALS_TEXTURES;

    case XZ_T7_LIGHT_DEF:
    case XZ_T7_LENSFLARE_DEF:
    case XZ_T7_NEW_LENSFLARE_DEF:
    case XZ_T7_LIGHT_DESCRIPTION:
    case XZ_T7_SHELLSHOCK:
        return XZ_PACKAGE_BOOT_LIGHTING_POSTFX;

    case XZ_T7_XANIMPARTS:
    case XZ_T7_PLAYER_CHARACTER:
    case XZ_T7_CHARACTER:
    case XZ_T7_SANIM:
        return XZ_PACKAGE_BOOT_ANIMATED_MODELS_RIGS;

    case XZ_T7_ANIMSELECTORTABLESET:
    case XZ_T7_ANIMMAPPINGTABLE:
    case XZ_T7_ANIMSTATEMACHINE:
    case XZ_T7_BEHAVIORTREE:
    case XZ_T7_BEHAVIORSTATEMACHINE:
    case XZ_T7_AITYPE:
        return XZ_PACKAGE_BOOT_ANIMATIONS;

    case XZ_T7_SOUND:
    case XZ_T7_SOUND_PATCH:
    case XZ_T7_SNDDRIVER_GLOBALS:
    case XZ_T7_PLAYERSOUNDS:
    case XZ_T7_SHAREDWEAPONSOUNDS:
    case XZ_T7_IMPACT_SOUND:
    case XZ_T7_SURFACESOUNDDEF:
    case XZ_T7_FOOTSTEP_TABLE:
    case XZ_T7_ENTITYSOUNDIMPACTS:
    case XZ_T7_VEHICLESOUNDDEF:
        return XZ_PACKAGE_BOOT_AUDIO_SFX;

    case XZ_T7_FX:
    case XZ_T7_TAGFX:
    case XZ_T7_IMPACT_FX:
    case XZ_T7_PLAYERFX:
    case XZ_T7_SURFACEFX_TABLE:
    case XZ_T7_ENTITYFXIMPACTS:
    case XZ_T7_VEHICLEFXDEF:
    case XZ_T7_TRACER:
    case XZ_T7_LASER:
    case XZ_T7_BEAM:
        return XZ_PACKAGE_BOOT_VFX_PARTICLES;

    case XZ_T7_WEAPON:
    case XZ_T7_WEAPONDEF:
    case XZ_T7_WEAPON_VARIANT:
    case XZ_T7_WEAPON_FULL:
    case XZ_T7_ATTACHMENT:
    case XZ_T7_ATTACHMENT_UNIQUE:
    case XZ_T7_ATTACHMENT_COSMETIC_VARIANT:
    case XZ_T7_WEAPON_CAMO:
    case XZ_T7_BULLETPENETRATION:
    case XZ_T7_LOCDMGTABLE:
    case XZ_T7_AIMTABLE:
    case XZ_T7_FLAMETABLE:
    case XZ_T7_SLUG:
        return XZ_PACKAGE_BOOT_WEAPONS_EQUIPMENT;

    case XZ_T7_UI_MAP:
    case XZ_T7_FONT:
    case XZ_T7_FONTICON:
    case XZ_T7_TTF:
    case XZ_T7_LOCALIZE_ENTRY:
    case XZ_T7_BINARYHTML:
    case XZ_T7_CGMEDIA:
    case XZ_T7_MAPTABLE_LOADING_IMAGES:
        return XZ_PACKAGE_BOOT_HUD_UI_PROMPTS;

    case XZ_T7_RAWFILE:
    case XZ_T7_STRINGTABLE:
    case XZ_T7_STRUCTURED_TABLE:
    case XZ_T7_DDL:
    case XZ_T7_SCRIPTPARSETREE:
    case XZ_T7_KEYVALUEPAIRS:
    case XZ_T7_TYPEINFO:
    case XZ_T7_SCRIPTBUNDLE:
    case XZ_T7_SCRIPTBUNDLELIST:
    case XZ_T7_BITFIELD:
    case XZ_T7_STRING:
    case XZ_T7_ASSETLIST:
    case XZ_T7_REPORT:
        return XZ_PACKAGE_BOOT_GAMEPLAY_SCRIPTS;

    case XZ_T7_OBJECTIVE:
    case XZ_T7_OBJECTIVE_LIST:
    case XZ_T7_MEDAL:
    case XZ_T7_MEDALTABLE:
    case XZ_T7_LEADERBOARD:
    case XZ_T7_BG_CACHE:
    case XZ_T7_MAPTABLE:
    case XZ_T7_CUSTOMIZATION_TABLE:
    case XZ_T7_CUSTOMIZATION_TABLE_FE_IMAGES:
    case XZ_T7_CUSTOMIZATION_TABLE_COLOR:
    case XZ_T7_GLASSES:
    case XZ_T7_RUMBLE:
    case XZ_T7_XCAM:
    case XZ_T7_VEHICLEDEF:
        return XZ_PACKAGE_BOOT_INTERACTABLES;

    case XZ_T7_STREAMER_HINT:
        return XZ_PACKAGE_BOOT_PLATFORM_PACKAGING;

    default:
        return XZ_PACKAGE_BOOT_SOAK_RELEASE_QUALITY;
    }
}

int XzT7AssetType_SelfTest(void)
{
    unsigned int i;
    for (i = 0u; i < XZ_T7_FULL_TYPE_COUNT; ++i) {
        if (!XzT7AssetType_Name((XzT7AssetType)i)[0])
            return 0;
        if ((unsigned int)XzT7AssetType_Family((XzT7AssetType)i) >=
            XZ_PACKAGE_BOOT_FAMILY_COUNT)
            return 0;
    }
    return XzT7AssetType_IsRuntimeType(XZ_T7_NAVMESH) &&
           !XzT7AssetType_IsRuntimeType(XZ_T7_STRING);
}

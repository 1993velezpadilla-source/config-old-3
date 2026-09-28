#include "xz_t7_asset_types.h"

static const char *const names[XZ_T7_FULL_TYPE_COUNT] = {
    "physpreset","physconstraints","destructibledef","xanimparts","xmodel","xmodelmesh",
    "material","compute_shader_set","technique_set","image","sound","sound_patch",
    "clipmap","comworld","gameworld","map_ents","gfxworld","light_def","lensflare_def",
    "ui_map","font","fonticon","localize_entry","weapon","weapondef","weapon_variant",
    "weapon_full","cgmedia","playersounds","playerfx","sharedweaponsounds","attachment",
    "attachment_unique","weapon_camo","customization_table","customization_table_fe_images",
    "customization_table_color","snddriver_globals","fx","tagfx","new_lensflare_def",
    "impact_fx","impact_sound","player_character","aitype","character","xmodelalias",
    "rawfile","stringtable","structured_table","leaderboard","ddl","glasses","texturelist",
    "scriptparsetree","keyvaluepairs","vehicledef","addon_map_ents","tracer","slug",
    "surfacefx_table","surfacesounddef","footstep_table","entityfximpacts",
    "entitysoundimpacts","zbarrier","vehiclefxdef","vehiclesounddef","typeinfo",
    "scriptbundle","scriptbundlelist","rumble","bulletpenetration","locdmgtable","aimtable",
    "animselectortableset","animmappingtable","animstatemachine","behaviortree",
    "behaviorstatemachine","ttf","sanim","light_description","shellshock","xcam","bg_cache",
    "texture_combo","flametable","bitfield","attachment_cosmetic_variant","maptable",
    "maptable_loading_images","medal","medaltable","objective","objective_list","umbra_tome",
    "navmesh","navvolume","binaryhtml","laser","beam","streamer_hint","string","assetlist",
    "report","depend"
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
    case XZ_T7_DEPEND:
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

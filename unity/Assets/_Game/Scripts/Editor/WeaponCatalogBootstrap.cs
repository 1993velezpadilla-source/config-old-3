#if UNITY_EDITOR
using System;
using System.IO;
using UnityEditor;
using UnityEngine;
using Sanctum.Zombies.Combat;

namespace Sanctum.Zombies.EditorTools
{
    public static class WeaponCatalogBootstrap
    {
        [Serializable] private sealed class WeaponTable { public WeaponRow[] weapons; }

        [Serializable] private sealed class WeaponRow
        {
            public string id;
            public string displayName;
            public string fireAudioId;
            public string weaponClass;
            public string fireMode;
            public float baseDamage;
            public float packDamage;
            public float rpm;
            public int magazine;
            public int packMagazine;
            public int reserve;
            public int pellets;
            public float falloffStart;
            public float falloffEnd;
            public float minFalloff;
            public float hipSpread;
            public float adsSpread;
            public float headMultiplier;
        }

        private const string BalancePath = "Assets/_Game/Data/weapon_balance.json";
        private const string ModelRoot = "Assets/_Game/Art/Weapons";
        private const string AudioRoot = "Assets/_Game/Audio/Weapons";
        private const string DefinitionRoot = "Assets/_Game/Data/Weapons";

        [MenuItem("Zombies/Bootstrap/Build Weapon Assets")]
        public static void Build()
        {
            Directory.CreateDirectory(DefinitionRoot);
            AssetDatabase.Refresh();

            TextAsset source = AssetDatabase.LoadAssetAtPath<TextAsset>(BalancePath);
            if (source == null) throw new FileNotFoundException(BalancePath);

            WeaponTable table = JsonUtility.FromJson<WeaponTable>(source.text);
            if (table == null || table.weapons == null) throw new InvalidDataException("Weapon balance table invalid.");

            int built = 0;

            foreach (WeaponRow row in table.weapons)
            {
                string modelPath = $"{ModelRoot}/{row.id}/viewmodel.glb";
                GameObject model = AssetDatabase.LoadAssetAtPath<GameObject>(modelPath);
                if (model == null)
                {
                    Debug.LogError($"REAL weapon import missing: {modelPath}");
                    continue;
                }

                string assetPath = $"{DefinitionRoot}/{row.id}.asset";
                WeaponDefinition definition = AssetDatabase.LoadAssetAtPath<WeaponDefinition>(assetPath);
                if (definition == null)
                {
                    definition = ScriptableObject.CreateInstance<WeaponDefinition>();
                    AssetDatabase.CreateAsset(definition, assetPath);
                }

                definition.weaponId = row.id;
                definition.displayName = row.displayName;
                definition.weaponClass = (WeaponClass)Enum.Parse(typeof(WeaponClass), row.weaponClass);
                definition.fireMode = (WeaponFireMode)Enum.Parse(typeof(WeaponFireMode), row.fireMode);
                definition.viewModelPrefab = model;
                definition.viewModelAnimatorController = WeaponAnimatorBootstrap.BuildFor(row.id, definition.fireMode);

                string audioId = string.IsNullOrWhiteSpace(row.fireAudioId) ? row.id : row.fireAudioId;
                string fireAudioPath = $"{AudioRoot}/{audioId}/fire.wav";
                definition.fireClip = AssetDatabase.LoadAssetAtPath<AudioClip>(fireAudioPath);
                definition.fireAudioSourceId = audioId;
                if (definition.fireClip == null)
                    throw new FileNotFoundException($"REAL/fallback fire audio missing: {fireAudioPath}");

                definition.baseDamage = row.baseDamage;
                definition.packAPunchDamage = row.packDamage;
                definition.roundsPerMinute = row.rpm;
                definition.magazineSize = row.magazine;
                definition.packAPunchMagazineSize = row.packMagazine;
                definition.startingReserve = row.reserve;
                definition.pellets = Mathf.Max(1, row.pellets);
                definition.falloffStartMeters = row.falloffStart;
                definition.falloffEndMeters = row.falloffEnd;
                definition.minimumFalloffMultiplier = row.minFalloff;
                definition.hipSpreadDegrees = row.hipSpread;
                definition.adsSpreadDegrees = row.adsSpread;
                definition.headMultiplier = row.headMultiplier;
                ApplyADSPreset(definition);

                EditorUtility.SetDirty(definition);
                built++;
            }

            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"UNITY_ZOMBIES weapon bootstrap: {built}/{table.weapons.Length} REAL viewmodels bound.");
        }

        private static void ApplyADSPreset(WeaponDefinition definition)
        {
            switch (definition.weaponClass)
            {
                case WeaponClass.Pistol:
                    definition.adsFieldOfView = 62f;
                    definition.adsSpeed = 17f;
                    break;
                case WeaponClass.SMG:
                    definition.adsFieldOfView = 60f;
                    definition.adsSpeed = 16f;
                    break;
                case WeaponClass.Shotgun:
                    definition.adsFieldOfView = 60f;
                    definition.adsSpeed = 13f;
                    break;
                case WeaponClass.LMG:
                    definition.adsFieldOfView = 56f;
                    definition.adsSpeed = 10f;
                    break;
                case WeaponClass.Sniper:
                    definition.adsFieldOfView = 40f;
                    definition.adsSpeed = 8f;
                    break;
                default:
                    definition.adsFieldOfView = 54f;
                    definition.adsSpeed = 12.5f;
                    break;
            }
        }
    }
}
#endif

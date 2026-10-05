#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;
using Sanctum.Zombies.Combat;

namespace Sanctum.Zombies.EditorTools
{
    public static class ProductionAssetValidator
    {
        [MenuItem("Zombies/Validate Production Assets")]
        public static void Validate()
        {
            string[] models = AssetDatabase.FindAssets("viewmodel", new[] { "Assets/_Game/Art/Weapons" });
            if (models.Length < 28)
                throw new InvalidDataException($"Expected >=28 real weapon viewmodels; imported {models.Length}.");

            string[] definitions = AssetDatabase.FindAssets("t:WeaponDefinition", new[] { "Assets/_Game/Data/Weapons" });
            if (definitions.Length < 28)
                throw new InvalidDataException($"Expected >=28 WeaponDefinition assets; generated {definitions.Length}. Run weapon bootstrap.");

            foreach (string guid in definitions)
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                WeaponDefinition definition = AssetDatabase.LoadAssetAtPath<WeaponDefinition>(path);
                if (definition == null || definition.viewModelPrefab == null)
                    throw new InvalidDataException($"{path}: missing REAL viewmodel.");
                if (definition.viewModelAnimatorController == null)
                    throw new InvalidDataException($"{path}: missing embedded-animation controller.");
                if (definition.fireClip == null)
                    throw new InvalidDataException($"{path}: missing weapon fire audio.");
                if (string.IsNullOrWhiteSpace(definition.fireAudioSourceId))
                    throw new InvalidDataException($"{path}: fire audio source ID is not auditable.");
                if (definition.packAPunchDamage <= definition.baseDamage)
                    throw new InvalidDataException($"{path}: Pack-a-Punch damage must exceed base damage.");
            }

            if (!File.Exists("Assets/_Game/Art/Zombies/MonjaClean/monja_basica_clean_rig.gltf"))
                throw new FileNotFoundException("Clean monja rig missing.");

            if (!File.Exists("Assets/_Game/Art/Environment/Church/church_final_architecture.glb"))
                throw new FileNotFoundException("Real church architecture missing.");

            Debug.Log($"UNITY_ZOMBIES PRODUCTION ASSET GATE GREEN: {models.Length} real animated weapons, {definitions.Length} definitions/controllers, church + clean monja present.");
        }
    }
}
#endif

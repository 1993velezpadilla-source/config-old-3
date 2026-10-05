#if UNITY_EDITOR
using System;
using System.Linq;
using UnityEditor;
using UnityEngine;

namespace Sanctum.Zombies.EditorTools
{
    public static class MonjaImportValidator
    {
        private const string RigPath = "Assets/_Game/Art/Zombies/MonjaClean/monja_basica_clean_rig.gltf";

        [MenuItem("Zombies/Validate Monja Animation Import")]
        public static void Validate()
        {
            AnimationClip[] clips = AssetDatabase.LoadAllAssetsAtPath(RigPath)
                .OfType<AnimationClip>()
                .Where(c => c != null && !c.name.StartsWith("__preview__", StringComparison.OrdinalIgnoreCase))
                .ToArray();

            string[] required = { "idle", "walk", "attack", "hit", "death" };
            foreach (string token in required)
            {
                if (!clips.Any(c => c.name.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0))
                    throw new InvalidOperationException($"Monja import missing required '{token}' clip. Found: {string.Join(", ", clips.Select(c => c.name))}");
            }

            Debug.Log($"MONJA ANIMATION IMPORT GREEN: {clips.Length} clips; required Idle/Walk/Attack/Hit/Death present.");
        }
    }
}
#endif

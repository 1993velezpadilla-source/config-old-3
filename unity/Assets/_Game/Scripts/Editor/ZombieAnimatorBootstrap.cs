#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace Sanctum.Zombies.EditorTools
{
    public static class ZombieAnimatorBootstrap
    {
        private const string RigPath = "Assets/_Game/Art/Zombies/MonjaClean/monja_basica_clean_rig.gltf";
        private const string AnimationRoot = "Assets/_Game/Animations/Monja";
        private const string ControllerPath = AnimationRoot + "/ZombieMonja.controller";

        private sealed class ClipSet
        {
            public AnimationClip idle;
            public AnimationClip walk;
            public AnimationClip attack;
            public AnimationClip hit;
            public AnimationClip death;
        }

        [MenuItem("Zombies/Bootstrap/Build Monja Animator")]
        public static RuntimeAnimatorController BuildOrGetController()
        {
            Directory.CreateDirectory(AnimationRoot);
            AssetDatabase.Refresh();

            ClipSet source = FindEmbeddedClips();
            ClipSet clips = new ClipSet
            {
                idle = CloneClip(source.idle, "Zombie_Idle", true),
                walk = CloneClip(source.walk, "Zombie_Walk", true),
                attack = CloneClip(source.attack, "Zombie_Attack", false),
                hit = CloneClip(source.hit, "Zombie_Hit", false),
                death = CloneClip(source.death, "Zombie_Death", false),
            };

            AssetDatabase.DeleteAsset(ControllerPath);
            AnimatorController controller = AnimatorController.CreateAnimatorControllerAtPath(ControllerPath);
            controller.AddParameter("Speed", AnimatorControllerParameterType.Float);
            controller.AddParameter("Attack", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Hit", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Dead", AnimatorControllerParameterType.Bool);
            controller.AddParameter("HitZone", AnimatorControllerParameterType.Int);

            AnimatorStateMachine sm = controller.layers[0].stateMachine;
            AnimatorState idle = sm.AddState("Idle");
            AnimatorState walk = sm.AddState("Walk");
            AnimatorState attack = sm.AddState("Attack");
            AnimatorState hit = sm.AddState("Hit");
            AnimatorState death = sm.AddState("Death");

            idle.motion = clips.idle;
            walk.motion = clips.walk;
            attack.motion = clips.attack;
            hit.motion = clips.hit;
            death.motion = clips.death;

            idle.writeDefaultValues = false;
            walk.writeDefaultValues = false;
            attack.writeDefaultValues = false;
            hit.writeDefaultValues = false;
            death.writeDefaultValues = false;
            sm.defaultState = idle;

            AnimatorStateTransition idleToWalk = idle.AddTransition(walk);
            ConfigureImmediate(idleToWalk, 0.12f);
            idleToWalk.AddCondition(AnimatorConditionMode.Greater, 0.15f, "Speed");

            AnimatorStateTransition walkToIdle = walk.AddTransition(idle);
            ConfigureImmediate(walkToIdle, 0.12f);
            walkToIdle.AddCondition(AnimatorConditionMode.Less, 0.10f, "Speed");

            AnimatorStateTransition deathAny = sm.AddAnyStateTransition(death);
            ConfigureImmediate(deathAny, 0.04f);
            deathAny.canTransitionToSelf = false;
            deathAny.AddCondition(AnimatorConditionMode.If, 0f, "Dead");

            AnimatorStateTransition attackAny = sm.AddAnyStateTransition(attack);
            ConfigureImmediate(attackAny, 0.06f);
            attackAny.canTransitionToSelf = false;
            attackAny.AddCondition(AnimatorConditionMode.If, 0f, "Attack");

            AnimatorStateTransition hitAny = sm.AddAnyStateTransition(hit);
            ConfigureImmediate(hitAny, 0.04f);
            hitAny.canTransitionToSelf = false;
            hitAny.AddCondition(AnimatorConditionMode.If, 0f, "Hit");

            AnimatorStateTransition attackExit = attack.AddTransition(idle);
            attackExit.hasExitTime = true;
            attackExit.exitTime = 0.92f;
            attackExit.duration = 0.08f;

            AnimatorStateTransition hitExit = hit.AddTransition(idle);
            hitExit.hasExitTime = true;
            hitExit.exitTime = 0.90f;
            hitExit.duration = 0.06f;

            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log("UNITY_ZOMBIES MONJA ANIMATOR GREEN: Idle + Walk + Attack + Hit + Death from clean embedded rig clips.");
            return controller;
        }

        private static ClipSet FindEmbeddedClips()
        {
            UnityEngine.Object[] all = AssetDatabase.LoadAllAssetsAtPath(RigPath);
            List<AnimationClip> clips = all
                .OfType<AnimationClip>()
                .Where(c => c != null && !c.name.StartsWith("__preview__", StringComparison.OrdinalIgnoreCase))
                .ToList();

            if (clips.Count == 0)
                throw new InvalidDataException($"No embedded AnimationClips imported from {RigPath}");

            AnimationClip Pick(params string[] tokens)
            {
                foreach (string token in tokens)
                {
                    AnimationClip match = clips.FirstOrDefault(c =>
                        c.name.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0);
                    if (match != null) return match;
                }
                return null;
            }

            ClipSet set = new ClipSet
            {
                idle = Pick("Idle_Clean", "Zombie_Idle", "Idle"),
                walk = Pick("Walk_Clean", "Zombie_Walk", "Walk"),
                attack = Pick("Attack_Clean", "Zombie_Attack", "Attack"),
                hit = Pick("Hit_Clean", "Zombie_Hit", "Hit"),
                death = Pick("Death_Clean", "Zombie_Death", "Death"),
            };

            if (set.idle == null || set.walk == null || set.attack == null || set.hit == null || set.death == null)
            {
                string discovered = string.Join(", ", clips.Select(c => c.name));
                throw new InvalidDataException(
                    "Clean monja rig did not expose all required clips. " +
                    $"Found: [{discovered}]");
            }

            return set;
        }

        private static AnimationClip CloneClip(AnimationClip source, string name, bool loop)
        {
            string path = $"{AnimationRoot}/{name}.anim";
            AssetDatabase.DeleteAsset(path);

            AnimationClip clone = new AnimationClip();
            EditorUtility.CopySerialized(source, clone);
            clone.name = name;

            AnimationClipSettings settings = AnimationUtility.GetAnimationClipSettings(clone);
            settings.loopTime = loop;
            settings.loopBlend = loop;
            settings.keepOriginalPositionXZ = true;
            settings.keepOriginalPositionY = true;
            settings.keepOriginalOrientation = true;
            AnimationUtility.SetAnimationClipSettings(clone, settings);

            AssetDatabase.CreateAsset(clone, path);
            return clone;
        }

        private static void ConfigureImmediate(AnimatorStateTransition transition, float duration)
        {
            transition.hasExitTime = false;
            transition.hasFixedDuration = true;
            transition.duration = duration;
            transition.offset = 0f;
        }
    }
}
#endif

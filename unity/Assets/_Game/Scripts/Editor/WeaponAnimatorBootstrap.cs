#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using Sanctum.Zombies.Combat;

namespace Sanctum.Zombies.EditorTools
{
    public static class WeaponAnimatorBootstrap
    {
        private const string ModelRoot = "Assets/_Game/Art/Weapons";
        private const string ControllerRoot = "Assets/_Game/Animations/Weapons";

        public static RuntimeAnimatorController BuildFor(string weaponId, WeaponFireMode fireMode)
        {
            string modelPath = $"{ModelRoot}/{weaponId}/viewmodel.glb";
            AnimationClip[] clips = AssetDatabase.LoadAllAssetsAtPath(modelPath)
                .OfType<AnimationClip>()
                .Where(c => c != null && !c.name.StartsWith("__preview__", StringComparison.OrdinalIgnoreCase))
                .ToArray();

            if (clips.Length == 0)
                throw new InvalidDataException($"{weaponId}: no embedded weapon animations imported from {modelPath}");

            Directory.CreateDirectory(ControllerRoot);
            string controllerPath = $"{ControllerRoot}/{weaponId}.controller";
            AssetDatabase.DeleteAsset(controllerPath);

            AnimationClip idle = Pick(clips, n => Has(n, "idle") && !Has(n, "empty"));
            AnimationClip fire = Pick(clips, n => (Has(n, "fire") || Has(n, "shoot")) && !Has(n, "ads") && !Has(n, "last"));
            AnimationClip fireAds = Pick(clips, n => (Has(n, "ads_fire") || Has(n, "fire_ads")));
            AnimationClip reloadEmpty = Pick(clips, n => Has(n, "reload") && Has(n, "empty"));
            AnimationClip reload = Pick(clips, n => Has(n, "reload") && !Has(n, "empty") && !Has(n, "start") && !Has(n, "loop") && !Has(n, "end") && !Has(n, "partial"));
            AnimationClip reloadStart = Pick(clips, n => Has(n, "reload") && Has(n, "start"));
            AnimationClip reloadLoop = Pick(clips, n => Has(n, "reload") && Has(n, "loop"));
            AnimationClip reloadEnd = Pick(clips, n => Has(n, "reload") && Has(n, "end"));
            AnimationClip rechamber = Pick(clips, n => Has(n, "rechamber"));
            AnimationClip lastShot = Pick(clips, n => Has(n, "lastshot") || Has(n, "last_shot") || Has(n, "lastfire"));
            AnimationClip equip = Pick(clips, n => Has(n, "equip") || Has(n, "pullout") || Has(n, "bringout") || Has(n, "first_raise"));

            if (idle == null) idle = clips[0];
            if (fire == null) fire = fireAds ?? clips.FirstOrDefault(c => c != idle) ?? idle;
            if (fireAds == null) fireAds = fire;
            if (reload == null) reload = reloadEmpty ?? idle;
            if (reloadEmpty == null) reloadEmpty = reload;
            if (lastShot == null) lastShot = fire;
            if (equip == null) equip = idle;
            if (rechamber == null) rechamber = idle;
            if (reloadStart == null) reloadStart = reload;
            if (reloadLoop == null) reloadLoop = reload;
            if (reloadEnd == null) reloadEnd = reload;

            AnimatorController controller = AnimatorController.CreateAnimatorControllerAtPath(controllerPath);
            foreach (string trigger in new[] { "Fire", "FireADS", "LastShot", "Reload", "ReloadEmpty", "ReloadStart", "ReloadLoop", "ReloadEnd", "Rechamber", "Equip" })
                controller.AddParameter(trigger, AnimatorControllerParameterType.Trigger);

            AnimatorStateMachine sm = controller.layers[0].stateMachine;
            AnimatorState idleState = AddState(sm, "Idle", idle);
            sm.defaultState = idleState;

            AnimatorState fireState = AddState(sm, "Fire", fire);
            AnimatorState fireAdsState = AddState(sm, "FireADS", fireAds);
            AnimatorState lastState = AddState(sm, "LastShot", lastShot);
            AnimatorState reloadState = AddState(sm, "Reload", reload);
            AnimatorState reloadEmptyState = AddState(sm, "ReloadEmpty", reloadEmpty);
            AnimatorState reloadStartState = AddState(sm, "ReloadStart", reloadStart);
            AnimatorState reloadLoopState = AddState(sm, "ReloadLoop", reloadLoop);
            AnimatorState reloadEndState = AddState(sm, "ReloadEnd", reloadEnd);
            AnimatorState rechamberState = AddState(sm, "Rechamber", rechamber);
            AnimatorState equipState = AddState(sm, "Equip", equip);

            AddTriggered(sm, fireState, "Fire");
            AddTriggered(sm, fireAdsState, "FireADS");
            AddTriggered(sm, lastState, "LastShot");
            AddTriggered(sm, reloadState, "Reload");
            AddTriggered(sm, reloadEmptyState, "ReloadEmpty");
            AddTriggered(sm, reloadStartState, "ReloadStart");
            AddTriggered(sm, reloadLoopState, "ReloadLoop");
            AddTriggered(sm, reloadEndState, "ReloadEnd");
            AddTriggered(sm, rechamberState, "Rechamber");
            AddTriggered(sm, equipState, "Equip");

            AddExit(fireState, fireMode == WeaponFireMode.Bolt || fireMode == WeaponFireMode.Pump ? rechamberState : idleState, 0.88f);
            AddExit(fireAdsState, fireMode == WeaponFireMode.Bolt || fireMode == WeaponFireMode.Pump ? rechamberState : idleState, 0.88f);
            AddExit(lastState, idleState, 0.92f);
            AddExit(reloadState, idleState, 0.96f);
            AddExit(reloadEmptyState, idleState, 0.96f);
            AddExit(reloadStartState, reloadLoopState, 0.95f);
            AddExit(reloadLoopState, reloadEndState, 0.95f);
            AddExit(reloadEndState, idleState, 0.95f);
            AddExit(rechamberState, idleState, 0.95f);
            AddExit(equipState, idleState, 0.95f);

            EditorUtility.SetDirty(controller);
            AssetDatabase.SaveAssets();
            return controller;
        }

        private static AnimatorState AddState(AnimatorStateMachine sm, string name, AnimationClip clip)
        {
            AnimatorState state = sm.AddState(name);
            state.motion = clip;
            state.writeDefaultValues = false;
            return state;
        }

        private static void AddTriggered(AnimatorStateMachine sm, AnimatorState state, string parameter)
        {
            AnimatorStateTransition t = sm.AddAnyStateTransition(state);
            t.hasExitTime = false;
            t.hasFixedDuration = true;
            t.duration = 0.035f;
            t.canTransitionToSelf = false;
            t.AddCondition(AnimatorConditionMode.If, 0f, parameter);
        }

        private static void AddExit(AnimatorState from, AnimatorState to, float exitTime)
        {
            AnimatorStateTransition t = from.AddTransition(to);
            t.hasExitTime = true;
            t.exitTime = exitTime;
            t.hasFixedDuration = true;
            t.duration = 0.05f;
        }

        private static AnimationClip Pick(IEnumerable<AnimationClip> clips, Func<string, bool> predicate)
        {
            return clips
                .OrderBy(c => Has(c.name, ".001") || Has(c.name, ".002") ? 1 : 0)
                .FirstOrDefault(c => predicate(c.name));
        }

        private static bool Has(string value, string token)
            => value.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0;
    }
}
#endif

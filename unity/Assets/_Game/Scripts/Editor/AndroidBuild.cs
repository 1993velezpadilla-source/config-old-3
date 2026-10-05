#if UNITY_EDITOR
using System;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Sanctum.Zombies.EditorTools
{
    public static class AndroidBuild
    {
        [MenuItem("Zombies/Build/Android Development APK")]
        public static void BuildDevelopment()
        {
            PlayerSettings.defaultInterfaceOrientation = UIOrientation.LandscapeLeft;
            PlayerSettings.allowedAutorotateToPortrait = false;
            PlayerSettings.allowedAutorotateToPortraitUpsideDown = false;
            PlayerSettings.allowedAutorotateToLandscapeLeft = true;
            PlayerSettings.allowedAutorotateToLandscapeRight = true;

            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel26;
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.SetScriptingBackend(NamedBuildTarget.Android, ScriptingImplementation.IL2CPP);

            EditorBuildSettingsScene[] enabled = Array.FindAll(EditorBuildSettings.scenes, s => s.enabled);
            if (enabled.Length == 0) throw new InvalidOperationException("No enabled Unity scene. Run vertical slice bootstrap first.");

            string[] scenes = Array.ConvertAll(enabled, s => s.path);
            BuildPlayerOptions options = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = "Builds/Android/UnityZombies-dev.apk",
                target = BuildTarget.Android,
                options = BuildOptions.Development | BuildOptions.AllowDebugging
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != BuildResult.Succeeded)
                throw new BuildFailedException($"Android build failed: {report.summary.result}");

            Debug.Log($"UNITY_ZOMBIES APK GREEN: {options.locationPathName} ({report.summary.totalSize} bytes)");
        }
    }
}
#endif

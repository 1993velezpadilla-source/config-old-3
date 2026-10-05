#if UNITY_EDITOR
using System;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Sanctum.Zombies.EditorTools
{
    public static class UnityZombiesCIEntry
    {
        public static void BuildAndroid()
        {
            ConfigureIdentity();
            VerticalSliceBootstrap.Build();
            ProductionAssetValidator.Validate();
            AndroidBuild.BuildDevelopment();
        }

        public static void BuildLinuxPreview()
        {
            ConfigureIdentity();
            VerticalSliceBootstrap.Build();
            ProductionAssetValidator.Validate();

            EditorBuildSettingsScene[] enabled = Array.FindAll(EditorBuildSettings.scenes, s => s.enabled);
            if (enabled.Length == 0)
                throw new InvalidOperationException("No enabled vertical-slice scene after bootstrap.");

            BuildPlayerOptions options = new BuildPlayerOptions
            {
                scenes = Array.ConvertAll(enabled, s => s.path),
                locationPathName = "Builds/LinuxPreview/UnityZombiesPreview.x86_64",
                target = BuildTarget.StandaloneLinux64,
                options = BuildOptions.Development
            };

            BuildReport report = BuildPipeline.BuildPlayer(options);
            if (report.summary.result != BuildResult.Succeeded)
                throw new BuildFailedException($"Linux preview build failed: {report.summary.result}");

            Debug.Log($"UNITY_ZOMBIES LINUX PREVIEW GREEN: {options.locationPathName}");
        }

        private static void ConfigureIdentity()
        {
            PlayerSettings.companyName = "Bubblegum Engine";
            PlayerSettings.productName = "Sanctum Zombies";
            PlayerSettings.bundleVersion = "0.1.0";
            PlayerSettings.applicationIdentifier = "com.bubblegumengine.sanctumzombies";
        }
    }
}
#endif

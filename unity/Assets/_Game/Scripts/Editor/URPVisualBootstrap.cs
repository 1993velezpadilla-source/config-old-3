#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Sanctum.Zombies.EditorTools
{
    public static class URPVisualBootstrap
    {
        private const string SettingsRoot = "Assets/_Game/Settings";
        private const string RendererPath = SettingsRoot + "/MobileForwardRenderer.asset";
        private const string PipelinePath = SettingsRoot + "/MobileURP.asset";
        private const string VolumePath = SettingsRoot + "/ChurchHorrorVolume.asset";

        public static UniversalRenderPipelineAsset BuildOrGetPipeline()
        {
            Directory.CreateDirectory(SettingsRoot);

            UniversalRendererData renderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>(RendererPath);
            if (renderer == null)
            {
                renderer = ScriptableObject.CreateInstance<UniversalRendererData>();
                renderer.name = "MobileForwardRenderer";
                renderer.renderingMode = RenderingMode.Forward;
                renderer.shadowTransparentReceive = false;
                AssetDatabase.CreateAsset(renderer, RendererPath);
            }

            UniversalRenderPipelineAsset pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>(PipelinePath);
            if (pipeline == null)
            {
                pipeline = UniversalRenderPipelineAsset.Create(renderer);
                pipeline.name = "MobileURP";
                AssetDatabase.CreateAsset(pipeline, PipelinePath);
            }

            pipeline.supportsHDR = true;
            pipeline.supportsCameraDepthTexture = true;
            pipeline.supportsCameraOpaqueTexture = false;
            pipeline.msaaSampleCount = 2;
            pipeline.renderScale = 1.0f;
            pipeline.shadowDistance = 42f;
            pipeline.shadowCascadeCount = 2;
            pipeline.maxAdditionalLightsCount = 8;
            pipeline.supportsDynamicBatching = true;
            pipeline.useSRPBatcher = true;

            GraphicsSettings.defaultRenderPipeline = pipeline;
            QualitySettings.renderPipeline = pipeline;
            GraphicsSettings.useScriptableRenderPipelineBatching = true;
            PlayerSettings.colorSpace = ColorSpace.Linear;

            EditorUtility.SetDirty(renderer);
            EditorUtility.SetDirty(pipeline);
            AssetDatabase.SaveAssets();
            return pipeline;
        }

        public static VolumeProfile BuildOrGetVolumeProfile()
        {
            Directory.CreateDirectory(SettingsRoot);

            VolumeProfile profile = AssetDatabase.LoadAssetAtPath<VolumeProfile>(VolumePath);
            if (profile == null)
            {
                profile = ScriptableObject.CreateInstance<VolumeProfile>();
                profile.name = "ChurchHorrorVolume";
                AssetDatabase.CreateAsset(profile, VolumePath);
            }

            Bloom bloom = GetOrAdd<Bloom>(profile);
            bloom.active = true;
            bloom.threshold.Override(1.05f);
            bloom.intensity.Override(0.32f);
            bloom.scatter.Override(0.62f);

            ColorAdjustments grade = GetOrAdd<ColorAdjustments>(profile);
            grade.active = true;
            grade.postExposure.Override(-0.10f);
            grade.contrast.Override(14f);
            grade.saturation.Override(-12f);
            grade.colorFilter.Override(new Color(0.96f, 0.98f, 1.0f, 1f));

            Vignette vignette = GetOrAdd<Vignette>(profile);
            vignette.active = true;
            vignette.intensity.Override(0.23f);
            vignette.smoothness.Override(0.62f);

            Tonemapping tone = GetOrAdd<Tonemapping>(profile);
            tone.active = true;
            tone.mode.Override(TonemappingMode.ACES);

            EditorUtility.SetDirty(profile);
            AssetDatabase.SaveAssets();
            return profile;
        }

        public static void ConfigureCamera(Camera camera)
        {
            UniversalAdditionalCameraData data = camera.GetComponent<UniversalAdditionalCameraData>();
            if (data == null) data = camera.gameObject.AddComponent<UniversalAdditionalCameraData>();
            data.renderPostProcessing = true;
            data.requiresDepthOption = CameraOverrideOption.On;
            data.requiresColorOption = CameraOverrideOption.Off;
        }

        private static T GetOrAdd<T>(VolumeProfile profile) where T : VolumeComponent
        {
            if (profile.TryGet(out T existing)) return existing;
            return profile.Add<T>(true);
        }
    }
}
#endif

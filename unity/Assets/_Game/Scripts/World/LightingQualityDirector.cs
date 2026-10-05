using System.Collections.Generic;
using UnityEngine;

namespace Sanctum.Zombies.World
{
    public enum LightingPriority { Critical, Accent, Decorative }

    [RequireComponent(typeof(Light))]
    public sealed class BudgetedLight : MonoBehaviour
    {
        public LightingPriority priority = LightingPriority.Accent;
        public bool wantsShadows = true;
        [HideInInspector] public Light cached;

        private void Awake() => cached = GetComponent<Light>();
        private void Reset() => cached = GetComponent<Light>();
    }

    public sealed class LightingQualityDirector : MonoBehaviour
    {
        public enum Tier { Low, Balanced, High, Ultra }

        [SerializeField] private bool autoDetect = true;
        [SerializeField] private Tier forcedTier = Tier.Balanced;
        [SerializeField] private float fogDensity = 0.018f;

        private readonly List<BudgetedLight> budgeted = new List<BudgetedLight>();

        private void Awake()
        {
            GetComponentsInChildren(true, budgeted);
            Apply(autoDetect ? Detect() : forcedTier);
        }

        public Tier Detect()
        {
            int ram = SystemInfo.systemMemorySize;
            int vram = SystemInfo.graphicsMemorySize;
            if (ram >= 10000 && vram >= 4000) return Tier.Ultra;
            if (ram >= 7000 && vram >= 2000) return Tier.High;
            if (ram >= 4500) return Tier.Balanced;
            return Tier.Low;
        }

        public void Apply(Tier tier)
        {
            int lightBudget = tier switch { Tier.Low => 5, Tier.Balanced => 9, Tier.High => 16, _ => 24 };
            int shadowBudget = tier switch { Tier.Low => 1, Tier.Balanced => 2, Tier.High => 4, _ => 6 };

            QualitySettings.shadowDistance = tier switch { Tier.Low => 20f, Tier.Balanced => 32f, Tier.High => 46f, _ => 60f };
            QualitySettings.lodBias = tier switch { Tier.Low => 0.72f, Tier.Balanced => 1f, Tier.High => 1.35f, _ => 1.65f };
            QualitySettings.pixelLightCount = lightBudget;

            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogDensity = fogDensity;

            budgeted.Sort((a, b) => a.priority.CompareTo(b.priority));
            int enabled = 0;
            int shadowed = 0;

            foreach (BudgetedLight item in budgeted)
            {
                if (item == null) continue;
                Light light = item.cached != null ? item.cached : item.GetComponent<Light>();
                bool keep = item.priority == LightingPriority.Critical || enabled < lightBudget;
                light.enabled = keep;
                if (!keep) continue;
                enabled++;

                bool shadows = item.wantsShadows && shadowed < shadowBudget && item.priority != LightingPriority.Decorative;
                light.shadows = shadows ? LightShadows.Soft : LightShadows.None;
                if (shadows) shadowed++;
            }
        }
    }
}

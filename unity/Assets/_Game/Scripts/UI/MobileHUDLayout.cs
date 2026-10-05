using UnityEngine;

namespace Sanctum.Zombies.UI
{
    [CreateAssetMenu(menuName = "Sanctum/Mobile HUD Layout", fileName = "MobileHUDLayout")]
    public sealed class MobileHUDLayout : ScriptableObject
    {
        [Header("Normalized landscape screen coordinates")]
        public Rect moveRegion = new Rect(0.00f, 0.00f, 0.45f, 0.70f);
        public Rect lookRegion = new Rect(0.45f, 0.00f, 0.55f, 1.00f);
        public Rect fireRegion = new Rect(0.80f, 0.18f, 0.18f, 0.30f);
        public Rect adsRegion = new Rect(0.68f, 0.48f, 0.13f, 0.20f);
        public Rect reloadRegion = new Rect(0.82f, 0.54f, 0.13f, 0.18f);
        public Rect useRegion = new Rect(0.60f, 0.26f, 0.12f, 0.18f);
        public Rect jumpRegion = new Rect(0.69f, 0.05f, 0.12f, 0.18f);
        public Rect sprintRegion = new Rect(0.18f, 0.56f, 0.13f, 0.18f);

        [Header("Presentation")]
        [Range(0.1f, 1f)] public float buttonAlpha = 0.58f;
        [Range(0.1f, 0.8f)] public float stickAlpha = 0.32f;
        [Range(60f, 260f)] public float stickRadiusPixels = 125f;
        [Range(0.1f, 3f)] public float lookScale = 1f;

        public static Rect ToGuiPixels(Rect normalized)
        {
            float x = normalized.x * Screen.width;
            float y = (1f - normalized.y - normalized.height) * Screen.height;
            return new Rect(x, y, normalized.width * Screen.width, normalized.height * Screen.height);
        }
    }
}

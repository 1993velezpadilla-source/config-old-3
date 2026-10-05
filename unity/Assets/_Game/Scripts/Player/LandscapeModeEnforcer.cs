using UnityEngine;

namespace Sanctum.Zombies.Player
{
    [DefaultExecutionOrder(-10000)]
    public sealed class LandscapeModeEnforcer : MonoBehaviour
    {
        [SerializeField] private bool allowLandscapeFlip = true;
        [SerializeField] private int targetFrameRate = 60;

        private void Awake()
        {
            Apply();
            Application.targetFrameRate = targetFrameRate;
        }

        private void OnApplicationFocus(bool hasFocus)
        {
            if (hasFocus) Apply();
        }

        private void OnApplicationPause(bool paused)
        {
            if (!paused) Apply();
        }

        private void Apply()
        {
#if UNITY_ANDROID || UNITY_IOS
            Screen.autorotateToPortrait = false;
            Screen.autorotateToPortraitUpsideDown = false;
            Screen.autorotateToLandscapeLeft = true;
            Screen.autorotateToLandscapeRight = allowLandscapeFlip;
            Screen.orientation = allowLandscapeFlip
                ? ScreenOrientation.AutoRotation
                : ScreenOrientation.LandscapeLeft;
#else
            // Editor/desktop keeps a wide aspect for testing without forcing OS rotation.
            if (Screen.width < Screen.height)
                Screen.SetResolution(Mathf.Max(Screen.width, 1280), Mathf.Min(Screen.height, 720), false);
#endif
        }
    }
}

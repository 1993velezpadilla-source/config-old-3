#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using Sanctum.Zombies.Debugging;

namespace Sanctum.Zombies.EditorTools
{
    public static class PlaymodeScreenshotMenu
    {
        [MenuItem("Zombies/Capture/Gameplay Screenshot")]
        public static void Capture()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogError("Enter Play Mode first, then use Zombies > Capture > Gameplay Screenshot.");
                return;
            }

            GameplayScreenshotCapture capture = Object.FindFirstObjectByType<GameplayScreenshotCapture>();
            if (capture == null)
            {
                Debug.LogError("GameplayScreenshotCapture not found in active scene.");
                return;
            }

            capture.CaptureManual();
        }
    }
}
#endif

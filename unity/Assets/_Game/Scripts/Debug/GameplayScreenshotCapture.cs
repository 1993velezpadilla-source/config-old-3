using System;
using System.Collections;
using System.IO;
using UnityEngine;

namespace Sanctum.Zombies.Debugging
{
    public sealed class GameplayScreenshotCapture : MonoBehaviour
    {
        [SerializeField] private bool captureFirstPlayableFrame = true;
        [SerializeField, Range(1, 4)] private int superSize = 1;
        [SerializeField] private float firstCaptureDelaySeconds = 2.0f;

        public string LastCapturePath { get; private set; }

        private IEnumerator Start()
        {
            if (!captureFirstPlayableFrame) yield break;
            yield return new WaitForSecondsRealtime(firstCaptureDelaySeconds);
            yield return new WaitForEndOfFrame();
            Capture("first_playable");
        }

        public void CaptureManual()
        {
            StartCoroutine(CaptureAtEndOfFrame("manual"));
        }

        private IEnumerator CaptureAtEndOfFrame(string label)
        {
            yield return new WaitForEndOfFrame();
            Capture(label);
        }

        private void Capture(string label)
        {
            string folder = Path.Combine(Application.persistentDataPath, "Screenshots");
            Directory.CreateDirectory(folder);

            string stamp = DateTime.Now.ToString("yyyyMMdd_HHmmss");
            string filename = $"UnityZombies_{label}_{Screen.width}x{Screen.height}_{stamp}.png";
            LastCapturePath = Path.Combine(folder, filename);

            ScreenCapture.CaptureScreenshot(LastCapturePath, superSize);
            Debug.Log($"UNITY_ZOMBIES PHOTO_CAPTURED={LastCapturePath}");
        }
    }
}

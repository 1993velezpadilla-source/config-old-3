using UnityEngine;

namespace Sanctum.Zombies.World
{
    [RequireComponent(typeof(Light))]
    public sealed class HorrorLightFlicker : MonoBehaviour
    {
        [SerializeField, Range(0f, 1f)] private float amount = 0.18f;
        [SerializeField, Range(0.1f, 40f)] private float speed = 8f;
        [SerializeField, Range(0f, 0.2f)] private float dropoutChancePerSecond = 0.015f;
        [SerializeField, Range(0.01f, 0.5f)] private float dropoutDuration = 0.07f;

        private Light source;
        private float baseIntensity;
        private float seed;
        private float dropoutUntil;

        private void Awake()
        {
            source = GetComponent<Light>();
            baseIntensity = source.intensity;
            seed = Random.value * 1000f;
        }

        private void Update()
        {
            if (Time.time < dropoutUntil)
            {
                source.intensity = baseIntensity * 0.05f;
                return;
            }

            if (Random.value < dropoutChancePerSecond * Time.deltaTime)
            {
                dropoutUntil = Time.time + dropoutDuration;
                return;
            }

            float noise = Mathf.PerlinNoise(seed, Time.time * speed);
            source.intensity = baseIntensity * Mathf.Lerp(1f - amount, 1f + amount, noise);
        }
    }
}

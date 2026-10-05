using UnityEngine;

namespace Sanctum.Zombies.AI
{
    [CreateAssetMenu(menuName = "Sanctum/Zombie Round Tuning")]
    public sealed class ZombieRoundTuning : ScriptableObject
    {
        [Header("Health")]
        public float roundOneHealth = 150f;
        public float linearHealthPerRound = 100f;
        public int exponentialStartsAfterRound = 9;
        public float exponentialMultiplier = 1.10f;

        [Header("Population")]
        public int baseZombieCount = 6;
        public float zombiesPerRound = 2.2f;
        public float extraPerAdditionalPlayer = 0.55f;
        public int maxAliveMobile = 24;

        [Header("Speed")]
        public float minWalkSpeed = 1.25f;
        public float maxRunSpeed = 3.9f;
        public int fullRunnerRound = 18;

        public float HealthForRound(int round)
        {
            round = Mathf.Max(1, round);
            float hp = roundOneHealth + (Mathf.Min(round, exponentialStartsAfterRound) - 1) * linearHealthPerRound;
            if (round > exponentialStartsAfterRound)
                hp *= Mathf.Pow(exponentialMultiplier, round - exponentialStartsAfterRound);
            return hp;
        }

        public int TotalForRound(int round, int players)
        {
            round = Mathf.Max(1, round);
            players = Mathf.Clamp(players, 1, 4);
            float raw = baseZombieCount + (round - 1) * zombiesPerRound;
            return Mathf.CeilToInt(raw * (1f + (players - 1) * extraPerAdditionalPlayer));
        }

        public float SpeedForRound(int round, float random01)
        {
            float progression = Mathf.InverseLerp(1, fullRunnerRound, Mathf.Max(1, round));
            float mixed = Mathf.Clamp01(progression * 0.80f + random01 * 0.35f);
            return Mathf.Lerp(minWalkSpeed, maxRunSpeed, mixed);
        }
    }
}

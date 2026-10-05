using System;
using UnityEngine;
using Sanctum.Zombies.AI;

namespace Sanctum.Zombies.Player
{
    [DisallowMultipleComponent]
    public sealed class PlayerHealth : MonoBehaviour
    {
        [SerializeField] private int maxHealth = 100;
        [SerializeField] private int reviveHealth = 50;
        [SerializeField] private float hitGraceSeconds = 0.20f;
        [SerializeField] private PlayerTarget target;

        private int currentHealth;
        private bool downed;
        private float invulnerableUntil;

        public int CurrentHealth => currentHealth;
        public int MaxHealth => maxHealth;
        public bool IsDowned => downed;
        public event Action<int, int> HealthChanged;
        public event Action Downed;
        public event Action Revived;

        private void Awake()
        {
            if (target == null) target = GetComponent<PlayerTarget>();
            ResetForSpawn();
        }

        public void ResetForSpawn()
        {
            downed = false;
            currentHealth = Mathf.Max(1, maxHealth);
            invulnerableUntil = 0f;
            if (target != null) target.SetAlive(true);
            HealthChanged?.Invoke(currentHealth, maxHealth);
        }

        public bool TakeZombieHit(int damage, Vector3 sourcePosition)
        {
            if (downed || damage <= 0 || Time.time < invulnerableUntil) return false;

            invulnerableUntil = Time.time + hitGraceSeconds;
            currentHealth = Mathf.Max(0, currentHealth - damage);
            HealthChanged?.Invoke(currentHealth, maxHealth);

            if (currentHealth == 0)
                EnterDowned();

            return true;
        }

        public bool TryRevive()
        {
            if (!downed) return false;

            downed = false;
            currentHealth = Mathf.Clamp(reviveHealth, 1, maxHealth);
            invulnerableUntil = Time.time + 1.5f;
            if (target != null) target.SetAlive(true);
            HealthChanged?.Invoke(currentHealth, maxHealth);
            Revived?.Invoke();
            return true;
        }

        private void EnterDowned()
        {
            if (downed) return;
            downed = true;
            if (target != null) target.SetAlive(false);
            Downed?.Invoke();
        }
    }
}

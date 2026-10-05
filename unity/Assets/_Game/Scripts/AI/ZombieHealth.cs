using System;
using UnityEngine;
using UnityEngine.AI;
using Sanctum.Zombies.Combat;

namespace Sanctum.Zombies.AI
{
    [DisallowMultipleComponent]
    public sealed class ZombieHealth : MonoBehaviour
    {
        [SerializeField] private ZombieRoundTuning tuning;
        [SerializeField] private Animator animator;
        [SerializeField] private NavMeshAgent agent;

        private float currentHealth;
        private bool alive;

        public bool IsAlive => alive;
        public float CurrentHealth => currentHealth;
        public event Action<ZombieHealth> Died;

        public void InitializeForRound(int round)
        {
            currentHealth = tuning != null ? tuning.HealthForRound(round) : 150f;
            alive = true;
            if (agent != null)
            {
                agent.enabled = true;
                agent.isStopped = false;
            }
            if (animator != null) animator.SetBool("Dead", false);
        }

        public void TakeDamage(float damage, HitZone zone, Vector3 point, Vector3 direction)
        {
            if (!alive || damage <= 0f) return;
            currentHealth -= damage;

            if (animator != null)
            {
                animator.SetInteger("HitZone", (int)zone);
                animator.SetTrigger("Hit");
            }

            if (currentHealth <= 0f) Die();
        }

        private void Die()
        {
            if (!alive) return;
            alive = false;
            currentHealth = 0f;
            if (agent != null && agent.enabled) agent.isStopped = true;
            if (animator != null) animator.SetBool("Dead", true);
            Died?.Invoke(this);
        }
    }
}

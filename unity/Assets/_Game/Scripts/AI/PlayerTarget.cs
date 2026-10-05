using System.Collections.Generic;
using UnityEngine;

namespace Sanctum.Zombies.AI
{
    public sealed class PlayerTarget : MonoBehaviour
    {
        private static readonly List<PlayerTarget> active = new List<PlayerTarget>(4);
        [SerializeField] private bool alive = true;
        [SerializeField] private Sanctum.Zombies.Player.PlayerHealth health;

        public bool IsAlive => alive && isActiveAndEnabled && (health == null || !health.IsDowned);
        public Sanctum.Zombies.Player.PlayerHealth Health => health;
        public static IReadOnlyList<PlayerTarget> Active => active;

        private void Awake()
        {
            if (health == null) health = GetComponent<Sanctum.Zombies.Player.PlayerHealth>();
        }

        private void OnEnable()
        {
            if (!active.Contains(this)) active.Add(this);
        }

        private void OnDisable() => active.Remove(this);
        public void SetAlive(bool value) => alive = value;
    }
}

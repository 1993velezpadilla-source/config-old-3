using System.Collections.Generic;
using UnityEngine;

namespace Sanctum.Zombies.AI
{
    public sealed class PlayerTarget : MonoBehaviour
    {
        private static readonly List<PlayerTarget> active = new List<PlayerTarget>(4);
        [SerializeField] private bool alive = true;

        public bool IsAlive => alive && isActiveAndEnabled;
        public static IReadOnlyList<PlayerTarget> Active => active;

        private void OnEnable()
        {
            if (!active.Contains(this)) active.Add(this);
        }

        private void OnDisable() => active.Remove(this);
        public void SetAlive(bool value) => alive = value;
    }
}

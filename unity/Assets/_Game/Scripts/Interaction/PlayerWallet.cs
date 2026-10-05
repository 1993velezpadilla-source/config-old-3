using UnityEngine;

namespace Sanctum.Zombies.Interaction
{
    public sealed class PlayerWallet : MonoBehaviour
    {
        [SerializeField] private int points = 500;
        public int Points => points;

        public void Add(int amount) => points = Mathf.Max(0, points + amount);

        public bool TrySpend(int amount)
        {
            if (amount < 0 || points < amount) return false;
            points -= amount;
            return true;
        }
    }
}

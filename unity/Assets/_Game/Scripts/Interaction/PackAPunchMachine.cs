using UnityEngine;
using Sanctum.Zombies.Combat;

namespace Sanctum.Zombies.Interaction
{
    public sealed class PackAPunchMachine : MonoBehaviour, IPlayerInteractable
    {
        [SerializeField] private int cost = 5000;
        public string Prompt => $"Pack-a-Punch — {cost}";

        public bool CanUse(PlayerWallet wallet, WeaponRuntime weapon)
        {
            return wallet != null && weapon != null && weapon.Definition != null && !weapon.IsPacked && wallet.Points >= cost;
        }

        public bool Use(PlayerWallet wallet, WeaponRuntime weapon)
        {
            if (!CanUse(wallet, weapon) || !wallet.TrySpend(cost)) return false;

            if (weapon.TryPackAPunch()) return true;
            wallet.Add(cost);
            return false;
        }
    }
}

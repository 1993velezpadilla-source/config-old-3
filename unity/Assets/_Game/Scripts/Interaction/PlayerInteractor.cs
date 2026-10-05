using UnityEngine;
using Sanctum.Zombies.Combat;

namespace Sanctum.Zombies.Interaction
{
    public interface IPlayerInteractable
    {
        bool CanUse(PlayerWallet wallet, WeaponRuntime weapon);
        bool Use(PlayerWallet wallet, WeaponRuntime weapon);
        string Prompt { get; }
    }

    public sealed class PlayerInteractor : MonoBehaviour
    {
        [SerializeField] private Camera playerCamera;
        [SerializeField] private PlayerWallet wallet;
        [SerializeField] private WeaponRuntime weapon;
        [SerializeField] private float range = 2.4f;
        [SerializeField] private LayerMask mask = ~0;

        public void Configure(Camera cameraRef, PlayerWallet walletRef, WeaponRuntime weaponRef)
        {
            playerCamera = cameraRef;
            wallet = walletRef;
            weapon = weaponRef;
        }

        public bool TryUse()
        {
            if (playerCamera == null) return false;
            Ray ray = new Ray(playerCamera.transform.position, playerCamera.transform.forward);
            if (!Physics.Raycast(ray, out RaycastHit hit, range, mask, QueryTriggerInteraction.Collide)) return false;

            MonoBehaviour[] behaviours = hit.collider.GetComponentsInParent<MonoBehaviour>(true);
            foreach (MonoBehaviour behaviour in behaviours)
            {
                if (behaviour is IPlayerInteractable interactable && interactable.CanUse(wallet, weapon))
                    return interactable.Use(wallet, weapon);
            }

            return false;
        }
    }
}

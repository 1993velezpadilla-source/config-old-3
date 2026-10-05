using UnityEngine;
using Sanctum.Zombies.AI;

namespace Sanctum.Zombies.Combat
{
    [DisallowMultipleComponent]
    public sealed class ZombieHitbox : MonoBehaviour
    {
        [SerializeField] private ZombieHealth owner;
        [SerializeField] private HitZone zone = HitZone.Torso;

        public ZombieHealth Owner => owner;
        public HitZone Zone => zone;

        private void Reset()
        {
            owner = GetComponentInParent<ZombieHealth>();
            string n = name.ToLowerInvariant();
            zone = n.Contains("head") ? HitZone.Head :
                   (n.Contains("arm") || n.Contains("hand")) ? HitZone.Arm :
                   (n.Contains("leg") || n.Contains("foot")) ? HitZone.Leg :
                   HitZone.Torso;
        }
    }
}

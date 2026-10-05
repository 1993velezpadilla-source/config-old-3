using UnityEngine;
using Sanctum.Zombies.Interaction;

namespace Sanctum.Zombies.Combat
{
    public sealed class MobileWeaponInput : MonoBehaviour
    {
        [SerializeField] private WeaponRuntime weapon;
        [SerializeField] private PlayerInteractor interactor;

        private bool touchFire;
        private bool touchADS;

        public void Configure(WeaponRuntime weaponRef, PlayerInteractor interactorRef)
        {
            weapon = weaponRef;
            interactor = interactorRef;
        }

        private void Update()
        {
            if (weapon == null) return;

#if UNITY_EDITOR || UNITY_STANDALONE
            bool desktopFire = Input.GetMouseButton(0);
            bool desktopADS = Input.GetMouseButton(1);
            if (Input.GetKeyDown(KeyCode.R)) weapon.TryReload();
            if (Input.GetKeyDown(KeyCode.E) && interactor != null) interactor.TryUse();
#else
            bool desktopFire = false;
            bool desktopADS = false;
#endif
            weapon.SetFireHeld(touchFire || desktopFire);
            weapon.SetADS(touchADS || desktopADS);
        }

        public void FireDown() => touchFire = true;
        public void FireUp() => touchFire = false;
        public void ADSDown() => touchADS = true;
        public void ADSUp() => touchADS = false;
        public void Reload() { if (weapon != null) weapon.TryReload(); }
        public void Use() { if (interactor != null) interactor.TryUse(); }
    }
}

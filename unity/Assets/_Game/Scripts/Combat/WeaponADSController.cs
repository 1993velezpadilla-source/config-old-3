using System;
using UnityEngine;

namespace Sanctum.Zombies.Combat
{
    [DisallowMultipleComponent]
    public sealed class WeaponADSController : MonoBehaviour
    {
        [SerializeField] private Camera playerCamera;
        [SerializeField] private float hipFieldOfView = 72f;

        private Transform weaponRoot;
        private WeaponDefinition definition;
        private bool aiming;

        public bool IsAiming => aiming;

        public void Bind(Transform root, WeaponDefinition weapon)
        {
            weaponRoot = root;
            definition = weapon;
            aiming = false;
            Snap(false);
        }

        public void SetAiming(bool value) => aiming = value;

        private void LateUpdate()
        {
            if (weaponRoot == null || definition == null || playerCamera == null) return;

            float blend = 1f - Mathf.Exp(-definition.adsSpeed * Time.unscaledDeltaTime);
            Vector3 targetPosition = aiming ? definition.adsLocalPosition : definition.hipLocalPosition;
            Quaternion targetRotation = Quaternion.Euler(aiming ? definition.adsLocalEuler : definition.hipLocalEuler);

            weaponRoot.localPosition = Vector3.Lerp(weaponRoot.localPosition, targetPosition, blend);
            weaponRoot.localRotation = Quaternion.Slerp(weaponRoot.localRotation, targetRotation, blend);
            playerCamera.fieldOfView = Mathf.Lerp(playerCamera.fieldOfView, aiming ? definition.adsFieldOfView : hipFieldOfView, blend);
        }

        public void Snap(bool toADS)
        {
            if (weaponRoot == null || definition == null) return;
            weaponRoot.localPosition = toADS ? definition.adsLocalPosition : definition.hipLocalPosition;
            weaponRoot.localRotation = Quaternion.Euler(toADS ? definition.adsLocalEuler : definition.hipLocalEuler);
            if (playerCamera != null) playerCamera.fieldOfView = toADS ? definition.adsFieldOfView : hipFieldOfView;
        }

        public bool TryAutoCalibrateFromSightNames()
        {
            if (weaponRoot == null || definition == null) return false;

            Transform authored = FindByNames(
                weaponRoot,
                "tag_iron_sights", "tag_ironsights", "tag_ads", "ads_anchor",
                "tag_scope", "scope_view", "scope_anchor");

            Vector3 sightWorld;

            if (authored != null)
            {
                sightWorld = authored.position;
            }
            else
            {
                Transform rear = FindByNames(weaponRoot, "rear_sight", "rearsight", "rear sight", "iron_rear", "ads_rear");
                Transform front = FindByNames(weaponRoot, "front_sight", "frontsight", "front sight", "iron_front", "ads_front");

                if (rear != null && front != null)
                {
                    sightWorld = Vector3.Lerp(rear.position, front.position, 0.20f);
                }
                else
                {
                    // Many recovered WaW viewmodels expose tag_flash but no explicit iron-sight tag.
                    // Centering the authored muzzle on the camera axis gives a per-weapon fallback
                    // instead of forcing every gun through one generic ADS translation.
                    Transform muzzle = FindByNames(weaponRoot, "tag_flash", "muzzle", "muzzle_flash");
                    if (muzzle == null) return false;
                    sightWorld = muzzle.position;
                }
            }

            Transform cameraTransform = playerCamera.transform;
            float depth = Vector3.Dot(sightWorld - cameraTransform.position, cameraTransform.forward);
            depth = Mathf.Clamp(depth, 0.15f, 1.75f);

            Vector3 desired = cameraTransform.position + cameraTransform.forward * depth;
            Vector3 worldDelta = desired - sightWorld;
            Vector3 localDelta = weaponRoot.parent.InverseTransformVector(worldDelta);
            definition.adsLocalPosition = weaponRoot.localPosition + localDelta;
            return true;
        }

        private static Transform FindByNames(Transform root, params string[] names)
        {
            foreach (Transform t in root.GetComponentsInChildren<Transform>(true))
            {
                string n = t.name.ToLowerInvariant();
                foreach (string wanted in names)
                    if (n == wanted || n.Contains(wanted)) return t;
            }
            return null;
        }
    }
}

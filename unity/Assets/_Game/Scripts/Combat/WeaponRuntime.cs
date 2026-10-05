using UnityEngine;

namespace Sanctum.Zombies.Combat
{
    [DisallowMultipleComponent]
    public sealed class WeaponRuntime : MonoBehaviour
    {
        [SerializeField] private Camera playerCamera;
        [SerializeField] private Transform viewModelSocket;
        [SerializeField] private WeaponADSController adsController;
        [SerializeField] private LayerMask hitMask = ~0;
        [SerializeField] private ParticleSystem muzzleFlash;
        [SerializeField] private AudioSource fireAudio;

        private WeaponDefinition definition;
        private GameObject viewModelInstance;
        private Animator viewModelAnimator;
        private Light muzzleLight;
        private float muzzleLightUntil;
        private int magazine;
        private int reserve;
        private bool packed;
        private bool fireHeld;
        private bool triggerPressed;
        private float nextShotTime;

        public WeaponDefinition Definition => definition;
        public bool IsPacked => packed;
        public int Magazine => magazine;
        public int Reserve => reserve;

        public void Equip(WeaponDefinition next)
        {
            if (viewModelInstance != null) Destroy(viewModelInstance);
            definition = next;
            packed = false;
            if (definition == null) return;

            magazine = definition.magazineSize;
            reserve = definition.startingReserve;

            if (definition.viewModelPrefab == null)
            {
                Debug.LogError($"[{definition.weaponId}] REAL viewmodel missing. Production fallback geometry is forbidden.");
                return;
            }

            viewModelInstance = Instantiate(definition.viewModelPrefab, viewModelSocket, false);
            viewModelInstance.name = $"VM_{definition.weaponId}";
            viewModelInstance.transform.localScale = Vector3.one;

            viewModelAnimator = viewModelInstance.GetComponentInChildren<Animator>();
            if (viewModelAnimator == null) viewModelAnimator = viewModelInstance.AddComponent<Animator>();
            viewModelAnimator.runtimeAnimatorController = definition.viewModelAnimatorController;
            viewModelAnimator.applyRootMotion = false;

            Transform flash = FindChildByName(viewModelInstance.transform, "tag_flash");
            if (flash != null)
            {
                muzzleLight = flash.GetComponent<Light>();
                if (muzzleLight == null) muzzleLight = flash.gameObject.AddComponent<Light>();
                muzzleLight.type = LightType.Point;
                muzzleLight.range = 2.4f;
                muzzleLight.intensity = 3.2f;
                muzzleLight.shadows = LightShadows.None;
                muzzleLight.enabled = false;
            }

            adsController.Bind(viewModelInstance.transform, definition);
            adsController.TryAutoCalibrateFromSightNames();
            adsController.Snap(false);
            TriggerAnimation("Equip");
        }

        public void SetFireHeld(bool value)
        {
            if (value && !fireHeld) triggerPressed = true;
            fireHeld = value;
        }

        public void SetADS(bool value) => adsController.SetAiming(value);

        public bool TryReload()
        {
            if (definition == null || reserve <= 0) return false;
            int capacity = definition.MagazineFor(packed);
            int need = capacity - magazine;
            if (need <= 0) return false;

            bool wasEmpty = magazine == 0;
            TriggerAnimation(wasEmpty ? "ReloadEmpty" : "Reload");

            int moved = Mathf.Min(need, reserve);
            magazine += moved;
            reserve -= moved;
            return true;
        }

        public bool TryPackAPunch()
        {
            if (definition == null || packed) return false;
            packed = true;
            int oldCapacity = Mathf.Max(1, definition.magazineSize);
            int newCapacity = definition.MagazineFor(true);
            magazine = Mathf.Min(newCapacity, magazine + Mathf.Max(0, newCapacity - oldCapacity));
            reserve = Mathf.Max(reserve, newCapacity * 4);
            return true;
        }

        private void Update()
        {
            if (muzzleLight != null && muzzleLight.enabled && Time.time >= muzzleLightUntil)
                muzzleLight.enabled = false;

            if (definition == null) return;

            bool shouldFire = definition.fireMode == WeaponFireMode.FullAuto ? fireHeld : triggerPressed;
            triggerPressed = false;
            if (shouldFire) TryFire();
        }

        private void TryFire()
        {
            if (playerCamera == null || Time.time < nextShotTime || magazine <= 0) return;
            nextShotTime = Time.time + definition.SecondsPerShot;
            bool lastShot = magazine == 1;
            magazine--;

            TriggerAnimation(lastShot ? "LastShot" : (adsController.IsAiming ? "FireADS" : "Fire"));

            if (muzzleLight != null)
            {
                muzzleLight.enabled = true;
                muzzleLightUntil = Time.time + 0.045f;
            }

            if (muzzleFlash != null) muzzleFlash.Play(true);
            if (fireAudio != null) fireAudio.Play();

            int pelletCount = Mathf.Max(1, definition.pellets);
            for (int i = 0; i < pelletCount; i++) FirePellet();
        }

        private void TriggerAnimation(string parameter)
        {
            if (viewModelAnimator == null || viewModelAnimator.runtimeAnimatorController == null) return;
            viewModelAnimator.ResetTrigger(parameter);
            viewModelAnimator.SetTrigger(parameter);
        }

        private static Transform FindChildByName(Transform root, string exactName)
        {
            Transform[] all = root.GetComponentsInChildren<Transform>(true);
            foreach (Transform t in all)
                if (string.Equals(t.name, exactName, System.StringComparison.OrdinalIgnoreCase))
                    return t;
            return null;
        }

        private void FirePellet()
        {
            float spreadDegrees = adsController.IsAiming ? definition.adsSpreadDegrees : definition.hipSpreadDegrees;
            float tangent = Mathf.Tan(spreadDegrees * Mathf.Deg2Rad);
            Vector2 spread = Random.insideUnitCircle * tangent;

            Transform cam = playerCamera.transform;
            Vector3 direction = (cam.forward + cam.right * spread.x + cam.up * spread.y).normalized;
            Ray ray = new Ray(cam.position, direction);

            if (!Physics.Raycast(ray, out RaycastHit hit, definition.maxRangeMeters, hitMask, QueryTriggerInteraction.Ignore))
                return;

            ZombieHitbox hitbox = hit.collider.GetComponent<ZombieHitbox>();
            if (hitbox == null || hitbox.Owner == null || !hitbox.Owner.IsAlive) return;

            float damage = DamageModel.Calculate(definition, packed, hitbox.Zone, hit.distance);
            hitbox.Owner.TakeDamage(damage, hitbox.Zone, hit.point, direction);
        }
    }
}

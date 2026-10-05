using UnityEngine;
using Sanctum.Zombies.Combat;
using Sanctum.Zombies.Interaction;
using Sanctum.Zombies.UI;

namespace Sanctum.Zombies.Player
{
    // Package-free fallback touch layer. It keeps gameplay testable before the editable HUD prefab lands.
    // Rects use normalized landscape screen coordinates.
    public sealed class TouchFPSInput : MonoBehaviour
    {
        [SerializeField] private MobileFPSController motor;
        [SerializeField] private MobileWeaponInput weapons;
        [SerializeField] private PlayerInteractor interactor;
        [SerializeField] private MobileHUDLayout layout;

        [Header("Fallback touch regions (used when no layout asset is assigned)")]
        [SerializeField] private Rect moveRegion = new Rect(0.00f, 0.00f, 0.45f, 0.70f);
        [SerializeField] private Rect lookRegion = new Rect(0.45f, 0.00f, 0.55f, 1.00f);
        [SerializeField] private Rect fireRegion = new Rect(0.80f, 0.18f, 0.18f, 0.30f);
        [SerializeField] private Rect adsRegion = new Rect(0.68f, 0.48f, 0.13f, 0.20f);
        [SerializeField] private Rect reloadRegion = new Rect(0.82f, 0.54f, 0.13f, 0.18f);
        [SerializeField] private Rect useRegion = new Rect(0.60f, 0.26f, 0.12f, 0.18f);
        [SerializeField] private Rect jumpRegion = new Rect(0.69f, 0.05f, 0.12f, 0.18f);
        [SerializeField] private Rect sprintRegion = new Rect(0.18f, 0.56f, 0.13f, 0.18f);

        [SerializeField] private float stickRadiusPixels = 125f;
        [SerializeField] private float lookScale = 1.0f;

        private int moveFinger = -1;
        private int lookFinger = -1;
        private Vector2 moveOrigin;
        private bool firing;
        private bool aiming;
        private bool sprinting;

        public void Configure(MobileFPSController motorRef, MobileWeaponInput weaponRef, PlayerInteractor interactorRef, MobileHUDLayout layoutRef)
        {
            motor = motorRef;
            weapons = weaponRef;
            interactor = interactorRef;
            layout = layoutRef;
        }

        private void OnDisable()
        {
            ReleaseAll();
        }

        private void Update()
        {
#if UNITY_ANDROID || UNITY_IOS || UNITY_EDITOR
            bool fireNow = false;
            bool adsNow = false;
            bool sprintNow = false;
            bool moveSeen = false;
            bool lookSeen = false;

            for (int i = 0; i < Input.touchCount; i++)
            {
                Touch touch = Input.GetTouch(i);
                Vector2 normalized = new Vector2(
                    touch.position.x / Mathf.Max(1f, Screen.width),
                    touch.position.y / Mathf.Max(1f, Screen.height));

                if (touch.phase == TouchPhase.Began)
                {
                    if (Contains(FireRegion, normalized)) { fireNow = true; continue; }
                    if (Contains(ADSRegion, normalized)) { adsNow = true; continue; }
                    if (Contains(ReloadRegion, normalized)) { weapons?.Reload(); continue; }
                    if (Contains(UseRegion, normalized)) { interactor?.TryUse(); continue; }
                    if (Contains(JumpRegion, normalized)) { motor?.QueueJump(); continue; }
                    if (Contains(SprintRegion, normalized)) { sprintNow = true; continue; }

                    if (moveFinger < 0 && Contains(MoveRegion, normalized))
                    {
                        moveFinger = touch.fingerId;
                        moveOrigin = touch.position;
                    }
                    else if (lookFinger < 0 && Contains(LookRegion, normalized))
                    {
                        lookFinger = touch.fingerId;
                    }
                }

                if (touch.fingerId == moveFinger)
                {
                    if (touch.phase == TouchPhase.Ended || touch.phase == TouchPhase.Canceled)
                    {
                        moveFinger = -1;
                        motor?.SetMove(Vector2.zero);
                    }
                    else
                    {
                        moveSeen = true;
                        Vector2 delta = (touch.position - moveOrigin) / Mathf.Max(1f, StickRadiusPixels);
                        motor?.SetMove(Vector2.ClampMagnitude(delta, 1f));
                    }
                    continue;
                }

                if (touch.fingerId == lookFinger)
                {
                    if (touch.phase == TouchPhase.Ended || touch.phase == TouchPhase.Canceled)
                    {
                        lookFinger = -1;
                    }
                    else
                    {
                        lookSeen = true;
                        motor?.AddLookDelta(touch.deltaPosition * LookScale);
                    }
                    continue;
                }

                if (Contains(FireRegion, normalized)) fireNow = true;
                if (Contains(ADSRegion, normalized)) adsNow = true;
                if (Contains(SprintRegion, normalized)) sprintNow = true;
            }

            if (!moveSeen && moveFinger < 0) motor?.SetMove(Vector2.zero);
            if (!lookSeen && lookFinger < 0) { }

            SetFire(fireNow);
            SetADS(adsNow);
            SetSprint(sprintNow);
#endif
        }

        private Rect MoveRegion => layout != null ? layout.moveRegion : moveRegion;
        private Rect LookRegion => layout != null ? layout.lookRegion : lookRegion;
        private Rect FireRegion => layout != null ? layout.fireRegion : fireRegion;
        private Rect ADSRegion => layout != null ? layout.adsRegion : adsRegion;
        private Rect ReloadRegion => layout != null ? layout.reloadRegion : reloadRegion;
        private Rect UseRegion => layout != null ? layout.useRegion : useRegion;
        private Rect JumpRegion => layout != null ? layout.jumpRegion : jumpRegion;
        private Rect SprintRegion => layout != null ? layout.sprintRegion : sprintRegion;
        private float StickRadiusPixels => layout != null ? layout.stickRadiusPixels : stickRadiusPixels;
        private float LookScale => layout != null ? layout.lookScale : lookScale;

        private static bool Contains(Rect rect, Vector2 point) => rect.Contains(point);

        private void SetFire(bool value)
        {
            if (firing == value) return;
            firing = value;
            if (value) weapons?.FireDown();
            else weapons?.FireUp();
        }

        private void SetADS(bool value)
        {
            if (aiming == value) return;
            aiming = value;
            if (value) weapons?.ADSDown();
            else weapons?.ADSUp();
        }

        private void SetSprint(bool value)
        {
            if (sprinting == value) return;
            sprinting = value;
            motor?.SetSprint(value);
        }

        private void ReleaseAll()
        {
            moveFinger = -1;
            lookFinger = -1;
            motor?.SetMove(Vector2.zero);
            SetFire(false);
            SetADS(false);
            SetSprint(false);
        }
    }
}

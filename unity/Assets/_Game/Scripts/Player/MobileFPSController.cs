using UnityEngine;

namespace Sanctum.Zombies.Player
{
    [RequireComponent(typeof(CharacterController))]
    public sealed class MobileFPSController : MonoBehaviour
    {
        [SerializeField] private Camera playerCamera;
        [SerializeField] private float walkSpeed = 4.4f;
        [SerializeField] private float sprintSpeed = 6.8f;
        [SerializeField] private float jumpHeight = 1.15f;
        [SerializeField] private float gravity = -24f;
        [SerializeField] private float lookSensitivity = 0.085f;
        [SerializeField] private bool gyroEnabled = true;
        [SerializeField] private float gyroSensitivity = 1.0f;

        private CharacterController controller;
        private Vector2 moveInput;
        private Vector2 lookDelta;
        private bool sprintHeld;
        private bool jumpQueued;
        private float pitch;
        private float verticalVelocity;

        public void Configure(Camera cameraRef)
        {
            playerCamera = cameraRef;
        }

        private void Awake()
        {
            controller = GetComponent<CharacterController>();
#if UNITY_ANDROID || UNITY_IOS
            if (SystemInfo.supportsGyroscope)
            {
                Input.gyro.enabled = true;
            }
#endif
        }

        private void Update()
        {
            float speed = sprintHeld ? sprintSpeed : walkSpeed;
            Vector3 planar = (transform.right * moveInput.x + transform.forward * moveInput.y);
            if (planar.sqrMagnitude > 1f) planar.Normalize();

            if (controller.isGrounded && verticalVelocity < 0f) verticalVelocity = -2f;
            if (jumpQueued && controller.isGrounded)
                verticalVelocity = Mathf.Sqrt(jumpHeight * -2f * gravity);

            jumpQueued = false;
            verticalVelocity += gravity * Time.deltaTime;

            Vector3 velocity = planar * speed;
            velocity.y = verticalVelocity;
            controller.Move(velocity * Time.deltaTime);

            Vector2 effectiveLook = lookDelta;
            lookDelta = Vector2.zero;

#if UNITY_ANDROID || UNITY_IOS
            if (gyroEnabled && SystemInfo.supportsGyroscope)
            {
                Vector3 rate = Input.gyro.rotationRateUnbiased;
                effectiveLook += new Vector2(rate.y, -rate.x) * (gyroSensitivity * Mathf.Rad2Deg * Time.deltaTime);
            }
#endif

            transform.Rotate(0f, effectiveLook.x * lookSensitivity, 0f, Space.Self);
            pitch = Mathf.Clamp(pitch - effectiveLook.y * lookSensitivity, -88f, 88f);
            if (playerCamera != null)
                playerCamera.transform.localRotation = Quaternion.Euler(pitch, 0f, 0f);
        }

        public void SetMove(Vector2 value) => moveInput = Vector2.ClampMagnitude(value, 1f);
        public void AddLookDelta(Vector2 pixels) => lookDelta += pixels;
        public void SetSprint(bool value) => sprintHeld = value;
        public void QueueJump() => jumpQueued = true;
        public void SetGyroEnabled(bool value) => gyroEnabled = value;
        public void SetGyroSensitivity(float value) => gyroSensitivity = Mathf.Clamp(value, 0f, 4f);
    }
}

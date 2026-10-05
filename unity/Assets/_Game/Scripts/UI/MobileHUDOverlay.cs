using UnityEngine;
using Sanctum.Zombies.AI;
using Sanctum.Zombies.Combat;
using Sanctum.Zombies.Interaction;
using Sanctum.Zombies.Player;

namespace Sanctum.Zombies.UI
{
    public sealed class MobileHUDOverlay : MonoBehaviour
    {
        [SerializeField] private MobileHUDLayout layout;
        [SerializeField] private WeaponRuntime weapon;
        [SerializeField] private PlayerWallet wallet;
        [SerializeField] private ZombieSpawnDirector rounds;
        [SerializeField] private PlayerHealth health;
        [SerializeField] private Texture2D fireIcon;
        [SerializeField] private Texture2D jumpIcon;

        private GUIStyle buttonStyle;
        private GUIStyle dataStyle;

        public void Configure(
            MobileHUDLayout layoutRef,
            WeaponRuntime weaponRef,
            PlayerWallet walletRef,
            ZombieSpawnDirector roundsRef,
            PlayerHealth healthRef,
            Texture2D fireTexture,
            Texture2D jumpTexture)
        {
            layout = layoutRef;
            weapon = weaponRef;
            wallet = walletRef;
            rounds = roundsRef;
            health = healthRef;
            fireIcon = fireTexture;
            jumpIcon = jumpTexture;
        }

        private void OnGUI()
        {
            if (layout == null) return;
            EnsureStyles();

            DrawStick();
            DrawButton(layout.fireRegion, "FIRE", fireIcon, 1.15f);
            DrawButton(layout.adsRegion, "ADS", null, 1f);
            DrawButton(layout.reloadRegion, "RLD", null, 0.85f);
            DrawButton(layout.useRegion, "USE", null, 0.85f);
            DrawButton(layout.jumpRegion, "JUMP", jumpIcon, 0.9f);
            DrawButton(layout.sprintRegion, "SPRINT", null, 0.82f);

            DrawCrosshair();
            DrawGameData();
        }

        private void DrawButton(Rect normalized, string fallback, Texture2D icon, float alphaScale)
        {
            Rect rect = MobileHUDLayout.ToGuiPixels(normalized);
            Color old = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, Mathf.Clamp01(layout.buttonAlpha * alphaScale));

            if (icon != null)
                GUI.DrawTexture(rect, icon, ScaleMode.ScaleToFit, true);
            else
                GUI.Box(rect, fallback, buttonStyle);

            GUI.color = old;
        }

        private void DrawStick()
        {
            Rect r = MobileHUDLayout.ToGuiPixels(layout.moveRegion);
            float size = Mathf.Min(r.width, r.height) * 0.42f;
            Rect ring = new Rect(r.x + r.width * 0.15f, r.y + r.height * 0.52f - size * 0.5f, size, size);

            Color old = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, layout.stickAlpha);
            GUI.Box(ring, "MOVE", buttonStyle);
            GUI.color = old;
        }

        private void DrawCrosshair()
        {
            float s = Mathf.Clamp(Screen.height * 0.012f, 6f, 16f);
            float cx = Screen.width * 0.5f;
            float cy = Screen.height * 0.5f;
            Color old = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, 0.62f);
            GUI.DrawTexture(new Rect(cx - s * 0.5f, cy - 1f, s, 2f), Texture2D.whiteTexture);
            GUI.DrawTexture(new Rect(cx - 1f, cy - s * 0.5f, 2f, s), Texture2D.whiteTexture);
            GUI.color = old;
        }

        private void DrawGameData()
        {
            string ammo = weapon != null && weapon.Definition != null
                ? $"{weapon.Magazine} / {weapon.Reserve}"
                : "-- / --";
            string points = wallet != null ? wallet.Points.ToString() : "0";
            string round = rounds != null ? rounds.Round.ToString() : "-";
            string hp = health != null ? $"{health.CurrentHealth}/{health.MaxHealth} HP" : "-- HP";

            Rect right = new Rect(Screen.width * 0.70f, Screen.height * 0.84f, Screen.width * 0.27f, Screen.height * 0.10f);
            GUI.Label(right, $"{ammo}   |   {points} pts", dataStyle);

            Rect left = new Rect(Screen.width * 0.03f, Screen.height * 0.04f, Screen.width * 0.20f, Screen.height * 0.08f);
            GUI.Label(left, $"ROUND {round}   |   {hp}", dataStyle);

            if (health != null && health.IsDowned)
            {
                Rect down = new Rect(Screen.width * 0.30f, Screen.height * 0.40f, Screen.width * 0.40f, Screen.height * 0.12f);
                GUI.Label(down, rounds != null && rounds.IsGameOver ? "GAME OVER" : "DOWNED", dataStyle);
            }
        }

        private void EnsureStyles()
        {
            if (buttonStyle == null)
            {
                buttonStyle = new GUIStyle(GUI.skin.box)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontStyle = FontStyle.Bold
                };
            }

            if (dataStyle == null)
            {
                dataStyle = new GUIStyle(GUI.skin.label)
                {
                    alignment = TextAnchor.MiddleRight,
                    fontStyle = FontStyle.Bold
                };
            }

            int font = Mathf.Clamp(Mathf.RoundToInt(Screen.height * 0.027f), 14, 34);
            buttonStyle.fontSize = font;
            dataStyle.fontSize = font;
        }
    }
}

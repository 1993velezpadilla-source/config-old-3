using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace Sanctum.Zombies.AI
{
    [DisallowMultipleComponent]
    public sealed class ZombieBarricade : MonoBehaviour
    {
        private static readonly List<ZombieBarricade> active = new List<ZombieBarricade>();

        [SerializeField] private Transform zombieApproachPoint;
        [SerializeField] private NavMeshObstacle blocker;
        [SerializeField, Range(1, 8)] private int maxBoards = 6;
        [SerializeField, Range(0, 8)] private int boards = 6;

        public static IReadOnlyList<ZombieBarricade> Active => active;
        public bool IsBlocking => boards > 0;
        public Vector3 ApproachPosition => zombieApproachPoint != null ? zombieApproachPoint.position : transform.position;

        private void OnEnable()
        {
            if (!active.Contains(this)) active.Add(this);
            Refresh();
        }

        private void OnDisable() => active.Remove(this);

        public bool ZombieHit()
        {
            if (boards <= 0) return false;
            boards--;
            Refresh();
            return true;
        }

        public bool RepairOne()
        {
            if (boards >= maxBoards) return false;
            boards++;
            Refresh();
            return true;
        }

        private void Refresh()
        {
            boards = Mathf.Clamp(boards, 0, maxBoards);
            if (blocker == null) return;
            blocker.enabled = boards > 0;
            blocker.carving = boards > 0;
        }
    }
}

using UnityEngine;
using UnityEngine.AI;

namespace Sanctum.Zombies.AI
{
    [RequireComponent(typeof(NavMeshAgent))]
    public sealed class ZombieStuckRecovery : MonoBehaviour
    {
        [SerializeField] private float checkInterval = 0.35f;
        [SerializeField] private float stuckSeconds = 1.25f;
        [SerializeField] private float minimumProgressMeters = 0.08f;
        [SerializeField] private float localSnapRadius = 0.45f;

        private NavMeshAgent agent;
        private Vector3 lastPosition;
        private float nextCheck;
        private float stuckFor;

        private void Awake()
        {
            agent = GetComponent<NavMeshAgent>();
            lastPosition = transform.position;
        }

        private void Update()
        {
            if (Time.time < nextCheck) return;
            nextCheck = Time.time + checkInterval;

            if (!agent.enabled || !agent.isOnNavMesh || agent.isStopped || !agent.hasPath)
            {
                ResetProgress();
                return;
            }

            if (agent.pathPending || agent.remainingDistance <= agent.stoppingDistance + 0.20f)
            {
                ResetProgress();
                return;
            }

            float moved = Vector3.Distance(transform.position, lastPosition);
            if (moved >= minimumProgressMeters)
            {
                ResetProgress();
                return;
            }

            stuckFor += checkInterval;
            lastPosition = transform.position;

            if (stuckFor < stuckSeconds) return;

            // First force a repath. If geometry left the agent slightly off the baked surface,
            // only snap to a very nearby point so recovery cannot jump through walls.
            Vector3 destination = agent.destination;
            agent.ResetPath();

            if (NavMesh.SamplePosition(transform.position, out NavMeshHit hit, localSnapRadius, agent.areaMask))
            {
                float snapDistance = Vector3.Distance(transform.position, hit.position);
                if (snapDistance <= localSnapRadius)
                    agent.Warp(hit.position);
            }

            agent.SetDestination(destination);
            stuckFor = 0f;
            lastPosition = transform.position;
        }

        private void ResetProgress()
        {
            stuckFor = 0f;
            lastPosition = transform.position;
        }
    }
}

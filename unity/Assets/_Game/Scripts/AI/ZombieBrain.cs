using UnityEngine;
using UnityEngine.AI;

namespace Sanctum.Zombies.AI
{
    [RequireComponent(typeof(NavMeshAgent), typeof(ZombieHealth))]
    public sealed class ZombieBrain : MonoBehaviour
    {
        private enum State { Acquire, ChasePlayer, BreakBarricade, AttackPlayer, Dead }

        [SerializeField] private Animator animator;
        [SerializeField] private float targetRefreshSeconds = 0.35f;
        [SerializeField] private float pathRefreshSeconds = 0.16f;
        [SerializeField] private float attackRange = 1.25f;
        [SerializeField] private float barricadeAttackRange = 1.35f;
        [SerializeField] private float attackCooldown = 0.9f;

        private NavMeshAgent agent;
        private ZombieHealth health;
        private PlayerTarget target;
        private ZombieBarricade barricade;
        private State state;
        private float nextTargetRefresh;
        private float nextPathRefresh;
        private float nextAttack;
        private readonly NavMeshPath probe = new NavMeshPath();

        private void Awake()
        {
            agent = GetComponent<NavMeshAgent>();
            health = GetComponent<ZombieHealth>();
            health.Died += _ => SetState(State.Dead);
        }

        public void Initialize(int round, float speed)
        {
            health.InitializeForRound(round);
            agent.speed = speed;
            agent.angularSpeed = 720f;
            agent.acceleration = 18f;
            agent.autoBraking = false;
            SetState(State.Acquire);
        }

        private void Update()
        {
            if (!health.IsAlive) return;

            if (Time.time >= nextTargetRefresh)
            {
                nextTargetRefresh = Time.time + targetRefreshSeconds;
                if (target == null || !target.IsAlive) target = FindBestPlayer();
            }

            if (target == null)
            {
                SetState(State.Acquire);
                return;
            }

            if (Time.time >= nextPathRefresh)
            {
                nextPathRefresh = Time.time + pathRefreshSeconds;
                ReevaluateRoute();
            }

            TickState();
            if (animator != null) animator.SetFloat("Speed", agent.velocity.magnitude);
        }

        private void ReevaluateRoute()
        {
            if (!agent.enabled || !agent.isOnNavMesh) return;

            if (NavMesh.CalculatePath(transform.position, target.transform.position, agent.areaMask, probe)
                && probe.status == NavMeshPathStatus.PathComplete)
            {
                barricade = null;
                SetState(Vector3.Distance(transform.position, target.transform.position) <= attackRange
                    ? State.AttackPlayer : State.ChasePlayer);
                return;
            }

            barricade = FindBestBarricade();
            SetState(barricade != null ? State.BreakBarricade : State.ChasePlayer);
        }

        private void TickState()
        {
            switch (state)
            {
                case State.ChasePlayer:
                    agent.isStopped = false;
                    agent.SetDestination(target.transform.position);
                    break;

                case State.BreakBarricade:
                    if (barricade == null || !barricade.IsBlocking)
                    {
                        barricade = null;
                        SetState(State.ChasePlayer);
                        return;
                    }

                    if (Vector3.Distance(transform.position, barricade.ApproachPosition) > barricadeAttackRange)
                    {
                        agent.isStopped = false;
                        agent.SetDestination(barricade.ApproachPosition);
                    }
                    else
                    {
                        agent.isStopped = true;
                        Face(barricade.transform.position);
                        if (Time.time >= nextAttack)
                        {
                            nextAttack = Time.time + attackCooldown;
                            if (animator != null) animator.SetTrigger("Attack");
                            barricade.ZombieHit();
                        }
                    }
                    break;

                case State.AttackPlayer:
                    if (Vector3.Distance(transform.position, target.transform.position) > attackRange * 1.15f)
                    {
                        SetState(State.ChasePlayer);
                        return;
                    }

                    agent.isStopped = true;
                    Face(target.transform.position);
                    if (Time.time >= nextAttack)
                    {
                        nextAttack = Time.time + attackCooldown;
                        if (animator != null) animator.SetTrigger("Attack");
                    }
                    break;
            }
        }

        private PlayerTarget FindBestPlayer()
        {
            PlayerTarget best = null;
            float bestSq = float.MaxValue;
            foreach (PlayerTarget candidate in PlayerTarget.Active)
            {
                if (candidate == null || !candidate.IsAlive) continue;
                float sq = (candidate.transform.position - transform.position).sqrMagnitude;
                if (sq >= bestSq) continue;
                bestSq = sq;
                best = candidate;
            }
            return best;
        }

        private ZombieBarricade FindBestBarricade()
        {
            ZombieBarricade best = null;
            float bestScore = float.MaxValue;

            foreach (ZombieBarricade candidate in ZombieBarricade.Active)
            {
                if (candidate == null || !candidate.IsBlocking) continue;
                float score = Vector3.Distance(transform.position, candidate.ApproachPosition)
                            + Vector3.Distance(candidate.transform.position, target.transform.position) * 0.35f;
                if (score >= bestScore) continue;
                bestScore = score;
                best = candidate;
            }
            return best;
        }

        private void SetState(State next)
        {
            state = next;
            if (next == State.Dead && agent != null && agent.enabled) agent.isStopped = true;
        }

        private void Face(Vector3 worldPoint)
        {
            Vector3 flat = worldPoint - transform.position;
            flat.y = 0f;
            if (flat.sqrMagnitude < 0.001f) return;
            transform.rotation = Quaternion.RotateTowards(transform.rotation, Quaternion.LookRotation(flat), 720f * Time.deltaTime);
        }
    }
}

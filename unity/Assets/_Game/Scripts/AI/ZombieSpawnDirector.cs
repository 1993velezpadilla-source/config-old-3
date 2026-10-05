using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace Sanctum.Zombies.AI
{
    public sealed class ZombieSpawnPoint : MonoBehaviour
    {
        [SerializeField] private float minimumPlayerDistance = 7f;

        public bool CanSpawn()
        {
            foreach (PlayerTarget p in PlayerTarget.Active)
            {
                if (p != null && p.IsAlive && Vector3.Distance(transform.position, p.transform.position) < minimumPlayerDistance)
                    return false;
            }

            return NavMesh.SamplePosition(transform.position, out _, 1.5f, NavMesh.AllAreas);
        }
    }

    public sealed class ZombieSpawnDirector : MonoBehaviour
    {
        [SerializeField] private ZombieRoundTuning tuning;
        [SerializeField] private ZombieBrain zombiePrefab;
        [SerializeField] private ZombieSpawnPoint[] spawnPoints;
        [SerializeField] private float spawnIntervalSeconds = 0.65f;
        [SerializeField] private float intermissionSeconds = 8f;

        private readonly List<ZombieHealth> alive = new List<ZombieHealth>();
        private int round;
        private int spawnedThisRound;
        private int totalThisRound;
        private bool running;

        public int Round => round;

        private IEnumerator Start()
        {
            yield return new WaitForSeconds(1f);
            BeginRound(1);
        }

        public void BeginRound(int value)
        {
            round = Mathf.Max(1, value);
            spawnedThisRound = 0;
            int players = Mathf.Clamp(PlayerTarget.Active.Count, 1, 4);
            totalThisRound = tuning.TotalForRound(round, players);
            if (!running) StartCoroutine(RoundLoop());
        }

        private IEnumerator RoundLoop()
        {
            running = true;

            while (spawnedThisRound < totalThisRound)
            {
                CleanupDead();

                if (alive.Count < tuning.maxAliveMobile)
                {
                    ZombieSpawnPoint point = ChooseSpawnPoint();
                    if (point != null)
                    {
                        ZombieBrain zombie = Instantiate(zombiePrefab, point.transform.position, point.transform.rotation);
                        zombie.Initialize(round, tuning.SpeedForRound(round, Random.value));
                        alive.Add(zombie.GetComponent<ZombieHealth>());
                        spawnedThisRound++;
                    }
                }

                yield return new WaitForSeconds(spawnIntervalSeconds);
            }

            while (true)
            {
                CleanupDead();
                if (alive.Count == 0) break;
                yield return new WaitForSeconds(0.5f);
            }

            running = false;
            yield return new WaitForSeconds(intermissionSeconds);
            BeginRound(round + 1);
        }

        private void CleanupDead() => alive.RemoveAll(z => z == null || !z.IsAlive);

        private ZombieSpawnPoint ChooseSpawnPoint()
        {
            if (spawnPoints == null || spawnPoints.Length == 0) return null;
            int start = Random.Range(0, spawnPoints.Length);

            for (int i = 0; i < spawnPoints.Length; i++)
            {
                ZombieSpawnPoint point = spawnPoints[(start + i) % spawnPoints.Length];
                if (point != null && point.CanSpawn()) return point;
            }
            return null;
        }
    }
}

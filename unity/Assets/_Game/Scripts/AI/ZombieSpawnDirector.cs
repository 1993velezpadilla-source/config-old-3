using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace Sanctum.Zombies.AI
{
    public sealed class ZombieSpawnPoint : MonoBehaviour
    {
        [SerializeField] private float minimumPlayerDistance = 7f;

        public bool CanSpawn() => TryGetSpawnPosition(out _);

        public bool TryGetSpawnPosition(out Vector3 position)
        {
            position = transform.position;

            foreach (PlayerTarget p in PlayerTarget.Active)
            {
                if (p != null && p.IsAlive && Vector3.Distance(transform.position, p.transform.position) < minimumPlayerDistance)
                    return false;
            }

            if (!NavMesh.SamplePosition(transform.position, out NavMeshHit hit, 1.5f, NavMesh.AllAreas))
                return false;

            position = hit.position;
            return true;
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
        private bool gameOver;

        public int Round => round;
        public bool IsGameOver => gameOver;

        private IEnumerator Start()
        {
            yield return new WaitForSeconds(1f);
            BeginRound(1);
        }

        public void BeginRound(int value)
        {
            if (gameOver) return;
            round = Mathf.Max(1, value);
            spawnedThisRound = 0;
            int players = Mathf.Clamp(AlivePlayerCount(), 1, 4);
            totalThisRound = tuning.TotalForRound(round, players);
            if (!running) StartCoroutine(RoundLoop());
        }

        private IEnumerator RoundLoop()
        {
            running = true;

            while (spawnedThisRound < totalThisRound)
            {
                if (AlivePlayerCount() == 0)
                {
                    gameOver = true;
                    running = false;
                    yield break;
                }

                CleanupDead();

                if (alive.Count < tuning.maxAliveMobile)
                {
                    ZombieSpawnPoint point = ChooseSpawnPoint();
                    if (point != null && point.TryGetSpawnPosition(out Vector3 spawnPosition))
                    {
                        ZombieBrain zombie = Instantiate(zombiePrefab, spawnPosition, point.transform.rotation);
                        zombie.Initialize(round, tuning.SpeedForRound(round, Random.value));
                        alive.Add(zombie.GetComponent<ZombieHealth>());
                        spawnedThisRound++;
                    }
                }

                yield return new WaitForSeconds(spawnIntervalSeconds);
            }

            while (true)
            {
                if (AlivePlayerCount() == 0)
                {
                    gameOver = true;
                    running = false;
                    yield break;
                }

                CleanupDead();
                if (alive.Count == 0) break;
                yield return new WaitForSeconds(0.5f);
            }

            running = false;
            yield return new WaitForSeconds(intermissionSeconds);
            BeginRound(round + 1);
        }

        public void ResetGame()
        {
            StopAllCoroutines();
            foreach (ZombieHealth zombie in alive)
                if (zombie != null) Destroy(zombie.gameObject);
            alive.Clear();
            gameOver = false;
            running = false;
            round = 0;
            BeginRound(1);
        }

        private static int AlivePlayerCount()
        {
            int count = 0;
            foreach (PlayerTarget player in PlayerTarget.Active)
                if (player != null && player.IsAlive) count++;
            return count;
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

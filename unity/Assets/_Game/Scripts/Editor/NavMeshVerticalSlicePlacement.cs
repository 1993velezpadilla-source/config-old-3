#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;
using UnityEngine.AI;

namespace Sanctum.Zombies.EditorTools
{
    public static class NavMeshVerticalSlicePlacement
    {
        public readonly struct Layout
        {
            public readonly Vector3 playerPosition;
            public readonly Vector3 lookTarget;
            public readonly Vector3[] zombieSpawns;

            public Layout(Vector3 playerPosition, Vector3 lookTarget, Vector3[] zombieSpawns)
            {
                this.playerPosition = playerPosition;
                this.lookTarget = lookTarget;
                this.zombieSpawns = zombieSpawns;
            }
        }

        public static Layout Build(int spawnCount = 8)
        {
            NavMeshTriangulation triangulation = NavMesh.CalculateTriangulation();
            Vector3[] vertices = triangulation.vertices;

            if (vertices == null || vertices.Length < 3)
                throw new InvalidOperationException("NavMesh triangulation is empty. Church navigation did not bake.");

            const float bandHeight = 0.35f;
            Dictionary<int, List<Vector3>> bands = new Dictionary<int, List<Vector3>>();

            foreach (Vector3 vertex in vertices)
            {
                int key = Mathf.RoundToInt(vertex.y / bandHeight);
                if (!bands.TryGetValue(key, out List<Vector3> list))
                {
                    list = new List<Vector3>();
                    bands.Add(key, list);
                }
                list.Add(vertex);
            }

            List<Vector3> primary = bands
                .OrderByDescending(kv => kv.Value.Count)
                .First().Value;

            Vector3 center = Average(primary);

            // Start from the far edge of the dominant walkable floor, then pull inward.
            // This produces an entrance-like composition while remaining driven by real baked geometry.
            Vector3 edge = primary
                .OrderByDescending(v => HorizontalSqrDistance(v, center))
                .First();

            Vector3 requestedPlayer = Vector3.Lerp(edge, center, 0.24f);
            Vector3 player = SampleOrThrow(requestedPlayer, 4.0f, "player");

            Vector3 flatLook = center;
            flatLook.y = player.y + 1.4f;

            List<Vector3> spawns = SelectSpawns(primary, player, spawnCount, 7.0f, 4.0f);
            if (spawns.Count < spawnCount)
                spawns = SelectSpawns(primary, player, spawnCount, 5.0f, 2.0f);

            if (spawns.Count < Mathf.Min(4, spawnCount))
                throw new InvalidOperationException($"Only {spawns.Count} safe NavMesh spawn points found.");

            return new Layout(player, flatLook, spawns.Take(spawnCount).ToArray());
        }

        public static Vector3 Project(Vector3 requested, float radius = 3f)
        {
            return NavMesh.SamplePosition(requested, out NavMeshHit hit, radius, NavMesh.AllAreas)
                ? hit.position
                : requested;
        }

        private static List<Vector3> SelectSpawns(
            List<Vector3> source,
            Vector3 player,
            int count,
            float minPlayerDistance,
            float minSpacing)
        {
            List<Vector3> selected = new List<Vector3>(count);

            foreach (Vector3 candidate in source.OrderByDescending(v => HorizontalSqrDistance(v, player)))
            {
                if (HorizontalDistance(candidate, player) < minPlayerDistance) continue;
                if (selected.Any(existing => HorizontalDistance(candidate, existing) < minSpacing)) continue;

                Vector3 snapped = Project(candidate, 0.8f);
                if (HorizontalDistance(snapped, player) < minPlayerDistance) continue;

                selected.Add(snapped);
                if (selected.Count >= count) break;
            }

            return selected;
        }

        private static Vector3 SampleOrThrow(Vector3 requested, float radius, string label)
        {
            if (!NavMesh.SamplePosition(requested, out NavMeshHit hit, radius, NavMesh.AllAreas))
                throw new InvalidOperationException($"Could not snap {label} to baked NavMesh near {requested}.");
            return hit.position;
        }

        private static Vector3 Average(List<Vector3> values)
        {
            Vector3 sum = Vector3.zero;
            foreach (Vector3 value in values) sum += value;
            return sum / Mathf.Max(1, values.Count);
        }

        private static float HorizontalSqrDistance(Vector3 a, Vector3 b)
        {
            float dx = a.x - b.x;
            float dz = a.z - b.z;
            return dx * dx + dz * dz;
        }

        private static float HorizontalDistance(Vector3 a, Vector3 b)
            => Mathf.Sqrt(HorizontalSqrDistance(a, b));
    }
}
#endif

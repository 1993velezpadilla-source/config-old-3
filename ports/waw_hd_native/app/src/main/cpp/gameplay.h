#pragma once
// Original, self-contained gameplay prototype. NOT decompiled game code.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace native_demo {
constexpr int kEnemyCapacity = 64;
constexpr int kMagazineSize = 8;
constexpr float kPi = 3.14159265358979323846f;

struct Enemy {
    float x = 0.0f, z = 0.0f;
    float attackCooldown = 0.0f;
    int health = 0;
    bool active = false;
};

struct Game {
    float px = 0.0f, pz = 7.0f, yaw = 0.0f, pitch = 0.0f;
    float joystickX = 0.0f, joystickY = 0.0f;
    float time = 0.0f, reloadDone = 0.0f, nextFire = 0.0f;
    float nextWave = 0.0f, lastShot = -10.0f;
    bool moving = false, sprint = false, ads = false, reloading = false, dead = false;
    int health = 100, wave = 0, kills = 0, ammo = kMagazineSize, reserve = 48;
    int enemyCount = 0, enemiesAlive = 0;
    uint32_t rng = 0xBADD1E55u;
    std::array<Enemy, kEnemyCapacity> enemies{};

    uint32_t random() {
        rng ^= rng << 13;
        rng ^= rng >> 17;
        rng ^= rng << 5;
        return rng;
    }

    float random01() { return static_cast<float>(random() & 0xffffu) / 65535.0f; }

    void spawnWave() {
        if (dead) return;
        ++wave; // No artificial round limit; enemy count is capped for performance.
        enemyCount = std::min(4 + wave * 2, kEnemyCapacity);
        enemiesAlive = enemyCount;
        for (int i = 0; i < enemyCount; ++i) {
            Enemy &e = enemies[static_cast<size_t>(i)];
            // Spawn ahead of the initial player, but behind room obstacles.
            e.x = -8.0f + random01() * 16.0f;
            e.z = -17.5f + random01() * 10.5f;
            e.attackCooldown = 0.0f;
            e.health = 1 + std::min(wave / 5, 6);
            e.active = true;
        }
        nextWave = -1.0f;
    }

    void reset() {
        *this = Game{};
        spawnWave();
    }

    bool startReload() {
        if (dead || reloading || ammo >= kMagazineSize || reserve <= 0) return false;
        reloading = true;
        reloadDone = time + 1.55f;
        return true;
    }

    bool fire() {
        if (dead || reloading || time + 0.0001f < nextFire) return false;
        if (ammo <= 0) {
            startReload();
            return false;
        }
        --ammo;
        nextFire = time + 0.28f;
        lastShot = time;
        // Hitscan: camera-to-enemy ray against a sphere in world coordinates.
        const float cp = std::cos(pitch);
        const float dx = std::sin(yaw) * cp;
        const float dy = std::sin(pitch);
        const float dz = -std::cos(yaw) * cp;
        float nearest = 10000.0f;
        Enemy* target = nullptr;
        for (int i = 0; i < enemyCount; ++i) {
            Enemy &e = enemies[static_cast<size_t>(i)];
            if (!e.active) continue;
            const float ex = e.x - px, ey = 1.25f - 1.60f, ez = e.z - pz;
            const float along = ex * dx + ey * dy + ez * dz;
            if (along <= 0.0f || along >= nearest) continue;
            const float distanceSq = ex * ex + ey * ey + ez * ez - along * along;
            if (distanceSq < 0.50f * 0.50f) {
                nearest = along;
                target = &e;
            }
        }
        if (target) {
            if (--target->health <= 0) {
                target->active = false;
                --enemiesAlive;
                ++kills;
                if (enemiesAlive == 0) nextWave = time + 3.0f;
            }
        }
        return true;
    }

    void update(float delta) {
        if (dead) return;
        const float dt = std::clamp(delta, 0.0f, 0.05f);
        time += dt;
        if (reloading && time >= reloadDone) {
            const int take = std::min(kMagazineSize - ammo, reserve);
            ammo += take;
            reserve -= take;
            reloading = false;
        }

        if (moving) {
            const float mag = std::sqrt(joystickX * joystickX + joystickY * joystickY);
            const float factor = mag > 1.0f ? (1.0f / mag) : 1.0f;
            const float speed = sprint ? 5.0f : 3.1f;
            const float rightX = std::cos(yaw), rightZ = std::sin(yaw);
            const float frontX = std::sin(yaw), frontZ = -std::cos(yaw);
            px += (rightX * joystickX + frontX * joystickY) * factor * speed * dt;
            pz += (rightZ * joystickX + frontZ * joystickY) * factor * speed * dt;
            px = std::clamp(px, -8.9f, 8.9f);
            pz = std::clamp(pz, -18.4f, 8.7f);
        }

        for (int i = 0; i < enemyCount; ++i) {
            Enemy &e = enemies[static_cast<size_t>(i)];
            if (!e.active) continue;
            e.attackCooldown = std::max(0.0f, e.attackCooldown - dt);
            const float diffX = px - e.x, diffZ = pz - e.z;
            const float distance = std::sqrt(diffX * diffX + diffZ * diffZ);
            if (distance > 1.00f) {
                const float speed = 0.76f + 0.036f * static_cast<float>(std::min(wave, 35));
                const float step = std::min(speed * dt, distance - 1.00f);
                e.x += diffX / distance * step;
                e.z += diffZ / distance * step;
            } else if (e.attackCooldown <= 0.0f) {
                health = std::max(0, health - 12);
                e.attackCooldown = 0.85f;
                if (health == 0) {
                    dead = true;
                    break;
                }
            }
        }
        if (enemiesAlive == 0 && nextWave >= 0.0f && time >= nextWave)
            spawnWave();
    }
};
} // namespace native_demo

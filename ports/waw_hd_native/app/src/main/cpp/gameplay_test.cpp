// Host-compiled invariant checks. Only original prototype game logic.
#include "gameplay.h"
#include <cassert>
#include <cmath>
#include <iostream>

using native_demo::Game;
static bool near(float a, float b) { return std::abs(a - b) < 0.01f; }

int main() {
    Game g;
    g.reset();
    assert(g.wave == 1);
    assert(g.enemyCount == 6);
    assert(g.enemiesAlive == 6);
    assert(g.health == 100);
    assert(g.ammo == 8);

    // Hitscan works against the closest enemy at the original camera aim point.
    g.px = 0.0f; g.pz = 0.0f; g.yaw = 0.0f; g.pitch = 0.0f;
    g.enemyCount = 1; g.enemiesAlive = 1;
    auto &e = g.enemies[0];
    e = {}; e.x = 0.0f; e.z = -5.0f; e.health = 1; e.active = true;
    assert(g.fire());
    assert(g.ammo == 7);
    assert(g.kills == 1);
    assert(g.enemiesAlive == 0);
    assert(!g.fire()); // time-gated fire, not arbitrary continuous hits

    // True limitless round counter, with a 3 second breathing period.
    for (int i = 0; i < 61; ++i) g.update(.05f);
    assert(g.wave == 2);
    assert(g.enemiesAlive == g.enemyCount);

    // Reload and sprint must work together: sprint NEVER cancels reload.
    g.reset();
    g.ammo = 2; g.reserve = 6;
    assert(g.startReload());
    g.sprint = true; g.moving = true; g.joystickY = 1;
    const float initialZ = g.pz;
    for (int i = 0; i < 33; ++i) g.update(.05f);
    assert(!g.reloading);
    assert(g.ammo == 8 && g.reserve == 0);
    assert(g.pz < initialZ);

    // Bounds prevent player from walking outside test room.
    g.moving = true; g.joystickX = 10; g.joystickY = -10;
    for (int i = 0; i < 500; ++i) g.update(.05f);
    assert(g.px >= -8.9f && g.px <= 8.9f);
    assert(g.pz >= -18.4f && g.pz <= 8.7f);

    // NPC can damage the player; dead player stops moving and firing.
    g.reset();
    g.enemyCount = 1; g.enemiesAlive = 1;
    g.enemies[0] = {}; g.enemies[0].x = 0; g.enemies[0].z = 7;
    g.enemies[0].health = 3; g.enemies[0].active = true;
    g.moving = false; g.health = 12;
    g.update(.05f);
    assert(g.dead && g.health == 0 && !g.fire());
    g.reset();
    assert(!g.dead && g.health == 100);

    std::cout << "NATIVE_GAMEPLAY_TEST_GREEN: wave, raycast, ammo, reload+sprint, bounds, melee, reset\n";
}

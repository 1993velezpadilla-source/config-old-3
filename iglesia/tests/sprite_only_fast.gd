extends SceneTree
## Fast CPU-only parse/invariant gate; does NOT require original Tripo archives.
## This does not claim visuals or Android performance.
func _initialize() -> void:
    call_deferred("_test")

func _test() -> void:
    var faults: Array[String] = []
    var animator_script = load("res://scripts/weapon_sprite_animator.gd")
    var player_script = load("res://scripts/player.gd")
    var hud_script = load("res://scripts/hud.gd")
    var enemy_script = load("res://scripts/enemy.gd")
    if animator_script == null or player_script == null or hud_script == null or enemy_script == null:
        faults.append("GDSCRIPT_IMPORT_RED")
    else:
        var player = player_script.new()
        var animator = animator_script.new()
        for budget in [12, 15, 24]:
            animator.set_profile(budget)
            if animator.required_count() != budget:
                faults.append("SPRITE_COUNT_RED " + str(budget))
        animator.set_profile(15)
        if animator.frames.size() != 7:
            faults.append("SPRITE_ACTION_COUNT_RED")
        var hud = hud_script.new()
        if hud.weapon_sprites == null:
            faults.append("PNG_RENDERER_NOT_CONNECTED")
        player.free()
        hud.free()
        var enemy = enemy_script.new()
        if enemy == null:
            faults.append("SPRITE_NUN_ENEMY_NOT_INSTANCED")
        else:
            enemy.free()
    if faults.is_empty():
        print("IGLESIA_SPRITE_ONLY_FAST_GATE_GREEN parser/12/15/24; art + APK + device NOT validated")
        quit(0)
    else:
        for fault in faults:
            push_error(fault)
        quit(1)

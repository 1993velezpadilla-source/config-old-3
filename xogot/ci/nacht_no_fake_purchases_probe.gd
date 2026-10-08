extends SceneTree

const InteractableScript := preload("res://scripts/interactable.gd")
const WeaponTestScript := preload("res://ci/nacht_no_fake_purchase_test_weapon.gd")
const BuyerScript := preload("res://ci/nacht_no_fake_purchase_buyer.gd")

func _init() -> void:
	call_deferred("_run")

func _check(condition: bool, reason: String) -> bool:
	if condition:
		return true
	push_error("XZOGOT_NACHT_NO_FAKE_PURCHASE_RED " + reason)
	quit(17)
	return false

func _run() -> void:
	set_meta("active_map_id", "nacht_chronicles_full")
	var buyer := BuyerScript.new() as CharacterBody3D
	buyer.name = "Player"
	var head := Node3D.new()
	head.name = "Head"
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	head.add_child(camera)
	buyer.add_child(head)
	var weapon := WeaponTestScript.new() as Node
	weapon.name = "Weapon"
	buyer.add_child(weapon)
	root.add_child(buyer)
	await process_frame

	if not _check(weapon.call("_nacht_external_source_placeholder_unavailable"), "Nacht identity not detected"):
		return
	var starting_id := str(weapon.call("get_weapon_id"))
	if not _check(not weapon.call("equip_source_external_item", "gun1911", true), "external source mapped to fake gun"):
		return
	if not _check(not weapon.call("buy_source_wall_weapon", "gun1911", 950, buyer), "external source charged wallbuy"):
		return
	if not _check(str(weapon.call("roll_source_mystery_weapon", ["gun1911", "raygun"])) == "", "mystery rolled placeholder"):
		return
	if not _check(int(buyer.get("spend_attempts")) == 0 and int(buyer.get("points")) == 1200, "money spent or attempted"):
		return
	if not _check(str(weapon.call("get_weapon_id")) == starting_id and not weapon.call("is_source_external_placeholder"), "weapon was mutated"):
		return
	if not _check(int(weapon.get("_mystery_serial")) == 0, "fake mystery roll incremented serial"):
		return

	for kind: int in [
		InteractableScript.Kind.MYSTERY,
		InteractableScript.Kind.GUMBALL,
		InteractableScript.Kind.WUNDERFIZZ,
		InteractableScript.Kind.WALLBUY,
	]:
		var machine := InteractableScript.new() as StaticBody3D
		machine.interaction_kind = kind
		machine.price = 950
		machine.one_shot = false
		machine.source_external_item = kind == InteractableScript.Kind.WALLBUY
		machine.source_item_pool = ["gun1911", "raygun"]
		machine.name = "NachtUnbuiltSource%d" % kind
		root.add_child(machine)
		if not _check(not machine.call("interact", buyer), "phantom machine succeeded: " + str(kind)):
			return
		if not _check(str(machine.get("_last_result")) == "NACHT_SOURCE_REWARD_NOT_READY", "no honest blocking result"):
			return
		if not _check(int(machine.get("_interaction_count")) == 0, "unbuilt machine counted as purchased"):
			return
		if not _check(int(buyer.get("spend_attempts")) == 0 and int(buyer.get("points")) == 1200, "source machine charged cash"):
			return
		machine.queue_free()
	await process_frame

	# Guard is strictly Nacht-scoped. Normal church/test content remains
	# eligible for pre-existing implementation (tested elsewhere).
	set_meta("active_map_id", "church")
	var ordinary := InteractableScript.new() as StaticBody3D
	ordinary.interaction_kind = InteractableScript.Kind.MYSTERY
	ordinary.price = 950
	root.add_child(ordinary)
	if not _check(not ordinary.call("_is_unimplemented_nacht_source_purchase"), "guard leaked onto church"):
		return
	if not _check(not weapon.call("_nacht_external_source_placeholder_unavailable"), "weapon guard leaked onto church"):
		return
	ordinary.queue_free()
	set_meta("active_map_id", "nacht_chronicles_full")
	print("XZOGOT_NACHT_NO_FAKE_PURCHASE_PROBE_GREEN unresolved=4 spent=0 weapon_unchanged=true serial_unchanged=true other_maps_unblocked=true")
	quit(0)

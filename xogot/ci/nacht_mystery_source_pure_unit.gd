extends SceneTree

# Pure runtime probe: source extraction is copied from successful Bytecode #37
# by the workflow, so the weapon pool/costs never come from a hand-made fixture.
const NACHT_SCRIPT := preload("res://scripts/nacht_full_map.gd")
const AUTHORITY := "res://ci/nacht_mystery_source_contract_fixture.json"

func _init() -> void:
	call_deferred("_run")

func _require(ok: bool, reason: String) -> bool:
	if not ok:
		push_error("NACHT_MYSTERY_PURE: " + reason)
		quit(42)
		return false
	return true

func _run() -> void:
	var file := FileAccess.open(AUTHORITY, FileAccess.READ)
	if not _require(file != null, "Bytecode #37 real source authority missing"):
		return
	var raw: Variant = JSON.parse_string(file.get_as_text())
	if not _require(raw is Dictionary, "real source authority is not a Dictionary"):
		return
	var source := raw as Dictionary
	if not _require(
		int(source.get("sourceInteractionContractCount", -1)) == 2,
		"real Blueprint source must include Gumball + Mystery",
	):
		return

	# No add_child(): _ready/_boot are not called, and no simulated map or
	# spoofed user points are created. These methods cannot mutate gameplay.
	var map := Node3D.new()
	map.set_script(NACHT_SCRIPT)
	map.set("_particle_activation_authority", source)
	map.set("_interactive_placements", {
		"counts": {
			"mystery_box": 0,
			"mystery_box_location": 1,
		},
	})
	var desc := map.call("describe_source_mystery_box_selection") as Dictionary
	var source_pool := desc.get("sourceWeaponPool", []) as Array
	if not _require(
		bool(desc.get("ready", false))
		and int(desc.get("sourceWeaponPoolSize", -1)) == 62
		and source_pool.size() == 62
		and str(desc.get("manager", "")) == "SpawnMystreyBox"
		and str(desc.get("spawnClass", "")) == "MysteryBox_C"
		and int(desc.get("locationMarkers", -1)) == 1
		and int(desc.get("directPlacedBoxes", -1)) == 0
		and str(desc.get("randomFunction", "")) == "KismetMathLibrary.RandomInteger(Array_Length)"
		and int(desc.get("previewCount", -1)) == 29
		and int(desc.get("teddyRefund", -1)) == 950
		and not bool(desc.get("purchaseLive", true)),
		"source description diverged from Bytecode #37",
	):
		return
	for index in range(source_pool.size()):
		var result := map.call("select_source_mystery_weapon_by_index", index) as Dictionary
		if not _require(
			bool(result.get("ready", false))
			and int(result.get("selectedIndex", -1)) == index
			and str(result.get("sourceWeaponId", "")) == str(source_pool[index])
			and not bool(result.get("purchaseLive", true)),
			"source weapon mismatch at index " + str(index),
		):
			return
	for invalid in [-1, 62, 1000]:
		var rejected := map.call("select_source_mystery_weapon_by_index", invalid) as Dictionary
		if not _require(not bool(rejected.get("ready", true)), "out-of-range source index accepted"):
			return
	var normal := map.call("evaluate_source_mystery_box_affordability", 950, false) as Dictionary
	var discount := map.call("evaluate_source_mystery_box_affordability", 10, true) as Dictionary
	var denied := map.call("evaluate_source_mystery_box_affordability", 949, false) as Dictionary
	if not _require(
		int(normal.get("selectedCost", -1)) == 950
		and bool(normal.get("canAfford", false))
		and int(normal.get("cashAfter", -1)) == 0
		and int(discount.get("selectedCost", -1)) == 10
		and bool(discount.get("canAfford", false))
		and int(discount.get("cashAfter", -1)) == 0
		and not bool(denied.get("canAfford", true))
		and int(denied.get("cashAfter", -1)) == 949
		and not bool(normal.get("purchaseLive", true))
		and not bool(discount.get("purchaseLive", true)),
		"source price and transactional safety mismatch",
	):
		return
	print("XZOGOT_NACHT_MYSTERY_SOURCE_PURE_UNIT_GREEN pool=62 index=0..61 invalid=-1,62,1000 cost=950 firesale=10 no_points_deducted=true")
	quit(0)

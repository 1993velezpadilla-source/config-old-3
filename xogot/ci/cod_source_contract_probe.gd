extends SceneTree

const CODSourceContract = preload("res://scripts/cod_source_contract.gd")

func _fail(code: int, message: String) -> void:
	push_error("COD_SOURCE_CONTRACT_PROBE: " + message)
	quit(code)

func _near(a: float, b: float, eps: float = 0.0001) -> bool:
	return absf(a - b) <= eps

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame

	var player := scene.get_node_or_null("Player") as CharacterBody3D
	if player == null:
		_fail(3, "Player missing")
		return
	var collider := player.get_node_or_null("CollisionShape3D") as CollisionShape3D
	var head := player.get_node_or_null("Head") as Node3D
	var camera := player.get_node_or_null("Head/Camera3D") as Camera3D
	if collider == null or head == null or camera == null:
		_fail(4, "player first-person nodes missing")
		return
	var capsule := collider.shape as CapsuleShape3D
	if capsule == null:
		_fail(5, "player collider is not CapsuleShape3D")
		return

	if not _near(capsule.height, CODSourceContract.PLAYER_STAND_CAPSULE_HEIGHT):
		_fail(10, "standing capsule height drift " + str(capsule.height))
		return
	if not _near(capsule.radius, CODSourceContract.PLAYER_RADIUS):
		_fail(11, "player radius drift " + str(capsule.radius))
		return
	if not _near(head.position.y, CODSourceContract.PLAYER_STAND_EYE_HEIGHT):
		_fail(12, "standing eye height drift " + str(head.position.y))
		return
	if not _near(camera.fov, CODSourceContract.BASE_VERTICAL_FOV):
		_fail(13, "base FOV drift " + str(camera.fov))
		return
	if not _near(float(player.get("ads_fov")), CODSourceContract.ADS_VERTICAL_FOV):
		_fail(14, "ADS FOV drift")
		return
	if not _near(float(player.get("sprint_fov")), CODSourceContract.SPRINT_VERTICAL_FOV):
		_fail(15, "sprint FOV drift")
		return
	if not _near(float(player.get("slide_fov")), CODSourceContract.SLIDE_VERTICAL_FOV):
		_fail(16, "slide FOV drift")
		return
	if not _near(float(player.get("ads_touch_multiplier")), CODSourceContract.ADS_TOUCH_MULTIPLIER):
		_fail(17, "ADS touch multiplier drift")
		return
	if not _near(float(player.get("gyro_ads_multiplier")), CODSourceContract.GYRO_ADS_MULTIPLIER):
		_fail(18, "gyro ADS multiplier drift")
		return
	if not _near(float(player.get("camera_stance_response")), CODSourceContract.STANCE_EYE_RESPONSE_HZ):
		_fail(19, "stance response drift")
		return
	if not _near(float(player.get("landing_spring_frequency")), CODSourceContract.LANDING_SPRING_HZ):
		_fail(20, "landing spring drift")
		return

	player.call("_set_crouched", true)
	await process_frame
	capsule = collider.shape as CapsuleShape3D
	if not _near(capsule.height, CODSourceContract.PLAYER_CROUCH_CAPSULE_HEIGHT):
		_fail(21, "crouch capsule height drift " + str(capsule.height))
		return

	print(
		"XZOGOT_COD_SOURCE_CONTRACT_GREEN ",
		"stand=", CODSourceContract.PLAYER_STAND_CAPSULE_HEIGHT,
		" eye=", CODSourceContract.PLAYER_STAND_EYE_HEIGHT,
		" radius=", CODSourceContract.PLAYER_RADIUS,
		" crouch=", CODSourceContract.PLAYER_CROUCH_CAPSULE_HEIGHT,
		" fov=", CODSourceContract.BASE_VERTICAL_FOV,
		" ads=", CODSourceContract.ADS_VERTICAL_FOV
	)
	scene.queue_free()
	await process_frame
	quit(0)

extends SceneTree

const TEST_PORT := 18881

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NETWORK_LOBBY_PROBE: " + message)
	paused = false
	quit(code)

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame

	var settings: Node = scene.get_node_or_null("HUD/MobileSettings")
	var network: Node = scene.get_node_or_null("NetworkManager")
	if settings == null or network == null:
		_fail(3, "settings/network manager missing")
		return

	for control_name: String in [
		"OpenNetwork",
		"NetworkStatus",
		"NetworkRoster",
		"NetworkShare",
		"NetworkError",
		"JoinAddress",
		"JoinPort",
		"HostPrivate",
		"HostPublic",
		"JoinDirect",
		"LeaveNetwork",
		"NetworkBack",
	]:
		if settings.find_child(control_name, true, false) == null:
			_fail(4, "network UI control missing: " + control_name)
			return
	print("XZOGOT_NETWORK_LOBBY_CONTROLS_GREEN")

	var port_edit: LineEdit = settings.find_child("JoinPort", true, false) as LineEdit
	var status: Label = settings.find_child("NetworkStatus", true, false) as Label
	var roster: Label = settings.find_child("NetworkRoster", true, false) as Label
	if port_edit == null or status == null or roster == null:
		_fail(5, "typed network controls missing")
		return

	# Offline pause remains a true pause.
	settings.call("open_pause_menu")
	settings.call("_show_page", "network")
	if not paused:
		_fail(6, "offline pause did not pause world")
		return

	port_edit.text = str(TEST_PORT)
	settings.call("_network_host", true)
	if str(network.call("get_mode")) != "host":
		_fail(7, "private host did not enter host mode")
		return
	if not bool(network.call("is_session_private")):
		_fail(8, "private host privacy flag wrong")
		return
	if int(network.call("get_session_port")) != TEST_PORT:
		_fail(9, "private host port wrong")
		return
	settings.call("_refresh_network_status")
	if not status.text.contains("HOST PRIVATE"):
		_fail(10, "private host status text wrong: " + status.text)
		return
	if not roster.text.contains("1/4") or not roster.text.contains("HOST") or not roster.text.contains("YOU"):
		_fail(11, "private host roster text wrong: " + roster.text)
		return
	print("XZOGOT_NETWORK_LOBBY_PRIVATE_GREEN")

	settings.call("_network_leave")
	if str(network.call("get_mode")) != "offline":
		_fail(12, "leave did not restore offline")
		return

	port_edit.text = str(TEST_PORT)
	settings.call("_network_host", false)
	if str(network.call("get_mode")) != "host":
		_fail(13, "public direct host did not enter host mode")
		return
	if bool(network.call("is_session_private")):
		_fail(14, "public direct privacy flag wrong")
		return
	settings.call("_refresh_network_status")
	if not status.text.contains("HOST PUBLIC DIRECT"):
		_fail(15, "public direct status text wrong: " + status.text)
		return
	print("XZOGOT_NETWORK_LOBBY_PUBLIC_GREEN")

	# Close/reopen while online: a multiplayer pause menu must not freeze host
	# rounds/zombies for every connected player.
	settings.call("close_menu")
	if paused:
		_fail(16, "close menu left tree paused")
		return
	settings.call("open_pause_menu")
	if paused:
		_fail(17, "online pause froze multiplayer world")
		return
	print("XZOGOT_NETWORK_ONLINE_PAUSE_GREEN")

	# Port input clamps to legal user ports.
	port_edit.text = "1"
	if int(settings.call("_network_port_value")) != 1024:
		_fail(18, "low port clamp failed")
		return
	port_edit.text = "99999"
	if int(settings.call("_network_port_value")) != 65535:
		_fail(19, "high port clamp failed")
		return
	port_edit.text = "garbage"
	if int(settings.call("_network_port_value")) != 7777:
		_fail(20, "invalid port fallback failed")
		return
	print("XZOGOT_NETWORK_LOBBY_PORT_GREEN")

	settings.call("_network_leave")
	settings.call("close_menu")
	if str(network.call("get_mode")) != "offline" or paused:
		_fail(21, "lobby teardown failed")
		return

	print("XZOGOT_NETWORK_LOBBY_SYSTEM_GREEN")
	scene.queue_free()
	await process_frame
	quit(0)

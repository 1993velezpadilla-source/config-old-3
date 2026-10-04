extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("PUBLIC_RELAY_FALLBACK_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame
	var network: Node = scene.get_node_or_null("NetworkManager")
	var directory: Node = scene.get_node_or_null("PublicMatchDirectory")
	if network == null or directory == null:
		_fail(3, "network runtime missing")
		return

	ProjectSettings.set_setting("network/xz/public_relay_url", "ws://127.0.0.1:19999")
	directory.call("configure_base_url", "http://127.0.0.1:19998")
	if not bool(network.call("is_public_relay_configured")):
		_fail(4, "relay setting not visible")
		return
	if str(network.call("get_public_relay_endpoint")) != "ws://127.0.0.1:19999":
		_fail(5, "relay endpoint wrong")
		return
	var err: Error = network.call("join_best_public_match") as Error
	if err != OK:
		_fail(6, "empty directory did not choose relay: " + str(err))
		return
	if str(network.call("get_transport")) != "websocket":
		_fail(7, "fallback transport is not websocket")
		return
	if str(network.call("get_mode")) != "joining":
		_fail(8, "fallback did not enter joining")
		return
	print("XZOGOT_PUBLIC_RELAY_CONFIG_GREEN")
	print("XZOGOT_PUBLIC_EMPTY_DIRECTORY_FALLBACK_GREEN")
	print("XZOGOT_PUBLIC_RELAY_AUTO_FALLBACK_GREEN")
	network.call("leave_game")
	scene.queue_free()
	await process_frame
	quit(0)

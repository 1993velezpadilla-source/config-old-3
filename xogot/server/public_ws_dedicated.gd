extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _port() -> int:
	var raw := OS.get_environment("PORT").strip_edges()
	return clampi(int(raw) if raw.is_valid_int() else 10000, 1024, 65535)

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		push_error("XZOGOT_PUBLIC_RELAY_MAIN_MISSING")
		quit(2)
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	await process_frame
	await process_frame
	var network: Node = scene.get_node_or_null("NetworkManager")
	if network == null:
		push_error("XZOGOT_PUBLIC_RELAY_NETWORK_MISSING")
		quit(3)
		return
	var port := _port()
	var err: Error = network.call("host_websocket_dedicated", port) as Error
	if err != OK:
		push_error("XZOGOT_PUBLIC_RELAY_BIND_FAILED_" + str(err))
		quit(4)
		return
	print("XZOGOT_PUBLIC_RELAY_READY port=", port, " human_slots=4")

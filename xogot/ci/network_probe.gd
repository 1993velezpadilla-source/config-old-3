extends SceneTree

func _init() -> void:
	call_deferred("_run")

func _fail(code: int, message: String) -> void:
	push_error("NETWORK_PROBE: " + message)
	quit(code)

func _run() -> void:
	var packed := load("res://main.tscn") as PackedScene
	if packed == null:
		_fail(2, "main scene missing")
		return
	var scene: Node = packed.instantiate()
	root.add_child(scene)
	await process_frame
	await physics_frame

	var network: Node = scene.get_node_or_null("NetworkManager")
	var player: Node = scene.get_node_or_null("Player")
	var rounds: Node = scene.get_node_or_null("RoundManager")
	var powerups: Node = scene.get_node_or_null("PowerUpManager")
	if network == null or player == null or rounds == null or powerups == null:
		_fail(3, "network/player/rounds/powerups missing")
		return
	if str(network.call("get_mode")) != "offline":
		_fail(4, "network did not boot offline")
		return
	if int(network.call("get_connected_player_count")) != 1:
		_fail(5, "offline roster must contain local player")
		return
	print("XZOGOT_NETWORK_BOOT_GREEN")

	# Actual ENet server creation through the production manager.
	var host_port: int = 18777
	var host_err: int = int(network.call("host_game", host_port, true))
	if host_err != OK:
		_fail(6, "production host creation failed: " + str(host_err))
		return
	if not bool(network.call("is_host")) or str(network.call("get_mode")) != "host":
		_fail(7, "manager did not enter host mode")
		return
	if int(network.call("get_local_peer_id")) != 1:
		_fail(8, "host peer ID must be 1")
		return
	print("XZOGOT_ENET_HOST_GREEN")

	# Add a production remote proxy and verify the real round formula sees 2P.
	var proxy: Node = network.call("_ensure_remote_proxy", 2) as Node
	if proxy == null:
		_fail(9, "remote proxy creation failed")
		return
	network.set("_roster", {1: true, 2: true})
	if int(network.call("get_connected_player_count")) != 2:
		_fail(10, "2P roster count wrong")
		return
	if int(rounds.call("zombies_for_round", 10)) != 42:
		_fail(11, "round manager did not see 2-player roster")
		return
	print("XZOGOT_NETWORK_ROSTER_2P_GREEN")

	# Host-authoritative remote damage + revive path.
	(player as Node3D).global_position = Vector3(0.0, 0.38, 6.24)
	(proxy as Node3D).global_position = Vector3(1.0, 0.38, 6.24)
	proxy.call("apply_damage", 9999.0)
	if not bool(proxy.call("is_downed")):
		_fail(12, "remote proxy did not enter host-owned downed state")
		return
	if not bool(network.call("submit_revive_hold", 2, 4.1)):
		_fail(13, "host network revive request rejected")
		return
	if bool(proxy.call("is_downed")) or bool(proxy.call("is_eliminated")):
		_fail(14, "host network revive did not restore proxy")
		return
	if absf(float(proxy.call("get_health")) - 50.0) > 0.1:
		_fail(15, "network revive health wrong")
		return
	print("XZOGOT_NETWORK_REVIVE_AUTHORITY_GREEN")

	# Client mode must not run a second independent round/power-up simulation.
	network.call("_set_client_simulation", true)
	if not bool(rounds.get("_dev_no_zombies")):
		_fail(16, "client mode did not suppress local round simulation")
		return
	if powerups.is_processing():
		_fail(17, "client mode left local power-up manager processing")
		return
	network.call("_set_client_simulation", false)
	if bool(rounds.get("_dev_no_zombies")):
		_fail(18, "host/offline mode did not restore round simulation")
		return
	if not powerups.is_processing():
		_fail(19, "host/offline mode did not restore power-up processing")
		return
	print("XZOGOT_NETWORK_HOST_AUTHORITY_GREEN")

	network.call("leave_game")
	if str(network.call("get_mode")) != "offline":
		_fail(20, "leave_game did not restore offline mode")
		return
	print("XZOGOT_NETWORK_LEAVE_GREEN")

	# Two independent SceneMultiplayer instances exercise a real localhost ENet
	# handshake in one Godot process without replacing the production tree API.
	var server_peer := ENetMultiplayerPeer.new()
	var client_peer := ENetMultiplayerPeer.new()
	var transport_port: int = 18778
	var server_err: Error = server_peer.create_server(transport_port, 3)
	if server_err != OK:
		_fail(21, "raw ENet server failed: " + str(server_err))
		return
	var client_err: Error = client_peer.create_client("127.0.0.1", transport_port)
	if client_err != OK:
		server_peer.close()
		_fail(22, "raw ENet client failed: " + str(client_err))
		return

	var server_api := SceneMultiplayer.new()
	var client_api := SceneMultiplayer.new()
	server_api.multiplayer_peer = server_peer
	client_api.multiplayer_peer = client_peer
	var server_connected: bool = false
	var client_connected: bool = false
	server_api.peer_connected.connect(func(_id: int): server_connected = true)
	client_api.connected_to_server.connect(func(): client_connected = true)

	for _i in range(240):
		server_api.poll()
		client_api.poll()
		if server_connected and client_connected:
			break
		await process_frame

	server_peer.close()
	client_peer.close()
	if not server_connected or not client_connected:
		_fail(
			23,
			"localhost ENet handshake failed server=%s client=%s" % [
				str(server_connected),
				str(client_connected),
			]
		)
		return
	print("XZOGOT_ENET_LOCALHOST_HANDSHAKE_GREEN")
	print("XZOGOT_4P_NETWORK_FOUNDATION_GREEN")

	scene.queue_free()
	await process_frame
	quit(0)

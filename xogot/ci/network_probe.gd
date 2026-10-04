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

	# Host is authoritative for client weapon damage and score awards.
	var barricades: Array[Node] = get_nodes_in_group("zombie_barricade")
	if barricades.is_empty():
		_fail(27, "no barricade available for network zombie hit test")
		return
	rounds.set("auto_start", false)
	var target_zombie: Node = rounds.call("spawn_from_barricade", barricades[0]) as Node
	if target_zombie == null:
		_fail(28, "failed to spawn host zombie for network hit")
		return
	var hp_before: float = float(target_zombie.call("get_health"))
	var points_before: int = int(proxy.call("get_points"))
	var hit_pos: Vector3 = (target_zombie as Node3D).global_position + Vector3(0.0, 1.45, 0.0)
	if not bool(network.call("_server_apply_zombie_hit", 2, target_zombie.name, hit_pos, false)):
		_fail(29, "host rejected valid network zombie hit")
		return
	if float(target_zombie.call("get_health")) >= hp_before:
		_fail(30, "host-authoritative network hit dealt no damage")
		return
	if int(proxy.call("get_points")) <= points_before:
		_fail(31, "host-authoritative hit awarded no points")
		return
	print("XZOGOT_NETWORK_ZOMBIE_DAMAGE_GREEN")

	# Client zombie representation uses the same Monja runtime, but no local AI.
	var net_zombie: Node = network.call("_ensure_network_zombie", "NetworkZombieVisualProbe") as Node
	if net_zombie == null:
		_fail(32, "network zombie proxy creation failed")
		return
	net_zombie.call(
		"apply_network_proxy_state",
		Vector3(2.0, 0.24, 4.0),
		0.4,
		125.0,
		2,
		false,
		false
	)
	if not bool(net_zombie.get_meta("network_proxy", false)):
		_fail(33, "network zombie proxy mode missing")
		return
	if net_zombie.get_node_or_null("MonjaBasicaVisual") == null:
		_fail(34, "network zombie did not instantiate Monja visual")
		return
	if int(network.call("get_network_zombie_count")) != 1:
		_fail(35, "network zombie proxy census wrong")
		return
	network.call("_remove_network_zombie", "NetworkZombieVisualProbe")
	target_zombie.call("powerup_kill")
	await process_frame
	print("XZOGOT_NETWORK_ZOMBIE_REPLICATION_GREEN")

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

	# Real localhost ENet socket handshake + reliable packet transfer. We use
	# ENetConnection directly here so two endpoints can coexist in one process.
	var server_host := ENetConnection.new()
	var client_host := ENetConnection.new()
	var transport_port: int = 18778
	var server_err: Error = server_host.create_host_bound("127.0.0.1", transport_port, 3)
	if server_err != OK:
		_fail(21, "raw ENet server failed: " + str(server_err))
		return
	var client_host_err: Error = client_host.create_host(1)
	if client_host_err != OK:
		server_host.destroy()
		_fail(22, "raw ENet client host failed: " + str(client_host_err))
		return
	var client_link: ENetPacketPeer = client_host.connect_to_host("127.0.0.1", transport_port, 2)
	if client_link == null:
		client_host.destroy()
		server_host.destroy()
		_fail(23, "raw ENet connect_to_host returned null")
		return

	var server_link: ENetPacketPeer = null
	var server_connected: bool = false
	var client_connected: bool = false
	for _i in range(360):
		var server_event: Array = server_host.service(0)
		var client_event: Array = client_host.service(0)
		if server_event.size() >= 2 and int(server_event[0]) == ENetConnection.EVENT_CONNECT:
			server_connected = true
			server_link = server_event[1] as ENetPacketPeer
		if client_event.size() >= 2 and int(client_event[0]) == ENetConnection.EVENT_CONNECT:
			client_connected = true
		if server_connected and client_connected:
			break
		await process_frame

	if not server_connected or not client_connected or server_link == null:
		client_host.destroy()
		server_host.destroy()
		_fail(
			24,
			"localhost ENet handshake failed server=%s client=%s" % [
				str(server_connected),
				str(client_connected),
			]
		)
		return

	var ping := "XZPING".to_utf8_buffer()
	var send_err: Error = client_link.send(0, ping, ENetPacketPeer.FLAG_RELIABLE)
	if send_err != OK:
		client_host.destroy()
		server_host.destroy()
		_fail(25, "reliable ENet send failed: " + str(send_err))
		return

	var received: bool = false
	for _i in range(240):
		var server_event: Array = server_host.service(0)
		client_host.service(0)
		if server_event.size() >= 2 and int(server_event[0]) == ENetConnection.EVENT_RECEIVE:
			var packet_peer: ENetPacketPeer = server_event[1] as ENetPacketPeer
			if packet_peer != null and packet_peer.get_available_packet_count() > 0:
				var packet: PackedByteArray = packet_peer.get_packet()
				if packet.get_string_from_utf8() == "XZPING":
					received = true
					break
		await process_frame

	client_host.destroy()
	server_host.destroy()
	if not received:
		_fail(26, "localhost ENet reliable packet was not received")
		return
	print("XZOGOT_ENET_LOCALHOST_HANDSHAKE_GREEN")
	print("XZOGOT_ENET_RELIABLE_PACKET_GREEN")
	print("XZOGOT_4P_NETWORK_FOUNDATION_GREEN")

	scene.queue_free()
	await process_frame
	quit(0)

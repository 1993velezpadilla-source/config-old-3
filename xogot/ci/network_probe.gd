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

	# Host-authoritative interaction economy for peer 2.
	proxy.call("add_points", 30000)
	var remote_weapon: Node = proxy.get_node_or_null("Weapon")
	if remote_weapon == null:
		_fail(36, "remote authoritative Weapon state missing")
		return

	var rear_door: Node = scene.get_node_or_null("RearDoor")
	var wallbuy: Node = scene.get_node_or_null("WallBuy_M1")
	var mystery: Node = scene.get_node_or_null("MysteryBoxSocket")
	var power: Node = scene.get_node_or_null("PowerSwitch")
	var perk: Node = scene.get_node_or_null("Perk_martyrs_blood")
	var forge: Node = scene.get_node_or_null("SanctumForge")
	if (
		rear_door == null or wallbuy == null or mystery == null
		or power == null or perk == null or forge == null
	):
		_fail(37, "network economy interactables missing")
		return

	(proxy as Node3D).global_position = (rear_door as Node3D).global_position
	var door_path: String = str(network.call("_relative_world_path", rear_door))
	var door_points_before: int = int(proxy.call("get_points"))
	if not bool(network.call("_server_apply_interaction", 2, door_path)):
		_fail(38, "host rejected valid remote door purchase")
		return
	if not bool(rear_door.call("was_used")):
		_fail(39, "remote door purchase did not open host door")
		return
	if int(proxy.call("get_points")) >= door_points_before:
		_fail(40, "remote door purchase did not charge host points")
		return
	print("XZOGOT_NETWORK_DOOR_ECONOMY_GREEN")

	(proxy as Node3D).global_position = (wallbuy as Node3D).global_position
	var wall_path: String = str(network.call("_relative_world_path", wallbuy))
	if not bool(network.call("_server_apply_interaction", 2, wall_path)):
		_fail(41, "host rejected remote M1 wallbuy")
		return
	if str(remote_weapon.call("get_weapon_id")) != "m1":
		_fail(42, "host remote wallbuy did not own M1")
		return
	print("XZOGOT_NETWORK_WALLBUY_ECONOMY_GREEN")

	(proxy as Node3D).global_position = (mystery as Node3D).global_position
	var mystery_path: String = str(network.call("_relative_world_path", mystery))
	if not bool(network.call("_server_apply_interaction", 2, mystery_path)):
		_fail(43, "host rejected remote Mystery Box")
		return
	var mystery_weapon: String = str(remote_weapon.call("get_weapon_id"))
	if mystery_weapon.is_empty() or mystery_weapon == "m1":
		_fail(44, "host Mystery Box did not change remote weapon")
		return
	print("XZOGOT_NETWORK_MYSTERY_ECONOMY_GREEN ", mystery_weapon)

	(proxy as Node3D).global_position = (power as Node3D).global_position
	var power_path: String = str(network.call("_relative_world_path", power))
	if not bool(network.call("_server_apply_interaction", 2, power_path)):
		_fail(45, "host rejected remote Power switch")
		return
	if not bool(get_meta("power_on", false)):
		_fail(46, "remote Power interaction did not set host power")
		return
	print("XZOGOT_NETWORK_POWER_SHARED_GREEN")

	(proxy as Node3D).global_position = (perk as Node3D).global_position
	var perk_path: String = str(network.call("_relative_world_path", perk))
	if not bool(network.call("_server_apply_interaction", 2, perk_path)):
		_fail(47, "host rejected remote perk purchase")
		return
	if not bool(proxy.call("has_perk", "martyrs_blood")):
		_fail(48, "remote perk not owned on host")
		return
	if float(proxy.call("get_max_health")) < 200.0:
		_fail(49, "remote Martyr perk did not update authoritative max health")
		return
	print("XZOGOT_NETWORK_PERK_ECONOMY_GREEN")

	(proxy as Node3D).global_position = (forge as Node3D).global_position
	var forge_path: String = str(network.call("_relative_world_path", forge))
	if not bool(network.call("_server_apply_interaction", 2, forge_path)):
		_fail(50, "host rejected remote Sanctum Forge")
		return
	if not bool(remote_weapon.call("is_upgraded")):
		_fail(51, "remote Forge upgrade not authoritative")
		return
	print("XZOGOT_NETWORK_FORGE_ECONOMY_GREEN")

	var window: Node = barricades[0]
	window.call("zombie_damage", 9999.0)
	if int(window.call("get_boards")) != 0:
		_fail(52, "network barricade setup did not break")
		return
	(proxy as Node3D).global_position = (window as Node3D).global_position
	var window_path: String = str(network.call("_relative_world_path", window))
	var repair_points_before: int = int(proxy.call("get_points"))
	if not bool(network.call("_server_apply_interaction", 2, window_path)):
		_fail(53, "host rejected remote barricade repair")
		return
	if int(window.call("get_boards")) != 1:
		_fail(54, "remote barricade repair did not change host board state")
		return
	if int(proxy.call("get_points")) <= repair_points_before:
		_fail(55, "remote barricade repair reward not owned by host")
		return
	print("XZOGOT_NETWORK_BARRICADE_SHARED_GREEN")

	# Spoofed client loadout never becomes damage authority.
	remote_weapon.call("equip_weapon", "colt", true)
	network.set("_peer_weapon_ids", {2: "tesla"})
	network.set("_peer_weapon_upgraded", {2: true})
	var spoof_zombie: Node = rounds.call("spawn_from_barricade", window) as Node
	if spoof_zombie == null:
		_fail(56, "failed to spawn loadout authority probe zombie")
		return
	var spoof_hp_before: float = float(spoof_zombie.call("get_health"))
	var spoof_hit := (spoof_zombie as Node3D).global_position + Vector3(0.0, 0.9, 0.0)
	if not bool(network.call("_server_apply_zombie_hit", 2, spoof_zombie.name, spoof_hit, false)):
		_fail(57, "valid authoritative Colt hit rejected")
		return
	var spoof_damage: float = spoof_hp_before - float(spoof_zombie.call("get_health"))
	if spoof_damage > 30.0:
		_fail(58, "client loadout spoof affected authoritative damage: " + str(spoof_damage))
		return
	spoof_zombie.call("powerup_kill")
	await process_frame
	print("XZOGOT_NETWORK_LOADOUT_AUTHORITY_GREEN damage=", spoof_damage)
	print("XZOGOT_NETWORK_SHARED_ECONOMY_GREEN")

	# Global Max Ammo must refill the authoritative remote Weapon state too.
	remote_weapon.set("_magazine", 0)
	remote_weapon.set("reserve_ammo", 0)
	if not bool(powerups.call("collect_powerup", "max_ammo", proxy)):
		_fail(59, "host Max Ammo collection failed")
		return
	if int(remote_weapon.call("get_magazine")) <= 0 or int(remote_weapon.call("get_reserve")) <= 0:
		_fail(60, "Max Ammo did not refill remote authoritative weapon")
		return
	print("XZOGOT_NETWORK_MAX_AMMO_GREEN")

	# Client display state comes from host snapshots, not a second simulation.
	rounds.call("apply_network_round_state", 7, 52, 0, 0, 3.5)
	if int(rounds.call("get_round")) != 7 or not bool(rounds.call("is_between_rounds")):
		_fail(61, "authoritative round snapshot did not apply")
		return
	if absf(float(rounds.call("get_round_break_remaining")) - 3.5) > 0.01:
		_fail(62, "network intermission timer wrong")
		return
	powerups.call("apply_network_effect_state", 12.0, 8.0)
	var effects: Dictionary = powerups.call("get_active_effects") as Dictionary
	if not effects.has("double_points") or not effects.has("insta_kill"):
		_fail(63, "network timed power-up effects did not apply")
		return
	print("XZOGOT_NETWORK_ROUND_STATE_GREEN")
	print("XZOGOT_NETWORK_POWERUP_EFFECTS_GREEN")

	# Existing host pickups are included for late join and client visual proxies
	# never collect themselves when the local player walks through them.
	var host_drop: Node3D = powerups.call(
		"spawn_powerup",
		"double_points",
		Vector3(60.0, 0.5, 60.0)
	) as Node3D
	if host_drop == null:
		_fail(64, "host power-up drop setup failed")
		return
	var session_snapshot: Dictionary = network.call("_build_session_snapshot") as Dictionary
	var pickup_states: Array = session_snapshot.get("pickups", []) as Array
	if int(session_snapshot.get("round", 0)) != 7 or pickup_states.is_empty():
		_fail(65, "session snapshot missing round or pickup")
		return
	powerups.call("apply_network_pickup_snapshot", pickup_states)
	if int(powerups.call("get_network_pickup_count")) != 1:
		_fail(66, "client power-up proxy was not created")
		return
	var network_pickup: Node3D = null
	for pickup_node: Node in get_nodes_in_group("xz_powerup_pickup"):
		if bool(pickup_node.get_meta("network_proxy", false)) and pickup_node is Node3D:
			network_pickup = pickup_node as Node3D
			break
	if network_pickup == null:
		_fail(67, "network pickup proxy node missing")
		return
	network_pickup.global_position = (player as Node3D).global_position
	await process_frame
	await process_frame
	if not is_instance_valid(network_pickup) or int(powerups.call("get_network_pickup_count")) != 1:
		_fail(68, "network visual pickup collected locally")
		return
	print("XZOGOT_NETWORK_POWERUP_PICKUP_GREEN")

	# Late join captures persistent doors/power/barricades plus the session.
	var late_snapshot: Dictionary = network.call("_build_late_join_snapshot") as Dictionary
	var late_interactions: Array = late_snapshot.get("interactions", []) as Array
	var late_barricades: Array = late_snapshot.get("barricades", []) as Array
	if late_interactions.size() < 2:
		_fail(69, "late-join snapshot missing persistent world interactions")
		return
	if late_barricades.size() < 8:
		_fail(70, "late-join snapshot missing barricade states")
		return
	var late_session: Dictionary = late_snapshot.get("session", {}) as Dictionary
	if int(late_session.get("round", 0)) != 7:
		_fail(71, "late-join session round missing")
		return
	print(
		"XZOGOT_NETWORK_LATE_JOIN_STATE_GREEN interactions=",
		late_interactions.size(),
		" barricades=", late_barricades.size()
	)

	powerups.call("apply_network_pickup_snapshot", [])
	powerups.call("debug_clear_timed_effects")
	host_drop.queue_free()
	await process_frame

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

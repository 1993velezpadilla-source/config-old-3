extends Node
class_name XzNetworkManager

signal session_state_changed(state: String)
signal roster_changed(peer_ids: PackedInt32Array)
signal network_error(message: String)

const REMOTE_PROXY_SCRIPT := preload("res://scripts/network_player_proxy.gd")
const SERVER_PEER_ID := 1
const DEFAULT_PORT := 7777
const MAX_PLAYERS := 4
const SNAPSHOT_INTERVAL := 0.05
const MAX_SNAPSHOT_DELTA := 3.0
const MAX_PITCH := 1.51

var _peer: ENetMultiplayerPeer
var _mode: String = "offline"
var _session_private: bool = true
var _port: int = DEFAULT_PORT
var _local_peer_id: int = SERVER_PEER_ID
var _snapshot_timer: float = 0.0
var _sequence: int = 0
var _roster: Dictionary = {}
var _remote_players: Dictionary = {}
var _accepted_positions: Dictionary = {}

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	_bind_multiplayer_signals()
	_configure_local_player(SERVER_PEER_ID)
	_roster[SERVER_PEER_ID] = true
	print("XZOGOT_NETWORK_MANAGER_READY port=", DEFAULT_PORT, " max_players=", MAX_PLAYERS)

func _bind_multiplayer_signals() -> void:
	var mp := multiplayer
	if not mp.peer_connected.is_connected(_on_peer_connected):
		mp.peer_connected.connect(_on_peer_connected)
	if not mp.peer_disconnected.is_connected(_on_peer_disconnected):
		mp.peer_disconnected.connect(_on_peer_disconnected)
	if not mp.connected_to_server.is_connected(_on_connected_to_server):
		mp.connected_to_server.connect(_on_connected_to_server)
	if not mp.connection_failed.is_connected(_on_connection_failed):
		mp.connection_failed.connect(_on_connection_failed)
	if not mp.server_disconnected.is_connected(_on_server_disconnected):
		mp.server_disconnected.connect(_on_server_disconnected)

func _local_player() -> Node:
	return get_parent().get_node_or_null("Player")

func _round_manager() -> Node:
	return get_parent().get_node_or_null("RoundManager")

func _powerup_manager() -> Node:
	return get_parent().get_node_or_null("PowerUpManager")

func _configure_local_player(peer_id: int) -> void:
	var player: Node = _local_player()
	if player == null:
		return
	_local_peer_id = peer_id
	player.set_meta("network_peer_id", peer_id)
	player.set_meta("network_remote", false)
	player.set_meta("network_session", _mode)

func _set_client_simulation(client_mode: bool) -> void:
	var rounds: Node = _round_manager()
	if rounds != null:
		if client_mode:
			if rounds.has_method("set_dev_no_zombies"):
				rounds.call("set_dev_no_zombies", true)
		else:
			if rounds.has_method("set_dev_no_zombies"):
				rounds.call("set_dev_no_zombies", false)
	var powerups: Node = _powerup_manager()
	if powerups != null:
		powerups.set_process(not client_mode)
	print("XZOGOT_NETWORK_HOST_AUTHORITY client_mode=", client_mode)

func host_game(port: int = DEFAULT_PORT, private_session: bool = true) -> Error:
	leave_game()
	var next_peer := ENetMultiplayerPeer.new()
	var err: Error = next_peer.create_server(port, MAX_PLAYERS - 1)
	if err != OK:
		network_error.emit("HOST_FAILED_%d" % int(err))
		print("XZOGOT_NETWORK_HOST_FAIL ", err)
		return err
	_peer = next_peer
	multiplayer.multiplayer_peer = _peer
	_mode = "host"
	_session_private = private_session
	_port = port
	_local_peer_id = SERVER_PEER_ID
	_roster.clear()
	_roster[SERVER_PEER_ID] = true
	_accepted_positions.clear()
	var player: Node3D = _local_player() as Node3D
	if player != null:
		_accepted_positions[SERVER_PEER_ID] = player.global_position
	_configure_local_player(SERVER_PEER_ID)
	_set_client_simulation(false)
	session_state_changed.emit(_mode)
	_emit_roster()
	print("XZOGOT_NETWORK_HOST_READY port=", port, " slots=", MAX_PLAYERS, " private=", private_session)
	return OK

func join_game(address: String, port: int = DEFAULT_PORT) -> Error:
	var clean_address: String = address.strip_edges()
	if clean_address.is_empty():
		clean_address = "127.0.0.1"
	leave_game()
	var next_peer := ENetMultiplayerPeer.new()
	var err: Error = next_peer.create_client(clean_address, port)
	if err != OK:
		network_error.emit("JOIN_FAILED_%d" % int(err))
		print("XZOGOT_NETWORK_JOIN_FAIL ", err)
		return err
	_peer = next_peer
	multiplayer.multiplayer_peer = _peer
	_mode = "joining"
	_port = port
	_set_client_simulation(true)
	session_state_changed.emit(_mode)
	print("XZOGOT_NETWORK_JOINING address=", clean_address, " port=", port)
	return OK

func leave_game() -> void:
	if _peer != null:
		_peer.close()
	_peer = null
	multiplayer.multiplayer_peer = OfflineMultiplayerPeer.new()
	_clear_remote_players()
	_roster.clear()
	_roster[SERVER_PEER_ID] = true
	_accepted_positions.clear()
	_mode = "offline"
	_local_peer_id = SERVER_PEER_ID
	_configure_local_player(SERVER_PEER_ID)
	_set_client_simulation(false)
	session_state_changed.emit(_mode)
	_emit_roster()
	print("XZOGOT_NETWORK_OFFLINE")

func _on_peer_connected(peer_id: int) -> void:
	if not multiplayer.is_server():
		return
	if peer_id <= 0:
		return
	_roster[peer_id] = true
	_ensure_remote_proxy(peer_id)
	_broadcast_roster()
	print("XZOGOT_NETWORK_PEER_JOIN peer=", peer_id, " count=", _roster.size())

func _on_peer_disconnected(peer_id: int) -> void:
	_roster.erase(peer_id)
	_accepted_positions.erase(peer_id)
	_remove_remote_proxy(peer_id)
	if multiplayer.is_server():
		_broadcast_roster()
	_emit_roster()
	print("XZOGOT_NETWORK_PEER_LEFT peer=", peer_id, " count=", _roster.size())

func _on_connected_to_server() -> void:
	_mode = "client"
	_local_peer_id = multiplayer.get_unique_id()
	_roster.clear()
	_roster[_local_peer_id] = true
	_configure_local_player(_local_peer_id)
	_set_client_simulation(true)
	rpc_id(SERVER_PEER_ID, "_server_request_roster")
	session_state_changed.emit(_mode)
	print("XZOGOT_NETWORK_CLIENT_READY peer=", _local_peer_id)

func _on_connection_failed() -> void:
	network_error.emit("CONNECTION_FAILED")
	print("XZOGOT_NETWORK_CONNECTION_FAILED")
	leave_game()

func _on_server_disconnected() -> void:
	network_error.emit("SERVER_DISCONNECTED")
	print("XZOGOT_NETWORK_SERVER_DISCONNECTED")
	leave_game()

func _emit_roster() -> void:
	var ids := PackedInt32Array()
	for id_var: Variant in _roster.keys():
		ids.append(int(id_var))
	ids.sort()
	roster_changed.emit(ids)

func _broadcast_roster() -> void:
	if not multiplayer.is_server():
		return
	var ids := PackedInt32Array()
	for id_var: Variant in _roster.keys():
		ids.append(int(id_var))
	ids.sort()
	rpc("_client_receive_roster", ids)
	_emit_roster()

@rpc("any_peer", "call_remote", "reliable")
func _server_request_roster() -> void:
	if not multiplayer.is_server():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	if sender <= 0:
		return
	var ids := PackedInt32Array()
	for id_var: Variant in _roster.keys():
		ids.append(int(id_var))
	ids.sort()
	rpc_id(sender, "_client_receive_roster", ids)

@rpc("authority", "call_remote", "reliable")
func _client_receive_roster(ids: PackedInt32Array) -> void:
	if multiplayer.is_server():
		return
	_roster.clear()
	for peer_id: int in ids:
		_roster[peer_id] = true
		if peer_id != _local_peer_id:
			_ensure_remote_proxy(peer_id)
	for existing_var: Variant in _remote_players.keys().duplicate():
		var existing: int = int(existing_var)
		if not _roster.has(existing):
			_remove_remote_proxy(existing)
	_emit_roster()
	print("XZOGOT_NETWORK_ROSTER ", ids)

func _ensure_remote_proxy(peer_id: int) -> Node:
	if peer_id == _local_peer_id:
		return null
	if _remote_players.has(peer_id):
		var existing: Node = _remote_players[peer_id] as Node
		if is_instance_valid(existing):
			return existing
	var proxy := CharacterBody3D.new()
	proxy.set_script(REMOTE_PROXY_SCRIPT)
	proxy.call("configure", peer_id, "PLAYER %d" % peer_id)
	get_parent().add_child(proxy)
	var origin := Vector3(float((_roster.size() % 3) - 1) * 1.1, 0.38, 6.24)
	proxy.global_position = origin
	_remote_players[peer_id] = proxy
	_accepted_positions[peer_id] = origin
	return proxy

func _remove_remote_proxy(peer_id: int) -> void:
	if not _remote_players.has(peer_id):
		return
	var proxy: Node = _remote_players[peer_id] as Node
	_remote_players.erase(peer_id)
	if is_instance_valid(proxy):
		proxy.queue_free()

func _clear_remote_players() -> void:
	for peer_var: Variant in _remote_players.keys().duplicate():
		_remove_remote_proxy(int(peer_var))
	_remote_players.clear()

func _process(delta: float) -> void:
	if _mode != "host" and _mode != "client":
		return
	_snapshot_timer -= delta
	if _snapshot_timer > 0.0:
		return
	_snapshot_timer = SNAPSHOT_INTERVAL
	_sequence += 1
	if _mode == "host":
		_broadcast_host_player_state()
		_broadcast_authoritative_remote_states()
	else:
		_send_client_motion()

func _safe_pitch(player: Node) -> float:
	var head: Node3D = player.get_node_or_null("Head") as Node3D
	return clampf(head.rotation.x if head != null else 0.0, -MAX_PITCH, MAX_PITCH)

func _send_client_motion() -> void:
	var player: Node3D = _local_player() as Node3D
	if player == null:
		return
	rpc_id(
		SERVER_PEER_ID,
		"_server_submit_motion",
		player.global_position,
		player.rotation.y,
		_safe_pitch(player),
		_sequence
	)

@rpc("any_peer", "call_remote", "unreliable_ordered", 1)
func _server_submit_motion(pos: Vector3, yaw: float, pitch: float, sequence: int) -> void:
	if not multiplayer.is_server():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	if sender <= SERVER_PEER_ID or not _roster.has(sender):
		return
	if not pos.is_finite() or not is_finite(yaw) or not is_finite(pitch):
		return
	var previous: Vector3 = _accepted_positions.get(sender, pos) as Vector3
	var delta_pos: Vector3 = pos - previous
	var accepted: Vector3 = pos
	if delta_pos.length() > MAX_SNAPSHOT_DELTA:
		accepted = previous + delta_pos.normalized() * MAX_SNAPSHOT_DELTA
		print("XZOGOT_NETWORK_MOVE_CLAMP peer=", sender, " delta=", delta_pos.length())
	_accepted_positions[sender] = accepted
	var proxy: Node = _ensure_remote_proxy(sender)
	if proxy != null and proxy.has_method("apply_network_state"):
		proxy.call(
			"apply_network_state",
			accepted,
			yaw,
			clampf(pitch, -MAX_PITCH, MAX_PITCH),
			float(proxy.call("get_health")),
			bool(proxy.call("is_downed")),
			bool(proxy.call("is_eliminated")),
			float(proxy.call("get_bleedout_remaining")),
			float(proxy.call("get_revive_progress_ratio"))
		)
	_relay_player_state(sender, sequence)

func _relay_player_state(peer_id: int, sequence: int) -> void:
	var node: Node = _network_player_node(peer_id)
	if node == null or not (node is Node3D):
		return
	var body := node as Node3D
	var health_value: float = float(node.call("get_health")) if node.has_method("get_health") else 100.0
	var downed_value: bool = bool(node.call("is_downed")) if node.has_method("is_downed") else false
	var eliminated_value: bool = bool(node.call("is_eliminated")) if node.has_method("is_eliminated") else false
	var bleedout_value: float = float(node.call("get_bleedout_remaining")) if node.has_method("get_bleedout_remaining") else 0.0
	var revive_ratio: float = float(node.call("get_revive_progress_ratio")) if node.has_method("get_revive_progress_ratio") else 0.0
	var pitch: float = _safe_pitch(node) if peer_id == SERVER_PEER_ID else (
		float(node.call("get_network_pitch")) if node.has_method("get_network_pitch") else 0.0
	)
	rpc(
		"_client_receive_player_state",
		peer_id,
		body.global_position,
		body.rotation.y,
		pitch,
		health_value,
		downed_value,
		eliminated_value,
		bleedout_value,
		revive_ratio,
		sequence
	)

func _broadcast_host_player_state() -> void:
	_relay_player_state(SERVER_PEER_ID, _sequence)

func _broadcast_authoritative_remote_states() -> void:
	for peer_var: Variant in _remote_players.keys():
		_relay_player_state(int(peer_var), _sequence)

@rpc("authority", "call_remote", "unreliable_ordered", 1)
func _client_receive_player_state(
	peer_id: int,
	pos: Vector3,
	yaw: float,
	pitch: float,
	health_value: float,
	downed_value: bool,
	eliminated_value: bool,
	bleedout_value: float,
	revive_ratio: float,
	_sequence_id: int
) -> void:
	if multiplayer.is_server():
		return
	if peer_id == _local_peer_id:
		var local: Node = _local_player()
		if local != null and local.has_method("apply_authoritative_network_vitals"):
			local.call(
				"apply_authoritative_network_vitals",
				health_value,
				downed_value,
				eliminated_value,
				bleedout_value,
				revive_ratio
			)
		if local is Node3D and (local as Node3D).global_position.distance_to(pos) > 1.25:
			(local as Node3D).global_position = (local as Node3D).global_position.lerp(pos, 0.35)
		return
	var proxy: Node = _ensure_remote_proxy(peer_id)
	if proxy != null and proxy.has_method("apply_network_state"):
		proxy.call(
			"apply_network_state",
			pos,
			yaw,
			pitch,
			health_value,
			downed_value,
			eliminated_value,
			bleedout_value,
			revive_ratio
		)

func _network_player_node(peer_id: int) -> Node:
	if peer_id == SERVER_PEER_ID and multiplayer.is_server():
		return _local_player()
	if peer_id == _local_peer_id:
		return _local_player()
	return _remote_players.get(peer_id, null) as Node

func submit_revive_hold(target_peer_id: int, delta: float) -> bool:
	if delta <= 0.0 or target_peer_id <= 0 or target_peer_id == _local_peer_id:
		return false
	if _mode == "host":
		return _server_apply_revive(SERVER_PEER_ID, target_peer_id, delta)
	if _mode == "client":
		rpc_id(SERVER_PEER_ID, "_server_revive_hold", target_peer_id, minf(delta, 0.15))
		return true
	return false

@rpc("any_peer", "call_remote", "unreliable_ordered", 2)
func _server_revive_hold(target_peer_id: int, delta: float) -> void:
	if not multiplayer.is_server():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	_server_apply_revive(sender, target_peer_id, clampf(delta, 0.0, 0.15))

func _server_apply_revive(reviver_peer_id: int, target_peer_id: int, delta: float) -> bool:
	var reviver: Node = _network_player_node(reviver_peer_id)
	var target: Node = _network_player_node(target_peer_id)
	if reviver == null or target == null or not (reviver is Node3D) or not (target is Node3D):
		return false
	if not target.has_method("is_downed") or not bool(target.call("is_downed")):
		return false
	if target.has_method("is_eliminated") and bool(target.call("is_eliminated")):
		return false
	if (reviver as Node3D).global_position.distance_to((target as Node3D).global_position) > 2.4:
		return false
	if not target.has_method("receive_revive_progress"):
		return false
	return bool(target.call("receive_revive_progress", reviver, delta))

func get_mode() -> String:
	return _mode

func is_network_session() -> bool:
	return _mode == "host" or _mode == "client" or _mode == "joining"

func is_host() -> bool:
	return _mode == "host"

func get_local_peer_id() -> int:
	return _local_peer_id

func get_connected_player_count() -> int:
	return _roster.size()

func get_roster_ids() -> PackedInt32Array:
	var ids := PackedInt32Array()
	for id_var: Variant in _roster.keys():
		ids.append(int(id_var))
	ids.sort()
	return ids

func get_status_text() -> String:
	match _mode:
		"host":
			return "HOST  %d/4  UDP:%d" % [_roster.size(), _port]
		"client":
			return "CONNECTED  PEER %d  %d/4" % [_local_peer_id, _roster.size()]
		"joining":
			return "CONNECTING..."
	return "OFFLINE"

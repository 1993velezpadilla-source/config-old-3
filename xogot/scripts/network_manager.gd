extends Node
class_name XzNetworkManager

signal session_state_changed(state: String)
signal roster_changed(peer_ids: PackedInt32Array)
signal network_error(message: String)
signal matchmaking_state_changed(phase: String, ready_count: int, player_count: int, countdown: float)
signal reconnect_state_changed(state: String, attempt: int, grace_remaining: float)

const REMOTE_PROXY_SCRIPT := preload("res://scripts/network_player_proxy.gd")
const WeaponCatalog = preload("res://scripts/weapon_catalog.gd")
const ZOMBIE_SCRIPT := preload("res://scripts/zombie_dummy.gd")
const SERVER_PEER_ID := 1
const DEFAULT_PORT := 7777
const MAX_PLAYERS := 4
const SNAPSHOT_INTERVAL := 0.05
const ZOMBIE_SNAPSHOT_INTERVAL := 0.10
const SESSION_SNAPSHOT_INTERVAL := 0.20
const MAX_SNAPSHOT_DELTA := 3.0
const MAX_PITCH := 1.51
const MAX_HIT_DISTANCE := 130.0
const MATCH_START_COUNTDOWN := 3.0
const RECONNECT_GRACE_MS := 45000
const RECONNECT_WATCHDOG_MS := 8000
const RECONNECT_MAX_ATTEMPTS := 12

var _peer: MultiplayerPeer
var _mode: String = "offline"
var _session_private: bool = true
var _port: int = DEFAULT_PORT
var _transport: String = "enet"
var _dedicated_server: bool = false
var _relay_url: String = ""
var _public_relay_fallback_pending: bool = false
var _local_peer_id: int = SERVER_PEER_ID
var _snapshot_timer: float = 0.0
var _zombie_snapshot_timer: float = 0.0
var _session_snapshot_timer: float = 0.0
var _sequence: int = 0
var _roster: Dictionary = {}
var _remote_players: Dictionary = {}
var _network_zombies: Dictionary = {}
var _accepted_positions: Dictionary = {}
var _peer_weapon_ids: Dictionary = {}
var _peer_weapon_upgraded: Dictionary = {}
var _match_phase: String = "idle"
var _ready_peers: Dictionary = {}
var _match_started: bool = false
var _match_countdown: float = 0.0
var _resume_token: String = ""
var _peer_resume_tokens: Dictionary = {}
var _peer_slots: Dictionary = {}
var _resume_snapshots: Dictionary = {}
var _local_player_slot: int = 0
var _last_server_activity_ms: int = 0
var _reconnect_active: bool = false
var _reconnect_attempt: int = 0
var _reconnect_generation: int = 0
var _reconnect_attempt_scheduled: bool = false
var _reconnect_base_url: String = ""

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	_bind_multiplayer_signals()
	_configure_local_player(SERVER_PEER_ID)
	_roster[SERVER_PEER_ID] = true
	_resume_token = _load_or_create_resume_token()
	call_deferred("_bind_public_reachability")
	print("XZOGOT_NETWORK_MANAGER_READY port=", DEFAULT_PORT, " max_players=", MAX_PLAYERS)

func _bind_public_reachability() -> void:
	var upnp: Node = _upnp_node()
	if upnp == null or not upnp.has_signal("mapping_finished"):
		return
	var cb := Callable(self, "_on_upnp_mapping_finished")
	if not upnp.is_connected("mapping_finished", cb):
		upnp.connect("mapping_finished", cb)
	print("XZOGOT_NETWORK_PUBLIC_REACHABILITY_BOUND")

func _on_upnp_mapping_finished(success: bool, external_ip: String, port: int, status: String) -> void:
	if _mode != "host" or _session_private:
		return
	if not success:
		print("XZOGOT_NETWORK_PUBLIC_REACHABILITY_UNAVAILABLE status=", status)
		return
	print("XZOGOT_NETWORK_PUBLIC_REACHABLE ", external_ip, ":", port)
	var directory: Node = _public_directory()
	if directory != null and directory.has_method("register_public_host"):
		if bool(directory.call("is_configured")):
			directory.call("register_public_host")
		else:
			print("XZOGOT_PUBLIC_DIRECTORY_NOT_CONFIGURED")

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

func _discovery() -> Node:
	return get_parent().get_node_or_null("NetworkDiscovery")

func _upnp_node() -> Node:
	return get_parent().get_node_or_null("NetworkUPNP")

func _public_directory() -> Node:
	return get_parent().get_node_or_null("PublicMatchDirectory")

func _valid_resume_token(token: String) -> bool:
	if token.length() < 16 or token.length() > 96:
		return false
	const ALLOWED := "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
	for index in range(token.length()):
		if ALLOWED.find(token.substr(index, 1)) < 0:
			return false
	return true

func _new_resume_token() -> String:
	var crypto := Crypto.new()
	var bytes := crypto.generate_random_bytes(24)
	return bytes.hex_encode()

func _load_or_create_resume_token() -> String:
	var env_token := OS.get_environment("XZOGOT_RESUME_TOKEN").strip_edges()
	if _valid_resume_token(env_token):
		return env_token
	if OS.has_feature("mobile"):
		var path := "user://xz_public_resume_token.txt"
		if FileAccess.file_exists(path):
			var read_file := FileAccess.open(path, FileAccess.READ)
			if read_file != null:
				var stored := read_file.get_as_text().strip_edges()
				if _valid_resume_token(stored):
					return stored
		var generated := _new_resume_token()
		var write_file := FileAccess.open(path, FileAccess.WRITE)
		if write_file != null:
			write_file.store_string(generated)
		return generated
	return _new_resume_token()

func _url_with_resume_token(base_url: String) -> String:
	if not _valid_resume_token(_resume_token):
		_resume_token = _load_or_create_resume_token()
	var separator := "&" if base_url.contains("?") else "?"
	return base_url + separator + "resume=" + _resume_token

func _mark_server_activity() -> void:
	_last_server_activity_ms = Time.get_ticks_msec()

func _reserved_slots() -> Dictionary:
	var used := {}
	for slot_var: Variant in _peer_slots.values():
		var slot := int(slot_var)
		if slot > 0:
			used[slot] = true
	for snapshot_var: Variant in _resume_snapshots.values():
		if snapshot_var is Dictionary:
			var slot := int((snapshot_var as Dictionary).get("slot", 0))
			if slot > 0:
				used[slot] = true
	return used

func _next_available_slot() -> int:
	var used := _reserved_slots()
	for slot in range(1, MAX_PLAYERS + 1):
		if not used.has(slot):
			return slot
	return 0

func _resume_snapshot_count() -> int:
	return _resume_snapshots.size()

func _capture_resume_snapshot(peer_id: int) -> void:
	if not _dedicated_server:
		return
	var token := str(_peer_resume_tokens.get(peer_id, ""))
	if not _valid_resume_token(token):
		return
	var player: Node = _network_player_node(peer_id)
	if player == null or not player.has_method("export_resume_state"):
		return
	var slot := int(_peer_slots.get(peer_id, 0))
	var snapshot := player.call("export_resume_state", slot) as Dictionary
	snapshot["ready"] = bool(_ready_peers.get(peer_id, false))
	snapshot["match_started"] = _match_started
	snapshot["expires_ms"] = Time.get_ticks_msec() + RECONNECT_GRACE_MS
	_resume_snapshots[token] = snapshot
	print(
		"XZOGOT_RECONNECT_RESERVED slot=", slot,
		" peer=", peer_id,
		" grace_ms=", RECONNECT_GRACE_MS
	)

func _expire_resume_snapshots() -> void:
	if _resume_snapshots.is_empty():
		return
	var now := Time.get_ticks_msec()
	var expired := PackedStringArray()
	for token_var: Variant in _resume_snapshots.keys():
		var token := str(token_var)
		var snapshot := _resume_snapshots[token] as Dictionary
		if int(snapshot.get("expires_ms", 0)) <= now:
			expired.append(token)
	for token: String in expired:
		var snapshot := _resume_snapshots[token] as Dictionary
		print("XZOGOT_RECONNECT_EXPIRED slot=", int(snapshot.get("slot", 0)))
		_resume_snapshots.erase(token)
	if _dedicated_server and _roster.is_empty() and _resume_snapshots.is_empty():
		_reset_dedicated_match()
	elif _dedicated_server and not _match_started and _resume_snapshots.is_empty():
		_recompute_matchmaking_phase()

func _set_reconnecting_phase() -> void:
	_match_phase = "reconnecting"
	_match_countdown = 0.0
	_broadcast_matchmaking_state()

@rpc("any_peer", "call_remote", "reliable")
func _server_register_resume_token(token: String) -> void:
	if not multiplayer.is_server() or not _dedicated_server or not _valid_resume_token(token):
		return
	var sender := multiplayer.get_remote_sender_id()
	if sender <= SERVER_PEER_ID or not _roster.has(sender):
		return
	_peer_resume_tokens[sender] = token
	var now := Time.get_ticks_msec()
	var resumed := false
	var slot := int(_peer_slots.get(sender, 0))
	if _resume_snapshots.has(token):
		var snapshot := _resume_snapshots[token] as Dictionary
		if int(snapshot.get("expires_ms", 0)) > now:
			resumed = true
			slot = int(snapshot.get("slot", slot))
			_peer_slots[sender] = slot
			var proxy: Node = _ensure_remote_proxy(sender)
			if proxy != null and proxy.has_method("apply_resume_state"):
				proxy.call("apply_resume_state", snapshot)
			_accepted_positions[sender] = snapshot.get("position", Vector3.ZERO) as Vector3
			var weapon_state := snapshot.get("weapon", {}) as Dictionary
			_peer_weapon_ids[sender] = str(weapon_state.get("id", WeaponCatalog.STARTING_WEAPON_ID))
			_peer_weapon_upgraded[sender] = bool(weapon_state.get("upgraded", false))
			if bool(snapshot.get("ready", false)):
				_ready_peers[sender] = true
			else:
				_ready_peers.erase(sender)
			_resume_snapshots.erase(token)
			if bool(snapshot.get("match_started", false)):
				_match_started = true
				_match_phase = "started"
				_set_dedicated_gameplay_active(true)
			elif _resume_snapshots.is_empty():
				_recompute_matchmaking_phase()
			else:
				_set_reconnecting_phase()
	if slot <= 0:
		slot = _next_available_slot()
		if slot <= 0:
			print("XZOGOT_RECONNECT_NO_SLOT peer=", sender)
			if _peer != null:
				_peer.disconnect_peer(sender, true)
			return
		_peer_slots[sender] = slot
	rpc_id(sender, "_client_resume_accepted", slot, resumed, RECONNECT_GRACE_MS)
	_broadcast_roster()
	_send_inventory_state(sender)
	_send_late_join_state(sender)
	_send_matchmaking_state(sender)
	_relay_player_state(sender, _sequence)
	print(
		"XZOGOT_RECONNECT_REGISTERED peer=", sender,
		" slot=", slot,
		" resumed=", resumed
	)

@rpc("authority", "call_remote", "reliable")
func _client_resume_accepted(slot: int, resumed: bool, grace_ms: int) -> void:
	if multiplayer.is_server():
		return
	_mark_server_activity()
	_local_player_slot = maxi(0, slot)
	var was_reconnecting := _reconnect_active
	_reconnect_active = false
	_reconnect_attempt = 0
	_reconnect_attempt_scheduled = false
	_mode = "client"
	session_state_changed.emit(_mode)
	reconnect_state_changed.emit("connected", 0, float(grace_ms) / 1000.0)
	print(
		"XZOGOT_RECONNECT_ACCEPTED slot=", _local_player_slot,
		" resumed=", resumed,
		" handover=", was_reconnecting
	)

func _ready_count() -> int:
	var count := 0
	for peer_var: Variant in _ready_peers.keys():
		var peer_id := int(peer_var)
		if _roster.has(peer_id) and bool(_ready_peers[peer_id]):
			count += 1
	return count

func _ready_ids() -> PackedInt32Array:
	var ids := PackedInt32Array()
	for peer_var: Variant in _ready_peers.keys():
		var peer_id := int(peer_var)
		if _roster.has(peer_id) and bool(_ready_peers[peer_id]):
			ids.append(peer_id)
	ids.sort()
	return ids

func _all_current_players_ready() -> bool:
	return not _roster.is_empty() and _ready_count() == _roster.size()

func _emit_matchmaking_state() -> void:
	matchmaking_state_changed.emit(
		_match_phase,
		_ready_count(),
		_roster.size(),
		maxf(0.0, _match_countdown)
	)

func _set_dedicated_gameplay_active(active: bool) -> void:
	var rounds: Node = _round_manager()
	if rounds != null and rounds.has_method("set_network_match_active"):
		rounds.call("set_network_match_active", active)
	var powerups: Node = _powerup_manager()
	if powerups != null:
		powerups.set_process(active)
	print("XZOGOT_MATCH_GAMEPLAY_ACTIVE ", active)

func _reset_dedicated_match() -> void:
	if _roster.is_empty():
		_resume_snapshots.clear()
		_peer_resume_tokens.clear()
		_peer_slots.clear()
	_ready_peers.clear()
	_match_started = false
	_match_countdown = 0.0
	_match_phase = "searching"
	var rounds: Node = _round_manager()
	if rounds != null:
		if rounds.has_method("reset_network_match"):
			rounds.call("reset_network_match")
		if rounds.has_method("set_network_match_active"):
			rounds.call("set_network_match_active", false)
	var powerups: Node = _powerup_manager()
	if powerups != null:
		if powerups.has_method("reset_for_match"):
			powerups.call("reset_for_match")
		powerups.set_process(false)
	_emit_matchmaking_state()
	print("XZOGOT_MATCH_RESET_WAITING")

func _broadcast_matchmaking_state() -> void:
	if multiplayer.is_server():
		rpc(
			"_client_receive_matchmaking_state",
			_match_phase,
			_ready_ids(),
			maxf(0.0, _match_countdown)
		)
	_emit_matchmaking_state()

func _send_matchmaking_state(peer_id: int) -> void:
	if not multiplayer.is_server() or not multiplayer.get_peers().has(peer_id):
		return
	rpc_id(
		peer_id,
		"_client_receive_matchmaking_state",
		_match_phase,
		_ready_ids(),
		maxf(0.0, _match_countdown)
	)

func _recompute_matchmaking_phase() -> void:
	if not _dedicated_server or _match_started:
		return
	if _roster.is_empty():
		_match_phase = "searching"
		_match_countdown = 0.0
	elif _all_current_players_ready():
		if _match_phase != "starting":
			_match_countdown = MATCH_START_COUNTDOWN
		_match_phase = "starting"
	else:
		_match_phase = "found"
		_match_countdown = 0.0
	_broadcast_matchmaking_state()
	print(
		"XZOGOT_MATCH_STATE phase=", _match_phase,
		" ready=", _ready_count(), "/", _roster.size(),
		" countdown=", _match_countdown
	)

func _update_matchmaking(delta: float) -> void:
	if not _dedicated_server or _match_started or _match_phase != "starting":
		return
	if not _all_current_players_ready():
		_recompute_matchmaking_phase()
		return
	_match_countdown = maxf(0.0, _match_countdown - delta)
	if _match_countdown <= 0.0:
		_match_started = true
		_match_phase = "started"
		_set_dedicated_gameplay_active(true)
		_broadcast_matchmaking_state()
		print("XZOGOT_MATCH_STARTED players=", _roster.size())
		return
	_emit_matchmaking_state()

@rpc("authority", "call_remote", "reliable")
func _client_receive_matchmaking_state(
	phase: String,
	ready_ids: PackedInt32Array,
	countdown: float
) -> void:
	if multiplayer.is_server():
		return
	_mark_server_activity()
	_match_phase = phase
	_match_started = phase == "started"
	_match_countdown = maxf(0.0, countdown)
	_ready_peers.clear()
	for peer_id: int in ready_ids:
		_ready_peers[peer_id] = true
	_emit_matchmaking_state()
	print(
		"XZOGOT_MATCH_CLIENT_STATE phase=", _match_phase,
		" ready=", _ready_count(), "/", _roster.size(),
		" countdown=", _match_countdown
	)

@rpc("any_peer", "call_remote", "reliable")
func _server_set_ready(ready: bool) -> void:
	if not multiplayer.is_server() or not _dedicated_server or _match_started:
		return
	var sender := multiplayer.get_remote_sender_id()
	if sender <= SERVER_PEER_ID or not _roster.has(sender):
		return
	if ready:
		_ready_peers[sender] = true
	else:
		_ready_peers.erase(sender)
	_recompute_matchmaking_phase()
	print("XZOGOT_MATCH_READY peer=", sender, " ready=", ready)

func _configure_local_player(peer_id: int) -> void:
	var player: Node = _local_player()
	if player == null:
		return
	_local_peer_id = peer_id
	player.set_meta("network_peer_id", peer_id)
	player.set_meta("network_remote", false)
	player.set_meta("network_session", _mode)

func _set_dedicated_local_player(enabled: bool) -> void:
	var player: Node = _local_player()
	if player == null:
		return
	if enabled:
		if player.is_in_group("player"):
			player.remove_from_group("player")
	else:
		if not player.is_in_group("player"):
			player.add_to_group("player")
	player.set_process(not enabled)
	player.set_physics_process(not enabled)
	player.set_process_unhandled_input(not enabled)
	if player is Node3D:
		(player as Node3D).visible = not enabled
	print("XZOGOT_NETWORK_DEDICATED_LOCAL_PLAYER disabled=", enabled)

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
	_transport = "enet"
	_dedicated_server = false
	_relay_url = ""
	_local_peer_id = SERVER_PEER_ID
	_roster.clear()
	_roster[SERVER_PEER_ID] = true
	_accepted_positions.clear()
	var player: Node3D = _local_player() as Node3D
	if player != null:
		_accepted_positions[SERVER_PEER_ID] = player.global_position
	_configure_local_player(SERVER_PEER_ID)
	_set_client_simulation(false)
	var discovery: Node = _discovery()
	if discovery != null:
		if private_session:
			if discovery.has_method("stop_advertising"):
				discovery.call("stop_advertising")
		elif discovery.has_method("start_advertising"):
			var discovery_err: int = int(discovery.call("start_advertising", port, "YOU WON'T WIN", "CHURCH", 7778))
			if discovery_err != OK:
				network_error.emit("LAN_ADVERTISE_FAILED_%d" % discovery_err)
				print("XZOGOT_NETWORK_LAN_ADVERTISE_FAIL ", discovery_err)

	var upnp: Node = _upnp_node()
	if upnp != null:
		if private_session:
			if upnp.has_method("clear_mapping"):
				upnp.call("clear_mapping")
		elif upnp.has_method("request_mapping"):
			# Public internet reachability is best-effort. ENet/LAN hosting stays
			# live even when the router has UPnP disabled or unsupported.
			var mapping_started: bool = bool(upnp.call("request_mapping", port))
			print("XZOGOT_NETWORK_UPNP_REQUEST started=", mapping_started, " port=", port)
	session_state_changed.emit(_mode)
	_emit_roster()
	print("XZOGOT_NETWORK_HOST_READY port=", port, " slots=", MAX_PLAYERS, " private=", private_session)
	return OK

func host_websocket_dedicated(port: int, bind_address: String = "*") -> Error:
	leave_game()
	var next_peer := WebSocketMultiplayerPeer.new()
	var clean_bind := bind_address.strip_edges()
	if clean_bind.is_empty():
		clean_bind = "*"
	var err: Error = next_peer.create_server(port, clean_bind)
	if err != OK:
		network_error.emit("WS_HOST_FAILED_%d" % int(err))
		print("XZOGOT_WS_HOST_FAIL ", err)
		return err
	_peer = next_peer
	multiplayer.multiplayer_peer = _peer
	_mode = "host"
	_session_private = false
	_port = port
	_transport = "websocket"
	_dedicated_server = true
	_relay_url = ""
	_local_peer_id = SERVER_PEER_ID
	_roster.clear()
	_accepted_positions.clear()
	_peer_weapon_ids.clear()
	_peer_weapon_upgraded.clear()
	_set_dedicated_local_player(true)
	_set_client_simulation(false)
	_reset_dedicated_match()
	session_state_changed.emit(_mode)
	_emit_roster()
	print("XZOGOT_WS_DEDICATED_READY port=", port, " bind=", clean_bind, " human_slots=", MAX_PLAYERS)
	return OK

func _open_websocket_connection(base_url: String, reconnecting: bool) -> Error:
	var clean_url := base_url.strip_edges()
	if not clean_url.begins_with("ws://") and not clean_url.begins_with("wss://"):
		return ERR_INVALID_PARAMETER
	if _peer != null:
		_peer.close()
	var next_peer := WebSocketMultiplayerPeer.new()
	var err: Error = next_peer.create_client(_url_with_resume_token(clean_url))
	if err != OK:
		print("XZOGOT_WS_JOIN_FAIL ", err)
		return err
	_peer = next_peer
	multiplayer.multiplayer_peer = _peer
	_mode = "reconnecting" if reconnecting else "joining"
	_transport = "websocket"
	_dedicated_server = false
	_relay_url = clean_url
	_reconnect_base_url = clean_url
	if not reconnecting:
		_match_phase = "searching"
		_match_started = false
		_match_countdown = 0.0
		_ready_peers.clear()
		_local_player_slot = 0
	_set_client_simulation(true)
	_mark_server_activity()
	_emit_matchmaking_state()
	session_state_changed.emit(_mode)
	print("XZOGOT_WS_JOINING ", clean_url, " reconnect=", reconnecting)
	return OK

func join_websocket_game(url: String) -> Error:
	var clean_url := url.strip_edges()
	if not clean_url.begins_with("ws://") and not clean_url.begins_with("wss://"):
		return ERR_INVALID_PARAMETER
	leave_game()
	_reconnect_active = false
	_reconnect_attempt = 0
	_reconnect_attempt_scheduled = false
	return _open_websocket_connection(clean_url, false)

func _schedule_next_reconnect() -> void:
	if not _reconnect_active or _reconnect_attempt_scheduled:
		return
	if _reconnect_attempt >= RECONNECT_MAX_ATTEMPTS:
		_reconnect_active = false
		_reconnect_attempt_scheduled = false
		network_error.emit("RECONNECT_TIMEOUT")
		reconnect_state_changed.emit("failed", _reconnect_attempt, 0.0)
		print("XZOGOT_RECONNECT_GAVE_UP attempts=", _reconnect_attempt)
		return
	var delay := 0.0 if _reconnect_attempt == 0 else minf(5.0, float(_reconnect_attempt))
	_reconnect_attempt_scheduled = true
	var generation := _reconnect_generation
	call_deferred("_reconnect_attempt_after_delay", generation, delay)

func _reconnect_attempt_after_delay(generation: int, delay: float) -> void:
	if delay > 0.0:
		await get_tree().create_timer(delay, true, false, true).timeout
	if generation != _reconnect_generation or not _reconnect_active:
		return
	_reconnect_attempt_scheduled = false
	_reconnect_attempt += 1
	reconnect_state_changed.emit("reconnecting", _reconnect_attempt, float(RECONNECT_GRACE_MS) / 1000.0)
	print("XZOGOT_RECONNECT_ATTEMPT ", _reconnect_attempt)
	var err := _open_websocket_connection(_reconnect_base_url, true)
	if err != OK:
		_schedule_next_reconnect()

func _begin_public_reconnect(reason: String) -> void:
	if _transport != "websocket" or _relay_url.is_empty():
		return
	if _reconnect_active:
		_schedule_next_reconnect()
		return
	_reconnect_active = true
	_reconnect_attempt = 0
	_reconnect_attempt_scheduled = false
	_reconnect_generation += 1
	_reconnect_base_url = _relay_url
	_mode = "reconnecting"
	_match_phase = "reconnecting"
	_clear_remote_players()
	_clear_network_zombies()
	_roster.clear()
	_roster[_local_peer_id] = true
	_emit_roster()
	_emit_matchmaking_state()
	session_state_changed.emit(_mode)
	reconnect_state_changed.emit("reconnecting", 0, float(RECONNECT_GRACE_MS) / 1000.0)
	if _peer != null:
		_peer.close()
	_peer = null
	multiplayer.multiplayer_peer = OfflineMultiplayerPeer.new()
	print("XZOGOT_RECONNECT_BEGIN reason=", reason)
	_schedule_next_reconnect()

func force_public_reconnect() -> bool:
	if _transport != "websocket" or (_mode != "client" and _mode != "reconnecting"):
		return false
	_begin_public_reconnect("forced")
	return true

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
	_transport = "enet"
	_dedicated_server = false
	_relay_url = ""
	_set_client_simulation(true)
	session_state_changed.emit(_mode)
	print("XZOGOT_NETWORK_JOINING address=", clean_address, " port=", port)
	return OK

func leave_game() -> void:
	_reconnect_generation += 1
	_reconnect_active = false
	_reconnect_attempt = 0
	_reconnect_attempt_scheduled = false
	var discovery: Node = _discovery()
	if discovery != null:
		if discovery.has_method("stop_advertising"):
			discovery.call("stop_advertising")
		if discovery.has_method("stop_discovery"):
			discovery.call("stop_discovery")
	var directory: Node = _public_directory()
	if directory != null and directory.has_method("unregister_public_host"):
		directory.call("unregister_public_host")
	var upnp: Node = _upnp_node()
	if upnp != null and upnp.has_method("clear_mapping"):
		upnp.call("clear_mapping")
	if _peer != null:
		_peer.close()
	_peer = null
	multiplayer.multiplayer_peer = OfflineMultiplayerPeer.new()
	_clear_remote_players()
	_clear_network_zombies()
	var powerups: Node = _powerup_manager()
	if powerups != null and powerups.has_method("clear_network_pickups"):
		powerups.call("clear_network_pickups")
	_roster.clear()
	_roster[SERVER_PEER_ID] = true
	_accepted_positions.clear()
	_peer_weapon_ids.clear()
	_peer_weapon_upgraded.clear()
	_set_dedicated_local_player(false)
	_mode = "offline"
	_transport = "enet"
	_dedicated_server = false
	_relay_url = ""
	_public_relay_fallback_pending = false
	_match_phase = "idle"
	_match_started = false
	_match_countdown = 0.0
	_ready_peers.clear()
	_peer_resume_tokens.clear()
	_peer_slots.clear()
	_resume_snapshots.clear()
	_local_player_slot = 0
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
	if _roster.size() >= MAX_PLAYERS:
		if _peer != null:
			_peer.disconnect_peer(peer_id, true)
		print("XZOGOT_NETWORK_SESSION_FULL_REJECT peer=", peer_id)
		return
	_roster[peer_id] = true
	_peer_weapon_ids[peer_id] = WeaponCatalog.STARTING_WEAPON_ID
	_peer_weapon_upgraded[peer_id] = false
	var initial_slot := _next_available_slot()
	if initial_slot > 0:
		_peer_slots[peer_id] = initial_slot
	_ensure_remote_proxy(peer_id)
	_broadcast_roster()
	if _dedicated_server and not _match_started:
		_ready_peers.erase(peer_id)
		if _resume_snapshots.is_empty():
			_recompute_matchmaking_phase()
		else:
			_set_reconnecting_phase()
	print(
		"XZOGOT_NETWORK_PEER_JOIN peer=", peer_id,
		" count=", _roster.size(),
		" slot=", int(_peer_slots.get(peer_id, 0))
	)

func _on_peer_disconnected(peer_id: int) -> void:
	_capture_resume_snapshot(peer_id)
	_roster.erase(peer_id)
	_accepted_positions.erase(peer_id)
	_peer_weapon_ids.erase(peer_id)
	_peer_weapon_upgraded.erase(peer_id)
	_peer_resume_tokens.erase(peer_id)
	_peer_slots.erase(peer_id)
	_remove_remote_proxy(peer_id)
	_ready_peers.erase(peer_id)
	if multiplayer.is_server():
		_broadcast_roster()
		if _dedicated_server:
			if _roster.is_empty():
				if _resume_snapshots.is_empty():
					_reset_dedicated_match()
				else:
					_set_dedicated_gameplay_active(false)
					_set_reconnecting_phase()
			elif not _match_started:
				if _resume_snapshots.is_empty():
					_recompute_matchmaking_phase()
				else:
					_set_reconnecting_phase()
	_emit_roster()
	print(
		"XZOGOT_NETWORK_PEER_LEFT peer=", peer_id,
		" count=", _roster.size(),
		" reserved=", _resume_snapshot_count()
	)

func _on_connected_to_server() -> void:
	_mode = "client"
	_local_peer_id = multiplayer.get_unique_id()
	_roster.clear()
	_roster[_local_peer_id] = true
	_configure_local_player(_local_peer_id)
	_set_client_simulation(true)
	_mark_server_activity()
	if _transport == "websocket" and _valid_resume_token(_resume_token):
		rpc_id(SERVER_PEER_ID, "_server_register_resume_token", _resume_token)
	rpc_id(SERVER_PEER_ID, "_server_request_roster")
	session_state_changed.emit(_mode)
	print("XZOGOT_NETWORK_CLIENT_READY peer=", _local_peer_id)

func _on_connection_failed() -> void:
	if _reconnect_active:
		print("XZOGOT_RECONNECT_CONNECT_FAILED attempt=", _reconnect_attempt)
		_schedule_next_reconnect()
		return
	if _public_relay_fallback_pending and is_public_relay_configured():
		var relay_url := get_public_relay_endpoint()
		_public_relay_fallback_pending = false
		print("XZOGOT_NETWORK_DIRECT_FAILED_FALLBACK_RELAY ", relay_url)
		var relay_err := join_websocket_game(relay_url)
		if relay_err == OK:
			return
		print("XZOGOT_NETWORK_RELAY_FALLBACK_FAIL ", relay_err)
	network_error.emit("CONNECTION_FAILED")
	print("XZOGOT_NETWORK_CONNECTION_FAILED")
	leave_game()

func _on_server_disconnected() -> void:
	if _reconnect_active:
		print("XZOGOT_RECONNECT_SERVER_DROPPED attempt=", _reconnect_attempt)
		_schedule_next_reconnect()
		return
	if _transport == "websocket" and not _relay_url.is_empty():
		_begin_public_reconnect("server_disconnected")
		return
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
	_send_inventory_state(sender)
	_send_late_join_state(sender)
	_send_matchmaking_state(sender)

@rpc("authority", "call_remote", "reliable")
func _client_receive_roster(ids: PackedInt32Array) -> void:
	if multiplayer.is_server():
		return
	_mark_server_activity()
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
	if _mode != "host" and _mode != "client" and _mode != "reconnecting":
		return
	if _mode == "host" and _dedicated_server:
		_expire_resume_snapshots()
		_update_matchmaking(delta)
		if _roster.is_empty():
			return
	if _mode == "client" and _transport == "websocket" and not _reconnect_active:
		var now := Time.get_ticks_msec()
		if _last_server_activity_ms > 0 and now - _last_server_activity_ms > RECONNECT_WATCHDOG_MS:
			_begin_public_reconnect("snapshot_watchdog")
			return
	if _mode == "reconnecting":
		return

	_snapshot_timer -= delta
	if _snapshot_timer <= 0.0:
		_snapshot_timer = SNAPSHOT_INTERVAL
		_sequence += 1
		if _mode == "host":
			if not _dedicated_server:
				_broadcast_host_player_state()
			_broadcast_authoritative_remote_states()
		else:
			_send_client_motion()

	if _mode == "host":
		_zombie_snapshot_timer -= delta
		if _zombie_snapshot_timer <= 0.0:
			_zombie_snapshot_timer = ZOMBIE_SNAPSHOT_INTERVAL
			_broadcast_zombie_states()

		_session_snapshot_timer -= delta
		if _session_snapshot_timer <= 0.0:
			_session_snapshot_timer = SESSION_SNAPSHOT_INTERVAL
			_broadcast_session_state()

func _safe_pitch(player: Node) -> float:
	var head: Node3D = player.get_node_or_null("Head") as Node3D
	return clampf(head.rotation.x if head != null else 0.0, -MAX_PITCH, MAX_PITCH)

func _send_client_motion() -> void:
	var player: Node3D = _local_player() as Node3D
	if player == null:
		return
	var weapon: Node = player.get_node_or_null("Weapon")
	var weapon_id: String = WeaponCatalog.STARTING_WEAPON_ID
	var upgraded: bool = false
	if weapon != null:
		weapon_id = str(weapon.get_meta("weapon_id", WeaponCatalog.STARTING_WEAPON_ID))
		upgraded = bool(weapon.get_meta("weapon_upgraded", false))
	rpc_id(
		SERVER_PEER_ID,
		"_server_submit_motion",
		player.global_position,
		player.rotation.y,
		_safe_pitch(player),
		weapon_id,
		upgraded,
		_sequence
	)

@rpc("any_peer", "call_remote", "unreliable_ordered", 1)
func _server_submit_motion(
	pos: Vector3,
	yaw: float,
	pitch: float,
	weapon_id: String,
	upgraded: bool,
	sequence: int
) -> void:
	if not multiplayer.is_server():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	if sender <= SERVER_PEER_ID or not _roster.has(sender):
		return
	if not pos.is_finite() or not is_finite(yaw) or not is_finite(pitch):
		return
	# Client-reported loadout is telemetry only. Purchases/upgrades are owned
	# by the host-side Weapon node on the remote player proxy.
	if not WeaponCatalog.has_weapon(weapon_id):
		weapon_id = WeaponCatalog.STARTING_WEAPON_ID
	if upgraded and not bool(_authoritative_weapon_state(sender).get("upgraded", false)):
		print("XZOGOT_NETWORK_LOADOUT_CLAIM_IGNORED peer=", sender)
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
			float(proxy.call("get_revive_progress_ratio")),
			int(proxy.call("get_points"))
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
	var points_value: int = int(node.call("get_points")) if node.has_method("get_points") else 500
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
		points_value,
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
	points_value: int,
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
		if local != null and local.has_method("apply_authoritative_network_points"):
			local.call("apply_authoritative_network_points", points_value)
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
			revive_ratio,
			points_value
		)

func _authoritative_weapon_state(peer_id: int) -> Dictionary:
	var player: Node = _network_player_node(peer_id)
	if player == null:
		return {
			"id": WeaponCatalog.STARTING_WEAPON_ID,
			"magazine": 8,
			"reserve": 80,
			"upgraded": false,
		}
	var weapon: Node = player.get_node_or_null("Weapon")
	if weapon == null:
		return {
			"id": WeaponCatalog.STARTING_WEAPON_ID,
			"magazine": 8,
			"reserve": 80,
			"upgraded": false,
		}
	if weapon.has_method("get_authoritative_state"):
		return weapon.call("get_authoritative_state") as Dictionary
	return {
		"id": str(weapon.call("get_weapon_id")) if weapon.has_method("get_weapon_id") else WeaponCatalog.STARTING_WEAPON_ID,
		"magazine": int(weapon.call("get_magazine")) if weapon.has_method("get_magazine") else 8,
		"reserve": int(weapon.call("get_reserve")) if weapon.has_method("get_reserve") else 80,
		"upgraded": bool(weapon.call("is_upgraded")) if weapon.has_method("is_upgraded") else false,
	}

func _authoritative_perks(peer_id: int) -> Array[String]:
	var player: Node = _network_player_node(peer_id)
	if player != null and player.has_method("get_owned_perks"):
		return player.call("get_owned_perks") as Array[String]
	return []

func _host_zombie_by_id(zombie_id: String) -> Node:
	for zombie: Node in get_tree().get_nodes_in_group("zombie"):
		if bool(zombie.get_meta("network_proxy", false)):
			continue
		if zombie.name == zombie_id:
			return zombie
	return null

func _ensure_network_zombie(zombie_id: String) -> Node:
	if _network_zombies.has(zombie_id):
		var existing: Node = _network_zombies[zombie_id] as Node
		if is_instance_valid(existing):
			return existing
	var zombie := CharacterBody3D.new()
	zombie.name = zombie_id
	zombie.set_script(ZOMBIE_SCRIPT)
	zombie.set_meta("network_proxy_boot", true)
	get_parent().add_child(zombie)
	zombie.call("set_network_proxy_mode", true)
	_network_zombies[zombie_id] = zombie
	return zombie

func _remove_network_zombie(zombie_id: String) -> void:
	if not _network_zombies.has(zombie_id):
		return
	var zombie: Node = _network_zombies[zombie_id] as Node
	_network_zombies.erase(zombie_id)
	if is_instance_valid(zombie):
		zombie.queue_free()

func _clear_network_zombies() -> void:
	for id_var: Variant in _network_zombies.keys().duplicate():
		_remove_network_zombie(str(id_var))
	_network_zombies.clear()

func _broadcast_zombie_states() -> void:
	if not multiplayer.is_server():
		return
	var states: Array = []
	for zombie: Node in get_tree().get_nodes_in_group("zombie"):
		if not (zombie is Node3D) or bool(zombie.get_meta("network_proxy", false)):
			continue
		var body := zombie as Node3D
		states.append([
			zombie.name,
			body.global_position,
			body.rotation.y,
			float(zombie.call("get_health")) if zombie.has_method("get_health") else 0.0,
			int(zombie.call("get_phase")) if zombie.has_method("get_phase") else 0,
			bool(zombie.call("is_crawler")) if zombie.has_method("is_crawler") else false,
			bool(zombie.call("is_headless")) if zombie.has_method("is_headless") else false,
		])
	rpc("_client_receive_zombie_states", states)

@rpc("authority", "call_remote", "unreliable_ordered", 3)
func _client_receive_zombie_states(states: Array) -> void:
	if multiplayer.is_server():
		return
	var seen: Dictionary = {}
	for state_var: Variant in states:
		if not (state_var is Array):
			continue
		var state: Array = state_var as Array
		if state.size() < 7:
			continue
		var zombie_id: String = str(state[0])
		seen[zombie_id] = true
		var zombie: Node = _ensure_network_zombie(zombie_id)
		if zombie != null and zombie.has_method("apply_network_proxy_state"):
			zombie.call(
				"apply_network_proxy_state",
				state[1] as Vector3,
				float(state[2]),
				float(state[3]),
				int(state[4]),
				bool(state[5]),
				bool(state[6])
			)
	for id_var: Variant in _network_zombies.keys().duplicate():
		var zombie_id: String = str(id_var)
		if not seen.has(zombie_id):
			_remove_network_zombie(zombie_id)

func submit_zombie_hit(zombie_id: String, hit_position: Vector3, melee: bool = false) -> bool:
	if _mode != "client":
		return false
	if zombie_id.is_empty() or not hit_position.is_finite():
		return false
	rpc_id(SERVER_PEER_ID, "_server_zombie_hit", zombie_id, hit_position, melee)
	return true

@rpc("any_peer", "call_remote", "reliable", 4)
func _server_zombie_hit(zombie_id: String, hit_position: Vector3, melee: bool) -> void:
	if not multiplayer.is_server():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	_server_apply_zombie_hit(sender, zombie_id, hit_position, melee)

func _server_apply_zombie_hit(
	peer_id: int,
	zombie_id: String,
	hit_position: Vector3,
	melee: bool
) -> bool:
	if peer_id <= SERVER_PEER_ID or not _roster.has(peer_id):
		return false
	var source: Node = _network_player_node(peer_id)
	var zombie: Node = _host_zombie_by_id(zombie_id)
	if source == null or zombie == null or not (source is Node3D):
		return false
	if (source as Node3D).global_position.distance_to(hit_position) > MAX_HIT_DISTANCE:
		print("XZOGOT_NETWORK_HIT_REJECT_RANGE peer=", peer_id)
		return false

	var damage_value: float = 150.0
	if not melee:
		var weapon_state: Dictionary = _authoritative_weapon_state(peer_id)
		var weapon_id: String = str(weapon_state.get("id", WeaponCatalog.STARTING_WEAPON_ID))
		if not WeaponCatalog.has_weapon(weapon_id):
			return false
		var def: Dictionary = WeaponCatalog.get_weapon(weapon_id)
		damage_value = float(def.get("damage", 30.0))
		if bool(weapon_state.get("upgraded", false)):
			damage_value *= 1.85
		if source.has_method("get_weapon_damage_multiplier"):
			damage_value *= float(source.call("get_weapon_damage_multiplier"))

	if melee and zombie.has_method("apply_melee_damage"):
		zombie.call("apply_melee_damage", damage_value, source, hit_position)
	elif zombie.has_method("apply_hitscan_damage"):
		zombie.call("apply_hitscan_damage", damage_value, source, hit_position)
	else:
		return false

	print(
		"XZOGOT_NETWORK_ZOMBIE_HIT peer=", peer_id,
		" zombie=", zombie_id,
		" damage=", damage_value,
		" melee=", melee
	)
	return true

func get_network_zombie_count() -> int:
	return _network_zombies.size()

func _build_session_snapshot() -> Dictionary:
	var rounds: Node = _round_manager()
	var powerups: Node = _powerup_manager()
	var snapshot := {
		"round": 0,
		"round_total": 0,
		"remaining": 0,
		"alive": 0,
		"break_remaining": 0.0,
		"double_points": 0.0,
		"insta_kill": 0.0,
		"pickups": [],
	}
	if rounds != null:
		snapshot["round"] = int(rounds.call("get_round")) if rounds.has_method("get_round") else 0
		snapshot["round_total"] = int(rounds.call("get_round_total")) if rounds.has_method("get_round_total") else 0
		snapshot["remaining"] = int(rounds.call("get_remaining_to_spawn")) if rounds.has_method("get_remaining_to_spawn") else 0
		snapshot["alive"] = int(rounds.call("get_alive")) if rounds.has_method("get_alive") else 0
		snapshot["break_remaining"] = float(rounds.call("get_round_break_remaining")) if rounds.has_method("get_round_break_remaining") else 0.0
	if powerups != null:
		snapshot["double_points"] = float(powerups.call("get_effect_remaining", "double_points")) if powerups.has_method("get_effect_remaining") else 0.0
		snapshot["insta_kill"] = float(powerups.call("get_effect_remaining", "insta_kill")) if powerups.has_method("get_effect_remaining") else 0.0
		snapshot["pickups"] = powerups.call("get_network_pickup_states") if powerups.has_method("get_network_pickup_states") else []
	return snapshot

func _apply_session_snapshot(snapshot: Dictionary) -> void:
	var rounds: Node = _round_manager()
	if rounds != null and rounds.has_method("apply_network_round_state"):
		rounds.call(
			"apply_network_round_state",
			int(snapshot.get("round", 0)),
			int(snapshot.get("round_total", 0)),
			int(snapshot.get("remaining", 0)),
			int(snapshot.get("alive", 0)),
			float(snapshot.get("break_remaining", 0.0))
		)
	var powerups: Node = _powerup_manager()
	if powerups != null:
		if powerups.has_method("apply_network_effect_state"):
			powerups.call(
				"apply_network_effect_state",
				float(snapshot.get("double_points", 0.0)),
				float(snapshot.get("insta_kill", 0.0))
			)
		if powerups.has_method("apply_network_pickup_snapshot"):
			powerups.call("apply_network_pickup_snapshot", snapshot.get("pickups", []) as Array)
	print(
		"XZOGOT_NETWORK_SESSION_STATE round=", int(snapshot.get("round", 0)),
		" pickups=", (snapshot.get("pickups", []) as Array).size()
	)

func _broadcast_session_state() -> void:
	if not multiplayer.is_server():
		return
	rpc("_client_receive_session_state", _build_session_snapshot())

func _send_session_state(peer_id: int) -> void:
	if not multiplayer.is_server() or not multiplayer.get_peers().has(peer_id):
		return
	rpc_id(peer_id, "_client_receive_session_state", _build_session_snapshot())

@rpc("authority", "call_remote", "unreliable_ordered", 9)
func _client_receive_session_state(snapshot: Dictionary) -> void:
	if multiplayer.is_server():
		return
	_mark_server_activity()
	_apply_session_snapshot(snapshot)

func _build_late_join_snapshot() -> Dictionary:
	var interactions: Array = []
	for target: Node in get_tree().get_nodes_in_group("zombie_interactable"):
		if not target.has_method("was_used"):
			continue
		# Only persistent world switches belong in the initial snapshot.
		# Personal machines are restored from the joining player's inventory.
		var kind_value: int = int(target.get("interaction_kind"))
		if kind_value != 0 and kind_value != 4:
			continue
		var relative_path: String = _relative_world_path(target)
		if relative_path.is_empty():
			continue
		interactions.append([
			relative_path,
			bool(target.call("was_used")),
			bool(get_tree().get_meta("power_on", false)),
			str(target.call("get_last_result")) if target.has_method("get_last_result") else "",
		])

	var barricades: Array = []
	for barricade: Node in get_tree().get_nodes_in_group("zombie_barricade"):
		if not barricade.has_method("get_boards"):
			continue
		var relative_path: String = _relative_world_path(barricade)
		if relative_path.is_empty():
			continue
		barricades.append([relative_path, int(barricade.call("get_boards"))])

	return {
		"session": _build_session_snapshot(),
		"interactions": interactions,
		"barricades": barricades,
	}

func _apply_late_join_snapshot(snapshot: Dictionary) -> void:
	_apply_session_snapshot(snapshot.get("session", {}) as Dictionary)
	for state_var: Variant in snapshot.get("interactions", []) as Array:
		if not (state_var is Array):
			continue
		var state: Array = state_var as Array
		if state.size() < 4:
			continue
		_client_apply_interaction_state(
			str(state[0]),
			bool(state[1]),
			bool(state[2]),
			str(state[3])
		)
	for state_var: Variant in snapshot.get("barricades", []) as Array:
		if not (state_var is Array):
			continue
		var state: Array = state_var as Array
		if state.size() < 2:
			continue
		_client_apply_barricade_state(str(state[0]), int(state[1]))
	print(
		"XZOGOT_NETWORK_LATE_JOIN_STATE interactions=",
		(snapshot.get("interactions", []) as Array).size(),
		" barricades=",
		(snapshot.get("barricades", []) as Array).size()
	)

func _send_late_join_state(peer_id: int) -> void:
	if not multiplayer.is_server() or not multiplayer.get_peers().has(peer_id):
		return
	rpc_id(peer_id, "_client_receive_late_join_state", _build_late_join_snapshot())

@rpc("authority", "call_remote", "reliable", 10)
func _client_receive_late_join_state(snapshot: Dictionary) -> void:
	if multiplayer.is_server():
		return
	_apply_late_join_snapshot(snapshot)

func _relative_world_path(target: Node) -> String:
	if target == null or get_parent() == null:
		return ""
	return str(get_parent().get_path_to(target))

func submit_interaction(target: Node) -> bool:
	if _mode != "client" or target == null:
		return false
	var relative_path: String = _relative_world_path(target)
	if relative_path.is_empty() or relative_path.length() > 256:
		return false
	rpc_id(SERVER_PEER_ID, "_server_interaction_request", relative_path)
	print("XZOGOT_NETWORK_INTERACTION_REQUEST ", relative_path)
	return true

@rpc("any_peer", "call_remote", "reliable", 5)
func _server_interaction_request(relative_path: String) -> void:
	if not multiplayer.is_server():
		return
	var sender: int = multiplayer.get_remote_sender_id()
	_server_apply_interaction(sender, relative_path)

func _server_apply_interaction(peer_id: int, relative_path: String) -> bool:
	if peer_id <= SERVER_PEER_ID or not _roster.has(peer_id):
		return false
	if relative_path.is_empty() or relative_path.length() > 256:
		return false
	var player: Node = _network_player_node(peer_id)
	var target: Node = get_parent().get_node_or_null(NodePath(relative_path))
	if (
		player == null
		or target == null
		or not (player is Node3D)
		or not (target is Node3D)
		or not target.has_method("interact")
	):
		return false
	if (
		not target.is_in_group("zombie_interactable")
		and not target.is_in_group("zombie_barricade")
	):
		return false
	if player.has_method("is_downed") and bool(player.call("is_downed")):
		return false
	if player.has_method("is_eliminated") and bool(player.call("is_eliminated")):
		return false
	if (player as Node3D).global_position.distance_to((target as Node3D).global_position) > 5.0:
		print("XZOGOT_NETWORK_INTERACTION_REJECT_RANGE peer=", peer_id, " target=", relative_path)
		return false

	var success: bool = bool(target.call("interact", player))
	if not success:
		_send_inventory_state(peer_id)
		return false

	# Current interactable and barricade scripts notify the host manager from
	# their successful authoritative mutation, avoiding duplicate RPC traffic.
	print("XZOGOT_NETWORK_INTERACTION_ACCEPT peer=", peer_id, " target=", relative_path)
	return true

func notify_host_interaction(target: Node, player: Node) -> void:
	if _mode != "host" or not multiplayer.is_server() or target == null:
		return
	_broadcast_interaction_state(target)
	var peer_id: int = int(player.get_meta("network_peer_id", SERVER_PEER_ID)) if player != null else SERVER_PEER_ID
	if peer_id > SERVER_PEER_ID:
		_send_inventory_state(peer_id)

func notify_host_powerup(kind: String) -> void:
	if _mode != "host" or not multiplayer.is_server():
		return
	_broadcast_session_state()
	for peer_var: Variant in _roster.keys():
		var peer_id: int = int(peer_var)
		if peer_id > SERVER_PEER_ID:
			_send_inventory_state(peer_id)
	print("XZOGOT_NETWORK_POWERUP_SYNC ", kind)

func notify_host_barricade(target: Node, player: Node = null) -> void:
	if _mode != "host" or not multiplayer.is_server() or target == null:
		return
	_broadcast_barricade_state(target)
	var peer_id: int = int(player.get_meta("network_peer_id", SERVER_PEER_ID)) if player != null else SERVER_PEER_ID
	if peer_id > SERVER_PEER_ID:
		_send_inventory_state(peer_id)

func _broadcast_interaction_state(target: Node) -> void:
	if target == null:
		return
	var relative_path: String = _relative_world_path(target)
	if relative_path.is_empty():
		return
	var used: bool = bool(target.call("was_used")) if target.has_method("was_used") else false
	var last_result: String = str(target.call("get_last_result")) if target.has_method("get_last_result") else ""
	var power_on: bool = bool(get_tree().get_meta("power_on", false))
	rpc("_client_apply_interaction_state", relative_path, used, power_on, last_result)

@rpc("authority", "call_remote", "reliable", 6)
func _client_apply_interaction_state(
	relative_path: String,
	used: bool,
	power_on: bool,
	last_result: String
) -> void:
	if multiplayer.is_server():
		return
	var target: Node = get_parent().get_node_or_null(NodePath(relative_path))
	if target != null and target.has_method("apply_network_world_state"):
		target.call("apply_network_world_state", used, power_on, last_result)
	else:
		get_tree().set_meta("power_on", power_on)

func _broadcast_barricade_state(target: Node) -> void:
	if target == null or not target.has_method("get_boards"):
		return
	var relative_path: String = _relative_world_path(target)
	if relative_path.is_empty():
		return
	rpc("_client_apply_barricade_state", relative_path, int(target.call("get_boards")))

@rpc("authority", "call_remote", "reliable", 7)
func _client_apply_barricade_state(relative_path: String, boards: int) -> void:
	if multiplayer.is_server():
		return
	var target: Node = get_parent().get_node_or_null(NodePath(relative_path))
	if target != null and target.has_method("apply_network_boards"):
		target.call("apply_network_boards", boards)

func _send_inventory_state(peer_id: int) -> void:
	if not multiplayer.is_server() or peer_id <= SERVER_PEER_ID or not _roster.has(peer_id):
		return
	if not multiplayer.get_peers().has(peer_id):
		# Unit/runtime probes can create an authoritative proxy without a real
		# socket peer. Production peers are present here, so only skip synthetic
		# destinations instead of generating RPC errors.
		return
	var player: Node = _network_player_node(peer_id)
	if player == null:
		return
	var weapon_state: Dictionary = _authoritative_weapon_state(peer_id)
	rpc_id(
		peer_id,
		"_client_receive_inventory_state",
		int(player.call("get_points")) if player.has_method("get_points") else 500,
		_authoritative_perks(peer_id),
		str(weapon_state.get("id", WeaponCatalog.STARTING_WEAPON_ID)),
		int(weapon_state.get("magazine", 8)),
		int(weapon_state.get("reserve", 80)),
		bool(weapon_state.get("upgraded", false))
	)

@rpc("authority", "call_remote", "reliable", 8)
func _client_receive_inventory_state(
	points_value: int,
	perks: Array[String],
	weapon_id: String,
	magazine: int,
	reserve: int,
	upgraded: bool
) -> void:
	if multiplayer.is_server():
		return
	_mark_server_activity()
	var player: Node = _local_player()
	if player != null:
		if player.has_method("apply_authoritative_network_points"):
			player.call("apply_authoritative_network_points", points_value)
		if player.has_method("apply_authoritative_network_perks"):
			player.call("apply_authoritative_network_perks", perks)
		var weapon: Node = player.get_node_or_null("Weapon")
		if weapon != null and weapon.has_method("apply_authoritative_network_loadout"):
			weapon.call(
				"apply_authoritative_network_loadout",
				weapon_id,
				magazine,
				reserve,
				upgraded
			)
	print(
		"XZOGOT_NETWORK_INVENTORY_SYNC points=", points_value,
		" perks=", perks.size(),
		" weapon=", weapon_id,
		" upgraded=", upgraded
	)

func _network_player_node(peer_id: int) -> Node:
	if peer_id == SERVER_PEER_ID and multiplayer.is_server():
		return null if _dedicated_server else _local_player()
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

func set_local_ready(ready: bool) -> bool:
	if _mode != "client" or _transport != "websocket" or _match_started:
		return false
	if _local_peer_id <= SERVER_PEER_ID:
		return false
	rpc_id(SERVER_PEER_ID, "_server_set_ready", ready)
	print("XZOGOT_MATCH_READY_REQUEST peer=", _local_peer_id, " ready=", ready)
	return true

func get_matchmaking_phase() -> String:
	return _match_phase

func get_matchmaking_ready_count() -> int:
	return _ready_count()

func get_matchmaking_countdown() -> float:
	return maxf(0.0, _match_countdown)

func is_local_ready() -> bool:
	return _ready_peers.has(_local_peer_id) and bool(_ready_peers[_local_peer_id])

func is_match_started() -> bool:
	return _match_started

func get_matchmaking_status_text() -> String:
	match _match_phase:
		"searching":
			return "SEARCHING FOR MATCH..."
		"found":
			return "FOUND %d/%d  •  READY %d/%d" % [
				_roster.size(), MAX_PLAYERS, _ready_count(), _roster.size()
			]
		"starting":
			return "STARTING IN %.1f  •  READY %d/%d" % [
				maxf(0.0, _match_countdown), _ready_count(), _roster.size()
			]
		"started":
			return "MATCH STARTED  •  %d/%d PLAYERS" % [_roster.size(), MAX_PLAYERS]
		"reconnecting":
			return "RECONNECTING PLAYER..."
	return ""

func get_local_player_slot() -> int:
	return _local_player_slot

func get_resume_grace_seconds() -> float:
	return float(RECONNECT_GRACE_MS) / 1000.0

func is_reconnect_in_progress() -> bool:
	return _reconnect_active

func get_reconnect_attempt() -> int:
	return _reconnect_attempt

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

func get_transport() -> String:
	return _transport

func is_dedicated_server() -> bool:
	return _dedicated_server

func get_relay_url() -> String:
	return _relay_url

func is_session_private() -> bool:
	return _session_private

func get_session_port() -> int:
	return _port

func get_max_players() -> int:
	return MAX_PLAYERS

func get_roster_ids() -> PackedInt32Array:
	var ids := PackedInt32Array()
	for id_var: Variant in _roster.keys():
		ids.append(int(id_var))
	ids.sort()
	return ids

func find_public_matches() -> bool:
	var directory: Node = _public_directory()
	if directory == null or not directory.has_method("find_public_matches"):
		return false
	if not bool(directory.call("is_configured")):
		network_error.emit("PUBLIC_DIRECTORY_NOT_CONFIGURED")
		return false
	return bool(directory.call("find_public_matches"))

func get_public_matches() -> Array:
	var directory: Node = _public_directory()
	if directory == null or not directory.has_method("get_matches"):
		return []
	return directory.call("get_matches") as Array

func get_public_relay_endpoint() -> String:
	var env_url := OS.get_environment("XZOGOT_PUBLIC_RELAY_URL").strip_edges()
	if not env_url.is_empty():
		return env_url
	return str(
		ProjectSettings.get_setting(
			"network/xz/public_relay_url",
			""
		)
	).strip_edges()

func is_public_relay_configured() -> bool:
	var url := get_public_relay_endpoint()
	return url.begins_with("ws://") or url.begins_with("wss://")

func join_public_relay() -> Error:
	if not is_public_relay_configured():
		return ERR_UNAVAILABLE
	var url := get_public_relay_endpoint()
	print("XZOGOT_NETWORK_JOIN_PUBLIC_RELAY ", url)
	return join_websocket_game(url)

func join_best_public_match() -> Error:
	var directory: Node = _public_directory()
	if directory == null or not directory.has_method("get_best_match"):
		return join_public_relay() if is_public_relay_configured() else ERR_UNAVAILABLE
	var session: Dictionary = directory.call("get_best_match") as Dictionary
	if session.is_empty():
		return join_public_relay() if is_public_relay_configured() else ERR_DOES_NOT_EXIST
	var address: String = str(session.get("ip", "")).strip_edges()
	var game_port: int = int(session.get("port", DEFAULT_PORT))
	if address.is_empty() or game_port < 1024 or game_port > 65535:
		return join_public_relay() if is_public_relay_configured() else ERR_INVALID_DATA
	print("XZOGOT_NETWORK_JOIN_PUBLIC ", address, ":", game_port)
	var err := join_game(address, game_port)
	if err == OK and is_public_relay_configured():
		_public_relay_fallback_pending = true
	return err

func is_public_directory_configured() -> bool:
	var directory: Node = _public_directory()
	return (
		directory != null
		and directory.has_method("is_configured")
		and bool(directory.call("is_configured"))
	)

func start_find_match(discovery_port: int = 7778) -> Error:
	if is_network_session():
		return ERR_ALREADY_IN_USE
	var discovery: Node = _discovery()
	if discovery == null or not discovery.has_method("start_discovery"):
		return ERR_UNAVAILABLE
	var err: int = int(discovery.call("start_discovery", discovery_port))
	if err == OK:
		print("XZOGOT_NETWORK_FIND_MATCH_READY port=", discovery_port)
	return err

func stop_find_match() -> void:
	var discovery: Node = _discovery()
	if discovery != null and discovery.has_method("stop_discovery"):
		discovery.call("stop_discovery")

func get_discovered_matches() -> Array:
	var discovery: Node = _discovery()
	if discovery == null or not discovery.has_method("get_discovered_sessions"):
		return []
	return discovery.call("get_discovered_sessions") as Array

func join_best_lan_match() -> Error:
	var discovery: Node = _discovery()
	if discovery == null or not discovery.has_method("get_best_session"):
		return ERR_UNAVAILABLE
	var session: Dictionary = discovery.call("get_best_session") as Dictionary
	if session.is_empty():
		return ERR_DOES_NOT_EXIST
	var address: String = str(session.get("ip", ""))
	var game_port: int = int(session.get("port", DEFAULT_PORT))
	if address.is_empty() or game_port <= 0:
		return ERR_INVALID_DATA
	print("XZOGOT_NETWORK_JOIN_FOUND ", address, ":", game_port)
	return join_game(address, game_port)

func is_private_session() -> bool:
	return _session_private

func get_upnp_status() -> String:
	var upnp: Node = _upnp_node()
	if upnp == null or not upnp.has_method("get_status"):
		return "unavailable"
	return str(upnp.call("get_status"))

func get_public_endpoint() -> String:
	var upnp: Node = _upnp_node()
	if upnp == null or not upnp.has_method("get_public_endpoint"):
		return ""
	return str(upnp.call("get_public_endpoint"))

func has_public_mapping() -> bool:
	return not get_public_endpoint().is_empty()

func get_status_text() -> String:
	match _mode:
		"host":
			if _dedicated_server:
				return "DEDICATED RELAY  %d/%d  WS:%d" % [_roster.size(), MAX_PLAYERS, _port]
			var privacy: String = "PRIVATE" if _session_private else "PUBLIC DIRECT"
			return "HOST %s  %d/%d  UDP:%d" % [privacy, _roster.size(), MAX_PLAYERS, _port]
		"client":
			if _transport == "websocket":
				return "CONNECTED RELAY  PEER %d  %d/%d" % [_local_peer_id, _roster.size(), MAX_PLAYERS]
			return "CONNECTED  PEER %d  %d/%d  UDP:%d" % [_local_peer_id, _roster.size(), MAX_PLAYERS, _port]
		"joining":
			if _transport == "websocket":
				return "CONNECTING INTERNET RELAY..."
			return "CONNECTING  UDP:%d..." % _port
	return "OFFLINE"

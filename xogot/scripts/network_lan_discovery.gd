extends Node
class_name XzLanDiscovery

signal sessions_changed(sessions: Array)

const DEFAULT_DISCOVERY_PORT := 7778
const MAGIC := "XZOGOT_DISCOVERY_V1"
const PROTOCOL_VERSION := 1
const BEACON_INTERVAL := 0.65
const SESSION_TTL_SECONDS := 2.5

var _listener: PacketPeerUDP
var _sender: PacketPeerUDP
var _discovering: bool = false
var _advertising: bool = false
var _discovery_port: int = DEFAULT_DISCOVERY_PORT
var _game_port: int = 7777
var _session_name: String = "YOU WON'T WIN"
var _map_name: String = "CHURCH"
var _beacon_timer: float = 0.0
var _sessions: Dictionary = {}

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	print("XZOGOT_LAN_DISCOVERY_READY port=", DEFAULT_DISCOVERY_PORT)

func _network_manager() -> Node:
	return get_parent().get_node_or_null("NetworkManager") if get_parent() != null else null

func start_advertising(
	game_port: int = 7777,
	session_name: String = "YOU WON'T WIN",
	map_name: String = "CHURCH",
	discovery_port: int = DEFAULT_DISCOVERY_PORT
) -> Error:
	stop_advertising()
	_game_port = game_port
	_session_name = session_name.strip_edges() if not session_name.strip_edges().is_empty() else "YOU WON'T WIN"
	_map_name = map_name.strip_edges() if not map_name.strip_edges().is_empty() else "CHURCH"
	_discovery_port = discovery_port

	_sender = PacketPeerUDP.new()
	_sender.set_broadcast_enabled(true)
	var err: Error = _sender.set_dest_address("255.255.255.255", _discovery_port)
	if err != OK:
		_sender = null
		print("XZOGOT_LAN_ADVERTISE_FAIL ", err)
		return err
	_advertising = true
	_beacon_timer = 0.0
	_send_beacon()
	print("XZOGOT_LAN_ADVERTISE_READY game_port=", _game_port, " discovery_port=", _discovery_port)
	return OK

func stop_advertising() -> void:
	_advertising = false
	if _sender != null:
		_sender.close()
	_sender = null

func start_discovery(discovery_port: int = DEFAULT_DISCOVERY_PORT) -> Error:
	stop_discovery()
	_discovery_port = discovery_port
	_listener = PacketPeerUDP.new()
	# Some Android devices require broadcast receive to be explicitly enabled.
	_listener.set_broadcast_enabled(true)
	var err: Error = _listener.bind(_discovery_port, "*")
	if err != OK:
		_listener = null
		print("XZOGOT_LAN_FIND_FAIL ", err)
		return err
	_discovering = true
	_sessions.clear()
	sessions_changed.emit(get_discovered_sessions())
	print("XZOGOT_LAN_FIND_READY port=", _discovery_port)
	return OK

func stop_discovery() -> void:
	_discovering = false
	if _listener != null:
		_listener.close()
	_listener = null
	if not _sessions.is_empty():
		_sessions.clear()
		sessions_changed.emit([])

func _build_beacon() -> Dictionary:
	var manager: Node = _network_manager()
	var players: int = 1
	if manager != null and manager.has_method("get_connected_player_count"):
		players = int(manager.call("get_connected_player_count"))
	return {
		"magic": MAGIC,
		"version": PROTOCOL_VERSION,
		"name": _session_name,
		"map": _map_name,
		"port": _game_port,
		"players": clampi(players, 1, 4),
		"max_players": 4,
	}

func _encode_beacon() -> PackedByteArray:
	return JSON.stringify(_build_beacon()).to_utf8_buffer()

func _send_beacon() -> bool:
	if not _advertising or _sender == null:
		return false
	var err: Error = _sender.put_packet(_encode_beacon())
	if err != OK:
		print("XZOGOT_LAN_BEACON_SEND_FAIL ", err)
		return false
	return true

func debug_send_beacon_to(address: String, discovery_port: int = DEFAULT_DISCOVERY_PORT) -> bool:
	var peer := PacketPeerUDP.new()
	var err: Error = peer.set_dest_address(address, discovery_port)
	if err != OK:
		return false
	err = peer.put_packet(_encode_beacon())
	peer.close()
	return err == OK

func _ingest_packet(packet: PackedByteArray, sender_ip: String) -> bool:
	var parsed: Variant = JSON.parse_string(packet.get_string_from_utf8())
	if not (parsed is Dictionary):
		return false
	var data := parsed as Dictionary
	if str(data.get("magic", "")) != MAGIC:
		return false
	if int(data.get("version", 0)) != PROTOCOL_VERSION:
		return false
	var port: int = int(data.get("port", 0))
	var max_players: int = int(data.get("max_players", 0))
	var players: int = int(data.get("players", 0))
	if port <= 0 or port > 65535 or max_players != 4 or players < 1 or players > max_players:
		return false
	if sender_ip.is_empty():
		return false

	var key := "%s:%d" % [sender_ip, port]
	var session := {
		"ip": sender_ip,
		"port": port,
		"name": str(data.get("name", "YOU WON'T WIN")),
		"map": str(data.get("map", "CHURCH")),
		"players": players,
		"max_players": max_players,
		"last_seen_ms": Time.get_ticks_msec(),
	}
	var changed: bool = not _sessions.has(key) or _sessions[key] != session
	_sessions[key] = session
	if changed:
		sessions_changed.emit(get_discovered_sessions())
		print("XZOGOT_LAN_MATCH_FOUND ", key, " players=", players)
	return true

func _receive_packets() -> void:
	if not _discovering or _listener == null:
		return
	var changed: bool = false
	while _listener.get_available_packet_count() > 0:
		var packet: PackedByteArray = _listener.get_packet()
		var sender_ip: String = _listener.get_packet_ip()
		var before: int = _sessions.size()
		if _ingest_packet(packet, sender_ip) and _sessions.size() != before:
			changed = true
	if changed:
		sessions_changed.emit(get_discovered_sessions())

func _prune_sessions() -> void:
	if _sessions.is_empty():
		return
	var now_ms: int = Time.get_ticks_msec()
	var ttl_ms: int = int(SESSION_TTL_SECONDS * 1000.0)
	var changed: bool = false
	for key_var: Variant in _sessions.keys().duplicate():
		var key: String = str(key_var)
		var session: Dictionary = _sessions[key] as Dictionary
		if now_ms - int(session.get("last_seen_ms", 0)) > ttl_ms:
			_sessions.erase(key)
			changed = true
	if changed:
		sessions_changed.emit(get_discovered_sessions())
		print("XZOGOT_LAN_MATCH_PRUNE remaining=", _sessions.size())

func _process(delta: float) -> void:
	if _advertising:
		_beacon_timer -= delta
		if _beacon_timer <= 0.0:
			_beacon_timer = BEACON_INTERVAL
			_send_beacon()
	if _discovering:
		_receive_packets()
		_prune_sessions()

func get_discovered_sessions() -> Array:
	var result: Array = []
	for session_var: Variant in _sessions.values():
		var session: Dictionary = (session_var as Dictionary).duplicate(true)
		session.erase("last_seen_ms")
		result.append(session)
	result.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		var ap: int = int(a.get("players", 0))
		var bp: int = int(b.get("players", 0))
		if ap != bp:
			return ap > bp
		return str(a.get("ip", "")) < str(b.get("ip", ""))
	)
	return result

func get_best_session() -> Dictionary:
	for session_var: Variant in get_discovered_sessions():
		var session := session_var as Dictionary
		if int(session.get("players", 4)) < int(session.get("max_players", 4)):
			return session
	return {}

func is_discovering() -> bool:
	return _discovering

func is_advertising() -> bool:
	return _advertising

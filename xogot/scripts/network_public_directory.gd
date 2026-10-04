extends Node
class_name XzPublicMatchDirectory

signal matches_changed(matches: Array)
signal registration_changed(registered: bool, message: String)

const PROTOCOL_VERSION := 1
const HEARTBEAT_SECONDS := 8.0
const REQUEST_TIMEOUT := 6.0

@export var base_url: String = ""

var _http: HTTPRequest
var _request_kind: String = ""
var _registered: bool = false
var _session_id: String = ""
var _host_token: String = ""
var _heartbeat_timer: float = 0.0
var _last_error: String = ""
var _matches: Array = []
var _pending_unregister: bool = false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	if base_url.is_empty():
		base_url = str(ProjectSettings.get_setting("network/xz/public_directory_url", "")).strip_edges()
	base_url = base_url.trim_suffix("/")
	_http = HTTPRequest.new()
	_http.name = "DirectoryHTTPRequest"
	_http.timeout = REQUEST_TIMEOUT
	add_child(_http)
	_http.request_completed.connect(_on_request_completed)
	print("XZOGOT_PUBLIC_DIRECTORY_READY configured=", is_configured())

func is_configured() -> bool:
	return base_url.begins_with("http://") or base_url.begins_with("https://")

func configure_base_url(url: String) -> void:
	base_url = url.strip_edges().trim_suffix("/")
	print("XZOGOT_PUBLIC_DIRECTORY_CONFIGURED ", base_url)

func _network() -> Node:
	return get_parent().get_node_or_null("NetworkManager") if get_parent() != null else null

func _upnp() -> Node:
	return get_parent().get_node_or_null("NetworkUPNP") if get_parent() != null else null

func _new_session_id() -> String:
	var seed := "%d:%d:%s" % [Time.get_ticks_usec(), randi(), OS.get_unique_id()]
	return seed.sha256_text().substr(0, 24)

func _new_host_token() -> String:
	var seed := "host:%d:%d:%s" % [Time.get_ticks_usec(), randi(), OS.get_unique_id()]
	return seed.sha256_text()

func _headers(include_token: bool = false) -> PackedStringArray:
	var headers := PackedStringArray(["Content-Type: application/json", "Accept: application/json"])
	if include_token and not _host_token.is_empty():
		headers.append("X-XZ-Host-Token: " + _host_token)
	return headers

func _can_request() -> bool:
	return is_configured() and _http != null and _request_kind.is_empty()

func register_public_host() -> bool:
	if not _can_request():
		return false
	var network: Node = _network()
	var upnp: Node = _upnp()
	if network == null or upnp == null:
		_last_error = "runtime_missing"
		return false
	if not network.has_method("is_host") or not bool(network.call("is_host")):
		_last_error = "not_host"
		return false
	if network.has_method("is_private_session") and bool(network.call("is_private_session")):
		_last_error = "private_session"
		return false
	if not upnp.has_method("has_mapping") or not bool(upnp.call("has_mapping")):
		_last_error = "public_mapping_missing"
		return false

	if _session_id.is_empty():
		_session_id = _new_session_id()
	if _host_token.is_empty():
		_host_token = _new_host_token()

	var endpoint: String = str(upnp.call("get_external_ip"))
	var port: int = int(network.call("get_session_port")) if network.has_method("get_session_port") else 7777
	var players: int = int(network.call("get_connected_player_count")) if network.has_method("get_connected_player_count") else 1
	var payload := {
		"id": _session_id,
		"host_token": _host_token,
		"name": "YOU WON'T WIN",
		"map": "CHURCH",
		"ip": endpoint,
		"port": port,
		"players": clampi(players, 1, 4),
		"max_players": 4,
		"protocol": PROTOCOL_VERSION,
	}
	_request_kind = "register"
	var err: Error = _http.request(
		base_url + "/v1/sessions/register",
		_headers(),
		HTTPClient.METHOD_POST,
		JSON.stringify(payload)
	)
	if err != OK:
		_request_kind = ""
		_last_error = "register_request_%d" % int(err)
		return false
	return true

func find_public_matches() -> bool:
	if not _can_request():
		return false
	_request_kind = "list"
	var err: Error = _http.request(
		base_url + "/v1/sessions",
		_headers(),
		HTTPClient.METHOD_GET
	)
	if err != OK:
		_request_kind = ""
		_last_error = "list_request_%d" % int(err)
		return false
	print("XZOGOT_PUBLIC_FIND_REQUEST")
	return true

func unregister_public_host() -> bool:
	if not is_configured() or _session_id.is_empty() or _host_token.is_empty():
		_clear_registration()
		return false
	if _http == null or not _request_kind.is_empty():
		_pending_unregister = true
		return false
	_request_kind = "delete"
	var err: Error = _http.request(
		base_url + "/v1/sessions/" + _session_id.uri_encode(),
		_headers(true),
		HTTPClient.METHOD_DELETE
	)
	if err != OK:
		_request_kind = ""
		_clear_registration()
		return false
	return true

func _clear_registration() -> void:
	_registered = false
	_session_id = ""
	_host_token = ""
	_heartbeat_timer = 0.0
	_pending_unregister = false
	registration_changed.emit(false, "offline")

func _parse_json(body: PackedByteArray) -> Dictionary:
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	return parsed as Dictionary if parsed is Dictionary else {}

func _on_request_completed(
	result: int,
	response_code: int,
	_response_headers: PackedStringArray,
	body: PackedByteArray
) -> void:
	var kind: String = _request_kind
	_request_kind = ""
	var ok_transport: bool = result == HTTPRequest.RESULT_SUCCESS
	var data: Dictionary = _parse_json(body)
	if not ok_transport or response_code < 200 or response_code >= 300:
		_last_error = "%s_http_%d_result_%d" % [kind, response_code, result]
		print("XZOGOT_PUBLIC_DIRECTORY_ERROR ", _last_error)
		if kind == "register":
			_registered = false
			registration_changed.emit(false, _last_error)
		if kind == "delete":
			_clear_registration()
		if _pending_unregister:
			_pending_unregister = false
			unregister_public_host()
		return

	match kind:
		"register":
			_session_id = str(data.get("id", _session_id))
			_host_token = str(data.get("host_token", _host_token))
			_registered = true
			_heartbeat_timer = HEARTBEAT_SECONDS
			_last_error = ""
			registration_changed.emit(true, "registered")
			print("XZOGOT_PUBLIC_DIRECTORY_REGISTERED ", _session_id)
		"list":
			var raw: Variant = data.get("sessions", [])
			_matches = raw as Array if raw is Array else []
			_last_error = ""
			matches_changed.emit(_matches.duplicate(true))
			print("XZOGOT_PUBLIC_MATCHES ", _matches.size())
		"delete":
			print("XZOGOT_PUBLIC_DIRECTORY_UNREGISTERED ", _session_id)
			_clear_registration()

	if _pending_unregister and _request_kind.is_empty():
		_pending_unregister = false
		unregister_public_host()

func _process(delta: float) -> void:
	if not _registered:
		return
	_heartbeat_timer -= delta
	if _heartbeat_timer <= 0.0 and _request_kind.is_empty():
		_heartbeat_timer = HEARTBEAT_SECONDS
		register_public_host()

func get_matches() -> Array:
	return _matches.duplicate(true)

func get_best_match() -> Dictionary:
	for session_var: Variant in _matches:
		var session := session_var as Dictionary
		if (
			int(session.get("protocol", 0)) == PROTOCOL_VERSION
			and int(session.get("players", 4)) < int(session.get("max_players", 4))
		):
			return session.duplicate(true)
	return {}

func is_registered() -> bool:
	return _registered

func get_last_error() -> String:
	return _last_error

func get_session_id() -> String:
	return _session_id

func _exit_tree() -> void:
	# HTTP cannot be awaited safely during teardown; server-side TTL is the
	# final safety net if a client process exits before DELETE completes.
	if _http != null and not _request_kind.is_empty():
		_http.cancel_request()

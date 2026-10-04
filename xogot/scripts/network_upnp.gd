extends Node
class_name XzUpnpReachability

signal mapping_finished(success: bool, external_ip: String, port: int, status: String)

const DESCRIPTION := "XZOGOT Zombies"
const DISCOVERY_TIMEOUT_MS := 1800
const DISCOVERY_TTL := 2

var _thread: Thread
var _upnp: UPNP
var _mapped_port: int = 0
var _external_ip: String = ""
var _status: String = "idle"
var _pending_result: Dictionary = {}
var _result_ready: bool = false
var _shutdown_requested: bool = false

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	print("XZOGOT_UPNP_READY")

func request_mapping(port: int) -> bool:
	if port < 1024 or port > 65535:
		_status = "invalid_port"
		return false
	if is_busy():
		return false
	clear_mapping()
	_status = "discovering"
	_mapped_port = 0
	_external_ip = ""
	_pending_result.clear()
	_result_ready = false
	_shutdown_requested = false
	_thread = Thread.new()
	var err: Error = _thread.start(_worker_map.bind(port))
	if err != OK:
		_thread = null
		_status = "thread_failed"
		mapping_finished.emit(false, "", port, _status)
		return false
	print("XZOGOT_UPNP_DISCOVERY_START port=", port)
	return true

func _worker_map(port: int) -> void:
	var result := {
		"success": false,
		"external_ip": "",
		"port": port,
		"status": "discover_failed",
	}
	var upnp := UPNP.new()
	var discover_result: int = upnp.discover(DISCOVERY_TIMEOUT_MS, DISCOVERY_TTL, "InternetGatewayDevice")
	if discover_result != UPNP.UPNP_RESULT_SUCCESS:
		result["status"] = "discover_failed_%d" % discover_result
		_pending_result = result
		_result_ready = true
		return

	var gateway: UPNPDevice = upnp.get_gateway()
	if gateway == null or not gateway.is_valid_gateway():
		result["status"] = "no_valid_gateway"
		_pending_result = result
		_result_ready = true
		return

	# ENet gameplay is UDP. Do not expose an unnecessary TCP mapping.
	var map_result: int = upnp.add_port_mapping(port, port, DESCRIPTION, "UDP")
	if map_result != UPNP.UPNP_RESULT_SUCCESS:
		result["status"] = "mapping_failed_%d" % map_result
		_pending_result = result
		_result_ready = true
		return

	var external: String = upnp.query_external_address()
	if external.is_empty():
		upnp.delete_port_mapping(port, "UDP")
		result["status"] = "external_ip_unavailable"
		_pending_result = result
		_result_ready = true
		return

	result["success"] = true
	result["external_ip"] = external
	result["status"] = "mapped"
	_upnp = upnp
	_pending_result = result
	_result_ready = true

func _process(_delta: float) -> void:
	if not _result_ready:
		return
	_result_ready = false
	if _thread != null:
		_thread.wait_to_finish()
		_thread = null
	var success: bool = bool(_pending_result.get("success", false))
	var port: int = int(_pending_result.get("port", 0))
	_status = str(_pending_result.get("status", "unknown"))
	_external_ip = str(_pending_result.get("external_ip", ""))
	if success:
		_mapped_port = port
		print("XZOGOT_UPNP_MAPPING_GREEN ", _external_ip, ":", port)
	else:
		_mapped_port = 0
		_external_ip = ""
		print("XZOGOT_UPNP_MAPPING_UNAVAILABLE status=", _status)
	mapping_finished.emit(success, _external_ip, port, _status)
	_pending_result.clear()

func clear_mapping() -> void:
	if _thread != null:
		# Discovery is synchronous; join before tearing down this node. Any
		# worker result produced while joining belongs to the old request and
		# must never overwrite the next mapping/session.
		_thread.wait_to_finish()
		_thread = null
	_result_ready = false
	_pending_result.clear()
	if _upnp != null and _mapped_port > 0:
		var delete_result: int = _upnp.delete_port_mapping(_mapped_port, "UDP")
		print("XZOGOT_UPNP_MAPPING_CLEARED port=", _mapped_port, " result=", delete_result)
	_upnp = null
	_mapped_port = 0
	_external_ip = ""
	_status = "idle"

func _exit_tree() -> void:
	clear_mapping()

func is_busy() -> bool:
	return _thread != null and _thread.is_started()

func debug_set_mapping_for_probe(external_ip: String, port: int) -> bool:
	# Test seam: never opens a socket or router mapping. Production hosting only
	# reaches mapped state through request_mapping() + the UPNP worker.
	if external_ip.is_empty() or port < 1024 or port > 65535:
		return false
	clear_mapping()
	_external_ip = external_ip
	_mapped_port = port
	_status = "mapped_probe"
	print("XZOGOT_UPNP_PROBE_MAPPING ", get_public_endpoint())
	mapping_finished.emit(true, _external_ip, _mapped_port, _status)
	return true

func has_mapping() -> bool:
	return _mapped_port > 0 and not _external_ip.is_empty()

func get_external_ip() -> String:
	return _external_ip

func get_mapped_port() -> int:
	return _mapped_port

func get_status() -> String:
	return _status

func get_public_endpoint() -> String:
	if not has_mapping():
		return ""
	return "%s:%d" % [_external_ip, _mapped_port]

extends Node

signal voice_frame_received(speaker_slot: int, distance_m: float, byte_count: int)
signal voice_state_changed()

const SAMPLE_RATE := 16000.0
const SAMPLES_PER_PACKET := 320
const PACKET_BYTES := 320
const PROXIMITY_FULL_M := 4.0
const PROXIMITY_MAX_M := 18.0
const VOICE_RATE_LIMIT_MS := 12
const VAD_RMS_THRESHOLD := 0.010
const CAPTURE_BUS := "XZVoiceCapture"
const MU := 255.0

var input_enabled: bool = true
var output_enabled: bool = true

var _capture: AudioEffectCapture
var _mic_player: AudioStreamPlayer
var _capture_ready: bool = false
var _sequence: int = 0
var _playback_players: Dictionary = {}
var _muted_slots: Dictionary = {}
var _last_server_packet_ms: Dictionary = {}
var _last_server_sequence: Dictionary = {}
var _received_frames: int = 0
var _app_paused: bool = false
var _mic_permission_granted: bool = false
var _permission_request_pending: bool = false
var _lifecycle_pause_count: int = 0
var _lifecycle_resume_count: int = 0
var _capture_restart_count: int = 0

func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	set_process(true)
	var main_loop := Engine.get_main_loop()
	if main_loop != null and main_loop.has_signal("on_request_permissions_result"):
		var permission_cb := Callable(self, "_on_permission_result")
		if not main_loop.is_connected("on_request_permissions_result", permission_cb):
			main_loop.connect("on_request_permissions_result", permission_cb)
	_refresh_mic_permission()
	print("XZOGOT_PROXIMITY_VOICE_READY rate=", int(SAMPLE_RATE), " packet=", PACKET_BYTES, " max_m=", PROXIMITY_MAX_M)

func _notification(what: int) -> void:
	if what == MainLoop.NOTIFICATION_APPLICATION_PAUSED:
		_handle_application_paused("os")
	elif what == MainLoop.NOTIFICATION_APPLICATION_RESUMED:
		_handle_application_resumed("os")

func _microphone_permission_name() -> String:
	if OS.has_feature("android"):
		return "android.permission.RECORD_AUDIO"
	if OS.has_feature("ios"):
		return "appleembedded.permission.AUDIO_RECORD"
	return ""

func _refresh_mic_permission() -> bool:
	var permission := _microphone_permission_name()
	if permission.is_empty():
		_mic_permission_granted = true
		return true
	var granted := OS.get_granted_permissions()
	_mic_permission_granted = granted.has(permission) or granted.has("RECORD_AUDIO") or granted.has("AUDIO_RECORD")
	return _mic_permission_granted

func _request_mic_permission() -> bool:
	if _refresh_mic_permission():
		return true
	if _permission_request_pending:
		return false
	var permission := _microphone_permission_name()
	if permission.is_empty():
		_mic_permission_granted = true
		return true
	_permission_request_pending = true
	_mic_permission_granted = OS.request_permission(permission)
	if _mic_permission_granted:
		_permission_request_pending = false
		print("XZOGOT_VOICE_PERMISSION_GRANTED immediate=true permission=", permission)
	else:
		print("XZOGOT_VOICE_PERMISSION_REQUESTED permission=", permission)
	return _mic_permission_granted

func _on_permission_result(permission: String, granted: bool) -> void:
	var expected := _microphone_permission_name()
	if expected.is_empty():
		return
	if permission != expected and not permission.ends_with("RECORD_AUDIO") and not permission.ends_with("AUDIO_RECORD"):
		return
	_permission_request_pending = false
	_mic_permission_granted = granted
	print("XZOGOT_VOICE_PERMISSION_RESULT permission=", permission, " granted=", granted)
	if granted and input_enabled and not _app_paused:
		call_deferred("_ensure_capture")

func _stop_capture_for_route_change() -> void:
	if _capture != null:
		var available := _capture.get_frames_available()
		if available > 0:
			_capture.get_buffer(available)
	if _mic_player != null and is_instance_valid(_mic_player):
		_mic_player.stop()
		_mic_player.queue_free()
	_mic_player = null
	_capture_ready = false

func _reset_playback_routes() -> void:
	for player_var: Variant in _playback_players.values():
		var player := player_var as AudioStreamPlayer
		if player != null and is_instance_valid(player):
			player.stop()
			player.queue_free()
	_playback_players.clear()

func _handle_application_paused(source: String) -> void:
	if _app_paused:
		return
	_app_paused = true
	_lifecycle_pause_count += 1
	_stop_capture_for_route_change()
	_reset_playback_routes()
	var network := _network()
	if network != null and network.has_method("handle_application_paused"):
		network.call("handle_application_paused")
	print("XZOGOT_MOBILE_AUDIO_PAUSED source=", source, " count=", _lifecycle_pause_count)

func _handle_application_resumed(source: String) -> bool:
	var was_paused := _app_paused
	_app_paused = false
	_lifecycle_resume_count += 1
	_stop_capture_for_route_change()
	_reset_playback_routes()
	_refresh_mic_permission()
	var handover_started := false
	var network := _network()
	if network != null and network.has_method("handle_application_resumed"):
		handover_started = bool(network.call("handle_application_resumed"))
	if input_enabled and _mic_permission_granted:
		_capture_restart_count += 1
		call_deferred("_ensure_capture")
	print(
		"XZOGOT_MOBILE_AUDIO_RESUMED source=", source,
		" was_paused=", was_paused,
		" handover=", handover_started,
		" count=", _lifecycle_resume_count
	)
	return handover_started

func _network() -> Node:
	return get_parent().get_node_or_null("NetworkManager")

func _network_mode() -> String:
	var network := _network()
	return str(network.call("get_mode")) if network != null and network.has_method("get_mode") else "offline"

func _is_dedicated() -> bool:
	var network := _network()
	return OS.get_environment("XZOGOT_DEDICATED") == "1" or (network != null and network.has_method("is_dedicated_server") and bool(network.call("is_dedicated_server")))

func _ensure_capture() -> void:
	if _capture_ready or _app_paused or _is_dedicated() or OS.get_environment("XZOGOT_DISABLE_MIC_CAPTURE") == "1":
		return
	if not _request_mic_permission():
		return
	var bus_index := AudioServer.get_bus_index(CAPTURE_BUS)
	if bus_index < 0:
		AudioServer.add_bus()
		bus_index = AudioServer.get_bus_count() - 1
		AudioServer.set_bus_name(bus_index, CAPTURE_BUS)
		var capture_effect := AudioEffectCapture.new()
		AudioServer.add_bus_effect(bus_index, capture_effect, 0)
		AudioServer.set_bus_mute(bus_index, true)
	_capture = AudioServer.get_bus_effect(bus_index, 0) as AudioEffectCapture
	if _capture == null:
		push_warning("XZOGOT_VOICE_CAPTURE_UNAVAILABLE")
		return
	_mic_player = AudioStreamPlayer.new()
	_mic_player.name = "VoiceMicrophone"
	_mic_player.stream = AudioStreamMicrophone.new()
	_mic_player.bus = CAPTURE_BUS
	add_child(_mic_player)
	_mic_player.play()
	_capture_ready = true
	print("XZOGOT_VOICE_CAPTURE_READY mix_rate=", AudioServer.get_mix_rate())

func _process(_delta: float) -> void:
	if _app_paused or _is_dedicated():
		return
	var mode := _network_mode()
	if mode != "host" and mode != "client":
		return
	if input_enabled:
		_ensure_capture()
		_capture_packets()
	elif _capture_ready and _capture != null:
		var available := _capture.get_frames_available()
		if available > 0:
			_capture.get_buffer(available)

func _capture_packets() -> void:
	if not _capture_ready or _capture == null:
		return
	var mix_rate := maxf(8000.0, AudioServer.get_mix_rate())
	var source_frames := maxi(SAMPLES_PER_PACKET, int(round(mix_rate * float(SAMPLES_PER_PACKET) / SAMPLE_RATE)))
	var packets := 0
	while _capture.get_frames_available() >= source_frames and packets < 3:
		var raw := _capture.get_buffer(source_frames)
		var mono := PackedFloat32Array()
		mono.resize(SAMPLES_PER_PACKET)
		var energy := 0.0
		for index in range(SAMPLES_PER_PACKET):
			var source_index := mini(source_frames - 1, int(floor(float(index) * float(source_frames) / float(SAMPLES_PER_PACKET))))
			var sample := clampf((raw[source_index].x + raw[source_index].y) * 0.5, -1.0, 1.0)
			mono[index] = sample
			energy += sample * sample
		var rms := sqrt(energy / float(SAMPLES_PER_PACKET))
		if rms >= VAD_RMS_THRESHOLD:
			_send_encoded_frame(_encode_mulaw(mono))
		packets += 1

func _encode_mulaw(samples: PackedFloat32Array) -> PackedByteArray:
	var out := PackedByteArray()
	out.resize(samples.size())
	var log_mu := log(1.0 + MU)
	for index in range(samples.size()):
		var sample := clampf(samples[index], -1.0, 1.0)
		var magnitude := log(1.0 + MU * absf(sample)) / log_mu
		var compressed := -magnitude if sample < 0.0 else magnitude
		out[index] = clampi(int(round((compressed + 1.0) * 127.5)), 0, 255)
	return out

func _decode_mulaw(data: PackedByteArray) -> PackedVector2Array:
	var frames := PackedVector2Array()
	frames.resize(data.size())
	for index in range(data.size()):
		var compressed := float(data[index]) / 127.5 - 1.0
		var magnitude := (pow(1.0 + MU, absf(compressed)) - 1.0) / MU
		var sample := -magnitude if compressed < 0.0 else magnitude
		frames[index] = Vector2(sample, sample)
	return frames

func _send_encoded_frame(frame: PackedByteArray) -> bool:
	if frame.size() != PACKET_BYTES:
		return false
	var network := _network()
	if network == null:
		return false
	var mode := str(network.call("get_mode")) if network.has_method("get_mode") else "offline"
	if mode != "host" and mode != "client":
		return false
	_sequence = (_sequence + 1) & 0x7fffffff
	if mode == "host" and multiplayer.is_server():
		var sender := int(network.call("get_local_peer_id")) if network.has_method("get_local_peer_id") else 1
		_route_voice_frame(sender, _sequence, frame)
		return true
	rpc_id(1, "_server_voice_frame", _sequence, frame)
	return true

@rpc("any_peer", "call_remote", "unreliable_ordered", 4)
func _server_voice_frame(sequence: int, frame: PackedByteArray) -> void:
	if not multiplayer.is_server() or frame.size() != PACKET_BYTES:
		return
	var sender := multiplayer.get_remote_sender_id()
	var network := _network()
	if network == null or not (network.call("get_roster_ids") as PackedInt32Array).has(sender):
		return
	var now := Time.get_ticks_msec()
	var last_ms := int(_last_server_packet_ms.get(sender, 0))
	if last_ms > 0 and now - last_ms < VOICE_RATE_LIMIT_MS:
		return
	var previous_sequence := int(_last_server_sequence.get(sender, -1))
	if previous_sequence >= 0 and sequence <= previous_sequence:
		return
	_last_server_packet_ms[sender] = now
	_last_server_sequence[sender] = sequence
	_route_voice_frame(sender, sequence, frame)

func _route_voice_frame(sender: int, sequence: int, frame: PackedByteArray) -> void:
	if not multiplayer.is_server():
		return
	var network := _network()
	if network == null or not network.has_method("get_peer_world_position"):
		return
	var sender_position := network.call("get_peer_world_position", sender) as Vector3
	var speaker_slot := int(network.call("get_peer_slot", sender)) if network.has_method("get_peer_slot") else 0
	for recipient: int in network.call("get_roster_ids") as PackedInt32Array:
		if recipient == sender:
			continue
		var recipient_position := network.call("get_peer_world_position", recipient) as Vector3
		var distance := sender_position.distance_to(recipient_position)
		if not is_distance_audible(distance):
			continue
		if recipient == 1 and not _is_dedicated():
			_client_voice_frame(sender, speaker_slot, sequence, frame, distance)
		elif multiplayer.get_peers().has(recipient):
			rpc_id(recipient, "_client_voice_frame", sender, speaker_slot, sequence, frame, distance)

@rpc("authority", "call_remote", "unreliable_ordered", 4)
func _client_voice_frame(sender_peer: int, speaker_slot: int, _sequence_value: int, frame: PackedByteArray, distance_m: float) -> void:
	if multiplayer.is_server() and _is_dedicated():
		return
	if not output_enabled or frame.size() != PACKET_BYTES:
		return
	if speaker_slot > 0 and is_slot_muted(speaker_slot):
		return
	_received_frames += 1
	voice_frame_received.emit(speaker_slot, distance_m, frame.size())
	if OS.get_environment("XZOGOT_DISABLE_VOICE_PLAYBACK") == "1":
		return
	_play_frame(sender_peer, frame, distance_m)

func _play_frame(sender_peer: int, frame: PackedByteArray, distance_m: float) -> void:
	var player := _playback_players.get(sender_peer, null) as AudioStreamPlayer
	if player == null or not is_instance_valid(player):
		var stream := AudioStreamGenerator.new()
		stream.mix_rate = SAMPLE_RATE
		stream.buffer_length = 0.45
		player = AudioStreamPlayer.new()
		player.name = "VoicePeer_%d" % sender_peer
		player.stream = stream
		add_child(player)
		player.play()
		_playback_players[sender_peer] = player
	var gain := distance_gain(distance_m)
	player.volume_db = linear_to_db(maxf(0.01, gain))
	var playback := player.get_stream_playback() as AudioStreamGeneratorPlayback
	if playback == null:
		return
	var decoded := _decode_mulaw(frame)
	if playback.can_push_buffer(decoded.size()):
		playback.push_buffer(decoded)

func distance_gain(distance_m: float) -> float:
	if distance_m <= PROXIMITY_FULL_M:
		return 1.0
	if distance_m >= PROXIMITY_MAX_M:
		return 0.0
	var t := clampf((distance_m - PROXIMITY_FULL_M) / (PROXIMITY_MAX_M - PROXIMITY_FULL_M), 0.0, 1.0)
	return pow(1.0 - t, 1.65)

func is_distance_audible(distance_m: float) -> bool:
	return distance_m >= 0.0 and distance_m <= PROXIMITY_MAX_M

func set_input_enabled(enabled: bool) -> void:
	input_enabled = enabled
	if input_enabled and not _app_paused:
		_ensure_capture()
	elif not input_enabled:
		_stop_capture_for_route_change()
	voice_state_changed.emit()
	print("XZOGOT_VOICE_MIC ", "ON" if input_enabled else "OFF")

func set_output_enabled(enabled: bool) -> void:
	output_enabled = enabled
	if not output_enabled:
		for player_var: Variant in _playback_players.values():
			var player := player_var as AudioStreamPlayer
			if player != null:
				player.stop()
	voice_state_changed.emit()
	print("XZOGOT_VOICE_OUTPUT ", "ON" if output_enabled else "OFF")

func set_slot_muted(slot: int, muted: bool) -> void:
	if slot <= 0 or slot > 4:
		return
	if muted:
		_muted_slots[slot] = true
	else:
		_muted_slots.erase(slot)
	voice_state_changed.emit()
	print("XZOGOT_VOICE_SLOT_MUTE slot=", slot, " muted=", muted)

func is_slot_muted(slot: int) -> bool:
	return bool(_muted_slots.get(slot, false))

func get_input_enabled() -> bool:
	return input_enabled

func get_output_enabled() -> bool:
	return output_enabled

func get_received_frame_count() -> int:
	return _received_frames

func get_status_text() -> String:
	return "PROXIMITY VOICE  %.0fm  •  MIC %s  •  OUTPUT %s" % [PROXIMITY_MAX_M, "ON" if input_enabled else "OFF", "ON" if output_enabled else "OFF"]

func debug_send_test_tone(packet_count: int = 6) -> bool:
	var count := clampi(packet_count, 1, 20)
	var samples := PackedFloat32Array()
	samples.resize(SAMPLES_PER_PACKET)
	for packet_index in range(count):
		for index in range(SAMPLES_PER_PACKET):
			var phase := TAU * 440.0 * float(packet_index * SAMPLES_PER_PACKET + index) / SAMPLE_RATE
			samples[index] = sin(phase) * 0.18
		if not _send_encoded_frame(_encode_mulaw(samples)):
			return false
	print("XZOGOT_VOICE_TEST_TONE_SENT packets=", count)
	return true

func debug_codec_roundtrip_error() -> float:
	var samples := PackedFloat32Array()
	samples.resize(SAMPLES_PER_PACKET)
	for index in range(SAMPLES_PER_PACKET):
		samples[index] = sin(TAU * 330.0 * float(index) / SAMPLE_RATE) * 0.25
	var decoded := _decode_mulaw(_encode_mulaw(samples))
	var error := 0.0
	for index in range(SAMPLES_PER_PACKET):
		error += absf(decoded[index].x - samples[index])
	return error / float(SAMPLES_PER_PACKET)

func is_application_paused() -> bool:
	return _app_paused

func has_microphone_permission() -> bool:
	return _mic_permission_granted

func get_lifecycle_pause_count() -> int:
	return _lifecycle_pause_count

func get_lifecycle_resume_count() -> int:
	return _lifecycle_resume_count

func get_capture_restart_count() -> int:
	return _capture_restart_count

func debug_simulate_application_paused() -> void:
	_handle_application_paused("debug")

func debug_simulate_application_resumed() -> bool:
	return _handle_application_resumed("debug")

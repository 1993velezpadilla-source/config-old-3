extends SceneTree
## Actual engine (Linux CI) unit test only; never pretend it is a phone.
func _initialize() -> void:
    call_deferred("_run")
func _run() -> void:
    var source: Script=load("res://nacht_native_android_device_profile.gd") as Script
    if source==null or not source.can_instantiate():
        push_error("XZOGOT_ANDROID_PHYSICAL_PROFILER_SCRIPT_PARSE_RED")
        quit(2)
        return
    var probe: Node=source.new() as Node
    root.add_child(probe)
    var sample: Array[float]=[]
    for i: int in range(100):
        sample.append(16.0 if i<98 else 33.0)
    var result: Dictionary=probe.call("summarize_frame_intervals",sample) as Dictionary
    if not result.get("valid",false) or int(result.get("frames",0))!=100:
        push_error("XZOGOT_ANDROID_PHYSICAL_PROFILER_SAMPLE_MATH_RED")
        quit(3)
        return
    if float(result.get("p95FrameIntervalMs",0.0))!=16.0 or float(result.get("p99FrameIntervalMs",0.0))!=33.0:
        push_error("XZOGOT_ANDROID_PHYSICAL_PROFILER_P95_P99_PERCENTILE_RED "+JSON.stringify(result))
        quit(4)
        return
    if OS.get_name()=="Android" or probe.call("start_physical_android_profile"):
        push_error("XZOGOT_ANDROID_PROFILER_FAKE_LINUX_PHYSICAL_GPU_CLAIM_RED")
        quit(5)
        return
    if not FileAccess.file_exists("res://nacht_native_android_device_profile.gd"):
        push_error("XZOGOT_ANDROID_PROFILER_SOURCE_MISSING_RED")
        quit(6)
        return
    print("XZOGOT_ANDROID_PHYSICAL_OPTIN_PROFILE_CODE_UNIT_GREEN ",
        "LINUX_NOT_ANDROID p95=",result["p95FrameIntervalMs"],
        " p99=",result["p99FrameIntervalMs"])
    quit(0)

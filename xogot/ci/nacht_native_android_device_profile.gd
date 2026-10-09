extends Node
## Research-only, opt-in, attachable native-device performance sampler.
## Never use llvmpipe/Xvfb results to infer Android FPS/VRAM.
## Does NOT create a playable APK or change shipping scenes itself.
signal profile_finished(report: Dictionary)

@export var run_automatically_on_android: bool=false
@export_range(3.0,60.0,1.0) var warmup_seconds: float=15.0
@export_range(15.0,600.0,1.0) var sample_seconds: float=120.0
@export var run_label: String="nacht_native_original_mobile"

var _state: int=0
var _started_us: int=0
var _last_us: int=0
var _frames_ms: Array[float]=[]
var _draw_peak: int=0
var _primitives_peak: int=0
var _objects_peak: int=0
var _static_memory_peak: int=0
var _render_reported_memory_peak: int=0
var _texture_reported_memory_peak: int=0
var _physics_peak_ms: float=0.0
var _process_peak_ms: float=0.0

func _ready() -> void:
    set_process(false)
    if run_automatically_on_android and OS.get_name()=="Android":
        start_physical_android_profile()

func start_physical_android_profile() -> bool:
    if OS.get_name()!="Android":
        push_warning("XZOGOT_ANDROID_PROFILER_REFUSED_NON_PHYSICAL_ANDROID_BACKEND")
        return false
    if _state!=0:
        return false
    _state=1
    _started_us=Time.get_ticks_usec()
    _last_us=0
    _frames_ms.clear()
    _draw_peak=0
    _primitives_peak=0
    _objects_peak=0
    _static_memory_peak=0
    _render_reported_memory_peak=0
    _texture_reported_memory_peak=0
    _process_peak_ms=0.0
    _physics_peak_ms=0.0
    set_process(true)
    print("XZOGOT_NATIVE_ANDROID_PHYSICAL_PROFILE_START",
        " device=",OS.get_model_name(),
        " backend=",RenderingServer.get_current_rendering_method(),
        " gpu=",RenderingServer.get_video_adapter_name())
    return true

func _process(_delta: float) -> void:
    if _state==0:
        return
    var now_us: int=Time.get_ticks_usec()
    var elapsed: float=float(now_us-_started_us)/1000000.0
    if elapsed<warmup_seconds:
        _last_us=0
        return
    if _state==1:
        _state=2
        _last_us=now_us
        return
    if _last_us!=0:
        var interval_ms: float=float(now_us-_last_us)/1000.0
        if is_finite(interval_ms) and interval_ms>0.1 and interval_ms<10000.0:
            _frames_ms.append(interval_ms)
    _last_us=now_us
    _draw_peak=maxi(_draw_peak,int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)))
    _primitives_peak=maxi(_primitives_peak,int(Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME)))
    _objects_peak=maxi(_objects_peak,int(Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME)))
    _static_memory_peak=maxi(_static_memory_peak,int(Performance.get_monitor(Performance.MEMORY_STATIC)))
    _render_reported_memory_peak=maxi(_render_reported_memory_peak,
        int(Performance.get_monitor(Performance.RENDER_VIDEO_MEM_USED)))
    _texture_reported_memory_peak=maxi(_texture_reported_memory_peak,
        int(Performance.get_monitor(Performance.RENDER_TEXTURE_MEM_USED)))
    _physics_peak_ms=maxf(_physics_peak_ms,1000.0*Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS))
    _process_peak_ms=maxf(_process_peak_ms,1000.0*Performance.get_monitor(Performance.TIME_PROCESS))
    if elapsed>=warmup_seconds+sample_seconds:
        _finish()

static func summarize_frame_intervals(samples: Array[float]) -> Dictionary:
    if samples.is_empty():
        return {"valid":false,"frames":0}
    var arr: Array[float]=samples.duplicate()
    arr.sort()
    var total: float=0.0
    for ms: float in arr:
        if not is_finite(ms) or ms<=0.0:
            return {"valid":false,"frames":arr.size()}
        total+=ms
    var avg: float=total/float(arr.size())
    var p50: float=arr[int(round(float(arr.size()-1)*0.50))]
    var p95: float=arr[int(round(float(arr.size()-1)*0.95))]
    var p99: float=arr[int(round(float(arr.size()-1)*0.99))]
    return {
        "valid":true,
        "frames":arr.size(),
        "meanFrameIntervalMs":avg,
        "p50FrameIntervalMs":p50,
        "p95FrameIntervalMs":p95,
        "p99FrameIntervalMs":p99,
        "worstFrameIntervalMs":arr[arr.size()-1],
        "effectiveSampleIntervalFPS":1000.0/avg,
        "onePercentLowFPSApproximatedFromP99FrameInterval":1000.0/p99,
        "note":"Frame interval includes VSync/scheduling; does not isolate GPU render duration"
    }

func _finish() -> void:
    _state=0
    set_process(false)
    var stats: Dictionary=summarize_frame_intervals(_frames_ms)
    var device: Dictionary={
        "platform":OS.get_name(),
        "model":OS.get_model_name(),
        "reportedGPUName":RenderingServer.get_video_adapter_name(),
        "reportedGPUVendor":RenderingServer.get_video_adapter_vendor(),
        "renderingMethod":RenderingServer.get_current_rendering_method(),
        "renderingDriver":RenderingServer.get_current_rendering_driver_name(),
        "Godot":Engine.get_version_info().get("string",""),
        "viewportSizePixels":str(get_viewport().get_visible_rect().size)
    }
    var report: Dictionary={
        "classification":"PHYSICAL_ANDROID_GODOT_FRAME_INTERVALS_MEASURED_NOT_GPU_PROFILER",
        "device":device,
        "startTimestampUnixSec":Time.get_unix_time_from_system(),
        "warmupSeconds":warmup_seconds,
        "sustainedSampleSeconds":sample_seconds,
        "sampleLabel":run_label,
        "sampledPerformance":stats,
        "maxDrawCalls":_draw_peak,
        "maxVisiblePrimitiveIndices":_primitives_peak,
        "maxVisibleGodotObjects":_objects_peak,
        "maxGodotStaticMemoryBytes":_static_memory_peak,
        "maxGodotReportedRenderMemoryBytes":_render_reported_memory_peak,
        "maxGodotReportedTextureMemoryBytes":_texture_reported_memory_peak,
        "reportedVideoMemoryMonitorSupported":_render_reported_memory_peak>0,
        "maxPhysicsProcessMs":_physics_peak_ms,
        "maxProcessMs":_process_peak_ms,
        "noOSLevelVRAMResidencyOrThermalTemperatureMeasured":true,
        "noTrueGPUFrameTimelineCaptured":true,
        "multiSceneSourceBatchPerformanceNotYetTestedUnlessSceneIsLoaded":true,
        "reportCapturedOnPhysicalAndroidRuntime":device["platform"]=="Android",
        "approvedForProductionWithoutVerification":false
    }
    var filename: String="user://nacht-physical-android-performance.json"
    var file: FileAccess=FileAccess.open(filename,FileAccess.WRITE)
    if file==null:
        push_error("XZOGOT_ANDROID_PHYSICAL_PROFILE_SAVE_RED "+str(FileAccess.get_open_error()))
        emit_signal("profile_finished",report)
        return
    file.store_string(JSON.stringify(report,"\t"))
    file.close()
    print("XZOGOT_NATIVE_ANDROID_PHYSICAL_PROFILE_CAPTURED ",
        " samples=",stats.get("frames",0)," p95Ms=",stats.get("p95FrameIntervalMs",-1),
        " file=",filename)
    emit_signal("profile_finished",report)

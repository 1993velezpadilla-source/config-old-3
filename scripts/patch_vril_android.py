#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_vril_android.py <vril-engine-dir>")

root = Path(sys.argv[1]).resolve()
source = root / "source"

if not source.is_dir():
    raise SystemExit(f"Vril source directory not found: {source}")

try:
    git_hash = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()
except Exception:
    git_hash = "unknown"

(source / "_build_info.h").write_text(
    '#define GIT_HASH "{}"\n'
    '#define GIT_BRANCH "xziel-android"\n'
    '#define BUILD_DATE "{}"\n'.format(
        git_hash,
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    ),
    encoding="utf-8",
)

gl_main = source / "platform" / "sdl" / "gl" / "gl_main.h"
text = gl_main.read_text(encoding="utf-8")
text = text.replace(
    "#else\n#include <GL/gl.h>\n#include <GL/glu.h>\n#endif",
    "#else\n#include <GL/gl.h>\n#ifndef __ANDROID__\n#include <GL/glu.h>\n#endif\n#endif",
)
gl_main.write_text(text, encoding="utf-8")

rmain = source / "platform" / "sdl" / "gl" / "gl_rmain.c"
text = rmain.read_text(encoding="utf-8")
text = text.replace(
    "gluPerspective (r_refdef.fov_y,  screenaspect,  4,  4096);",
    "MYgluPerspective (r_refdef.fov_y,  screenaspect,  4,  4096);",
)
rmain.write_text(text, encoding="utf-8")

vid = source / "platform" / "sdl" / "gl" / "gl_vidsdl.c"
text = vid.read_text(encoding="utf-8")

needle = '#include "../../../nzportable_def.h"\n#include "../sdl_local.h"\n'
replacement = (
    '#include "../../../nzportable_def.h"\n'
    '#include "../sdl_local.h"\n\n'
    '#ifdef __ANDROID__\n'
    'extern void initialize_gl4es(void);\n'
    '#endif\n'
)
if needle not in text:
    raise SystemExit("Could not find gl_vidsdl include block")
text = text.replace(needle, replacement, 1)

old_context = """\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 1);
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_COMPATIBILITY);
"""
new_context = """#ifdef __ANDROID__
\t/* GL4ES performs its own temporary EGL hardware probe and finishes by
\t * unbinding/terminating that EGL display. Run it before SDL creates the
\t * real game context so its cleanup cannot invalidate SDL's context. */
\tinitialize_gl4es();
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
#else
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 1);
\tSDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_COMPATIBILITY);
#endif
"""
if old_context not in text:
    raise SystemExit("Could not find desktop GL context setup")
text = text.replace(old_context, new_context, 1)

old_create = """\tsdl_gl_context = SDL_GL_CreateContext(sdl_window);
\tif (!sdl_gl_context) Sys_Error("SDL_GL_CreateContext: %s", SDL_GetError());
"""
new_create = """\tsdl_gl_context = SDL_GL_CreateContext(sdl_window);
\tif (!sdl_gl_context) Sys_Error("SDL_GL_CreateContext: %s", SDL_GetError());
#ifdef __ANDROID__
\tif (SDL_GL_MakeCurrent(sdl_window, sdl_gl_context) != 0)
\t\tSys_Error("SDL_GL_MakeCurrent: %s", SDL_GetError());
#endif
"""
if old_create not in text:
    raise SystemExit("Could not find SDL_GL_CreateContext block")
text = text.replace(old_create, new_create, 1)

vid.write_text(text, encoding="utf-8")

print(f"Patched Vril {git_hash} for Android/GL4ES")


# Android/Bionic does not expose gethostid(). Keep UDP multiplayer enabled by
# resolving the local hostname to an IPv4 address instead of disabling UDP.
udp = source / "platform" / "sdl" / "net_udp_sdl.c"
text = udp.read_text(encoding="utf-8")
old_udp = """	#if defined(_WIN32)
		{
			char hostname[256];
			struct hostent *hostentry;

			gethostname(hostname, sizeof(hostname));

			hostentry = gethostbyname(hostname);
			if (hostentry && hostentry->h_addr_list[0])
				myAddr = *(unsigned long *)hostentry->h_addr_list[0];
			else
				myAddr = inet_addr("127.0.0.1");
		}
	#else
		myAddr = gethostid();
	#endif
"""
new_udp = """	#if defined(_WIN32)
		{
			char hostname[256];
			struct hostent *hostentry;

			gethostname(hostname, sizeof(hostname));

			hostentry = gethostbyname(hostname);
			if (hostentry && hostentry->h_addr_list[0])
				myAddr = *(unsigned long *)hostentry->h_addr_list[0];
			else
				myAddr = inet_addr("127.0.0.1");
		}
	#elif defined(__ANDROID__)
		{
			char local_hostname[256] = "localhost";
			struct hostent *hostentry;
			struct in_addr resolved;

			if (gethostname(local_hostname, sizeof(local_hostname)) != 0)
				strcpy(local_hostname, "localhost");
			local_hostname[sizeof(local_hostname) - 1] = 0;

			hostentry = gethostbyname(local_hostname);
			if (hostentry && hostentry->h_addr_list[0]) {
				memcpy(&resolved.s_addr, hostentry->h_addr_list[0], sizeof(resolved.s_addr));
				myAddr = resolved.s_addr;
			} else {
				myAddr = inet_addr("127.0.0.1");
			}
		}
	#else
		myAddr = gethostid();
	#endif
"""
if old_udp not in text:
    raise SystemExit("Could not find UDP gethostid block")
text = text.replace(old_udp, new_udp, 1)
udp.write_text(text, encoding="utf-8")


# Persist coarse Android startup stages so a device-side crash can be
# diagnosed on the next launch even without adb/logcat.
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

android_diag = r'''
#ifdef __ANDROID__
#include <android/log.h>
static const char *xziel_diag_basedir = NULL;

static void Xziel_WriteStage(const char *stage)
{
    char path[1024];
    FILE *f;
    if (!xziel_diag_basedir || !stage)
        return;
    snprintf(path, sizeof(path), "%s/.xziel-stage", xziel_diag_basedir);
    f = fopen(path, "wb");
    if (f) {
        fwrite(stage, 1, strlen(stage), f);
        fwrite("\n", 1, 1, f);
        fclose(f);
    }
    __android_log_print(ANDROID_LOG_INFO, "Xziel", "stage=%s", stage);
}

static void Xziel_WriteError(const char *error)
{
    char path[1024];
    FILE *f;
    if (!xziel_diag_basedir || !error)
        return;
    snprintf(path, sizeof(path), "%s/.xziel-last-error", xziel_diag_basedir);
    f = fopen(path, "wb");
    if (f) {
        fwrite(error, 1, strlen(error), f);
        fwrite("\n", 1, 1, f);
        fclose(f);
    }
    __android_log_print(ANDROID_LOG_ERROR, "Xziel", "%s", error);
}
#endif
'''

needle = "#define DEFAULT_MEMORY_MB 128\n"
if android_diag not in text:
    text = text.replace(needle, needle + android_diag, 1)

old_system_error = 'void Sys_SystemError(char *error) { fprintf(stderr, "Vril Engine: %s\\n", error); if (SDL_WasInit(SDL_INIT_VIDEO)) SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Vril Engine", error, sdl_window); SDL_Quit(); exit(1); }'
new_system_error = '''void Sys_SystemError(char *error) {
#ifdef __ANDROID__
    Xziel_WriteError(error);
    Xziel_WriteStage("SYS_ERROR");
#endif
    fprintf(stderr, "Vril Engine: %s\\n", error);
    if (SDL_WasInit(SDL_INIT_VIDEO))
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Vril Engine", error, sdl_window);
    SDL_Quit();
    exit(1);
}'''
if old_system_error in text:
    text = text.replace(old_system_error, new_system_error, 1)

old_base = '''	if (!Startup_GetBaseDirectory(&startup, ".", &base_directory,
		startup_error, sizeof(startup_error))) {
		fprintf(stderr, "Startup: %s\\n", startup_error);
		Startup_FreeArguments(&startup);
		return 1;
	}
'''
new_base = old_base + '''#ifdef __ANDROID__
	xziel_diag_basedir = base_directory;
	Xziel_WriteStage("ARGS_READY");
#endif
'''
if old_base not in text:
    raise SystemExit("Could not find base-directory startup block")
text = text.replace(old_base, new_base, 1)

# Keep Android in landscape before SDL creates the video window. SDL2 otherwise
# maps a resizable window with no orientation hint to FULL_USER, which can
# rotate/recreate the Surface and invalidate the just-created EGL context.
android_orientation_needle = """	if (SDL_Init(headless_test ? SDL_INIT_TIMER :
"""
android_orientation_replacement = """#ifdef __ANDROID__
	SDL_SetHintWithPriority(SDL_HINT_ORIENTATIONS,
		"LandscapeLeft LandscapeRight", SDL_HINT_OVERRIDE);
#endif
	if (SDL_Init(headless_test ? SDL_INIT_TIMER :
"""
if android_orientation_needle not in text:
    raise SystemExit("Could not find SDL_Init orientation insertion point")
text = text.replace(android_orientation_needle, android_orientation_replacement, 1)

old_sdl = '''	if (SDL_Init(headless_test ? SDL_INIT_TIMER :
		(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_EVENTS | SDL_INIT_GAMECONTROLLER)) != 0) {
		fprintf(stderr, "SDL_Init: %s\\n", SDL_GetError());
		Startup_FreeArguments(&startup);
		return 1;
	}
'''
new_sdl = old_sdl + '''#ifdef __ANDROID__
	Xziel_WriteStage("SDL_INIT_OK");
#endif
'''
if old_sdl not in text:
    raise SystemExit("Could not find SDL_Init block")
text = text.replace(old_sdl, new_sdl, 1)

old_host = '''	Host_Init(&parms);
	oldtime = Sys_FloatTime();
	while (sdl_running) {
'''
new_host = '''#ifdef __ANDROID__
	Xziel_WriteStage("HOST_INIT_BEGIN");
#endif
	Host_Init(&parms);
#ifdef __ANDROID__
	Xziel_WriteStage("HOST_INIT_OK");
#endif
	oldtime = Sys_FloatTime();
	{
		int xziel_first_frame = 1;
	while (sdl_running) {
'''
if old_host not in text:
    raise SystemExit("Could not find Host_Init block")
text = text.replace(old_host, new_host, 1)

old_loop_tail = '''		music_update();
		oldtime = now;
	}
	if (host_initialized)
'''
new_loop_tail = '''		music_update();
		oldtime = now;
#ifdef __ANDROID__
		if (xziel_first_frame) {
			Xziel_WriteStage("FIRST_FRAME_OK");
			xziel_first_frame = 0;
		}
#endif
	}
	}
#ifdef __ANDROID__
	Xziel_WriteStage("CLEAN_EXIT");
#endif
	if (host_initialized)
'''
if old_loop_tail not in text:
    raise SystemExit("Could not find main loop tail")
text = text.replace(old_loop_tail, new_loop_tail, 1)

sys_sdl.write_text(text, encoding="utf-8")


# Android music fallback: Vril's SFX backend already owns an SDL audio device.
# SDL_mixer currently attempts to open a second device for MP3 music and can
# fail on Android/OpenSL ES. Do not abort the whole engine: keep SFX active and
# leave background music disabled until both paths are mixed through one device.
snd_music = source / "snd_music.c"
text = snd_music.read_text(encoding="utf-8")

old_music_init = """	if (music_init() == 0) {
		Sys_Error("Could not Initialize Music Subsystem.");
	}
"""
new_music_init = """	if (music_init() == 0) {
#ifdef __ANDROID__
		Con_Printf("Android music backend unavailable; continuing with SFX audio only.\\n");
		enabled = false;
		return;
#else
		Sys_Error("Could not Initialize Music Subsystem.");
#endif
	}
"""
if old_music_init not in text:
    raise SystemExit("Could not find Music_Init failure block")
text = text.replace(old_music_init, new_music_init, 1)

old_music_play = """void Music_PlayFromString(char* track_name, qboolean looping)
{
	Music_Stop();
"""
new_music_play = """void Music_PlayFromString(char* track_name, qboolean looping)
{
#ifdef __ANDROID__
	if (!enabled) return;
#endif
	Music_Stop();
"""
if old_music_play not in text:
    raise SystemExit("Could not find Music_PlayFromString block")
text = text.replace(old_music_play, new_music_play, 1)

old_music_shutdown = """void Music_Shutdown(void)
{
	Music_Stop();
	music_deinit();
}
"""
new_music_shutdown = """void Music_Shutdown(void)
{
#ifdef __ANDROID__
	if (!enabled) return;
#endif
	Music_Stop();
	music_deinit();
	enabled = false;
}
"""
if old_music_shutdown not in text:
    raise SystemExit("Could not find Music_Shutdown block")
text = text.replace(old_music_shutdown, new_music_shutdown, 1)

snd_music.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android native mobile controls v1
# ---------------------------------------------------------------------------
# Goals:
# - real SDL finger events, no touch->mouse synthesis
# - dynamic left movement stick
# - free-look on the right side
# - dedicated FIRE, ADS, ADS+FIRE, RELOAD, USE, JUMP, KNIFE, SWITCH buttons
# - semi-auto pistol auto-tap while FIRE is held
# - direct menu touch coordinates
# - tap/back to leave Game Over
#
# This intentionally uses Vril's existing input commands instead of inventing
# a parallel movement/weapon system.

in_sdl = source / "platform" / "sdl" / "in_sdl.c"
text = in_sdl.read_text(encoding="utf-8")

touch_externs = r'''
#ifdef __ANDROID__
extern qboolean xziel_mobile_move_active;
extern float xziel_mobile_move_x;
extern float xziel_mobile_move_y;
#endif
'''
inc = '#include "sdl_local.h"\n'
if touch_externs not in text:
    if inc not in text:
        raise SystemExit("Could not find in_sdl include anchor")
    text = text.replace(inc, inc + touch_externs, 1)

old_stick = r'''void IN_GetAnalogStick(in_analog_stick_id_t stick, in_analog_stick_t *value)
{
	SDL_GameControllerAxis xaxis = stick == IN_STICK_LEFT ? SDL_CONTROLLER_AXIS_LEFTX : SDL_CONTROLLER_AXIS_RIGHTX;
	SDL_GameControllerAxis yaxis = stick == IN_STICK_LEFT ? SDL_CONTROLLER_AXIS_LEFTY : SDL_CONTROLLER_AXIS_RIGHTY;
	value->x = value->y = 0.0f;
	if (!sdl_controller) return;
	value->x = SDL_GameControllerGetAxis(sdl_controller, xaxis) / 32767.0f;
	value->y = -SDL_GameControllerGetAxis(sdl_controller, yaxis) / 32767.0f;
}
'''
new_stick = r'''void IN_GetAnalogStick(in_analog_stick_id_t stick, in_analog_stick_t *value)
{
	SDL_GameControllerAxis xaxis = stick == IN_STICK_LEFT ? SDL_CONTROLLER_AXIS_LEFTX : SDL_CONTROLLER_AXIS_RIGHTX;
	SDL_GameControllerAxis yaxis = stick == IN_STICK_LEFT ? SDL_CONTROLLER_AXIS_LEFTY : SDL_CONTROLLER_AXIS_RIGHTY;
	value->x = value->y = 0.0f;
#ifdef __ANDROID__
	if (stick == IN_STICK_LEFT && xziel_mobile_move_active) {
		value->x = xziel_mobile_move_x;
		value->y = xziel_mobile_move_y;
		return;
	}
#endif
	if (!sdl_controller) return;
	value->x = SDL_GameControllerGetAxis(sdl_controller, xaxis) / 32767.0f;
	value->y = -SDL_GameControllerGetAxis(sdl_controller, yaxis) / 32767.0f;
}
'''
if old_stick not in text:
    raise SystemExit("Could not find IN_GetAnalogStick block")
text = text.replace(old_stick, new_stick, 1)
in_sdl.write_text(text, encoding="utf-8")

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

touch_core = r'''
#ifdef __ANDROID__
#define XZIEL_MAX_TOUCHES 12

typedef enum {
	XZ_TOUCH_NONE = 0,
	XZ_TOUCH_MOVE,
	XZ_TOUCH_LOOK,
	XZ_TOUCH_FIRE,
	XZ_TOUCH_ADSFIRE,
	XZ_TOUCH_ADS,
	XZ_TOUCH_RELOAD,
	XZ_TOUCH_USE,
	XZ_TOUCH_JUMP,
	XZ_TOUCH_KNIFE,
	XZ_TOUCH_SWITCH
} xziel_touch_role_t;

typedef struct {
	qboolean active;
	SDL_FingerID finger;
	xziel_touch_role_t role;
	float last_x;
	float last_y;
} xziel_touch_slot_t;

static xziel_touch_slot_t xziel_touches[XZIEL_MAX_TOUCHES];

qboolean xziel_mobile_move_active = false;
float xziel_mobile_move_x = 0.0f;
float xziel_mobile_move_y = 0.0f;
float xziel_mobile_move_anchor_x = 0.17f;
float xziel_mobile_move_anchor_y = 0.74f;

qboolean xziel_mobile_fire_pressed = false;
qboolean xziel_mobile_adsfire_pressed = false;
qboolean xziel_mobile_ads_pressed = false;
qboolean xziel_mobile_reload_pressed = false;
qboolean xziel_mobile_use_pressed = false;
qboolean xziel_mobile_jump_pressed = false;
qboolean xziel_mobile_knife_pressed = false;
qboolean xziel_mobile_switch_pressed = false;

static int xziel_attack_refs = 0;
static int xziel_aim_refs = 0;
static qboolean xziel_attack_command_down = false;
static Uint32 xziel_attack_release_ms = 0;
static Uint32 xziel_attack_next_ms = 0;

static qboolean Xziel_IsInside(float nx, float ny, float cx, float cy, float radius_h)
{
	float px = nx * (float)vid.width;
	float py = ny * (float)vid.height;
	float bx = cx * (float)vid.width;
	float by = cy * (float)vid.height;
	float r = radius_h * (float)vid.height;
	float dx = px - bx;
	float dy = py - by;
	return dx * dx + dy * dy <= r * r;
}

static qboolean Xziel_IsAutoTapPistol(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_COLT:
	case W_357:
	case W_KILLU:
	case W_BIATCH:
		return true;
	default:
		return false;
	}
}

static void Xziel_QueueHold(const char *down, const char *up, int *refs, qboolean pressed)
{
	if (pressed) {
		(*refs)++;
		if (*refs == 1)
			Cbuf_AddText((char *)down);
	} else {
		if (*refs > 0)
			(*refs)--;
		if (*refs == 0)
			Cbuf_AddText((char *)up);
	}
}

static void Xziel_SetAttackRef(qboolean pressed)
{
	if (pressed) {
		xziel_attack_refs++;
		if (xziel_attack_refs == 1) {
			xziel_attack_next_ms = SDL_GetTicks();
			xziel_attack_release_ms = 0;
		}
	} else {
		if (xziel_attack_refs > 0)
			xziel_attack_refs--;
		if (xziel_attack_refs == 0 && xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
		}
	}
}

static void Xziel_UpdateMobileFire(void)
{
	Uint32 now = SDL_GetTicks();

	if (xziel_attack_refs <= 0) {
		if (xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
		}
		return;
	}

	if (!Xziel_IsAutoTapPistol()) {
		if (!xziel_attack_command_down) {
			Cbuf_AddText("+attack\n");
			xziel_attack_command_down = true;
		}
		return;
	}

	/* Semi-auto pistols require a release between shots. Generate short,
	   bounded pulses while the mobile fire control is held. Weapon fire_delay
	   remains authoritative, so this cannot exceed the weapon's real ROF. */
	if (xziel_attack_command_down && now >= xziel_attack_release_ms) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
	}
	if (!xziel_attack_command_down && now >= xziel_attack_next_ms) {
		Cbuf_AddText("+attack\n");
		xziel_attack_command_down = true;
		xziel_attack_release_ms = now + 42;
		xziel_attack_next_ms = now + 92;
	}
}

static void Xziel_ActionDown(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = true;
		Xziel_SetAttackRef(true);
		break;
	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		Xziel_SetAttackRef(true);
		Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		break;
	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		break;
	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		Cbuf_AddText("+reload\n");
		break;
	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		Cbuf_AddText("+use\n");
		break;
	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = true;
		Cbuf_AddText("+jump\n");
		break;
	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = true;
		Cbuf_AddText("+knife\n");
		break;
	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		Cbuf_AddText("+switch\n");
		break;
	default:
		break;
	}
}

static void Xziel_ActionUp(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = false;
		Xziel_SetAttackRef(false);
		break;
	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;
		Xziel_SetAttackRef(false);
		Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
		break;
	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = false;
		Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
		break;
	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = false;
		Cbuf_AddText("-reload\n");
		break;
	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = false;
		Cbuf_AddText("-use\n");
		break;
	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = false;
		Cbuf_AddText("-jump\n");
		break;
	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = false;
		Cbuf_AddText("-knife\n");
		break;
	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = false;
		Cbuf_AddText("-switch\n");
		break;
	default:
		break;
	}
}

static xziel_touch_slot_t *Xziel_FindTouch(SDL_FingerID finger)
{
	int i;
	for (i = 0; i < XZIEL_MAX_TOUCHES; ++i)
		if (xziel_touches[i].active && xziel_touches[i].finger == finger)
			return &xziel_touches[i];
	return NULL;
}

static xziel_touch_slot_t *Xziel_AllocTouch(SDL_FingerID finger)
{
	int i;
	for (i = 0; i < XZIEL_MAX_TOUCHES; ++i) {
		if (!xziel_touches[i].active) {
			memset(&xziel_touches[i], 0, sizeof(xziel_touches[i]));
			xziel_touches[i].active = true;
			xziel_touches[i].finger = finger;
			return &xziel_touches[i];
		}
	}
	return NULL;
}

static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)
{
	/* Button cluster: COD-style separation leaves the middle-right area open
	   for free-look while keeping fire controls reachable by the thumb. */
	if (Xziel_IsInside(x, y, 0.885f, 0.585f, 0.073f)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, 0.795f, 0.435f, 0.056f)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, 0.695f, 0.575f, 0.047f)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, 0.805f, 0.785f, 0.044f)) return XZ_TOUCH_RELOAD;
	if (Xziel_IsInside(x, y, 0.605f, 0.675f, 0.044f)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, 0.695f, 0.790f, 0.044f)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, 0.915f, 0.800f, 0.044f)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, 0.905f, 0.300f, 0.041f)) return XZ_TOUCH_SWITCH;
	if (x < 0.45f && y > 0.30f) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_LOOK;
}

static void Xziel_UpdateMove(float x, float y)
{
	float dx, dy, len, radius_x, radius_y;
	radius_x = 0.16f * ((float)vid.height / (float)vid.width);
	radius_y = 0.16f;
	dx = (x - xziel_mobile_move_anchor_x) / radius_x;
	dy = (xziel_mobile_move_anchor_y - y) / radius_y;
	len = sqrtf(dx * dx + dy * dy);
	if (len < 0.10f) {
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
		return;
	}
	if (len > 1.0f) {
		dx /= len;
		dy /= len;
	}
	xziel_mobile_move_x = dx;
	xziel_mobile_move_y = dy;
}

static void Xziel_ReleaseAllTouches(void)
{
	int i;
	for (i = 0; i < XZIEL_MAX_TOUCHES; ++i) {
		if (!xziel_touches[i].active)
			continue;
		Xziel_ActionUp(xziel_touches[i].role);
		xziel_touches[i].active = false;
	}
	xziel_mobile_move_active = false;
	xziel_mobile_move_x = 0.0f;
	xziel_mobile_move_y = 0.0f;
	if (xziel_attack_command_down) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
	}
	xziel_attack_refs = 0;
	if (xziel_aim_refs > 0)
		Cbuf_AddText("-aim\n");
	xziel_aim_refs = 0;
}

static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)
{
	int mx = (int)(x * (float)vid.width);
	int my = (int)(y * (float)vid.height);
	qboolean slider_handled = false;

	Menu_MouseMove(mx, my);
	if (motion)
		return;

	if (down) {
		slider_handled = Menu_MouseButton(mx, my, true);
		if (!slider_handled)
			Menu_ButtonPress();
	} else {
		Menu_MouseButton(mx, my, false);
	}
}

static void Xziel_FingerDown(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;
	xziel_touch_role_t role;

	IN_SetActiveDevice(IN_DEVICE_KEYBOARD_MOUSE);
	Menu_SetInputDevice(IN_DEVICE_KEYBOARD_MOUSE);

	if (cl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
		Xziel_ReleaseAllTouches();
		Menu_ExitMap();
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		Xziel_MenuFinger(finger->x, finger->y, true, false);
		return;
	}

	if (key_dest != key_game)
		return;

	slot = Xziel_AllocTouch(finger->fingerId);
	if (!slot)
		return;

	role = Xziel_RoleForPoint(finger->x, finger->y);
	slot->role = role;
	slot->last_x = finger->x;
	slot->last_y = finger->y;

	if (role == XZ_TOUCH_MOVE) {
		xziel_mobile_move_active = true;
		xziel_mobile_move_anchor_x = finger->x;
		xziel_mobile_move_anchor_y = finger->y;
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (role != XZ_TOUCH_LOOK) {
		Xziel_ActionDown(role);
	}
}

static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		Xziel_MenuFinger(finger->x, finger->y, false, true);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
	if (!slot)
		return;

	if (slot->role == XZ_TOUCH_MOVE) {
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (slot->role == XZ_TOUCH_LOOK ||
		slot->role == XZ_TOUCH_FIRE ||
		slot->role == XZ_TOUCH_ADSFIRE ||
		slot->role == XZ_TOUCH_ADS) {
		/* Free-look remains active while dragging FIRE/ADS controls, matching
		   modern mobile FPS behavior. */
		mouse_dx += (int)((finger->x - slot->last_x) * (float)vid.width);
		mouse_dy += (int)((finger->y - slot->last_y) * (float)vid.height);
	}
	slot->last_x = finger->x;
	slot->last_y = finger->y;
}

static void Xziel_FingerUp(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		Xziel_MenuFinger(finger->x, finger->y, false, false);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
	if (!slot)
		return;

	if (slot->role == XZ_TOUCH_MOVE) {
		xziel_mobile_move_active = false;
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
	} else if (slot->role != XZ_TOUCH_LOOK) {
		Xziel_ActionUp(slot->role);
	}
	slot->active = false;
}
#endif
'''

mouse_anchor = "int mouse_dx;\nint mouse_dy;\n"
if touch_core not in text:
    if mouse_anchor not in text:
        raise SystemExit("Could not find SDL mouse globals anchor")
    text = text.replace(mouse_anchor, mouse_anchor + touch_core, 1)

# Android system Back behaves like Escape; on Game Over it exits the map.
key_anchor = "case SDLK_ESCAPE: return K_ESCAPE; case SDLK_RETURN: case SDLK_KP_ENTER: return K_ENTER;"
key_repl = """case SDLK_ESCAPE: return K_ESCAPE;
#ifdef __ANDROID__
\tcase SDLK_AC_BACK: return K_ESCAPE;
#endif
\tcase SDLK_RETURN: case SDLK_KP_ENTER: return K_ENTER;"""
if key_anchor not in text:
    raise SystemExit("Could not find SDL key mapping anchor")
text = text.replace(key_anchor, key_repl, 1)

# Handle direct finger events before synthetic mouse events.
event_anchor = "\t\tcase SDL_MOUSEBUTTONDOWN: case SDL_MOUSEBUTTONUP:\n"
event_repl = r'''#ifdef __ANDROID__
		case SDL_FINGERDOWN:
			Xziel_FingerDown(&event.tfinger);
			break;
		case SDL_FINGERMOTION:
			Xziel_FingerMotion(&event.tfinger);
			break;
		case SDL_FINGERUP:
			Xziel_FingerUp(&event.tfinger);
			break;
#endif
		case SDL_MOUSEBUTTONDOWN: case SDL_MOUSEBUTTONUP:
'''
if event_anchor not in text:
    raise SystemExit("Could not find SDL event insertion anchor")
text = text.replace(event_anchor, event_repl, 1)

# Back key shortcut for the end screen.
keydown_anchor = """\t\tcase SDL_KEYDOWN: case SDL_KEYUP:
\t\t\tif (event.type == SDL_KEYDOWN) { IN_SetActiveDevice(IN_DEVICE_KEYBOARD_MOUSE); Menu_SetInputDevice(IN_DEVICE_KEYBOARD_MOUSE); }
"""
keydown_repl = """\t\tcase SDL_KEYDOWN: case SDL_KEYUP:
\t\t\tif (event.type == SDL_KEYDOWN) { IN_SetActiveDevice(IN_DEVICE_KEYBOARD_MOUSE); Menu_SetInputDevice(IN_DEVICE_KEYBOARD_MOUSE); }
#ifdef __ANDROID__
\t\t\tif (event.type == SDL_KEYDOWN && event.key.keysym.sym == SDLK_AC_BACK &&
\t\t\t\tcl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
\t\t\t\tXziel_ReleaseAllTouches();
\t\t\t\tMenu_ExitMap();
\t\t\t\tbreak;
\t\t\t}
#endif
"""
if keydown_anchor not in text:
    raise SystemExit("Could not find SDL keydown block")
text = text.replace(keydown_anchor, keydown_repl, 1)

# Release held virtual buttons if Android loses focus, and advance auto-fire
# once per input pump.
window_anchor = """\t\tcase SDL_WINDOWEVENT:
\t\t\tif (event.window.event == SDL_WINDOWEVENT_SIZE_CHANGED || event.window.event == SDL_WINDOWEVENT_RESIZED)
\t\t\t\tVID_SDLResize();
\t\t\tbreak;
"""
window_repl = """\t\tcase SDL_WINDOWEVENT:
\t\t\tif (event.window.event == SDL_WINDOWEVENT_SIZE_CHANGED || event.window.event == SDL_WINDOWEVENT_RESIZED)
\t\t\t\tVID_SDLResize();
#ifdef __ANDROID__
\t\t\tif (event.window.event == SDL_WINDOWEVENT_FOCUS_LOST ||
\t\t\t\tevent.window.event == SDL_WINDOWEVENT_MINIMIZED)
\t\t\t\tXziel_ReleaseAllTouches();
#endif
\t\t\tbreak;
"""
if window_anchor not in text:
    raise SystemExit("Could not find SDL window-event block")
text = text.replace(window_anchor, window_repl, 1)

pump_anchor = """\t}
\tSDL_SetRelativeMouseMode((key_dest == key_game && SDL_GetKeyboardFocus() == sdl_window) ? SDL_TRUE : SDL_FALSE);
}
"""
pump_repl = """\t}
#ifdef __ANDROID__
\tXziel_UpdateMobileFire();
\t/* Touch is handled directly above. Avoid Android relative-mouse capture and
\t   SDL's touch-mouse path fighting the mobile camera. */
\tSDL_SetRelativeMouseMode(SDL_FALSE);
#else
\tSDL_SetRelativeMouseMode((key_dest == key_game && SDL_GetKeyboardFocus() == sdl_window) ? SDL_TRUE : SDL_FALSE);
#endif
}
"""
if pump_anchor not in text:
    raise SystemExit("Could not find SDL event-pump tail")
text = text.replace(pump_anchor, pump_repl, 1)

# Stop SDL from synthesizing mouse button/motion events for finger input.
hint_anchor = """#ifdef __ANDROID__
\tSDL_SetHintWithPriority(SDL_HINT_ORIENTATIONS,
\t\t"LandscapeLeft LandscapeRight", SDL_HINT_OVERRIDE);
#endif
"""
hint_repl = """#ifdef __ANDROID__
\tSDL_SetHintWithPriority(SDL_HINT_ORIENTATIONS,
\t\t"LandscapeLeft LandscapeRight", SDL_HINT_OVERRIDE);
\tSDL_SetHintWithPriority(SDL_HINT_TOUCH_MOUSE_EVENTS, "0", SDL_HINT_OVERRIDE);
#endif
"""
if hint_anchor not in text:
    raise SystemExit("Could not find Android SDL hint block")
text = text.replace(hint_anchor, hint_repl, 1)

sys_sdl.write_text(text, encoding="utf-8")

# Draw a native mobile HUD over the existing game HUD. No external artwork is
# used; controls are translucent geometry/text so they can be restyled later.
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")

mobile_hud = r'''
#ifdef __ANDROID__
extern qboolean xziel_mobile_move_active;
extern float xziel_mobile_move_x;
extern float xziel_mobile_move_y;
extern float xziel_mobile_move_anchor_x;
extern float xziel_mobile_move_anchor_y;
extern qboolean xziel_mobile_fire_pressed;
extern qboolean xziel_mobile_adsfire_pressed;
extern qboolean xziel_mobile_ads_pressed;
extern qboolean xziel_mobile_reload_pressed;
extern qboolean xziel_mobile_use_pressed;
extern qboolean xziel_mobile_jump_pressed;
extern qboolean xziel_mobile_knife_pressed;
extern qboolean xziel_mobile_switch_pressed;

static void Xziel_DrawDisc(int cx, int cy, int radius, int r, int g, int b, int a)
{
	int y;
	int step = radius / 10;
	if (step < 2) step = 2;
	for (y = -radius; y <= radius; y += step) {
		float fy = (float)y;
		int half = (int)sqrtf((float)(radius * radius) - fy * fy);
		Draw_FillByColor(cx - half, cy + y, half * 2, step + 1, r, g, b, a);
	}
}

static void Xziel_DrawTouchButton(float nx, float ny, float radius_h,
	const char *label1, const char *label2, qboolean pressed)
{
	int cx = (int)(nx * vid.width);
	int cy = (int)(ny * vid.height);
	int radius = (int)(radius_h * vid.height);
	int inner = radius - (int)(2.0f * vid.scale);
	float text_scale = vid.scale * 0.70f;
	int tw;

	if (inner < 2) inner = 2;
	Xziel_DrawDisc(cx, cy, radius, 235, 235, 235, pressed ? 150 : 95);
	Xziel_DrawDisc(cx, cy, inner, pressed ? 110 : 8, pressed ? 18 : 8,
		pressed ? 18 : 8, pressed ? 155 : 105);

	if (label1 && label1[0]) {
		tw = getTextWidth((char *)label1, text_scale);
		Draw_ColoredString(cx - tw / 2,
			cy - (label2 && label2[0] ? (int)(7 * vid.scale) : (int)(3 * vid.scale)),
			(char *)label1, 255, 255, 255, 235, text_scale);
	}
	if (label2 && label2[0]) {
		tw = getTextWidth((char *)label2, text_scale);
		Draw_ColoredString(cx - tw / 2, cy + (int)(3 * vid.scale),
			(char *)label2, 255, 255, 255, 235, text_scale);
	}
}

static void Xziel_MobileHUD_Draw(void)
{
	int base_x, base_y, knob_x, knob_y, radius, knob_r;

	if (key_dest != key_game || cl.stats[STAT_HEALTH] <= 0)
		return;

	/* Dynamic joystick, with a faint home position before first touch. */
	base_x = (int)((xziel_mobile_move_active ? xziel_mobile_move_anchor_x : 0.17f) * vid.width);
	base_y = (int)((xziel_mobile_move_active ? xziel_mobile_move_anchor_y : 0.74f) * vid.height);
	radius = (int)(0.095f * vid.height);
	knob_r = (int)(0.042f * vid.height);
	Xziel_DrawDisc(base_x, base_y, radius, 240, 240, 240, 55);
	Xziel_DrawDisc(base_x, base_y, radius - (int)(2 * vid.scale), 0, 0, 0, 45);
	knob_x = base_x + (int)(xziel_mobile_move_x * radius * 0.72f);
	knob_y = base_y - (int)(xziel_mobile_move_y * radius * 0.72f);
	Xziel_DrawDisc(knob_x, knob_y, knob_r, 245, 245, 245,
		xziel_mobile_move_active ? 125 : 70);

	Xziel_DrawTouchButton(0.885f, 0.585f, 0.073f, "FIRE", "", xziel_mobile_fire_pressed);
	Xziel_DrawTouchButton(0.795f, 0.435f, 0.056f, "ADS", "FIRE", xziel_mobile_adsfire_pressed);
	Xziel_DrawTouchButton(0.695f, 0.575f, 0.047f, "ADS", "", xziel_mobile_ads_pressed);
	Xziel_DrawTouchButton(0.805f, 0.785f, 0.044f, "RLD", "", xziel_mobile_reload_pressed);
	Xziel_DrawTouchButton(0.605f, 0.675f, 0.044f, "USE", "", xziel_mobile_use_pressed);
	Xziel_DrawTouchButton(0.695f, 0.790f, 0.044f, "JUMP", "", xziel_mobile_jump_pressed);
	Xziel_DrawTouchButton(0.915f, 0.800f, 0.044f, "KNIFE", "", xziel_mobile_knife_pressed);
	Xziel_DrawTouchButton(0.905f, 0.300f, 0.041f, "SWAP", "", xziel_mobile_switch_pressed);
}

static void Xziel_MobileGameOverPrompt(void)
{
	const char *msg = "TAP TO RETURN TO MENU";
	float s = vid.scale;
	int w = getTextWidth((char *)msg, s);
	Draw_ColoredString((vid.width - w) / 2, vid.height - (int)(28 * vid.scale),
		(char *)msg, 255, 255, 255, 235, s);
}
#endif
'''

hud_anchor = "void\nHUD_Draw(void)\n{"
if mobile_hud not in text:
    if hud_anchor not in text:
        raise SystemExit("Could not find HUD_Draw anchor")
    text = text.replace(hud_anchor, mobile_hud + "\n" + hud_anchor, 1)

gameover_anchor = """    if (cl.stats[STAT_HEALTH] <= 0 || showscoreboard == true) {
        HUD_EndScreen();

        // Make sure we still draw the screen flash.
"""
gameover_repl = """    if (cl.stats[STAT_HEALTH] <= 0 || showscoreboard == true) {
        HUD_EndScreen();
#ifdef __ANDROID__
        if (cl.stats[STAT_HEALTH] <= 0)
            Xziel_MobileGameOverPrompt();
#endif

        // Make sure we still draw the screen flash.
"""
if gameover_anchor not in text:
    raise SystemExit("Could not find HUD game-over block")
text = text.replace(gameover_anchor, gameover_repl, 1)

zoom_anchor = """    if (cl.stats[STAT_ZOOM] == 2) {
        if (screenflash_duration > sv.time)
            HUD_Screenflash();
        return;
    }
"""
zoom_repl = """    if (cl.stats[STAT_ZOOM] == 2) {
        if (screenflash_duration > sv.time)
            HUD_Screenflash();
#ifdef __ANDROID__
        Xziel_MobileHUD_Draw();
#endif
        return;
    }
"""
if zoom_anchor not in text:
    raise SystemExit("Could not find scoped HUD block")
text = text.replace(zoom_anchor, zoom_repl, 1)

gamemode_anchor = """        if (screenflash_duration > sv.time)
            HUD_Screenflash();

        return;
    }

    if (bettyprompt_time > sv.time)
"""
gamemode_repl = """        if (screenflash_duration > sv.time)
            HUD_Screenflash();
#ifdef __ANDROID__
        Xziel_MobileHUD_Draw();
#endif

        return;
    }

    if (bettyprompt_time > sv.time)
"""
if gamemode_anchor not in text:
    raise SystemExit("Could not find special gamemode HUD block")
text = text.replace(gamemode_anchor, gamemode_repl, 1)

hud_tail = """    // This should always come last!
    if (screenflash_duration > sv.time)
        HUD_Screenflash();
} /* HUD_Draw */
"""
hud_tail_repl = """    // This should always come last!
    if (screenflash_duration > sv.time)
        HUD_Screenflash();
#ifdef __ANDROID__
    Xziel_MobileHUD_Draw();
#endif
} /* HUD_Draw */
"""
if hud_tail not in text:
    raise SystemExit("Could not find HUD tail")
text = text.replace(hud_tail, hud_tail_repl, 1)

hud.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android mobile UX v0.4
# Sprint threshold, persistent mobile settings, contextual use, pause/save/
# resume countdown, stronger gyro and cleaner COD-style HUD behavior.
# ---------------------------------------------------------------------------

# Persistent mobile cvars live in input.c so Host_WriteConfiguration writes
# them to config.cfg automatically (archive=true).
inp = source / "input.c"
text = inp.read_text(encoding="utf-8")

mobile_cvars = r'''
#ifdef __ANDROID__
cvar_t xziel_mobile_ads_toggle = {"xziel_mobile_ads_toggle", "0", true};
cvar_t xziel_mobile_sprint_threshold = {"xziel_mobile_sprint_threshold", "0.84", true};
cvar_t xziel_mobile_touch_sensitivity = {"xziel_mobile_touch_sensitivity", "1.15", true};
cvar_t xziel_mobile_ads_sensitivity = {"xziel_mobile_ads_sensitivity", "0.62", true};
cvar_t xziel_mobile_gyro_boost = {"xziel_mobile_gyro_boost", "5.0", true};
cvar_t xziel_mobile_hud_scale = {"xziel_mobile_hud_scale", "1.0", true};
cvar_t xziel_mobile_hud_opacity = {"xziel_mobile_hud_opacity", "0.72", true};
cvar_t xziel_mobile_autofire_ms = {"xziel_mobile_autofire_ms", "185", true};
#endif
'''
active_anchor = "static in_device_t in_active_device = IN_DEVICE_KEYBOARD_MOUSE;\n"
if mobile_cvars not in text:
    if active_anchor not in text:
        raise SystemExit("Could not find input.c active-device anchor")
    text = text.replace(active_anchor, active_anchor + mobile_cvars, 1)

register_anchor = """void IN_Init(void)
{
"""
register_repl = """void IN_Init(void)
{
#ifdef __ANDROID__
	Cvar_RegisterVariable(&xziel_mobile_ads_toggle);
	Cvar_RegisterVariable(&xziel_mobile_sprint_threshold);
	Cvar_RegisterVariable(&xziel_mobile_touch_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_ads_sensitivity);
	Cvar_RegisterVariable(&xziel_mobile_gyro_boost);
	Cvar_RegisterVariable(&xziel_mobile_hud_scale);
	Cvar_RegisterVariable(&xziel_mobile_hud_opacity);
	Cvar_RegisterVariable(&xziel_mobile_autofire_ms);
	Cvar_RegisterVariable(&xziel_bot_telemetry);
#endif
"""
if "Cvar_RegisterVariable(&xziel_mobile_ads_toggle);" not in text:
    if register_anchor not in text:
        raise SystemExit("Could not find IN_Init anchor")
    text = text.replace(register_anchor, register_repl, 1)

gyro_anchor = """			cl.viewangles[YAW] += gyro_y * radians_to_degrees * in_gyro_sensitivity_x.value * gyro_scale * (float)host_frametime;
			cl.viewangles[PITCH] -= gyro_x * radians_to_degrees * in_gyro_sensitivity_y.value * (m_pitch.value > 0 ? -1.0f : 1.0f) * gyro_scale * (float)host_frametime;
"""
gyro_repl = """#ifdef __ANDROID__
			gyro_scale *= xziel_mobile_gyro_boost.value;
#endif
			cl.viewangles[YAW] += gyro_y * radians_to_degrees * in_gyro_sensitivity_x.value * gyro_scale * (float)host_frametime;
			cl.viewangles[PITCH] -= gyro_x * radians_to_degrees * in_gyro_sensitivity_y.value * (m_pitch.value > 0 ? -1.0f : 1.0f) * gyro_scale * (float)host_frametime;
"""
if "gyro_scale *= xziel_mobile_gyro_boost.value;" not in text:
    if gyro_anchor not in text:
        raise SystemExit("Could not find gyro scaling anchor")
    text = text.replace(gyro_anchor, gyro_repl, 1)
inp.write_text(text, encoding="utf-8")

# Update Android touch runtime.
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

externs_anchor = "#ifdef __ANDROID__\n#define XZIEL_MAX_TOUCHES 12\n"
externs_repl = """#ifdef __ANDROID__
extern cvar_t xziel_mobile_ads_toggle;
extern cvar_t xziel_mobile_sprint_threshold;
extern cvar_t xziel_mobile_touch_sensitivity;
extern cvar_t xziel_mobile_ads_sensitivity;
extern cvar_t xziel_mobile_autofire_ms;
extern qboolean xziel_mobile_use_available;
#define XZIEL_MAX_TOUCHES 12
"""
if "extern cvar_t xziel_mobile_ads_toggle;" not in text:
    if externs_anchor not in text:
        raise SystemExit("Could not find mobile touch block anchor")
    text = text.replace(externs_anchor, externs_repl, 1)

# Add Pause role.
text = text.replace(
"""	XZ_TOUCH_KNIFE,
	XZ_TOUCH_SWITCH
} xziel_touch_role_t;""",
"""	XZ_TOUCH_KNIFE,
	XZ_TOUCH_SWITCH,
	XZ_TOUCH_PAUSE
} xziel_touch_role_t;""", 1)

# Sprint state.
state_anchor = "static Uint32 xziel_attack_next_ms = 0;\n"
state_repl = """static Uint32 xziel_attack_next_ms = 0;
static qboolean xziel_mobile_sprint_active = false;
"""
if "xziel_mobile_sprint_active" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find mobile fire state anchor")
    text = text.replace(state_anchor, state_repl, 1)

# Slow semi-auto pulse to a COD-mobile-like pace; server fire_delay remains authoritative.
old_next = "xziel_attack_next_ms = now + 92;"
new_next = "xziel_attack_next_ms = now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);"
if old_next in text:
    text = text.replace(old_next, new_next, 1)

# Separate ADS button can be HOLD or TOGGLE. ADS+FIRE always behaves as hold.
ads_down_old = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		break;
"""
ads_down_new = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		if (xziel_mobile_ads_toggle.value >= 0.5f)
			Cbuf_AddText("impulse 26\\n");
		else
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		break;
"""
if ads_down_old not in text:
    raise SystemExit("Could not find ADS down block")
text = text.replace(ads_down_old, ads_down_new, 1)

ads_up_old = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = false;
		Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, false);
		break;
"""
ads_up_new = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = false;
		if (xziel_mobile_ads_toggle.value < 0.5f)
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, false);
		break;
"""
if ads_up_old not in text:
    raise SystemExit("Could not find ADS up block")
text = text.replace(ads_up_old, ads_up_new, 1)

# Contextual use + Pause hit region.
role_old = """	if (Xziel_IsInside(x, y, 0.605f, 0.675f, 0.044f)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, 0.695f, 0.790f, 0.044f)) return XZ_TOUCH_JUMP;
"""
role_new = """	if (xziel_mobile_use_available && Xziel_IsInside(x, y, 0.605f, 0.675f, 0.050f)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, 0.965f, 0.075f, 0.036f)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, 0.695f, 0.790f, 0.044f)) return XZ_TOUCH_JUMP;
"""
if role_old not in text:
    raise SystemExit("Could not find mobile role layout block")
text = text.replace(role_old, role_new, 1)

# Pause is immediate on touch-down.
action_down_anchor = """	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		Cbuf_AddText("+switch\\n");
		break;
	default:
"""
action_down_repl = """	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		Cbuf_AddText("+switch\\n");
		break;
	case XZ_TOUCH_PAUSE:
		Xziel_ReleaseAllTouches();
		Menu_Pause_Set();
		break;
	default:
"""
# Xziel_ReleaseAllTouches is defined later, so call would be undeclared in C99.
# Use Menu_Pause_Set only; touch-up will be harmless because menu input takes over.
action_down_repl = action_down_repl.replace("\t\tXziel_ReleaseAllTouches();\n", "")
if "case XZ_TOUCH_PAUSE:" not in text:
    if action_down_anchor not in text:
        raise SystemExit("Could not find action down tail")
    text = text.replace(action_down_anchor, action_down_repl, 1)

# Sprint when stick crosses forward threshold; stop when it drops back.
move_tail_old = """	xziel_mobile_move_x = dx;
	xziel_mobile_move_y = dy;
}
"""
move_tail_new = """	xziel_mobile_move_x = dx;
	xziel_mobile_move_y = dy;

	if (dy >= xziel_mobile_sprint_threshold.value) {
		if (!xziel_mobile_sprint_active) {
			Cbuf_AddText("impulse 23\\n");
			xziel_mobile_sprint_active = true;
		}
	} else if (xziel_mobile_sprint_active) {
		Cbuf_AddText("impulse 24\\n");
		xziel_mobile_sprint_active = false;
	}
}
"""
if move_tail_old not in text:
    raise SystemExit("Could not find Xziel_UpdateMove tail")
text = text.replace(move_tail_old, move_tail_new, 1)

# Stop sprint on joystick release and global touch release.
move_up_old = """		xziel_mobile_move_active = false;
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
"""
move_up_new = """		xziel_mobile_move_active = false;
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
		if (xziel_mobile_sprint_active) {
			Cbuf_AddText("impulse 24\\n");
			xziel_mobile_sprint_active = false;
		}
"""
# Replace both relevant clear sequences.
text = text.replace(move_up_old, move_up_new)

# Look sensitivity and separate ADS dampening.
look_old = """		mouse_dx += (int)((finger->x - slot->last_x) * (float)vid.width);
		mouse_dy += (int)((finger->y - slot->last_y) * (float)vid.height);
"""
look_new = """		{
			float look_scale = xziel_mobile_touch_sensitivity.value;
			if (cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)
				look_scale *= xziel_mobile_ads_sensitivity.value;
			mouse_dx += (int)((finger->x - slot->last_x) * (float)vid.width * look_scale);
			mouse_dy += (int)((finger->y - slot->last_y) * (float)vid.height * look_scale);
		}
"""
if look_old not in text:
    raise SystemExit("Could not find touch look delta block")
text = text.replace(look_old, look_new, 1)

# Pause role should not expect an up command.
up_tail = """	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = false;
		Cbuf_AddText("-switch\\n");
		break;
	default:
"""
up_tail_repl = """	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = false;
		Cbuf_AddText("-switch\\n");
		break;
	case XZ_TOUCH_PAUSE:
		break;
	default:
"""
if up_tail not in text:
    raise SystemExit("Could not find action up tail")
text = text.replace(up_tail, up_tail_repl, 1)

sys_sdl.write_text(text, encoding="utf-8")

# Expose the existing NZ:P useprint as a contextual mobile action.
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")

use_global_anchor = "static int hud_use_type;\n"
use_global_repl = """static int hud_use_type;
#ifdef __ANDROID__
qboolean xziel_mobile_use_available = false;
extern cvar_t xziel_hud_use_x;
extern cvar_t xziel_hud_use_y;
#endif
"""
if "qboolean xziel_mobile_use_available" not in text:
    if use_global_anchor not in text:
        raise SystemExit("Could not find HUD use globals")
    text = text.replace(use_global_anchor, use_global_repl, 1)

use_inactive_old = """    if (Sys_FloatTime() >= hud_use_until || key_dest != key_game || cl.stats[STAT_HEALTH] <= 0) {
        scr_usetime_off = 0;
        return;
    }
"""
use_inactive_new = """    if (Sys_FloatTime() >= hud_use_until || key_dest != key_game || cl.stats[STAT_HEALTH] <= 0) {
        scr_usetime_off = 0;
#ifdef __ANDROID__
        xziel_mobile_use_available = false;
#endif
        return;
    }
#ifdef __ANDROID__
    xziel_mobile_use_available = true;
#endif
"""
if use_inactive_old not in text:
    raise SystemExit("Could not find HUD use active test")
text = text.replace(use_inactive_old, use_inactive_new, 1)

# Reposition prompt on Android into a COD-like contextual card near USE button.
use_xy_old = """    y = vid.height - 74 * vid.scale;
    x = (vid.width - getTextWidth(hud_usestring, vid.scale)) / 2;
"""
use_xy_new = """#ifdef __ANDROID__
    y = (int)(vid.height * 0.54f);
    x = (int)(vid.width * 0.48f) - getTextWidth(hud_usestring, vid.scale);
#else
    y = vid.height - 74 * vid.scale;
    x = (vid.width - getTextWidth(hud_usestring, vid.scale)) / 2;
#endif
"""
if use_xy_old not in text:
    raise SystemExit("Could not find HUD use coordinates")
text = text.replace(use_xy_old, use_xy_new, 1)

# Mobile HUD cvar externs and scale/opacity.
hud_extern_anchor = """extern qboolean xziel_mobile_switch_pressed;

static void Xziel_DrawDisc"""
hud_extern_repl = """extern qboolean xziel_mobile_switch_pressed;
extern qboolean xziel_mobile_use_available;
extern cvar_t xziel_mobile_hud_scale;
extern cvar_t xziel_mobile_hud_opacity;

static void Xziel_DrawDisc"""
if hud_extern_anchor not in text:
    raise SystemExit("Could not find mobile HUD extern anchor")
text = text.replace(hud_extern_anchor, hud_extern_repl, 1)

# Clean circle rendering and use cvar opacity.
disc_old = """	int y;
	int step = radius / 10;
	if (step < 2) step = 2;
	for (y = -radius; y <= radius; y += step) {
"""
disc_new = """	int y;
	int step = 2;
	for (y = -radius; y <= radius; y += step) {
"""
if disc_old not in text:
    raise SystemExit("Could not find mobile disc renderer")
text = text.replace(disc_old, disc_new, 1)

button_radius_old = "int radius = (int)(radius_h * vid.height);"
button_radius_new = "int radius = (int)(radius_h * vid.height * xziel_mobile_hud_scale.value);"
text = text.replace(button_radius_old, button_radius_new, 1)

# Replace fixed alpha values with persistent HUD opacity multiplier.
text = text.replace("pressed ? 150 : 95", "(int)((pressed ? 190 : 125) * xziel_mobile_hud_opacity.value)", 1)
text = text.replace("pressed ? 155 : 105", "(int)((pressed ? 180 : 130) * xziel_mobile_hud_opacity.value)", 1)

# USE only while prompt is active, plus Pause button.
use_draw_old = """	Xziel_DrawTouchButton(0.605f, 0.675f, 0.044f, "USE", "", xziel_mobile_use_pressed);
	Xziel_DrawTouchButton(0.695f, 0.790f, 0.044f, "JUMP", "", xziel_mobile_jump_pressed);
"""
use_draw_new = """	if (xziel_mobile_use_available)
		Xziel_DrawTouchButton(0.605f, 0.675f, 0.050f, "USE", "", xziel_mobile_use_pressed);
	Xziel_DrawTouchButton(0.965f, 0.075f, 0.036f, "II", "", false);
	Xziel_DrawTouchButton(0.695f, 0.790f, 0.044f, "JUMP", "", xziel_mobile_jump_pressed);
"""
if use_draw_old not in text:
    raise SystemExit("Could not find mobile USE HUD line")
text = text.replace(use_draw_old, use_draw_new, 1)

hud.write_text(text, encoding="utf-8")

# Mobile Controls menu integrated into existing menu system.
defs = source / "menu" / "menu_defs.h"
text = defs.read_text(encoding="utf-8")
if "#define m_mobile" not in text:
    text = text.replace("#define m_gyro\t\t\t24\n", "#define m_gyro\t\t\t24\n#define m_mobile\t\t25\n", 1)
    text = text.replace("void Menu_Controls_Set(void);\n", "void Menu_Controls_Set(void);\nvoid Menu_Mobile_Set(void);\nvoid Menu_Mobile_Draw(void);\n", 1)
    text = text.replace("void Menu_Controls_Set (void);\n", "void Menu_Controls_Set (void);\nvoid Menu_Mobile_Set(void);\nvoid Menu_Mobile_Draw(void);\n", 1)
defs.write_text(text, encoding="utf-8")

menu = source / "menu" / "menu.c"
text = menu.read_text(encoding="utf-8")
mobile_case_anchor = """	case m_controls:
		Menu_Controls_Draw ();
		break;
"""
mobile_case_repl = """	case m_controls:
		Menu_Controls_Draw ();
		break;
#ifdef __ANDROID__
	case m_mobile:
		Menu_Mobile_Draw ();
		break;
#endif
"""
if "case m_mobile:" not in text:
    if mobile_case_anchor not in text:
        raise SystemExit("Could not find menu controls switch")
    text = text.replace(mobile_case_anchor, mobile_case_repl, 1)
menu.write_text(text, encoding="utf-8")

menu_sys = source / "menu" / "menu_sys.c"
text = menu_sys.read_text(encoding="utf-8")
prev_anchor = """		case m_controls:
			Menu_Controls_Set();
			break;
"""
prev_repl = """		case m_controls:
			Menu_Controls_Set();
			break;
#ifdef __ANDROID__
		case m_mobile:
			Menu_Mobile_Set();
			break;
#endif
"""
if "case m_mobile:" not in text:
    if prev_anchor not in text:
        raise SystemExit("Could not find previous-menu controls block")
    text = text.replace(prev_anchor, prev_repl, 1)
menu_sys.write_text(text, encoding="utf-8")

controls = source / "menu" / "menu_controls.c"
text = controls.read_text(encoding="utf-8")

mobile_menu_code = r'''
#ifdef __ANDROID__
extern cvar_t xziel_mobile_ads_toggle;
extern cvar_t xziel_mobile_sprint_threshold;
extern cvar_t xziel_mobile_touch_sensitivity;
extern cvar_t xziel_mobile_ads_sensitivity;
extern cvar_t xziel_mobile_gyro_boost;
extern cvar_t xziel_mobile_hud_scale;
extern cvar_t xziel_mobile_hud_opacity;
extern cvar_t xziel_mobile_autofire_ms;

static char *xziel_ads_mode_string;

static void Menu_Mobile_ToggleADS(void)
{
	Cvar_SetValue("xziel_mobile_ads_toggle",
		xziel_mobile_ads_toggle.value >= 0.5f ? 0.0f : 1.0f);
}

void Menu_Mobile_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_controls;
	m_state = m_mobile;
}

void Menu_Mobile_Draw(void)
{
	int idx = 0;
	int row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE CONTROLS", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	xziel_ads_mode_string = xziel_mobile_ads_toggle.value >= 0.5f ? "TOGGLE" : "HOLD";

	Menu_DrawButton(row++, idx++, "ADS BEHAVIOR", "Choose Hold or Toggle for the dedicated ADS button.", Menu_Mobile_ToggleADS);
	Menu_DrawOptionButton(row-1, xziel_ads_mode_string);

	Menu_DrawButton(row++, idx++, "TOUCH LOOK", "Camera sensitivity while swiping the screen.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.35f, 3.0f, xziel_mobile_touch_sensitivity, "xziel_mobile_touch_sensitivity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "ADS LOOK", "Sensitivity multiplier while aiming down sights.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.25f, 1.0f, xziel_mobile_ads_sensitivity, "xziel_mobile_ads_sensitivity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "AUTO SPRINT", "How far forward the movement stick must travel before sprinting.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.65f, 0.98f, xziel_mobile_sprint_threshold, "xziel_mobile_sprint_threshold", false, true, 0.01f);

	Menu_DrawButton(row++, idx++, "PISTOL AUTO FIRE", "Milliseconds between automatic semi-auto trigger taps.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 140.0f, 320.0f, xziel_mobile_autofire_ms, "xziel_mobile_autofire_ms", false, true, 10.0f);

	Menu_DrawButton(row++, idx++, "HUD SCALE", "Scale all mobile HUD buttons.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.70f, 1.35f, xziel_mobile_hud_scale, "xziel_mobile_hud_scale", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "HUD OPACITY", "Opacity of mobile controls.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.30f, 1.0f, xziel_mobile_hud_opacity, "xziel_mobile_hud_opacity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "GYRO BOOST", "Extra multiplier for phone gyroscope input.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 1.0f, 12.0f, xziel_mobile_gyro_boost, "xziel_mobile_gyro_boost", false, true, 0.5f);

	Menu_DrawButton(-1, idx, "BACK", "Return to Control Options.", Menu_Controls_Set);
}
#endif
'''
if "void Menu_Mobile_Draw(void)" not in text:
    text += "\n" + mobile_menu_code

# Add Mobile Controls entry to controls screen.
binding_anchor = """#ifdef PLATFORM_SUPPORTS_GYRO
	Menu_DrawButton(controls_buttons++, controls_index++, "GYROSCOPE", "Configure Gyroscope.", Menu_Gyro_Set);
#endif

	// Bindings
"""
binding_repl = """#ifdef PLATFORM_SUPPORTS_GYRO
	Menu_DrawButton(controls_buttons++, controls_index++, "GYROSCOPE", "Configure Gyroscope.", Menu_Gyro_Set);
#endif
#ifdef __ANDROID__
	Menu_DrawButton(controls_buttons++, controls_index++, "MOBILE CONTROLS", "Touch HUD, ADS, sprint and mobile sensitivity.", Menu_Mobile_Set);
#endif

	// Bindings
"""
if "MOBILE CONTROLS" not in text:
    if binding_anchor not in text:
        raise SystemExit("Could not find controls gyro/bindings anchor")
    text = text.replace(binding_anchor, binding_repl, 1)

# Expand raw gyro sliders too; boost menu adds a second multiplier.
text = text.replace("0.5f, 5.0f, in_gyro_sensitivity_x", "0.5f, 15.0f, in_gyro_sensitivity_x")
text = text.replace("0.5f, 5.0f, in_gyro_sensitivity_y", "0.5f, 15.0f, in_gyro_sensitivity_y")
controls.write_text(text, encoding="utf-8")

# Pause/save/resume/countdown.
host_cmd = source / "host_cmd.c"
text = host_cmd.read_text(encoding="utf-8")
countdown_globals = r'''
#ifdef __ANDROID__
qboolean xziel_mobile_resume_countdown = false;
double xziel_mobile_resume_countdown_end = 0.0;

void Xziel_BeginMobileResumeCountdown(void)
{
	sv.paused = true;
	xziel_mobile_resume_countdown = true;
	xziel_mobile_resume_countdown_end = Sys_FloatTime() + 3.0;
}
#endif
'''
host_anchor = "/*\n===============\nHost_Savegame_f"
if countdown_globals not in text:
    if host_anchor not in text:
        raise SystemExit("Could not find host savegame anchor")
    text = text.replace(host_anchor, countdown_globals + "\n" + host_anchor, 1)

# Detect loading our mobile resume slot.
load_set_anchor = """	sv.paused = true;		// pause until all clients connect
	sv.loadgame = true;
"""
load_set_repl = """	sv.paused = true;		// pause until all clients connect
	sv.loadgame = true;
#ifdef __ANDROID__
	if (!strcmp(Cmd_Argv(1), "xziel_resume"))
		xziel_mobile_resume_countdown = true;
#endif
"""
if "if (!strcmp(Cmd_Argv(1), \"xziel_resume\"))" not in text:
    if load_set_anchor not in text:
        raise SystemExit("Could not find loadgame paused block")
    text = text.replace(load_set_anchor, load_set_repl, 1)

# When client spawns from our save, keep paused and start countdown.
spawn_anchor = """	if (sv.loadgame)
	{	// loaded games are fully inited allready
		// if this is the last client to be connected, unpause
		sv.paused = false;
	}
"""
spawn_repl = """	if (sv.loadgame)
	{	// loaded games are fully inited allready
#ifdef __ANDROID__
		if (xziel_mobile_resume_countdown) {
			sv.paused = true;
			xziel_mobile_resume_countdown_end = Sys_FloatTime() + 3.0;
		} else
#endif
		{
			// if this is the last client to be connected, unpause
			sv.paused = false;
		}
	}
"""
if spawn_anchor not in text:
    raise SystemExit("Could not find Host_Spawn loadgame block")
text = text.replace(spawn_anchor, spawn_repl, 1)
host_cmd.write_text(text, encoding="utf-8")

pause = source / "menu" / "menu_pause.c"
text = pause.read_text(encoding="utf-8")
pause_extern = r'''
#ifdef __ANDROID__
extern qboolean xziel_mobile_resume_countdown;
extern double xziel_mobile_resume_countdown_end;
void Xziel_BeginMobileResumeCountdown(void);
#endif
'''
inc_anchor = '#include "menu_defs.h"\n'
if pause_extern not in text:
    text = text.replace(inc_anchor, inc_anchor + pause_extern, 1)

resume_old = """void Menu_Resume(void)
{ 
	Music_Resume();

	key_dest = key_game; 
	m_state = m_none; 
	m_previous_state = m_state; 
}
"""
resume_new = """void Menu_Resume(void)
{
	key_dest = key_game;
	m_state = m_none;
	m_previous_state = m_state;
#ifdef __ANDROID__
	if (sv.active && svs.maxclients == 1) {
		Xziel_BeginMobileResumeCountdown();
		return;
	}
#endif
	Music_Resume();
}
"""
if resume_old not in text:
    raise SystemExit("Could not find Menu_Resume")
text = text.replace(resume_old, resume_new, 1)

# Freeze solo world while pause menu is open.
pause_set_anchor = """	m_state = m_pause;
	m_previous_state = m_state;
}
"""
pause_set_repl = """	m_state = m_pause;
	m_previous_state = m_state;
#ifdef __ANDROID__
	if (sv.active && svs.maxclients == 1)
		sv.paused = true;
#endif
}
"""
if "if (sv.active && svs.maxclients == 1)\n\t\tsv.paused = true;" not in text:
    if pause_set_anchor not in text:
        raise SystemExit("Could not find Menu_Pause_Set tail")
    text = text.replace(pause_set_anchor, pause_set_repl, 1)

saveexit_code = r'''
#ifdef __ANDROID__
static void Menu_Pause_SaveAndExit(void)
{
	if (!sv.active || svs.maxclients != 1 || cl.stats[STAT_HEALTH] <= 0)
		return;
	Cbuf_AddText("save xziel_resume\n");
	Cbuf_Execute();
	sv.paused = false;
	Menu_ExitMap();
}
#endif
'''
draw_anchor = "void Menu_Pause_Draw (void)\n"
if "Menu_Pause_SaveAndExit" not in text:
    text = text.replace(draw_anchor, saveexit_code + "\n" + draw_anchor, 1)

pause_buttons_old = """		// End game
		Menu_DrawButton (4, 3, "END GAME", "Return to Main Menu.", Menu_Pause_EnterSubMenu);
"""
pause_buttons_new = """#ifdef __ANDROID__
		// Save local solo state and return to main menu.
		Menu_DrawButton (4, 3, "SAVE & EXIT", "Save current Solo state and return to Main Menu.", Menu_Pause_SaveAndExit);
		// End game without keeping this state.
		Menu_DrawButton (5, 4, "EXIT TO MENU", "Return to Main Menu without saving.", Menu_Pause_EnterSubMenu);
#else
		// End game
		Menu_DrawButton (4, 3, "END GAME", "Return to Main Menu.", Menu_Pause_EnterSubMenu);
#endif
"""
if pause_buttons_old not in text:
    raise SystemExit("Could not find pause END GAME button")
text = text.replace(pause_buttons_old, pause_buttons_new, 1)

# Existing submenu index for end game was 3; Android's Exit To Menu is now cursor 4.
text = text.replace(
"""	} else if (menu_paus_submenu == 3) {
		// User is returning to Main Menu
""",
"""	} else if (menu_paus_submenu ==
#ifdef __ANDROID__
		4
#else
		3
#endif
	) {
		// User is returning to Main Menu
""", 1)

text = text.replace(
"""		} else if (menu_paus_submenu == 3) {
			Menu_DrawSubMenu("Are you sure you want to quit?", "You will lose any progress that you have made.");
		}
""",
"""		} else if (menu_paus_submenu ==
#ifdef __ANDROID__
			4
#else
			3
#endif
		) {
			Menu_DrawSubMenu("Are you sure you want to quit?", "You will lose any unsaved progress.");
		}
""", 1)

pause.write_text(text, encoding="utf-8")

# Main-menu Resume Game entry when a mobile save exists.
main = source / "menu" / "menu_main.c"
text = main.read_text(encoding="utf-8")

resume_func = r'''
#ifdef __ANDROID__
static qboolean Menu_XzielResumeExists(void)
{
	char path[MAX_OSPATH + 1];
	snprintf(path, sizeof(path), "%s/xziel_resume.sav", com_gamedir);
	return Sys_FileTime(path) != -1;
}

static void Menu_XzielResume(void)
{
	Cbuf_AddText("load xziel_resume\n");
	Cbuf_Execute();
	key_dest = key_game;
	m_state = m_none;
}
#endif
'''
main_anchor = "qboolean in_submenu;\n"
if "Menu_XzielResumeExists" not in text:
    text = text.replace(main_anchor, main_anchor + resume_func, 1)

main_buttons_old = """	if (!in_submenu) {
		Menu_DrawButton(1, 0, "SOLO", "Play Solo.", Menu_Solo);
		Menu_DrawGreyButton(2, "COOPERATIVE");

		Menu_DrawDivider(3);

		Menu_DrawButton(3, 1, "CONFIGURATION", "Tweak Game Related Options", Menu_Configuration_Set);
		Menu_DrawButton(4, 2, "CHARACTER BIOS", "View Character Bios", Menu_Bios_Set);

		Menu_DrawDivider(5);

		Menu_DrawButton(5, 3, "CREDITS", "NZ:P Team + Special Thanks", Menu_Credits_Set);

		Menu_DrawDivider(6);

		Menu_DrawButton(6, 4, "QUIT GAME", "Return to Home Screen", Menu_EnterSubMenu);
"""
main_buttons_new = """	if (!in_submenu) {
#ifdef __ANDROID__
		int xziel_offset = 0;
		if (Menu_XzielResumeExists()) {
			Menu_DrawButton(1, 0, "RESUME GAME", "Resume your saved Solo match.", Menu_XzielResume);
			xziel_offset = 1;
		}
		Menu_DrawButton(1 + xziel_offset, xziel_offset, "SOLO", "Play Solo.", Menu_Solo);
		Menu_DrawGreyButton(2 + xziel_offset, "COOPERATIVE");

		Menu_DrawDivider(3 + xziel_offset);

		Menu_DrawButton(3 + xziel_offset, 1 + xziel_offset, "CONFIGURATION", "Tweak Game Related Options", Menu_Configuration_Set);
		Menu_DrawButton(4 + xziel_offset, 2 + xziel_offset, "CHARACTER BIOS", "View Character Bios", Menu_Bios_Set);

		Menu_DrawDivider(5 + xziel_offset);

		Menu_DrawButton(5 + xziel_offset, 3 + xziel_offset, "CREDITS", "NZ:P Team + Special Thanks", Menu_Credits_Set);

		Menu_DrawDivider(6 + xziel_offset);

		Menu_DrawButton(6 + xziel_offset, 4 + xziel_offset, "QUIT GAME", "Return to Home Screen", Menu_EnterSubMenu);
#else
		Menu_DrawButton(1, 0, "SOLO", "Play Solo.", Menu_Solo);
		Menu_DrawGreyButton(2, "COOPERATIVE");

		Menu_DrawDivider(3);

		Menu_DrawButton(3, 1, "CONFIGURATION", "Tweak Game Related Options", Menu_Configuration_Set);
		Menu_DrawButton(4, 2, "CHARACTER BIOS", "View Character Bios", Menu_Bios_Set);

		Menu_DrawDivider(5);

		Menu_DrawButton(5, 3, "CREDITS", "NZ:P Team + Special Thanks", Menu_Credits_Set);

		Menu_DrawDivider(6);

		Menu_DrawButton(6, 4, "QUIT GAME", "Return to Home Screen", Menu_EnterSubMenu);
#endif
"""
if main_buttons_old not in text:
    raise SystemExit("Could not find main menu button block")
text = text.replace(main_buttons_old, main_buttons_new, 1)
main.write_text(text, encoding="utf-8")

# Draw/complete the 3-2-1 countdown in HUD.
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")
countdown_draw = r'''
#ifdef __ANDROID__
extern qboolean xziel_mobile_resume_countdown;
extern double xziel_mobile_resume_countdown_end;

static void Xziel_MobileResumeCountdown(void)
{
	double left;
	char number[8];
	int w;
	float scale = vid.scale * 4.0f;

	if (!xziel_mobile_resume_countdown)
		return;

	left = xziel_mobile_resume_countdown_end - Sys_FloatTime();
	if (left <= 0.0) {
		xziel_mobile_resume_countdown = false;
		sv.paused = false;
		Music_Resume();
		return;
	}

	snprintf(number, sizeof(number), "%d", (int)ceil(left));
	w = getTextWidth(number, scale);
	Draw_ColoredString((vid.width - w) / 2, (int)(vid.height * 0.42f),
		number, 255, 255, 255, 255, scale);
}
#endif
'''
hud_draw_anchor = "void\nHUD_Draw(void)\n{"
if "static void Xziel_MobileResumeCountdown" not in text:
    text = text.replace(hud_draw_anchor, countdown_draw + "\n" + hud_draw_anchor, 1)

hud_start_anchor = """void
HUD_Draw(void)
{
    if (scr_con_current == vid.height)
"""
hud_start_repl = """void
HUD_Draw(void)
{
#ifdef __ANDROID__
    Xziel_MobileResumeCountdown();
#endif
    if (scr_con_current == vid.height)
"""
if hud_start_anchor not in text:
    raise SystemExit("Could not find HUD_Draw start for countdown")
text = text.replace(hud_start_anchor, hud_start_repl, 1)
hud.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android Custom HUD editor v0.5
# Persistent drag/drop positions shared by rendering and touch hitboxes.
# ---------------------------------------------------------------------------

inp = source / "input.c"
text = inp.read_text(encoding="utf-8")

pos_cvars = r'''
#ifdef __ANDROID__
cvar_t xziel_bot_telemetry = {"xziel_bot_telemetry", "0", false};
cvar_t xziel_hud_joy_x = {"xziel_hud_joy_x", "0.17", true};
cvar_t xziel_hud_joy_y = {"xziel_hud_joy_y", "0.74", true};
cvar_t xziel_hud_fire_x = {"xziel_hud_fire_x", "0.885", true};
cvar_t xziel_hud_fire_y = {"xziel_hud_fire_y", "0.585", true};
cvar_t xziel_hud_adsfire_x = {"xziel_hud_adsfire_x", "0.795", true};
cvar_t xziel_hud_adsfire_y = {"xziel_hud_adsfire_y", "0.435", true};
cvar_t xziel_hud_ads_x = {"xziel_hud_ads_x", "0.695", true};
cvar_t xziel_hud_ads_y = {"xziel_hud_ads_y", "0.575", true};
cvar_t xziel_hud_reload_x = {"xziel_hud_reload_x", "0.805", true};
cvar_t xziel_hud_reload_y = {"xziel_hud_reload_y", "0.785", true};
cvar_t xziel_hud_use_x = {"xziel_hud_use_x", "0.605", true};
cvar_t xziel_hud_use_y = {"xziel_hud_use_y", "0.675", true};
cvar_t xziel_hud_jump_x = {"xziel_hud_jump_x", "0.695", true};
cvar_t xziel_hud_jump_y = {"xziel_hud_jump_y", "0.790", true};
cvar_t xziel_hud_knife_x = {"xziel_hud_knife_x", "0.915", true};
cvar_t xziel_hud_knife_y = {"xziel_hud_knife_y", "0.800", true};
cvar_t xziel_hud_switch_x = {"xziel_hud_switch_x", "0.905", true};
cvar_t xziel_hud_switch_y = {"xziel_hud_switch_y", "0.300", true};
cvar_t xziel_hud_pause_x = {"xziel_hud_pause_x", "0.965", true};
cvar_t xziel_hud_pause_y = {"xziel_hud_pause_y", "0.075", true};
#endif
'''
pos_anchor = 'cvar_t xziel_mobile_autofire_ms = {"xziel_mobile_autofire_ms", "185", true};\n'
if "cvar_t xziel_hud_fire_x" not in text:
    if pos_anchor not in text:
        raise SystemExit("Could not find mobile cvar insertion anchor")
    text = text.replace(pos_anchor, pos_anchor + pos_cvars, 1)

reg_anchor = """	Cvar_RegisterVariable(&xziel_mobile_autofire_ms);
#endif
"""
reg_repl = """	Cvar_RegisterVariable(&xziel_mobile_autofire_ms);
	Cvar_RegisterVariable(&xziel_hud_joy_x);
	Cvar_RegisterVariable(&xziel_hud_joy_y);
	Cvar_RegisterVariable(&xziel_hud_fire_x);
	Cvar_RegisterVariable(&xziel_hud_fire_y);
	Cvar_RegisterVariable(&xziel_hud_adsfire_x);
	Cvar_RegisterVariable(&xziel_hud_adsfire_y);
	Cvar_RegisterVariable(&xziel_hud_ads_x);
	Cvar_RegisterVariable(&xziel_hud_ads_y);
	Cvar_RegisterVariable(&xziel_hud_reload_x);
	Cvar_RegisterVariable(&xziel_hud_reload_y);
	Cvar_RegisterVariable(&xziel_hud_use_x);
	Cvar_RegisterVariable(&xziel_hud_use_y);
	Cvar_RegisterVariable(&xziel_hud_jump_x);
	Cvar_RegisterVariable(&xziel_hud_jump_y);
	Cvar_RegisterVariable(&xziel_hud_knife_x);
	Cvar_RegisterVariable(&xziel_hud_knife_y);
	Cvar_RegisterVariable(&xziel_hud_switch_x);
	Cvar_RegisterVariable(&xziel_hud_switch_y);
	Cvar_RegisterVariable(&xziel_hud_pause_x);
	Cvar_RegisterVariable(&xziel_hud_pause_y);
#endif
"""
if "Cvar_RegisterVariable(&xziel_hud_fire_x);" not in text:
    if reg_anchor not in text:
        raise SystemExit("Could not find mobile cvar registration tail")
    text = text.replace(reg_anchor, reg_repl, 1)

inp.write_text(text, encoding="utf-8")

# Menu states/prototypes.
defs = source / "menu" / "menu_defs.h"
text = defs.read_text(encoding="utf-8")
if "#define m_hudedit" not in text:
    text = text.replace("#define m_mobile\t\t25\n", "#define m_mobile\t\t25\n#define m_hudedit\t\t26\n", 1)
    proto = "void Menu_Mobile_Draw(void);\n"
    if proto not in text:
        raise SystemExit("Could not find Mobile menu prototype")
    text = text.replace(proto, proto + "void Menu_HudEdit_Set(void);\nvoid Menu_HudEdit_Draw(void);\n", 1)
defs.write_text(text, encoding="utf-8")

menu = source / "menu" / "menu.c"
text = menu.read_text(encoding="utf-8")
case_anchor = """	case m_mobile:
		Menu_Mobile_Draw ();
		break;
#endif
"""
case_repl = """	case m_mobile:
		Menu_Mobile_Draw ();
		break;
	case m_hudedit:
		Menu_HudEdit_Draw ();
		break;
#endif
"""
if "case m_hudedit:" not in text:
    if case_anchor not in text:
        raise SystemExit("Could not find m_mobile draw case")
    text = text.replace(case_anchor, case_repl, 1)
menu.write_text(text, encoding="utf-8")

# Touch runtime now reads all button positions from archived cvars and supports
# editor drags without triggering gameplay actions.
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

pos_externs = r'''
extern cvar_t xziel_mobile_hud_scale;
extern cvar_t xziel_hud_joy_x;
extern cvar_t xziel_hud_joy_y;
extern cvar_t xziel_hud_fire_x;
extern cvar_t xziel_hud_fire_y;
extern cvar_t xziel_hud_adsfire_x;
extern cvar_t xziel_hud_adsfire_y;
extern cvar_t xziel_hud_ads_x;
extern cvar_t xziel_hud_ads_y;
extern cvar_t xziel_hud_reload_x;
extern cvar_t xziel_hud_reload_y;
extern cvar_t xziel_hud_use_x;
extern cvar_t xziel_hud_use_y;
extern cvar_t xziel_hud_jump_x;
extern cvar_t xziel_hud_jump_y;
extern cvar_t xziel_hud_knife_x;
extern cvar_t xziel_hud_knife_y;
extern cvar_t xziel_hud_switch_x;
extern cvar_t xziel_hud_switch_y;
extern cvar_t xziel_hud_pause_x;
extern cvar_t xziel_hud_pause_y;
'''
pos_ext_anchor = "extern qboolean xziel_mobile_use_available;\n"
if "extern cvar_t xziel_hud_fire_x;" not in text:
    if pos_ext_anchor not in text:
        raise SystemExit("Could not find sys mobile extern anchor")
    text = text.replace(pos_ext_anchor, pos_ext_anchor + pos_externs, 1)

slot_old = """	qboolean active;
	SDL_FingerID finger;
	xziel_touch_role_t role;
	float last_x;
	float last_y;
"""
slot_new = """	qboolean active;
	qboolean editor_drag;
	SDL_FingerID finger;
	xziel_touch_role_t role;
	float last_x;
	float last_y;
"""
if "qboolean editor_drag;" not in text:
    if slot_old not in text:
        raise SystemExit("Could not find touch slot struct")
    text = text.replace(slot_old, slot_new, 1)

# Joystick default home follows saved layout.
joy_init_anchor = """float xziel_mobile_move_anchor_x = 0.17f;
float xziel_mobile_move_anchor_y = 0.74f;
"""
joy_init_repl = """float xziel_mobile_move_anchor_x = 0.17f;
float xziel_mobile_move_anchor_y = 0.74f;
"""
# globals remain plain floats; HUD uses cvars when idle and touch down sets anchor dynamically.

role_func_start = text.find("static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)")
if role_func_start < 0:
    raise SystemExit("Could not find Xziel_RoleForPoint")
role_func_end = text.find("\n}\n\nstatic void Xziel_UpdateMove", role_func_start)
if role_func_end < 0:
    raise SystemExit("Could not find Xziel_RoleForPoint end")
role_func_end += 3

new_role_func = r'''static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.073f * hs)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.056f * hs)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.047f * hs)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.044f * hs)) return XZ_TOUCH_RELOAD;
	if (xziel_mobile_use_available && Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.050f * hs)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f * hs)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.044f * hs)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f * hs)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.041f * hs)) return XZ_TOUCH_SWITCH;
	if (x < 0.45f && y > 0.30f) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_LOOK;
}

static xziel_touch_role_t Xziel_HudEditorRole(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.090f * hs)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.075f * hs)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.065f * hs)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.060f * hs)) return XZ_TOUCH_RELOAD;
	if (Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.065f * hs)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.055f * hs)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.060f * hs)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.060f * hs)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.057f * hs)) return XZ_TOUCH_SWITCH;
	if (Xziel_IsInside(x, y, xziel_hud_joy_x.value, xziel_hud_joy_y.value, 0.120f * hs)) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_NONE;
}

static void Xziel_HudEditorSetPosition(xziel_touch_role_t role, float x, float y)
{
	if (x < 0.035f) x = 0.035f;
	if (x > 0.965f) x = 0.965f;
	if (y < 0.055f) y = 0.055f;
	if (y > 0.945f) y = 0.945f;

	switch (role) {
	case XZ_TOUCH_MOVE:
		Cvar_SetValue("xziel_hud_joy_x", x); Cvar_SetValue("xziel_hud_joy_y", y); break;
	case XZ_TOUCH_FIRE:
		Cvar_SetValue("xziel_hud_fire_x", x); Cvar_SetValue("xziel_hud_fire_y", y); break;
	case XZ_TOUCH_ADSFIRE:
		Cvar_SetValue("xziel_hud_adsfire_x", x); Cvar_SetValue("xziel_hud_adsfire_y", y); break;
	case XZ_TOUCH_ADS:
		Cvar_SetValue("xziel_hud_ads_x", x); Cvar_SetValue("xziel_hud_ads_y", y); break;
	case XZ_TOUCH_RELOAD:
		Cvar_SetValue("xziel_hud_reload_x", x); Cvar_SetValue("xziel_hud_reload_y", y); break;
	case XZ_TOUCH_USE:
		Cvar_SetValue("xziel_hud_use_x", x); Cvar_SetValue("xziel_hud_use_y", y); break;
	case XZ_TOUCH_JUMP:
		Cvar_SetValue("xziel_hud_jump_x", x); Cvar_SetValue("xziel_hud_jump_y", y); break;
	case XZ_TOUCH_KNIFE:
		Cvar_SetValue("xziel_hud_knife_x", x); Cvar_SetValue("xziel_hud_knife_y", y); break;
	case XZ_TOUCH_SWITCH:
		Cvar_SetValue("xziel_hud_switch_x", x); Cvar_SetValue("xziel_hud_switch_y", y); break;
	case XZ_TOUCH_PAUSE:
		Cvar_SetValue("xziel_hud_pause_x", x); Cvar_SetValue("xziel_hud_pause_y", y); break;
	default:
		break;
	}
}
'''
text = text[:role_func_start] + new_role_func + text[role_func_end:]

# HUD editor down path before ordinary menu handling.
fingerdown_anchor = """	if (cl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
		Xziel_ReleaseAllTouches();
		Menu_ExitMap();
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
"""
fingerdown_repl = """	if (cl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
		Xziel_ReleaseAllTouches();
		Menu_ExitMap();
		return;
	}

	if (key_dest == key_menu && m_state == m_hudedit) {
		xziel_touch_role_t edit_role = Xziel_HudEditorRole(finger->x, finger->y);
		if (edit_role != XZ_TOUCH_NONE) {
			slot = Xziel_AllocTouch(finger->fingerId);
			if (slot) {
				slot->editor_drag = true;
				slot->role = edit_role;
				slot->last_x = finger->x;
				slot->last_y = finger->y;
				Xziel_HudEditorSetPosition(edit_role, finger->x, finger->y);
			}
			return;
		}
		Xziel_MenuFinger(finger->x, finger->y, true, false);
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
"""
if "m_state == m_hudedit" not in text:
    if fingerdown_anchor not in text:
        raise SystemExit("Could not find finger down menu anchor")
    text = text.replace(fingerdown_anchor, fingerdown_repl, 1)

# Editor motion before ordinary menu-motion path.
motion_anchor = """	if (key_dest == key_menu || key_dest == key_menu_pause) {
		Xziel_MenuFinger(finger->x, finger->y, false, true);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
"""
motion_repl = """	slot = Xziel_FindTouch(finger->fingerId);
	if (slot && slot->editor_drag) {
		Xziel_HudEditorSetPosition(slot->role, finger->x, finger->y);
		slot->last_x = finger->x;
		slot->last_y = finger->y;
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		Xziel_MenuFinger(finger->x, finger->y, false, true);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
"""
if "slot && slot->editor_drag" not in text:
    if motion_anchor not in text:
        raise SystemExit("Could not find finger motion menu anchor")
    text = text.replace(motion_anchor, motion_repl, 1)

# Editor touch-up.
up_anchor = """	if (key_dest == key_menu || key_dest == key_menu_pause) {
		Xziel_MenuFinger(finger->x, finger->y, false, false);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
"""
up_repl = """	slot = Xziel_FindTouch(finger->fingerId);
	if (slot && slot->editor_drag) {
		Xziel_HudEditorSetPosition(slot->role, finger->x, finger->y);
		slot->active = false;
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		Xziel_MenuFinger(finger->x, finger->y, false, false);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
"""
if up_anchor not in text:
    raise SystemExit("Could not find finger up menu anchor")
text = text.replace(up_anchor, up_repl, 1)

sys_sdl.write_text(text, encoding="utf-8")

# HUD reads persistent positions and exposes an editor rendering mode.
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")

hud_pos_externs = r'''
extern cvar_t xziel_hud_joy_x;
extern cvar_t xziel_hud_joy_y;
extern cvar_t xziel_hud_fire_x;
extern cvar_t xziel_hud_fire_y;
extern cvar_t xziel_hud_adsfire_x;
extern cvar_t xziel_hud_adsfire_y;
extern cvar_t xziel_hud_ads_x;
extern cvar_t xziel_hud_ads_y;
extern cvar_t xziel_hud_reload_x;
extern cvar_t xziel_hud_reload_y;
extern cvar_t xziel_hud_use_x;
extern cvar_t xziel_hud_use_y;
extern cvar_t xziel_hud_jump_x;
extern cvar_t xziel_hud_jump_y;
extern cvar_t xziel_hud_knife_x;
extern cvar_t xziel_hud_knife_y;
extern cvar_t xziel_hud_switch_x;
extern cvar_t xziel_hud_switch_y;
extern cvar_t xziel_hud_pause_x;
extern cvar_t xziel_hud_pause_y;
'''
hud_pos_anchor = "extern cvar_t xziel_mobile_hud_opacity;\n"
if "extern cvar_t xziel_hud_fire_x;" not in text:
    text = text.replace(hud_pos_anchor, hud_pos_anchor + hud_pos_externs, 1)

func_start = text.find("static void Xziel_MobileHUD_Draw(void)")
if func_start < 0:
    raise SystemExit("Could not find mobile HUD draw function")
func_end = text.find("\n}\n\nstatic void Xziel_MobileGameOverPrompt", func_start)
if func_end < 0:
    raise SystemExit("Could not find mobile HUD draw function end")
func_end += 3
old_func = text[func_start:func_end]

new_func = r'''static void Xziel_MobileHUD_DrawInternal(qboolean editor)
{
	int base_x, base_y, knob_x, knob_y, radius, knob_r;

	if (!editor && (key_dest != key_game || cl.stats[STAT_HEALTH] <= 0))
		return;

	base_x = (int)((xziel_mobile_move_active && !editor ? xziel_mobile_move_anchor_x : xziel_hud_joy_x.value) * vid.width);
	base_y = (int)((xziel_mobile_move_active && !editor ? xziel_mobile_move_anchor_y : xziel_hud_joy_y.value) * vid.height);
	radius = (int)(0.095f * vid.height * xziel_mobile_hud_scale.value);
	knob_r = (int)(0.042f * vid.height * xziel_mobile_hud_scale.value);
	Xziel_DrawDisc(base_x, base_y, radius, 240, 240, 240, (int)(70 * xziel_mobile_hud_opacity.value));
	Xziel_DrawDisc(base_x, base_y, radius - (int)(2 * vid.scale), 0, 0, 0, (int)(95 * xziel_mobile_hud_opacity.value));
	knob_x = base_x + (int)(xziel_mobile_move_x * radius * 0.72f);
	knob_y = base_y - (int)(xziel_mobile_move_y * radius * 0.72f);
	Xziel_DrawDisc(knob_x, knob_y, knob_r, 245, 245, 245,
		(int)((xziel_mobile_move_active ? 150 : 90) * xziel_mobile_hud_opacity.value));

	Xziel_DrawTouchButton(xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.073f, "FIRE", "", xziel_mobile_fire_pressed);
	Xziel_DrawTouchButton(xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.056f, "ADS", "FIRE", xziel_mobile_adsfire_pressed);
	Xziel_DrawTouchButton(xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.047f, "ADS", "", xziel_mobile_ads_pressed);
	Xziel_DrawTouchButton(xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.044f, "RLD", "", xziel_mobile_reload_pressed);
	if (editor || xziel_mobile_use_available)
		Xziel_DrawTouchButton(xziel_hud_use_x.value, xziel_hud_use_y.value, 0.050f, "USE", "", xziel_mobile_use_pressed);
	Xziel_DrawTouchButton(xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f, "II", "", false);
	Xziel_DrawTouchButton(xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.044f, "JUMP", "", xziel_mobile_jump_pressed);
	Xziel_DrawTouchButton(xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f, "KNIFE", "", xziel_mobile_knife_pressed);
	Xziel_DrawTouchButton(xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.041f, "SWAP", "", xziel_mobile_switch_pressed);
}

static void Xziel_MobileHUD_Draw(void)
{
	Xziel_MobileHUD_DrawInternal(false);
}

void Xziel_MobileHUD_DrawEditor(void)
{
	Xziel_MobileHUD_DrawInternal(true);
}
'''
text = text[:func_start] + new_func + text[func_end:]

# Context card follows custom USE position.
fixed_card = """    y = (int)(vid.height * 0.54f);
    x = (int)(vid.width * 0.48f) - getTextWidth(hud_usestring, vid.scale);
"""
custom_card = """    y = (int)(xziel_hud_use_y.value * vid.height) - (int)(35 * vid.scale);
    x = (int)(xziel_hud_use_x.value * vid.width) - getTextWidth(hud_usestring, vid.scale) - (int)(28 * vid.scale);
"""
if fixed_card in text:
    text = text.replace(fixed_card, custom_card, 1)

hud.write_text(text, encoding="utf-8")

# HUD editor UI lives in menu_controls.c.
controls = source / "menu" / "menu_controls.c"
text = controls.read_text(encoding="utf-8")

editor_code = r'''
#ifdef __ANDROID__
void Xziel_MobileHUD_DrawEditor(void);
extern void Host_WriteConfiguration(void);

static void Menu_HudEdit_Reset(void)
{
	Cvar_SetValue("xziel_hud_joy_x", 0.17f); Cvar_SetValue("xziel_hud_joy_y", 0.74f);
	Cvar_SetValue("xziel_hud_fire_x", 0.885f); Cvar_SetValue("xziel_hud_fire_y", 0.585f);
	Cvar_SetValue("xziel_hud_adsfire_x", 0.795f); Cvar_SetValue("xziel_hud_adsfire_y", 0.435f);
	Cvar_SetValue("xziel_hud_ads_x", 0.695f); Cvar_SetValue("xziel_hud_ads_y", 0.575f);
	Cvar_SetValue("xziel_hud_reload_x", 0.805f); Cvar_SetValue("xziel_hud_reload_y", 0.785f);
	Cvar_SetValue("xziel_hud_use_x", 0.605f); Cvar_SetValue("xziel_hud_use_y", 0.675f);
	Cvar_SetValue("xziel_hud_jump_x", 0.695f); Cvar_SetValue("xziel_hud_jump_y", 0.790f);
	Cvar_SetValue("xziel_hud_knife_x", 0.915f); Cvar_SetValue("xziel_hud_knife_y", 0.800f);
	Cvar_SetValue("xziel_hud_switch_x", 0.905f); Cvar_SetValue("xziel_hud_switch_y", 0.300f);
	Cvar_SetValue("xziel_hud_pause_x", 0.965f); Cvar_SetValue("xziel_hud_pause_y", 0.075f);
}

static void Menu_HudEdit_Done(void)
{
	Host_WriteConfiguration();
	Menu_Mobile_Set();
}

void Menu_HudEdit_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_hudedit;
}

void Menu_HudEdit_Draw(void)
{
	Menu_DrawCustomBackground(true);
	Menu_DrawMapPanel();
	Menu_DrawTitle("CUSTOM HUD", MENU_COLOR_WHITE);

	Draw_ColoredString((int)(vid.width * 0.5f) - getTextWidth("DRAG CONTROLS TO MOVE THEM", vid.scale) / 2,
		(int)(28 * vid.scale), "DRAG CONTROLS TO MOVE THEM", 255, 255, 255, 230, vid.scale);

	Xziel_MobileHUD_DrawEditor();

	Menu_DrawButton(-2, 0, "RESET LAYOUT", "Restore default mobile HUD positions.", Menu_HudEdit_Reset);
	Menu_DrawButton(-1, 1, "DONE", "Save HUD layout and return.", Menu_HudEdit_Done);
}
#endif
'''
if "void Menu_HudEdit_Draw(void)" not in text:
    text += "\n" + editor_code

mobile_back_anchor = """	Menu_DrawButton(-1, idx, "BACK", "Return to Control Options.", Menu_Controls_Set);
}
#endif
"""
mobile_back_repl = """	Menu_DrawButton(row++, idx++, "CUSTOM HUD", "Drag and place mobile controls.", Menu_HudEdit_Set);
	Menu_DrawButton(-1, idx, "BACK", "Return to Control Options.", Menu_Controls_Set);
}
#endif
"""
if "Drag and place mobile controls." not in text:
    if mobile_back_anchor not in text:
        raise SystemExit("Could not find mobile menu back button")
    text = text.replace(mobile_back_anchor, mobile_back_repl, 1)

controls.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android mobile settings/gyro/full interaction pass v0.6
# ---------------------------------------------------------------------------

def xziel_replace_c_function(src, signature, replacement):
    start = src.find(signature)
    if start < 0:
        raise SystemExit("Could not find function: " + signature)
    brace = src.find("{", start)
    if brace < 0:
        raise SystemExit("Could not find function body: " + signature)
    depth = 0
    end = -1
    for i in range(brace, len(src)):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end < 0:
        raise SystemExit("Could not find function end: " + signature)
    return src[:start] + replacement + src[end:]

# ---- Phone-native gyro -----------------------------------------------------
in_sdl = source / "platform" / "sdl" / "in_sdl.c"
text = in_sdl.read_text(encoding="utf-8")

sensor_global_anchor = "static SDL_GameController *sdl_controller;\n"
sensor_global_repl = """static SDL_GameController *sdl_controller;
#ifdef __ANDROID__
static SDL_Sensor *xziel_android_gyro_sensor = NULL;
#endif
"""
if "xziel_android_gyro_sensor" not in text:
    if sensor_global_anchor not in text:
        raise SystemExit("Could not find SDL controller global")
    text = text.replace(sensor_global_anchor, sensor_global_repl, 1)

gyro_func = r'''qboolean IN_PlatformGetGyro(float *x, float *y)
{
	float data[3];
	*x = *y = 0.0f;

#ifdef __ANDROID__
	/* Phone gyro is a generic SDL sensor, not a GameController sensor.
	   The game is locked to landscape, so rotate Android's portrait-natural
	   sensor axes into screen-space pitch/yaw. */
	if (xziel_android_gyro_sensor) {
		SDL_DisplayOrientation orientation;
		SDL_SensorUpdate();
		if (SDL_SensorGetData(xziel_android_gyro_sensor, data, 3) == 0) {
			orientation = SDL_GetDisplayOrientation(0);
			if (orientation == SDL_ORIENTATION_LANDSCAPE_FLIPPED) {
				*x = data[1];   /* pitch */
				*y = -data[0];  /* yaw */
			} else {
				*x = -data[1];  /* pitch */
				*y = data[0];   /* yaw */
			}
			return true;
		}
	}
#endif

	if (!sdl_controller || !SDL_GameControllerHasSensor(sdl_controller, SDL_SENSOR_GYRO))
		return false;
	if (SDL_GameControllerGetSensorData(sdl_controller, SDL_SENSOR_GYRO, data, 3) != 0)
		return false;
	*x = data[0];
	*y = data[1];
	return true;
}'''
text = xziel_replace_c_function(text, "qboolean IN_PlatformGetGyro(float *x, float *y)", gyro_func)

init_old = """void IN_PlatformInit(void)
{
	int i;
	Cvar_SetValue("in_anub_mode", 1);
	for (i = 0; i < SDL_NumJoysticks(); ++i)
		IN_SDLOpenController(i);
}
"""
init_new = """void IN_PlatformInit(void)
{
	int i;
	Cvar_SetValue("in_anub_mode", 1);
	for (i = 0; i < SDL_NumJoysticks(); ++i)
		IN_SDLOpenController(i);
#ifdef __ANDROID__
	for (i = 0; i < SDL_NumSensors(); ++i) {
		if (SDL_SensorGetDeviceType(i) == SDL_SENSOR_GYRO) {
			xziel_android_gyro_sensor = SDL_SensorOpen(i);
			if (xziel_android_gyro_sensor) {
				Con_Printf("Xziel: Android phone gyroscope opened: %s\\n",
					SDL_SensorGetName(xziel_android_gyro_sensor));
				break;
			}
		}
	}
#endif
}
"""
if init_old not in text:
    raise SystemExit("Could not find IN_PlatformInit for phone gyro")
text = text.replace(init_old, init_new, 1)

shutdown_old = """void IN_PlatformShutdown(void)
{
	int i;
	for (i = 0; i < MAX_SDL_CONTROLLERS; ++i) {
"""
shutdown_new = """void IN_PlatformShutdown(void)
{
	int i;
#ifdef __ANDROID__
	if (xziel_android_gyro_sensor) {
		SDL_SensorClose(xziel_android_gyro_sensor);
		xziel_android_gyro_sensor = NULL;
	}
#endif
	for (i = 0; i < MAX_SDL_CONTROLLERS; ++i) {
"""
if shutdown_old not in text:
    raise SystemExit("Could not find IN_PlatformShutdown for phone gyro")
text = text.replace(shutdown_old, shutdown_new, 1)
in_sdl.write_text(text, encoding="utf-8")

# ---- Persistent mobile interaction setting --------------------------------
inp = source / "input.c"
text = inp.read_text(encoding="utf-8")
autocvar_anchor = 'cvar_t xziel_mobile_autofire_ms = {"xziel_mobile_autofire_ms", "185", true};\n'
if "xziel_mobile_auto_rebuild" not in text:
    if autocvar_anchor not in text:
        raise SystemExit("Could not find mobile autofire cvar")
    text = text.replace(
        autocvar_anchor,
        autocvar_anchor + 'cvar_t xziel_mobile_auto_rebuild = {"xziel_mobile_auto_rebuild", "1", true};\n',
        1
    )

reg_anchor = "\tCvar_RegisterVariable(&xziel_mobile_autofire_ms);\n"
if "Cvar_RegisterVariable(&xziel_mobile_auto_rebuild);" not in text:
    if reg_anchor not in text:
        raise SystemExit("Could not find mobile cvar registration anchor")
    text = text.replace(
        reg_anchor,
        reg_anchor + "\tCvar_RegisterVariable(&xziel_mobile_auto_rebuild);\n",
        1
    )
inp.write_text(text, encoding="utf-8")

# ---- Contextual auto-rebuild -----------------------------------------------
hud = source / "render" / "r_hud.c"
text = hud.read_text(encoding="utf-8")

use_flag_anchor = "qboolean xziel_mobile_use_available = false;\n"
if "xziel_mobile_auto_rebuild_available" not in text:
    if use_flag_anchor not in text:
        raise SystemExit("Could not find mobile use availability global")
    text = text.replace(
        use_flag_anchor,
        use_flag_anchor + "qboolean xziel_mobile_auto_rebuild_available = false;\n",
        1
    )

inactive_anchor = """        xziel_mobile_use_available = false;
#endif
        return;
"""
inactive_repl = """        xziel_mobile_use_available = false;
        xziel_mobile_auto_rebuild_available = false;
#endif
        return;
"""
if "xziel_mobile_auto_rebuild_available = false;" not in text[text.find("HUD_DrawUsePrint"):]:
    if inactive_anchor not in text:
        raise SystemExit("Could not find mobile use inactive block")
    text = text.replace(inactive_anchor, inactive_repl, 1)

active_anchor = """    xziel_mobile_use_available = true;
#endif
"""
active_repl = """    xziel_mobile_use_available = true;
    xziel_mobile_auto_rebuild_available =
        (strstr(hud_usestring, "Rebuild Barrier") != NULL);
#endif
"""
if "strstr(hud_usestring, \"Rebuild Barrier\")" not in text:
    if active_anchor not in text:
        raise SystemExit("Could not find mobile use active block")
    text = text.replace(active_anchor, active_repl, 1)
hud.write_text(text, encoding="utf-8")

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

extern_anchor = "extern qboolean xziel_mobile_use_available;\n"
auto_externs = """extern qboolean xziel_mobile_auto_rebuild_available;
extern cvar_t xziel_mobile_auto_rebuild;
"""
if "extern qboolean xziel_mobile_auto_rebuild_available;" not in text:
    if extern_anchor not in text:
        raise SystemExit("Could not find mobile use extern")
    text = text.replace(extern_anchor, extern_anchor + auto_externs, 1)

state_anchor = "static qboolean xziel_mobile_sprint_active = false;\n"
if "xziel_auto_rebuild_use_down" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find mobile sprint state")
    text = text.replace(
        state_anchor,
        state_anchor + "static qboolean xziel_auto_rebuild_use_down = false;\n",
        1
    )

# Make manual USE coexist safely with automatic barricade +use.
use_down_old = """	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		Cbuf_AddText("+use\\n");
		break;
"""
use_down_new = """	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		if (!xziel_auto_rebuild_use_down)
			Cbuf_AddText("+use\\n");
		break;
"""
if use_down_old in text:
    text = text.replace(use_down_old, use_down_new, 1)

use_up_old = """	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = false;
		Cbuf_AddText("-use\\n");
		break;
"""
use_up_new = """	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = false;
		if (!xziel_auto_rebuild_use_down)
			Cbuf_AddText("-use\\n");
		break;
"""
if use_up_old in text:
    text = text.replace(use_up_old, use_up_new, 1)

autouse_func = r'''
static void Xziel_UpdateAutoRebuild(void)
{
	qboolean should_hold =
		xziel_mobile_auto_rebuild.value >= 0.5f &&
		xziel_mobile_auto_rebuild_available &&
		key_dest == key_game &&
		cl.stats[STAT_HEALTH] > 0;

	if (should_hold && !xziel_auto_rebuild_use_down) {
		if (!xziel_mobile_use_pressed)
			Cbuf_AddText("+use\n");
		xziel_auto_rebuild_use_down = true;
	} else if (!should_hold && xziel_auto_rebuild_use_down) {
		xziel_auto_rebuild_use_down = false;
		if (!xziel_mobile_use_pressed)
			Cbuf_AddText("-use\n");
	}
}
'''
fire_func_anchor = "static void Xziel_UpdateMobileFire(void)\n"
if "static void Xziel_UpdateAutoRebuild(void)" not in text:
    idx = text.find(fire_func_anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile fire updater")
    text = text[:idx] + autouse_func + "\n" + text[idx:]

pump_anchor = """	Xziel_UpdateMobileFire();
	/* Touch is handled directly above."""
pump_repl = """	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
	/* Touch is handled directly above."""
if "Xziel_UpdateAutoRebuild();" not in text:
    if pump_anchor not in text:
        raise SystemExit("Could not find mobile pump update")
    text = text.replace(pump_anchor, pump_repl, 1)

sys_sdl.write_text(text, encoding="utf-8")

# ---- Mobile Settings hierarchy ---------------------------------------------
defs = source / "menu" / "menu_defs.h"
text = defs.read_text(encoding="utf-8")

state_anchor = "#define m_hudedit\t\t26\n"
state_repl = """#define m_hudedit		26
#define m_mobileaim		27
#define m_mobilegyro		28
#define m_mobilehud		29
#define m_mobilegameplay	30
"""
if "#define m_mobileaim" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find mobile HUD editor state")
    text = text.replace(state_anchor, state_repl, 1)

proto_anchor = "void Menu_HudEdit_Draw(void);\n"
proto_repl = """void Menu_HudEdit_Draw(void);
void Menu_MobileAim_Set(void);
void Menu_MobileAim_Draw(void);
void Menu_MobileGyro_Set(void);
void Menu_MobileGyro_Draw(void);
void Menu_MobileHud_Set(void);
void Menu_MobileHud_Draw(void);
void Menu_MobileGameplay_Set(void);
void Menu_MobileGameplay_Draw(void);
"""
if "void Menu_MobileAim_Set(void);" not in text:
    if proto_anchor not in text:
        raise SystemExit("Could not find HUD editor prototypes")
    text = text.replace(proto_anchor, proto_repl, 1)
defs.write_text(text, encoding="utf-8")

menu = source / "menu" / "menu.c"
text = menu.read_text(encoding="utf-8")
case_anchor = """	case m_hudedit:
		Menu_HudEdit_Draw ();
		break;
#endif
"""
case_repl = """	case m_hudedit:
		Menu_HudEdit_Draw ();
		break;
	case m_mobileaim:
		Menu_MobileAim_Draw ();
		break;
	case m_mobilegyro:
		Menu_MobileGyro_Draw ();
		break;
	case m_mobilehud:
		Menu_MobileHud_Draw ();
		break;
	case m_mobilegameplay:
		Menu_MobileGameplay_Draw ();
		break;
#endif
"""
if "case m_mobileaim:" not in text:
    if case_anchor not in text:
        raise SystemExit("Could not find HUD editor menu switch")
    text = text.replace(case_anchor, case_repl, 1)
menu.write_text(text, encoding="utf-8")

menu_sys = source / "menu" / "menu_sys.c"
text = menu_sys.read_text(encoding="utf-8")
prev_anchor = """		case m_mobile:
			Menu_Mobile_Set();
			break;
#endif
"""
prev_repl = """		case m_mobile:
			Menu_Mobile_Set();
			break;
		case m_mobileaim:
		case m_mobilegyro:
		case m_mobilehud:
		case m_mobilegameplay:
		case m_hudedit:
			Menu_Mobile_Set();
			break;
#endif
"""
if "case m_mobileaim:" not in text[text.find("void Menu_SetPreviousMenu"):]:
    if prev_anchor not in text:
        raise SystemExit("Could not find mobile previous-menu case")
    text = text.replace(prev_anchor, prev_repl, 1)
menu_sys.write_text(text, encoding="utf-8")

# Put MOBILE SETTINGS directly under Configuration.
config = source / "menu" / "menu_configuration.c"
text = config.read_text(encoding="utf-8")
config_buttons = """	Menu_DrawButton(1, 0, "VIDEO", "Visual Fidelity options.", Menu_Video_Set);
	Menu_DrawButton(2, 1, "AUDIO", "Volume sliders.", Menu_Audio_Set);
	Menu_DrawButton(3, 2, "CONTROLS", "Control Options and Bindings.", Menu_Controls_Set);
    Menu_DrawButton(4, 3, "ACCESSIBILITY", "Content, Interface, and Readability options.", Menu_Accessibility_Set);

	Menu_DrawDivider(5);

    Menu_DrawButton(5, 4, "OPEN CONSOLE", "Access the Developer Console.", Con_ToggleConsole_f);

	Menu_DrawButton(-1, 5, "BACK", "Return to Main Menu.", Menu_Configuration_Back);
"""
config_mobile = """	Menu_DrawButton(1, 0, "VIDEO", "Visual Fidelity options.", Menu_Video_Set);
	Menu_DrawButton(2, 1, "AUDIO", "Volume sliders.", Menu_Audio_Set);
	Menu_DrawButton(3, 2, "CONTROLS", "Keyboard, controller and general control options.", Menu_Controls_Set);
#ifdef __ANDROID__
	Menu_DrawButton(4, 3, "MOBILE SETTINGS", "Touch, aim, gyroscope, HUD and mobile gameplay.", Menu_Mobile_Set);
	Menu_DrawButton(5, 4, "ACCESSIBILITY", "Content, Interface, and Readability options.", Menu_Accessibility_Set);
	Menu_DrawDivider(6);
	Menu_DrawButton(6, 5, "OPEN CONSOLE", "Access the Developer Console.", Con_ToggleConsole_f);
	Menu_DrawButton(-1, 6, "BACK", "Return to Main Menu.", Menu_Configuration_Back);
#else
	Menu_DrawButton(4, 3, "ACCESSIBILITY", "Content, Interface, and Readability options.", Menu_Accessibility_Set);
	Menu_DrawDivider(5);
	Menu_DrawButton(5, 4, "OPEN CONSOLE", "Access the Developer Console.", Con_ToggleConsole_f);
	Menu_DrawButton(-1, 5, "BACK", "Return to Main Menu.", Menu_Configuration_Back);
#endif
"""
if "MOBILE SETTINGS" not in text:
    if config_buttons not in text:
        raise SystemExit("Could not find Configuration menu button block")
    text = text.replace(config_buttons, config_mobile, 1)
config.write_text(text, encoding="utf-8")

controls = source / "menu" / "menu_controls.c"
text = controls.read_text(encoding="utf-8")

# Root Mobile Settings now comes back to Configuration, not legacy Controls.
text = text.replace(
"""void Menu_Mobile_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_controls;
	m_state = m_mobile;
}
""",
"""void Menu_Mobile_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_configuration;
	m_state = m_mobile;
}
""", 1)

# Remove the duplicate entry from the generic Controls page.
legacy_mobile_entry = """#ifdef __ANDROID__
	Menu_DrawButton(controls_buttons++, controls_index++, "MOBILE CONTROLS", "Touch HUD, ADS, sprint and mobile sensitivity.", Menu_Mobile_Set);
#endif
"""
text = text.replace(legacy_mobile_entry, "", 1)

# Toggle for auto-rebuild.
if "extern cvar_t xziel_mobile_auto_rebuild;" not in text:
    extern_anchor = "extern cvar_t xziel_mobile_autofire_ms;\n"
    if extern_anchor not in text:
        raise SystemExit("Could not find mobile cvar externs")
    text = text.replace(
        extern_anchor,
        extern_anchor + "extern cvar_t xziel_mobile_auto_rebuild;\n",
        1
    )

# Replace old all-in-one Mobile menu with a hub.
mobile_root = r'''void Menu_Mobile_Draw(void)
{
	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE SETTINGS", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	Menu_DrawButton(1, 0, "AIM & TOUCH", "ADS behavior and touch camera sensitivity.", Menu_MobileAim_Set);
	Menu_DrawButton(2, 1, "GYROSCOPE", "Phone gyroscope mode and sensitivity.", Menu_MobileGyro_Set);
	Menu_DrawButton(3, 2, "HUD & LAYOUT", "HUD size, opacity and custom control placement.", Menu_MobileHud_Set);
	Menu_DrawButton(4, 3, "GAMEPLAY & INTERACTIONS", "Auto sprint and contextual mobile interactions.", Menu_MobileGameplay_Set);

	Menu_DrawButton(-1, 4, "BACK", "Return to Configuration.", Menu_Configuration_Set);
}'''
text = xziel_replace_c_function(text, "void Menu_Mobile_Draw(void)", mobile_root)

mobile_pages = r'''
#ifdef __ANDROID__
static char *xziel_mobile_auto_rebuild_string;

static void Menu_Mobile_ToggleAutoRebuild(void)
{
	Cvar_SetValue("xziel_mobile_auto_rebuild",
		xziel_mobile_auto_rebuild.value >= 0.5f ? 0.0f : 1.0f);
}

void Menu_MobileAim_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobileaim;
}

void Menu_MobileGyro_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobilegyro;
}

void Menu_MobileHud_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobilehud;
}

void Menu_MobileGameplay_Set(void)
{
	Menu_ResetMenuButtons();
	m_previous_state = m_mobile;
	m_state = m_mobilegameplay;
}

void Menu_MobileAim_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - AIM & TOUCH", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();
	xziel_ads_mode_string = xziel_mobile_ads_toggle.value >= 0.5f ? "TOGGLE" : "HOLD";

	Menu_DrawButton(row++, idx++, "ADS BEHAVIOR", "Dedicated ADS button: Hold or Toggle.", Menu_Mobile_ToggleADS);
	Menu_DrawOptionButton(row-1, xziel_ads_mode_string);

	Menu_DrawButton(row++, idx++, "TOUCH LOOK", "Hip-fire/free-look sensitivity.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.25f, 4.0f, xziel_mobile_touch_sensitivity, "xziel_mobile_touch_sensitivity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "ADS LOOK", "Touch sensitivity multiplier while ADS.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.20f, 1.50f, xziel_mobile_ads_sensitivity, "xziel_mobile_ads_sensitivity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "PISTOL AUTO FIRE", "Delay between automatic semi-auto trigger taps.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 140.0f, 320.0f, xziel_mobile_autofire_ms, "xziel_mobile_autofire_ms", false, true, 10.0f);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}

void Menu_MobileGyro_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - GYROSCOPE", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();
	Menu_Controls_SetStrings();

	Menu_DrawButton(row++, idx++, "GYRO MODE", "Off, Always On, or ADS Only.", Menu_Controls_ApplyGyroMode);
	Menu_DrawOptionButton(row-1, gyro_mode_string);

	Menu_DrawButton(row++, idx++, "HORIZONTAL", "Phone gyro horizontal/yaw sensitivity.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.5f, 30.0f, in_gyro_sensitivity_x, "in_gyro_sensitivity_x", false, true, 0.5f);

	Menu_DrawButton(row++, idx++, "VERTICAL", "Phone gyro vertical/pitch sensitivity.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.5f, 30.0f, in_gyro_sensitivity_y, "in_gyro_sensitivity_y", false, true, 0.5f);

	Menu_DrawButton(row++, idx++, "PHONE GYRO BOOST", "Extra Android phone-sensor multiplier.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 1.0f, 20.0f, xziel_mobile_gyro_boost, "xziel_mobile_gyro_boost", false, true, 0.5f);

	Menu_DrawButton(row++, idx++, "ADS DAMPENING", "Reduce gyroscope sensitivity while ADS.", Menu_Controls_ApplyGyroZoomScaling);
	Menu_DrawOptionButton(row-1, gyro_zoom_scaling_string);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}

void Menu_MobileHud_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - HUD & LAYOUT", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	Menu_DrawButton(row++, idx++, "HUD SCALE", "Scale all mobile controls.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.70f, 1.35f, xziel_mobile_hud_scale, "xziel_mobile_hud_scale", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "HUD OPACITY", "Opacity of mobile controls.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.25f, 1.0f, xziel_mobile_hud_opacity, "xziel_mobile_hud_opacity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "CUSTOM HUD", "Drag controls to your preferred positions.", Menu_HudEdit_Set);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}

void Menu_MobileGameplay_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - GAMEPLAY", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	xziel_mobile_auto_rebuild_string =
		xziel_mobile_auto_rebuild.value >= 0.5f ? "ENABLED" : "DISABLED";

	Menu_DrawButton(row++, idx++, "AUTO SPRINT", "Stick-forward threshold that starts sprinting.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.65f, 0.98f, xziel_mobile_sprint_threshold, "xziel_mobile_sprint_threshold", false, true, 0.01f);

	Menu_DrawButton(row++, idx++, "AUTO REBUILD BARRIERS", "Automatically repair barricades while you remain in range.", Menu_Mobile_ToggleAutoRebuild);
	Menu_DrawOptionButton(row-1, xziel_mobile_auto_rebuild_string);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}
#endif
'''
if "void Menu_MobileAim_Draw(void)" not in text:
    text += "\n" + mobile_pages

controls.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android sticky toggle ADS + reload restore v0.7
# ---------------------------------------------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

state_anchor = "static qboolean xziel_mobile_sprint_active = false;\n"
state_add = """static qboolean xziel_mobile_restore_ads_after_reload = false;
static qboolean xziel_mobile_reload_animation_seen = false;
"""
if "xziel_mobile_restore_ads_after_reload" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find mobile sprint state for ADS restore")
    text = text.replace(state_anchor, state_anchor + state_add, 1)

adsfire_down_old = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		Xziel_SetAttackRef(true);
		Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		break;
"""
adsfire_down_new = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		Xziel_SetAttackRef(true);
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			/* Toggle ADS behaves as sticky state: ADS+FIRE may enter ADS,
			   but never becomes the control that exits it. */
			if (cl.stats[STAT_ZOOM] == 0)
				Cbuf_AddText("impulse 26\\n");
		} else {
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		}
		break;
"""
if adsfire_down_old not in text:
    raise SystemExit("Could not find ADS+FIRE down block")
text = text.replace(adsfire_down_old, adsfire_down_new, 1)

adsfire_up_old = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;
		Xziel_SetAttackRef(false);
		Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, false);
		break;
"""
adsfire_up_new = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;
		Xziel_SetAttackRef(false);
		if (xziel_mobile_ads_toggle.value < 0.5f)
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, false);
		break;
"""
if adsfire_up_old not in text:
    raise SystemExit("Could not find ADS+FIRE up block")
text = text.replace(adsfire_up_old, adsfire_up_new, 1)

ads_down_old = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		if (xziel_mobile_ads_toggle.value >= 0.5f)
			Cbuf_AddText("impulse 26\\n");
		else
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		break;
"""
ads_down_new = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			/* A deliberate dedicated-ADS tap overrides any automatic
			   post-reload restoration. */
			xziel_mobile_restore_ads_after_reload = false;
			xziel_mobile_reload_animation_seen = false;
			Cbuf_AddText("impulse 26\\n");
		} else {
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		}
		break;
"""
if ads_down_old not in text:
    raise SystemExit("Could not find dedicated ADS down block")
text = text.replace(ads_down_old, ads_down_new, 1)

reload_down_old = """	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		Cbuf_AddText("+reload\\n");
		break;
"""
reload_down_new = """	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		if (xziel_mobile_ads_toggle.value >= 0.5f &&
			(cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)) {
			xziel_mobile_restore_ads_after_reload = true;
			xziel_mobile_reload_animation_seen = false;
		}
		Cbuf_AddText("+reload\\n");
		break;
"""
if reload_down_old not in text:
    raise SystemExit("Could not find reload down block")
text = text.replace(reload_down_old, reload_down_new, 1)

restore_func = r'''
static void Xziel_UpdateReloadAdsRestore(void)
{
	if (!xziel_mobile_restore_ads_after_reload)
		return;

	/* STAT_WEAPONFRAME is networked from the actual viewmodel animation.
	   Wait until reload leaves idle, then returns to idle after the button
	   has been released. This follows the real weapon animation instead of
	   guessing a weapon-specific reload duration. */
	if (cl.stats[STAT_WEAPONFRAME] != 0)
		xziel_mobile_reload_animation_seen = true;

	if (xziel_mobile_reload_animation_seen &&
		!xziel_mobile_reload_pressed &&
		cl.stats[STAT_WEAPONFRAME] == 0) {
		if (xziel_mobile_ads_toggle.value >= 0.5f &&
			cl.stats[STAT_ZOOM] == 0)
			Cbuf_AddText("impulse 26\n");

		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;
	}
}
'''
update_anchor = "static void Xziel_UpdateAutoRebuild(void)\n"
if "static void Xziel_UpdateReloadAdsRestore(void)" not in text:
    idx = text.find(update_anchor)
    if idx < 0:
        # v0.6 may not have inserted auto rebuild if disabled; fall back to fire updater
        idx = text.find("static void Xziel_UpdateMobileFire(void)\n")
    if idx < 0:
        raise SystemExit("Could not find mobile updater insertion point")
    text = text[:idx] + restore_func + "\n" + text[idx:]

pump_anchor = """	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
"""
pump_repl = """	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
	Xziel_UpdateReloadAdsRestore();
"""
if "Xziel_UpdateReloadAdsRestore();" not in text:
    if pump_anchor in text:
        text = text.replace(pump_anchor, pump_repl, 1)
    else:
        pump_anchor2 = """	Xziel_UpdateMobileFire();
	/* Touch is handled directly above."""
        pump_repl2 = """	Xziel_UpdateMobileFire();
	Xziel_UpdateReloadAdsRestore();
	/* Touch is handled directly above."""
        if pump_anchor2 not in text:
            raise SystemExit("Could not find mobile pump for ADS restore")
        text = text.replace(pump_anchor2, pump_repl2, 1)

# Losing focus or leaving gameplay must never leave a deferred ADS action.
release_anchor = """	xziel_aim_refs = 0;
}
"""
release_repl = """	xziel_aim_refs = 0;
	xziel_mobile_restore_ads_after_reload = false;
	xziel_mobile_reload_animation_seen = false;
}
"""
if "xziel_mobile_restore_ads_after_reload = false;" not in text[text.find("static void Xziel_ReleaseAllTouches"):text.find("static void Xziel_MenuFinger")]:
    if release_anchor not in text:
        raise SystemExit("Could not find touch release tail")
    text = text.replace(release_anchor, release_repl, 1)

sys_sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android gyro/ADS/auto-knife correction pass v0.8
# ---------------------------------------------------------------------------

# SDL's Android generic sensor backend is a separate subsystem. Without this
# flag SDL_NumSensors() returns no phone sensors even though the device has a
# gyroscope.
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")
sensor_init_old = "(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_EVENTS | SDL_INIT_GAMECONTROLLER)"
sensor_init_new = "(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_EVENTS | SDL_INIT_GAMECONTROLLER | SDL_INIT_SENSOR)"
if sensor_init_old not in text:
    raise SystemExit("Could not find SDL_Init flags for phone sensor subsystem")
text = text.replace(sensor_init_old, sensor_init_new, 1)

# Persistent auto-melee behavior.
inp = source / "input.c"
itext = inp.read_text(encoding="utf-8")
knife_cvar_anchor = 'cvar_t xziel_mobile_auto_rebuild = {"xziel_mobile_auto_rebuild", "1", true};\n'
knife_cvars = """cvar_t xziel_mobile_auto_knife = {"xziel_mobile_auto_knife", "1", true};
cvar_t xziel_mobile_knife_range_only = {"xziel_mobile_knife_range_only", "1", true};
cvar_t xziel_mobile_auto_knife_range = {"xziel_mobile_auto_knife_range", "96", true};
"""
if "xziel_mobile_auto_knife" not in itext:
    if knife_cvar_anchor not in itext:
        raise SystemExit("Could not find mobile interaction cvar anchor")
    itext = itext.replace(knife_cvar_anchor, knife_cvar_anchor + knife_cvars, 1)

knife_reg_anchor = "\tCvar_RegisterVariable(&xziel_mobile_auto_rebuild);\n"
knife_regs = """	Cvar_RegisterVariable(&xziel_mobile_auto_knife);
	Cvar_RegisterVariable(&xziel_mobile_knife_range_only);
	Cvar_RegisterVariable(&xziel_mobile_auto_knife_range);
"""
if "Cvar_RegisterVariable(&xziel_mobile_auto_knife);" not in itext:
    if knife_reg_anchor not in itext:
        raise SystemExit("Could not find mobile interaction registration anchor")
    itext = itext.replace(knife_reg_anchor, knife_reg_anchor + knife_regs, 1)
inp.write_text(itext, encoding="utf-8")

# Runtime state.
state_anchor = "static qboolean xziel_mobile_reload_animation_seen = false;\n"
state_more = """static qboolean xziel_mobile_ads_latched = false;
static int xziel_mobile_reload_start_frame = 0;
qboolean xziel_mobile_knife_target_near = false;
static Uint32 xziel_mobile_auto_knife_next_ms = 0;
"""
if "xziel_mobile_ads_latched" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find v0.7 ADS state anchor")
    text = text.replace(state_anchor, state_anchor + state_more, 1)

extern_anchor = "extern cvar_t xziel_mobile_auto_rebuild;\n"
extern_more = """extern cvar_t xziel_mobile_auto_knife;
extern cvar_t xziel_mobile_knife_range_only;
extern cvar_t xziel_mobile_auto_knife_range;
"""
if "extern cvar_t xziel_mobile_auto_knife;" not in text:
    if extern_anchor not in text:
        raise SystemExit("Could not find mobile interaction extern anchor")
    text = text.replace(extern_anchor, extern_anchor + extern_more, 1)

# Immediate attack-down removes the extra frame of touch latency. Semi-auto
# pistols still use timed release/repress pulses after the first immediate shot.
attack_ref_func = r'''static void Xziel_SetAttackRef(qboolean pressed)
{
	if (pressed) {
		xziel_attack_refs++;
		if (xziel_attack_refs == 1) {
			Uint32 now = SDL_GetTicks();
			Cbuf_AddText("+attack\n");
			xziel_attack_command_down = true;
			if (Xziel_IsAutoTapPistol()) {
				xziel_attack_release_ms = now + 42;
				xziel_attack_next_ms =
					now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);
			} else {
				xziel_attack_release_ms = 0;
				xziel_attack_next_ms = 0;
			}
		}
	} else {
		if (xziel_attack_refs > 0)
			xziel_attack_refs--;
		if (xziel_attack_refs == 0 && xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
		}
	}
}'''
text = xziel_replace_c_function(text, "static void Xziel_SetAttackRef(qboolean pressed)", attack_ref_func)

# Dedicated ADS toggle owns the persistent latch. ADS+FIRE becomes temporary
# hold ADS when the latch is not already active.
adsfire_down_old = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		Xziel_SetAttackRef(true);
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			/* Toggle ADS behaves as sticky state: ADS+FIRE may enter ADS,
			   but never becomes the control that exits it. */
			if (cl.stats[STAT_ZOOM] == 0)
				Cbuf_AddText("impulse 26\\n");
		} else {
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		}
		break;
"""
adsfire_down_new = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		if (xziel_mobile_ads_toggle.value >= 0.5f && !xziel_mobile_ads_latched)
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		else if (xziel_mobile_ads_toggle.value < 0.5f)
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		Xziel_SetAttackRef(true);
		Cbuf_Execute();
		break;
"""
if adsfire_down_old not in text:
    raise SystemExit("Could not find v0.7 ADS+FIRE down block")
text = text.replace(adsfire_down_old, adsfire_down_new, 1)

adsfire_up_old = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;
		Xziel_SetAttackRef(false);
		if (xziel_mobile_ads_toggle.value < 0.5f)
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, false);
		break;
"""
adsfire_up_new = """	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;
		Xziel_SetAttackRef(false);
		if (xziel_mobile_ads_toggle.value < 0.5f ||
			(xziel_mobile_ads_toggle.value >= 0.5f && !xziel_mobile_ads_latched))
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, false);
		Cbuf_Execute();
		break;
"""
if adsfire_up_old not in text:
    raise SystemExit("Could not find v0.7 ADS+FIRE up block")
text = text.replace(adsfire_up_old, adsfire_up_new, 1)

ads_down_old = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			/* A deliberate dedicated-ADS tap overrides any automatic
			   post-reload restoration. */
			xziel_mobile_restore_ads_after_reload = false;
			xziel_mobile_reload_animation_seen = false;
			Cbuf_AddText("impulse 26\\n");
		} else {
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		}
		break;
"""
ads_down_new = """	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			xziel_mobile_ads_latched = !xziel_mobile_ads_latched;
			Cbuf_AddText("impulse 26\\n");
		} else {
			xziel_mobile_ads_latched = false;
			Xziel_QueueHold("+aim\\n", "-aim\\n", &xziel_aim_refs, true);
		}
		Cbuf_Execute();
		break;
"""
if ads_down_old not in text:
    raise SystemExit("Could not find v0.7 dedicated ADS down block")
text = text.replace(ads_down_old, ads_down_new, 1)

reload_down_old = """	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		if (xziel_mobile_ads_toggle.value >= 0.5f &&
			(cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)) {
			xziel_mobile_restore_ads_after_reload = true;
			xziel_mobile_reload_animation_seen = false;
		}
		Cbuf_AddText("+reload\\n");
		break;
"""
reload_down_new = """	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		xziel_mobile_restore_ads_after_reload =
			(xziel_mobile_ads_toggle.value >= 0.5f && xziel_mobile_ads_latched);
		xziel_mobile_reload_animation_seen = false;
		xziel_mobile_reload_start_frame = cl.stats[STAT_WEAPONFRAME];
		Cbuf_AddText("+reload\\n");
		Cbuf_Execute();
		break;
"""
if reload_down_old not in text:
    raise SystemExit("Could not find v0.7 reload block")
text = text.replace(reload_down_old, reload_down_new, 1)

restore_func = r'''static void Xziel_UpdateReloadAdsRestore(void)
{
	if (!xziel_mobile_restore_ads_after_reload)
		return;

	if (cl.stats[STAT_WEAPONFRAME] != xziel_mobile_reload_start_frame)
		xziel_mobile_reload_animation_seen = true;

	if (xziel_mobile_reload_animation_seen &&
		!xziel_mobile_reload_pressed &&
		(cl.stats[STAT_WEAPONFRAME] == xziel_mobile_reload_start_frame ||
		 cl.stats[STAT_WEAPONFRAME] == 0)) {
		if (xziel_mobile_ads_toggle.value >= 0.5f &&
			xziel_mobile_ads_latched &&
			cl.stats[STAT_ZOOM] == 0) {
			Cbuf_AddText("impulse 26\n");
			Cbuf_Execute();
		}

		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;
	}
}'''
text = xziel_replace_c_function(text, "static void Xziel_UpdateReloadAdsRestore(void)", restore_func)

# Sprint should end sticky ADS just like CoD-style mobile controls.
sprint_old = """		if (!xziel_mobile_sprint_active) {
			Cbuf_AddText("impulse 23\\n");
			xziel_mobile_sprint_active = true;
		}
"""
sprint_new = """		if (!xziel_mobile_sprint_active) {
			xziel_mobile_ads_latched = false;
			xziel_mobile_restore_ads_after_reload = false;
			Cbuf_AddText("impulse 23\\n");
			xziel_mobile_sprint_active = true;
		}
"""
if sprint_old in text:
    text = text.replace(sprint_old, sprint_new, 1)

# Auto knife uses the real local server collision trace. This is intentionally
# local-Solo only for now; remote multiplayer needs a networked proximity stat.
knife_func = r'''
static void Xziel_UpdateAutoKnife(void)
{
	qboolean near_target = false;
	Uint32 now = SDL_GetTicks();

	if (key_dest == key_game &&
		cl.stats[STAT_HEALTH] > 0 &&
		sv.active && sv_player && cls.signon == SIGNONS) {
		vec3_t start, end, forward;
		trace_t tr;
		float range = xziel_mobile_auto_knife_range.value;

		if (range < 48.0f) range = 48.0f;
		if (range > 128.0f) range = 128.0f;

		VectorAdd(sv_player->v.origin, sv_player->v.view_ofs, start);
		AngleVectors(cl.viewangles, forward, NULLVEC, NULLVEC);
		VectorMA(start, range, forward, end);
		tr = SV_Move(start, vec3_origin, vec3_origin, end, MOVE_NORMAL, sv_player);

		/* The server already tells us whether the forward trace is an enemy.
		   Combining that with this short local collision trace gives us a
		   real melee-distance gate without auto-knifing distant targets. */
		near_target =
			tr.fraction < 1.0f &&
			tr.ent != NULL &&
			(((int)tr.ent->v.flags & FL_MONSTER) != 0);
	}

	xziel_mobile_knife_target_near = near_target;

	if (xziel_mobile_auto_knife.value >= 0.5f &&
		near_target &&
		!xziel_mobile_knife_pressed &&
		cl.stats[STAT_ZOOM] == 0 &&
		now >= xziel_mobile_auto_knife_next_ms) {
		Cbuf_AddText("+knife\n-knife\n");
		Cbuf_Execute();
		xziel_mobile_auto_knife_next_ms = now + 180;
	} else if (!near_target) {
		xziel_mobile_auto_knife_next_ms = now;
	}
}
'''
insert_anchor = "static void Xziel_UpdateAutoRebuild(void)\n"
if "static void Xziel_UpdateAutoKnife(void)" not in text:
    idx = text.find(insert_anchor)
    if idx < 0:
        raise SystemExit("Could not find auto rebuild updater for knife insertion")
    text = text[:idx] + knife_func + "\n" + text[idx:]

pump_old = """	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
	Xziel_UpdateReloadAdsRestore();
"""
pump_new = """	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
	Xziel_UpdateAutoKnife();
	Xziel_UpdateReloadAdsRestore();
"""
if "Xziel_UpdateAutoKnife();" not in text:
    if pump_old not in text:
        raise SystemExit("Could not find mobile updater pump for auto knife")
    text = text.replace(pump_old, pump_new, 1)

# Knife hitbox exists only when configured visible.
knife_role_old = """	if (Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f * hs)) return XZ_TOUCH_KNIFE;
"""
knife_role_new = """	if ((!xziel_mobile_knife_range_only.value || xziel_mobile_knife_target_near) &&
		Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f * hs))
		return XZ_TOUCH_KNIFE;
"""
if knife_role_old not in text:
    raise SystemExit("Could not find custom knife role hitbox")
text = text.replace(knife_role_old, knife_role_new, 1)

sys_sdl.write_text(text, encoding="utf-8")

# HUD visibility follows Always/In Range setting, while editor always shows it.
hud = source / "render" / "r_hud.c"
htext = hud.read_text(encoding="utf-8")
hud_extern_anchor = "extern qboolean xziel_mobile_switch_pressed;\n"
hud_extern_more = """extern qboolean xziel_mobile_knife_target_near;
extern cvar_t xziel_mobile_knife_range_only;
"""
if "extern qboolean xziel_mobile_knife_target_near;" not in htext:
    if hud_extern_anchor not in htext:
        raise SystemExit("Could not find mobile HUD knife extern anchor")
    htext = htext.replace(hud_extern_anchor, hud_extern_anchor + hud_extern_more, 1)

knife_draw_old = """	Xziel_DrawTouchButton(xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f, "KNIFE", "", xziel_mobile_knife_pressed);
"""
knife_draw_new = """	if (editor || !xziel_mobile_knife_range_only.value || xziel_mobile_knife_target_near)
		Xziel_DrawTouchButton(xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f, "KNIFE", "", xziel_mobile_knife_pressed);
"""
if knife_draw_old not in htext:
    raise SystemExit("Could not find mobile knife HUD draw")
htext = htext.replace(knife_draw_old, knife_draw_new, 1)
hud.write_text(htext, encoding="utf-8")

# Add Auto Knife and Knife Button visibility to Mobile Gameplay settings.
controls = source / "menu" / "menu_controls.c"
mtext = controls.read_text(encoding="utf-8")

extern_anchor = "extern cvar_t xziel_mobile_auto_rebuild;\n"
extern_more = """extern cvar_t xziel_mobile_auto_knife;
extern cvar_t xziel_mobile_knife_range_only;
extern cvar_t xziel_mobile_auto_knife_range;
"""
if "extern cvar_t xziel_mobile_auto_knife;" not in mtext:
    if extern_anchor not in mtext:
        raise SystemExit("Could not find mobile gameplay cvar extern anchor")
    mtext = mtext.replace(extern_anchor, extern_anchor + extern_more, 1)

string_anchor = "static char *xziel_mobile_auto_rebuild_string;\n"
string_more = """static char *xziel_mobile_auto_knife_string;
static char *xziel_mobile_knife_visibility_string;
"""
if "xziel_mobile_auto_knife_string" not in mtext:
    if string_anchor not in mtext:
        raise SystemExit("Could not find mobile gameplay strings")
    mtext = mtext.replace(string_anchor, string_anchor + string_more, 1)

toggle_anchor = """static void Menu_Mobile_ToggleAutoRebuild(void)
{
	Cvar_SetValue("xziel_mobile_auto_rebuild",
		xziel_mobile_auto_rebuild.value >= 0.5f ? 0.0f : 1.0f);
}
"""
toggle_more = """
static void Menu_Mobile_ToggleAutoKnife(void)
{
	Cvar_SetValue("xziel_mobile_auto_knife",
		xziel_mobile_auto_knife.value >= 0.5f ? 0.0f : 1.0f);
}

static void Menu_Mobile_ToggleKnifeVisibility(void)
{
	Cvar_SetValue("xziel_mobile_knife_range_only",
		xziel_mobile_knife_range_only.value >= 0.5f ? 0.0f : 1.0f);
}
"""
if "Menu_Mobile_ToggleAutoKnife" not in mtext:
    if toggle_anchor not in mtext:
        raise SystemExit("Could not find auto rebuild toggle")
    mtext = mtext.replace(toggle_anchor, toggle_anchor + toggle_more, 1)

game_func = r'''void Menu_MobileGameplay_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - GAMEPLAY", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	xziel_mobile_auto_rebuild_string =
		xziel_mobile_auto_rebuild.value >= 0.5f ? "ENABLED" : "DISABLED";
	xziel_mobile_auto_knife_string =
		xziel_mobile_auto_knife.value >= 0.5f ? "ENABLED" : "DISABLED";
	xziel_mobile_knife_visibility_string =
		xziel_mobile_knife_range_only.value >= 0.5f ? "IN RANGE" : "ALWAYS";

	Menu_DrawButton(row++, idx++, "AUTO SPRINT", "Stick-forward threshold that starts sprinting.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.65f, 0.98f, xziel_mobile_sprint_threshold, "xziel_mobile_sprint_threshold", false, true, 0.01f);

	Menu_DrawButton(row++, idx++, "AUTO REBUILD BARRIERS", "Automatically repair barricades while you remain in range.", Menu_Mobile_ToggleAutoRebuild);
	Menu_DrawOptionButton(row-1, xziel_mobile_auto_rebuild_string);

	Menu_DrawButton(row++, idx++, "AUTO KNIFE", "Automatically melee a zombie/dog directly inside melee range.", Menu_Mobile_ToggleAutoKnife);
	Menu_DrawOptionButton(row-1, xziel_mobile_auto_knife_string);

	Menu_DrawButton(row++, idx++, "KNIFE BUTTON", "Show the manual knife button always or only when a melee target is in range.", Menu_Mobile_ToggleKnifeVisibility);
	Menu_DrawOptionButton(row-1, xziel_mobile_knife_visibility_string);

	Menu_DrawButton(row++, idx++, "AUTO KNIFE RANGE", "Distance used by the mobile auto-melee proximity check.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 64.0f, 120.0f, xziel_mobile_auto_knife_range, "xziel_mobile_auto_knife_range", false, true, 4.0f);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}'''
mtext = xziel_replace_c_function(mtext, "void Menu_MobileGameplay_Draw(void)", game_func)
controls.write_text(mtext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android COD-style touch input correction pass v0.9
# Native melee distance, menu touch isolation, weapon-aware ADS+FIRE release
# semantics, and explicit sprint-lock zone above the movement stick.
# ---------------------------------------------------------------------------

# ---- Persistent sprint-lock setting ----------------------------------------
inp = source / "input.c"
itext = inp.read_text(encoding="utf-8")
sprint_cvar_anchor = 'cvar_t xziel_mobile_auto_knife_range = {"xziel_mobile_auto_knife_range", "96", true};\n'
if "xziel_mobile_sprint_zone" not in itext:
    if sprint_cvar_anchor not in itext:
        raise SystemExit("Could not find v0.8 mobile cvar anchor for sprint zone")
    itext = itext.replace(
        sprint_cvar_anchor,
        sprint_cvar_anchor + 'cvar_t xziel_mobile_sprint_zone = {"xziel_mobile_sprint_zone", "1.10", true};\n',
        1
    )

sprint_reg_anchor = "\tCvar_RegisterVariable(&xziel_mobile_auto_knife_range);\n"
if "Cvar_RegisterVariable(&xziel_mobile_sprint_zone);" not in itext:
    if sprint_reg_anchor not in itext:
        raise SystemExit("Could not find v0.8 cvar registration anchor for sprint zone")
    itext = itext.replace(
        sprint_reg_anchor,
        sprint_reg_anchor + "\tCvar_RegisterVariable(&xziel_mobile_sprint_zone);\n",
        1
    )
inp.write_text(itext, encoding="utf-8")

# ---- Touch runtime ----------------------------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

sprint_extern_anchor = "extern cvar_t xziel_mobile_auto_knife_range;\n"
if "extern cvar_t xziel_mobile_sprint_zone;" not in text:
    if sprint_extern_anchor not in text:
        raise SystemExit("Could not find v0.8 runtime cvar extern anchor")
    text = text.replace(
        sprint_extern_anchor,
        sprint_extern_anchor + "extern cvar_t xziel_mobile_sprint_zone;\n",
        1
    )

state_anchor = "static Uint32 xziel_mobile_auto_knife_next_ms = 0;\n"
state_add = """qboolean xziel_mobile_sprint_zone_hot = false;
static qboolean xziel_mobile_sprint_suppressed = false;
static Uint32 xziel_mobile_sprint_retry_ms = 0;
static qboolean xziel_adsfire_attack_engaged = false;
static qboolean xziel_adsfire_release_pending = false;
static qboolean xziel_adsfire_release_requested = false;
static qboolean xziel_adsfire_temp_aim = false;
static qboolean xziel_adsfire_cancelled = false;
static qboolean xziel_menu_touch_active = false;
static SDL_FingerID xziel_menu_touch_finger = 0;
static int xziel_menu_touch_state = -1;
"""
if "xziel_adsfire_release_pending" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find v0.8 runtime state anchor")
    text = text.replace(state_anchor, state_anchor + state_add, 1)

helpers = r'''
static qboolean Xziel_IsDualWeaponMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_BIATCH:
	case W_SNUFF:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_WeaponDoesNotAdsMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_TESLA:
	case W_DG3:
	case W_BK:
	case W_KRAUS:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_AdsFireReleaseWeapon(void)
{
	/* COD-mobile-like hold-to-aim / release-to-fire behavior is most useful
	   for the native bolt-action rifles and single-shot shotguns.  Upgraded
	   dual Sawed-Off (SNUFF) is intentionally excluded because native NZ:P
	   treats its ADS input as the second trigger, not as ADS. */
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_KAR:
	case W_ARMAGEDDON:
	case W_SPRING:
	case W_PULVERIZER:
	case W_KAR_SCOPE:
	case W_DB:
	case W_BORE:
	case W_SAWNOFF:
	case W_TRENCH:
	case W_GUT:
		return true;
	default:
		return false;
	}
}

static void Xziel_PulseAttackNow(void)
{
	/* KeyDown+KeyUp in one pump leaves the impulse-down bit set for the next
	   CL_SendMove, producing exactly one server trigger edge. */
	Cbuf_AddText("+attack\n-attack\n");
	Cbuf_Execute();
}

static void Xziel_StopSprintForAction(void)
{
	if (xziel_mobile_sprint_zone_hot)
		xziel_mobile_sprint_suppressed = true;

	if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
		Cbuf_AddText("impulse 24\n");
		Cbuf_Execute();
	}
	xziel_mobile_sprint_active = false;
}

static void Xziel_FinishTemporaryAdsFireAim(void)
{
	if (xziel_adsfire_temp_aim && !xziel_mobile_ads_latched) {
		Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
		Cbuf_Execute();
	}
	xziel_adsfire_temp_aim = false;
}

static void Xziel_CancelAdsFireForSprint(void)
{
	if (xziel_adsfire_attack_engaged) {
		Xziel_SetAttackRef(false);
		xziel_adsfire_attack_engaged = false;
	}

	xziel_adsfire_release_pending = false;
	xziel_adsfire_release_requested = false;
	xziel_adsfire_cancelled = true;
	Xziel_FinishTemporaryAdsFireAim();

	/* Dedicated toggle ADS must be explicitly toggled out before native
	   W_SprintStart can succeed.  Sprint is retried while the stick remains
	   in the sprint lock zone, so the following frame starts running as soon
	   as the native zoom state has cleared. */
	if (xziel_mobile_ads_latched) {
		Cbuf_AddText("impulse 26\n");
		Cbuf_Execute();
		xziel_mobile_ads_latched = false;
	}
	xziel_mobile_restore_ads_after_reload = false;
}
'''
action_anchor = "static void Xziel_ActionDown(xziel_touch_role_t role)\n"
if "static qboolean Xziel_AdsFireReleaseWeapon(void)" not in text:
    idx = text.find(action_anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile action insertion point")
    text = text[:idx] + helpers + "\n" + text[idx:]

# Immediate command-buffer execution removes the avoidable extra event-pump
# latency from ordinary FIRE.  Weapon fire_delay remains native authority.
attack_ref_func = r'''static void Xziel_SetAttackRef(qboolean pressed)
{
	qboolean changed = false;

	if (pressed) {
		xziel_attack_refs++;
		if (xziel_attack_refs == 1) {
			Uint32 now = SDL_GetTicks();
			Cbuf_AddText("+attack\n");
			xziel_attack_command_down = true;
			changed = true;
			if (Xziel_IsAutoTapPistol()) {
				xziel_attack_release_ms = now + 42;
				xziel_attack_next_ms =
					now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);
			} else {
				xziel_attack_release_ms = 0;
				xziel_attack_next_ms = 0;
			}
		}
	} else {
		if (xziel_attack_refs > 0)
			xziel_attack_refs--;
		if (xziel_attack_refs == 0 && xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
			changed = true;
		}
	}

	if (changed)
		Cbuf_Execute();
}'''
text = xziel_replace_c_function(text, "static void Xziel_SetAttackRef(qboolean pressed)", attack_ref_func)

update_fire_func = r'''static void Xziel_UpdateMobileFire(void)
{
	Uint32 now = SDL_GetTicks();
	qboolean changed = false;

	/* ADS+FIRE is a state machine rather than two commands submitted in the
	   same usercmd. Native NZ:P evaluates FIRE before ADS, so sending both
	   together can hip-fire or add inconsistent latency. Establish ADS first,
	   then engage the trigger on the earliest frame where the native zoom
	   state confirms ADS. No arbitrary millisecond ADS delay is added. */
	if ((xziel_mobile_adsfire_pressed || xziel_adsfire_release_requested) &&
		!xziel_adsfire_cancelled) {
		if (xziel_adsfire_release_pending) {
			if (xziel_adsfire_release_requested &&
				(cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2 ||
				 xziel_mobile_ads_latched)) {
				Xziel_PulseAttackNow();
				xziel_adsfire_release_pending = false;
				xziel_adsfire_release_requested = false;
				Xziel_FinishTemporaryAdsFireAim();
			}
		} else if (!xziel_adsfire_attack_engaged &&
			(Xziel_WeaponDoesNotAdsMobile() || Xziel_IsDualWeaponMobile() ||
			 cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)) {
			Xziel_SetAttackRef(true);
			xziel_adsfire_attack_engaged = true;
		}
	}

	if (xziel_attack_refs <= 0) {
		if (xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
			changed = true;
		}
		if (changed)
			Cbuf_Execute();
		return;
	}

	if (!Xziel_IsAutoTapPistol())
		return;

	/* Semi-auto pistols are held like COD Mobile but translated to bounded
	   native trigger taps. The actual NZ:P fire_delay still limits ROF. */
	if (xziel_attack_command_down && now >= xziel_attack_release_ms) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
		changed = true;
	}
	if (!xziel_attack_command_down && now >= xziel_attack_next_ms) {
		Cbuf_AddText("+attack\n");
		xziel_attack_command_down = true;
		xziel_attack_release_ms = now + 42;
		xziel_attack_next_ms =
			now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);
		changed = true;
	}
	if (changed)
		Cbuf_Execute();
}'''
text = xziel_replace_c_function(text, "static void Xziel_UpdateMobileFire(void)", update_fire_func)

action_down_func = r'''static void Xziel_ActionDown(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = true;
		Xziel_StopSprintForAction();
		Xziel_SetAttackRef(true);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		xziel_adsfire_cancelled = false;
		xziel_adsfire_attack_engaged = false;
		xziel_adsfire_release_requested = false;
		xziel_adsfire_release_pending = Xziel_AdsFireReleaseWeapon();
		xziel_adsfire_temp_aim = false;

		Xziel_StopSprintForAction();

		/* Dual/no-ADS weapons must never wait for a zoom state that cannot
		   exist. Everything else enters ADS immediately, and UpdateMobileFire
		   starts standard weapons as soon as native ADS is established. */
		if (Xziel_WeaponDoesNotAdsMobile() || Xziel_IsDualWeaponMobile()) {
			if (!xziel_adsfire_release_pending) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		} else {
			if (!xziel_mobile_ads_latched) {
				Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
				xziel_adsfire_temp_aim = true;
				Cbuf_Execute();
			}
			if (!xziel_adsfire_release_pending &&
				(cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;
		Xziel_StopSprintForAction();
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			xziel_mobile_ads_latched = !xziel_mobile_ads_latched;
			Cbuf_AddText("impulse 26\n");
		} else {
			xziel_mobile_ads_latched = false;
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		}
		Cbuf_Execute();
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		xziel_mobile_restore_ads_after_reload =
			(xziel_mobile_ads_toggle.value >= 0.5f && xziel_mobile_ads_latched);
		xziel_mobile_reload_animation_seen = false;
		xziel_mobile_reload_start_frame = cl.stats[STAT_WEAPONFRAME];
		Cbuf_AddText("+reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("+use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = true;
		Cbuf_AddText("+jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = true;
		Xziel_StopSprintForAction();
		Cbuf_AddText("+knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		if (xziel_adsfire_release_pending || xziel_adsfire_release_requested)
			Xziel_CancelAdsFireForSprint();
		Cbuf_AddText("+switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		Menu_Pause_Set();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(text, "static void Xziel_ActionDown(xziel_touch_role_t role)", action_down_func)

action_up_func = r'''static void Xziel_ActionUp(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = false;
		Xziel_SetAttackRef(false);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;

		if (xziel_adsfire_release_pending && !xziel_adsfire_cancelled) {
			/* Release is the trigger edge for bolt-action rifles and the
			   single-shot shotguns. If ADS has not arrived yet, keep the
			   temporary aim down for the minimum additional frame and let the
			   updater fire immediately when the native zoom state appears. */
			xziel_adsfire_release_requested = true;
			if (cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2 ||
				xziel_mobile_ads_latched) {
				Xziel_PulseAttackNow();
				xziel_adsfire_release_pending = false;
				xziel_adsfire_release_requested = false;
				Xziel_FinishTemporaryAdsFireAim();
			}
		} else {
			if (xziel_adsfire_attack_engaged) {
				Xziel_SetAttackRef(false);
				xziel_adsfire_attack_engaged = false;
			}
			Xziel_FinishTemporaryAdsFireAim();
			xziel_adsfire_release_pending = false;
			xziel_adsfire_release_requested = false;
		}
		xziel_adsfire_cancelled = false;
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = false;
		if (xziel_mobile_ads_toggle.value < 0.5f) {
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = false;
		Cbuf_AddText("-reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = false;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("-use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = false;
		Cbuf_AddText("-jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = false;
		Cbuf_AddText("-knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = false;
		Cbuf_AddText("-switch\n");
		Cbuf_Execute();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(text, "static void Xziel_ActionUp(xziel_touch_role_t role)", action_up_func)

# Exact native melee distance: WepDef_GetWeaponMeleeRange() is 88 for normal
# weapons and 96 for Ballistic Knife / Krauss. Match the same short forward
# trace and recognize the limb classnames the native melee code can hit.
auto_knife_func = r'''static void Xziel_UpdateAutoKnife(void)
{
	qboolean near_target = false;
	Uint32 now = SDL_GetTicks();

	if (key_dest == key_game &&
		cl.stats[STAT_HEALTH] > 0 &&
		sv.active && sv_player && cls.signon == SIGNONS) {
		vec3_t start, end, forward;
		trace_t tr;
		const char *classname = "";
		float range =
			(cl.stats[STAT_ACTIVEWEAPON] == W_BK ||
			 cl.stats[STAT_ACTIVEWEAPON] == W_KRAUS) ? 96.0f : 88.0f;

		VectorAdd(sv_player->v.origin, sv_player->v.view_ofs, start);
		AngleVectors(cl.viewangles, forward, NULLVEC, NULLVEC);
		VectorMA(start, range, forward, end);
		tr = SV_Move(start, vec3_origin, vec3_origin, end, MOVE_NORMAL, sv_player);

		if (tr.fraction < 1.0f && tr.ent != NULL)
			classname = PR_GetString(tr.ent->v.classname);

		near_target =
			!strcmp(classname, "ai_zombie") ||
			!strcmp(classname, "ai_zombie_head") ||
			!strcmp(classname, "ai_zombie_larm") ||
			!strcmp(classname, "ai_zombie_rarm") ||
			!strcmp(classname, "ai_dog");
	}

	xziel_mobile_knife_target_near = near_target;

	if (xziel_mobile_auto_knife.value >= 0.5f &&
		near_target &&
		!xziel_mobile_knife_pressed &&
		cl.stats[STAT_ZOOM] == 0 &&
		now >= xziel_mobile_auto_knife_next_ms) {
		Cbuf_AddText("+knife\n-knife\n");
		Cbuf_Execute();
		/* Native knife_delay remains authoritative. This throttle only avoids
		   flooding input edges while the same target remains in range. */
		xziel_mobile_auto_knife_next_ms = now + 250;
	} else if (!near_target) {
		xziel_mobile_auto_knife_next_ms = now;
	}
}'''
text = xziel_replace_c_function(text, "static void Xziel_UpdateAutoKnife(void)", auto_knife_func)

# Explicit outer sprint-lock zone. Normal full-forward movement remains a walk
# until the thumb is deliberately dragged into the icon above the stick.
move_func = r'''static void Xziel_UpdateMove(float x, float y)
{
	float raw_dx, raw_dy, dx, dy, len, radius_x, radius_y;
	float sprint_zone;
	Uint32 now = SDL_GetTicks();

	radius_x = 0.16f * ((float)vid.height / (float)vid.width);
	radius_y = 0.16f;
	raw_dx = (x - xziel_mobile_move_anchor_x) / radius_x;
	raw_dy = (xziel_mobile_move_anchor_y - y) / radius_y;

	dx = raw_dx;
	dy = raw_dy;
	len = sqrtf(dx * dx + dy * dy);

	if (len < 0.10f) {
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
		xziel_mobile_sprint_zone_hot = false;
		if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
			Cbuf_AddText("impulse 24\n");
			Cbuf_Execute();
		}
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_suppressed = false;
		return;
	}

	if (len > 1.0f) {
		dx /= len;
		dy /= len;
	}

	xziel_mobile_move_x = dx;
	xziel_mobile_move_y = dy;

	sprint_zone = xziel_mobile_sprint_zone.value;
	if (sprint_zone < 1.02f) sprint_zone = 1.02f;
	if (sprint_zone > 1.35f) sprint_zone = 1.35f;

	xziel_mobile_sprint_zone_hot =
		raw_dy >= sprint_zone &&
		fabsf(raw_dx) <= raw_dy * 0.70f;

	if (xziel_mobile_sprint_zone_hot) {
		if (!xziel_mobile_sprint_suppressed) {
			if (xziel_adsfire_release_pending ||
				xziel_adsfire_release_requested ||
				xziel_adsfire_attack_engaged ||
				xziel_adsfire_temp_aim ||
				xziel_mobile_ads_latched)
				Xziel_CancelAdsFireForSprint();

			/* The native stamina/fire-delay rules can legitimately reject a
			   sprint request. Retry while the user is explicitly holding the
			   sprint zone, but never modify native stamina. STAT_ZOOM==3 is
			   the native confirmed sprint state. */
			if (cl.stats[STAT_ZOOM] != 3 && now >= xziel_mobile_sprint_retry_ms) {
				Cbuf_AddText("impulse 23\n");
				Cbuf_Execute();
				xziel_mobile_sprint_retry_ms = now + 120;
			}
			xziel_mobile_sprint_active = true;
		}
	} else {
		if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
			Cbuf_AddText("impulse 24\n");
			Cbuf_Execute();
		}
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_suppressed = false;
		xziel_mobile_sprint_retry_ms = 0;
	}
}'''
text = xziel_replace_c_function(text, "static void Xziel_UpdateMove(float x, float y)", move_func)

# Menu touch semantics:
# - one gesture can never activate a control in a newly-opened child menu;
# - in Mobile Settings child pages, left of the yellow divider selects a row
#   only; values/toggles change only on the right side.
menu_helper = r'''
static qboolean Xziel_IsMobileSettingsChild(void)
{
	return m_state == m_mobileaim ||
		m_state == m_mobilegyro ||
		m_state == m_mobilehud ||
		m_state == m_mobilegameplay;
}

static int Xziel_MenuRowAtY(int my)
{
	int i;
	for (i = 0; i < MAX_MENU_BUTTONS; ++i) {
		menu_button_t *button = &current_menu.button[i];
		if (!button->enabled)
			break;
		if (my >= button->y && my < button->y + button->height)
			return i;
	}
	return -1;
}

static void Xziel_MenuSetCursor(int row)
{
	if (row < 0 || row >= MAX_MENU_BUTTONS)
		return;
	if (current_menu.cursor != row) {
		current_menu.cursor = row;
		Menu_SetSound(MENU_SND_NAVIGATE);
	}
}
'''
menu_func_anchor = "static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)\n"
if "static qboolean Xziel_IsMobileSettingsChild(void)" not in text:
    idx = text.find(menu_func_anchor)
    if idx < 0:
        raise SystemExit("Could not find menu finger helper insertion point")
    text = text[:idx] + menu_helper + "\n" + text[idx:]

menu_finger_func = r'''static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)
{
	int mx = (int)(x * (float)vid.width);
	int my = (int)(y * (float)vid.height);
	int divider_x = UI_X(150);
	qboolean slider_handled = false;

	if (Xziel_IsMobileSettingsChild()) {
		int row = Xziel_MenuRowAtY(my);

		/* Left of the exact yellow MapPanel divider is navigation/selection
		   only. This prevents touching a label from toggling its value. */
		if (mx < divider_x) {
			if (down && row >= 0) {
				Xziel_MenuSetCursor(row);
				if (current_menu.button[row].name &&
					!strcmp(current_menu.button[row].name, "BACK"))
					Menu_ButtonPress();
			}
			return;
		}

		/* Right panel owns settings. Pick the row by Y even though the stock
		   menu's text hitbox lives on the left. Sliders drag directly; option
		   rows activate once on touch-down. */
		if (down && row >= 0) {
			Xziel_MenuSetCursor(row);
			slider_handled = Menu_MouseButton(mx, my, true);
			if (!slider_handled)
				Menu_ButtonPress();
			return;
		}
		if (motion) {
			Menu_MouseMove(mx, my);
			return;
		}
		Menu_MouseButton(mx, my, false);
		return;
	}

	Menu_MouseMove(mx, my);
	if (motion)
		return;

	if (down) {
		slider_handled = Menu_MouseButton(mx, my, true);
		if (!slider_handled)
			Menu_ButtonPress();
	} else {
		Menu_MouseButton(mx, my, false);
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)",
    menu_finger_func
)

finger_down_func = r'''static void Xziel_FingerDown(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;
	xziel_touch_role_t role;

	IN_SetActiveDevice(IN_DEVICE_KEYBOARD_MOUSE);
	Menu_SetInputDevice(IN_DEVICE_KEYBOARD_MOUSE);

	if (cl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
		Xziel_ReleaseAllTouches();
		Menu_ExitMap();
		return;
	}

	if (m_state == m_hudedit && (key_dest == key_menu || key_dest == key_menu_pause)) {
		role = Xziel_HudEditorRole(finger->x, finger->y);
		if (role != XZ_TOUCH_LOOK) {
			slot = Xziel_AllocTouch(finger->fingerId);
			if (!slot) return;
			slot->role = role;
			slot->editor_drag = true;
			slot->last_x = finger->x;
			slot->last_y = finger->y;
			Xziel_HudEditorSetPosition(role, finger->x, finger->y);
			return;
		}
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		xziel_menu_touch_active = true;
		xziel_menu_touch_finger = finger->fingerId;
		xziel_menu_touch_state = m_state;
		Xziel_MenuFinger(finger->x, finger->y, true, false);
		return;
	}

	if (key_dest != key_game)
		return;

	slot = Xziel_AllocTouch(finger->fingerId);
	if (!slot)
		return;

	role = Xziel_RoleForPoint(finger->x, finger->y);
	slot->role = role;
	slot->last_x = finger->x;
	slot->last_y = finger->y;

	if (role == XZ_TOUCH_MOVE) {
		xziel_mobile_move_active = true;
		xziel_mobile_move_anchor_x = finger->x;
		xziel_mobile_move_anchor_y = finger->y;
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (role != XZ_TOUCH_LOOK) {
		Xziel_ActionDown(role);
	}
}'''
text = xziel_replace_c_function(text, "static void Xziel_FingerDown(const SDL_TouchFingerEvent *finger)", finger_down_func)

finger_motion_func = r'''static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;

	slot = Xziel_FindTouch(finger->fingerId);
	if (slot && slot->editor_drag) {
		Xziel_HudEditorSetPosition(slot->role, finger->x, finger->y);
		slot->last_x = finger->x;
		slot->last_y = finger->y;
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		if (!xziel_menu_touch_active ||
			xziel_menu_touch_finger != finger->fingerId ||
			xziel_menu_touch_state != m_state)
			return;
		Xziel_MenuFinger(finger->x, finger->y, false, true);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
	if (!slot)
		return;

	if (slot->role == XZ_TOUCH_MOVE) {
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (slot->role == XZ_TOUCH_LOOK ||
		slot->role == XZ_TOUCH_FIRE ||
		slot->role == XZ_TOUCH_ADSFIRE ||
		slot->role == XZ_TOUCH_ADS) {
		float look_scale = xziel_mobile_touch_sensitivity.value;
		if (cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)
			look_scale *= xziel_mobile_ads_sensitivity.value;
		mouse_dx += (int)((finger->x - slot->last_x) * (float)vid.width * look_scale);
		mouse_dy += (int)((finger->y - slot->last_y) * (float)vid.height * look_scale);
	}
	slot->last_x = finger->x;
	slot->last_y = finger->y;
}'''
text = xziel_replace_c_function(text, "static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)", finger_motion_func)

finger_up_func = r'''static void Xziel_FingerUp(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;

	slot = Xziel_FindTouch(finger->fingerId);
	if (slot && slot->editor_drag) {
		Xziel_HudEditorSetPosition(slot->role, finger->x, finger->y);
		slot->active = false;
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		/* If touch-down changed menu state, consume the rest of that gesture.
		   This is the parent->child accidental selection bug reported on
		   Android. */
		if (xziel_menu_touch_active &&
			xziel_menu_touch_finger == finger->fingerId &&
			xziel_menu_touch_state == m_state)
			Xziel_MenuFinger(finger->x, finger->y, false, false);
		xziel_menu_touch_active = false;
		xziel_menu_touch_state = -1;
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
	if (!slot)
		return;

	if (slot->role == XZ_TOUCH_MOVE) {
		xziel_mobile_move_active = false;
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
		xziel_mobile_sprint_zone_hot = false;
		xziel_mobile_sprint_suppressed = false;
		if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
			Cbuf_AddText("impulse 24\n");
			Cbuf_Execute();
		}
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_retry_ms = 0;
	} else if (slot->role != XZ_TOUCH_LOOK) {
		Xziel_ActionUp(slot->role);
	}
	slot->active = false;
}'''
text = xziel_replace_c_function(text, "static void Xziel_FingerUp(const SDL_TouchFingerEvent *finger)", finger_up_func)

# Full reset must also clear pending release-fire/sprint/menu state.
release_func = r'''static void Xziel_ReleaseAllTouches(void)
{
	int i;
	for (i = 0; i < XZIEL_MAX_TOUCHES; ++i) {
		if (!xziel_touches[i].active)
			continue;
		if (!xziel_touches[i].editor_drag)
			Xziel_ActionUp(xziel_touches[i].role);
		xziel_touches[i].active = false;
	}
	xziel_mobile_move_active = false;
	xziel_mobile_move_x = 0.0f;
	xziel_mobile_move_y = 0.0f;
	xziel_mobile_sprint_zone_hot = false;
	xziel_mobile_sprint_suppressed = false;
	xziel_mobile_sprint_active = false;
	xziel_mobile_sprint_retry_ms = 0;

	if (xziel_attack_command_down) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
	}
	xziel_attack_refs = 0;
	if (xziel_aim_refs > 0)
		Cbuf_AddText("-aim\n");
	xziel_aim_refs = 0;

	xziel_adsfire_attack_engaged = false;
	xziel_adsfire_release_pending = false;
	xziel_adsfire_release_requested = false;
	xziel_adsfire_temp_aim = false;
	xziel_adsfire_cancelled = false;
	xziel_mobile_restore_ads_after_reload = false;
	xziel_mobile_reload_animation_seen = false;
	xziel_menu_touch_active = false;
	xziel_menu_touch_state = -1;
	Cbuf_Execute();
}'''
text = xziel_replace_c_function(text, "static void Xziel_ReleaseAllTouches(void)", release_func)

sys_sdl.write_text(text, encoding="utf-8")

# ---- HUD: explicit sprint lock icon ----------------------------------------
hud = source / "render" / "r_hud.c"
htext = hud.read_text(encoding="utf-8")

hud_extern_anchor = "extern cvar_t xziel_mobile_knife_range_only;\n"
hud_externs = """extern qboolean xziel_mobile_sprint_zone_hot;
extern qboolean xziel_mobile_sprint_active;
extern cvar_t xziel_mobile_sprint_zone;
"""
if "extern qboolean xziel_mobile_sprint_zone_hot;" not in htext:
    if hud_extern_anchor not in htext:
        raise SystemExit("Could not find HUD v0.8 extern anchor for sprint icon")
    htext = htext.replace(hud_extern_anchor, hud_extern_anchor + hud_externs, 1)

hud_func = r'''static void Xziel_MobileHUD_DrawInternal(qboolean editor)
{
	int base_x, base_y, knob_x, knob_y, radius, knob_r;
	int sprint_x, sprint_y, sprint_r;
	float sprint_zone;
	const char *sprint_label = "^^";
	int sprint_tw;

	if (!editor && (key_dest != key_game || cl.stats[STAT_HEALTH] <= 0))
		return;

	base_x = (int)((xziel_mobile_move_active && !editor ? xziel_mobile_move_anchor_x : xziel_hud_joy_x.value) * vid.width);
	base_y = (int)((xziel_mobile_move_active && !editor ? xziel_mobile_move_anchor_y : xziel_hud_joy_y.value) * vid.height);
	radius = (int)(0.095f * vid.height * xziel_mobile_hud_scale.value);
	knob_r = (int)(0.042f * vid.height * xziel_mobile_hud_scale.value);
	Xziel_DrawDisc(base_x, base_y, radius, 240, 240, 240, (int)(70 * xziel_mobile_hud_opacity.value));
	Xziel_DrawDisc(base_x, base_y, radius - (int)(2 * vid.scale), 0, 0, 0, (int)(95 * xziel_mobile_hud_opacity.value));
	knob_x = base_x + (int)(xziel_mobile_move_x * radius * 0.72f);
	knob_y = base_y - (int)(xziel_mobile_move_y * radius * 0.72f);
	Xziel_DrawDisc(knob_x, knob_y, knob_r, 245, 245, 245,
		(int)((xziel_mobile_move_active ? 150 : 90) * xziel_mobile_hud_opacity.value));

	/* COD-style sprint lock target lives beyond the normal joystick throw.
	   It is not a separate tap button: drag the movement thumb upward into it. */
	sprint_zone = xziel_mobile_sprint_zone.value;
	if (sprint_zone < 1.02f) sprint_zone = 1.02f;
	if (sprint_zone > 1.35f) sprint_zone = 1.35f;
	sprint_x = base_x;
	sprint_y = base_y - (int)(0.16f * vid.height * sprint_zone);
	sprint_r = (int)(0.030f * vid.height * xziel_mobile_hud_scale.value);
	if (editor || xziel_mobile_move_active) {
		qboolean sprint_on = xziel_mobile_sprint_zone_hot || xziel_mobile_sprint_active ||
			cl.stats[STAT_ZOOM] == 3;
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r, 245, 245, 245,
			(int)((sprint_on ? 145 : 70) * xziel_mobile_hud_opacity.value));
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r - (int)(2 * vid.scale),
			sprint_on ? 95 : 8, sprint_on ? 95 : 8, sprint_on ? 20 : 8,
			(int)((sprint_on ? 165 : 100) * xziel_mobile_hud_opacity.value));
		sprint_tw = getTextWidth((char *)sprint_label, vid.scale * 0.70f);
		Draw_ColoredString(sprint_x - sprint_tw / 2, sprint_y - (int)(3 * vid.scale),
			(char *)sprint_label, 255, 255, 255, 235, vid.scale * 0.70f);
	}

	Xziel_DrawTouchButton(xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.073f, "FIRE", "", xziel_mobile_fire_pressed);
	Xziel_DrawTouchButton(xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.056f, "ADS", "FIRE", xziel_mobile_adsfire_pressed);
	Xziel_DrawTouchButton(xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.047f, "ADS", "", xziel_mobile_ads_pressed);
	Xziel_DrawTouchButton(xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.044f, "RLD", "", xziel_mobile_reload_pressed);
	if (editor || xziel_mobile_use_available)
		Xziel_DrawTouchButton(xziel_hud_use_x.value, xziel_hud_use_y.value, 0.050f, "USE", "", xziel_mobile_use_pressed);
	Xziel_DrawTouchButton(xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f, "II", "", false);
	Xziel_DrawTouchButton(xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.044f, "JUMP", "", xziel_mobile_jump_pressed);
	if (editor || !xziel_mobile_knife_range_only.value || xziel_mobile_knife_target_near)
		Xziel_DrawTouchButton(xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f, "KNIFE", "", xziel_mobile_knife_pressed);
	Xziel_DrawTouchButton(xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.041f, "SWAP", "", xziel_mobile_switch_pressed);
}'''
htext = xziel_replace_c_function(
    htext,
    "static void Xziel_MobileHUD_DrawInternal(qboolean editor)",
    hud_func
)
hud.write_text(htext, encoding="utf-8")

# ---- Mobile Gameplay UI -----------------------------------------------------
controls = source / "menu" / "menu_controls.c"
mtext = controls.read_text(encoding="utf-8")
menu_extern_anchor = "extern cvar_t xziel_mobile_auto_knife_range;\n"
if "extern cvar_t xziel_mobile_sprint_zone;" not in mtext:
    if menu_extern_anchor not in mtext:
        raise SystemExit("Could not find Mobile Gameplay extern anchor")
    mtext = mtext.replace(
        menu_extern_anchor,
        menu_extern_anchor + "extern cvar_t xziel_mobile_sprint_zone;\n",
        1
    )

gameplay_func = r'''void Menu_MobileGameplay_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - GAMEPLAY", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	xziel_mobile_auto_rebuild_string =
		xziel_mobile_auto_rebuild.value >= 0.5f ? "ENABLED" : "DISABLED";
	xziel_mobile_auto_knife_string =
		xziel_mobile_auto_knife.value >= 0.5f ? "ENABLED" : "DISABLED";
	xziel_mobile_knife_visibility_string =
		xziel_mobile_knife_range_only.value >= 0.5f ? "IN RANGE" : "ALWAYS";

	Menu_DrawButton(row++, idx++, "SPRINT LOCK ZONE", "Drag the joystick into the icon above it to request native sprint.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 1.02f, 1.35f, xziel_mobile_sprint_zone, "xziel_mobile_sprint_zone", false, true, 0.01f);

	Menu_DrawButton(row++, idx++, "AUTO REBUILD BARRIERS", "Automatically repair barricades while you remain in range.", Menu_Mobile_ToggleAutoRebuild);
	Menu_DrawOptionButton(row-1, xziel_mobile_auto_rebuild_string);

	Menu_DrawButton(row++, idx++, "AUTO KNIFE", "Automatically melee only when native NZ:P melee distance can reach the target.", Menu_Mobile_ToggleAutoKnife);
	Menu_DrawOptionButton(row-1, xziel_mobile_auto_knife_string);

	Menu_DrawButton(row++, idx++, "KNIFE BUTTON", "Show the manual knife button always or only at native melee distance.", Menu_Mobile_ToggleKnifeVisibility);
	Menu_DrawOptionButton(row-1, xziel_mobile_knife_visibility_string);

	Menu_DrawButton(row++, idx++, "KNIFE RANGE", "Uses native weapon melee range; not an artificial mobile distance.", NULL);
	Menu_DrawOptionButton(row-1, "NATIVE 88 / 96");

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}'''
mtext = xziel_replace_c_function(
    mtext,
    "void Menu_MobileGameplay_Draw(void)",
    gameplay_func
)
controls.write_text(mtext, encoding="utf-8")


# ---- v0.9.1 compile-order compatibility -----------------------------------
# Vril currently comments out W_KRAUS even though the current QuakeC weapon
# table still assigns the upgraded Ballistic Knife/Krauss ID 53.
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

compat_anchor = "#ifdef __ANDROID__\n"
compat_define = """#ifdef __ANDROID__
#ifndef W_KRAUS
#define W_KRAUS 53
#endif
"""
if "#ifndef W_KRAUS" not in text:
    if compat_anchor not in text:
        raise SystemExit("Could not find Android runtime block for W_KRAUS compatibility")
    text = text.replace(compat_anchor, compat_define, 1)

proto_anchor = "static void Xziel_UpdateMobileFire(void)\n"
prototypes = """static qboolean Xziel_IsDualWeaponMobile(void);
static qboolean Xziel_WeaponDoesNotAdsMobile(void);
static void Xziel_PulseAttackNow(void);
static void Xziel_FinishTemporaryAdsFireAim(void);

"""
if "static qboolean Xziel_IsDualWeaponMobile(void);" not in text:
    idx = text.find(proto_anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile-fire function for v0.9 helper prototypes")
    text = text[:idx] + prototypes + text[idx:]

sys_sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# v0.9.1 compile-order / Krauss client-ID correction
# ---------------------------------------------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

# Vril's client header comments out W_KRAUS even though QuakeC still assigns
# the Pack-a-Punched Ballistic Knife weapon ID 53. Use the protocol ID here so
# mobile behavior continues to match the authoritative QuakeC definition.
text = text.replace("case W_KRAUS:", "case 53: /* W_KRAUS in QuakeC */")
text = text.replace(
	"cl.stats[STAT_ACTIVEWEAPON] == W_KRAUS",
	"cl.stats[STAT_ACTIVEWEAPON] == 53 /* W_KRAUS in QuakeC */"
)

# Xziel_UpdateMobileFire is physically earlier in sys_sdl.c than the v0.9
# helper definitions. C99 requires declarations before use.
proto_anchor = "static void Xziel_UpdateMobileFire(void)\n"
proto_block = """static qboolean Xziel_IsDualWeaponMobile(void);
static qboolean Xziel_WeaponDoesNotAdsMobile(void);
static void Xziel_PulseAttackNow(void);
static void Xziel_FinishTemporaryAdsFireAim(void);

"""
if proto_block not in text:
    idx = text.find(proto_anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile fire updater for v0.9.1 prototypes")
    text = text[:idx] + proto_block + text[idx:]

sys_sdl.write_text(text, encoding="utf-8")


# ---- v0.9.2 HUD/runtime link visibility ------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")
if "static qboolean xziel_mobile_sprint_active = false;" in text:
    text = text.replace(
        "static qboolean xziel_mobile_sprint_active = false;",
        "qboolean xziel_mobile_sprint_active = false;",
        1
    )
sys_sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# v0.9.2 linker correction: sprint state is shared with Android HUD
# ---------------------------------------------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")
text = text.replace(
    "static qboolean xziel_mobile_sprint_active = false;",
    "qboolean xziel_mobile_sprint_active = false;"
)
sys_sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android weapon-class ADS+FIRE pass v0.10
# Per-class PRESS/RELEASE/COD STYLE, pistol ADS coverage, early-release cancel.
# ---------------------------------------------------------------------------

# Archived per-class behavior. 0=PRESS, 1=RELEASE, 2=COD STYLE.
inp = source / "input.c"
itext = inp.read_text(encoding="utf-8")
cvar_anchor = 'cvar_t xziel_mobile_sprint_zone = {"xziel_mobile_sprint_zone", "1.10", true};\n'
class_cvars = """cvar_t xziel_mobile_sniper_adsfire = {"xziel_mobile_sniper_adsfire", "2", true};
cvar_t xziel_mobile_shotgun_adsfire = {"xziel_mobile_shotgun_adsfire", "2", true};
cvar_t xziel_mobile_marksman_adsfire = {"xziel_mobile_marksman_adsfire", "2", true};
"""
if "xziel_mobile_sniper_adsfire" not in itext:
    if cvar_anchor not in itext:
        raise SystemExit("Could not find v0.9 mobile cvar anchor")
    itext = itext.replace(cvar_anchor, cvar_anchor + class_cvars, 1)

reg_anchor = "\tCvar_RegisterVariable(&xziel_mobile_sprint_zone);\n"
class_regs = """	Cvar_RegisterVariable(&xziel_mobile_sniper_adsfire);
	Cvar_RegisterVariable(&xziel_mobile_shotgun_adsfire);
	Cvar_RegisterVariable(&xziel_mobile_marksman_adsfire);
"""
if "Cvar_RegisterVariable(&xziel_mobile_sniper_adsfire);" not in itext:
    if reg_anchor not in itext:
        raise SystemExit("Could not find v0.9 mobile cvar register anchor")
    itext = itext.replace(reg_anchor, reg_anchor + class_regs, 1)
inp.write_text(itext, encoding="utf-8")

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

extern_anchor = "extern cvar_t xziel_mobile_sprint_zone;\n"
class_externs = """extern cvar_t xziel_mobile_sniper_adsfire;
extern cvar_t xziel_mobile_shotgun_adsfire;
extern cvar_t xziel_mobile_marksman_adsfire;
"""
if "extern cvar_t xziel_mobile_sniper_adsfire;" not in text:
    if extern_anchor not in text:
        raise SystemExit("Could not find v0.9 runtime cvar extern anchor")
    text = text.replace(extern_anchor, extern_anchor + class_externs, 1)

# All native ADS-capable single weapons must use ADS+FIRE. Only the weapons
# explicitly blocked by QuakeC WepDef_DoesNotADS(), plus the two native dual
# wield forms that W_AimIn rejects, bypass ADS.
weapon_helpers = r'''
static qboolean Xziel_WeaponCanAdsMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_TESLA:
	case W_DG3:
	case W_BK:
	case 53: /* W_KRAUS in QuakeC */
	case W_BIATCH:
	case W_SNUFF:
		return false;
	default:
		return true;
	}
}

static qboolean Xziel_IsPistolMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_COLT:
	case W_357:
	case W_KILLU:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_IsShotgunMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_DB:
	case W_BORE:
	case W_SAWNOFF:
	case W_TRENCH:
	case W_GUT:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_IsSniperMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_KAR_SCOPE:
	case W_HEADCRACKER:
	case W_PTRS:
	case W_PENETRATOR:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_IsMarksmanMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	/* Bolt/iron-sight precision rifles */
	case W_KAR:
	case W_ARMAGEDDON:
	case W_SPRING:
	case W_PULVERIZER:
	/* Semi-auto precision rifles */
	case W_GEWEHR:
	case W_COMPRESSOR:
	case W_M1:
	case W_M1000:
	case W_M1A1:
	case W_WIDDER:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_IsBoltMarksmanMobile(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_KAR:
	case W_ARMAGEDDON:
	case W_SPRING:
	case W_PULVERIZER:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_AdsReadyForFire(void)
{
	/* NZ:P reports a true sniper scope as zoom 2 after its scope-in delay.
	   Ordinary iron-sight ADS uses zoom 1. */
	if (Xziel_IsSniperMobile())
		return cl.stats[STAT_ZOOM] == 2;
	return cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2;
}

static int Xziel_AdsFireModeForCurrentWeapon(void)
{
	int mode = 0;

	if (Xziel_IsSniperMobile()) {
		mode = (int)xziel_mobile_sniper_adsfire.value;
		if (mode == 2) return 1; /* COD style: release */
		return mode == 1 ? 1 : 0;
	}

	if (Xziel_IsShotgunMobile()) {
		mode = (int)xziel_mobile_shotgun_adsfire.value;
		if (mode == 2) return 1; /* COD style: release */
		return mode == 1 ? 1 : 0;
	}

	if (Xziel_IsMarksmanMobile()) {
		mode = (int)xziel_mobile_marksman_adsfire.value;
		if (mode == 2)
			return Xziel_IsBoltMarksmanMobile() ? 1 : 0;
		return mode == 1 ? 1 : 0;
	}

	return 0; /* pistols/SMGs/ARs/LMGs/etc: press-to-fire */
}
'''
helper_anchor = "static qboolean Xziel_IsDualWeaponMobile(void)\n"
if "static qboolean Xziel_WeaponCanAdsMobile(void)" not in text:
    idx = text.find(helper_anchor)
    if idx < 0:
        raise SystemExit("Could not find v0.9 helper insertion anchor")
    text = text[:idx] + weapon_helpers + "\n" + text[idx:]

# Replace release classification with the new per-class setting.
release_func = r'''static qboolean Xziel_AdsFireReleaseWeapon(void)
{
	return Xziel_AdsFireModeForCurrentWeapon() == 1;
}'''
text = xziel_replace_c_function(
    text,
    "static qboolean Xziel_AdsFireReleaseWeapon(void)",
    release_func
)

# Native ADS readiness is now centralized. This removes pistol/weapon-specific
# holes caused by relying on older no-ADS/dual shortcuts.
update_fire_func = r'''static void Xziel_UpdateMobileFire(void)
{
	Uint32 now = SDL_GetTicks();
	qboolean changed = false;

	if ((xziel_mobile_adsfire_pressed || xziel_adsfire_release_requested) &&
		!xziel_adsfire_cancelled) {
		if (xziel_adsfire_release_pending) {
			/* Release-mode never fires after an early cancellation. Finger-up
			   is the only trigger edge and ActionUp requires ADS-ready first. */
		} else if (!xziel_adsfire_attack_engaged) {
			if (!Xziel_WeaponCanAdsMobile() || Xziel_AdsReadyForFire()) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
	}

	if (xziel_attack_refs <= 0) {
		if (xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
			changed = true;
		}
		if (changed)
			Cbuf_Execute();
		return;
	}

	if (!Xziel_IsAutoTapPistol())
		return;

	/* Mobile hold-fire for native semi-auto pistols. Native weapon fire_delay
	   remains authoritative; these are only input edges. */
	if (xziel_attack_command_down && now >= xziel_attack_release_ms) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
		changed = true;
	}
	if (!xziel_attack_command_down && now >= xziel_attack_next_ms) {
		Cbuf_AddText("+attack\n");
		xziel_attack_command_down = true;
		xziel_attack_release_ms = now + 42;
		xziel_attack_next_ms =
			now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);
		changed = true;
	}
	if (changed)
		Cbuf_Execute();
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_UpdateMobileFire(void)",
    update_fire_func
)

# ADS+FIRE: every native ADS-capable single weapon begins ADS immediately.
# PRESS mode fires on the earliest native ADS-ready frame. RELEASE mode arms
# the shot but does not fire until finger-up. No arbitrary timer is used.
action_down_func = r'''static void Xziel_ActionDown(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = true;
		Xziel_StopSprintForAction();
		Xziel_SetAttackRef(true);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		xziel_adsfire_cancelled = false;
		xziel_adsfire_attack_engaged = false;
		xziel_adsfire_release_requested = false;
		xziel_adsfire_release_pending = Xziel_AdsFireReleaseWeapon();
		xziel_adsfire_temp_aim = false;

		Xziel_StopSprintForAction();

		if (Xziel_WeaponCanAdsMobile()) {
			if (!xziel_mobile_ads_latched) {
				Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
				xziel_adsfire_temp_aim = true;
				Cbuf_Execute();
			}

			/* If already ADS-latched, PRESS mode can fire in this same touch
			   turn. Otherwise UpdateMobileFire starts at the first native
			   ADS-ready frame. */
			if (!xziel_adsfire_release_pending &&
				(xziel_mobile_ads_latched || Xziel_AdsReadyForFire())) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		} else {
			/* True native no-ADS or dual-wield forms behave as fire-only. */
			if (!xziel_adsfire_release_pending) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;
		Xziel_StopSprintForAction();
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			xziel_mobile_ads_latched = !xziel_mobile_ads_latched;
			Cbuf_AddText("impulse 26\n");
		} else {
			xziel_mobile_ads_latched = false;
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		}
		Cbuf_Execute();
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		xziel_mobile_restore_ads_after_reload =
			(xziel_mobile_ads_toggle.value >= 0.5f && xziel_mobile_ads_latched);
		xziel_mobile_reload_animation_seen = false;
		xziel_mobile_reload_start_frame = cl.stats[STAT_WEAPONFRAME];
		Cbuf_AddText("+reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("+use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = true;
		Cbuf_AddText("+jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = true;
		Xziel_StopSprintForAction();
		Cbuf_AddText("+knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		if (xziel_adsfire_release_pending || xziel_adsfire_release_requested)
			Xziel_CancelAdsFireForSprint();
		Cbuf_AddText("+switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		Menu_Pause_Set();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionDown(xziel_touch_role_t role)",
    action_down_func
)

# Critical cancellation semantics:
# - RELEASE mode fires only if the weapon reached its native ADS-ready state.
# - releasing before that immediately aims out and produces NO shot.
# - PRESS mode releases whatever trigger is active and also exits temporary ADS.
action_up_func = r'''static void Xziel_ActionUp(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = false;
		Xziel_SetAttackRef(false);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;

		if (xziel_adsfire_release_pending && !xziel_adsfire_cancelled) {
			if (Xziel_WeaponCanAdsMobile() && Xziel_AdsReadyForFire()) {
				Xziel_PulseAttackNow();
			}
			/* If ADS was not ready, this is a cancelled shot: show whatever
			   partial aim-in animation occurred, then immediately aim back out. */
			xziel_adsfire_release_pending = false;
			xziel_adsfire_release_requested = false;
			Xziel_FinishTemporaryAdsFireAim();
		} else {
			if (xziel_adsfire_attack_engaged) {
				Xziel_SetAttackRef(false);
				xziel_adsfire_attack_engaged = false;
			}
			Xziel_FinishTemporaryAdsFireAim();
			xziel_adsfire_release_pending = false;
			xziel_adsfire_release_requested = false;
		}

		xziel_adsfire_cancelled = false;
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = false;
		if (xziel_mobile_ads_toggle.value < 0.5f) {
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = false;
		Cbuf_AddText("-reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = false;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("-use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = false;
		Cbuf_AddText("-jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = false;
		Cbuf_AddText("-knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = false;
		Cbuf_AddText("-switch\n");
		Cbuf_Execute();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionUp(xziel_touch_role_t role)",
    action_up_func
)

sys_sdl.write_text(text, encoding="utf-8")

# ---- Aim & Touch menu: class-specific ADS+FIRE behavior --------------------
controls = source / "menu" / "menu_controls.c"
mtext = controls.read_text(encoding="utf-8")

menu_extern_anchor = "extern cvar_t xziel_mobile_autofire_ms;\n"
menu_externs = """extern cvar_t xziel_mobile_sniper_adsfire;
extern cvar_t xziel_mobile_shotgun_adsfire;
extern cvar_t xziel_mobile_marksman_adsfire;
"""
if "extern cvar_t xziel_mobile_sniper_adsfire;" not in mtext:
    if menu_extern_anchor not in mtext:
        raise SystemExit("Could not find Aim & Touch cvar extern anchor")
    mtext = mtext.replace(menu_extern_anchor, menu_extern_anchor + menu_externs, 1)

strings_anchor = "static char *xziel_ads_mode_string;\n"
strings = """static char *xziel_sniper_fire_string;
static char *xziel_shotgun_fire_string;
static char *xziel_marksman_fire_string;
"""
if "xziel_sniper_fire_string" not in mtext:
    if strings_anchor not in mtext:
        raise SystemExit("Could not find mobile aim menu string anchor")
    mtext = mtext.replace(strings_anchor, strings_anchor + strings, 1)

cycle_code = r'''
static const char *Menu_MobileAdsFireModeString(cvar_t *value)
{
	int mode = (int)value->value;
	if (mode == 0) return "PRESS TO FIRE";
	if (mode == 1) return "RELEASE TO FIRE";
	return "COD STYLE";
}

static void Menu_MobileCycleSniperFire(void)
{
	Cvar_SetValue("xziel_mobile_sniper_adsfire",
		((int)xziel_mobile_sniper_adsfire.value + 1) % 3);
}

static void Menu_MobileCycleShotgunFire(void)
{
	Cvar_SetValue("xziel_mobile_shotgun_adsfire",
		((int)xziel_mobile_shotgun_adsfire.value + 1) % 3);
}

static void Menu_MobileCycleMarksmanFire(void)
{
	Cvar_SetValue("xziel_mobile_marksman_adsfire",
		((int)xziel_mobile_marksman_adsfire.value + 1) % 3);
}
'''
toggle_anchor = "static void Menu_Mobile_ToggleADS(void)\n"
if "Menu_MobileCycleSniperFire" not in mtext:
    idx = mtext.find(toggle_anchor)
    if idx < 0:
        raise SystemExit("Could not find ADS toggle helper for class fire options")
    mtext = mtext[:idx] + cycle_code + "\n" + mtext[idx:]

aim_menu_func = r'''void Menu_MobileAim_Draw(void)
{
	int idx = 0, row = 1;

	Menu_DrawCustomBackground(true);
	Menu_DrawTitle("MOBILE - AIM & TOUCH", MENU_COLOR_WHITE);
	Menu_DrawMapPanel();

	xziel_ads_mode_string = xziel_mobile_ads_toggle.value >= 0.5f ? "TOGGLE" : "HOLD";
	xziel_sniper_fire_string = (char *)Menu_MobileAdsFireModeString(&xziel_mobile_sniper_adsfire);
	xziel_shotgun_fire_string = (char *)Menu_MobileAdsFireModeString(&xziel_mobile_shotgun_adsfire);
	xziel_marksman_fire_string = (char *)Menu_MobileAdsFireModeString(&xziel_mobile_marksman_adsfire);

	Menu_DrawButton(row++, idx++, "ADS BEHAVIOR", "Dedicated ADS button: Hold or Toggle.", Menu_Mobile_ToggleADS);
	Menu_DrawOptionButton(row-1, xziel_ads_mode_string);

	Menu_DrawButton(row++, idx++, "SNIPER ADS+FIRE", "PRESS fires when native scope is ready. RELEASE fires on release. COD STYLE defaults to release.", Menu_MobileCycleSniperFire);
	Menu_DrawOptionButton(row-1, xziel_sniper_fire_string);

	Menu_DrawButton(row++, idx++, "SHOTGUN ADS+FIRE", "Choose press-to-fire or hold ADS and release to shoot.", Menu_MobileCycleShotgunFire);
	Menu_DrawOptionButton(row-1, xziel_shotgun_fire_string);

	Menu_DrawButton(row++, idx++, "MARKSMAN ADS+FIRE", "COD STYLE: bolt marksman release; semi-auto marksman press.", Menu_MobileCycleMarksmanFire);
	Menu_DrawOptionButton(row-1, xziel_marksman_fire_string);

	Menu_DrawButton(row++, idx++, "TOUCH LOOK", "Hip-fire/free-look sensitivity.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.25f, 4.0f, xziel_mobile_touch_sensitivity, "xziel_mobile_touch_sensitivity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "ADS LOOK", "Touch sensitivity multiplier while ADS.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 0.20f, 1.50f, xziel_mobile_ads_sensitivity, "xziel_mobile_ads_sensitivity", false, true, 0.05f);

	Menu_DrawButton(row++, idx++, "PISTOL AUTO FIRE", "Delay between mobile trigger taps for native semi-auto pistols.", NULL);
	Menu_DrawOptionSlider(row-1, idx-1, 140.0f, 320.0f, xziel_mobile_autofire_ms, "xziel_mobile_autofire_ms", false, true, 10.0f);

	Menu_DrawButton(-1, idx, "BACK", "Return to Mobile Settings.", Menu_Mobile_Set);
}'''
mtext = xziel_replace_c_function(
    mtext,
    "void Menu_MobileAim_Draw(void)",
    aim_menu_func
)
controls.write_text(mtext, encoding="utf-8")


# ---------------------------------------------------------------------------
# v0.10.1 compile-order correction
# ---------------------------------------------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

proto_anchor = "static void Xziel_UpdateMobileFire(void)\n"
proto_block = """static qboolean Xziel_WeaponCanAdsMobile(void);
static qboolean Xziel_AdsReadyForFire(void);

"""
if proto_block not in text:
    idx = text.find(proto_anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile fire updater for v0.10.1 prototypes")
    text = text[:idx] + proto_block + text[idx:]

sys_sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android settings/input correctness pass v0.11
# - split-panel touch rules across settings
# - auto-fit long setting labels
# - release-to-fire ADS-ready latch
# - exact native melee trace for auto knife
# - clearer gyro wording
# - persistent grenade touch control
# ---------------------------------------------------------------------------

# ---- Grenade control persistent HUD position -------------------------------
inp = source / "input.c"
itext = inp.read_text(encoding="utf-8")

grenade_cvar_anchor = 'cvar_t xziel_hud_pause_y = {"xziel_hud_pause_y", "0.075", true};\n'
grenade_cvars = '''cvar_t xziel_hud_grenade_x = {"xziel_hud_grenade_x", "0.835", true};
cvar_t xziel_hud_grenade_y = {"xziel_hud_grenade_y", "0.300", true};
'''
if "xziel_hud_grenade_x" not in itext:
    if grenade_cvar_anchor not in itext:
        raise SystemExit("Could not find pause HUD cvar anchor for grenade")
    itext = itext.replace(grenade_cvar_anchor, grenade_cvar_anchor + grenade_cvars, 1)

grenade_reg_anchor = "\tCvar_RegisterVariable(&xziel_hud_pause_y);\n"
grenade_regs = """	Cvar_RegisterVariable(&xziel_hud_grenade_x);
	Cvar_RegisterVariable(&xziel_hud_grenade_y);
"""
if "Cvar_RegisterVariable(&xziel_hud_grenade_x);" not in itext:
    if grenade_reg_anchor not in itext:
        raise SystemExit("Could not find pause HUD registration anchor for grenade")
    itext = itext.replace(grenade_reg_anchor, grenade_reg_anchor + grenade_regs, 1)

inp.write_text(itext, encoding="utf-8")

# ---- Runtime input ----------------------------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

# Add grenade role after pause.
if "XZ_TOUCH_GRENADE" not in text:
    enum_anchors = [
        "\tXZ_TOUCH_SWITCH,\n\tXZ_TOUCH_PAUSE\n} xziel_touch_role_t;",
        "\tXZ_TOUCH_SWITCH,\n\tXZ_TOUCH_PAUSE,\n} xziel_touch_role_t;"
    ]
    replaced = False
    for anchor in enum_anchors:
        if anchor in text:
            repl = anchor.replace("\tXZ_TOUCH_PAUSE\n", "\tXZ_TOUCH_PAUSE,\n\tXZ_TOUCH_GRENADE\n")
            repl = repl.replace("\tXZ_TOUCH_PAUSE,\n} xziel_touch_role_t;", "\tXZ_TOUCH_PAUSE,\n\tXZ_TOUCH_GRENADE\n} xziel_touch_role_t;")
            text = text.replace(anchor, repl, 1)
            replaced = True
            break
    if not replaced:
        raise SystemExit("Could not find touch enum pause/switch tail for grenade")

state_anchor = "qboolean xziel_mobile_switch_pressed = false;\n"
if "qboolean xziel_mobile_grenade_pressed" not in text:
    if state_anchor not in text:
        raise SystemExit("Could not find mobile switch state for grenade")
    text = text.replace(
        state_anchor,
        state_anchor + "qboolean xziel_mobile_grenade_pressed = false;\n",
        1
    )

pos_anchor = "extern cvar_t xziel_hud_pause_y;\n"
if "extern cvar_t xziel_hud_grenade_x;" not in text:
    if pos_anchor not in text:
        raise SystemExit("Could not find pause position extern for grenade")
    text = text.replace(
        pos_anchor,
        pos_anchor +
        "extern cvar_t xziel_hud_grenade_x;\n"
        "extern cvar_t xziel_hud_grenade_y;\n",
        1
    )

# Track whether release-mode ADS actually reached a shoot-ready state during
# the hold. This avoids racing the networked zoom stat on the exact finger-up.
ads_seen_anchor = "static qboolean xziel_adsfire_cancelled = false;\n"
if "xziel_adsfire_ads_seen" not in text:
    if ads_seen_anchor not in text:
        raise SystemExit("Could not find ADS+FIRE state anchor")
    text = text.replace(
        ads_seen_anchor,
        ads_seen_anchor + "static qboolean xziel_adsfire_ads_seen = false;\n",
        1
    )

# Auto-knife uses a real held input edge for long enough to cross a move packet,
# rather than +knife/-knife in the same event callback.
knife_state_anchor = "static Uint32 xziel_mobile_auto_knife_next_ms = 0;\n"
if "xziel_auto_knife_down" not in text:
    if knife_state_anchor not in text:
        raise SystemExit("Could not find auto knife timing state")
    text = text.replace(
        knife_state_anchor,
        knife_state_anchor +
        "static qboolean xziel_auto_knife_down = false;\n"
        "static Uint32 xziel_auto_knife_release_ms = 0;\n",
        1
    )

# ---- Split settings touch behavior across all yellow-divider settings -------
split_helpers = r'''
static qboolean Xziel_IsSplitSettingsMenu(void)
{
	switch (m_state) {
	case m_video:
	case m_accessibility:
	case m_controls:
	case m_gyro:
	case m_gamesettings:
	case m_mobileaim:
	case m_mobilegyro:
	case m_mobilehud:
	case m_mobilegameplay:
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_LeftSideIsNavigation(const char *name)
{
	if (!name) return false;
	return !strcmp(name, "BACK") ||
		!strcmp(name, "GYROSCOPE") ||
		!strcmp(name, "BINDINGS") ||
		!strcmp(name, "CUSTOM HUD");
}
'''
if "static qboolean Xziel_IsSplitSettingsMenu(void)" not in text:
    helper_anchor = "static qboolean Xziel_IsMobileSettingsChild(void)\n"
    idx = text.find(helper_anchor)
    if idx < 0:
        raise SystemExit("Could not find old mobile settings helper")
    text = text[:idx] + split_helpers + "\n" + text[idx:]

menu_finger = r'''static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)
{
	int mx = (int)(x * (float)vid.width);
	int my = (int)(y * (float)vid.height);
	int divider_x = UI_X(150);
	qboolean slider_handled = false;

	if (Xziel_IsSplitSettingsMenu()) {
		int row = Xziel_MenuRowAtY(my);

		/* On every settings page with the yellow vertical divider:
		   LEFT = select/navigate only. RIGHT = edit values. */
		if (mx < divider_x) {
			if (down && row >= 0) {
				Xziel_MenuSetCursor(row);
				if (Xziel_LeftSideIsNavigation(current_menu.button[row].name))
					Menu_ButtonPress();
			}
			return;
		}

		if (down && row >= 0) {
			Xziel_MenuSetCursor(row);
			slider_handled = Menu_MouseButton(mx, my, true);
			if (!slider_handled)
				Menu_ButtonPress();
			return;
		}

		if (motion) {
			/* Only let stock slider dragging see motion on the value side. */
			Menu_MouseMove(mx, my);
			return;
		}

		Menu_MouseButton(mx, my, false);
		return;
	}

	Menu_MouseMove(mx, my);
	if (motion)
		return;

	if (down) {
		slider_handled = Menu_MouseButton(mx, my, true);
		if (!slider_handled)
			Menu_ButtonPress();
	} else {
		Menu_MouseButton(mx, my, false);
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)",
    menu_finger
)

# ---- ADS+FIRE state machine ------------------------------------------------
update_fire = r'''static void Xziel_UpdateMobileFire(void)
{
	Uint32 now = SDL_GetTicks();
	qboolean changed = false;

	if (xziel_mobile_adsfire_pressed &&
		!xziel_adsfire_cancelled &&
		Xziel_WeaponCanAdsMobile() &&
		Xziel_AdsReadyForFire())
		xziel_adsfire_ads_seen = true;

	if ((xziel_mobile_adsfire_pressed || xziel_adsfire_release_requested) &&
		!xziel_adsfire_cancelled) {
		if (!xziel_adsfire_release_pending &&
			!xziel_adsfire_attack_engaged) {
			if (!Xziel_WeaponCanAdsMobile() || Xziel_AdsReadyForFire()) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
	}

	if (xziel_attack_refs <= 0) {
		if (xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
			changed = true;
		}
		if (changed)
			Cbuf_Execute();
		return;
	}

	if (!Xziel_IsAutoTapPistol())
		return;

	if (xziel_attack_command_down && now >= xziel_attack_release_ms) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
		changed = true;
	}
	if (!xziel_attack_command_down && now >= xziel_attack_next_ms) {
		Cbuf_AddText("+attack\n");
		xziel_attack_command_down = true;
		xziel_attack_release_ms = now + 42;
		xziel_attack_next_ms =
			now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);
		changed = true;
	}
	if (changed)
		Cbuf_Execute();
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_UpdateMobileFire(void)",
    update_fire
)

action_down = r'''static void Xziel_ActionDown(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = true;
		Xziel_StopSprintForAction();
		Xziel_SetAttackRef(true);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		xziel_adsfire_cancelled = false;
		xziel_adsfire_attack_engaged = false;
		xziel_adsfire_release_requested = false;
		xziel_adsfire_release_pending = Xziel_AdsFireReleaseWeapon();
		xziel_adsfire_temp_aim = false;
		xziel_adsfire_ads_seen = false;

		Xziel_StopSprintForAction();

		if (Xziel_WeaponCanAdsMobile()) {
			if (!xziel_mobile_ads_latched) {
				Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
				xziel_adsfire_temp_aim = true;
				Cbuf_Execute();
			}

			if (Xziel_AdsReadyForFire())
				xziel_adsfire_ads_seen = true;

			if (!xziel_adsfire_release_pending &&
				(xziel_mobile_ads_latched || Xziel_AdsReadyForFire())) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		} else {
			if (!xziel_adsfire_release_pending) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;
		Xziel_StopSprintForAction();
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			xziel_mobile_ads_latched = !xziel_mobile_ads_latched;
			Cbuf_AddText("impulse 26\n");
		} else {
			xziel_mobile_ads_latched = false;
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		}
		Cbuf_Execute();
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		xziel_mobile_restore_ads_after_reload =
			(xziel_mobile_ads_toggle.value >= 0.5f && xziel_mobile_ads_latched);
		xziel_mobile_reload_animation_seen = false;
		xziel_mobile_reload_start_frame = cl.stats[STAT_WEAPONFRAME];
		Cbuf_AddText("+reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("+use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = true;
		Cbuf_AddText("+jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = true;
		Xziel_StopSprintForAction();
		Cbuf_AddText("+knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_GRENADE:
		xziel_mobile_grenade_pressed = true;
		Xziel_StopSprintForAction();
		Cbuf_AddText("+grenade\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		if (xziel_adsfire_release_pending || xziel_adsfire_release_requested)
			Xziel_CancelAdsFireForSprint();
		Cbuf_AddText("+switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		Menu_Pause_Set();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionDown(xziel_touch_role_t role)",
    action_down
)

action_up = r'''static void Xziel_ActionUp(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = false;
		Xziel_SetAttackRef(false);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;

		if (xziel_adsfire_release_pending && !xziel_adsfire_cancelled) {
			/* A release shot is legal if ADS became ready at any time during
			   this hold. Do not depend on the exact zoom value on finger-up. */
			if (!Xziel_WeaponCanAdsMobile() ||
				xziel_adsfire_ads_seen ||
				Xziel_AdsReadyForFire()) {
				Xziel_PulseAttackNow();
			}
			xziel_adsfire_release_pending = false;
			xziel_adsfire_release_requested = false;
			Xziel_FinishTemporaryAdsFireAim();
		} else {
			if (xziel_adsfire_attack_engaged) {
				Xziel_SetAttackRef(false);
				xziel_adsfire_attack_engaged = false;
			}
			Xziel_FinishTemporaryAdsFireAim();
			xziel_adsfire_release_pending = false;
			xziel_adsfire_release_requested = false;
		}

		xziel_adsfire_ads_seen = false;
		xziel_adsfire_cancelled = false;
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = false;
		if (xziel_mobile_ads_toggle.value < 0.5f) {
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = false;
		Cbuf_AddText("-reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = false;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("-use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = false;
		Cbuf_AddText("-jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = false;
		Cbuf_AddText("-knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_GRENADE:
		xziel_mobile_grenade_pressed = false;
		Cbuf_AddText("-grenade\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = false;
		Cbuf_AddText("-switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionUp(xziel_touch_role_t role)",
    action_up
)

# Cancel helper must clear ADS-ready history too.
cancel_func = r'''static void Xziel_CancelAdsFireForSprint(void)
{
	if (xziel_adsfire_attack_engaged) {
		Xziel_SetAttackRef(false);
		xziel_adsfire_attack_engaged = false;
	}

	xziel_adsfire_release_pending = false;
	xziel_adsfire_release_requested = false;
	xziel_adsfire_ads_seen = false;
	xziel_adsfire_cancelled = true;
	Xziel_FinishTemporaryAdsFireAim();

	if (xziel_mobile_ads_latched) {
		Cbuf_AddText("impulse 26\n");
		Cbuf_Execute();
		xziel_mobile_ads_latched = false;
	}
	xziel_mobile_restore_ads_after_reload = false;
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_CancelAdsFireForSprint(void)",
    cancel_func
)

# ---- Exact native melee trace ----------------------------------------------
auto_knife = r'''static void Xziel_UpdateAutoKnife(void)
{
	qboolean near_target = false;
	Uint32 now = SDL_GetTicks();

	/* Finish the short synthetic knife hold after at least one movement packet
	   has had a chance to carry button6 to the native server code. */
	if (xziel_auto_knife_down && now >= xziel_auto_knife_release_ms) {
		Cbuf_AddText("-knife\n");
		Cbuf_Execute();
		xziel_auto_knife_down = false;
	}

	if (key_dest == key_game &&
		sv.active && sv_player &&
		sv_player->v.health > 0 &&
		cls.signon == SIGNONS) {
		vec3_t start, end, forward;
		trace_t tr;
		edict_t *target = NULL;
		const char *classname = "";
		int weapon = (int)sv_player->v.weapon;
		float range = (weapon == W_BK || weapon == 53) ? 96.0f : 88.0f;

		/* Mirror WeaponCore_Melee:
		   makevectors(self.v_angle)
		   trace_source = self.origin + self.view_ofs
		   traceline(trace_source, trace_source + v_forward * range, 0, self) */
		VectorAdd(sv_player->v.origin, sv_player->v.view_ofs, start);
		AngleVectors(sv_player->v.v_angle, forward, NULLVEC, NULLVEC);
		VectorMA(start, range, forward, end);
		tr = SV_Move(start, vec3_origin, vec3_origin, end, 0, sv_player);
		target = tr.ent;

		if (target && target != sv.edicts && tr.fraction < 1.0f &&
			(tr.endpos[2] - start[2]) <= 15.0f) {
			/* Native melee promotes zombie limb edicts back to their body. */
			if (target->v.owner) {
				edict_t *owner = PROG_TO_EDICT(target->v.owner);
				int target_prog = EDICT_TO_PROG(target);
				if (owner && owner != sv.edicts &&
					(owner->v.head == target_prog ||
					 owner->v.larm == target_prog ||
					 owner->v.rarm == target_prog))
					target = owner;
			}

			classname = PR_GetString(target->v.classname);
			near_target =
				(!strcmp(classname, "ai_zombie") ||
				 !strcmp(classname, "ai_dog")) &&
				target->v.takedamage != 0;
		}
	}

	xziel_mobile_knife_target_near = near_target;

	if (xziel_mobile_auto_knife.value >= 0.5f &&
		near_target &&
		!xziel_mobile_knife_pressed &&
		!xziel_auto_knife_down &&
		sv_player && sv_player->v.zoom == 0 &&
		now >= xziel_mobile_auto_knife_next_ms) {
		Cbuf_AddText("+knife\n");
		Cbuf_Execute();
		xziel_auto_knife_down = true;
		xziel_auto_knife_release_ms = now + 90;
		xziel_mobile_auto_knife_next_ms = now + 450;
	} else if (!near_target && !xziel_auto_knife_down) {
		xziel_mobile_auto_knife_next_ms = now;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_UpdateAutoKnife(void)",
    auto_knife
)

# ---- Grenade hitbox + HUD editor ------------------------------------------
role_func = r'''static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.073f * hs)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.056f * hs)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.047f * hs)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.044f * hs)) return XZ_TOUCH_RELOAD;
	if (xziel_mobile_use_available && Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.050f * hs)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f * hs)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.041f * hs)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.044f * hs)) return XZ_TOUCH_JUMP;
	if ((!xziel_mobile_knife_range_only.value || xziel_mobile_knife_target_near) &&
		Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f * hs))
		return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.041f * hs)) return XZ_TOUCH_SWITCH;
	if (x < 0.45f && y > 0.30f) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_LOOK;
}'''
text = xziel_replace_c_function(
    text,
    "static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)",
    role_func
)

editor_role = r'''static xziel_touch_role_t Xziel_HudEditorRole(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.090f * hs)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.075f * hs)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.065f * hs)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.060f * hs)) return XZ_TOUCH_RELOAD;
	if (Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.065f * hs)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.055f * hs)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.057f * hs)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.060f * hs)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.060f * hs)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.057f * hs)) return XZ_TOUCH_SWITCH;
	if (Xziel_IsInside(x, y, xziel_hud_joy_x.value, xziel_hud_joy_y.value, 0.120f * hs)) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_NONE;
}'''
text = xziel_replace_c_function(
    text,
    "static xziel_touch_role_t Xziel_HudEditorRole(float x, float y)",
    editor_role
)

editor_set = r'''static void Xziel_HudEditorSetPosition(xziel_touch_role_t role, float x, float y)
{
	if (x < 0.035f) x = 0.035f;
	if (x > 0.965f) x = 0.965f;
	if (y < 0.055f) y = 0.055f;
	if (y > 0.945f) y = 0.945f;

	switch (role) {
	case XZ_TOUCH_MOVE:
		Cvar_SetValue("xziel_hud_joy_x", x); Cvar_SetValue("xziel_hud_joy_y", y); break;
	case XZ_TOUCH_FIRE:
		Cvar_SetValue("xziel_hud_fire_x", x); Cvar_SetValue("xziel_hud_fire_y", y); break;
	case XZ_TOUCH_ADSFIRE:
		Cvar_SetValue("xziel_hud_adsfire_x", x); Cvar_SetValue("xziel_hud_adsfire_y", y); break;
	case XZ_TOUCH_ADS:
		Cvar_SetValue("xziel_hud_ads_x", x); Cvar_SetValue("xziel_hud_ads_y", y); break;
	case XZ_TOUCH_RELOAD:
		Cvar_SetValue("xziel_hud_reload_x", x); Cvar_SetValue("xziel_hud_reload_y", y); break;
	case XZ_TOUCH_USE:
		Cvar_SetValue("xziel_hud_use_x", x); Cvar_SetValue("xziel_hud_use_y", y); break;
	case XZ_TOUCH_JUMP:
		Cvar_SetValue("xziel_hud_jump_x", x); Cvar_SetValue("xziel_hud_jump_y", y); break;
	case XZ_TOUCH_KNIFE:
		Cvar_SetValue("xziel_hud_knife_x", x); Cvar_SetValue("xziel_hud_knife_y", y); break;
	case XZ_TOUCH_GRENADE:
		Cvar_SetValue("xziel_hud_grenade_x", x); Cvar_SetValue("xziel_hud_grenade_y", y); break;
	case XZ_TOUCH_SWITCH:
		Cvar_SetValue("xziel_hud_switch_x", x); Cvar_SetValue("xziel_hud_switch_y", y); break;
	case XZ_TOUCH_PAUSE:
		Cvar_SetValue("xziel_hud_pause_x", x); Cvar_SetValue("xziel_hud_pause_y", y); break;
	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_HudEditorSetPosition(xziel_touch_role_t role, float x, float y)",
    editor_set
)

# Global release clears pending mobile-only action states.
release_all = r'''static void Xziel_ReleaseAllTouches(void)
{
	int i;
	for (i = 0; i < XZIEL_MAX_TOUCHES; ++i) {
		if (!xziel_touches[i].active)
			continue;
		if (!xziel_touches[i].editor_drag)
			Xziel_ActionUp(xziel_touches[i].role);
		xziel_touches[i].active = false;
	}
	xziel_mobile_move_active = false;
	xziel_mobile_move_x = 0.0f;
	xziel_mobile_move_y = 0.0f;
	xziel_mobile_sprint_zone_hot = false;
	xziel_mobile_sprint_suppressed = false;
	xziel_mobile_sprint_active = false;
	xziel_mobile_sprint_retry_ms = 0;

	if (xziel_attack_command_down) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
	}
	if (xziel_auto_knife_down) {
		Cbuf_AddText("-knife\n");
		xziel_auto_knife_down = false;
	}
	xziel_mobile_grenade_pressed = false;
	xziel_attack_refs = 0;
	if (xziel_aim_refs > 0)
		Cbuf_AddText("-aim\n");
	xziel_aim_refs = 0;

	xziel_adsfire_attack_engaged = false;
	xziel_adsfire_release_pending = false;
	xziel_adsfire_release_requested = false;
	xziel_adsfire_temp_aim = false;
	xziel_adsfire_ads_seen = false;
	xziel_adsfire_cancelled = false;
	xziel_mobile_restore_ads_after_reload = false;
	xziel_mobile_reload_animation_seen = false;
	xziel_menu_touch_active = false;
	xziel_menu_touch_state = -1;
	Cbuf_Execute();
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ReleaseAllTouches(void)",
    release_all
)

sys_sdl.write_text(text, encoding="utf-8")

# ---- HUD rendering + persistent editor -------------------------------------
hud = source / "render" / "r_hud.c"
htext = hud.read_text(encoding="utf-8")

hud_pos_anchor = "extern cvar_t xziel_hud_pause_y;\n"
if "extern cvar_t xziel_hud_grenade_x;" not in htext:
    if hud_pos_anchor not in htext:
        raise SystemExit("Could not find HUD pause extern for grenade")
    htext = htext.replace(
        hud_pos_anchor,
        hud_pos_anchor +
        "extern cvar_t xziel_hud_grenade_x;\n"
        "extern cvar_t xziel_hud_grenade_y;\n"
        "extern qboolean xziel_mobile_grenade_pressed;\n",
        1
    )

# Add grenade button to the latest HUD renderer.
hud_draw_anchor = '\tXziel_DrawTouchButton(xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f, "II", "", false);\n'
if '"NADE"' not in htext:
    if hud_draw_anchor not in htext:
        raise SystemExit("Could not find mobile pause draw line for grenade")
    htext = htext.replace(
        hud_draw_anchor,
        hud_draw_anchor +
        '\tXziel_DrawTouchButton(xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.041f, "NADE", "", xziel_mobile_grenade_pressed);\n',
        1
    )

hud.write_text(htext, encoding="utf-8")

# ---- Menus: clearer wording + grenade editor reset --------------------------
controls = source / "menu" / "menu_controls.c"
mtext = controls.read_text(encoding="utf-8")

# Remove product-name wording from user-visible settings.
mtext = mtext.replace('return "COD STYLE";', 'return "AUTO BY WEAPON";')
mtext = mtext.replace("COD STYLE defaults to release.", "AUTO BY WEAPON defaults to release.")
mtext = mtext.replace("COD STYLE: bolt marksman release; semi-auto marksman press.", "AUTO BY WEAPON: bolt rifles release; semi-auto rifles press.")

# Clearer gyro label in both stock and Mobile pages.
mtext = mtext.replace('"ADS DAMPENING"', '"GYRO ADS SLOWDOWN"')
mtext = mtext.replace(
    '"Reduce Gyroscope sensitivity in ADS."',
    '"Reduce gyro sensitivity while aiming down sights."'
)
mtext = mtext.replace(
    '"Reduce gyroscope sensitivity while ADS."',
    '"Reduce gyro sensitivity while aiming down sights."'
)

reset_anchor = 'Cvar_SetValue("xziel_hud_pause_x", 0.965f); Cvar_SetValue("xziel_hud_pause_y", 0.075f);\n'
if 'Cvar_SetValue("xziel_hud_grenade_x"' not in mtext:
    if reset_anchor not in mtext:
        raise SystemExit("Could not find HUD reset pause line for grenade")
    mtext = mtext.replace(
        reset_anchor,
        reset_anchor +
        '\tCvar_SetValue("xziel_hud_grenade_x", 0.835f); Cvar_SetValue("xziel_hud_grenade_y", 0.300f);\n',
        1
    )

controls.write_text(mtext, encoding="utf-8")

# ---- Android menu label auto-fit -------------------------------------------
helper = source / "menu" / "menu_helper.c"
mhelp = helper.read_text(encoding="utf-8")

draw_button = r'''void Menu_DrawButton (int order, int button_index, char* button_name, char* button_summary, void *on_activate)
{
	int y_factor = 15;
	int x_pos = 140;
	int y_pos = 0;
	float label_scale = vid.scale;

#ifdef __ANDROID__
	/* Keep long setting labels inside the left pane instead of letting them
	   run off-screen. Only shrink when necessary. */
	{
		int max_width = UI_W(134);
		int width = getTextWidth(button_name, label_scale);
		if (width > max_width && width > 0) {
			label_scale *= (float)max_width / (float)width;
			if (label_scale < vid.scale * 0.68f)
				label_scale = vid.scale * 0.68f;
		}
	}
#endif

	if (order < 0) {
		y_pos = big_bar_height + ((order*-1)*y_factor);
		UI_SetAlignment (UI_ANCHOR_LEFT, UI_ANCHOR_BOTTOM);
	} else {
		y_pos = 30 + (order*y_factor);
		UI_SetAlignment (UI_ANCHOR_LEFT, UI_ANCHOR_TOP);
	}

	if (!current_menu.button[button_index].enabled)
		Menu_BuildMenuButtons (button_index, button_name, on_activate);

	current_menu.button[button_index].x = 0;
	current_menu.button[button_index].width = UI_W(141);
	current_menu.button[button_index].height = UI_H(_CHAR_HEIGHT + 8);
	if (order < 0)
		current_menu.button[button_index].y = vid.height - UI_Y(y_pos + _CHAR_HEIGHT + 4);
	else
		current_menu.button[button_index].y = UI_Y(y_pos - 4);

	if (Menu_IsButtonHovered(button_index)) {
		Menu_DrawSelectionBox (x_pos, y_pos);
		Menu_DrawString (x_pos, y_pos, button_name, 255, 0, 0, 255, label_scale, UI_FLIPTEXTPOS);
		UI_SetAlignment (UI_ANCHOR_CENTER, UI_ANCHOR_BOTTOM);
		Menu_DrawStringCentered (0, big_bar_height + 4 - _CHAR_HEIGHT, button_summary, 255, 255, 255, 255);
	} else {
		if (order < 0)
			UI_SetAlignment (UI_ANCHOR_LEFT, UI_ANCHOR_BOTTOM);
		else
			UI_SetAlignment (UI_ANCHOR_LEFT, UI_ANCHOR_TOP);
		Menu_DrawString (x_pos, y_pos, button_name, 255, 255, 255, 255, label_scale, UI_FLIPTEXTPOS);
	}
}'''
mhelp = xziel_replace_c_function(
    mhelp,
    "void Menu_DrawButton (int order, int button_index, char* button_name, char* button_summary, void *on_activate)",
    draw_button
)
helper.write_text(mhelp, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android ADS+FIRE / grenade cook feedback v0.12
# Fixes release-to-fire by holding a real attack state across usercmd frames.
# Adds a tiny 5-second grenade fuse indicator beside the NADE button.
# ---------------------------------------------------------------------------

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

# Real release-shot pulse state. A +attack/-attack pair in the same command
# pump does NOT survive KeyUp() into CL_SendMove; keep +attack alive long enough
# for real movement packets, just like the now-working auto-knife path.
release_state_anchor = "static qboolean xziel_adsfire_ads_seen = false;\n"
release_states = """static qboolean xziel_release_shot_active = false;
static qboolean xziel_release_shot_aimout_pending = false;
static Uint32 xziel_release_shot_release_ms = 0;
"""
if "xziel_release_shot_active" not in text:
    if release_state_anchor not in text:
        raise SystemExit("Could not find ADS-ready state for v0.12 release shot")
    text = text.replace(release_state_anchor, release_state_anchor + release_states, 1)

# Grenade cook state is shared with the HUD. The native frag fuse is exactly
# 5 seconds (W_Grenade sets self.grenade_delay = time + 5).
grenade_state_anchor = "qboolean xziel_mobile_grenade_pressed = false;\n"
grenade_states = """qboolean xziel_mobile_grenade_cooking = false;
float xziel_mobile_grenade_seconds_left = 0.0f;
static qboolean xziel_mobile_grenade_pending = false;
static Uint32 xziel_mobile_grenade_press_ms = 0;
static int xziel_mobile_grenade_count_before = 0;
"""
if "xziel_mobile_grenade_cooking" not in text:
    if grenade_state_anchor not in text:
        raise SystemExit("Could not find grenade pressed state for cook timer")
    text = text.replace(grenade_state_anchor, grenade_state_anchor + grenade_states, 1)

pulse_func = r'''static void Xziel_PulseAttackNow(void)
{
	if (xziel_release_shot_active)
		return;

	/* Keep native FIRE down across actual CL_SendMove packets. 90 ms is short
	   enough to remain a single trigger pull, but long enough to survive
	   typical 60/90/120 Hz frame pacing. */
	Xziel_SetAttackRef(true);
	xziel_release_shot_active = true;
	xziel_release_shot_aimout_pending = true;
	xziel_release_shot_release_ms = SDL_GetTicks() + 90;
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_PulseAttackNow(void)\n{",
    pulse_func
)

update_fire = r'''static void Xziel_UpdateMobileFire(void)
{
	Uint32 now = SDL_GetTicks();
	qboolean changed = false;

	/* Finish a release-to-fire pulse only after it has lived across real input
	   frames. Keep temporary ADS held until after FIRE is released so the
	   server receives ADS + FIRE together for the shot. */
	if (xziel_release_shot_active && now >= xziel_release_shot_release_ms) {
		Xziel_SetAttackRef(false);
		xziel_release_shot_active = false;
		if (xziel_release_shot_aimout_pending) {
			xziel_release_shot_aimout_pending = false;
			Xziel_FinishTemporaryAdsFireAim();
		}
	}

	if (xziel_mobile_adsfire_pressed &&
		!xziel_adsfire_cancelled &&
		Xziel_WeaponCanAdsMobile() &&
		Xziel_AdsReadyForFire())
		xziel_adsfire_ads_seen = true;

	/* PRESS behavior is universal: ADS-capable weapons establish native ADS
	   first, then use the exact same trigger path as the normal FIRE button.
	   No-ADS weapons simply become FIRE immediately. */
	if ((xziel_mobile_adsfire_pressed || xziel_adsfire_release_requested) &&
		!xziel_adsfire_cancelled &&
		!xziel_release_shot_active) {
		if (!xziel_adsfire_release_pending &&
			!xziel_adsfire_attack_engaged) {
			if (!Xziel_WeaponCanAdsMobile() || Xziel_AdsReadyForFire()) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
	}

	if (xziel_attack_refs <= 0) {
		if (xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
			changed = true;
		}
		if (changed)
			Cbuf_Execute();
		return;
	}

	/* Pistols use native semi-auto edges while the mobile trigger is held.
	   Automatic weapons simply keep +attack down; native weapon fire_delay
	   remains authoritative in every case. */
	if (!Xziel_IsAutoTapPistol())
		return;

	if (xziel_attack_command_down && now >= xziel_attack_release_ms) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
		changed = true;
	}
	if (!xziel_attack_command_down && now >= xziel_attack_next_ms) {
		Cbuf_AddText("+attack\n");
		xziel_attack_command_down = true;
		xziel_attack_release_ms = now + 42;
		xziel_attack_next_ms =
			now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);
		changed = true;
	}
	if (changed)
		Cbuf_Execute();
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_UpdateMobileFire(void)",
    update_fire
)

# Release mode now delays aim-out until the actual held FIRE pulse completes.
action_up = r'''static void Xziel_ActionUp(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = false;
		Xziel_SetAttackRef(false);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = false;

		if (xziel_adsfire_release_pending && !xziel_adsfire_cancelled) {
			if (!Xziel_WeaponCanAdsMobile() ||
				xziel_adsfire_ads_seen ||
				Xziel_AdsReadyForFire()) {
				/* Do NOT aim out here. Xziel_UpdateMobileFire releases FIRE
				   after 90 ms, then releases temporary ADS. */
				Xziel_PulseAttackNow();
			} else {
				/* Early release before native ADS became ready = cancel. */
				Xziel_FinishTemporaryAdsFireAim();
			}
			xziel_adsfire_release_pending = false;
			xziel_adsfire_release_requested = false;
		} else {
			if (xziel_adsfire_attack_engaged) {
				Xziel_SetAttackRef(false);
				xziel_adsfire_attack_engaged = false;
			}
			if (!xziel_release_shot_active)
				Xziel_FinishTemporaryAdsFireAim();
			xziel_adsfire_release_pending = false;
			xziel_adsfire_release_requested = false;
		}

		xziel_adsfire_ads_seen = false;
		xziel_adsfire_cancelled = false;
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = false;
		if (xziel_mobile_ads_toggle.value < 0.5f) {
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = false;
		Cbuf_AddText("-reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = false;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("-use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = false;
		Cbuf_AddText("-jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = false;
		Cbuf_AddText("-knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_GRENADE:
		xziel_mobile_grenade_pressed = false;
		xziel_mobile_grenade_pending = false;
		xziel_mobile_grenade_cooking = false;
		xziel_mobile_grenade_seconds_left = 0.0f;
		Cbuf_AddText("-grenade\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = false;
		Cbuf_AddText("-switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionUp(xziel_touch_role_t role)",
    action_up
)

# Start grenade cook tracking only when the button is actually pressed.
action_down = r'''static void Xziel_ActionDown(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = true;
		Xziel_StopSprintForAction();
		Xziel_SetAttackRef(true);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		xziel_adsfire_cancelled = false;
		xziel_adsfire_attack_engaged = false;
		xziel_adsfire_release_requested = false;
		xziel_adsfire_release_pending = Xziel_AdsFireReleaseWeapon();
		xziel_adsfire_temp_aim = false;
		xziel_adsfire_ads_seen = false;

		Xziel_StopSprintForAction();

		if (Xziel_WeaponCanAdsMobile()) {
			if (!xziel_mobile_ads_latched) {
				Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
				xziel_adsfire_temp_aim = true;
				Cbuf_Execute();
			}

			if (Xziel_AdsReadyForFire())
				xziel_adsfire_ads_seen = true;

			if (!xziel_adsfire_release_pending &&
				(xziel_mobile_ads_latched || Xziel_AdsReadyForFire())) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		} else {
			if (!xziel_adsfire_release_pending) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;
		Xziel_StopSprintForAction();
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			xziel_mobile_ads_latched = !xziel_mobile_ads_latched;
			Cbuf_AddText("impulse 26\n");
		} else {
			xziel_mobile_ads_latched = false;
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		}
		Cbuf_Execute();
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		xziel_mobile_restore_ads_after_reload =
			(xziel_mobile_ads_toggle.value >= 0.5f && xziel_mobile_ads_latched);
		xziel_mobile_reload_animation_seen = false;
		xziel_mobile_reload_start_frame = cl.stats[STAT_WEAPONFRAME];
		Cbuf_AddText("+reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("+use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = true;
		Cbuf_AddText("+jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = true;
		Xziel_StopSprintForAction();
		Cbuf_AddText("+knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_GRENADE:
		xziel_mobile_grenade_pressed = true;
		xziel_mobile_grenade_pending = true;
		xziel_mobile_grenade_cooking = false;
		xziel_mobile_grenade_seconds_left = 5.0f;
		xziel_mobile_grenade_press_ms = SDL_GetTicks();
		xziel_mobile_grenade_count_before =
			(sv_player && sv.active) ? (int)sv_player->v.primary_grenades :
			(int)cl.stats[STAT_GRENADES];
		Xziel_StopSprintForAction();
		Cbuf_AddText("+grenade\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		if (xziel_adsfire_release_pending || xziel_adsfire_release_requested)
			Xziel_CancelAdsFireForSprint();
		Cbuf_AddText("+switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		Menu_Pause_Set();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionDown(xziel_touch_role_t role)",
    action_down
)

# Grenade cook updater: confirm that native W_Grenade actually consumed a frag
# before showing the timer. This avoids fake countdowns when grenade use is
# rejected (no grenades, ADS, animation lock, etc.).
grenade_update = r'''
static void Xziel_UpdateGrenadeCook(void)
{
	Uint32 now = SDL_GetTicks();
	int current_count;

	if (!xziel_mobile_grenade_pressed) {
		xziel_mobile_grenade_pending = false;
		xziel_mobile_grenade_cooking = false;
		xziel_mobile_grenade_seconds_left = 0.0f;
		return;
	}

	current_count = (sv_player && sv.active) ?
		(int)sv_player->v.primary_grenades :
		(int)cl.stats[STAT_GRENADES];

	if (xziel_mobile_grenade_pending) {
		if (current_count < xziel_mobile_grenade_count_before) {
			xziel_mobile_grenade_pending = false;
			xziel_mobile_grenade_cooking = true;
		} else if (now - xziel_mobile_grenade_press_ms > 350) {
			/* Native grenade action never started. */
			xziel_mobile_grenade_pending = false;
			xziel_mobile_grenade_cooking = false;
			xziel_mobile_grenade_seconds_left = 0.0f;
			return;
		}
	}

	if (xziel_mobile_grenade_cooking) {
		float elapsed = (float)(now - xziel_mobile_grenade_press_ms) / 1000.0f;
		xziel_mobile_grenade_seconds_left = 5.0f - elapsed;
		if (xziel_mobile_grenade_seconds_left < 0.0f)
			xziel_mobile_grenade_seconds_left = 0.0f;
	}
}
'''
if "static void Xziel_UpdateGrenadeCook(void)" not in text:
    anchor = "static void Xziel_UpdateAutoKnife(void)\n"
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find auto knife updater for grenade cook insertion")
    text = text[:idx] + grenade_update + "\n" + text[idx:]

pump_anchor = """	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
	Xziel_UpdateAutoKnife();
	Xziel_UpdateReloadAdsRestore();
"""
pump_repl = """	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
	Xziel_UpdateAutoKnife();
	Xziel_UpdateGrenadeCook();
	Xziel_UpdateReloadAdsRestore();
"""
if "Xziel_UpdateGrenadeCook();" not in text:
    if pump_anchor not in text:
        raise SystemExit("Could not find v0.12 mobile updater pump")
    text = text.replace(pump_anchor, pump_repl, 1)

# Cancellation/reset covers any in-flight release shot and grenade timer.
release_all = r'''static void Xziel_ReleaseAllTouches(void)
{
	int i;
	for (i = 0; i < XZIEL_MAX_TOUCHES; ++i) {
		if (!xziel_touches[i].active)
			continue;
		if (!xziel_touches[i].editor_drag)
			Xziel_ActionUp(xziel_touches[i].role);
		xziel_touches[i].active = false;
	}
	xziel_mobile_move_active = false;
	xziel_mobile_move_x = 0.0f;
	xziel_mobile_move_y = 0.0f;
	xziel_mobile_sprint_zone_hot = false;
	xziel_mobile_sprint_suppressed = false;
	xziel_mobile_sprint_active = false;
	xziel_mobile_sprint_retry_ms = 0;

	if (xziel_release_shot_active) {
		Xziel_SetAttackRef(false);
		xziel_release_shot_active = false;
		xziel_release_shot_aimout_pending = false;
	}
	if (xziel_attack_command_down) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
	}
	if (xziel_auto_knife_down) {
		Cbuf_AddText("-knife\n");
		xziel_auto_knife_down = false;
	}

	xziel_mobile_grenade_pressed = false;
	xziel_mobile_grenade_pending = false;
	xziel_mobile_grenade_cooking = false;
	xziel_mobile_grenade_seconds_left = 0.0f;

	xziel_attack_refs = 0;
	if (xziel_aim_refs > 0)
		Cbuf_AddText("-aim\n");
	xziel_aim_refs = 0;

	xziel_adsfire_attack_engaged = false;
	xziel_adsfire_release_pending = false;
	xziel_adsfire_release_requested = false;
	xziel_adsfire_temp_aim = false;
	xziel_adsfire_ads_seen = false;
	xziel_adsfire_cancelled = false;
	xziel_mobile_restore_ads_after_reload = false;
	xziel_mobile_reload_animation_seen = false;
	xziel_menu_touch_active = false;
	xziel_menu_touch_state = -1;
	Cbuf_Execute();
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ReleaseAllTouches(void)",
    release_all
)

sys_sdl.write_text(text, encoding="utf-8")

# ---- HUD: compact cook timer beside NADE, only while held ------------------
hud = source / "render" / "r_hud.c"
htext = hud.read_text(encoding="utf-8")

grenade_hud_extern_anchor = "extern qboolean xziel_mobile_grenade_pressed;\n"
grenade_hud_externs = """extern qboolean xziel_mobile_grenade_cooking;
extern float xziel_mobile_grenade_seconds_left;
"""
if "extern qboolean xziel_mobile_grenade_cooking;" not in htext:
    if grenade_hud_extern_anchor not in htext:
        raise SystemExit("Could not find grenade HUD extern state")
    htext = htext.replace(
        grenade_hud_extern_anchor,
        grenade_hud_extern_anchor + grenade_hud_externs,
        1
    )

fuse_helper = r'''
static void Xziel_DrawGrenadeFuseIndicator(void)
{
	char timer_text[16];
	int cx, cy, w, bar_w, fill_w;
	float left, fraction;
	int r = 255, g = 255, b = 255;

	if (!xziel_mobile_grenade_cooking || !xziel_mobile_grenade_pressed)
		return;

	left = xziel_mobile_grenade_seconds_left;
	if (left < 0.0f) left = 0.0f;
	if (left > 5.0f) left = 5.0f;
	fraction = left / 5.0f;

	cx = (int)(xziel_hud_grenade_x.value * vid.width);
	cy = (int)(xziel_hud_grenade_y.value * vid.height);
	bar_w = (int)(42.0f * vid.scale * xziel_mobile_hud_scale.value);
	if (bar_w < 24) bar_w = 24;
	fill_w = (int)(bar_w * fraction);

	if (left <= 1.0f) {
		r = 255; g = 70; b = 70;
	} else if (left <= 2.0f) {
		r = 255; g = 210; b = 70;
	}

	snprintf(timer_text, sizeof(timer_text), "%.1f", (double)left);
	w = getTextWidth(timer_text, vid.scale * 0.72f);

	/* Tiny readout + 2px fuse bar directly above NADE. No center-screen UI. */
	Draw_ColoredString(cx - w / 2, cy - (int)(38 * vid.scale),
		timer_text, r, g, b, 235, vid.scale * 0.72f);
	Draw_FillByColor(cx - bar_w / 2, cy - (int)(28 * vid.scale),
		bar_w, (int)fmaxf(2.0f, 2.0f * vid.scale),
		20, 20, 20, 150);
	if (fill_w > 0)
		Draw_FillByColor(cx - bar_w / 2, cy - (int)(28 * vid.scale),
			fill_w, (int)fmaxf(2.0f, 2.0f * vid.scale),
			r, g, b, 220);
}
'''
if "static void Xziel_DrawGrenadeFuseIndicator(void)" not in htext:
    anchor = "static void Xziel_MobileHUD_DrawInternal(qboolean editor)\n"
    idx = htext.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile HUD renderer for fuse helper")
    htext = htext[:idx] + fuse_helper + "\n" + htext[idx:]

# Draw after the grenade button so timer is always readable above it.
nade_draw = '\tXziel_DrawTouchButton(xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.041f, "NADE", "", xziel_mobile_grenade_pressed);\n'
if "Xziel_DrawGrenadeFuseIndicator();" not in htext:
    if nade_draw not in htext:
        raise SystemExit("Could not find NADE draw line for fuse indicator")
    htext = htext.replace(
        nade_draw,
        nade_draw + "\tif (!editor) Xziel_DrawGrenadeFuseIndicator();\n",
        1
    )

hud.write_text(htext, encoding="utf-8")

# ---- Aim & Touch descriptions: explain universal behavior succinctly -------
controls = source / "menu" / "menu_controls.c"
mtext = controls.read_text(encoding="utf-8")
mtext = mtext.replace(
    '"Dedicated ADS button: Hold or Toggle."',
    '"Dedicated ADS control. ADS+FIRE automatically uses each weapon native trigger."'
)
mtext = mtext.replace(
    '"Delay between mobile trigger taps for native semi-auto pistols."',
    '"Repeat-fire speed for semi-auto pistols on FIRE and ADS+FIRE."'
)
controls.write_text(mtext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android CODM-like marksman sticky ADS pass v0.13
# Semi-auto / PRESS-mode marksman rifles remain ADS after a shot so repeated
# ADS+FIRE presses shoot immediately without replaying ADS in/out every shot.
# AUTO BY WEAPON keeps bolt marksman on RELEASE behavior.
# ---------------------------------------------------------------------------

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

sticky_anchor = "static Uint32 xziel_release_shot_release_ms = 0;\n"
if "xziel_marksman_sticky_ads" not in text:
    if sticky_anchor not in text:
        raise SystemExit("Could not find release-shot state for marksman sticky ADS")
    text = text.replace(
        sticky_anchor,
        sticky_anchor + "static qboolean xziel_marksman_sticky_ads = false;\n",
        1
    )

sticky_helpers = r'''
static qboolean Xziel_ShouldKeepMarksmanAds(void)
{
	/* COD Mobile-style marksman behavior: PRESS-mode marksman rifles stay ADS
	   after the shot so the next trigger press fires from the existing sight
	   picture. AUTO BY WEAPON still maps bolt marksman rifles to RELEASE. */
	return Xziel_IsMarksmanMobile() && !Xziel_AdsFireReleaseWeapon();
}

static void Xziel_CommitMarksmanStickyAds(void)
{
	if (!Xziel_ShouldKeepMarksmanAds() ||
		xziel_mobile_ads_latched ||
		!xziel_adsfire_temp_aim)
		return;

	/* The ADS hold that began as a temporary ADS+FIRE hold becomes persistent
	   only once a real shot has actually been engaged. Early-release cancel
	   therefore still works before ADS is ready. */
	xziel_marksman_sticky_ads = true;
	xziel_adsfire_temp_aim = false;
}

static void Xziel_ClearMarksmanStickyAds(void)
{
	if (!xziel_marksman_sticky_ads)
		return;

	Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);
	xziel_marksman_sticky_ads = false;
	Cbuf_Execute();
}
'''
if "static qboolean Xziel_ShouldKeepMarksmanAds(void)" not in text:
    anchor = "static void Xziel_PulseAttackNow(void)\n"
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find release-shot helper insertion point for marksman ADS")
    text = text[:idx] + sticky_helpers + "\n" + text[idx:]

update_fire = r'''static void Xziel_UpdateMobileFire(void)
{
	Uint32 now = SDL_GetTicks();
	qboolean changed = false;

	/* Safety: weapon switches or scripted weapon changes must never leave an
	   orphan marksman ADS hold behind. */
	if (xziel_marksman_sticky_ads && !Xziel_IsMarksmanMobile())
		Xziel_ClearMarksmanStickyAds();

	/* Finish a release-to-fire pulse only after it has lived across real input
	   frames. Keep temporary ADS held until after FIRE is released so the
	   server receives ADS + FIRE together for the shot. */
	if (xziel_release_shot_active && now >= xziel_release_shot_release_ms) {
		Xziel_SetAttackRef(false);
		xziel_release_shot_active = false;
		if (xziel_release_shot_aimout_pending) {
			xziel_release_shot_aimout_pending = false;
			Xziel_FinishTemporaryAdsFireAim();
		}
	}

	if (xziel_mobile_adsfire_pressed &&
		!xziel_adsfire_cancelled &&
		Xziel_WeaponCanAdsMobile() &&
		Xziel_AdsReadyForFire())
		xziel_adsfire_ads_seen = true;

	/* PRESS behavior is universal: ADS-capable weapons establish native ADS
	   first, then use the exact same trigger path as the normal FIRE button. */
	if ((xziel_mobile_adsfire_pressed || xziel_adsfire_release_requested) &&
		!xziel_adsfire_cancelled &&
		!xziel_release_shot_active) {
		if (!xziel_adsfire_release_pending &&
			!xziel_adsfire_attack_engaged) {
			if (!Xziel_WeaponCanAdsMobile() || Xziel_AdsReadyForFire()) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
				Xziel_CommitMarksmanStickyAds();
			}
		}
	}

	if (xziel_attack_refs <= 0) {
		if (xziel_attack_command_down) {
			Cbuf_AddText("-attack\n");
			xziel_attack_command_down = false;
			changed = true;
		}
		if (changed)
			Cbuf_Execute();
		return;
	}

	if (!Xziel_IsAutoTapPistol())
		return;

	if (xziel_attack_command_down && now >= xziel_attack_release_ms) {
		Cbuf_AddText("-attack\n");
		xziel_attack_command_down = false;
		changed = true;
	}
	if (!xziel_attack_command_down && now >= xziel_attack_next_ms) {
		Cbuf_AddText("+attack\n");
		xziel_attack_command_down = true;
		xziel_attack_release_ms = now + 42;
		xziel_attack_next_ms =
			now + (Uint32)fmaxf(120.0f, xziel_mobile_autofire_ms.value);
		changed = true;
	}
	if (changed)
		Cbuf_Execute();
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_UpdateMobileFire(void)",
    update_fire
)

action_down = r'''static void Xziel_ActionDown(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = true;
		Xziel_StopSprintForAction();
		Xziel_SetAttackRef(true);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		xziel_adsfire_cancelled = false;
		xziel_adsfire_attack_engaged = false;
		xziel_adsfire_release_requested = false;
		xziel_adsfire_release_pending = Xziel_AdsFireReleaseWeapon();
		xziel_adsfire_temp_aim = false;
		xziel_adsfire_ads_seen = false;

		Xziel_StopSprintForAction();

		if (Xziel_WeaponCanAdsMobile()) {
			/* A marksman rifle that already committed sticky ADS reuses that
			   native +aim hold. Do not stack another aim reference. */
			if (!xziel_mobile_ads_latched && !xziel_marksman_sticky_ads) {
				Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
				xziel_adsfire_temp_aim = true;
				Cbuf_Execute();
			}

			if (Xziel_AdsReadyForFire())
				xziel_adsfire_ads_seen = true;

			if (!xziel_adsfire_release_pending &&
				(xziel_mobile_ads_latched ||
				 xziel_marksman_sticky_ads ||
				 Xziel_AdsReadyForFire())) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
				Xziel_CommitMarksmanStickyAds();
			}
		} else {
			if (!xziel_adsfire_release_pending) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;

		/* When a marksman is sticky-ADS, the normal ADS button becomes the
		   explicit cancel/unscope control, matching CODM's sticky marksman
		   sight behavior. */
		if (xziel_marksman_sticky_ads) {
			Xziel_ClearMarksmanStickyAds();
			break;
		}

		Xziel_StopSprintForAction();
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			xziel_mobile_ads_latched = !xziel_mobile_ads_latched;
			Cbuf_AddText("impulse 26\n");
		} else {
			xziel_mobile_ads_latched = false;
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		}
		Cbuf_Execute();
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		xziel_mobile_restore_ads_after_reload =
			(xziel_mobile_ads_toggle.value >= 0.5f && xziel_mobile_ads_latched);
		xziel_mobile_reload_animation_seen = false;
		xziel_mobile_reload_start_frame = cl.stats[STAT_WEAPONFRAME];
		Cbuf_AddText("+reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("+use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = true;
		Cbuf_AddText("+jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = true;
		Xziel_StopSprintForAction();
		Cbuf_AddText("+knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_GRENADE:
		/* Native grenade use rejects while zoomed, so explicitly leave sticky
		   marksman ADS before starting the grenade action. */
		Xziel_ClearMarksmanStickyAds();
		xziel_mobile_grenade_pressed = true;
		xziel_mobile_grenade_pending = true;
		xziel_mobile_grenade_cooking = false;
		xziel_mobile_grenade_seconds_left = 5.0f;
		xziel_mobile_grenade_press_ms = SDL_GetTicks();
		xziel_mobile_grenade_count_before =
			(sv_player && sv.active) ? (int)sv_player->v.primary_grenades :
			(int)cl.stats[STAT_GRENADES];
		Xziel_StopSprintForAction();
		Cbuf_AddText("+grenade\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		Xziel_ClearMarksmanStickyAds();
		if (xziel_adsfire_release_pending || xziel_adsfire_release_requested)
			Xziel_CancelAdsFireForSprint();
		Cbuf_AddText("+switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		Menu_Pause_Set();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionDown(xziel_touch_role_t role)",
    action_down
)

# Sprint cancellation must also release marksman sticky ADS.
cancel_ads = r'''static void Xziel_CancelAdsFireForSprint(void)
{
	if (xziel_adsfire_attack_engaged) {
		Xziel_SetAttackRef(false);
		xziel_adsfire_attack_engaged = false;
	}

	xziel_adsfire_release_pending = false;
	xziel_adsfire_release_requested = false;
	xziel_adsfire_ads_seen = false;
	xziel_adsfire_cancelled = true;
	Xziel_FinishTemporaryAdsFireAim();
	Xziel_ClearMarksmanStickyAds();

	if (xziel_mobile_ads_latched) {
		Cbuf_AddText("impulse 26\n");
		Cbuf_Execute();
		xziel_mobile_ads_latched = false;
	}
	xziel_mobile_restore_ads_after_reload = false;
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_CancelAdsFireForSprint(void)",
    cancel_ads
)

# The sprint-zone gate must notice sticky marksman ADS as an ADS state that
# needs cancellation before native sprint can begin.
move_old = """				xziel_adsfire_temp_aim ||
				xziel_mobile_ads_latched)
				Xziel_CancelAdsFireForSprint();"""
move_new = """				xziel_adsfire_temp_aim ||
				xziel_marksman_sticky_ads ||
				xziel_mobile_ads_latched)
				Xziel_CancelAdsFireForSprint();"""
if move_old in text:
    text = text.replace(move_old, move_new, 1)
elif "xziel_marksman_sticky_ads ||\n\t\t\t\txziel_mobile_ads_latched" not in text:
    raise SystemExit("Could not find sprint ADS cancellation gate for marksman sticky ADS")

# Reset sticky state whenever all touch state is force-released.
release_tail = """	xziel_adsfire_temp_aim = false;
	xziel_adsfire_ads_seen = false;
	xziel_adsfire_cancelled = false;"""
release_tail_new = """	xziel_adsfire_temp_aim = false;
	xziel_adsfire_ads_seen = false;
	xziel_marksman_sticky_ads = false;
	xziel_adsfire_cancelled = false;"""
if release_tail in text:
    text = text.replace(release_tail, release_tail_new, 1)
elif "xziel_marksman_sticky_ads = false;" not in text[text.find("static void Xziel_ReleaseAllTouches"):]:
    raise SystemExit("Could not find touch reset tail for marksman sticky ADS")

sys_sdl.write_text(text, encoding="utf-8")

# Menu copy: explain the actual AUTO BY WEAPON marksman behavior.
controls = source / "menu" / "menu_controls.c"
mtext = controls.read_text(encoding="utf-8")
mtext = mtext.replace(
    '"AUTO BY WEAPON: bolt rifles release; semi-auto rifles press."',
    '"AUTO BY WEAPON: semi-auto marksman stay ADS for repeat shots; bolt rifles use release-fire."'
)
mtext = mtext.replace(
    '"AUTO BY WEAPON: bolt marksman release; semi-auto marksman press."',
    '"AUTO BY WEAPON: semi-auto marksman stay ADS for repeat shots; bolt rifles use release-fire."'
)
controls.write_text(mtext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android visible adjustable sprint target + v0.13 compile fix v0.14
# ---------------------------------------------------------------------------

# Fresh installs start with a more deliberate sprint throw. Existing archived
# configs remain user-controlled through the slider.
inp = source / "input.c"
itext = inp.read_text(encoding="utf-8")
itext = itext.replace(
    'cvar_t xziel_mobile_sprint_zone = {"xziel_mobile_sprint_zone", "1.10", true};',
    'cvar_t xziel_mobile_sprint_zone = {"xziel_mobile_sprint_zone", "1.35", true};'
)
inp.write_text(itext, encoding="utf-8")

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

# v0.13 helpers are used by Xziel_UpdateMobileFire before their definitions.
proto_anchor = "static void Xziel_UpdateMobileFire(void)\n"
marksman_protos = """static qboolean Xziel_IsMarksmanMobile(void);
static void Xziel_CommitMarksmanStickyAds(void);
static void Xziel_ClearMarksmanStickyAds(void);

"""
if "static void Xziel_CommitMarksmanStickyAds(void);" not in text:
    idx = text.find(proto_anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile fire updater for v0.14 prototypes")
    text = text[:idx] + marksman_protos + text[idx:]

# Wider deliberate sprint activation range. The native stamina system is not
# touched: this only controls when mobile input requests impulse 23/24.
move_func = r'''static void Xziel_UpdateMove(float x, float y)
{
	float raw_dx, raw_dy, dx, dy, len, radius_x, radius_y;
	float sprint_zone;
	Uint32 now = SDL_GetTicks();

	radius_x = 0.16f * ((float)vid.height / (float)vid.width);
	radius_y = 0.16f;
	raw_dx = (x - xziel_mobile_move_anchor_x) / radius_x;
	raw_dy = (xziel_mobile_move_anchor_y - y) / radius_y;

	dx = raw_dx;
	dy = raw_dy;
	len = sqrtf(dx * dx + dy * dy);

	if (len < 0.10f) {
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
		xziel_mobile_sprint_zone_hot = false;
		if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
			Cbuf_AddText("impulse 24\n");
			Cbuf_Execute();
		}
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_suppressed = false;
		xziel_mobile_sprint_retry_ms = 0;
		return;
	}

	if (len > 1.0f) {
		dx /= len;
		dy /= len;
	}

	xziel_mobile_move_x = dx;
	xziel_mobile_move_y = dy;

	/* This is intentionally beyond the normal joystick circle. Higher values
	   require a farther, deliberate upward drag before sprint is requested. */
	sprint_zone = xziel_mobile_sprint_zone.value;
	if (sprint_zone < 1.10f) sprint_zone = 1.10f;
	if (sprint_zone > 1.85f) sprint_zone = 1.85f;

	xziel_mobile_sprint_zone_hot =
		raw_dy >= sprint_zone &&
		fabsf(raw_dx) <= raw_dy * 0.70f;

	if (xziel_mobile_sprint_zone_hot) {
		if (!xziel_mobile_sprint_suppressed) {
			if (xziel_adsfire_release_pending ||
				xziel_adsfire_release_requested ||
				xziel_adsfire_attack_engaged ||
				xziel_adsfire_temp_aim ||
				xziel_marksman_sticky_ads ||
				xziel_mobile_ads_latched)
				Xziel_CancelAdsFireForSprint();

			/* Native NZ:P still owns stamina, sprint duration and recovery.
			   While the thumb deliberately remains in the sprint target,
			   retry a rejected request so sprint starts once native stamina/
			   weapon rules permit it. */
			if (cl.stats[STAT_ZOOM] != 3 && now >= xziel_mobile_sprint_retry_ms) {
				Cbuf_AddText("impulse 23\n");
				Cbuf_Execute();
				xziel_mobile_sprint_retry_ms = now + 120;
			}
			xziel_mobile_sprint_active = true;
		}
	} else {
		if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
			Cbuf_AddText("impulse 24\n");
			Cbuf_Execute();
		}
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_suppressed = false;
		xziel_mobile_sprint_retry_ms = 0;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_UpdateMove(float x, float y)",
    move_func
)
sys_sdl.write_text(text, encoding="utf-8")

# Sprint icon is now always visible during gameplay, not only after a thumb is
# already touching the joystick. Its vertical position exactly matches the
# activation-height setting.
hud = source / "render" / "r_hud.c"
htext = hud.read_text(encoding="utf-8")

htext = htext.replace(
    "if (sprint_zone < 1.02f) sprint_zone = 1.02f;",
    "if (sprint_zone < 1.10f) sprint_zone = 1.10f;"
)
htext = htext.replace(
    "if (sprint_zone > 1.35f) sprint_zone = 1.35f;",
    "if (sprint_zone > 1.85f) sprint_zone = 1.85f;"
)

old_visible_gate = """	if (editor || xziel_mobile_move_active) {
		qboolean sprint_on = xziel_mobile_sprint_zone_hot || xziel_mobile_sprint_active ||
			cl.stats[STAT_ZOOM] == 3;
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r, 245, 245, 245,
			(int)((sprint_on ? 145 : 70) * xziel_mobile_hud_opacity.value));
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r - (int)(2 * vid.scale),
			sprint_on ? 95 : 8, sprint_on ? 95 : 8, sprint_on ? 20 : 8,
			(int)((sprint_on ? 165 : 100) * xziel_mobile_hud_opacity.value));
		sprint_tw = getTextWidth((char *)sprint_label, vid.scale * 0.70f);
		Draw_ColoredString(sprint_x - sprint_tw / 2, sprint_y - (int)(3 * vid.scale),
			(char *)sprint_label, 255, 255, 255, 235, vid.scale * 0.70f);
	}
"""
new_visible_gate = """	{
		qboolean sprint_on = xziel_mobile_sprint_zone_hot || xziel_mobile_sprint_active ||
			cl.stats[STAT_ZOOM] == 3;
		int outer_alpha = sprint_on ? 190 : (xziel_mobile_move_active ? 135 : 105);
		int inner_alpha = sprint_on ? 205 : (xziel_mobile_move_active ? 150 : 125);

		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r, 245, 245, 245,
			(int)(outer_alpha * xziel_mobile_hud_opacity.value));
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r - (int)(2 * vid.scale),
			sprint_on ? 95 : 8, sprint_on ? 95 : 8, sprint_on ? 20 : 8,
			(int)(inner_alpha * xziel_mobile_hud_opacity.value));
		sprint_tw = getTextWidth((char *)sprint_label, vid.scale * 0.70f);
		Draw_ColoredString(sprint_x - sprint_tw / 2, sprint_y - (int)(3 * vid.scale),
			(char *)sprint_label, 255, 255, 255,
			sprint_on ? 255 : 220, vid.scale * 0.70f);
	}
"""
if old_visible_gate not in htext:
    raise SystemExit("Could not find sprint HUD visibility gate for v0.14")
htext = htext.replace(old_visible_gate, new_visible_gate, 1)
hud.write_text(htext, encoding="utf-8")

# Clearer mobile setting and much wider adjustable height.
controls = source / "menu" / "menu_controls.c"
mtext = controls.read_text(encoding="utf-8")
mtext = mtext.replace(
    '"SPRINT LOCK ZONE", "Drag the joystick into the icon above it to request native sprint."',
    '"SPRINT ACTIVATION HEIGHT", "Higher = drag farther above the joystick before native sprint starts."'
)
mtext = mtext.replace(
    'Menu_DrawOptionSlider(row-1, idx-1, 1.02f, 1.35f, xziel_mobile_sprint_zone, "xziel_mobile_sprint_zone", false, true, 0.01f);',
    'Menu_DrawOptionSlider(row-1, idx-1, 1.10f, 1.85f, xziel_mobile_sprint_zone, "xziel_mobile_sprint_zone", false, true, 0.05f);'
)
controls.write_text(mtext, encoding="utf-8")


# ---------------------------------------------------------------------------
# v0.14.1 sprint icon visibility correction
# Keep the existing UX: sprint target appears only while the joystick is held.
# Retain the wider adjustable activation-height range from v0.14.
# ---------------------------------------------------------------------------
hud = source / "render" / "r_hud.c"
htext = hud.read_text(encoding="utf-8")

always_visible = """	{
		qboolean sprint_on = xziel_mobile_sprint_zone_hot || xziel_mobile_sprint_active ||
			cl.stats[STAT_ZOOM] == 3;
		int outer_alpha = sprint_on ? 190 : (xziel_mobile_move_active ? 135 : 105);
		int inner_alpha = sprint_on ? 205 : (xziel_mobile_move_active ? 150 : 125);

		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r, 245, 245, 245,
			(int)(outer_alpha * xziel_mobile_hud_opacity.value));
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r - (int)(2 * vid.scale),
			sprint_on ? 95 : 8, sprint_on ? 95 : 8, sprint_on ? 20 : 8,
			(int)(inner_alpha * xziel_mobile_hud_opacity.value));
		sprint_tw = getTextWidth((char *)sprint_label, vid.scale * 0.70f);
		Draw_ColoredString(sprint_x - sprint_tw / 2, sprint_y - (int)(3 * vid.scale),
			(char *)sprint_label, 255, 255, 255,
			sprint_on ? 255 : 220, vid.scale * 0.70f);
	}
"""

held_only = """	if (editor || xziel_mobile_move_active) {
		qboolean sprint_on = xziel_mobile_sprint_zone_hot || xziel_mobile_sprint_active ||
			cl.stats[STAT_ZOOM] == 3;
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r, 245, 245, 245,
			(int)((sprint_on ? 145 : 70) * xziel_mobile_hud_opacity.value));
		Xziel_DrawDisc(sprint_x, sprint_y, sprint_r - (int)(2 * vid.scale),
			sprint_on ? 95 : 8, sprint_on ? 95 : 8, sprint_on ? 20 : 8,
			(int)((sprint_on ? 165 : 100) * xziel_mobile_hud_opacity.value));
		sprint_tw = getTextWidth((char *)sprint_label, vid.scale * 0.70f);
		Draw_ColoredString(sprint_x - sprint_tw / 2, sprint_y - (int)(3 * vid.scale),
			(char *)sprint_label, 255, 255, 255, 235, vid.scale * 0.70f);
	}
"""

if always_visible in htext:
    htext = htext.replace(always_visible, held_only, 1)
elif held_only not in htext:
    raise SystemExit("Could not find v0.14 sprint icon visibility block")

hud.write_text(htext, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android universal sprint-cancels-ADS pass v0.15
# Sprint activation always exits every mobile/native ADS path before requesting
# native sprint. Stamina/sprint duration/recovery remain fully native.
# ---------------------------------------------------------------------------
sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

force_ads_helper = r'''
static void Xziel_ForceExitAdsForSprint(void)
{
	qboolean had_hold_aim =
		xziel_aim_refs > 0 ||
		xziel_adsfire_temp_aim ||
		xziel_marksman_sticky_ads;

	/* Sprint cancels any prepared/active ADS+FIRE shot rather than allowing
	   a delayed shot to escape after the player has committed to running. */
	if (xziel_adsfire_attack_engaged) {
		Xziel_SetAttackRef(false);
		xziel_adsfire_attack_engaged = false;
	}
	if (xziel_release_shot_active) {
		Xziel_SetAttackRef(false);
		xziel_release_shot_active = false;
		xziel_release_shot_aimout_pending = false;
	}

	xziel_adsfire_release_pending = false;
	xziel_adsfire_release_requested = false;
	xziel_adsfire_ads_seen = false;
	xziel_adsfire_cancelled = true;
	xziel_mobile_restore_ads_after_reload = false;
	xziel_mobile_reload_animation_seen = false;

	/* Temporary ADS+FIRE and sticky marksman ADS both own +aim references. */
	Xziel_FinishTemporaryAdsFireAim();
	Xziel_ClearMarksmanStickyAds();

	/* Dedicated HOLD ADS may own an additional +aim reference. Release every
	   remaining mobile aim reference so holding ADS cannot block sprint. */
	while (xziel_aim_refs > 0)
		Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, false);

	/* Dedicated TOGGLE ADS is not reference-counted; toggle it out explicitly.
	   If the engine is ADS for some residual path that mobile state no longer
	   owns, use the same native impulse as a final fallback. */
	if (xziel_mobile_ads_latched) {
		Cbuf_AddText("impulse 26\n");
		xziel_mobile_ads_latched = false;
	} else if (!had_hold_aim &&
		(cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)) {
		Cbuf_AddText("impulse 26\n");
	}

	/* A finger may still physically be resting on ADS; the existing touch slot
	   can release later without re-arming because refs/latch are already zero. */
	xziel_mobile_ads_pressed = false;
	Cbuf_Execute();
}
'''

if "static void Xziel_ForceExitAdsForSprint(void)" not in text:
    anchor = "static void Xziel_CancelAdsFireForSprint(void)\n"
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find sprint ADS cancellation helper anchor")
    text = text[:idx] + force_ads_helper + "\n" + text[idx:]

move_func = r'''static void Xziel_UpdateMove(float x, float y)
{
	float raw_dx, raw_dy, dx, dy, len, radius_x, radius_y;
	float sprint_zone;
	Uint32 now = SDL_GetTicks();

	radius_x = 0.16f * ((float)vid.height / (float)vid.width);
	radius_y = 0.16f;
	raw_dx = (x - xziel_mobile_move_anchor_x) / radius_x;
	raw_dy = (xziel_mobile_move_anchor_y - y) / radius_y;

	dx = raw_dx;
	dy = raw_dy;
	len = sqrtf(dx * dx + dy * dy);

	if (len < 0.10f) {
		xziel_mobile_move_x = 0.0f;
		xziel_mobile_move_y = 0.0f;
		xziel_mobile_sprint_zone_hot = false;
		if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
			Cbuf_AddText("impulse 24\n");
			Cbuf_Execute();
		}
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_suppressed = false;
		xziel_mobile_sprint_retry_ms = 0;
		return;
	}

	if (len > 1.0f) {
		dx /= len;
		dy /= len;
	}

	xziel_mobile_move_x = dx;
	xziel_mobile_move_y = dy;

	sprint_zone = xziel_mobile_sprint_zone.value;
	if (sprint_zone < 1.10f) sprint_zone = 1.10f;
	if (sprint_zone > 1.85f) sprint_zone = 1.85f;

	xziel_mobile_sprint_zone_hot =
		raw_dy >= sprint_zone &&
		fabsf(raw_dx) <= raw_dy * 0.70f;

	if (xziel_mobile_sprint_zone_hot) {
		if (!xziel_mobile_sprint_suppressed) {
			/* Universal mobile rule: committing the movement thumb to the
			   sprint target always exits ADS first, regardless of weapon class
			   or whether ADS came from Hold, Toggle, ADS+FIRE, sticky marksman,
			   sniper scope, or a residual native zoom state. */
			if (cl.stats[STAT_ZOOM] == 1 ||
				cl.stats[STAT_ZOOM] == 2 ||
				xziel_aim_refs > 0 ||
				xziel_adsfire_release_pending ||
				xziel_adsfire_release_requested ||
				xziel_adsfire_attack_engaged ||
				xziel_adsfire_temp_aim ||
				xziel_release_shot_active ||
				xziel_marksman_sticky_ads ||
				xziel_mobile_ads_latched) {
				Xziel_ForceExitAdsForSprint();
			}

			/* Native NZ:P remains authoritative for stamina and whether sprint
			   is currently allowed. Retry only while the thumb deliberately
			   stays inside the configured sprint target. */
			if (cl.stats[STAT_ZOOM] != 3 && now >= xziel_mobile_sprint_retry_ms) {
				Cbuf_AddText("impulse 23\n");
				Cbuf_Execute();
				xziel_mobile_sprint_retry_ms = now + 120;
			}
			xziel_mobile_sprint_active = true;
		}
	} else {
		if (xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3) {
			Cbuf_AddText("impulse 24\n");
			Cbuf_Execute();
		}
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_suppressed = false;
		xziel_mobile_sprint_retry_ms = 0;
	}
}'''

text = xziel_replace_c_function(
    text,
    "static void Xziel_UpdateMove(float x, float y)",
    move_func
)

sys_sdl.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Xziel Android input/menu/quit polish v0.16
# - grenade drag-look
# - first tap select / second tap confirm
# - stronger text auto-fit
# - Android finishAndRemoveTask on Quit Game
# - ADS+FIRE waits for visual ADS completion before firing
# ---------------------------------------------------------------------------

sys_sdl = source / "platform" / "sdl" / "sys_sdl.c"
text = sys_sdl.read_text(encoding="utf-8")

# JNI is only needed for Android task shutdown.
if "#include <jni.h>" not in text:
    include_anchor = "#include <unistd.h>\n"
    if include_anchor not in text:
        raise SystemExit("Could not find sys_sdl include anchor for JNI")
    text = text.replace(
        include_anchor,
        include_anchor + "#ifdef __ANDROID__\n#include <jni.h>\n#endif\n",
        1
    )

# Fully finish/remove the Android Activity task when native Quit Game executes.
sys_quit = r'''void Sys_Quit(void)
{
#ifdef __ANDROID__
	JNIEnv *env = (JNIEnv *)SDL_AndroidGetJNIEnv();
	jobject activity = (jobject)SDL_AndroidGetActivity();

	if (env && activity) {
		jclass cls = (*env)->GetObjectClass(env, activity);
		if (cls) {
			jmethodID method = (*env)->GetMethodID(env, cls,
				"requestFullExitFromNative", "()V");
			if (method)
				(*env)->CallVoidMethod(env, activity, method);
			if ((*env)->ExceptionCheck(env))
				(*env)->ExceptionClear(env);
			(*env)->DeleteLocalRef(env, cls);
		}
		(*env)->DeleteLocalRef(env, activity);
	}
#endif
	sdl_running = false;
}'''
text = xziel_replace_c_function(text, "void Sys_Quit(void)", sys_quit)

# ADS+FIRE timing state. NZ:P sets zoom=1 at the START of aim-in while the
# viewmodel is still interpolating. Gate mobile firing until the visible aim-in
# is effectively complete instead of treating zoom=1 as instant readiness.
ads_state_anchor = "static qboolean xziel_adsfire_ads_seen = false;\n"
if "xziel_adsfire_visual_ready_ms" not in text:
    if ads_state_anchor not in text:
        raise SystemExit("Could not find ADS state anchor for visual-ready timing")
    text = text.replace(
        ads_state_anchor,
        ads_state_anchor + "static Uint32 xziel_adsfire_visual_ready_ms = 0;\n",
        1
    )

menu_state_anchor = "static int xziel_menu_touch_state = -1;\n"
menu_states = """static int xziel_menu_confirm_state = -1;
static int xziel_menu_confirm_row = -1;
"""
if "xziel_menu_confirm_state" not in text:
    if menu_state_anchor not in text:
        raise SystemExit("Could not find menu touch state anchor")
    text = text.replace(menu_state_anchor, menu_state_anchor + menu_states, 1)

timing_helpers = r'''
static Uint32 Xziel_AdsVisualDelayMs(void)
{
	/* Scoped NZ:P weapons already define a native 0.2 s scope-in timer.
	   Ordinary ADS viewmodel interpolation uses 16*frametime smoothing; ~180
	   ms is about 96% visually settled at common 60-120 Hz frame rates. */
	if (Xziel_IsSniperMobile())
		return 200;
	return 180;
}

static qboolean Xziel_AdsVisualReady(void)
{
	Uint32 now = SDL_GetTicks();

	if (!Xziel_WeaponCanAdsMobile())
		return true;

	if (now < xziel_adsfire_visual_ready_ms)
		return false;

	if (Xziel_IsSniperMobile())
		return cl.stats[STAT_ZOOM] == 2;

	return cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2;
}
'''
if "static Uint32 Xziel_AdsVisualDelayMs(void)" not in text:
    anchor = "static qboolean Xziel_AdsReadyForFire(void)\n{"
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find ADS-ready helper for visual timing")
    text = text[:idx] + timing_helpers + "\n" + text[idx:]

# Keep legacy helper name but make it respect visual aim-in completion.
proto_anchor = "static void Xziel_UpdateMobileFire(void)\n"
visual_protos = """static Uint32 Xziel_AdsVisualDelayMs(void);
static qboolean Xziel_AdsVisualReady(void);

"""
if visual_protos not in text:
    idx = text.find(proto_anchor)
    if idx < 0:
        raise SystemExit("Could not find mobile fire prototype anchor for visual ADS helpers")
    text = text[:idx] + visual_protos + text[idx:]

ads_ready = r'''static qboolean Xziel_AdsReadyForFire(void)
{
	return Xziel_AdsVisualReady();
}'''
text = xziel_replace_c_function(
    text,
    "static qboolean Xziel_AdsReadyForFire(void)\n{",
    ads_ready
)

# Grenade finger can drag-look exactly like FIRE / ADS+FIRE / ADS.
finger_motion = r'''static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;

	slot = Xziel_FindTouch(finger->fingerId);
	if (slot && slot->editor_drag) {
		Xziel_HudEditorSetPosition(slot->role, finger->x, finger->y);
		slot->last_x = finger->x;
		slot->last_y = finger->y;
		return;
	}

	if (key_dest == key_menu || key_dest == key_menu_pause) {
		if (!xziel_menu_touch_active ||
			xziel_menu_touch_finger != finger->fingerId ||
			xziel_menu_touch_state != m_state)
			return;
		Xziel_MenuFinger(finger->x, finger->y, false, true);
		return;
	}

	slot = Xziel_FindTouch(finger->fingerId);
	if (!slot)
		return;

	if (slot->role == XZ_TOUCH_MOVE) {
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (slot->role == XZ_TOUCH_LOOK ||
		slot->role == XZ_TOUCH_FIRE ||
		slot->role == XZ_TOUCH_ADSFIRE ||
		slot->role == XZ_TOUCH_ADS ||
		slot->role == XZ_TOUCH_GRENADE) {
		float look_scale = xziel_mobile_touch_sensitivity.value;
		if (cl.stats[STAT_ZOOM] == 1 || cl.stats[STAT_ZOOM] == 2)
			look_scale *= xziel_mobile_ads_sensitivity.value;
		mouse_dx += (int)((finger->x - slot->last_x) * (float)vid.width * look_scale);
		mouse_dy += (int)((finger->y - slot->last_y) * (float)vid.height * look_scale);
	}
	slot->last_x = finger->x;
	slot->last_y = finger->y;
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)",
    finger_motion
)

# More robust hit test for two-tap menu confirmation.
menu_helpers = r'''
static int Xziel_MenuButtonAtPoint(int mx, int my)
{
	int i;
	for (i = 0; i < MAX_MENU_BUTTONS; ++i) {
		menu_button_t *button = &current_menu.button[i];
		if (!button->enabled)
			continue;
		if (mx >= button->x && mx < button->x + button->width &&
			my >= button->y && my < button->y + button->height)
			return i;
	}
	return -1;
}

static qboolean Xziel_MenuTapConfirms(int row)
{
	if (row < 0)
		return false;

	if (xziel_menu_confirm_state == m_state &&
		xziel_menu_confirm_row == row) {
		xziel_menu_confirm_state = -1;
		xziel_menu_confirm_row = -1;
		return true;
	}

	xziel_menu_confirm_state = m_state;
	xziel_menu_confirm_row = row;
	Xziel_MenuSetCursor(row);
	return false;
}
'''
if "static int Xziel_MenuButtonAtPoint(int mx, int my)" not in text:
    anchor = "static void Xziel_MenuSetCursor(int row)\n"
    idx = text.find(anchor)
    if idx < 0:
        raise SystemExit("Could not find menu cursor helper for two-tap insertion")
    # Insert after the full function body.
    brace = text.find("{", idx)
    depth = 0
    end = -1
    for j in range(brace, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end < 0:
        raise SystemExit("Could not find MenuSetCursor function end")
    text = text[:end] + "\n\n" + menu_helpers + text[end:]

menu_finger = r'''static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)
{
	int mx = (int)(x * (float)vid.width);
	int my = (int)(y * (float)vid.height);
	int divider_x = UI_X(150);
	qboolean slider_handled = false;

	if (Xziel_IsSplitSettingsMenu()) {
		int row = Xziel_MenuRowAtY(my);

		/* LEFT pane = select/navigate. First tap selects, second tap on the
		   same row confirms navigation. RIGHT pane = edit setting directly. */
		if (mx < divider_x) {
			if (down && row >= 0) {
				if (Xziel_MenuTapConfirms(row) &&
					Xziel_LeftSideIsNavigation(current_menu.button[row].name))
					Menu_ButtonPress();
			}
			return;
		}

		if (down && row >= 0) {
			xziel_menu_confirm_state = -1;
			xziel_menu_confirm_row = -1;
			Xziel_MenuSetCursor(row);
			slider_handled = Menu_MouseButton(mx, my, true);
			if (!slider_handled)
				Menu_ButtonPress();
			return;
		}

		if (motion) {
			Menu_MouseMove(mx, my);
			return;
		}

		Menu_MouseButton(mx, my, false);
		return;
	}

	/* Non-settings menus: first tap only selects. A second tap on the same
	   actual button confirms/opens it. This prevents accidental one-touch
	   traversal through parent + child menus. */
	if (motion) {
		Menu_MouseMove(mx, my);
		return;
	}

	if (down) {
		int row = Xziel_MenuButtonAtPoint(mx, my);
		if (row >= 0) {
			if (Xziel_MenuTapConfirms(row))
				Menu_ButtonPress();
		}
		return;
	}

	Menu_MouseButton(mx, my, false);
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)",
    menu_finger
)

# ADS+FIRE starts a visual-ready deadline whenever it begins a fresh aim-in.
action_down = r'''static void Xziel_ActionDown(xziel_touch_role_t role)
{
	switch (role) {
	case XZ_TOUCH_FIRE:
		xziel_mobile_fire_pressed = true;
		Xziel_StopSprintForAction();
		Xziel_SetAttackRef(true);
		break;

	case XZ_TOUCH_ADSFIRE:
		xziel_mobile_adsfire_pressed = true;
		xziel_adsfire_cancelled = false;
		xziel_adsfire_attack_engaged = false;
		xziel_adsfire_release_requested = false;
		xziel_adsfire_release_pending = Xziel_AdsFireReleaseWeapon();
		xziel_adsfire_temp_aim = false;
		xziel_adsfire_ads_seen = false;

		Xziel_StopSprintForAction();

		if (Xziel_WeaponCanAdsMobile()) {
			if (xziel_mobile_ads_latched || xziel_marksman_sticky_ads) {
				/* Already visually ADS: next shot can use the sight picture
				   immediately, especially semi-auto marksman repeat fire. */
				xziel_adsfire_visual_ready_ms = SDL_GetTicks();
			} else {
				xziel_adsfire_visual_ready_ms =
					SDL_GetTicks() + Xziel_AdsVisualDelayMs();
				Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
				xziel_adsfire_temp_aim = true;
				Cbuf_Execute();
			}

			if (Xziel_AdsReadyForFire())
				xziel_adsfire_ads_seen = true;

			if (!xziel_adsfire_release_pending &&
				Xziel_AdsReadyForFire()) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
				Xziel_CommitMarksmanStickyAds();
			}
		} else {
			xziel_adsfire_visual_ready_ms = SDL_GetTicks();
			if (!xziel_adsfire_release_pending) {
				Xziel_SetAttackRef(true);
				xziel_adsfire_attack_engaged = true;
			}
		}
		break;

	case XZ_TOUCH_ADS:
		xziel_mobile_ads_pressed = true;
		xziel_mobile_restore_ads_after_reload = false;
		xziel_mobile_reload_animation_seen = false;

		if (xziel_marksman_sticky_ads) {
			Xziel_ClearMarksmanStickyAds();
			break;
		}

		Xziel_StopSprintForAction();
		if (xziel_mobile_ads_toggle.value >= 0.5f) {
			xziel_mobile_ads_latched = !xziel_mobile_ads_latched;
			Cbuf_AddText("impulse 26\n");
		} else {
			xziel_mobile_ads_latched = false;
			Xziel_QueueHold("+aim\n", "-aim\n", &xziel_aim_refs, true);
		}
		Cbuf_Execute();
		break;

	case XZ_TOUCH_RELOAD:
		xziel_mobile_reload_pressed = true;
		xziel_mobile_restore_ads_after_reload =
			(xziel_mobile_ads_toggle.value >= 0.5f && xziel_mobile_ads_latched);
		xziel_mobile_reload_animation_seen = false;
		xziel_mobile_reload_start_frame = cl.stats[STAT_WEAPONFRAME];
		Cbuf_AddText("+reload\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_USE:
		xziel_mobile_use_pressed = true;
		if (!xziel_auto_rebuild_use_down) {
			Cbuf_AddText("+use\n");
			Cbuf_Execute();
		}
		break;

	case XZ_TOUCH_JUMP:
		xziel_mobile_jump_pressed = true;
		Cbuf_AddText("+jump\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_KNIFE:
		xziel_mobile_knife_pressed = true;
		Xziel_StopSprintForAction();
		Cbuf_AddText("+knife\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_GRENADE:
		Xziel_ClearMarksmanStickyAds();
		xziel_mobile_grenade_pressed = true;
		xziel_mobile_grenade_pending = true;
		xziel_mobile_grenade_cooking = false;
		xziel_mobile_grenade_seconds_left = 5.0f;
		xziel_mobile_grenade_press_ms = SDL_GetTicks();
		xziel_mobile_grenade_count_before =
			(sv_player && sv.active) ? (int)sv_player->v.primary_grenades :
			(int)cl.stats[STAT_GRENADES];
		Xziel_StopSprintForAction();
		Cbuf_AddText("+grenade\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_SWITCH:
		xziel_mobile_switch_pressed = true;
		Xziel_ClearMarksmanStickyAds();
		if (xziel_adsfire_release_pending || xziel_adsfire_release_requested)
			Xziel_CancelAdsFireForSprint();
		Cbuf_AddText("+switch\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_PAUSE:
		Menu_Pause_Set();
		break;

	default:
		break;
	}
}'''
text = xziel_replace_c_function(
    text,
    "static void Xziel_ActionDown(xziel_touch_role_t role)",
    action_down
)

# Reset two-tap/ADS deadline state on forced input release.
release_reset_anchor = """	xziel_menu_touch_active = false;
	xziel_menu_touch_state = -1;
	Cbuf_Execute();
}"""
release_reset_repl = """	xziel_menu_touch_active = false;
	xziel_menu_touch_state = -1;
	xziel_menu_confirm_state = -1;
	xziel_menu_confirm_row = -1;
	xziel_adsfire_visual_ready_ms = 0;
	Cbuf_Execute();
}"""
if release_reset_anchor in text:
    text = text.replace(release_reset_anchor, release_reset_repl, 1)

sys_sdl.write_text(text, encoding="utf-8")

# ---- Menu text fitting ------------------------------------------------------
helper = source / "menu" / "menu_helper.c"
mhelp = helper.read_text(encoding="utf-8")

# Allow very long left labels to shrink farther before overflowing.
mhelp = mhelp.replace(
    "if (label_scale < vid.scale * 0.68f)\n\t\t\t\tlabel_scale = vid.scale * 0.68f;",
    "if (label_scale < vid.scale * 0.48f)\n\t\t\t\tlabel_scale = vid.scale * 0.48f;"
)

option_button = r'''void Menu_DrawOptionButton(int order, char* selection_name)
{
	int y_factor = 15;
	int x_pos = 165;
	int y_pos = 30 + (order*y_factor);
	float option_scale = vid.scale;
	int max_width;

	UI_SetAlignment (UI_ANCHOR_LEFT, UI_ANCHOR_TOP);

#ifdef __ANDROID__
	max_width = vid.width - UI_X(x_pos) - UI_W(8);
	if (max_width > 0) {
		int width = getTextWidth(selection_name, option_scale);
		if (width > max_width && width > 0) {
			option_scale *= (float)max_width / (float)width;
			if (option_scale < vid.scale * 0.50f)
				option_scale = vid.scale * 0.50f;
		}
	}
#endif

	Menu_DrawString(x_pos, y_pos, selection_name,
		255, 255, 255, 255, option_scale, 0);
}'''
mhelp = xziel_replace_c_function(
    mhelp,
    "void Menu_DrawOptionButton(int order, char* selection_name)",
    option_button
)

title_func = r'''void Menu_DrawTitle (char *title_name, int color)
{
	int x_pos = vid.width/64;
	int y_pos = 5 * vid.scale;
	float title_scale = vid.scale * 2.0f;

#ifdef __ANDROID__
	{
		int max_width = vid.width - (x_pos * 2);
		int width = getTextWidth(title_name, title_scale);
		if (width > max_width && width > 0) {
			title_scale *= (float)max_width / (float)width;
			if (title_scale < vid.scale)
				title_scale = vid.scale;
		}
	}
#endif

	switch (color) {
	case MENU_COLOR_WHITE:
		Draw_ColoredString (x_pos, y_pos, title_name,
			255, 255, 255, 255, title_scale);
		break;
	case MENU_COLOR_YELLOW:
		Draw_ColoredString (x_pos, y_pos, title_name,
			255, 255, 0, 255, title_scale);
		break;
	}
}'''
mhelp = xziel_replace_c_function(
    mhelp,
    "void Menu_DrawTitle (char *title_name, int color)",
    title_func
)

helper.write_text(mhelp, encoding="utf-8")

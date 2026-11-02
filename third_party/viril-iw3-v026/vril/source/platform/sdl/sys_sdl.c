#include "../../nzportable_def.h"
#include "../../menu/menu_defs.h"
#include "sdl_local.h"

#include <errno.h>
#if defined(_WIN32)
#include <direct.h>
#endif
#include <sys/stat.h>
#include <unistd.h>
#ifdef __ANDROID__
#include <jni.h>
#endif

#define MAX_HANDLES 32
#define DEFAULT_MEMORY_MB 128

#ifdef __ANDROID__
#ifndef W_KRAUS
#define W_KRAUS 53
#endif
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

static FILE *sys_handles[MAX_HANDLES];
qboolean isDedicated;
qboolean sdl_running = true;

static qboolean SDL_ArgumentsRequestHeadless(int argc, char **argv)
{
	int i;

	for (i = 1; i + 1 < argc; ++i)
		if (!strcmp(argv[i], "+vid_renderer") &&
			!Q_strcasecmp(argv[i + 1], "headless"))
			return true;
	return false;
}

static int Sys_FindHandle(void)
{
	int i;
	for (i = 1; i < MAX_HANDLES; ++i)
		if (!sys_handles[i]) return i;
	Sys_Error("out of handles");
	return -1;
}

static int Sys_FileLength(FILE *file)
{
	long position = ftell(file);
	long length;
	fseek(file, 0, SEEK_END);
	length = ftell(file);
	fseek(file, position, SEEK_SET);
	return (int)length;
}

int Sys_FileOpenRead(char *path, int *handle)
{
	FILE *file = fopen(path, "rb");
	int index;
	if (!file) { *handle = -1; return -1; }
	index = Sys_FindHandle();
	sys_handles[index] = file;
	*handle = index;
	return Sys_FileLength(file);
}

int Sys_FileOpenWrite(char *path)
{
	FILE *file = fopen(path, "wb");
	int index;
	if (!file) Sys_Error("Error opening %s: %s", path, strerror(errno));
	index = Sys_FindHandle();
	sys_handles[index] = file;
	return index;
}

void Sys_FileClose(int handle) { fclose(sys_handles[handle]); sys_handles[handle] = NULL; }
void Sys_FileSeek(int handle, int position) { fseek(sys_handles[handle], position, SEEK_SET); }
int Sys_FileRead(int handle, void *dest, int count) { return (int)fread(dest, 1, count, sys_handles[handle]); }
int Sys_FileWrite(int handle, void *data, int count) { return (int)fwrite(data, 1, count, sys_handles[handle]); }
int Sys_FileTime(char *path) {

	#if defined(_WIN32)
	struct _stat st;
	return _stat(path, &st) == 0 ? (int)st.st_mtime : -1;
	#else
	struct stat st;
	return stat(path, &st) == 0 ? (int)st.st_mtime : -1;
	#endif
}
void Sys_mkdir(char *path)
{ 
	#if defined(_WIN32)
	_mkdir(path);
	#else
	mkdir(path, 0777);
	#endif
}
void Sys_MakeCodeWriteable(unsigned long startaddr, unsigned long length) { (void)startaddr; (void)length; }

void Sys_PrintSystemInfo(void) { Con_Printf("Vril Engine SDL (%s)\n", SDL_GetPlatform()); }
void Sys_Printf(char *fmt, ...) { va_list args; va_start(args, fmt); vfprintf(stdout, fmt, args); va_end(args); }
void Sys_SystemError(char *error) {
#ifdef __ANDROID__
    Xziel_WriteError(error);
    Xziel_WriteStage("SYS_ERROR");
#endif
    fprintf(stderr, "Vril Engine: %s\n", error);
    if (SDL_WasInit(SDL_INIT_VIDEO))
        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Vril Engine", error, sdl_window);
    SDL_Quit();
    exit(1);
}
void Sys_Quit(void)
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
}
double Sys_FloatTime(void) { static Uint64 start; Uint64 now = SDL_GetPerformanceCounter(); if (!start) start = now; return (double)(now - start) / SDL_GetPerformanceFrequency(); }
char *Sys_ConsoleInput(void) { return NULL; }
void Sys_Sleep(void) { SDL_Delay(1); }
void Sys_HighFPPrecision(void) {}
void Sys_LowFPPrecision(void) {}
void Sys_SetFPCW(void) {}
void Sys_DebugLog(char *file, char *fmt, ...) { (void)file; (void)fmt; }
void Sys_CaptureScreenshot(void)
{
	SDL_Surface *screenshot;
	unsigned char *pixels;
	int width = vid.width;
	int height = vid.height;
	int row_size = width * 3;
	int y;

	pixels = malloc((size_t)row_size * height);
	if (!pixels) {
		Con_Printf("Could not allocate screenshot buffer.\n");
		return;
	}

	glReadBuffer(GL_BACK);
	glPixelStorei(GL_PACK_ALIGNMENT, 1);
	glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE, pixels);

#if SDL_BYTEORDER == SDL_BIG_ENDIAN
	screenshot = SDL_CreateRGBSurface(0, width, height, 24,
		0xff0000, 0x00ff00, 0x0000ff, 0);
#else
	screenshot = SDL_CreateRGBSurface(0, width, height, 24,
		0x0000ff, 0x00ff00, 0xff0000, 0);
#endif
	if (!screenshot) {
		Con_Printf("Could not create screenshot surface: %s\n", SDL_GetError());
		free(pixels);
		return;
	}

	for (y = 0; y < height; ++y)
		memcpy((byte *)screenshot->pixels + y * screenshot->pitch,
			pixels + (height - y - 1) * row_size, row_size);

	if (SDL_SaveBMP(screenshot, "capture.bmp") != 0)
		Con_Printf("Could not save capture.bmp: %s\n", SDL_GetError());

	SDL_FreeSurface(screenshot);
	free(pixels);
}

void Sys_DefaultConfig(void)
{
	Cbuf_AddText("bind MOUSE1 +attack\n");
	Cbuf_AddText("bind MOUSE2 +aim\n");
	Cbuf_AddText("bind w +forward\n");
	Cbuf_AddText("bind s +back\n");
	Cbuf_AddText("bind a +moveleft\n");
	Cbuf_AddText("bind d +moveright\n");
	Cbuf_AddText("bind SPACE +jump\n");
	Cbuf_AddText("bind MWHEELUP +switch\n");
	Cbuf_AddText("bind MWHEELDOWN +switch\n");
	Cbuf_AddText("bind ` toggleconsole\n");
}


int mouse_dx;
int mouse_dy;

#ifdef __ANDROID__
extern cvar_t xziel_mobile_ads_toggle;
extern cvar_t xziel_mobile_sprint_threshold;
extern cvar_t xziel_mobile_touch_sensitivity;
extern cvar_t xziel_mobile_ads_sensitivity;
extern cvar_t xziel_mobile_joystick_sensitivity;
extern cvar_t xziel_mobile_ads_move_sensitivity;
extern cvar_t xziel_mobile_track_fire;
extern cvar_t xziel_mobile_fire_camera_rotation;
extern cvar_t xziel_mobile_minimap;
extern cvar_t xziel_mobile_minimap_range;
extern cvar_t xziel_hud_minimap_x;
extern cvar_t xziel_hud_minimap_y;
extern cvar_t xziel_hud_minimap_scale;
extern cvar_t xziel_hud_minimap_opacity;
extern cvar_t xziel_hud_slide_x;
extern cvar_t xziel_hud_slide_y;
extern cvar_t xziel_hud_slide_scale;
extern cvar_t xziel_hud_slide_opacity;
extern cvar_t xziel_hud_crouch_x;
extern cvar_t xziel_hud_crouch_y;
extern cvar_t xziel_hud_prone_x;
extern cvar_t xziel_hud_prone_y;
extern cvar_t xziel_mobile_autofire_ms;
extern qboolean xziel_mobile_use_available;
extern qboolean xziel_mobile_auto_rebuild_available;
extern cvar_t xziel_mobile_auto_rebuild;
extern cvar_t xziel_mobile_auto_knife;
extern cvar_t xziel_mobile_knife_range_only;
extern cvar_t xziel_mobile_auto_knife_range;
extern cvar_t xziel_mobile_sprint_zone;
extern cvar_t xziel_mobile_sniper_adsfire;
extern cvar_t xziel_mobile_shotgun_adsfire;
extern cvar_t xziel_mobile_marksman_adsfire;

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
extern cvar_t xziel_hud_grenade_x;
extern cvar_t xziel_hud_grenade_y;
extern cvar_t xziel_mobile_fire_sensitivity;
extern cvar_t xziel_mobile_ads_fire_sensitivity;
extern cvar_t xziel_mobile_sniper_sensitivity;
extern cvar_t xziel_mobile_sniper_fire_sensitivity;
extern cvar_t xziel_hud_joy_scale;
extern cvar_t xziel_hud_joy_opacity;
extern cvar_t xziel_hud_fire_scale;
extern cvar_t xziel_hud_fire_opacity;
extern cvar_t xziel_hud_adsfire_scale;
extern cvar_t xziel_hud_adsfire_opacity;
extern cvar_t xziel_hud_ads_scale;
extern cvar_t xziel_hud_ads_opacity;
extern cvar_t xziel_hud_reload_scale;
extern cvar_t xziel_hud_reload_opacity;
extern cvar_t xziel_hud_use_scale;
extern cvar_t xziel_hud_use_opacity;
extern cvar_t xziel_hud_jump_scale;
extern cvar_t xziel_hud_jump_opacity;
extern cvar_t xziel_hud_knife_scale;
extern cvar_t xziel_hud_knife_opacity;
extern cvar_t xziel_hud_pause_scale;
extern cvar_t xziel_hud_pause_opacity;
extern cvar_t xziel_hud_grenade_scale;
extern cvar_t xziel_hud_grenade_opacity;
extern cvar_t xziel_hud_weapon1_x;
extern cvar_t xziel_hud_weapon1_y;
extern cvar_t xziel_hud_weapon1_scale;
extern cvar_t xziel_hud_weapon1_opacity;
extern cvar_t xziel_hud_weapon2_x;
extern cvar_t xziel_hud_weapon2_y;
extern cvar_t xziel_hud_weapon2_scale;
extern cvar_t xziel_hud_weapon2_opacity;
extern cvar_t xziel_hud_pistol_x;
extern cvar_t xziel_hud_pistol_y;
extern cvar_t xziel_hud_pistol_scale;
extern cvar_t xziel_hud_pistol_opacity;
extern cvar_t xziel_mobile_unlimited_pistol;
extern cvar_t xziel_hud_weapons_x;
extern cvar_t xziel_hud_weapons_y;
extern cvar_t xziel_hud_weapons_scale;
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
	XZ_TOUCH_SWITCH,
	XZ_TOUCH_PAUSE,
	XZ_TOUCH_GRENADE,
	XZ_TOUCH_WEAPON2,
	XZ_TOUCH_WEAPON3,
	XZ_TOUCH_WEAPONSTRIP,
	XZ_TOUCH_SLIDE,
	XZ_TOUCH_MINIMAP,
	XZ_TOUCH_CROUCH,
	XZ_TOUCH_PRONE
} xziel_touch_role_t;

typedef struct {
	qboolean active;
	qboolean editor_drag;
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
qboolean xziel_mobile_grenade_pressed = false;
qboolean xziel_mobile_grenade_cooking = false;
float xziel_mobile_grenade_seconds_left = 0.0f;
static qboolean xziel_mobile_grenade_pending = false;
static Uint32 xziel_mobile_grenade_press_ms = 0;
static int xziel_mobile_grenade_count_before = 0;

static int xziel_attack_refs = 0;
static int xziel_aim_refs = 0;
static qboolean xziel_attack_command_down = false;
static Uint32 xziel_attack_release_ms = 0;
static Uint32 xziel_attack_next_ms = 0;
qboolean xziel_mobile_sprint_active = false;
static qboolean xziel_mobile_restore_ads_after_reload = false;
static qboolean xziel_mobile_reload_animation_seen = false;
static qboolean xziel_mobile_ads_latched = false;
static int xziel_mobile_reload_start_frame = 0;
qboolean xziel_mobile_knife_target_near = false;
static Uint32 xziel_mobile_auto_knife_next_ms = 0;
static qboolean xziel_auto_knife_down = false;
static Uint32 xziel_auto_knife_release_ms = 0;
qboolean xziel_mobile_sprint_zone_hot = false;
static qboolean xziel_mobile_sprint_suppressed = false;
static Uint32 xziel_mobile_sprint_retry_ms = 0;
static qboolean xziel_adsfire_attack_engaged = false;
static qboolean xziel_adsfire_release_pending = false;
static qboolean xziel_adsfire_release_requested = false;
static qboolean xziel_adsfire_temp_aim = false;
static qboolean xziel_adsfire_cancelled = false;
static qboolean xziel_adsfire_ads_seen = false;
static Uint32 xziel_adsfire_visual_ready_ms = 0;
static qboolean xziel_release_shot_active = false;
static qboolean xziel_release_shot_aimout_pending = false;
static Uint32 xziel_release_shot_release_ms = 0;
static qboolean xziel_marksman_sticky_ads = false;
static qboolean xziel_menu_touch_active = false;
static SDL_FingerID xziel_menu_touch_finger = 0;
static int xziel_menu_touch_state = -1;
static int xziel_menu_confirm_state = -1;
qboolean xziel_mobile_slide_pressed = false;
qboolean xziel_mobile_crouch_pressed = false;
qboolean xziel_mobile_prone_pressed = false;
static Uint32 xziel_mobile_slide_visual_start_ms;
static Uint32 xziel_mobile_slide_visual_end_ms;

/* -1 means inactive. 0..1 is normalized slide progress.
   Kept client-side because this is presentation only; movement remains QC. */
float Xziel_MobileSlideVisualPhase(void)
{
    Uint32 now;
    Uint32 span;
    float phase;

    if (!xziel_mobile_slide_visual_start_ms ||
        !xziel_mobile_slide_visual_end_ms)
        return -1.0f;

    now = SDL_GetTicks();
    if (now >= xziel_mobile_slide_visual_end_ms) {
        xziel_mobile_slide_visual_start_ms = 0;
        xziel_mobile_slide_visual_end_ms = 0;
        return -1.0f;
    }

    span = xziel_mobile_slide_visual_end_ms -
        xziel_mobile_slide_visual_start_ms;
    if (!span)
        return -1.0f;

    phase = (float)(now - xziel_mobile_slide_visual_start_ms) /
        (float)span;
    if (phase < 0.0f) phase = 0.0f;
    if (phase > 1.0f) phase = 1.0f;
    return phase;
}
float xziel_mobile_track_fire_dx = 0.0f;
float xziel_mobile_track_fire_dy = 0.0f;
float xziel_mobile_track_adsfire_dx = 0.0f;
float xziel_mobile_track_adsfire_dy = 0.0f;
int xziel_hud_editor_selected = XZ_TOUCH_FIRE;
static int xziel_menu_confirm_row = -1;
static qboolean xziel_auto_rebuild_use_down = false;

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
}



static void Xziel_UpdateReloadAdsRestore(void)
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
}



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

static void Xziel_UpdateAutoKnife(void)
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
}

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

static qboolean Xziel_IsDualWeaponMobile(void);
static qboolean Xziel_WeaponDoesNotAdsMobile(void);
static void Xziel_PulseAttackNow(void);
static void Xziel_FinishTemporaryAdsFireAim(void);

static qboolean Xziel_WeaponCanAdsMobile(void);
static qboolean Xziel_AdsReadyForFire(void);

static qboolean Xziel_IsMarksmanMobile(void);
static void Xziel_CommitMarksmanStickyAds(void);
static void Xziel_ClearMarksmanStickyAds(void);

static Uint32 Xziel_AdsVisualDelayMs(void);
static qboolean Xziel_AdsVisualReady(void);

static void Xziel_UpdateMobileFire(void)
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
}



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


static Uint32 Xziel_AdsVisualDelayMs(void)
{
	switch (cl.stats[STAT_ACTIVEWEAPON]) {
	case W_COLT:
	case W_357:
	case W_KILLU:
		return 115;

	case W_THOMPSON:
	case W_GIBS:
	case W_MP40:
	case W_AFTERBURNER:
	case W_PPSH:
	case W_REAPER:
	case W_MP5:
	case W_KOLLIDER:
		return 130;

	case W_DB:
	case W_BORE:
	case W_SAWNOFF:
	case W_TRENCH:
	case W_GUT:
		return 150;

	case W_BROWNING:
	case W_ACCELERATOR:
	case W_MG:
	case W_BARRACUDA:
		return 195;

	case W_KAR:
	case W_ARMAGEDDON:
	case W_SPRING:
	case W_PULVERIZER:
	case W_GEWEHR:
	case W_COMPRESSOR:
	case W_M1:
	case W_M1000:
	case W_M1A1:
	case W_WIDDER:
		return 190;

	case W_KAR_SCOPE:
	case W_HEADCRACKER:
	case W_PTRS:
	case W_PENETRATOR:
		return 220;

	default:
		return 165;
	}
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

static qboolean Xziel_AdsReadyForFire(void)
{
	return Xziel_AdsVisualReady();
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
	case 53: /* W_KRAUS in QuakeC */
		return true;
	default:
		return false;
	}
}

static qboolean Xziel_AdsFireReleaseWeapon(void)
{
	return Xziel_AdsFireModeForCurrentWeapon() == 1;
}


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

static void Xziel_PulseAttackNow(void)
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

static void Xziel_CancelAdsFireForSprint(void)
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
}

static void Xziel_ActionDown(xziel_touch_role_t role)
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

	case XZ_TOUCH_SLIDE:
	{
		Uint32 slide_now = SDL_GetTicks();
		qboolean confirmed_sprint =
			xziel_mobile_sprint_active || cl.stats[STAT_ZOOM] == 3;

		xziel_mobile_slide_pressed = true;

		/* Only play the dramatic skid pose for sprint -> crouch. A normal
		   standing crouch remains a normal crouch. */
		if (confirmed_sprint) {
			xziel_mobile_slide_visual_start_ms = slide_now;
			xziel_mobile_slide_visual_end_ms = slide_now + 560;
		}

		xziel_mobile_sprint_suppressed = true;
		xziel_mobile_sprint_active = false;
		xziel_mobile_sprint_retry_ms = slide_now + 650;
		Cbuf_AddText("impulse 34\n");
		Cbuf_Execute();
		break;
	}

	case XZ_TOUCH_CROUCH:
		xziel_mobile_crouch_pressed = true;
		Cbuf_AddText("impulse 31\n");
		break;
	case XZ_TOUCH_PRONE:
		xziel_mobile_prone_pressed = true;
		Cbuf_AddText("impulse 32\n");
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

	case XZ_TOUCH_WEAPON2:
		Xziel_ForceExitAdsForSprint();
		Cbuf_AddText("impulse 60\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_WEAPON3:
		Xziel_ForceExitAdsForSprint();
		Cbuf_AddText("impulse 61\n");
		Cbuf_Execute();
		break;

	case XZ_TOUCH_WEAPONSTRIP:
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

	case XZ_TOUCH_SLIDE:
		xziel_mobile_slide_pressed = false;
		break;

	case XZ_TOUCH_CROUCH:
		xziel_mobile_crouch_pressed = false;
		break;
	case XZ_TOUCH_PRONE:
		xziel_mobile_prone_pressed = false;
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

	case XZ_TOUCH_WEAPON2:
	case XZ_TOUCH_WEAPON3:
	case XZ_TOUCH_WEAPONSTRIP:
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


static qboolean Xziel_PointInRect(float x, float y, float cx, float cy, float w, float h)
{
    return x >= cx - w * 0.5f && x <= cx + w * 0.5f &&
        y >= cy - h * 0.5f && y <= cy + h * 0.5f;
}

static qboolean Xziel_WeaponStripHit(float x, float y, int slot)
{
	float s = xziel_hud_weapon1_scale.value;
	float cx = xziel_hud_weapon1_x.value;
	float cy = xziel_hud_weapon1_y.value;
	float w = 0.155f;
	float h = 0.084f;

	if (slot == 2)
		return false;
	if (s < 0.35f) s = 0.35f;
	if (s > 2.25f) s = 2.25f;
	return Xziel_PointInRect(x, y, cx, cy, w * s, h * s);
}

static qboolean Xziel_WeaponStripGroupHit(float x, float y)
{
	return Xziel_WeaponStripHit(x, y, 0) ||
		Xziel_WeaponStripHit(x, y, 1) ||
		Xziel_WeaponStripHit(x, y, 2);
}

static xziel_touch_role_t Xziel_RoleForPoint(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.073f * hs * xziel_hud_fire_scale.value)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.056f * hs * xziel_hud_adsfire_scale.value)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.047f * hs * xziel_hud_ads_scale.value)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.044f * hs * xziel_hud_reload_scale.value)) return XZ_TOUCH_RELOAD;
	if (xziel_mobile_use_available && Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.050f * hs * xziel_hud_use_scale.value)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.036f * hs * xziel_hud_pause_scale.value)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.041f * hs * xziel_hud_grenade_scale.value)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.044f * hs * xziel_hud_jump_scale.value)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_slide_x.value, xziel_hud_slide_y.value, 0.044f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_SLIDE;
	if (Xziel_IsInside(x, y, xziel_hud_crouch_x.value, xziel_hud_crouch_y.value, 0.044f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_CROUCH;
	if (Xziel_IsInside(x, y, xziel_hud_prone_x.value, xziel_hud_prone_y.value, 0.044f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_PRONE;
	if ((!xziel_mobile_knife_range_only.value || xziel_mobile_knife_target_near) &&
		Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.044f * hs * xziel_hud_knife_scale.value)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.041f * hs)) return XZ_TOUCH_SWITCH;
	if (x < 0.45f && y > 0.30f) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_LOOK;
}

static xziel_touch_role_t Xziel_HudEditorRole(float x, float y)
{
	float hs = xziel_mobile_hud_scale.value;
	if (Xziel_IsInside(x, y, xziel_hud_minimap_x.value, xziel_hud_minimap_y.value,
		0.082f * hs * xziel_hud_minimap_scale.value)) return XZ_TOUCH_MINIMAP;
	if (Xziel_IsInside(x, y, xziel_hud_fire_x.value, xziel_hud_fire_y.value, 0.090f * hs * xziel_hud_fire_scale.value)) return XZ_TOUCH_FIRE;
	if (Xziel_IsInside(x, y, xziel_hud_adsfire_x.value, xziel_hud_adsfire_y.value, 0.075f * hs * xziel_hud_adsfire_scale.value)) return XZ_TOUCH_ADSFIRE;
	if (Xziel_IsInside(x, y, xziel_hud_ads_x.value, xziel_hud_ads_y.value, 0.065f * hs * xziel_hud_ads_scale.value)) return XZ_TOUCH_ADS;
	if (Xziel_IsInside(x, y, xziel_hud_reload_x.value, xziel_hud_reload_y.value, 0.060f * hs * xziel_hud_reload_scale.value)) return XZ_TOUCH_RELOAD;
	if (Xziel_IsInside(x, y, xziel_hud_use_x.value, xziel_hud_use_y.value, 0.065f * hs * xziel_hud_use_scale.value)) return XZ_TOUCH_USE;
	if (Xziel_IsInside(x, y, xziel_hud_pause_x.value, xziel_hud_pause_y.value, 0.055f * hs * xziel_hud_pause_scale.value)) return XZ_TOUCH_PAUSE;
	if (Xziel_IsInside(x, y, xziel_hud_grenade_x.value, xziel_hud_grenade_y.value, 0.057f * hs * xziel_hud_grenade_scale.value)) return XZ_TOUCH_GRENADE;
	if (Xziel_IsInside(x, y, xziel_hud_slide_x.value, xziel_hud_slide_y.value, 0.060f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_SLIDE;
	if (Xziel_IsInside(x, y, xziel_hud_crouch_x.value, xziel_hud_crouch_y.value, 0.060f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_CROUCH;
	if (Xziel_IsInside(x, y, xziel_hud_prone_x.value, xziel_hud_prone_y.value, 0.060f * hs * xziel_hud_slide_scale.value)) return XZ_TOUCH_PRONE;
	if (Xziel_IsInside(x, y, xziel_hud_jump_x.value, xziel_hud_jump_y.value, 0.060f * hs * xziel_hud_jump_scale.value)) return XZ_TOUCH_JUMP;
	if (Xziel_IsInside(x, y, xziel_hud_knife_x.value, xziel_hud_knife_y.value, 0.060f * hs * xziel_hud_knife_scale.value)) return XZ_TOUCH_KNIFE;
	if (Xziel_IsInside(x, y, xziel_hud_switch_x.value, xziel_hud_switch_y.value, 0.057f * hs)) return XZ_TOUCH_SWITCH;
	if (Xziel_IsInside(x, y, xziel_hud_joy_x.value, xziel_hud_joy_y.value, 0.120f * hs * xziel_hud_joy_scale.value)) return XZ_TOUCH_MOVE;
	return XZ_TOUCH_NONE;
}

static void Xziel_HudEditorSetPosition(xziel_touch_role_t role, float x, float y)
{
	if (x < 0.035f) x = 0.035f;
	if (x > 0.965f) x = 0.965f;
	if (y < 0.055f) y = 0.055f;
	if (y > 0.945f) y = 0.945f;
	xziel_hud_editor_selected = role;
	switch (role) {
	case XZ_TOUCH_MOVE: Cvar_SetValue("xziel_hud_joy_x", x); Cvar_SetValue("xziel_hud_joy_y", y); break;
	case XZ_TOUCH_FIRE: Cvar_SetValue("xziel_hud_fire_x", x); Cvar_SetValue("xziel_hud_fire_y", y); break;
	case XZ_TOUCH_ADSFIRE: Cvar_SetValue("xziel_hud_adsfire_x", x); Cvar_SetValue("xziel_hud_adsfire_y", y); break;
	case XZ_TOUCH_ADS: Cvar_SetValue("xziel_hud_ads_x", x); Cvar_SetValue("xziel_hud_ads_y", y); break;
	case XZ_TOUCH_RELOAD: Cvar_SetValue("xziel_hud_reload_x", x); Cvar_SetValue("xziel_hud_reload_y", y); break;
	case XZ_TOUCH_USE: Cvar_SetValue("xziel_hud_use_x", x); Cvar_SetValue("xziel_hud_use_y", y); break;
	case XZ_TOUCH_JUMP: Cvar_SetValue("xziel_hud_jump_x", x); Cvar_SetValue("xziel_hud_jump_y", y); break;
	case XZ_TOUCH_SLIDE: Cvar_SetValue("xziel_hud_slide_x", x); Cvar_SetValue("xziel_hud_slide_y", y); break;
	case XZ_TOUCH_CROUCH: Cvar_SetValue("xziel_hud_crouch_x", x); Cvar_SetValue("xziel_hud_crouch_y", y); break;
	case XZ_TOUCH_PRONE: Cvar_SetValue("xziel_hud_prone_x", x); Cvar_SetValue("xziel_hud_prone_y", y); break;
	case XZ_TOUCH_KNIFE: Cvar_SetValue("xziel_hud_knife_x", x); Cvar_SetValue("xziel_hud_knife_y", y); break;
	case XZ_TOUCH_GRENADE: Cvar_SetValue("xziel_hud_grenade_x", x); Cvar_SetValue("xziel_hud_grenade_y", y); break;
	case XZ_TOUCH_SWITCH: Cvar_SetValue("xziel_hud_switch_x", x); Cvar_SetValue("xziel_hud_switch_y", y); break;
	case XZ_TOUCH_PAUSE: Cvar_SetValue("xziel_hud_pause_x", x); Cvar_SetValue("xziel_hud_pause_y", y); break;
	case XZ_TOUCH_MINIMAP: Cvar_SetValue("xziel_hud_minimap_x", x); Cvar_SetValue("xziel_hud_minimap_y", y); break;
	default: break;
	}
}

static void Xziel_UpdateMove(float x, float y)
{
	float raw_dx, raw_dy, dx, dy, len, radius_x, radius_y;
	float sprint_zone;
	float response;
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

	response = xziel_mobile_joystick_sensitivity.value;
	if (response < 0.50f) response = 0.50f;
	if (response > 2.00f) response = 2.00f;
	dx *= response;
	dy *= response;

	len = sqrtf(dx * dx + dy * dy);
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

	/* A slide temporarily owns the sprint lane. Once its short suppression
	   window ends, holding the stick forward can naturally return to sprint. */
	if (xziel_mobile_sprint_suppressed &&
		xziel_mobile_sprint_retry_ms &&
		now >= xziel_mobile_sprint_retry_ms) {
		xziel_mobile_sprint_suppressed = false;
		xziel_mobile_sprint_retry_ms = 0;
	}

	if (xziel_mobile_sprint_zone_hot) {
		if (!xziel_mobile_sprint_suppressed) {
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
}

static void Xziel_ReleaseAllTouches(void)
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
	xziel_marksman_sticky_ads = false;
	xziel_adsfire_cancelled = false;
	xziel_mobile_restore_ads_after_reload = false;
	xziel_mobile_reload_animation_seen = false;
	xziel_menu_touch_active = false;
	xziel_menu_touch_state = -1;
	xziel_menu_confirm_state = -1;
	xziel_menu_confirm_row = -1;
	xziel_adsfire_visual_ready_ms = 0;
	Cbuf_Execute();
}



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


static void Xziel_MenuFinger(float x, float y, qboolean down, qboolean motion)
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
}

static void Xziel_FingerDown(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot;
	qboolean menu = (key_dest == key_menu || key_dest == key_menu_pause);

	if (cl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
		Xziel_ReleaseAllTouches();
		Menu_ExitMap();
		return;
	}

	if (m_state == m_hudedit && menu) {
		int mx = (int)(finger->x * (float)vid.width);
		int my = (int)(finger->y * (float)vid.height);
		int row;

		/* Editor widgets always win over draggable HUD controls. This fixes
		   Reset Layout / Done being swallowed by the joystick/control hitbox. */
		Menu_MouseMove(mx, my);
		if (Menu_MouseButton(mx, my, true)) {
			xziel_menu_touch_active = true;
			xziel_menu_touch_finger = finger->fingerId;
			xziel_menu_touch_state = m_state;
			return;
		}
		row = Xziel_MenuButtonAtPoint(mx, my);
		if (row >= 0) {
			Xziel_MenuSetCursor(row);
			Menu_ButtonPress();
			xziel_menu_touch_active = false;
			xziel_menu_touch_state = -1;
			return;
		}

		xziel_touch_role_t role = Xziel_HudEditorRole(finger->x, finger->y);
		if (role != XZ_TOUCH_NONE && role != XZ_TOUCH_LOOK) {
			xziel_hud_editor_selected = role;
			slot = Xziel_AllocTouch(finger->fingerId);
			if (slot) {
				slot->editor_drag = true;
				slot->role = role;
				slot->last_x = finger->x;
				slot->last_y = finger->y;
				Xziel_HudEditorSetPosition(role, finger->x, finger->y);
			}
			return;
		}
		return;
	}

	if (menu) {
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

	slot->role = Xziel_RoleForPoint(finger->x, finger->y);
	slot->last_x = finger->x;
	slot->last_y = finger->y;
	if (slot->role == XZ_TOUCH_FIRE) {
		xziel_mobile_track_fire_dx = 0.0f;
		xziel_mobile_track_fire_dy = 0.0f;
	} else if (slot->role == XZ_TOUCH_ADSFIRE) {
		xziel_mobile_track_adsfire_dx = 0.0f;
		xziel_mobile_track_adsfire_dy = 0.0f;
	}
	if (slot->role == XZ_TOUCH_MOVE) {
		xziel_mobile_move_active = true;
		xziel_mobile_move_anchor_x = xziel_hud_joy_x.value;
		xziel_mobile_move_anchor_y = xziel_hud_joy_y.value;
		Xziel_UpdateMove(finger->x, finger->y);
	} else if (slot->role != XZ_TOUCH_LOOK) {
		Xziel_ActionDown(slot->role);
	}
}

static void Xziel_FingerMotion(const SDL_TouchFingerEvent *finger)
{
	xziel_touch_slot_t *slot = Xziel_FindTouch(finger->fingerId);
	if (slot && slot->editor_drag) {
		Xziel_HudEditorSetPosition(slot->role, finger->x, finger->y);
		slot->last_x = finger->x;
		slot->last_y = finger->y;
		return;
	}
	if (key_dest == key_menu || key_dest == key_menu_pause) {
		if (xziel_menu_touch_active &&
			xziel_menu_touch_finger == finger->fingerId &&
			xziel_menu_touch_state == m_state)
			Xziel_MenuFinger(finger->x, finger->y, false, true);
		return;
	}
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
		qboolean firing_touch =
			slot->role == XZ_TOUCH_FIRE ||
			slot->role == XZ_TOUCH_ADSFIRE ||
			slot->role == XZ_TOUCH_GRENADE;

		if (cl.stats[STAT_ZOOM] == 2)
			look_scale *= firing_touch ?
				xziel_mobile_sniper_fire_sensitivity.value :
				xziel_mobile_sniper_sensitivity.value;
		else if (cl.stats[STAT_ZOOM] == 1)
			look_scale *= firing_touch ?
				xziel_mobile_ads_fire_sensitivity.value :
				xziel_mobile_ads_sensitivity.value;
		else if (firing_touch)
			look_scale *= xziel_mobile_fire_sensitivity.value;

		if (!((slot->role == XZ_TOUCH_FIRE || slot->role == XZ_TOUCH_ADSFIRE) &&
			xziel_mobile_fire_camera_rotation.value < 0.5f)) {
			mouse_dx += (int)((finger->x - slot->last_x) * (float)vid.width * look_scale);
			mouse_dy += (int)((finger->y - slot->last_y) * (float)vid.height * look_scale);
		}

		if (xziel_mobile_track_fire.value >= 0.5f &&
			(slot->role == XZ_TOUCH_FIRE || slot->role == XZ_TOUCH_ADSFIRE)) {
			float cx = slot->role == XZ_TOUCH_FIRE ? xziel_hud_fire_x.value : xziel_hud_adsfire_x.value;
			float cy = slot->role == XZ_TOUCH_FIRE ? xziel_hud_fire_y.value : xziel_hud_adsfire_y.value;
			float rs = slot->role == XZ_TOUCH_FIRE ?
				(0.073f * xziel_mobile_hud_scale.value * xziel_hud_fire_scale.value) :
				(0.056f * xziel_mobile_hud_scale.value * xziel_hud_adsfire_scale.value);
			float dx = (finger->x - cx) * ((float)vid.width / (float)vid.height) / rs;
			float dy = (finger->y - cy) / rs;
			float len = sqrtf(dx*dx + dy*dy);
			if (len > 0.78f) { dx *= 0.78f/len; dy *= 0.78f/len; }
			if (slot->role == XZ_TOUCH_FIRE) {
				xziel_mobile_track_fire_dx = dx;
				xziel_mobile_track_fire_dy = dy;
			} else {
				xziel_mobile_track_adsfire_dx = dx;
				xziel_mobile_track_adsfire_dy = dy;
			}
		}
	}
	slot->last_x = finger->x;
	slot->last_y = finger->y;
}

static void Xziel_FingerUp(const SDL_TouchFingerEvent *finger)
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
}
#endif

static int SDL_KeyToQuake(SDL_Keycode key)
{
	switch (key) {
	case SDLK_UP: return K_UPARROW; case SDLK_DOWN: return K_DOWNARROW;
	case SDLK_LEFT: return K_LEFTARROW; case SDLK_RIGHT: return K_RIGHTARROW;
	case SDLK_ESCAPE: return K_ESCAPE;
#ifdef __ANDROID__
	case SDLK_AC_BACK: return K_ESCAPE;
#endif
	case SDLK_RETURN: case SDLK_KP_ENTER: return K_ENTER;
	case SDLK_TAB: return K_TAB; case SDLK_BACKSPACE: return '\b';
	case SDLK_DELETE: return K_DELETE;
	case SDLK_F1: return K_AUX1; case SDLK_F2: return K_AUX2; case SDLK_F3: return K_AUX3;
	case SDLK_F4: return K_AUX4; case SDLK_F5: return K_AUX5; case SDLK_F6: return K_AUX6;
	case SDLK_F7: return K_AUX7; case SDLK_F8: return K_AUX8; case SDLK_F9: return K_AUX9;
	case SDLK_F10: return K_AUX10; case SDLK_F11: return K_AUX11; case SDLK_F12: return K_AUX12;
	case SDLK_F13: return K_AUX13; case SDLK_F14: return K_AUX14; case SDLK_F15: return K_AUX15;
	case SDLK_F16: return K_AUX16; case SDLK_F17: return K_AUX17; case SDLK_F18: return K_AUX18;
	case SDLK_F19: return K_AUX19; case SDLK_F20: return K_AUX20; case SDLK_F21: return K_AUX21;
	case SDLK_F22: return K_AUX22; case SDLK_F23: return K_AUX23; case SDLK_F24: return K_AUX24;
	case SDLK_LSHIFT: case SDLK_RSHIFT: return K_SHIFT;
	case SDLK_LCTRL: case SDLK_RCTRL: return K_CTRL;
	case SDLK_LALT: case SDLK_RALT: return K_ALT;
	case SDLK_HOME: return K_HOME; case SDLK_END: return K_END;
	case SDLK_PAGEUP: return K_PGUP; case SDLK_PAGEDOWN: return K_PGDN;
	case SDLK_INSERT: return K_INSERT; case SDLK_PAUSE: return K_PAUSE;
	case SDLK_CAPSLOCK: return K_CAPSLOCK; case SDLK_NUMLOCKCLEAR: return K_NUMLOCK;
	case SDLK_SCROLLLOCK: return K_SCROLLLOCK; case SDLK_PRINTSCREEN: return K_PRINTSCREEN;
	case SDLK_KP_9: return K_KP_9; case SDLK_KP_PERIOD: return K_KP_PERIOD;
	case SDLK_KP_DIVIDE: return K_KP_DIVIDE; case SDLK_KP_MULTIPLY: return K_KP_MULTIPLY;
	case SDLK_KP_MINUS: return K_KP_MINUS; case SDLK_KP_PLUS: return K_KP_PLUS;
	case SDLK_KP_EQUALS: return K_KP_EQUALS;
	case SDLK_APPLICATION: return K_APPLICATION; case SDLK_POWER: return K_POWER;
	case SDLK_HELP: return K_HELP; case SDLK_MENU: return K_MENU; case SDLK_SELECT: return K_SELECT_KEY;
	case SDLK_STOP: return K_STOP; case SDLK_AGAIN: return K_AGAIN; case SDLK_UNDO: return K_UNDO;
	case SDLK_CUT: return K_CUT; case SDLK_COPY: return K_COPY; case SDLK_PASTE: return K_PASTE;
	case SDLK_FIND: return K_FIND; case SDLK_MUTE: return K_MUTE; case SDLK_VOLUMEUP: return K_VOLUMEUP;
	case SDLK_VOLUMEDOWN: return K_VOLUMEDOWN; case SDLK_SYSREQ: return K_SYSREQ; case SDLK_CLEAR: return K_CLEAR;
	case SDLK_SPACE: return K_SPACE;
	default:
		if (key >= 32 && key < 127) return (int)key;
		{
			SDL_Scancode scancode = SDL_GetScancodeFromKey(key);
			return scancode != SDL_SCANCODE_UNKNOWN ? K_SDL_SCANCODE_BASE + scancode : 0;
		}
	}
}

static int SDL_StringToKeynum(const char *name)
{
	SDL_Scancode scancode = SDL_GetScancodeFromName(name);
	return scancode != SDL_SCANCODE_UNKNOWN ? K_SDL_SCANCODE_BASE + scancode : -1;
}

static const char *SDL_KeynumToString(int keynum)
{
	if (keynum < K_SDL_SCANCODE_BASE || keynum >= MAX_KEYS)
		return NULL;
	return SDL_GetScancodeName((SDL_Scancode)(keynum - K_SDL_SCANCODE_BASE));
}

static int SDL_MouseToQuake(Uint8 button)
{
	switch (button) { case SDL_BUTTON_LEFT: return K_MOUSE1; case SDL_BUTTON_RIGHT: return K_MOUSE2; case SDL_BUTTON_MIDDLE: return K_MOUSE3; case SDL_BUTTON_X1: return K_MOUSE4; case SDL_BUTTON_X2: return K_MOUSE5; default: return 0; }
}

static int SDL_ControllerToQuake(SDL_GameControllerButton button)
{
	switch (button) {
	case SDL_CONTROLLER_BUTTON_A: return K_BOTTOMFACE;
	case SDL_CONTROLLER_BUTTON_B: return K_RIGHTFACE;
	case SDL_CONTROLLER_BUTTON_X: return K_LEFTFACE;
	case SDL_CONTROLLER_BUTTON_Y: return K_TOPFACE;
	case SDL_CONTROLLER_BUTTON_BACK: return K_SELECT;
	case SDL_CONTROLLER_BUTTON_START: return K_START;
	case SDL_CONTROLLER_BUTTON_LEFTSTICK: return K_LTHUMB;
	case SDL_CONTROLLER_BUTTON_RIGHTSTICK: return K_RTHUMB;
	case SDL_CONTROLLER_BUTTON_LEFTSHOULDER: return K_LTRIGGER;
	case SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: return K_RTRIGGER;
	case SDL_CONTROLLER_BUTTON_DPAD_UP: return K_DPAD_UP;
	case SDL_CONTROLLER_BUTTON_DPAD_DOWN: return K_DPAD_DOWN;
	case SDL_CONTROLLER_BUTTON_DPAD_LEFT: return K_DPAD_LEFT;
	case SDL_CONTROLLER_BUTTON_DPAD_RIGHT: return K_DPAD_RIGHT;
	default: return 0;
	}
}

static void SDL_MenuCoordinates(int window_x, int window_y, int *drawable_x, int *drawable_y)
{
	int window_width, window_height;
	SDL_GetWindowSize(sdl_window, &window_width, &window_height);
	*drawable_x = window_width > 0 ? window_x * (int)vid.width / window_width : window_x;
	*drawable_y = window_height > 0 ? window_y * (int)vid.height / window_height : window_y;
}

void Sys_SendKeyEvents(void)
{
	SDL_Event event;
	static qboolean trigger_down[2];
	if (!SDL_WasInit(SDL_INIT_EVENTS))
		return;
	while (SDL_PollEvent(&event)) {
		int key;
		switch (event.type) {
		case SDL_QUIT: sdl_running = false; break;
		case SDL_KEYDOWN: case SDL_KEYUP:
			if (event.type == SDL_KEYDOWN) { IN_SetActiveDevice(IN_DEVICE_KEYBOARD_MOUSE); Menu_SetInputDevice(IN_DEVICE_KEYBOARD_MOUSE); }
#ifdef __ANDROID__
			if (event.type == SDL_KEYDOWN && event.key.keysym.sym == SDLK_AC_BACK &&
				cl.stats[STAT_HEALTH] <= 0 && key_dest == key_game) {
				Xziel_ReleaseAllTouches();
				Menu_ExitMap();
				break;
			}
#endif
			if (event.type == SDL_KEYDOWN && !event.key.repeat &&
				event.key.keysym.sym == SDLK_BACKQUOTE && key_dest == key_menu) {
				Con_ToggleConsole_f();
				break;
			}
			key = SDL_KeyToQuake(event.key.keysym.sym);
			if (key && !event.key.repeat) Key_Event(key, event.type == SDL_KEYDOWN);
			break;
#ifdef __ANDROID__
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
			if (event.type == SDL_MOUSEBUTTONDOWN) { IN_SetActiveDevice(IN_DEVICE_KEYBOARD_MOUSE); Menu_SetInputDevice(IN_DEVICE_KEYBOARD_MOUSE); }
			key = SDL_MouseToQuake(event.button.button);
			if (key && !in_bind && (key_dest == key_menu || key_dest == key_menu_pause)) {
				int x, y;
				qboolean slider_handled = false;
				SDL_MenuCoordinates(event.button.x, event.button.y, &x, &y);
				Menu_MouseMove(x, y);
				if (key == K_MOUSE1)
					slider_handled = Menu_MouseButton(x, y, event.type == SDL_MOUSEBUTTONDOWN);
				if (event.type == SDL_MOUSEBUTTONDOWN && key == K_MOUSE1 && !slider_handled) Menu_ButtonPress();
			} else if (key) Key_Event(key, event.type == SDL_MOUSEBUTTONDOWN);
			break;
		case SDL_MOUSEMOTION:
			if (event.motion.xrel || event.motion.yrel) { IN_SetActiveDevice(IN_DEVICE_KEYBOARD_MOUSE); Menu_SetInputDevice(IN_DEVICE_KEYBOARD_MOUSE); }
			if (key_dest == key_menu || key_dest == key_menu_pause) {
				int x, y;
				SDL_MenuCoordinates(event.motion.x, event.motion.y, &x, &y);
				Menu_MouseMove(x, y);
			}
			else { mouse_dx += event.motion.xrel; mouse_dy += event.motion.yrel; }
			break;
		case SDL_MOUSEWHEEL:
			if (in_bind || (key_dest != key_menu && key_dest != key_menu_pause)) {
				key = event.wheel.y > 0 ? K_MWHEELUP : event.wheel.y < 0 ? K_MWHEELDOWN : 0;
				if (key) { Key_Event(key, true); Key_Event(key, false); }
			} else {
				if (event.wheel.y > 0) Menu_IncreaseCursor();
				if (event.wheel.y < 0) Menu_DecreaseCursor();
			}
			break;
		case SDL_CONTROLLERBUTTONDOWN: case SDL_CONTROLLERBUTTONUP:
			IN_SDLControllerActivated(event.cbutton.which);
			if (event.type == SDL_CONTROLLERBUTTONDOWN) { IN_SetActiveDevice(IN_DEVICE_GAMEPAD); Menu_SetInputDevice(IN_DEVICE_GAMEPAD); }
			key = SDL_ControllerToQuake(event.cbutton.button);
			if (key) Key_Event(key, event.type == SDL_CONTROLLERBUTTONDOWN);
			break;
		case SDL_CONTROLLERAXISMOTION:
			IN_SDLControllerActivated(event.caxis.which);
			if (event.caxis.value > 8192 || event.caxis.value < -8192) { IN_SetActiveDevice(IN_DEVICE_GAMEPAD); Menu_SetInputDevice(IN_DEVICE_GAMEPAD); }
			if (event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT ||
				event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERRIGHT) {
				int trigger = event.caxis.axis == SDL_CONTROLLER_AXIS_TRIGGERLEFT ? 0 : 1;
				qboolean down = event.caxis.value > 16384;
				if (down != trigger_down[trigger]) {
					trigger_down[trigger] = down;
					Key_Event(trigger ? K_ZRTRIGGER : K_ZLTRIGGER, down);
				}
			}
			break;
		case SDL_CONTROLLERDEVICEADDED: IN_SDLControllerAdded(event.cdevice.which); break;
		case SDL_CONTROLLERDEVICEREMOVED: IN_SDLControllerRemoved(event.cdevice.which); break;
		case SDL_WINDOWEVENT:
			if (event.window.event == SDL_WINDOWEVENT_SIZE_CHANGED || event.window.event == SDL_WINDOWEVENT_RESIZED)
				VID_SDLResize();
#ifdef __ANDROID__
			if (event.window.event == SDL_WINDOWEVENT_FOCUS_LOST ||
				event.window.event == SDL_WINDOWEVENT_MINIMIZED)
				Xziel_ReleaseAllTouches();
#endif
			break;
		}
	}
#ifdef __ANDROID__
	Xziel_UpdateMobileFire();
	Xziel_UpdateAutoRebuild();
	Xziel_UpdateAutoKnife();
	Xziel_UpdateGrenadeCook();
	Xziel_UpdateReloadAdsRestore();
	/* Touch is handled directly above. Avoid Android relative-mouse capture and
	   SDL's touch-mouse path fighting the mobile camera. */
	SDL_SetRelativeMouseMode(SDL_FALSE);
#else
	SDL_SetRelativeMouseMode((key_dest == key_game && SDL_GetKeyboardFocus() == sdl_window) ? SDL_TRUE : SDL_FALSE);
#endif
}

int main(int argc, char **argv)
{
	quakeparms_t parms;
	startup_arguments_t startup;
	const char *base_directory;
	char startup_error[256];
	size_t heap_size;
	double oldtime;
	qboolean headless_test;
	memset(&parms, 0, sizeof(parms));
	if (!Startup_LoadArguments(&startup, argc, argv, "setup.ini",
		startup_error, sizeof(startup_error))) {
		fprintf(stderr, "Startup: %s\n", startup_error);
		return 1;
	}
	if (!Startup_GetBaseDirectory(&startup, ".", &base_directory,
		startup_error, sizeof(startup_error))) {
		fprintf(stderr, "Startup: %s\n", startup_error);
		Startup_FreeArguments(&startup);
		return 1;
	}
#ifdef __ANDROID__
	xziel_diag_basedir = base_directory;
	Xziel_WriteStage("ARGS_READY");
#endif
	headless_test = TestHandler_ArgumentsAllowHeadless(startup.argc, startup.argv) ||
		SDL_ArgumentsRequestHeadless(startup.argc, startup.argv);
#ifdef __ANDROID__
	SDL_SetHintWithPriority(SDL_HINT_ORIENTATIONS,
		"LandscapeLeft LandscapeRight", SDL_HINT_OVERRIDE);
	SDL_SetHintWithPriority(SDL_HINT_TOUCH_MOUSE_EVENTS, "0", SDL_HINT_OVERRIDE);
#endif
	if (SDL_Init(headless_test ? SDL_INIT_TIMER :
		(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_EVENTS | SDL_INIT_GAMECONTROLLER | SDL_INIT_SENSOR)) != 0) {
		fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
		Startup_FreeArguments(&startup);
		return 1;
	}
#ifdef __ANDROID__
	Xziel_WriteStage("SDL_INIT_OK");
#endif
	Key_SetPlatformKeyConversion(SDL_StringToKeynum, SDL_KeynumToString);
	parms.membase = Startup_AllocateHeap(&startup, DEFAULT_MEMORY_MB * 1024 * 1024,
		&heap_size, startup_error, sizeof(startup_error));
	if (!parms.membase) {
		fprintf(stderr, "Startup: %s\n", startup_error);
		Startup_FreeArguments(&startup);
		SDL_Quit();
		return 1;
	}
	parms.memsize = (int)heap_size;
	parms.basedir = (char *)base_directory;
	COM_InitArgv(startup.argc, startup.argv);
	parms.argc = com_argc;
	parms.argv = com_argv;
#ifdef __ANDROID__
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
		double now = Sys_FloatTime();
		Host_Frame(now - oldtime);
		music_update();
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
		Host_Shutdown();
	free(parms.membase);
	Startup_FreeArguments(&startup);
	SDL_Quit();
	return 0;
}

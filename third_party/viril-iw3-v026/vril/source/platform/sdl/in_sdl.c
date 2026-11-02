#include "../../nzportable_def.h"
#include "sdl_local.h"

#ifdef __ANDROID__
extern qboolean xziel_mobile_move_active;
extern float xziel_mobile_move_x;
extern float xziel_mobile_move_y;
#endif

extern int mouse_dx;
extern int mouse_dy;

qboolean IN_PlatformHasMouse(void) { return true; }
qboolean IN_PlatformHasGamepad(void) { return true; }

void IN_SetMouseToRelative(bool relative)
{
	if (relative)
		SDL_SetRelativeMouseMode(SDL_TRUE);
	else
		SDL_SetRelativeMouseMode(SDL_FALSE);
}

void IN_PlatformClearPendingInput(void)
{
	mouse_dx = 0;
	mouse_dy = 0;
}

void IN_PlatformMouseMove(usercmd_t *cmd)
{
	(void)cmd;

	V_StopPitchDrift();
	if (mouse_dx || mouse_dy) {
		float pitch_direction = m_pitch.value > 0 ? -1.0f : 1.0f;
		cl.viewangles[YAW] -= mouse_dx * sensitivity.value * 0.022f;
		cl.viewangles[PITCH] += mouse_dy * sensitivity.value * 0.022f * pitch_direction;
		if (cl.viewangles[PITCH] > 80) cl.viewangles[PITCH] = 80;
		if (cl.viewangles[PITCH] < -70) cl.viewangles[PITCH] = -70;
		mouse_dx = mouse_dy = 0;
	}
}

#define MAX_SDL_CONTROLLERS 4
static SDL_GameController *sdl_controllers[MAX_SDL_CONTROLLERS];
static SDL_GameController *sdl_controller;
#ifdef __ANDROID__
static SDL_Sensor *xziel_android_gyro_sensor = NULL;
#endif

void IN_PlatformSetLightbar(byte red, byte green, byte blue)
{
	if (sdl_controller && SDL_GameControllerHasLED(sdl_controller))
		SDL_GameControllerSetLED(sdl_controller, red, green, blue);
}

qboolean IN_PlatformGetGyro(float *x, float *y)
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
}

void IN_PlatformRumble(unsigned short low_frequency, unsigned short high_frequency, unsigned int duration)
{
	if (sdl_controller)
		SDL_GameControllerRumble(sdl_controller, low_frequency, high_frequency, duration);
}

static void IN_SDLOpenController(int device_index)
{
	int i;
	SDL_GameController *controller;

	if (!SDL_IsGameController(device_index)) return;
	controller = SDL_GameControllerOpen(device_index);
	if (!controller) return;
	for (i = 0; i < MAX_SDL_CONTROLLERS; ++i) {
		if (!sdl_controllers[i]) {
			sdl_controllers[i] = controller;
			if (SDL_GameControllerHasSensor(controller, SDL_SENSOR_GYRO))
				SDL_GameControllerSetSensorEnabled(controller, SDL_SENSOR_GYRO, SDL_TRUE);
			if (!sdl_controller) sdl_controller = controller;
			return;
		}
	}
	SDL_GameControllerClose(controller);
}

void IN_PlatformInit(void)
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
				Con_Printf("Xziel: Android phone gyroscope opened: %s\n",
					SDL_SensorGetName(xziel_android_gyro_sensor));
				break;
			}
		}
	}
#endif
}

void IN_PlatformShutdown(void)
{
	int i;
#ifdef __ANDROID__
	if (xziel_android_gyro_sensor) {
		SDL_SensorClose(xziel_android_gyro_sensor);
		xziel_android_gyro_sensor = NULL;
	}
#endif
	for (i = 0; i < MAX_SDL_CONTROLLERS; ++i) {
		if (sdl_controllers[i]) SDL_GameControllerClose(sdl_controllers[i]);
		sdl_controllers[i] = NULL;
	}
	sdl_controller = NULL;
}

void IN_PlatformCommands(void) {}
void IN_PlatformMove(usercmd_t *cmd) { (void)cmd; }

void IN_GetAnalogStick(in_analog_stick_id_t stick, in_analog_stick_t *value)
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

void IN_SDLControllerAdded(int device_index)
{
	IN_SDLOpenController(device_index);
}

void IN_SDLControllerActivated(SDL_JoystickID instance_id)
{
	int i;
	for (i = 0; i < MAX_SDL_CONTROLLERS; ++i) {
		if (sdl_controllers[i] &&
			SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(sdl_controllers[i])) == instance_id) {
			sdl_controller = sdl_controllers[i];
			return;
		}
	}
}

void IN_SDLControllerRemoved(SDL_JoystickID instance_id)
{
	int i;
	for (i = 0; i < MAX_SDL_CONTROLLERS; ++i) {
		if (sdl_controllers[i] &&
			SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(sdl_controllers[i])) == instance_id) {
			if (sdl_controller == sdl_controllers[i]) sdl_controller = NULL;
			SDL_GameControllerClose(sdl_controllers[i]);
			sdl_controllers[i] = NULL;
			break;
		}
	}
	if (!sdl_controller)
		for (i = 0; i < MAX_SDL_CONTROLLERS; ++i)
			if (sdl_controllers[i]) { sdl_controller = sdl_controllers[i]; break; }
}

class_name CODSourceContract
extends RefCounted

# Canonical first-person measurements from xogot/docs/COD_AUDIT_PORT_CONTRACT.md.
# These are source/audit constants, not tuning knobs.
const PLAYER_STAND_CAPSULE_HEIGHT := 1.76
const PLAYER_RADIUS := 0.36
const PLAYER_STAND_EYE_HEIGHT := 1.60
const PLAYER_CROUCH_CAPSULE_HEIGHT := 1.16
const PLAYER_CROUCH_EYE_HEIGHT := 1.03

const BASE_VERTICAL_FOV := 66.0
const ADS_VERTICAL_FOV := 52.0
const SPRINT_VERTICAL_FOV := 69.0
const SLIDE_VERTICAL_FOV := 70.5

const STANCE_EYE_RESPONSE_HZ := 18.0
const LANDING_SPRING_HZ := 17.0
const SLIDE_ENTRY_PHASE := 0.14
const SLIDE_HOLD_END_PHASE := 0.72
const SLIDE_CAMERA_ROLL_DEG := 1.15

const TOUCH_LOOK_MULTIPLIER := 1.00
const ADS_TOUCH_MULTIPLIER := 0.62
const GYRO_ADS_MULTIPLIER := 0.65
const SNIPER_SENSITIVITY_REFERENCE := 0.42

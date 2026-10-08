extends CharacterBody3D

# Minimal visual-only host for first-person real gun rig in an isolated
# Godot viewport. Source weapon/PSA/GDScript are identical to runtime.
# Avoids importing/rendering the entire zombie scene during 56-frame audit.
func is_ads_active() -> bool:
	return bool(get_meta("ads_toggled", false))

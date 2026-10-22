shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_opaque;

// GAMEPLAY VISUAL REGRESSION: previous "diffuse_toon" shader multiplied very
// dark metal (0.20) by nearly absent cathedral illumination. The resulting
// MP40 was a silhouette even when rendered correctly. Camera viewmodels
// require their own stable, cheap and legible light treatment on Android.
// This uses REAL existing metal/skin/cloth texture UV, not generated photos.
uniform sampler2D source_map : source_color, filter_linear_mipmap;
uniform int surface_role = 0;
uniform vec4 nun_skin : source_color = vec4(0.91, 0.81, 0.80, 1.0);
uniform vec4 habit_black : source_color = vec4(0.12, 0.12, 0.15, 1.0);
uniform vec4 gun_metal : source_color = vec4(0.39, 0.41, 0.45, 1.0);
uniform float ink_strength : hint_range(0.0, 1.0) = 0.36;

void fragment() {
    vec3 source_sample = texture(source_map, UV).rgb;
    float source_luma = clamp(dot(source_sample, vec3(0.299, 0.587, 0.114)), 0.07, 1.0);
    // Keep metal details perceptible while retaining illustrated dark shading.
    float detail_luma = mix(source_luma, floor(source_luma * 8.0 + 0.5) / 8.0, ink_strength);
    vec3 palette = gun_metal.rgb;
    if (surface_role == 1) { palette = nun_skin.rgb; }
    if (surface_role == 2) { palette = habit_black.rgb; }
    if (surface_role == 3) { palette = vec3(0.24, 0.22, 0.23); }
    float readable = max(0.62, 0.55 + detail_luma * 1.1);
    // Cheap stylized normal rim gives form without six dynamic light passes.
    float rim = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), 2.5);
    ALBEDO = clamp(palette * readable + vec3(0.055) * rim, vec3(0.0), vec3(1.0));
    ROUGHNESS = surface_role == 0 ? 0.47 : 0.92;
    METALLIC = 0.0;
}

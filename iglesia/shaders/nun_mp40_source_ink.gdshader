shader_type spatial;
render_mode cull_disabled, diffuse_toon, specular_disabled, depth_draw_opaque;

// The exact recovered MP40 and skeletal hand meshes remain untouched.
// A single coherent Nun palette is applied to every authored animation.
// Role 0 = black metal MP40, 1 = pale skin, 2 = black habit sleeves,
// 3 = muted decorative trims.
// This is an interim gothic 2.5D material, not a photo or new art atlas.
uniform sampler2D source_map : source_color, filter_linear_mipmap;
uniform int surface_role = 0;
uniform vec4 nun_skin : source_color = vec4(0.88, 0.77, 0.75, 1.0);
uniform vec4 habit_black : source_color = vec4(0.065, 0.060, 0.083, 1.0);
uniform vec4 gun_metal : source_color = vec4(0.20, 0.215, 0.245, 1.0);
uniform float ink_strength : hint_range(0.0,1.0) = 0.60;

void fragment() {
    vec3 sampled = texture(source_map, UV).rgb;
    float luminance = clamp(dot(sampled, vec3(0.299,0.587,0.114)),0.06,0.98);
    float ink = floor(luminance*7.0+0.5)/7.0;
    float value = mix(luminance,ink,ink_strength);
    vec3 pigment = gun_metal.rgb;
    if (surface_role == 1) {
        pigment = nun_skin.rgb;
    } else if (surface_role == 2) {
        pigment = habit_black.rgb;
    } else if (surface_role == 3) {
        pigment = vec3(0.20,0.18,0.19);
    }
    ALBEDO = pigment * (0.56 + value);
    ROUGHNESS = surface_role == 0 ? 0.44 : 0.93;
    METALLIC = surface_role == 0 ? 0.27 : 0.0;
    // Readable hands/iron sights even where the cathedral has no direct light.
    EMISSION = ALBEDO * 0.13;
}

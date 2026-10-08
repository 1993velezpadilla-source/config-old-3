shader_type canvas_item;
render_mode unshaded, blend_mix;

// Procedural, original artwork. 2008 WaW used scope_overlay_mp for
// shared scoped-sniper reticle (Mosin / PTRS). Do NOT copy game bitmaps.
// Keep mobile aspect-safe circle and transparent real-camera world center.
void fragment() {
    vec2 pixel = (SCREEN_UV - vec2(0.5)) / SCREEN_PIXEL_SIZE;
    float radius_px = 0.465 / SCREEN_PIXEL_SIZE.y;
    float radial_px = length(pixel);
    float outside = smoothstep(radius_px - 1.5, radius_px + 2.0, radial_px);
    float edge = smoothstep(radius_px - 13.0, radius_px - 1.5, radial_px);
    float opacity = max(outside, 0.78 * edge);
    COLOR = vec4(0.0, 0.0, 0.0, opacity);
}

shader_type canvas_item;
render_mode unshaded;

// First-person playable Nun palette pass: owner reference 1000244682.
// This never fabricates geometry or PNG sprites; it only tones the existing
// approved MP40 atlas toward graphic gothic comic lighting and black habit.
// Glove shapes remain legacy source until a correct bare-hand atlas exists.
uniform float graphic_ink_strength : hint_range(0.0, 1.0) = 0.25;
uniform float habit_cloth_darkening : hint_range(0.0, 1.0) = 0.88;
uniform float pale_skin_shift : hint_range(0.0, 1.0) = 0.23;
uniform vec4 habit_black : source_color = vec4(0.086, 0.080, 0.104, 1.0);
uniform vec4 exposed_skin : source_color = vec4(0.83, 0.72, 0.70, 1.0);

void fragment() {
    vec4 pix = texture(TEXTURE, UV);
    if (pix.a <= 0.003) {
        COLOR = vec4(0.0);
    } else {
        vec3 rgb = pix.rgb;
        float bright = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
        // The gun/ironsights are usually metallic neutral tones. Only cloth-
        // colored regions at the arm perimeter are eligible for the tint.
        float left_arm = 1.0 - smoothstep(0.28, 0.52, UV.x);
        float right_arm = smoothstep(0.75, 0.92, UV.x);
        float arms = max(left_arm, right_arm) * smoothstep(0.38, 0.71, UV.y);
        float olive = smoothstep(0.035, 0.105, rgb.g - rgb.b)
                    * smoothstep(0.015, 0.085, rgb.r - rgb.b)
                    * (1.0 - smoothstep(0.45, 0.70, max(max(rgb.r, rgb.g), rgb.b)));
        float fabric = arms * olive;
        float level = clamp(bright * 1.75 + 0.28, 0.18, 1.0);
        rgb = mix(rgb, habit_black.rgb * level, fabric * habit_cloth_darkening);
        // Retain sculpted exposed fingers; lightly desaturate the warm pixels
        // toward the pale nun reference without recoloring the metal receiver.
        float warm_skin = arms * smoothstep(0.05, 0.15, pix.r - pix.b)
                          * smoothstep(0.015, 0.085, pix.r - pix.g)
                          * smoothstep(0.20, 0.44, pix.r);
        rgb = mix(rgb, exposed_skin.rgb * clamp(bright * 1.55, 0.25, 1.0),
                  warm_skin * pale_skin_shift);
        float output_luma = max(0.001, dot(rgb, vec3(0.2126, 0.7152, 0.0722)));
        float ink_luma = floor(output_luma * 7.0 + 0.5) / 7.0;
        // Graphic shading is deliberately subtle: preserve metal glints and
        // readability of the rear sight alignment in ADS.
        rgb *= mix(1.0, clamp(ink_luma / output_luma, 0.75, 1.17),
                   graphic_ink_strength);
        COLOR = vec4(clamp(rgb, vec3(0.0), vec3(1.0)), pix.a);
    }
}

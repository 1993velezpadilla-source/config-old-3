# XZIEL / NZ:P — Auditoría de gráficos y sistema zombi
**Fecha:** 2026-10-11. **Alcance:** lectura del paquete PC realmente descargado por `scripts/prepare_android.sh`, QuakeC PINNED `8a77f1ce45f1a2b9aa0afb301446954fda40e696`, Vril PINNED `aaa474061bff5d0e3aa471ac01f5f0e01b4fca31`. Sin modificaciones de gameplay. El ZIP completo y el SHA256 están documentados en el artefacto del workflow.

## Resultados binarios — evidencia de la auditoría verde
| Recurso | Triángulos | Vértices | Frames del MDL | Skin incrustada |
|---|---:|---:|---:|---|
| zfull.mdl (zombi completo) | 484 | 389 | 211 | 128×128 |
| zb%.mdl (torso principal) | 331 | 292 | 211 | 128×128 |
| zh^.mdl (cabeza) | 116 | 66 | 211 | 128×128 |
| zal(.mdl (brazo izquierdo) | 59 | 61 | 211 | 128×128 |
| zar(.mdl (brazo derecho) | 59 | 60 | 211 | 128×128 |
| zcfull.mdl (crawler completo) | 416 | 363 | 127 | 128×128 |
| zbc%.mdl (crawler cuerpo) | 261 | 260 | 127 | 128×128 |
| zhc^.mdl (crawler cabeza) | 116 | 66 | 127 | 128×128 |
| zalc(.mdl (crawler brazo izquierdo) | 59 | 61 | 127 | 128×128 |
| zarc(.mdl (crawler brazo derecho) | 59 | 60 | 127 | 128×128 |
| dog.mdl (hellhound) | 554 | 455 | 46 | 256×256 |
| dog_lightning.mdl (efecto spawn) | 90 | 81 | 14 | 32×32 |

**Total:** 12 modelos MDL (10 para zombi/crawler y 2 de hellhound/efecto). Los ficheros de texturas externas en models/ai son 4 variantes `zfull.mdl_0..3.pcx` (128×128) y `dog.mdl_0.pcx` (256×256); los otros cuatro son `.palhint`, NO imágenes. Todos son modelos Quake IDPO v6: animación por cuadros de vértices, no huesos. El formato MDL declara una skin incrustada por archivo, mientras el renderer principal de zombis hace selección de cuatro skins externas por separado.

**Animaciones:** QC usa índices explícitos hasta 210 (zombi), 126 (crawler), 36 (hellhound). Las cabeceras respectivas aportan 211/127/46 cuadros, por tanto las referencias directas están dentro del rango. 211 cuadros **no son 211 clips diferentes**. QuakeC separa caminatas, carreras, ataques, ventanas, saltos/caídas, transformaciones crawler y muertes, y avanza la animación escribiendo `self.frame`. Son necesarios ensayos de sincronización visual, no solo de límites.

**Audio básico incluido:** 45 WAV bajo sounds/zombie y 4 WAV bajo sounds/hound (sin contar otros sonidos auxiliares en otras carpetas).

## Código importante para cualquier mejora HD
1. `quakec/source/server/ai/zombie_core.qc` (pinned): el zombi usa cuerpo, cabeza, dos brazos y hitboxes distintos, desmembramiento y heridas en la cabeza. Conservar esos eventos y el frame index es obligatorio para no perder gameplay. `spawn_a_zombieB` asigna los modelos `zb%.mdl`, `zh^.mdl`, `zal(.mdl`, `zar(.mdl`, e inicializa las skins 0..3.
2. `quakec/source/server/ai/crawler_core.qc` cambia a modelos `zbc%.mdl`, `zhc^.mdl`, `zalc(.mdl`, `zarc(.mdl`. No basta con remodelar solo el zombi de pie.
3. `quakec/source/server/ai/dog_core.qc` tiene walk/run/idle/attack/death + spawn lightning por separado; no es una variante de humano.
4. `vril-engine/source/platform/sdl/gl/gl_rmain.c`: optimización deliberada. Para cuerpos con marcador `%` el motor puede usar `zfull.mdl`/`zcfull.mdl` en vez del cuerpo por piezas, según presencia de miembros y presupuesto de zombies parciales. Las versiones full y segmentadas deben coincidir en frames, UV y escala. El renderer usa pose interpolation; no interpreta rigs Blender/GLB directamente.
5. `vril-engine/source/platform/sdl/gl/gl_rmisc.c`: `R_InitOtherTextures` carga **únicamente `IMAGE_PCX`** para `zfull.mdl_0..3`; no pide PNG/TGA. Solamente instalar imágenes PNG en el paquete no subirá la definición de los zombis. Para una sustitución HD hay que ajustar la ruta de carga (o usar un formato/ruta de override compatible y probada).
6. `vril-engine/source/platform/sdl/gl/gl_model.c`: soporte general para modelos alias con overrides TGA/PCX por modelo; el PCX tiene límites explícitos en `source/images.c`: máximos `xmax<640`, `ymax<480`. No prometer 1024/4096 en el stock PCX loader.
7. `vril-engine/source/platform/sdl/gl/gl_model.h`: `MAXALIASVERTS=2048`, `MAXALIASTRIS=2048`, `MAXALIASFRAMES=256`. Subir un modelo a 10k/30k polígonos **sin ampliar o reemplazar este pipeline** puede fallar al cargar. En `gl_model.c`, los modelos sobre 2048 vértices causan error fatal. Nuestras paredes de iglesia utilizan **XZSM estático**, no prueban que los zombis animados soporten automáticamente mallas HD 4K/50k tris.
8. `vril-engine/source/platform/sdl/gl/gl_rmain.c`: render de alias aún basado en GL fixed-function, vertex normals/lightcolor, `GL_MODULATE`, `gl_smoothmodels`, optimización especial `doZHack`. No hay evidencia de PBR, normal maps o esqueletos para zombie MDL en la ruta actual.

## Diagnóstico de calidad
**Principal:** el cuello de botella visual se concentra en mallas de 484 tris (full) / 331 cuerpo y skins de 128×128, y no en potencia demostrada del teléfono. Para que parezcan modernos habría que reconstruir la superficie o añadir un renderer de zombis animados moderno.

**Riesgos antes de retexturizar:** recalculado UV, 4 variantes, compatibilidad `full` vs miembros segmentados, sincronización 211/127 frames, desmembramiento y hitbox, LOD de muchos zombis, GPU coste de malla animada, sangrado/iluminación, z-fighting y GL states después del mapa.

**Secuencia de experimentos sugerida, SIN implementar:** 
- Gate 0: Dead Cell stock, capturas cerca del zombi y rendimiento como referencia.
- Gate 1: retextura de 1 zombi (mismo MDL 484/211, cuatro imágenes nuevas 512px) usando ruta de carga nueva; comparar UV, cara, manos y brillo.
- Gate 2: nuevos MDL compatibles sin aumentar límites, con sus 211 cuadros y versiones cuerpo/miembros y crawler.
- Gate 3: solo si calidad insuficiente, nuevo formato para meshes *dinámicos* con animación e instancing/LOD y límites de memoria. XZSM actual es estático, no es reemplazo directo para entidades animadas.
- Gate 4: 1, 5, 10, 20+ zombis simultáneos, caminar/correr/golpear/ventanas/caídas/muerte/decapitación, fps/ram y audio.

### Estado comprobado
La auditoría del **formato y los recursos descargados está GREEN**; **la fidelidad en Android y los cambios HD todavía no están implementados ni aprobados**. Dead Cell y el juego funcional NO han sido alterados. Los hashes, la lista de los assets y el informe legible se encuentran en el artefacto `XZIEL-NZP-Zombie-Visual-Audit-MDL-Skins-Frames-Sounds` de GitHub Actions.

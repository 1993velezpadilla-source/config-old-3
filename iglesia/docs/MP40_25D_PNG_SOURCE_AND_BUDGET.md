# Iglesia — MP40 y monja enemiga PNG 2.5D (22 octubre 2026)

**Autoridad única:** `iglesia/`. El mapa y las colisiones son 3D; la MP40 en primera persona y el enemigo son imágenes RGBA 2D. Esta rama no dibuja ni importa el viejo MP40 de soldado, la primera lámina PNG rechazada, manos T4 Marine, GLB de pistola, BoneAttachment3D, ni la monja rectangular. El resto del repositorio se mantiene intacto.

## Lo que existe y lo que falta

- Implementado: compositor PNG de MP40 centrado en cámara, disparo, ADS, recarga que continúa durante sprint, perfiles 12/15/24 cuadros, movimiento de cámara ligero, controles táctiles existentes.
- Implementado: enemigo billboard `Sprite3D` con secuencias idle/walk/attack/death compatibles con clip cache compartida. La colisión, navegación y daño no cambian.
- **FALTAN los nuevos PNGs aprobados.** Sin arte, el sistema muestra `ART_BLOCKER`, no recicla el arma del soldado ni simula que terminó el arte. La ausencia de una captura auténtica del Pixel Fold también sigue pendiente.
- `Forgive Me Father 2` es **referencia de dirección artística**. No se afirmará un número de cuadros oficial: no hay máximo por arma públicamente confirmado.

## Nombres exactos de imágenes que debe recibir Godot

Carpeta arma: `iglesia/assets/weapons/mp40_nun_2d/`. Todas las imágenes deben tener **exactamente la misma anchura/altura/canvas/posición base y perspectiva** para evitar salto entre cuadros. La MP40, dos manos femeninas pálidas con dedos descubiertos, mangas negras rasgadas de hábito y sombras de tinta se dibujan EN CADA pose. Fondo transparente RGBA. **Máximo 768×512** por cuadro.

| Acción | 12 cuadros | 15 cuadros (default) | 24 cuadros |
|---|---:|---:|---:|
| idle | 1 | 1 | 1 |
| ads_idle | 1 | 1 | 1 |
| fire | 2 | 2 | 4 |
| ads_fire | 1 | 2 | 3 |
| reload | 5 | 7 | 12 |
| sprint | 1 | 1 | 1 |
| equip | 1 | 1 | 2 |
| **Total** | **12** | **15** | **24** |

Ejemplos: `idle_00.png`, `fire_00.png`, `fire_01.png`, `reload_00.png`… `reload_06.png`. Los 15 cuadros por defecto son un **presupuesto nuestro**, no datos oficiales del videojuego comercial. `equip` queda preparado para futuros cambios de arma.

Carpeta monja: `iglesia/assets/enemies/gothic_nun_2d/`: `idle_00.png`, `walk_00.png`, `attack_00.png`, `death_00.png` con secuencias `_01, _02`… hasta 24; el código comparte las mismas texturas entre todos los zombis, sin duplicar imágenes en GPU por cada enemigo. Animación temporal 8 fps caminar, 6 fps atacar. Debe coincidir con el personaje aprobado; nada de rectángulos.

## GIF sí, pero solamente como formato intermedio

Se pueden dibujar cuadros y exportarlos como GIF/APNG por acción, después ejecutar:

```bash
python3 iglesia/tools/import_gif_sprite.py --source ./art/reload.gif --role reload --profile 15
```

El importador exige 7 cuadros de `reload` para el perfil 15, RGBA transparente y tamaño máximo. Copia los fotogramas como `reload_00.png` … `reload_06.png`; el juego **nunca reproduce un GIF**. Exportar PNG directamente desde el programa de dibujo suele preservar mejor el color y alfa que GIF, limitado a 256 colores.

## Presupuesto RAM/GPU y prueba en el Pixel Fold

A 768×512 por cuadro RGBA8 sin comprimir, el presupuesto teórico es **18.0 MiB (12)** / **22.5 MiB (15)** / **36.0 MiB (24)**. Texturas importadas, mipmaps, atlas y drivers pueden alterar estos valores. Cargar solo el cuadro visible no garantiza ahorro si todas las texturas fueron precargadas; este sistema carga únicamente los cuadros del perfil elegido.

En el APK debug, pulsa el rótulo `SPRITES 15` bajo VIDA para alternar 12 → 15 → 24. Los logs `IGLESIA_SPRITE_PROFILE` y `IGLESIA_ANDROID_PERF_SAMPLE` incluyen perfil, cuadros faltantes, estimación RGBA y FPS reales. Para comparar RAM justa, **reinicia la APK entre perfiles**: ResourceLoader y el driver pueden conservar caché. El test de FPS objetivo requiere **10 zombis durante 2 minutos en un Pixel Fold real**. GitHub Actions solo ejecuta smoke y exportación, no un benchmark real de teléfono.

**Gate final RED** hasta: 15 imágenes reales MP40, monja original con movimiento y ataque, comprobación visual auténtica y FPS mínimo 30 en Pixel Fold. No se pueden aprobar imágenes provisionales solo por pasar los tests de código.

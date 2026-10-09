/**
 * Tripo Studio scene exporter (standalone).
 * Run from DevTools Console on a Tripo Studio model page that you own or are
 * authorized to export. Does not call Tripo's export API; it serializes the
 * geometry already present in the browser's Three.js scene into a GLB.
 */
(async function tripoSceneExporter() {
  'use strict';

  const log = (...args) => console.log('[tripo-scene-exporter]', ...args);
  const warn = (...args) => console.warn('[tripo-scene-exporter]', ...args);
  const fail = (message) => { throw new Error(`[tripo-scene-exporter] ${message}`); };
  const align4 = (n) => (n + 3) & ~3;

  function locateVueApp() {
    const roots = [
      document.querySelector('[data-v-app]'),
      document.querySelector('#__nuxt'),
      document.body,
    ].filter(Boolean);
    for (const el of roots) {
      if (el.__vue_app__) return el.__vue_app__;
    }
    fail('Vue app not found. Open a studio.tripo3d.ai model page first.');
  }

  function walkVNode(vnode, visit, depth = 0, seen = new Set()) {
    if (!vnode || depth > 80 || typeof vnode !== 'object' || seen.has(vnode)) return null;
    seen.add(vnode);
    if (vnode.component) {
      const hit = visit(vnode.component);
      if (hit) return hit;
      const nested = walkVNode(vnode.component.subTree, visit, depth + 1, seen);
      if (nested) return nested;
    }
    const children = Array.isArray(vnode.children) ? vnode.children : [];
    for (const child of children) {
      const hit = walkVNode(child, visit, depth + 1, seen);
      if (hit) return hit;
    }
    return null;
  }

  function locateThreeScene(vueApp) {
    const router = vueApp.config?.globalProperties?.$router;
    const route = router?.currentRoute?.value;
    const candidates = [];
    for (const record of route?.matched || []) {
      for (const inst of Object.values(record.instances || {})) {
        if (inst?._?.subTree) candidates.push(inst._.subTree);
        else if (inst?.subTree) candidates.push(inst.subTree);
      }
    }
    if (vueApp._instance?.subTree) candidates.push(vueApp._instance.subTree);

    for (const tree of candidates) {
      const found = walkVNode(tree, (inst) => {
        const provides = inst?.provides;
        if (!provides) return null;
        for (const value of Object.values(provides)) {
          const scene = value?.scene?.value ?? value?.scene;
          if (scene?.isScene) return scene;
        }
        const direct = provides.useTres;
        const scene = direct?.scene?.value ?? direct?.scene;
        return scene?.isScene ? scene : null;
      });
      if (found) return found;
    }
    fail('Three.js scene not found in Vue/TresJS component tree.');
  }

  function collectMeshes(root) {
    const meshes = [];
    root.traverse?.((obj) => {
      if (!obj?.isMesh || !obj.geometry?.attributes?.position) return;
      if (obj.visible === false) return;
      const count = obj.geometry.attributes.position.count || 0;
      if (count > 0) meshes.push(obj);
    });
    return meshes;
  }

  function choosePrimaryMesh(meshes) {
    if (!meshes.length) fail('No visible mesh with positions found in scene.');
    const score = (mesh) => {
      const pos = mesh.geometry?.attributes?.position?.count || 0;
      const idx = mesh.geometry?.index?.count || 0;
      const nameBoost = /tripo|model|mesh/i.test(mesh.name || '') ? 1.05 : 1;
      return (Math.max(pos, idx / 3) || 0) * nameBoost;
    };
    return meshes.reduce((best, mesh) => score(mesh) > score(best) ? mesh : best, meshes[0]);
  }

  function readVecAttribute(attr, itemSize) {
    if (!attr) return null;
    const out = new Float32Array(attr.count * itemSize);
    for (let i = 0; i < attr.count; i++) {
      if (itemSize >= 1) out[i * itemSize] = attr.getX ? attr.getX(i) : attr.array[i * itemSize];
      if (itemSize >= 2) out[i * itemSize + 1] = attr.getY ? attr.getY(i) : attr.array[i * itemSize + 1];
      if (itemSize >= 3) out[i * itemSize + 2] = attr.getZ ? attr.getZ(i) : attr.array[i * itemSize + 2];
      if (itemSize >= 4) out[i * itemSize + 3] = attr.getW ? attr.getW(i) : attr.array[i * itemSize + 3];
    }
    return out;
  }

  function bakeWorldPositions(mesh, localPositions) {
    mesh.updateWorldMatrix?.(true, false);
    const e = mesh.matrixWorld?.elements;
    if (!e || e.length !== 16) return localPositions;
    const out = new Float32Array(localPositions.length);
    for (let i = 0; i < localPositions.length; i += 3) {
      const x = localPositions[i], y = localPositions[i + 1], z = localPositions[i + 2];
      out[i]     = e[0] * x + e[4] * y + e[8]  * z + e[12];
      out[i + 1] = e[1] * x + e[5] * y + e[9]  * z + e[13];
      out[i + 2] = e[2] * x + e[6] * y + e[10] * z + e[14];
    }
    return out;
  }

  function normalizeIndices(indexAttr) {
    if (!indexAttr) return null;
    const src = indexAttr.array;
    if (!src) return null;
    let max = 0;
    for (let i = 0; i < src.length; i++) max = Math.max(max, src[i]);
    return max <= 65535 ? new Uint16Array(src) : new Uint32Array(src);
  }

  async function textureToPngBytes(texture) {
    const image = texture?.image;
    if (!image) return null;
    const width = image.width || image.videoWidth || image.naturalWidth || 0;
    const height = image.height || image.videoHeight || image.naturalHeight || 0;
    if (!width || !height) return null;

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return null;

    ctx.translate(0, height);
    ctx.scale(1, -1);
    ctx.drawImage(image, 0, 0, width, height);

    const blob = await new Promise((resolve, reject) =>
      canvas.toBlob((b) => b ? resolve(b) : reject(new Error('PNG encoding failed')), 'image/png')
    );
    return new Uint8Array(await blob.arrayBuffer());
  }

  function aabb(positions) {
    const min = [Infinity, Infinity, Infinity];
    const max = [-Infinity, -Infinity, -Infinity];
    for (let i = 0; i < positions.length; i += 3) {
      for (let a = 0; a < 3; a++) {
        const v = positions[i + a];
        if (v < min[a]) min[a] = v;
        if (v > max[a]) max[a] = v;
      }
    }
    return { min, max };
  }

  const vueApp = locateVueApp();
  const scene = locateThreeScene(vueApp);
  const meshes = collectMeshes(scene);
  const mesh = choosePrimaryMesh(meshes);
  log(`scene=${scene.type || 'Scene'} meshes=${meshes.length}`);
  log(`primary mesh="${mesh.name || '(unnamed)'}" vertices=${mesh.geometry.attributes.position.count}`);

  const positionsLocal = readVecAttribute(mesh.geometry.attributes.position, 3);
  const positions = bakeWorldPositions(mesh, positionsLocal);
  const uvs = readVecAttribute(mesh.geometry.attributes.uv, 2);
  const indices = normalizeIndices(mesh.geometry.index);

  const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
  if (Array.isArray(mesh.material) && mesh.material.length > 1) {
    warn('Primary mesh has multiple materials; v1 exports the first material only.');
  }
  const textureBytes = await textureToPngBytes(material?.map);
  if (!textureBytes) warn('No readable base-color texture found; exporting geometry only.');

  const chunks = [];
  let binSize = 0;
  function addChunk(bytes, target) {
    if (!bytes) return null;
    const offset = align4(binSize);
    binSize = offset + align4(bytes.byteLength);
    const idx = chunks.length;
    chunks.push({ bytes: new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength), offset, target });
    return idx;
  }

  const posChunk = addChunk(new Uint8Array(positions.buffer), 34962);
  const uvChunk = uvs ? addChunk(new Uint8Array(uvs.buffer), 34962) : null;
  const idxChunk = indices ? addChunk(new Uint8Array(indices.buffer), 34963) : null;
  const texChunk = textureBytes ? addChunk(textureBytes, null) : null;

  const bufferViews = chunks.map((c) => ({
    buffer: 0,
    byteOffset: c.offset,
    byteLength: c.bytes.byteLength,
    ...(c.target ? { target: c.target } : {}),
  }));
  const accessors = [];
  const attrs = {};
  const bounds = aabb(positions);

  attrs.POSITION = accessors.length;
  accessors.push({ bufferView: posChunk, componentType: 5126, count: positions.length / 3, type: 'VEC3', min: bounds.min, max: bounds.max });
  if (uvs) {
    attrs.TEXCOORD_0 = accessors.length;
    accessors.push({ bufferView: uvChunk, componentType: 5126, count: uvs.length / 2, type: 'VEC2' });
  }

  let indexAccessor = null;
  if (indices) {
    indexAccessor = accessors.length;
    accessors.push({
      bufferView: idxChunk,
      componentType: indices instanceof Uint16Array ? 5123 : 5125,
      count: indices.length,
      type: 'SCALAR',
    });
  }

  const primitive = { attributes: attrs, mode: 4 };
  if (indexAccessor !== null) primitive.indices = indexAccessor;
  if (textureBytes) primitive.material = 0;

  const color = material?.color;
  const opacity = Number.isFinite(material?.opacity) ? material.opacity : 1;
  const baseColorFactor = [color?.r ?? 1, color?.g ?? 1, color?.b ?? 1, opacity];

  const gltf = {
    asset: { version: '2.0', generator: 'xz-tripo-scene-exporter-v1' },
    scene: 0,
    scenes: [{ nodes: [0], name: 'Scene' }],
    nodes: [{ mesh: 0, name: mesh.name || 'tripo_model' }],
    meshes: [{ name: mesh.name || 'tripo_mesh', primitives: [primitive] }],
    accessors,
    bufferViews,
    buffers: [{ byteLength: align4(binSize) }],
  };

  if (textureBytes) {
    gltf.images = [{ bufferView: texChunk, mimeType: 'image/png', name: 'baseColor' }];
    gltf.samplers = [{ magFilter: 9729, minFilter: 9987, wrapS: 10497, wrapT: 10497 }];
    gltf.textures = [{ sampler: 0, source: 0 }];
    gltf.materials = [{
      name: material?.name || 'tripo_material',
      pbrMetallicRoughness: {
        baseColorFactor,
        baseColorTexture: { index: 0, texCoord: 0 },
        metallicFactor: Number.isFinite(material?.metalness) ? material.metalness : 0,
        roughnessFactor: Number.isFinite(material?.roughness) ? material.roughness : 0.5,
      },
      doubleSided: true,
      ...(opacity < 1 ? { alphaMode: 'BLEND' } : {}),
    }];
  }

  const jsonBytes = new TextEncoder().encode(JSON.stringify(gltf));
  const jsonLen = align4(jsonBytes.byteLength);
  const binLen = align4(binSize);
  const total = 12 + 8 + jsonLen + 8 + binLen;
  const glb = new ArrayBuffer(total);
  const dv = new DataView(glb);
  const out = new Uint8Array(glb);
  let off = 0;

  dv.setUint32(off, 0x46546c67, true); off += 4;
  dv.setUint32(off, 2, true); off += 4;
  dv.setUint32(off, total, true); off += 4;
  dv.setUint32(off, jsonLen, true); off += 4;
  dv.setUint32(off, 0x4e4f534a, true); off += 4;
  out.set(jsonBytes, off);
  out.fill(0x20, off + jsonBytes.byteLength, off + jsonLen);
  off += jsonLen;

  dv.setUint32(off, binLen, true); off += 4;
  dv.setUint32(off, 0x004e4942, true); off += 4;
  const binStart = off;
  for (const chunk of chunks) out.set(chunk.bytes, binStart + chunk.offset);

  if (dv.getUint32(0, true) !== 0x46546c67) fail('GLB header validation failed.');
  if (dv.getUint32(8, true) !== total) fail('GLB length validation failed.');

  const modelId = location.pathname.split('/').filter(Boolean).pop() || 'model';
  const filename = `tripo_${modelId}.glb`;
  const blob = new Blob([glb], { type: 'model/gltf-binary' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 15000);

  const result = {
    filename,
    sizeMB: Number((blob.size / 1024 / 1024).toFixed(2)),
    meshName: mesh.name || '',
    vertices: positions.length / 3,
    indices: indices?.length || 0,
    textured: Boolean(textureBytes),
    sourceMeshesSeen: meshes.length,
  };
  log('DONE', result);
  return result;
})();
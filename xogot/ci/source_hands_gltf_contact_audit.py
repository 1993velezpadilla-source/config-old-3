#!/usr/bin/env python3
"""Source-authoritative WaW ActorX glTF wrist-to-gun socket audit.
Reads original GLB PSA bone tracks; no guessed transforms, retarget or pose edits.
"""
import json
import math
import pathlib
import struct
import sys

PROJECT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = PROJECT / 'assets/weapons/mapmod_weapon_asset_manifest.json'
MAX_TRIGGER_WRIST_TO_SOURCE_SOCKET_M = 0.50

def original_glb(path):
    binary = path.read_bytes()
    if binary[:4] != b'glTF':
        raise ValueError('source GLB magic invalid: ' + str(path))
    chunk_len, chunk_type = struct.unpack_from('<II', binary, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError('missing GLB JSON chunk')
    doc = json.loads(binary[20:20 + chunk_len])
    offset = 20 + chunk_len
    bin_len, bin_type = struct.unpack_from('<II', binary, offset)
    if bin_type != 0x004E4942:
        raise ValueError('missing GLB binary chunk')
    return doc, memoryview(binary)[offset + 8:offset + 8 + bin_len]

def first_key(doc, binary, accessor_index):
    accessor = doc['accessors'][accessor_index]
    if accessor['componentType'] != 5126:
        raise ValueError('original PSA accessor is not FLOAT32')
    components = {'VEC3': 3, 'VEC4': 4}[accessor['type']]
    view = doc['bufferViews'][accessor['bufferView']]
    off = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    return struct.unpack_from('<' + ('f' * components), binary, off)

def mul_quaternion(a, b):
    x1, y1, z1, w1 = a
    x2, y2, z2, w2 = b
    return (w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2,
            w1*w2 - x1*x2 - y1*y2 - z1*z2)

def rotate(q, v):
    x, y, z, w = q
    p = (v[0], v[1], v[2], 0.0)
    r = mul_quaternion(mul_quaternion(q, p), (-x, -y, -z, w))
    return r[:3]

def source_wrist_distances(doc, binary):
    nodes = doc['nodes']
    clips = [a for a in doc['animations'] if 'idle' in a.get('name', '').lower()]
    if len(clips) != 1:
        raise ValueError('expected one authentic idle PSA; got ' + str([a.get('name') for a in clips]))
    clip = clips[0]
    overrides = {}
    for ch in clip['channels']:
        target = ch['target']
        role = target['path']
        if role not in ('translation', 'rotation', 'scale'):
            continue
        sampler = clip['samplers'][ch['sampler']]
        overrides.setdefault(target['node'], {})[role] = first_key(doc, binary, sampler['output'])
    parents = {}
    for i, node in enumerate(nodes):
        for child in node.get('children', []):
            parents[child] = i
    cached = {}
    def world(i):
        if i in cached:
            return cached[i]
        node = nodes[i]
        p = overrides.get(i, {})
        xyz = p.get('translation', node.get('translation', (0., 0., 0.)))
        quat = p.get('rotation', node.get('rotation', (0., 0., 0., 1.)))
        scale = p.get('scale', node.get('scale', (1., 1., 1.)))
        if i in parents:
            parent_xyz, parent_q, parent_s = world(parents[i])
            rotated = rotate(parent_q, tuple(a * b for a, b in zip(xyz, parent_s)))
            result = (tuple(a + b for a, b in zip(parent_xyz, rotated)),
                      mul_quaternion(parent_q, quat),
                      tuple(a * b for a, b in zip(parent_s, scale)))
        else:
            result = (tuple(xyz), tuple(quat), tuple(scale))
        cached[i] = result
        return result
    by_name = {node.get('name'): i for i, node in enumerate(nodes)}
    names = ['tag_weapon', 'j_wrist_ri', 'j_wrist_le']
    if not all(name in by_name for name in names):
        raise ValueError('source skeleton missing mandatory source hand socket/wrists')
    points = {name: world(by_name[name])[0] for name in names}
    if not all(math.isfinite(v) for point in points.values() for v in point):
        raise ValueError('nonfinite original source bone position')
    distances = {side: math.dist(points['tag_weapon'], points['j_wrist_' + side])
                 for side in ('ri', 'le')}
    return distances, clip['name'], len(doc['skins'][0]['joints'])

def main():
    manifest = json.loads(MANIFEST.read_text())
    # The manifest also contains three developer/legacy entries. Audit the
    # exact same 28 shipping WaW firearm IDs as Godot's FIREARMS constant.
    ids = [
        'colt','walther','nambu','tt33','357','mp40','thompson',
        'ppsh','type100','stg','m1','m1a1','gewehr','svt40',
        'arisaka','kar98k','springfield','mosin','ptrs','trench',
        'doublebarrel','sawnoff','bar','fg42','mg42','browning',
        'dp28','type99'
    ]
    if len(ids) != 28 or len(set(ids)) != 28:
        raise ValueError('canonical 28 original source gun IDs invalid')
    if any(gun not in manifest['weapons'] for gun in ids):
        raise ValueError('canonical source weapon absent from manifest')
    failures = []
    for gun in sorted(ids):
        hands = manifest['weapons'][gun].get('runtime', {}).get('hands', '')
        if not hands.startswith('res://'):
            failures.append(gun + ':source_hands_missing')
            continue
        path = PROJECT / hands[6:]
        try:
            doc, binary = original_glb(path)
            distances, source_clip, joints = source_wrist_distances(doc, binary)
            print('XZOGOT_ORIGINAL_SOURCE_HANDS_CONTACT', gun,
                  'source_clip=' + source_clip,
                  'trigger_wrist_to_animated_tag_weapon_m=%.4f' % distances['ri'],
                  'support_wrist_to_animated_tag_weapon_m=%.4f' % distances['le'],
                  'source_bones=' + str(joints))
            if joints != 113:
                failures.append(gun + ':source_113_bones_missing')
            if distances['ri'] > MAX_TRIGGER_WRIST_TO_SOURCE_SOCKET_M:
                failures.append(gun + ':original_trigger_wrist_disconnected_m=%.4f' % distances['ri'])
        except (OSError, KeyError, IndexError, ValueError, TypeError, struct.error) as error:
            failures.append(gun + ':original_asset_unreadable:' + str(error))
    print('XZOGOT_SOURCE_HANDS_GLTF_28_INSPECTED',len(ids))
    print('XZOGOT_SOURCE_HANDS_GLTF_WRIST_BLOCKERS',json.dumps(failures))
    if failures:
        print('XZOGOT_SOURCE_HANDS_GLTF_GRIP_ACCEPTANCE_RED',len(failures))
        return 3
    print('XZOGOT_SOURCE_HANDS_GLTF_ORIENTATION_ONLY_GREEN_VISUAL_APPROVAL_STILL_REQUIRED')
    return 0

if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""从 SAR/RCS 的 .cst 提取 .sab, 并在内存中分析 (复用 batch_sab 逻辑)"""
import os, struct, collections
from cst_parser import find_eocd, parse_central_directory, read_entry

def extract_sab(path):
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        window = min(size, 65535 + 22)
        f.seek(size - window)
        tail = f.read(window)
        eocd_in_tail, cd_off, cd_size, count, comment = find_eocd(tail, size)
        f.seek(cd_off)
        cd_data = f.read(cd_size)
        entries = parse_central_directory(cd_data, count)
        sabs = {}
        for e in entries:
            if e['name'].lower().endswith('.sab'):
                content, crc_ok, _ = read_entry(f, e)
                sabs[e['name']] = content
    return sabs

def find_segments(data):
    pos = []
    idx = data.find(b'ACIS BinaryFile')
    while idx != -1:
        pos.append(idx)
        idx = data.find(b'ACIS BinaryFile', idx + 1)
    return pos

def parse_header(data, start):
    pos = start + 15
    version = data[pos]; pos += 1
    extra = data[pos:pos+15]; pos += 15
    h = {'version': version}
    for key in ('product_id', 'acis_version', 'date'):
        ln = data[pos+1]
        h[key] = data[pos+2:pos+2+ln].decode('latin1')
        pos += 2 + ln
    for key in ('mm_per_unit', 'resabs', 'resnor'):
        h[key] = struct.unpack('<d', data[pos+1:pos+9])[0]
        pos += 9
    pos += 1  # 0x0a
    ln = data[pos+1]
    h['uuid'] = data[pos+2:pos+2+ln].decode('latin1')
    pos += 2 + ln
    if data[pos] == 0x04:
        vals = [struct.unpack('<I', data[pos+1+i*5:pos+5+i*5])[0] for i in range(3)]
        h['tail_uints'] = vals
        pos += 15
        if data[pos] == 0x0a:
            pos += 1
    return h, pos

def scan_segment(data, start, type_names):
    pos = start
    entities = []
    points = []

    def parse_chain(p):
        chain = []
        while True:
            t = data[p]
            if t not in (0x0d, 0x0e):
                raise ValueError(f'@{p} 链标签 {t:02x}')
            ln = data[p+1]
            payload = data[p+2:p+2+ln]
            if payload == b'End-of-ACIS-data':
                return ('END',), p + 2 + ln
            tid = struct.unpack('<i', payload[-4:])[0]
            name = payload[:-5].decode('latin1') if ln > 5 else None
            if name is not None:
                type_names[tid] = name
            chain.append((t, name, tid))
            p += 2 + ln
            if t == 0x0d:
                return chain, p

    while pos < len(data) - 16:
        tag = data[pos]
        if tag == 0x0b:
            pos += 1
        elif tag in (0x0a, 0x0f, 0x10, 0x11):
            pos += 1
            if data[pos] in (0x0d, 0x0e):
                r = parse_chain(pos)
                if r[0] == ('END',):
                    return entities, points
                chain, pos = r
                entities.append(chain)
        elif tag in (0x0d, 0x0e):
            r = parse_chain(pos)
            if r[0] == ('END',):
                return entities, points
            chain, pos = r
            entities.append(chain)
        elif tag == 0x07:
            ln = data[pos+1]; pos += 2 + ln
        elif tag in (0x04, 0x0c, 0x15):
            pos += 5
        elif tag == 0x19:
            pos += 3
        elif tag == 0x06:
            pos += 9
        elif tag == 0x13:
            points.append(struct.unpack('<3d', data[pos+1:pos+25])); pos += 25
        elif tag == 0x14:
            pos += 25
        else:
            pos += 1
    return entities, points

def chain_typename(chain, type_names):
    for t, n, tid in chain:
        if n:
            return n
    return type_names.get(chain[0][2], f'#{chain[0][2]}')

def analyze(data):
    seg_starts = find_segments(data)
    type_names = {}
    out = []
    for sstart in seg_starts:
        h, epos = parse_header(data, sstart)
        ents, pts = scan_segment(data, epos, type_names)
        tc = collections.Counter(chain_typename(c, type_names) for c in ents)
        bbox = None
        if pts:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
            bbox = {'x': [min(xs), max(xs)], 'y': [min(ys), max(ys)], 'z': [min(zs), max(zs)]}
        out.append({'header': h, 'entities': len(ents), 'types': dict(tc),
                    'points': len(pts), 'bbox': bbox})
    return out

for cst in [r'D:\training\cst\RCS of a Ship.cst',
            r'D:\training\cst\SAR Head Hand and Phone.cst']:
    print('#' * 72)
    print(f'提取 {os.path.basename(cst)} 的 .sab ...')
    sabs = extract_sab(cst)
    for name, data in sabs.items():
        print('=' * 72)
        print(f'  {name}  ({len(data)} 字节, {len(find_segments(data))} 段)')
        for si, seg in enumerate(analyze(data)):
            h = seg['header']
            tag = '主段' if si == 0 else f'嵌入{si}'
            print(f'    [{tag}] ver={h["version"]}  产品={h["product_id"]}  ACIS={h["acis_version"]}')
            if 'tail_uints' in h:
                print(f'          尾部uint={h["tail_uints"]}')
            print(f'          实体={seg["entities"]}  point={seg["points"]}')
            if seg['bbox']:
                b = seg['bbox']
                print(f'          bbox X:[{b["x"][0]:.2f},{b["x"][1]:.2f}] Y:[{b["y"][0]:.2f},{b["y"][1]:.2f}] Z:[{b["z"][0]:.2f},{b["z"][1]:.2f}]')
            if si == 0:
                top = list(seg['types'].items())[:16]
                print(f'          类型: ' + ', '.join(f'{k}:{v}' for k, v in top))

# -*- coding: utf-8 -*-
"""批量分析 SAB (v2) - 支持多段容器 / 新旧头部 / End-of-ACIS-data 结束标记

新理解:
  1. 头部版本字段: 0x1c(28)=旧版完整模型, 0x80(128)=新版缓存
  2. 旧版头部尾部有 3 个 uint(实体数等), 新版无(直接实体流)
  3. 新版 ModelCache 是多段容器: 主段 + 多个嵌入 SAB 段(bbox 缓存)
  4. 每段以 `0d 10 "End-of-ACIS-data"` 结尾 (无 25+id)
"""
import struct, collections, glob, os

def find_segments(data):
    """返回所有 'ACIS BinaryFile' magic 的位置"""
    pos = []
    idx = data.find(b'ACIS BinaryFile')
    while idx != -1:
        pos.append(idx)
        idx = data.find(b'ACIS BinaryFile', idx + 1)
    return pos

def parse_header(data, start):
    """解析一个 SAB 段的头部, 返回 (header, pos). pos 指向实体流起始"""
    assert data[start:start+15] == b'ACIS BinaryFile'
    pos = start + 15
    version = data[pos]; pos += 1
    extra = data[pos:pos+15]; pos += 15
    h = {'version': version, 'extra_hex': extra.hex()}
    for key in ('product_id', 'acis_version', 'date'):
        if data[pos] != 0x07:
            raise ValueError(f'头部字符串标签 @{pos} = {data[pos]:02x}')
        ln = data[pos+1]
        h[key] = data[pos+2:pos+2+ln].decode('latin1')
        pos += 2 + ln
    for key in ('mm_per_unit', 'resabs', 'resnor'):
        if data[pos] != 0x06:
            raise ValueError(f'头部 double 标签 @{pos} = {data[pos]:02x}')
        h[key] = struct.unpack('<d', data[pos+1:pos+9])[0]
        pos += 9
    # 0x0a 分隔
    sep = data[pos]; pos += 1
    # uuid
    ln = data[pos+1]
    h['uuid'] = data[pos+2:pos+2+ln].decode('latin1')
    pos += 2 + ln
    # 旧版: 3 个 uint; 新版: 直接实体流
    if data[pos] == 0x04:
        vals = []
        for _ in range(3):
            vals.append(struct.unpack('<I', data[pos+1:pos+5])[0])
            pos += 5
        h['tail_uints'] = vals
        if data[pos] == 0x0a:
            pos += 1
    return h, pos

def scan_segment(data, start, type_names):
    """扫描一个段的实体流 (从 start 到 End-of-ACIS-data), 返回实体列表"""
    pos = start
    entities = []
    field_count = collections.Counter()
    points = []
    unknown = collections.Counter()

    def parse_chain(p):
        chain = []
        while True:
            t = data[p]
            if t not in (0x0d, 0x0e):
                raise ValueError(f'@{p} 链标签 {t:02x}')
            ln = data[p+1]
            payload = data[p+2:p+2+ln]
            # End-of-ACIS-data 结束标记 (无 25+id)
            if payload == b'End-of-ACIS-data':
                return ('END',), p + 2 + ln
            if ln == 4:
                # 短引用编码 (ACIS 28.x): <int32 id>, 无 25 前缀, 单元素链(隐式链尾)
                tid = struct.unpack('<i', payload)[0]
                name = None
                chain.append((t, name, tid))
                p += 2 + ln
                return chain, p
            else:
                if ln >= 5 and payload[-5] == 0x25:
                    # 标准编码: <name?> 25 <int32 id>
                    tid = struct.unpack('<i', payload[-4:])[0]
                    name = payload[:-5].decode('latin1') if ln > 5 else None
                elif ln == 5 and payload[0] == 0x04:
                    # 整数符号引用: 04 <uint32 val> (空符号=0), 单元素链
                    tid = struct.unpack('<I', payload[1:5])[0]
                    name = None
                    chain.append((t, name, tid))
                    p += 2 + ln
                    return chain, p
                else:
                    raise ValueError(f'@{p} 异常类型链 (ln={ln}): {payload[:12]!r}')
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
                    return entities, field_count, points, unknown, pos
                chain, pos = r
                entities.append(chain)
        elif tag in (0x0d, 0x0e):
            r = parse_chain(pos)
            if r[0] == ('END',):
                return entities, field_count, points, unknown, pos
            chain, pos = r
            entities.append(chain)
        elif tag == 0x07:
            ln = data[pos+1]; field_count['str'] += 1; pos += 2 + ln
        elif tag == 0x04:
            field_count['uint'] += 1; pos += 5
        elif tag == 0x0c:
            field_count['int'] += 1; pos += 5
        elif tag == 0x15:
            field_count['uint2'] += 1; pos += 5
        elif tag == 0x19:
            field_count['int16'] += 1; pos += 3
        elif tag == 0x06:
            field_count['double'] += 1; pos += 9
        elif tag == 0x13:
            v = struct.unpack('<3d', data[pos+1:pos+25])
            points.append(v); field_count['pos'] += 1; pos += 25
        elif tag == 0x14:
            field_count['vec'] += 1; pos += 25
        else:
            unknown[tag] += 1
            pos += 1
    return entities, field_count, points, unknown, pos

def chain_typename(chain, type_names):
    for t, n, tid in chain:
        if n:
            return n
    return type_names.get(chain[0][2], f'#{chain[0][2]}')

def analyze_file(path):
    data = open(path, 'rb').read()
    seg_starts = find_segments(data)
    result = {'size': len(data), 'segments': []}
    type_names = {}
    for si, sstart in enumerate(seg_starts):
        try:
            h, epos = parse_header(data, sstart)
            ents, fld, pts, unk, endpos = scan_segment(data, epos, type_names)
        except ValueError as e:
            result['segments'].append({'start': sstart, 'error': str(e)})
            continue
        tc = collections.Counter(chain_typename(c, type_names) for c in ents)
        bbox = None
        if pts:
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
            bbox = {'x': [min(xs), max(xs)], 'y': [min(ys), max(ys)], 'z': [min(zs), max(zs)]}
        result['segments'].append({
            'start': sstart, 'header': h, 'entity_count': len(ents),
            'types': dict(tc), 'point_count': len(pts), 'bbox': bbox,
            'unknown': dict(unk), 'end': endpos,
        })
    return result

files = sorted(glob.glob(r'D:\training\cst\**\*.sab', recursive=True))
print(f'共 {len(files)} 个 .sab 文件\n')

for path in files:
    rel = os.path.relpath(path, r'D:\training\cst')
    r = analyze_file(path)
    nseg = len(r['segments'])
    print('=' * 72)
    print(f'文件: {rel}  ({r["size"]} 字节, {nseg} 段)')
    for si, seg in enumerate(r['segments']):
        if 'error' in seg:
            print(f'  段{si} @{seg["start"]}: 错误 {seg["error"]}')
            continue
        h = seg['header']
        tag = '主段' if si == 0 else f'嵌入段{si}'
        print(f'  [{tag}] @{seg["start"]}  ver={h["version"]}  产品={h["product_id"]}  ACIS={h["acis_version"]}')
        if 'tail_uints' in h:
            print(f'        尾部uint: {h["tail_uints"]}')
        print(f'        实体={seg["entity_count"]}  point={seg["point_count"]}  未知标签={seg["unknown"] if seg["unknown"] else "无"}')
        if seg['bbox']:
            b = seg['bbox']
            print(f'        bbox X:[{b["x"][0]:.3f},{b["x"][1]:.3f}] Y:[{b["y"][0]:.3f},{b["y"][1]:.3f}] Z:[{b["z"][0]:.3f},{b["z"][1]:.3f}]')
        if si == 0:
            top = list(seg['types'].items())[:14]
            print(f'        类型(top14): ' + ', '.join(f'{k}:{v}' for k, v in top))

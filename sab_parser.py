# -*- coding: utf-8 -*-
"""ACIS SAB 二进制几何文件完整解析器 (CST .sab)

解析 CST 项目导出的 ACIS BinaryFile (.sab)：
  - 文件头 (magic/版本/product_id/ACIS版本/日期/单位/uuid/实体数)
  - 实体流 (类型链 + 字段 + 嵌套), 扁平遍历 + 几何/属性提取
  - 输出 JSON 报告

字段标签宽度:
  0x04 uint32(4)  0x06 double(8)  0x07 string(1+len)
  0x0c int32(4)   0x13 position(24)  0x14 vector(24)
  0x15 uint32(4)  0x19 int16(2)
  0x0a/0x0f/0x10/0x11 记录起始, 0x0d/0x0e 类型链, 0x0b 结束, 0x25 类型ID前缀
"""
import struct, json, collections

SRC = r'extracted/Model/3D/CSTphone2022_1.sab'
OUT = r'sab_report.json'
data = open(SRC, 'rb').read()

# ---------------- 头部 ----------------
def parse_header(d):
    h = {}
    assert d[0:15] == b'ACIS BinaryFile', 'magic 错误'
    pos = 15
    h['version'] = d[pos]; pos += 1
    extra = d[pos:pos+15]; pos += 15
    # extra 内含实体数 (offset 8 = 0x71 = 113)
    h['header_extra_hex'] = extra.hex()
    for key in ('product_id', 'acis_version', 'date'):
        ln = d[pos+1]
        h[key] = d[pos+2:pos+2+ln].decode('latin1')
        pos += 2 + ln
    for key in ('mm_per_unit', 'resabs', 'resnor'):
        h[key] = struct.unpack('<d', d[pos+1:pos+9])[0]
        pos += 9
    pos += 1  # 分隔 0x0a
    ln = d[pos+1]
    h['uuid'] = d[pos+2:pos+2+ln].decode('latin1')
    pos += 2 + ln
    for key in ('entity_count', 'u2', 'u3'):
        h[key] = struct.unpack('<I', d[pos+1:pos+5])[0]
        pos += 5
    return h, pos

header, pos = parse_header(data)

# ---------------- 类型注册表 & 类型链 ----------------
type_names = {}

def parse_chain(d, pos):
    chain = []
    while True:
        t = d[pos]
        if t not in (0x0d, 0x0e):
            raise ValueError(f'@{pos} 类型链标签 {t:02x}')
        ln = d[pos+1]
        payload = d[pos+2:pos+2+ln]
        tid = struct.unpack('<i', payload[-4:])[0]
        name = payload[:-5].decode('latin1') if ln > 5 else None
        if name is not None:
            type_names[tid] = name
        chain.append((t, name, tid))
        pos += 2 + ln
        if t == 0x0d:
            return chain, pos

def chain_typename(chain):
    for t, n, tid in chain:
        if n:
            return n
    return type_names.get(chain[0][2], f'#{chain[0][2]}')

# ---------------- 扁平遍历, 实体 + 字段归属 ----------------
entities = []        # dict(type, id, fields)
cur = None
field_count = collections.Counter()
end_count = 0
anon = 0

def new_entity(chain, pos):
    return {
        'type': chain_typename(chain),
        'id': chain[0][2],
        'chain': [(t, n, i) for t, n, i in chain],
        'offset': pos,
        'fields': [],
    }

while pos < len(data) - 20:
    tag = data[pos]
    if tag == 0x0b:
        end_count += 1
        pos += 1
    elif tag in (0x0a, 0x0f, 0x10, 0x11):
        pos += 1
        if data[pos] in (0x0d, 0x0e):
            chain, pos = parse_chain(data, pos)
            cur = new_entity(chain, pos)
            entities.append(cur)
        else:
            anon += 1
    elif tag in (0x0d, 0x0e):
        chain, pos = parse_chain(data, pos)
        cur = new_entity(chain, pos)
        entities.append(cur)
    elif tag == 0x07:
        ln = data[pos+1]
        s = data[pos+2:pos+2+ln].decode('latin1')
        if cur is not None:
            cur['fields'].append(('str', s))
        field_count['str'] += 1
        pos += 2 + ln
    elif tag == 0x04:
        v = struct.unpack('<I', data[pos+1:pos+5])[0]
        if cur is not None:
            cur['fields'].append(('uint', v))
        field_count['uint'] += 1
        pos += 5
    elif tag == 0x0c:
        v = struct.unpack('<i', data[pos+1:pos+5])[0]
        if cur is not None:
            cur['fields'].append(('int', v))
        field_count['int'] += 1
        pos += 5
    elif tag == 0x15:
        v = struct.unpack('<I', data[pos+1:pos+5])[0]
        if cur is not None:
            cur['fields'].append(('uint2', v))
        field_count['uint2'] += 1
        pos += 5
    elif tag == 0x19:
        v = struct.unpack('<h', data[pos+1:pos+3])[0]
        if cur is not None:
            cur['fields'].append(('int16', v))
        field_count['int16'] += 1
        pos += 3
    elif tag == 0x06:
        v = struct.unpack('<d', data[pos+1:pos+9])[0]
        if cur is not None:
            cur['fields'].append(('double', v))
        field_count['double'] += 1
        pos += 9
    elif tag == 0x13:
        v = struct.unpack('<3d', data[pos+1:pos+25])
        if cur is not None:
            cur['fields'].append(('pos', list(v)))
        field_count['pos'] += 1
        pos += 25
    elif tag == 0x14:
        v = struct.unpack('<3d', data[pos+1:pos+25])
        if cur is not None:
            cur['fields'].append(('vec', list(v)))
        field_count['vec'] += 1
        pos += 25
    else:
        pos += 1

# ---------------- 统计 ----------------
type_counter = collections.Counter(e['type'] for e in entities)

# 提取 point 坐标 (point 实体的 pos 字段)
points = []
for e in entities:
    if e['type'] == 'point':
        for kind, v in e['fields']:
            if kind == 'pos':
                points.append(v)
                break

# 提取 name_attrib 字符串 (部件/材质名)
names = []
for e in entities:
    if e['type'] == 'name_attrib':
        for kind, v in e['fields']:
            if kind == 'str':
                names.append(v)
                break

# ---------------- 输出 ----------------
print('=== 文件头 ===')
for k, v in header.items():
    print(f'  {k:16s} = {v!r}')

print(f'\n=== 实体统计 (共 {len(entities)} 个实体, {len(type_names)} 种类型) ===')
for name, cnt in type_counter.most_common():
    print(f'  {name:24s} {cnt}')

print(f'\n=== 字段统计 ===')
for k, v in sorted(field_count.items()):
    print(f'  {k:8s} {v}')

print(f'\n=== 几何数据 ===')
print(f'  point 实体数: {type_counter["point"]}, 提取坐标 {len(points)} 个')
for p in points[:5]:
    print(f'    point = ({p[0]:.6f}, {p[1]:.6f}, {p[2]:.6f})')

print(f'\n=== 属性字符串 (name_attrib, 共 {len(names)} 个, 前 12 个) ===')
for s in names[:12]:
    print(f'    {s}')

# 包围盒 (所有 point 坐标的 min/max)
if points:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    print(f'\n=== 包围盒 (bbox) ===')
    print(f'  X: [{min(xs):.6f}, {max(xs):.6f}]')
    print(f'  Y: [{min(ys):.6f}, {max(ys):.6f}]')
    print(f'  Z: [{min(zs):.6f}, {max(zs):.6f}]')

# JSON 报告
report = {
    'header': header,
    'entity_count': len(entities),
    'type_count': len(type_names),
    'types': dict(type_counter),
    'fields': dict(field_count),
    'points': points,
    'names': names,
    'bbox': {'x': [min(xs), max(xs)], 'y': [min(ys), max(ys)], 'z': [min(zs), max(zs)]} if points else None,
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f'\n报告已写入 {OUT}')

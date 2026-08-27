# -*- coding: utf-8 -*-
"""SAB 记录帧探针：验证帧语法假设
假设:
  记录起始: 0a(首条/body) | 0b 11(带属性前缀?) | 11(普通)
  类型链元素: <0d|0e> <len> [<name>] 25 <int32 id>   len=namelen+5, len=5时为引用
  字段标签: 04/0c int32, 06 double, 07 str, 13 3xdouble, 25 id-ref...
"""
import struct, sys, collections

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()
print('size', len(data))

# 1) 扫描所有类型定义: <0d|0e> <len> <name> 25 <int32>
#    name 为可打印 ASCII, len = namelen+5, 紧跟 25
TD = (0x0d, 0x0e)
type_defs = []   # (pos, tag, name, id)
i = 0
while i < len(data) - 10:
    t = data[i]
    if t in TD:
        ln = data[i+1]
        if 5 <= ln <= 60 and i + 2 + ln <= len(data):
            payload = data[i+2:i+2+ln]
            if payload[-5] == 0x25 and ln > 5:
                name = payload[:-5]
                tid = struct.unpack('<i', payload[-4:])[0]
                if all(32 <= b < 127 for b in name) and name.isascii():
                    type_defs.append((i, t, name.decode(), tid))
                    i += 2 + ln
                    continue
    i += 1

print('type-def entries:', len(type_defs))

# 2) 段边界: body 类型定义位置
body_pos = [td[0] for td in type_defs if td[2] == 'body']
print('body type-def positions (前5):', body_pos[:5])
print('相邻body间距(前10):', [body_pos[i+1]-body_pos[i] for i in range(min(10,len(body_pos)-1))])

# 3) 段1的类型定义序列(到下一个body前)
seg1_end = body_pos[1] if len(body_pos) > 1 else len(data)
seg1_defs = [td for td in type_defs if body_pos[0] <= td[0] < seg1_end]
print(f'\n=== 段1 类型定义序列 ({len(seg1_defs)}个) ===')
for pos, t, name, tid in seg1_defs:
    print(f'  @{pos:6d} tag={t:02x} id={tid:3d} {name}')

# 4) 段尾: 段1最后类型定义之后、段2 body 之前的原始字节
last_def_end = None
for pos, t, name, tid in seg1_defs:
    ln = data[pos+1]
    end = pos + 2 + ln
    last_def_end = max(last_def_end or 0, end)
print(f'\n段1最后类型定义结束于 @{last_def_end}, 段2 body@{seg1_end}')

# 5) 0b 上下文统计: 0b 后跟字节分布
after_b = collections.Counter()
for i in range(len(data)-1):
    if data[i] == 0x0b:
        after_b[data[i+1]] += 1
print('\n0b 后跟字节 top12:', [(f'{k:02x}', v) for k, v in after_b.most_common(12)])

# 6) 0b 0b 的典型上下文(取5处)
print('\n=== 0b 0b 上下文样本 ===')
cnt = 0
i = 0
while i < len(data)-1 and cnt < 5:
    if data[i] == 0x0b and data[i+1] == 0x0b:
        s = max(0, i-24)
        chunk = data[s:i+10]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'@{i:7d}  {asc}')
        print(f'          {hexs}')
        cnt += 1
        i += 4000   # 间隔采样
    else:
        i += 1

# 7) 几何实体记录转储: point/straight/cone/plane/ellipse 首次出现区域
def dump_region(start, end, title):
    print(f'\n=== {title} (@{start}-@{end}) ===')
    for off in range(start, min(end, start+320), 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'{off:7d}  {hexs:<48s}  {asc}')

# 8) 锚点法: 扫描所有记录起始 (11|0a) + 类型链, 提取字段区域
def parse_chain(d, i):
    """从 i 开始解析类型链, 返回 (chain_end, names) 或 None"""
    names = []
    pos = i
    while True:
        if pos >= len(d) - 1:
            return None
        t = d[pos]
        if t not in (0x0d, 0x0e):
            return None
        ln = d[pos+1]
        if ln < 5 or pos + 2 + ln > len(d):
            return None
        payload = d[pos+2:pos+2+ln]
        if payload[-5] != 0x25:
            return None
        tid = struct.unpack('<i', payload[-4:])[0]
        name = payload[:-5].decode('latin1') if ln > 5 else None
        names.append((tid, name))
        pos += 2 + ln
        if t == 0x0d:
            return pos, names

records = []   # (rec_start, chain_end, names, field_start)
i = 0
while i < len(data) - 4:
    if data[i] in (0x11, 0x0a):
        r = parse_chain(data, i+1)
        if r:
            chain_end, names = r
            # 合法性: 有名字的元素至少1个, 或引用链
            if any(n is not None for _, n in names):
                records.append((i, chain_end, names))
                i = chain_end
                continue
    i += 1

print('锚点记录数:', len(records))
# 统计记录类型分布
tc = collections.Counter()
for _, _, names in records:
    named = [n for _, n in names if n]
    tc[named[0] if named else '?'] += 1
print('记录类型分布:', dict(tc.most_common(15)))

# 9) 完整转储 plane/loop/coedge/vertex 记录的字段区域
def show_fields(idx, limit=200):
    st, ce, names = records[idx]
    nxt = records[idx+1][0] if idx+1 < len(records) else len(data)
    fld = data[ce:nxt]
    chain_str = '>'.join((n or f'#{tid}') for tid, n in names)
    print(f'\n--- @{st} {chain_str} fields[{len(fld)}] ---')
    for off in range(0, min(len(fld), limit), 16):
        chunk = fld[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'+{off:4d}  {hexs:<48s}  {asc}')

# 找 plane(loop/coedge/vertex) 的索引
ByName = {}
for k, (st, ce, names) in enumerate(records):
    named = [n for _, n in names if n]
    if named:
        ByName.setdefault(named[0], []).append(k)
for t in ('face',):
    if t in ByName:
        show_fields(ByName[t][0], limit=460)
        print('  (该类型记录数:', len(ByName[t]), ')')

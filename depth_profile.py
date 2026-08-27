# -*- coding: utf-8 -*-
"""统计整个实体流中 open/close 标签的平衡性, 并跟踪深度profile"""
import struct, collections

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

# 解析头部找到实体流起始
pos = 15
ver = data[pos]; pos += 1
pos += 15
for _ in range(3):
    ln = data[pos+1]; pos += 2 + ln
for _ in range(3):
    pos += 9
pos += 1  # 0x0a separator
ln = data[pos+1]; pos += 2 + ln  # uuid
n_skipped_0a = 1
if data[pos] == 0x04:
    for _ in range(3):
        pos += 5
    if data[pos] == 0x0a:
        pos += 1
        n_skipped_0a += 1
print(f'实体流起始: @{pos}, 跳过了{n_skipped_0a}个0a')
print(f'头部跳过的0a位置: 检查...')

# 重新定位那两个0a
p2 = 15
p2 += 1 + 15
for _ in range(3):
    ln = data[p2+1]; p2 += 2 + ln
for _ in range(3):
    p2 += 9
print(f'第一个0a位置: @{p2} (tag={data[p2]:02x})')
p2 += 1
ln = data[p2+1]; p2 += 2 + ln
if data[p2] == 0x04:
    for _ in range(3):
        p2 += 5
    print(f'第二个0a位置: @{p2} (tag={data[p2]:02x})')

# 简单统计: 遍历实体流, 计算各标签出现次数
# 但需要正确跳过字段数据
type_names = {}

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
        if ln == 4:
            tid = struct.unpack('<i', payload)[0]
            chain.append((t, None, tid))
            return chain, p + 2 + ln
        if ln >= 5 and payload[-5] == 0x25:
            tid = struct.unpack('<i', payload[-4:])[0]
            name = payload[:-5].decode('latin1') if ln > 5 else None
        elif ln == 5 and payload[0] == 0x04:
            tid = struct.unpack('<I', payload[1:5])[0]
            chain.append((t, None, tid))
            return chain, p + 2 + ln
        else:
            raise ValueError(f'@{p} 异常类型链 (ln={ln}): {payload[:12]!r}')
        if name is not None:
            type_names[tid] = name
        chain.append((t, name, tid))
        p += 2 + ln
        if t == 0x0d:
            return chain, p

# 允许负深度的解析
depth = 0
opens = 0
closes = 0
neg_positions = []  # (pos, depth)
depth_profile = []  # (pos, depth) 每100步采样
p = pos
steps = 0
error = None

try:
    while p < len(data) - 16:
        steps += 1
        tag = data[p]
        if tag == 0x0b:
            depth -= 1
            closes += 1
            if depth < 0:
                neg_positions.append((p, depth))
            p += 1
        elif tag in (0x0a, 0x11, 0x0f, 0x10):
            depth += 1
            opens += 1
            p += 1
            if data[p] in (0x0d, 0x0e):
                r = parse_chain(p)
                if r[0] == ('END',):
                    break
                chain, p = r
        elif tag in (0x0d, 0x0e):
            r = parse_chain(p)
            if r[0] == ('END',):
                break
            chain, p = r
            depth += 1
            opens += 1
        elif tag == 0x07:
            ln = data[p+1]
            p += 2 + ln
        elif tag in (0x04, 0x0c, 0x15):
            p += 5
        elif tag == 0x19:
            p += 3
        elif tag == 0x06:
            p += 9
        elif tag == 0x13:
            p += 25
        elif tag == 0x14:
            p += 25
        else:
            error = f'@{p} 未知标签 {tag:02x}'
            break
        if steps % 100 == 0:
            depth_profile.append((p, depth))
except Exception as e:
    error = str(e)

print(f'\n=== 统计 ===')
print(f'总步数: {steps}')
print(f'opens (11/0a/0f/10/chain): {opens}')
print(f'closes (0b): {closes}')
print(f'差值 (opens - closes): {opens - closes}')
print(f'最终深度: {depth}')
print(f'错误: {error}')
print(f'深度为负的位置数: {len(neg_positions)}')
if neg_positions:
    print(f'前10个负深度位置: {neg_positions[:10]}')
    print(f'最小深度: {min(d for _, d in neg_positions)}')

# 打印深度profile (采样)
print(f'\n=== 深度profile (每100步采样, 前30个) ===')
for pp, dd in depth_profile[:30]:
    print(f'  @{pp:8d}  depth={dd}')
print('  ...')
print(f'\n=== 深度profile (最后30个) ===')
for pp, dd in depth_profile[-30:]:
    print(f'  @{pp:8d}  depth={dd}')

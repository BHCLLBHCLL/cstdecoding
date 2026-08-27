# -*- coding: utf-8 -*-
"""查看文件开头的实体结构和 0a 的上下文"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

# 解析头部
pos = 15
pos += 1 + 15
for _ in range(3):
    ln = data[pos+1]; pos += 2 + ln
for _ in range(3):
    pos += 9
pos += 1
ln = data[pos+1]; pos += 2 + ln
if data[pos] == 0x04:
    for _ in range(3):
        pos += 5
    if data[pos] == 0x0a:
        pos += 1
start = pos
print(f'实体流起始: @{start}')

# hex dump 开头 100 字节
print('\n=== 实体流开头 @218-320 ===')
for base in range(start, start+102, 16):
    hexstr = ' '.join(f'{data[i]:02x}' for i in range(base, min(base+16, start+102)))
    ascii_str = ''.join(chr(data[i]) if 32 <= data[i] < 127 else '.' for i in range(base, min(base+16, start+102)))
    print(f'{base:6d}  {hexstr:<48}  {ascii_str}')

# 找前几个 0a 的位置和上下文
print('\n=== 前20个 0a 标签的上下文 ===')
count = 0
p = start
# 简化遍历: 找 0a 位置
# 先手动扫描前 5000 字节中的 0a
oa_positions = []
i = start
while i < min(start + 5000, len(data)):
    if data[i] == 0x0a:
        oa_positions.append(i)
        if len(oa_positions) >= 20:
            break
    i += 1

for op in oa_positions:
    # 显示前后各8字节
    ctx_start = max(0, op - 8)
    ctx_end = min(len(data), op + 12)
    hexstr = ' '.join(f'{data[j]:02x}' for j in range(ctx_start, ctx_end))
    # 标记 0a 位置
    marker = ' ' * ((op - ctx_start) * 3) + '^^'
    print(f'  @{op:6d}: {hexstr}')
    print(f'           {marker}')

# 统计 0a 后面跟什么
from collections import Counter
after_0a = Counter()
for op in oa_positions:
    if op + 1 < len(data):
        after_0a[data[op+1]] += 1
print(f'\n=== 0a 后面的标签分布 (前{len(oa_positions)}个) ===')
for tag, cnt in after_0a.most_common(10):
    print(f'  {tag:02x}: {cnt}')

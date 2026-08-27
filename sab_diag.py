# -*- coding: utf-8 -*-
"""诊断: loop 记录结构 与 0x15 标签"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

def dump(start, end):
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'{off:7d}  {hexs:<48s}  {asc}')

# loop 定义 @1260 (0d), face 结束 @1258 (0b)
print('=== face 尾 -> loop -> cone 区 (@1255-@1340) ===')
dump(1255, 1340)

# 0x15 标签的上下文统计
print('\n=== 0x15 后跟字节分布 ===')
import collections
after = collections.Counter()
for i in range(len(data)-1):
    if data[i] == 0x15:
        after[data[i+1]] += 1
print(after.most_common(10))

# 0x12, 0x0f, 0x10 等潜在标签的分布
for tag in (0x0f, 0x10, 0x12, 0x15, 0x16, 0x17):
    cnt = data.count(bytes([tag]))
    print(f'标签 {tag:02x} 出现次数: {cnt}')

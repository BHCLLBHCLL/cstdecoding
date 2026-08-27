# -*- coding: utf-8 -*-
"""在 ACIS 30 的 SAR Model.sab 中找 "unknown" 模式和 edge 周围结构"""
import struct

data = open(r'D:\training\cst\SAR Head Hand and Phone\Model.sab', 'rb').read()
print('size', len(data))

cnt = data.count(b'\x07\x07unknown')
print(f'"unknown" 出现: {cnt} 次')

idx = data.find(b'\x07\x07unknown')
if idx >= 0:
    print(f'首处 @{idx}, 前后转储:')
    start = max(0, idx - 240)
    for off in range(start, idx + 320, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'{off:9d}  {hexs:<48s}  {asc}')
else:
    print('无 "unknown" — ACIS 30 用别的写法')

# 找 edge 类型定义位置
i = 0
while i < len(data) - 10:
    if data[i] in (0x0d, 0x0e) and data[i+1] == 9 and data[i+2:i+6] == b'edge' and data[i+6] == 0x25:
        print(f'\nedge 类型定义 @{i}: {data[i:i+11].hex()}')
        break
    i += 1

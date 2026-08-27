# -*- coding: utf-8 -*-
"""对照: 在 CSTphone2022_1.sab (ACIS28, 解析成功) 中找 "unknown"+0a 模式的完整记录结构"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

# 找第一处 "unknown" 字符串, 转储前后区域
idx = data.find(b'\x07\x07unknown')
print(f'首处 "unknown" @{idx}')
start = max(0, idx - 200)
for off in range(start, idx + 400, 16):
    chunk = data[off:off+16]
    hexs = ' '.join(f'{b:02x}' for b in chunk)
    asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
    print(f'{off:8d}  {hexs:<48s}  {asc}')

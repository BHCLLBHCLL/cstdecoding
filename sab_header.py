# -*- coding: utf-8 -*-
"""SAB 头部逐字节精确解析"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

# 逐字节打印 0-230
print('offset: hex  dec  char')
for off in range(0, 232):
    b = data[off]
    ch = chr(b) if 32 <= b < 127 else '.'
    print(f'{off:5d}: {b:02x} {b:5d}  {ch}')

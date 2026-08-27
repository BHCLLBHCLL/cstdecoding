# -*- coding: utf-8 -*-
"""SAB 框架语法探针2: 转储头部+段1完整原始字节, 弄清记录框架"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()
print('size', len(data))

def dump(start, end, title=''):
    print(f'\n=== {title} (@{start}-@{end}) ===')
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'{off:7d}  {hexs:<48s}  {asc}')

# 1) 文件头
dump(0, 220, '文件头')

# 2) 段1开头: body记录 + rgb_color记录区域
dump(210, 470, 'body记录 + rgb_color记录')

# 3) name_attrib -> shell 区域
dump(410, 640, 'name_attrib/gen -> shell')

# 4) integer_attrib -> face 记录开头
dump(600, 830, 'integer_attrib -> face链')

# 5) 段1尾部: point类型定义之后到段2 body 之前
dump(8790, 9200, '段1尾: point定义后 -> 段边界')

# 6) 文件末尾
dump(len(data)-300, len(data), '文件末尾300字节')

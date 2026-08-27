# -*- coding: utf-8 -*-
"""推断未知字段标签 (0x0f/0x10/0x12/0x15/0x16/0x17 等) 的宽度
方法: 找 "0b <tag> ..." 或 "<tag> ... 0b" 的字段实例, dump 上下文
"""
import struct, collections

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

def hexdump(start, end):
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'  {off:7d}  {hexs:<48s}  {asc}')

# 对每个候选标签, 找 "0b 后紧跟 tag" 的实例 (tag 在字段位置)
candidates = [0x0f, 0x10, 0x12, 0x15, 0x16, 0x17, 0x18, 0x19]
for tag in candidates:
    print(f'\n===== 标签 {tag:02x} (0b 后紧跟) =====')
    found = 0
    i = 0
    while i < len(data)-2 and found < 2:
        if data[i] == 0x0b and data[i+1] == tag:
            print(f'@ {i}: 0b 后跟 {tag:02x}')
            hexdump(i, i+40)
            found += 1
            i += 40
        else:
            i += 1

# 也看 "tag 后跟 0b" (字段结束)
for tag in candidates:
    print(f'\n===== 标签 {tag:02x} (后跟 0b) =====')
    found = 0
    i = 0
    while i < len(data)-2 and found < 2:
        if data[i] == tag and data[i+1] == 0x0b:
            print(f'@ {i}: {tag:02x} 后跟 0b')
            hexdump(i-16, i+16)
            found += 1
            i += 40
        else:
            i += 1

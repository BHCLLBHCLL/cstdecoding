# -*- coding: utf-8 -*-
"""对比 ACIS 28 vs 31 的 13/14 标签宽度 (position/vector)"""
import struct

def find_chain(data, name, start=0):
    """找类型链 name 的位置"""
    idx = data.find(name.encode())
    while idx != -1 and idx < len(data):
        # 检查前面是 0d/0e + len
        if idx >= 2 and data[idx-2] in (0x0d, 0x0e) and data[idx-1] == len(name)+5:
            return idx-2
        idx = data.find(name.encode(), idx+1)
    return -1

def dump_pos(data, chain_pos):
    """dump 类型链后面的字段 (找 13/14 标签)"""
    p = chain_pos
    # 跳过类型链
    while data[p] in (0x0d, 0x0e):
        ln = data[p+1]
        p += 2 + ln
        if data[p-3] == 0x0d:  # 链尾
            break
    # 这里简化: 直接 dump p 之后 40 字节
    for off in range(p, p+40, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'    {off:8d}  {hexs:<48s}  {asc}')

for path, label in [(r'D:\training\cst\CST Phone 5G\Model\3D\CSTphone2022_1.sab', 'ACIS31'),
                    (r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'ACIS28')]:
    data = open(path, 'rb').read()
    print(f'=== {label} ({path.split(chr(92))[-1]}) ===')
    pos = find_chain(data, 'point')
    print(f'  point 类型链 @{pos}')
    if pos >= 0:
        dump_pos(data, pos)
    print()

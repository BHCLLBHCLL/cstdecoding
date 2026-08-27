# -*- coding: utf-8 -*-
"""诊断 HeadHand 第二个出错位置"""
import struct

data = open(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'rb').read()

def hexdump(start, end):
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'  {off:8d}  {hexs:<48s}  {asc}')

target = 10486042
print(f'=== 出错位置 @{target} 前 64 + 后 80 字节 ===')
hexdump(target-64, target+96)

# 往前找最近的类型链
print('\n=== 往前找类型链 ===')
i = target
found = 0
while i > 0 and found < 8:
    if data[i] in (0x0d, 0x0e):
        ln = data[i+1]
        if 4 <= ln <= 60 and i+2+ln <= len(data):
            payload = data[i+2:i+2+ln]
            if len(payload) >= 4:
                tid = struct.unpack('<i', payload[-4:])[0]
                prefix = payload[:-4]
                print(f'  @{i}: tag={data[i]:02x} len={ln} prefix={prefix!r} id={tid}')
                found += 1
    i -= 1

# -*- coding: utf-8 -*-
"""诊断 HeadHand_1.sab 解析出错位置"""
import struct

data = open(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'rb').read()
print('文件大小:', len(data))
print('头部版本:', data[15], f'({data[15]:#04x})')

# dump 出错位置 7340297 附近
target = 7340297
def hexdump(start, end):
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'  {off:8d}  {hexs:<48s}  {asc}')

print(f'\n=== 出错位置 @{target} 前 64 字节 + 后 80 字节 ===')
hexdump(target-64, target+96)

# 统计 0x04 附近出现的上下文
print('\n=== 找 7340297 之前最近的类型链 ===')
# 从 target 往前找最近的 0d/0e + 名字
i = target
found = 0
while i > 0 and found < 5:
    if data[i] in (0x0d, 0x0e):
        ln = data[i+1]
        if 5 <= ln <= 60 and i+2+ln <= len(data):
            payload = data[i+2:i+2+ln]
            if payload[-5] == 0x25:
                name = payload[:-5].decode('latin1')
                tid = struct.unpack('<i', payload[-4:])[0]
                print(f'  类型链 @{i}: tag={data[i]:02x} {name} id={tid}')
                found += 1
    i -= 1

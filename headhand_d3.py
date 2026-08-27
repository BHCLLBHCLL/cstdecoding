# -*- coding: utf-8 -*-
"""精确分析 HeadHand 17501910 附近, 判断 0a 后的 13 宽度"""
import struct

data = open(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'rb').read()

def d(off):
    return struct.unpack('<d', data[off:off+8])[0]

print('=== 17501904 起逐字节 ===')
for off in range(17501904, 17501960):
    b = data[off]
    ch = chr(b) if 32 <= b < 127 else '.'
    print(f'  {off}: {b:02x} {b:5d}  {ch}')

print('\n=== 尝试 3 doubles (从 17501912) ===')
print('  d1 =', d(17501912))
print('  d2 =', d(17501920))
print('  d3 =', d(17501928))

print('\n=== 尝试 2 doubles (从 17501912), 然后字段 ===')
print('  d1 =', d(17501912))
print('  d2 =', d(17501920))
print('  17501928 =', f'{data[17501928]:02x}', '(若为04=uint标签)')
print('  17501929 uint =', struct.unpack('<I', data[17501929:17501933])[0])
print('  17501933 =', f'{data[17501933]:02x}')
print('  17501934 uint =', struct.unpack('<I', data[17501934:17501938])[0])

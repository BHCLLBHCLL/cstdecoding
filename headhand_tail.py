# -*- coding: utf-8 -*-
"""诊断 HeadHand 尾部 ln=0 异常"""
import struct

data = open(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'rb').read()
print('文件大小:', len(data))

def hexdump(start, end):
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'  {off:8d}  {hexs:<48s}  {asc}')

target = 17501936
print(f'=== 出错位置 @{target} 前 32 + 后 96 字节 ===')
hexdump(target-32, target+96)

print(f'\n=== 文件最后 160 字节 ===')
hexdump(len(data)-160, len(data))

# 找尾部是否有 'ACIS BinaryFile' 或 'End-of-ACIS-data'
tail = data[17500000:]
print(f'\n尾部 (从 17500000 起) 搜索 "ACIS BinaryFile":', tail.find(b'ACIS BinaryFile'))
print(f'尾部搜索 "End-of-ACIS-data":', tail.find(b'End-of-ACIS-data'))

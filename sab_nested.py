# -*- coding: utf-8 -*-
"""搜索新版 SAB 里嵌入的 'ACIS BinaryFile' 及 cstbboxcache 结构"""
import struct

path = r'D:\training\cst\IFA_design\ModelCache\Model.sab'
data = open(path, 'rb').read()

magic = b'ACIS BinaryFile'
print(f'文件大小: {len(data)}')
print(f'"ACIS BinaryFile" 出现次数: {data.count(magic)}')

# 找所有 magic 位置
positions = []
idx = data.find(magic)
while idx != -1:
    positions.append(idx)
    idx = data.find(magic, idx+1)

print('magic 位置:', positions)

def hexdump(start, end):
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'  {off:6d}  {hexs:<48s}  {asc}')

# dump 每个 magic 的上下文 (前 16 字节 + 后 60 字节)
for p in positions:
    if p == 0:
        continue
    print(f'\n=== 嵌入 magic @{p} (前16字节 + 后80字节) ===')
    hexdump(p-16, p+96)

# 也看 cstbboxcache 实体
print('\n=== 搜索 "cstbboxcache" 字符串 ===')
idx = data.find(b'cstbboxcache')
print(f'"cstbboxcache" 首次出现 @{idx}')
if idx != -1:
    hexdump(idx-40, idx+120)

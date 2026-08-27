# -*- coding: utf-8 -*-
"""扫描 HeadHand_1.sab 全文件的类型定义 (id -> name), 以及 "unknown"+0a 模式统计"""
import struct, re

data = open(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'rb').read()

# 1) 全文件类型定义扫描: <0d|0e> <len> <name> 25 <int32 id>
typedefs = {}
i = 0
while i < len(data) - 10:
    t = data[i]
    if t in (0x0d, 0x0e):
        ln = data[i+1]
        if 5 <= ln <= 60 and i + 2 + ln <= len(data):
            payload = data[i+2:i+2+ln]
            if ln > 5 and payload[-5] == 0x25:
                name = payload[:-5]
                tid = struct.unpack('<i', payload[-4:])[0]
                if all(32 <= b < 127 for b in name):
                    n = name.decode()
                    if tid not in typedefs:
                        typedefs[tid] = (n, i)
    i += 1

print(f'共发现 {len(typedefs)} 个类型定义 (按首次出现):')
for tid in sorted(typedefs):
    n, off = typedefs[tid]
    print(f'  id={tid:3d}  @{off:9d}  {n}')

# 2) "unknown" 字符串出现次数
cnt = 0
idx = data.find(b'\x07\x07unknown')
while idx != -1:
    cnt += 1
    idx = data.find(b'\x07\x07unknown', idx + 1)
print(f'\n"unknown" 字符串出现: {cnt} 次')

# 3) 0d 00 出现次数
cnt2 = data.count(b'\x0d\x00')
print(f'0d 00 序列出现: {cnt2} 次')

# 4) 检查 CSTphone2022_1.sab 的类型定义 (ACIS 28 对照)
data2 = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()
typedefs2 = {}
i = 0
while i < len(data2) - 10:
    t = data2[i]
    if t in (0x0d, 0x0e):
        ln = data2[i+1]
        if 5 <= ln <= 60 and i + 2 + ln <= len(data2):
            payload = data2[i+2:i+2+ln]
            if ln > 5 and payload[-5] == 0x25:
                name = payload[:-5]
                tid = struct.unpack('<i', payload[-4:])[0]
                if all(32 <= b < 127 for b in name):
                    if tid not in typedefs2:
                        typedefs2[tid] = (name.decode(), i)
    i += 1
print(f'\nCSTphone2022_1.sab 类型定义 ({len(typedefs2)} 个):')
for tid in sorted(typedefs2):
    n, off = typedefs2[tid]
    print(f'  id={tid:3d}  @{off:9d}  {n}')

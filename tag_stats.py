# -*- coding: utf-8 -*-
"""检查深度攀升区域的标签模式 - 看11后面到底跟什么"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

# 解析头部
pos = 15
pos += 1 + 15
for _ in range(3):
    ln = data[pos+1]; pos += 2 + ln
for _ in range(3):
    pos += 9
pos += 1
ln = data[pos+1]; pos += 2 + ln
if data[pos] == 0x04:
    for _ in range(3):
        pos += 5
    if data[pos] == 0x0a:
        pos += 1
start = pos

# 检查有多少个 ACIS BinaryFile 段
segs = []
idx = data.find(b'ACIS BinaryFile')
while idx != -1:
    segs.append(idx)
    idx = data.find(b'ACIS BinaryFile', idx + 1)
print(f'段数: {len(segs)}, 位置: {segs[:5]}')

# 统计 11 后面跟的标签分布
from collections import Counter
after_11 = Counter()
tag_counts = Counter()

# 逐tag遍历(简化: 只统计标签, 不跟踪结构)
p = start
chain_depth = 0
try:
    while p < len(data) - 16:
        tag = data[p]
        tag_counts[tag] += 1
        if tag == 0x11:
            nxt = data[p+1]
            after_11[nxt] += 1
            p += 1
            # 解析链
            if data[p] in (0x0d, 0x0e):
                while True:
                    t = data[p]
                    ln = data[p+1]
                    payload = data[p+2:p+2+ln]
                    if payload == b'End-of-ACIS-data':
                        p += 2 + ln
                        break
                    p += 2 + ln
                    if t == 0x0d:
                        break
        elif tag in (0x0d, 0x0e):
            # 顶层级链
            while True:
                t = data[p]
                ln = data[p+1]
                payload = data[p+2:p+2+ln]
                if payload == b'End-of-ACIS-data':
                    p += 2 + ln
                    break
                p += 2 + ln
                if t == 0x0d:
                    break
        elif tag == 0x07:
            ln = data[p+1]
            p += 2 + ln
        elif tag in (0x04, 0x0c, 0x15):
            p += 5
        elif tag == 0x19:
            p += 3
        elif tag == 0x06:
            p += 9
        elif tag == 0x13:
            p += 25
        elif tag == 0x14:
            p += 25
        elif tag == 0x0b:
            p += 1
        elif tag in (0x0a, 0x0f, 0x10):
            p += 1
        else:
            print(f'@{p} 未知标签 {tag:02x}')
            break
except Exception as e:
    print(f'异常 @{p}: {e}')

print(f'\n=== 标签出现次数 (top 20) ===')
for tag, cnt in tag_counts.most_common(20):
    print(f'  {tag:02x} ({tag:3d}): {cnt:8d}')

print(f'\n=== 11 后面跟的标签 (top 10) ===')
for tag, cnt in after_11.most_common(10):
    print(f'  {tag:02x} ({tag:3d}): {cnt:8d}')

# 看深度攀升区域 9000-9100 的hex
print('\n=== hex dump 9000-9100 ===')
for base in range(9000, 9100, 16):
    hexstr = ' '.join(f'{data[i]:02x}' for i in range(base, min(base+16, 9100)))
    print(f'{base:6d}  {hexstr}')

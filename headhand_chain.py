# -*- coding: utf-8 -*-
"""分析 HeadHand (ACIS 28.0.2) 类型链编码差异: 0d/0e 后的长度分布"""
import struct, collections

data = open(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'rb').read()

# 统计 0d/0e 后跟字节的分布 (作为"长度")
for tag in (0x0d, 0x0e):
    dist = collections.Counter()
    for i in range(len(data)-1):
        if data[i] == tag:
            dist[data[i+1]] += 1
    print(f'标签 {tag:02x} 后跟长度分布 (top15):', [(f'{k}', v) for k, v in dist.most_common(15)])

# 找 "0e 04" 后面跟什么 (下一个标签)
print('\n=== "0e 04" 后面的下一个标签分布 ===')
after = collections.Counter()
i = 0
while i < len(data)-7:
    if data[i] == 0x0e and data[i+1] == 0x04:
        # 0e 04 <id4字节> 后面 1 字节
        nxt = data[i+6]
        after[nxt] += 1
        i += 6
    else:
        i += 1
print('"0e 04 <id>" 后跟标签:', [(f'{k:02x}', v) for k, v in after.most_common(15)])

# 找 "0d 04" 后面跟什么
print('\n=== "0d 04" 后面的下一个标签分布 ===')
after2 = collections.Counter()
i = 0
while i < len(data)-7:
    if data[i] == 0x0d and data[i+1] == 0x04:
        nxt = data[i+6]
        after2[nxt] += 1
        i += 6
    else:
        i += 1
print('"0d 04 <id>" 后跟标签:', [(f'{k:02x}', v) for k, v in after2.most_common(15)])

# 找 "0e 05" (标准短引用, 25+id) 后面跟什么
print('\n=== "0e 05" 后跟标签 (标准引用) ===')
after3 = collections.Counter()
i = 0
while i < len(data)-8:
    if data[i] == 0x0e and data[i+1] == 0x05 and data[i+2] == 0x25:
        nxt = data[i+7]
        after3[nxt] += 1
        i += 7
    else:
        i += 1
print('"0e 05 25 <id>" 后跟标签:', [(f'{k:02x}', v) for k, v in after3.most_common(15)])

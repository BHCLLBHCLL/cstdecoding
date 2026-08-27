# -*- coding: utf-8 -*-
"""统计 HeadHand / CSTphone 中 "unknown" 后的语法模式, 以及 0a 匿名记录的内容形态"""
import struct, collections

def scan(path, label):
    data = open(path, 'rb').read()
    print(f'=== {label} ({len(data)} B) ===')
    # 1) "unknown" 后跟什么
    after_unknown = collections.Counter()
    positions = []
    idx = data.find(b'\x07\x07unknown')
    while idx != -1:
        nxt = data[idx+9]
        after_unknown[f'{nxt:02x}'] += 1
        positions.append(idx)
        idx = data.find(b'\x07\x07unknown', idx + 1)
    print(f'"unknown" 出现 {len(positions)} 次, 后跟字节分布: {dict(after_unknown.most_common(8))}')

    # 2) "unknown" 之前的字节 (属于什么记录结尾)
    before = collections.Counter()
    for p in positions:
        # 回看: 找 0b 或其他
        before[f'{data[p-1]:02x}'] += 1
    print(f'"unknown" 前字节分布: {dict(before.most_common(8))}')

    # 3) 0a 匿名记录的内容: 0a 后跟的字节分布
    #    只统计 "unknown" 之后的 0a (即 idx+9 == 0a 的位置)
    after_0a = collections.Counter()
    samples = {}
    for p in positions:
        if data[p+9] == 0x0a:
            nxt = data[p+10]
            after_0a[f'{nxt:02x}'] += 1
            if nxt not in samples:
                samples[nxt] = data[p+10:p+10+64].hex()
    print(f'"unknown" 后的 0a 其后字节分布: {dict(after_0a.most_common(8))}')
    for k, v in list(samples.items())[:6]:
        print(f'  0a {k}: {v}')

    # 4) 0d 00 的分布位置 (前 20 个)
    d00 = []
    i = data.find(b'\x0d\x00')
    while i != -1 and len(d00) < 12:
        d00.append(i)
        i = data.find(b'\x0d\x00', i + 1)
    print(f'0d 00 前 12 处位置: {d00}')
    print()

scan(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'HeadHand_1.sab')
scan(r'extracted/Model/3D/CSTphone2022_1.sab', 'CSTphone2022_1.sab')

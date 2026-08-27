# -*- coding: utf-8 -*-
"""统计成功解析的 SAB 中 0a 记录起始标签的语法模式, 对比 HeadHand (ACIS28) 的差异"""
import collections, glob, sys
sys.path.insert(0, '.')
from batch_sab import find_segments, parse_header

def after_0a_stats(path, label):
    data = open(path, 'rb').read()
    seg = find_segments(data)
    s0 = seg[0]
    h, epos = parse_header(data, s0)
    # 限制在主段范围内 (到第一个 End-of-ACIS-data)
    end_marker = data.find(b'End-of-ACIS-data', epos)
    region = data[epos:end_marker]
    stats = collections.Counter()
    ctx = {}
    i = 0
    while i < len(region) - 2:
        if region[i] == 0x0a:
            nxt = region[i+1]
            stats[f'{nxt:02x}'] += 1
            if nxt not in ctx:
                ctx[nxt] = region[max(0,i-16):i+24].hex()
        i += 1
    print(f'--- {label} (ACIS={h["acis_version"]}, 主段 {len(region)} B) ---')
    print('  0a 后跟字节分布:', dict(stats.most_common(10)))
    for k, v in ctx.items():
        print(f'  0a {k} 首见上下文: {v}')
    # 也统计 0b 后跟什么 (记录关闭后是什么)
    stats_b = collections.Counter()
    i = 0
    while i < len(region) - 1:
        if region[i] == 0x0b:
            stats_b[f'{region[i+1]:02x}'] += 1
        i += 1
    print('  0b 后跟字节分布(top10):', dict(stats_b.most_common(10)))

after_0a_stats(r'D:\training\cst\SAR Head Hand and Phone\Model.sab', 'SAR Model.sab')
after_0a_stats(r'D:\training\cst\SingleAntenna\ModelCache\Model.sab', 'SingleAntenna Model.sab')
after_0a_stats(r'extracted_ship/ModelCache/Model.sab', 'Ship Model.sab')

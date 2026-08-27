# -*- coding: utf-8 -*-
"""分析 RCS of a Ship 的 Model.sab (ver=228 多段容器) + .sab.index 验证"""
import sys, struct, collections
sys.path.insert(0, '.')
from batch_sab import find_segments, parse_header, scan_segment, chain_typename

data = open(r'extracted_ship/ModelCache/Model.sab', 'rb').read()
type_names = {}
segs = find_segments(data)
print(f'文件 {len(data)} 字节, {len(segs)} 段\n')

for si, s in enumerate(segs):
    try:
        h, epos = parse_header(data, s)
        ents, fld, pts, unk, endpos = scan_segment(data, epos, type_names)
    except ValueError as e:
        print(f'段{si} @{s}: 错误 {e}')
        continue
    tc = collections.Counter(chain_typename(c, type_names) for c in ents)
    tag = '主段' if si == 0 else f'嵌入{si}'
    print(f'[{tag}] @{s} ver={h["version"]} ACIS={h["acis_version"]} 实体={len(ents)} point={len(pts)} 未知={dict(unk) if unk else "无"}')
    if pts:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]; zs = [p[2] for p in pts]
        print(f'   bbox X[{min(xs):.1f},{max(xs):.1f}] Y[{min(ys):.1f},{max(ys):.1f}] Z[{min(zs):.1f},{max(zs):.1f}]')
    if si == 0:
        print('   类型:', ', '.join(f'{k}:{v}' for k, v in tc.most_common(20)))

# 索引文件交叉验证
idx = open(r'extracted_ship/ModelCache/Model.sab.index', 'rb').read()
n = struct.unpack('<i', idx[:4])[0]
offs = [struct.unpack('<q', idx[4 + i * 8:12 + i * 8])[0] for i in range(n)]
print(f'\n.sab.index: 段数={n}, 偏移与实际吻合: {offs == segs}')

# -*- coding: utf-8 -*-
"""批量分析所有 .cst 容器的结构 (版本/license/条目/几何文件)"""
import glob, os, struct
from cst_parser import (find_eocd, parse_central_directory,
                        parse_eocd_comment, sniff_type, CstParseError)

files = sorted(glob.glob(r'D:\training\cst\*.cst'))
print(f'共 {len(files)} 个 .cst 文件\n')

for path in files:
    name = os.path.basename(path)
    size = os.path.getsize(path)
    try:
        with open(path, 'rb') as f:
            window = min(size, 65535 + 22)
            f.seek(size - window)
            tail = f.read(window)
            eocd_in_tail, cd_off, cd_size, count, comment = find_eocd(tail, size)
            f.seek(cd_off)
            cd_data = f.read(cd_size)
            entries = parse_central_directory(cd_data, count)
        meta = parse_eocd_comment(comment)
        # 找几何/关键文件
        geom = [e['name'] for e in entries
                if e['name'].lower().endswith(('.sab', '.sat', '.smt'))]
        n_geom = len(geom)
        # 统计条目类型
        types = {}
        for e in entries:
            # 不读数据, 仅按扩展名粗分
            ext = os.path.splitext(e['name'])[1].lower() or '(无扩展)'
            types[ext] = types.get(ext, 0) + 1
        print('=' * 72)
        print(f'{name}  ({size:,} 字节)')
        print(f'  CST 版本: {meta.get("cst_version", "?")}')
        print(f'  License: {meta.get("license", "?")[:50]}')
        print(f'  条目数: {len(entries)}')
        print(f'  几何文件(.sab/.sat): {n_geom}')
        for g in geom[:6]:
            print(f'    - {g}')
        if n_geom > 6:
            print(f'    ... 共 {n_geom} 个')
        ext_list = ', '.join(f'{k}:{v}' for k, v in sorted(types.items(), key=lambda x: -x[1])[:10])
        print(f'  扩展名分布: {ext_list}')
    except CstParseError as e:
        print('=' * 72)
        print(f'{name}  ({size:,} 字节)')
        print(f'  解析错误: {e}')
    except Exception as e:
        print('=' * 72)
        print(f'{name}  ({size:,} 字节)')
        print(f'  异常: {type(e).__name__}: {e}')

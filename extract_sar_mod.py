# -*- coding: utf-8 -*-
"""提取 SAR 项目的 Model.mod 和 ModelHistory.json, 分析 SAB 导入关系"""
import os
from cst_parser import find_eocd, parse_central_directory, read_entry

path = r'D:\training\cst\SAR Head Hand and Phone.cst'
size = os.path.getsize(path)
os.makedirs('extracted_sar', exist_ok=True)

with open(path, 'rb') as f:
    window = min(size, 65535 + 22)
    f.seek(size - window)
    tail = f.read(window)
    _, cd_off, cd_size, count, comment = find_eocd(tail, size)
    f.seek(cd_off)
    cd_data = f.read(cd_size)
    entries = parse_central_directory(cd_data, count)
    print(f'条目数: {len(entries)}')
    for e in entries:
        n = e['name']
        if n in ('Model/3D/Model.mod', 'Model/3D/ModelHistory.json', 'Model/Parameters.json'):
            f.seek(0)
            content, crc_ok, local = read_entry(f, e)
            out = os.path.join('extracted_sar', os.path.basename(n))
            open(out, 'wb').write(content)
            print(f'  {n}: {len(content):,} 字节 -> {out} (crc_ok={crc_ok})')

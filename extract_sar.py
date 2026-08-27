# -*- coding: utf-8 -*-
"""提取 SAR 的 .sab 到磁盘, 并诊断 HeadHand 解析出错位置"""
import os, struct
from cst_parser import find_eocd, parse_central_directory, read_entry

path = r'D:\training\cst\SAR Head Hand and Phone.cst'
outdir = r'D:\training\cst\SAR Head Hand and Phone'
os.makedirs(outdir, exist_ok=True)

size = os.path.getsize(path)
with open(path, 'rb') as f:
    window = min(size, 65535 + 22)
    f.seek(size - window)
    tail = f.read(window)
    eocd_in_tail, cd_off, cd_size, count, comment = find_eocd(tail, size)
    f.seek(cd_off)
    cd_data = f.read(cd_size)
    entries = parse_central_directory(cd_data, count)
    for e in entries:
        if e['name'].lower().endswith('.sab'):
            content, crc_ok, _ = read_entry(f, e)
            out = os.path.join(outdir, os.path.basename(e['name']))
            with open(out, 'wb') as o:
                o.write(content)
            print(f'提取: {e["name"]} -> {out}  ({len(content)} 字节)')

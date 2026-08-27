# -*- coding: utf-8 -*-
"""提取 8 个 CST 2023:3 文件的 Model/3D/Model.mod (参数化几何) 并保存到 mod_files/"""
import os
from cst_parser import find_eocd, parse_central_directory, read_entry

FILES = [
    'IFA_design.cst', 'SingleAntenna.cst',
    'dipole1_monitors7.cst', 'dipole1_monitors7v2.cst', 'dipole1_monitors7v3.cst',
    'microstrip_patch_antenna.cst', 'microstrip_patch_antennav2.cst',
    'microstrip_patch_antennav3.cst',
]

os.makedirs('mod_files', exist_ok=True)
for name in FILES:
    path = os.path.join(r'D:\training\cst', name)
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        window = min(size, 65535 + 22)
        f.seek(size - window)
        tail = f.read(window)
        _, cd_off, cd_size, count, comment = find_eocd(tail, size)
        f.seek(cd_off)
        cd_data = f.read(cd_size)
        entries = parse_central_directory(cd_data, count)
        for e in entries:
            if e['name'] in ('Model/3D/Model.mod',):
                f.seek(0)
                content, crc_ok, local = read_entry(f, e)
                stem = name.replace('.cst', '')
                out = os.path.join('mod_files', f'{stem}.mod')
                open(out, 'wb').write(content)
                print(f'{name}: Model.mod {len(content):,} 字节 -> {out} (crc_ok={crc_ok})')

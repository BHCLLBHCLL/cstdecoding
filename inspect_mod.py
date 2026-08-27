# -*- coding: utf-8 -*-
"""Inspect Model.mod content from a .cst file"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from cst_parser import find_eocd, parse_central_directory, read_entry

cst_path = sys.argv[1] if len(sys.argv) > 1 else r'D:\training\cst\CST Phone 5G.cst'
size = os.path.getsize(cst_path)
with open(cst_path, 'rb') as f:
    window = min(size, 65535 + 22)
    f.seek(size - window)
    tail = f.read(window)
    _, cd_off, cd_size, count, comment = find_eocd(tail, size)
    f.seek(cd_off)
    cd_data = f.read(cd_size)
    entries = parse_central_directory(cd_data, count)

for e in entries:
    name = e['name'].replace('\\', '/')
    if 'Model.mod' in name:
        print(f'Found: {name} (size={e["uncompressed_size"]})')
        with open(cst_path, 'rb') as f:
            content, crc_ok, _ = read_entry(f, e)
        text = content.decode('latin1', errors='replace')
        lines = text.split('\n')
        print(f'Total lines: {len(lines)}')
        print('===== FIRST 100 LINES =====')
        for i, line in enumerate(lines[:100]):
            print(f'{i+1}: {line.rstrip()}')
        print('===== KEYWORD SEARCH =====')
        keywords = ['Brick', 'Cylinder', 'Sphere', 'Torus', 'Cone', 'Primitive',
                    'Component', 'Material', 'DiscretePort', 'WaveguidePort',
                    'Monitor', 'FieldMonitor', 'SParameter', 'VoltageMonitor',
                    'Group', 'Face', 'Curve', 'WCS', 'Probe', 'LumpedElement',
                    'Import', 'SAT', 'SAB', 'STL', 'STEP', 'Boolean',
                    'Union', 'Subtract', 'Intersect']
        for i, line in enumerate(lines):
            stripped = line.rstrip()
            for kw in keywords:
                if kw in stripped:
                    print(f'  [{kw}] Line {i+1}: {stripped[:120]}')
                    break
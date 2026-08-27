# -*- coding: utf-8 -*-
"""对比新旧版 SAB 头部结构"""
import struct

files = [
    r'D:\training\cst\CST Phone 5G\Model\3D\CSTphone2022_1.sab',
    r'D:\training\cst\IFA_design\ModelCache\Model.sab',
    r'D:\training\cst\dipole1_monitors7\ModelCache\Model.sab',
]

for path in files:
    data = open(path, 'rb').read()
    print('=' * 70)
    print(path.split('cst\\')[-1])
    print(f'大小: {len(data)}')
    print('前 260 字节逐字节:')
    for off in range(0, 260):
        b = data[off]
        ch = chr(b) if 32 <= b < 127 else '.'
        print(f'  {off:4d}: {b:02x} {b:5d}  {ch}')
    print()

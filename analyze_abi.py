# -*- coding: utf-8 -*-
"""分析 Model.abi (AssemblyBlockInf) 格式"""
import glob, os

def dump(data, start, end, base=0):
    for off in range(start, end, 16):
        chunk = data[off:off+16]
        hexs = ' '.join(f'{b:02x}' for b in chunk)
        asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        print(f'  {base+off:6d}  {hexs:<48s}  {asc}')

for p in sorted(glob.glob(r'D:\training\cst\IFA_design\Model\3D\Model.abi')):
    data = open(p, 'rb').read()
    print('=' * 70)
    print(f'文件: {p}  ({len(data)} 字节)')
    print('完整内容:')
    dump(data, 0, len(data))

print('\n\n' + '=' * 70)
print('CST Phone 5G 的 Model.abi (3773 字节, 更大的装配) 前 400 字节:')
data = open(r'D:\training\cst\CST Phone 5G\Model\3D\Model.abi', 'rb').read()
dump(data, 0, min(400, len(data)))

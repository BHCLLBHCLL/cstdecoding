# -*- coding: utf-8 -*-
"""检查 Model.abi 等文件的格式, 并分析 SAR/RCS 未解压 .cst 里的 .sab"""
import glob, os, struct

# 1) 检查已解压目录里的 Model.abi 头部
print('=== Model.abi 文件头部检查 ===')
abi_files = glob.glob(r'D:\training\cst\**\Model.abi', recursive=True)
for p in abi_files[:6]:
    data = open(p, 'rb').read()
    head = data[:16]
    print(f'{os.path.relpath(p, "D:/training/cst")}  ({len(data)} 字节)')
    print(f'  头部16字节: {head!r}  hex={head.hex()}')
    if head[:15] == b'ACIS BinaryFile':
        print(f'  -> ACIS SAB 格式, version={data[15]:#04x}')
    print()

# 2) 检查已解压目录里所有可能的几何文件 (abi/sat/sab 头部)
print('=== 所有 .abi 文件 (含版本) ===')
for p in abi_files:
    data = open(p, 'rb').read()
    if data[:15] == b'ACIS BinaryFile':
        print(f'  {os.path.relpath(p, "D:/training/cst")}: SAB version={data[15]}')
    else:
        print(f'  {os.path.relpath(p, "D:/training/cst")}: 非SAB, 头={data[:8]!r}')

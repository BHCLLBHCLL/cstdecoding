# -*- coding: utf-8 -*-
"""提取更多cst文件并分析其内容结构"""
import sys, os
sys.path.insert(0, '.')
from cst_parser import find_eocd, parse_central_directory, parse_eocd_comment, read_entry

def extract_cst(path, outdir, max_size=None):
    """提取cst文件的所有条目"""
    os.makedirs(outdir, exist_ok=True)
    extracted = []
    with open(path, 'rb') as f:
        size = os.fstat(f.fileno()).st_size
        window = min(size, 65535 + 22)
        f.seek(size - window)
        tail = f.read(window)
        eocd_in_tail, cd_off, cd_size, count, comment = find_eocd(tail, size)
        f.seek(cd_off)
        cd_data = f.read(cd_size)
        entries = parse_central_directory(cd_data, count)
        for e in entries:
            try:
                f.seek(0)
                content, crc_ok, local = read_entry(f, e)
                if max_size and len(content) > max_size:
                    content = content[:max_size]
                outpath = os.path.join(outdir, e['name'].replace('/', os.sep))
                os.makedirs(os.path.dirname(outpath) or '.', exist_ok=True)
                with open(outpath, 'wb') as out:
                    out.write(content)
                extracted.append((e['name'], len(content)))
            except Exception as ex:
                extracted.append((e['name'], f'ERROR: {ex}'))
    return extracted

# 1. 提取 microstrip_patch_antenna.cst (2023:3, 无SAB)
print('=== 提取 microstrip_patch_antenna.cst (CST 2023:3, 无SAB) ===')
entries = extract_cst(r'D:\training\cst\microstrip_patch_antenna.cst',
                      r'extracted_msa', max_size=10*1024*1024)
for name, sz in entries:
    print(f'  {name}: {sz}')

# 2. 提取 SAR Head Hand and Phone.cst 的SAB文件
print('\n=== 提取 SAR Head Hand and Phone.cst 的 SAB 文件 ===')
sab_entries = []
with open(r'D:\training\cst\SAR Head Hand and Phone.cst', 'rb') as f:
    size = os.fstat(f.fileno()).st_size
    window = min(size, 65535 + 22)
    f.seek(size - window)
    tail = f.read(window)
    eocd_in_tail, cd_off, cd_size, count, comment = find_eocd(tail, size)
    f.seek(cd_off)
    cd_data = f.read(cd_size)
    entries = parse_central_directory(cd_data, count)

    os.makedirs(r'extracted_sar', exist_ok=True)
    for e in entries:
        if e['name'].lower().endswith('.sab'):
            try:
                f.seek(0)
                content, crc_ok, local = read_entry(f, e)
                outname = os.path.basename(e['name'])
                outpath = os.path.join(r'extracted_sar', outname)
                with open(outpath, 'wb') as out:
                    out.write(content)
                print(f'  {e["name"]}: {len(content):,} 字节 -> {outpath}')
                sab_entries.append(outpath)
            except Exception as ex:
                print(f'  {e["name"]}: ERROR {ex}')

# 3. 检查2023:3文件中的关键文件内容
print('\n=== 分析 microstrip_patch_antenna 的关键文件 ===')
key_files = [
    r'extracted_msa\Model\3D\Model.abi',
    r'extracted_msa\Model\3D\Model.mod',
    r'extracted_msa\Model\3D\Model.crs',
    r'extracted_msa\Model\3D\Model.fct',
    r'extracted_msa\Model\3D\Model.sjson',
]
for kf in key_files:
    if os.path.exists(kf):
        content = open(kf, 'rb').read()
        print(f'\n--- {kf} ({len(content)} 字节) ---')
        # 尝试文本解码
        try:
            text = content.decode('utf-8')
            print(text[:2000])
        except:
            print(f'  二进制内容: {content[:100].hex()}')
    else:
        print(f'\n--- {kf}: 不存在 ---')

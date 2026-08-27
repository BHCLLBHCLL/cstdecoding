# -*- coding: utf-8 -*-
"""顺序解析 HeadHand_1.sab 直到出错位置, 打印出错前的解析轨迹 (最后 60 步)"""
import struct, sys

data = open(r'D:\training\cst\SAR Head Hand and Phone\HeadHand_1.sab', 'rb').read()
LIMIT = 17501936  # 出错位置

type_names = {}
trace = []  # (pos, desc)

def parse_chain(p):
    chain = []
    while True:
        t = data[p]
        if t not in (0x0d, 0x0e):
            raise ValueError(f'@{p} 链标签 {t:02x}')
        ln = data[p+1]
        payload = data[p+2:p+2+ln]
        if payload == b'End-of-ACIS-data':
            return ('END',), p + 2 + ln
        if ln == 4:
            tid = struct.unpack('<i', payload)[0]
            chain.append((t, None, tid))
            return chain, p + 2 + ln
        if ln >= 5 and payload[-5] == 0x25:
            tid = struct.unpack('<i', payload[-4:])[0]
            name = payload[:-5].decode('latin1') if ln > 5 else None
        elif ln == 5 and payload[0] == 0x04:
            tid = struct.unpack('<I', payload[1:5])[0]
            chain.append((t, None, tid))
            return chain, p + 2 + ln
        else:
            raise ValueError(f'@{p} 异常类型链 (ln={ln}): {payload[:12]!r}')
        if name is not None:
            type_names[tid] = name
        chain.append((t, name, tid))
        p += 2 + ln
        if t == 0x0d:
            return chain, p

pos = 0
# 跳过头部
assert data[:15] == b'ACIS BinaryFile'
pos = 15
ver = data[pos]; pos += 1
pos += 15
for _ in range(3):
    ln = data[pos+1]; pos += 2 + ln
for _ in range(3):
    pos += 9
pos += 1
ln = data[pos+1]; pos += 2 + ln
if data[pos] == 0x04:
    for _ in range(3):
        pos += 5
    if data[pos] == 0x0a:
        pos += 1

depth = 0
try:
    while pos < LIMIT:
        tag = data[pos]
        if tag == 0x0b:
            trace.append((pos, f'close (depth {depth}->{depth-1})')); depth -= 1; pos += 1
        elif tag in (0x0a, 0x0f, 0x10, 0x11):
            names = {0x0a: 'START-a', 0x0f: 'START-f', 0x10: 'START-10', 0x11: 'START-1'}
            desc = names[tag]
            pos += 1
            if data[pos] in (0x0d, 0x0e):
                r = parse_chain(pos)
                if r[0] == ('END',):
                    trace.append((pos, 'END marker')); break
                chain, pos = r
                cn = '/'.join((n or f'#{i}') for _, n, i in chain)
                trace.append((pos, f'{desc} chain=[{cn}]')); depth += 1
            else:
                trace.append((pos, f'{desc} 无链! 下字节 {data[pos]:02x}')); depth += 1
        elif tag in (0x0d, 0x0e):
            r = parse_chain(pos)
            if r[0] == ('END',):
                trace.append((pos, 'END marker')); break
            chain, pos = r
            cn = '/'.join((n or f'#{i}') for _, n, i in chain)
            trace.append((pos, f'chain(no-start) [{cn}]'))
        elif tag == 0x07:
            ln = data[pos+1]; trace.append((pos, f'str "{data[pos+2:pos+2+ln].decode("latin1", "replace")[:24]}"')); pos += 2 + ln
        elif tag == 0x04:
            v = struct.unpack('<I', data[pos+1:pos+5])[0]; trace.append((pos, f'uint {v}')); pos += 5
        elif tag == 0x0c:
            v = struct.unpack('<i', data[pos+1:pos+5])[0]; trace.append((pos, f'int {v}')); pos += 5
        elif tag == 0x15:
            v = struct.unpack('<I', data[pos+1:pos+5])[0]; trace.append((pos, f'uint2 {v}')); pos += 5
        elif tag == 0x19:
            v = struct.unpack('<h', data[pos+1:pos+3])[0]; trace.append((pos, f'int16 {v}')); pos += 3
        elif tag == 0x06:
            v = struct.unpack('<d', data[pos+1:pos+9])[0]; trace.append((pos, f'dbl {v:.6g}')); pos += 9
        elif tag == 0x13:
            x, y, z = struct.unpack('<3d', data[pos+1:pos+25])
            trace.append((pos, f'pos ({x:.4f},{y:.4f},{z:.4f})')); pos += 25
        elif tag == 0x14:
            x, y, z = struct.unpack('<3d', data[pos+1:pos+25])
            trace.append((pos, f'vec ({x:.4f},{y:.4f},{z:.4f})')); pos += 25
        else:
            trace.append((pos, f'未知 {tag:02x}')); pos += 1
except ValueError as e:
    print(f'解析中断: {e}')

print(f'\n=== 出错前最后 70 步轨迹 ===')
for p, d in trace[-70:]:
    print(f'  @{p:<10d} {d}')

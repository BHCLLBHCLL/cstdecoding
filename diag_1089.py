# -*- coding: utf-8 -*-
"""诊断 @1089 栈下溢: 打印出错前完整解析轨迹(带字节hex)"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

# 解析头部
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
print(f'实体流起始: @{pos}, 头部版本={ver:02x}')

# hex dump 1000-1110
print('\n--- hex dump 1000-1110 ---')
for base in range(1000, 1110, 16):
    hexstr = ' '.join(f'{data[i]:02x}' for i in range(base, min(base+16, 1110)))
    ascii_str = ''.join(chr(data[i]) if 32 <= data[i] < 127 else '.' for i in range(base, min(base+16, 1110)))
    print(f'{base:6d}  {hexstr:<48}  {ascii_str}')

# 从实体流开始逐tag跟踪, 打印每个tag位置和含义
type_names = {}

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

print('\n--- 逐tag轨迹 (到1100) ---')
stack = []
trace = []
p = pos
try:
    while p < 1120:
        tag = data[p]
        if tag == 0x0b:
            if stack:
                kind, name, sp, nf, ns = stack.pop()
                trace.append((p, len(stack), f'CLOSE {kind}:{name or "?"} (opened @{sp}, {nf}f {ns}s)'))
            else:
                trace.append((p, len(stack), f'CLOSE *** UNDERFLOW ***'))
                # 打印之前的20个事件
                print('!!! 栈下溢 !!!')
                for tp, td, desc in trace[-25:]:
                    print(f'  @{tp:6d} d={td}  {desc}')
                break
            p += 1
        elif tag in (0x0a, 0x11, 0x0f, 0x10):
            kind = 'anon' if tag == 0x0a else f'rec{tag:02x}'
            p += 1
            if data[p] in (0x0d, 0x0e):
                r = parse_chain(p)
                if r[0] == ('END',):
                    trace.append((p, len(stack), 'END-of-ACIS'))
                    break
                chain, p = r
                cn = '/'.join((n or f'#{i}') for _, n, i in chain)
                stack.append([kind, cn, p, 0, 0])
            else:
                stack.append([kind, None, p, 0, 0])
            trace.append((p, len(stack), f'OPEN {kind}:{stack[-1][1] or "?"}'))
            depth = len(stack)
        elif tag in (0x0d, 0x0e):
            r = parse_chain(p)
            if r[0] == ('END',):
                trace.append((p, len(stack), 'END-of-ACIS'))
                break
            chain, p = r
            cn = '/'.join((n or f'#{i}') for _, n, i in chain)
            stack.append(['rec', cn, p, 0, 0])
            trace.append((p, len(stack), f'OPEN(chain) {cn}'))
        elif tag == 0x07:
            ln = data[p+1]
            s = data[p+2:p+2+ln].decode('latin1', 'replace')
            if stack: stack[-1][3] += 1
            trace.append((p, len(stack), f'str "{s[:30]}"'))
            p += 2 + ln
        elif tag in (0x04, 0x0c, 0x15):
            v = struct.unpack('<i', data[p+1:pos+5] if False else data[p+1:p+5])[0]
            if stack: stack[-1][3] += 1
            trace.append((p, len(stack), f'i32 {v}'))
            p += 5
        elif tag == 0x19:
            if stack: stack[-1][3] += 1
            trace.append((p, len(stack), f'i16'))
            p += 3
        elif tag == 0x06:
            v = struct.unpack('<d', data[p+1:p+9])[0]
            if stack: stack[-1][3] += 1
            trace.append((p, len(stack), f'dbl {v:.6g}'))
            p += 9
        elif tag == 0x13:
            x, y, z = struct.unpack('<3d', data[p+1:p+25])
            if stack: stack[-1][3] += 1
            trace.append((p, len(stack), f'pos ({x:.4g},{y:.4g},{z:.4g})'))
            p += 25
        elif tag == 0x14:
            x, y, z = struct.unpack('<3d', data[p+1:p+25])
            if stack: stack[-1][3] += 1
            trace.append((p, len(stack), f'vec ({x:.4g},{y:.4g},{z:.4g})'))
            p += 25
        else:
            print(f'@{p} 未知标签 {tag:02x}')
            for tp, td, desc in trace[-15:]:
                print(f'  @{tp:6d} d={td}  {desc}')
            break
except Exception as e:
    print(f'异常: {e}')

# 打印最后50个事件
print('\n--- 最后50个事件 ---')
for tp, td, desc in trace[-50:]:
    print(f'  @{tp:6d} d={td}  {desc}')

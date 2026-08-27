# -*- coding: utf-8 -*-
"""栈式严格解析器: 验证记录嵌套语法
语法假设:
  记录开始: 11 <类型链> | 0a (匿名)
  记录结束: 0b (弹栈)
  字段与子记录可交错出现
在 CSTphone (已知可顺序解析到底) 上验证栈是否平衡、最大深度、匿名记录形态。
"""
import struct, sys, collections

def parse_chain(data, p, type_names):
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

def parse(path, max_steps=None):
    data = open(path, 'rb').read()
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

    type_names = {}
    stack = []          # 每项: (kind, name, start_pos, nfields, nsubs)
    depth_hist = collections.Counter()
    anon_shapes = collections.Counter()   # 匿名记录的字段形态签名
    cur_anon_sig = []
    events = []         # (pos, depth, desc) 最近事件
    steps = 0
    endpos = None

    while pos < len(data) - 16:
        if max_steps and steps > max_steps:
            break
        steps += 1
        tag = data[pos]
        if tag == 0x0b:
            if not stack:
                return {'error': f'@{pos} 栈下溢 (多余close)', 'pos': pos}
            kind, name, sp, nf, ns = stack.pop()
            if kind == 'anon':
                sig = tuple(cur_anon_sig)
                anon_shapes[sig] += 1
                cur_anon_sig = []
            events.append((pos, len(stack), f'close {kind}:{name or "?"} @{sp} fields={nf} subs={ns}'))
            pos += 1
        elif tag in (0x0a, 0x11, 0x0f, 0x10):
            kind = 'anon' if tag == 0x0a else 'rec'
            pos += 1
            if data[pos] in (0x0d, 0x0e):
                r = parse_chain(data, pos, type_names)
                if r[0] == ('END',):
                    endpos = pos
                    events.append((pos, len(stack), 'END-of-ACIS'))
                    break
                chain, pos = r
                cn = '/'.join((n or f'#{i}') for _, n, i in chain)
                stack.append([kind, cn, pos, 0, 0])
            else:
                stack.append([kind, None, pos, 0, 0])
            events.append((pos, len(stack), f'open {kind}'))
            depth_hist[len(stack)] += 1
        elif tag in (0x0d, 0x0e):
            r = parse_chain(data, pos, type_names)
            if r[0] == ('END',):
                endpos = pos
                break
            chain, pos = r
            cn = '/'.join((n or f'#{i}') for _, n, i in chain)
            stack.append(['rec', cn, pos, 0, 0])
            depth_hist[len(stack)] += 1
        elif tag == 0x07:
            ln = data[pos+1]
            s = data[pos+2:pos+2+ln].decode('latin1', 'replace')
            if stack: stack[-1][3] += 1
            if stack and stack[-1][0] == 'anon':
                cur_anon_sig.append(f'str:{s[:8]}')
            pos += 2 + ln
        elif tag in (0x04, 0x0c, 0x15):
            v = struct.unpack('<i', data[pos+1:pos+5])[0]
            if stack: stack[-1][3] += 1
            if stack and stack[-1][0] == 'anon':
                cur_anon_sig.append(f'i:{v}' if v != -1 else 'i:-1')
            pos += 5
        elif tag == 0x19:
            if stack: stack[-1][3] += 1
            if stack and stack[-1][0] == 'anon':
                cur_anon_sig.append('i16')
            pos += 3
        elif tag == 0x06:
            if stack: stack[-1][3] += 1
            if stack and stack[-1][0] == 'anon':
                cur_anon_sig.append('d')
            pos += 9
        elif tag == 0x13:
            x, y, z = struct.unpack('<3d', data[pos+1:pos+25])
            ok = abs(x) < 1e6 and abs(y) < 1e6 and abs(z) < 1e6
            if stack: stack[-1][3] += 1
            if stack and stack[-1][0] == 'anon':
                cur_anon_sig.append('p' if ok else 'P!')
            pos += 25
        elif tag == 0x14:
            if stack: stack[-1][3] += 1
            if stack and stack[-1][0] == 'anon':
                cur_anon_sig.append('v')
            pos += 25
        else:
            return {'error': f'@{pos} 未知标签 {tag:02x}', 'pos': pos, 'stack_top': stack[-3:] if stack else []}
    else:
        endpos = pos

    return {
        'endpos': endpos, 'filelen': len(data), 'steps': steps,
        'stack_left': len(stack), 'stack_top': [s[1] for s in stack[-5:]],
        'max_depth': max(depth_hist) if depth_hist else 0,
        'depth_top10': dict(sorted(depth_hist.items())[-10:]),
        'anon_shapes': dict(anon_shapes.most_common(15)),
        'events_tail': events[-30:],
    }

if __name__ == '__main__':
    import json
    r = parse(r'extracted/Model/3D/CSTphone2022_1.sab')
    print('=== CSTphone2022_1.sab (ACIS 28, 已知可解析) ===')
    for k in ('endpos', 'filelen', 'steps', 'stack_left', 'max_depth', 'stack_top'):
        print(f'  {k}: {r.get(k)}')
    print('  深度分布(最后10):', r.get('depth_top10'))
    print('  匿名记录形态(top15):')
    for sig, c in r.get('anon_shapes', {}).items():
        print(f'    {c:6d} × {sig}')
    if 'error' in r:
        print('  错误:', r['error'])
        for ev in r.get('events_tail', [])[-15:]:
            print('   ', ev)

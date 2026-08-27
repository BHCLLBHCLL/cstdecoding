# -*- coding: utf-8 -*-
"""深入诊断: 检查 #6/#7/#4 记录及其子记录的完整字节结构"""
import struct

data = open(r'extracted/Model/3D/CSTphone2022_1.sab', 'rb').read()

def hexdump(start, end):
    for base in range(start, end, 16):
        hexstr = ' '.join(f'{data[i]:02x}' for i in range(base, min(base+16, end)))
        ascii_str = ''.join(chr(data[i]) if 32 <= data[i] < 127 else '.' for i in range(base, min(base+16, end)))
        print(f'{base:6d}  {hexstr:<48}  {ascii_str}')

# 关键区域
print('=== @855-895: rgb_color 关闭后, #6/#7/#4 开始 ===')
hexdump(855, 895)

print('\n=== @905-950: 字符串字段和 #5 子记录开始 ===')
hexdump(905, 950)

print('\n=== @975-995: #5 关闭后, #9 开始 ===')
hexdump(975, 995)

print('\n=== @1085-1115: 连续4个0b ===')
hexdump(1085, 1115)

# 检查字符串字段的确切内容
print('\n=== 字符串字段分析 ===')
pos = 912
tag = data[pos]
ln = data[pos+1]
print(f'@{pos}: tag={tag:02x}, len={ln} ({ln}字节)')
s = data[pos+2:pos+2+ln]
print(f'  内容: {s!r}')
print(f'  结束位置: @{pos+2+ln}')
print(f'  下一字节 @{pos+2+ln}: {data[pos+2+ln]:02x}')
print(f'  再下一字节 @{pos+2+ln+1}: {data[pos+2+ln+1]:02x}')

# 检查 #6/#7/#4 的类型链
print('\n=== #6/#7/#4 类型链分析 (从@860) ===')
pos = 860
print(f'@{pos}: tag={data[pos]:02x} (应该是11)')
pos += 1
# 手动解析链
chain_elements = []
while True:
    t = data[pos]
    ln = data[pos+1]
    payload = data[pos+2:pos+2+ln]
    if ln >= 5 and payload[-5] == 0x25:
        tid = struct.unpack('<i', payload[-4:])[0]
        name = payload[:-5].decode('latin1') if ln > 5 else None
    elif ln == 4:
        tid = struct.unpack('<i', payload)[0]
        name = None
    else:
        tid = None
        name = payload.decode('latin1', 'replace')
    chain_elements.append((t, ln, name, tid, payload.hex()))
    pos += 2 + ln
    if t == 0x0d:
        break

print(f'链元素数: {len(chain_elements)}')
for i, (t, ln, name, tid, ph) in enumerate(chain_elements):
    print(f'  [{i}] tag={t:02x} len={ln} name={name} id={tid} payload={ph}')
print(f'链结束后位置: @{pos}')
print(f'下一字节: {data[pos]:02x}')

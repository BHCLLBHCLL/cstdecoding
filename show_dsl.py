# -*- coding: utf-8 -*-
"""提取 Model.mod 中的关键 DSL 语法块: Transform / Material / Brick / DiscretePort"""
import re

text = open('mod_files/SingleAntenna.mod', encoding='latin1').read()
m = re.search(r"With Transform.*?End With", text, re.S)
print("=== Transform 块 (SingleAntenna) ===")
print(m.group(0))

text2 = open('mod_files/microstrip_patch_antenna.mod', encoding='latin1').read()
m2 = re.search(r"'@ define material.*?End With", text2, re.S)
print("\n=== Material 定义 (patch_antenna) ===")
print(m2.group(0)[:1500])

blocks = re.findall(r"With Brick.*?End With", text2, re.S)
for i, b in enumerate(blocks):
    print(f"\n=== Brick 块 {i+1} (patch_antenna) ===")
    print(b)

text3 = open('mod_files/SingleAntenna.mod', encoding='latin1').read()
m3 = re.search(r"With DiscretePort.*?End With", text3, re.S)
print("\n=== DiscretePort 块 (SingleAntenna) ===")
print(m3.group(0))

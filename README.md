# cstdecoding — CST 项目逆向工程、查看器与编辑器

解析并编辑 CST Studio Suite 的 `.cst` 工程文件（DE-ZIP 容器、ACIS SAB、Model.mod）。

**定位**

- 逆向：私有容器与几何格式的读/写
- 查看器：导航树、3D 视口、参数与结果
- 编辑器：建模 / 材料 / 端口等工程对象的修改与保存
- **不含求解器**：不运行电磁仿真；求解设置仅原样保留

开发规划见 [`DEV_PLAN.md`](DEV_PLAN.md)，差距分析见 [`function_gap_analysis.md`](function_gap_analysis.md)。

运行：`python cst_gui.py [project.cst]`。测试：`python -m pytest tests -q`。

---

## 1. .cst 容器格式（DE-ZIP）

.cst 是 CST 定制的 ZIP 变体容器：

| 结构 | 标准 ZIP | CST DE-ZIP | 大小 |
|---|---|---|---|
| 本地文件头 | `PK\x03\x04` | `DE\x03\x04` | 34 字节（多 4 字节字段 X） |
| 中央目录条目 | `PK\x01\x02` | `DE\x01\x02` | 50 字节（多 4 字节字段 X） |
| EOCD | `PK\x05\x06` | `PK\x05\x06`（不变） | 22 字节 |

- 4 字节 X 插在 "DOS date" 与 "CRC32" 之间（疑似 DOS date+time 打包的修改时间），后续字段整体后移
- 压缩方法沿用标准值：`8`=deflate（raw，无 zlib 头），`0`=store
- EOCD 注释区存储元信息：`-cst-version:2024:0:20230801-license:...`

核心解析器：`cst_parser.py`（提取 + CRC 校验 + manifest.json 生成）

## 2. CST 项目几何存储架构（核心成果）

```
.cst 容器
├── Model/3D/Model.mod          ← 建模历史脚本（VBScript DSL）= 几何"源代码"
├── Model/Parameters.json       ← 参数表 {name, expr, value}
├── Model/3D/<Name>_<Id>.sab    ← 导入的外部 ACIS CAD 模型（SAT 构建器 .Read）
├── ModelCache/Model.sab        ← 建模器派生的 ACIS 缓存（多段容器）
├── ModelCache/Model.sab.index  ← 段偏移索引：int32 段数 + N×int64 段偏移
└── Model/3D/ModelHistory.json  ← .mod 的结构化 JSON 版本（新版双轨存储）
```

**关键结论**：
- 每个 CST 项目都有 `Model.mod`，几何以参数化脚本形式存储（"源代码"）
- `Model/3D/*.sab` 是**用户导入**的外部 ACIS 模型（如手机 CAD、人体头手模型），
  通过 `With SAT .FileName "*xxx.sab" .Id "1" ... .Read` 导入，嵌入副本命名为 `<名>_<Id>.sab`
- `ModelCache/Model.sab` 是**派生缓存**（重放 .mod + 导入模型后由建模器生成），
  可删除；部分项目保存了它（多段容器：主段 + 多个 bbox 缓存段）
- CST 2023:3 的小项目（8/11 个）只保存 .mod，无任何 SAB → 完全参数化

## 3. Model.mod — 参数化建模 DSL

VBScript 风格，每条历史操作 = `'@ caption` 注释 + `[VERSION]cst|acis|date[/VERSION]` 标记 + 代码块。

### 已确认的语法元素

**单位/求解器/边界**：
```vbscript
With Units
    .SetUnit "Length", "mm"
    .SetUnit "Frequency", "GHz"
End With
Solver.FrequencyRange "0.5", "8"
With Boundary
    .Xmin "expanded open"   ' 边界条件
End With
```

**参数定义（VBA 级）**：
```vbscript
MakeSureParameterExists "antenna_metal_thickness", "0.01"
SetParameterDescription "antenna_metal_thickness", "antenna element metal thickness"
```
参数表另存 `Model/Parameters.json`：`{"parameters": [{"name": "W", "expr": "95", "value": "95"}], "version": 1}`

**几何构建器（尺寸为参数表达式）**：
```vbscript
With Brick                       ' 长方体
     .Reset
     .Name "ant"                 ' 形状名
     .Component "component1"     ' 所属组件
     .Material "PEC"             ' 材料
     .Xrange "-W/2", "W/2"       ' 参数表达式!
     .Yrange "-L/2", "L/2"
     .Zrange "0", "0"            ' Zrange 相同 = 平面片(零厚度)
     .Create
End With
```

**材料定义**：
```vbscript
With Material
     .Reset
     .Name "Rogers RT-duroid 5880 (loss free)"
     .Folder ""
     .FrqType "all"
     .Type "Normal"              ' Normal / Lossy metal / ...
     .SetMaterialUnit "GHz", "mm"
     .Epsilon "2.2"              ' 介电常数
     .Mu "1.0"                   ' 磁导率
     .Kappa "0.0"                ' 电导率
     .TanD "0.0"                 ' 损耗角正切
     .Colour "0.75", "0.95", "0.85"
     .Create
End With
```

**SAB/SAT 导入**：
```vbscript
With SAT
     .Reset
     .FileName "*CSTphone2022.sab"   ' * 前缀 = 项目内嵌入文件
     .Id "1"                          ' → Model/3D/CSTphone2022_1.sab
     .Version "9.0"
     .ScaleToUnit "0"
     .ImportToActiveCoordinateSystem "True"
     .Curves "True"
     .Read
End With
```

**WCS（工作坐标系）与拾取**：
```vbscript
WCS.ActivateWCS "local"
Pick.PickEndpointFromId "component1:GND", "3"   ' 按实体 ID 拾取端点
Pick.PickMidpointFromId "component1:GND", "2"   ' 拾取中点
Pick.PickFaceFromId "component1:Antenna1", "1"  ' 拾取面
WCS.AlignWCSWithSelected "Point"                ' 对齐 WCS
WCS.RotateWCS "w", "45"                         ' 绕 w 轴旋转
```

**布尔运算**：
```vbscript
Solid.Subtract "component1:solid1", "component1:Antenna1"
```

**变换（镜像/平移/旋转/阵列）**：
```vbscript
With Transform
     .Reset
     .Name "component1:Antenna1"
     .Origin "Free"
     .Center "0", "0", "0"
     .PlaneNormal "1", "0", "0"     ' 镜像面法向
     .MultipleObjects "True"
     .Repetitions "1"
     .Transform "Shape", "Mirror"   ' 操作类型
End With
```

**离散端口**：
```vbscript
With DiscretePort
     .Reset
     .PortNumber "1"
     .Type "SParameter"
     .Impedance "50.0"
     .SetP1 "True", "40.5", "0", "0"    ' 坐标
     .SetP2 "True", "0", "0", "0"
     .LocalCoordinates "True"
     .Position "end1"                    ' 也可绑定拾取点
     .Create
End With
```

**监视器**（场/远场采样）：
```vbscript
With Monitor
     .Reset
     .Domain "Frequency"
     .FieldType "Hfield"               ' Hfield / Efield / Farfield / Powerflow...
     .Dimension "Volume"
     .Coordinates "Structure"
     .SetSubvolume "-0.5", "0.5", "-75", "75", "0", "0"
     .CreateUsingLinearStep "0.95", "6.95", "1"   ' fmin, fmax, step
End With
```

**组件/分组管理**：
```vbscript
Component.New "component1"
Group.Add "AntennaMetals", "mesh"
Solid.AddToMaterialGroup / Group.Rename ...
```

### ModelHistory.json（结构化双轨）
`{general: {version, acis, units, freq range...}, history: [{caption, version, hidden, type: "vba", code: [行...]}]}`
phone 项目（2022.0 创建 / 2024.0 保存）同时存在 .mod 与 ModelHistory.json。

## 4. ACIS SAB 二进制格式

`ModelCache/Model.sab` 与导入的 `*.sab` 都是 ACIS BinaryFile。

### 头部
```
"ACIS BinaryFile" + ver(1) + extra(15) + 0x07 str(product_id)
+ 0x07 str(acis_version) + 0x07 str(date)
+ 0x06 f64 ×3 (mm_per_unit, resabs, resnor) + 0x0a
+ 0x07 str(uuid)
[旧版: 0x04 u32 ×3 (实体数等) + 0x0a]
```

### 字段标签
| 标签 | 含义 |
|---|---|
| `0x04` | uint32（实体引用/指针） |
| `0x06` | double |
| `0x07` | 字符串（1 字节长度 + ASCII） |
| `0x0a` | 匿名记录起始 / 分隔符 |
| `0x0b` | 记录结束（弹栈） |
| `0x0c` | int32 |
| `0x0d` | 类型链尾元素 |
| `0x0e` | 类型链中元素 |
| `0x0f`/`0x10`/`0x11` | 记录起始（0x11 带类型链） |
| `0x13` | position（3×double） |
| `0x14` | vector（3×double） |
| `0x15` | uint32（指针/引用） |
| `0x19` | int16 |

### 类型链编码（版本差异）
- ACIS 31+ 标准编码：`<name?> 0x25 <int32 id>`
- ACIS 28.x 短引用：`0x04 <int32 id>`（ln=4，单元素链，隐式链尾）
- ACIS 28.x 整数符号引用：`0x04 <uint32 val>`（ln=5，空符号=0）
- 类型 ID 可中途重定义（如 id 20/21 均曾映射 edge）→ 解析需按位置更新 type_names

### 结构要点
- 多段容器：主段 + N 个嵌入 SAB 段（bbox 缓存），每段以 `End-of-ACIS-data` 链（`0d 10` + 字符串，无 25+id）结束
- `.sab.index`：`int32 段数 + N×int64 段偏移`，与段起始位置精确对应（SAR Model.sab 66 段已验证）
- **记录嵌套非纯树形**：`0x11` 起始标签数 >> `0x0b` 结束标签数（36189 vs 19901，CSTphone2022_1.sab），
  大多数记录无显式结束符 → 顺序解析可行（batch_sab.py），栈式严格解析会下溢
- 文件尾部 `End-of-ACIS-data` 后可能存在残余字节（HeadHand_1.sab 尾部 ln=0 链），属正常文件结束

## 5. 11 个样本文件分析结果

| 文件 | CST 版本 | 条目 | SAB | 几何来源 |
|---|---|---|---|---|
| CST Phone 5G.cst | 2024:0 | 58 | 1 | .mod + 导入 CSTphone2022.sab |
| IFA_design.cst | 2023:3 | 29 | 0 | 纯参数化 (7 Brick) |
| RCS of a Ship.cst | 2024:0 | 117 | 1 | .mod + ModelCache 缓存 |
| SAR Head Hand and Phone.cst | 2022:0 | 143 | 3 | .mod + 导入 HeadHand.sab + CST-SmartPhone.sab + 缓存 |
| SingleAntenna.cst | 2023:3 | 30 | 0 | 纯参数化 (3 Brick + mirror + subtract) |
| dipole1_monitors7.cst | 2023:3 | 29 | 0 | 纯参数化 (1 Brick) |
| dipole1_monitors7v2.cst | 2023:3 | 31 | 0 | v1 + port Brick + 布尔减 + 离散端口 |
| dipole1_monitors7v3.cst | 2023:3 | 31 | 0 | v2 + 求解器类型切换历史 |
| microstrip_patch_antenna.cst | 2023:3 | 29 | 0 | 纯参数化 (2 Brick + 材料) |
| microstrip_patch_antennav2.cst | 2023:3 | 29 | 0 | v1 + 频率范围修改 + 监视器增删 |
| microstrip_patch_antennav3.cst | 2023:3 | 29 | 0 | v2 + 离散端口 |

同项目多版本（dipole v1→v2→v3, patch v1→v2→v3）显示 .mod 是**追加式操作日志**：
修改操作（改频率、删监视器、切换求解器）都追加新代码块，不回溯修改。

## 6. 工具脚本

| 脚本 | 功能 |
|---|---|
| `cst_parser.py` | .cst 容器解析/提取/CRC 校验/manifest（核心） |
| `batch_cst.py` | 批量分析所有 .cst 容器结构 |
| `batch_sab.py` | 批量解析 SAB（多段/新旧头部/版本差异兼容） |
| `sab_parser.py` | 单 SAB 解析 → JSON 报告 |
| `extract_mod.py` | 提取 8 个 2023:3 项目的 Model.mod |
| `extract_sar_mod.py` | 提取 SAR 项目的 Model.mod/Parameters.json |
| `extract_more.py` / `extract_sar.py` | 提取指定 .cst 的条目 |
| `analyze_new_sab.py` | 分析新提取 SAB 的实体分布/bbox |
| `stack_parser.py` / `depth_profile.py` / `tag_stats.py` | 记录嵌套语法研究（证明非纯树形） |
| `scan_typedefs.py` | 扫描类型定义与 ID 重定义现象 |

## 7. 提取产物

- `extracted/` — CST Phone 5G（phone.cst）
- `extracted_msa/` — microstrip_patch_antenna
- `extracted_sar/` — SAR 项目（3 个 SAB + Model.mod + Parameters.json）
- `extracted_ship/` — RCS of a Ship（含完整 ModelCache）
- `mod_files/` — 8 个 2023:3 项目的 Model.mod 汇集

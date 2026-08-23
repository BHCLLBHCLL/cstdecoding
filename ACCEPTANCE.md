# M12 验收矩阵

对照 README §5 的 11 个样本。大文件不入库；本机目录默认 `D:\training\cst`，或环境变量 `CST_SAMPLES`。

自动化：`tests/test_cst_accept.py`（`QT_QPA_PLATFORM=offscreen`）。

## 1. 每一样本检查项

| 项 | 含义 | 通过标准 |
|---|---|---|
| 打开 | `open_cst` + GUI `_load_cst` | 有 `Model.mod`，条目数 ≥ 期望下限 |
| 另存 | `write_cst` 后再 `open_cst` | 条目名集合一致 |
| 树节点 | Components / Materials / Ports / Monitors / Parameters / 树根类别 | 不低于样本期望；树根 ≥ 8 |
| 截图 | Copy View 抓图 | pixmap 非空；对照下表清单 |

SAR（约 50 MB、多 SAB）在矩阵中**打开并另存容器**，默认不细分 HeadHand SAB（`load_sab=False`），避免验收超时。Phone / Ship 的 SAB 显示由既有用例覆盖。

## 2. 11 样本矩阵

| id | 文件 | 类型 | 打开 | 另存 | 树/对象 | 截图项 |
|---|---|---|---|---|---|---|
| phone | CST Phone 5G.cst | 导入 SAB | 条目 ≥ 50 | 往返 | 复杂组件树 | nav_tree, view_3d, components |
| ifa | IFA_design.cst | 参数化 | 条目 ≥ 20 | 往返 | ≥1 solid | nav_tree, view_3d, parameters |
| ship | RCS of a Ship.cst | ModelCache | 条目 ≥ 80 | 往返 | 缓存段 | nav_tree, view_3d, mesh_view |
| sar | SAR Head Hand and Phone.cst | 多 SAB | 条目 ≥ 100 | 往返 | 容器级 | nav_tree, view_3d |
| single_antenna | SingleAntenna.cst | 参数化 | 条目 ≥ 20 | 往返 | ≥1 solid | nav_tree, view_3d |
| dipole_v1 | dipole1_monitors7.cst | 参数化 | 条目 ≥ 20 | 往返 | 监视器 | nav_tree, monitors |
| dipole_v2 | dipole1_monitors7v2.cst | 参数化 | 条目 ≥ 20 | 往返 | 端口 | nav_tree, ports |
| dipole_v3 | dipole1_monitors7v3.cst | 参数化 | 条目 ≥ 20 | 往返 | 端口 | nav_tree, ports |
| patch_v1 | microstrip_patch_antenna.cst | 参数化 | 条目 ≥ 20 | 往返 | 材料 | nav_tree, materials |
| patch_v2 | microstrip_patch_antennav2.cst | 参数化 | 条目 ≥ 20 | 往返 | 监视器 | nav_tree, monitors |
| patch_v3 | microstrip_patch_antennav3.cst | 参数化 | 条目 ≥ 20 | 往返 | 端口 | nav_tree, ports, view_3d |

无样本目录时：合成 New 项目仍跑打开 / 另存 / 树 / Copy View。有样本时 pytest 对 11 个文件做容器往返，并对 IFA / dipole v2 / patch v3 做 GUI 树 + 截图。

## 3. 截图对照清单

人工与 CST Studio 并排时核对这些画面（自动化只保证本工具能抓到非空图）：

| id | 对照内容 |
|---|---|
| nav_tree | 类别与 CST 导航树一致（Components / Materials / Ports / …） |
| view_3d | Shading 下固体可见，无整板误填充（Phone PCB / sh_cans） |
| components | 实体名称与层级（如 Phone/Battery:Cell） |
| materials | 材料名与颜色 |
| ports | 离散端口位置与阻抗 |
| monitors | 场 / 远场监视器条目 |
| parameters | 参数名与表达式 |
| mesh_view | Mesh View 显示已有三角边，不声称已划分 hex |
| copy_view | Copy View 写入剪贴板 |
| quad_view | Top / Front / Side / 3D |

## 4. 差距表

`function_gap_analysis.md` §3：范围内模块 **100% / 100%**；**模块 6 求解器为 N/A**。网格生成、扫描运行、场计算同样 N/A，不计入目标。

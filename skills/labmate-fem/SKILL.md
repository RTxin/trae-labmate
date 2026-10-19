---
name: labmate-fem
description: 轻量有限元与网格工具链（scikit-fem + gmsh + meshio + pyvista）。当用户需要应力场近似分析、简单构件建模、网格生成/转换、结果可视化时使用。触发：「有限元」「算一下应力分布」「建个模」「网格划分」「FEM」。
---

# LabMate · 有限元工具链

按重量分三档，默认从轻的开始：

| 档位 | 工具 | 适用 | 依赖 |
|---|---|---|---|
| 轻 | **scikit-fem** | 线弹性/热传导等标准问题，几百行脚本内 | `pip install scikit-fem` |
| 中 | **gmsh + meshio + pyvista** | 复杂几何建模、网格格式转换、3D 可视化 | `pip install gmsh meshio pyvista` |
| 重 | FEniCSx / CalculiX | 用户本地已有或明确要求时 | 指引用户自行安装 |

## 轻 量 路线（scikit-fem，默认）

```python
# 例：矩形板平面应力（教学级示例：快速验证量级）
from skfem import MeshTri, Basis, LinearElasticity, asm
from skfem.models.elasticity import linear_elasticity, lame_parameters
import numpy as np

mesh = MeshTri().refined(4)                      # 网格细分
basis = Basis(mesh, LinearElasticity(mesh))      # 线弹性
K = asm(linear_elasticity(LM, MU), basis)        # 总刚
# 边界条件与载荷向量按问题定义……
```

**适用边界（要诚实）**：scikit-fem 适合线性、小规模、标准单元的问题。用户问的是复杂接触/非线性/大变形 → 明确说"这超出本工具链，建议 ABAQUS/ANSYS"，不要硬做。

## 中 量 路线（几何建模 → 网格 → 可视化）

```python
# gmsh：脚本化建模（支持 STEP/IGES 导入）
import gmsh
gmsh.initialize()
gmsh.open("part.step")            # 导入 CAD
gmsh.model.mesh.generate(3)       # 3D 网格
gmsh.write("part.msh")

# meshio：格式互转（abaqus/ansys/vtk/nastran...）
import meshio
m = meshio.read("part.msh")
meshio.write("part.inp", m)       # 转 Abaqus 输入文件

# pyvista：3D 可视化与切片分析
import pyvista as pv
grid = pv.read("result.vtu")
grid.plot(scalars="von_mises", cmap="coolwarm")
slices = grid.slice_along_axis(n=8)   # 应力切片
```

**pyvista 单独也很有用**：用户给来 .vtu/.vtk/.inp 结果文件（从商业软件导出），pyvista 直接读、切片、出论文图——**不用装任何商业软件**。

## 与 consult/handcalc 的配合

FEM 结果**永远先跟量级校核对一遍**（handcalc 手算 vs FEM，差超过 30% 必有哪里错了）——这是给专家用户建立信任的关键动作。

## 规则

- 单元类型、边界条件、网格数量的假设全部显式声明
- 应力集中区提醒加密网格、给网格收敛性建议
- 明确这是"近似量级分析"还是"发表级仿真"——前者可以快，后者要走校核流程

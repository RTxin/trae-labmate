---
name: labmate-handcalc
description: 教科书式手算排版工具（基于 handcalcs）。当用户需要"可以逐步校核的计算过程"、安全系数/应力校核、或明确表达"我要看过程"时使用。把每个计算排成公式→代入→结果三段式，让领域专家能逐行校核。触发：「给我算一下」「校核」「要过程」「安全系数」。
---

# LabMate · 手算排版（handcalcs）

领域专家不信任黑箱数字。本模块用 [handcalcs](https://github.com/connorferster/handcalcs) 把计算排成教科书式推导，每一步可校核——**透明产生信任**。

依赖：`pip install handcalcs`

## 使用模式

### 1. 标准校核（在 Jupyter cell 或脚本中）

```python
import handcalcs.render as render  # 在 notebook 中: %%render
from math import pi
from pint import UnitRegistry
ureg = UnitRegistry()

# 剪应力校核：设备能力 vs 材料强度（教学示例，数字为虚构）
F = 150e3      # N，试验机最大载荷
b = 0.10       # m，剪切面长度
h_s = 0.025    # m，剪切面高度
tau_u = 90e6   # Pa，脆性材料抗剪强度估计（下限）

A_s = b * h_s
tau = F / A_s
SF = tau_u / tau   # 强度富余
F_req = tau_u * A_s / 1e3
```

用 `%%render` 渲染时输出为：公式 → 数值代入 → 结果，三行一组。

### 2. 纯脚本环境降级

没有 Jupyter 时，按"三段式"手写输出（一样的效果）：

```
剪切面积   A_s = b × h_s = 0.10 m × 0.025 m = 2.5×10⁻³ m²
设备剪应力  τ  = F / A_s = 150 kN / 0.0025 m² = 60.0 MPa
所需吨位   F_req = τ_u × A_s = 90 MPa × 0.0025 m² = 225 kN（超过试验机满载 150 kN）
→ 结论：满载下材料富余系数仅 1.5，吨位不够破坏该试样；建议剪切面积减至 ≤ 1.7×10⁻³ m² 或换设备
```

### 3. 何时必须走本模块

- 安全系数、设备能力校核、破坏载荷预估——**必走**
- 试验咨询协议（labmate-consult）第 3 步的量级校核——**必走**
- 快速估算且用户赶时间——可省，但结论附一行"详细过程可展开"

## 规则

- 每个符号首次出现时给一句注释（变量名、单位、来源是"给定"还是"假设"）
- 假设值与实测值分开标注：`# 假设：τ_u = 90 MPa（文献下限）`
- 最终结论给敏感性：哪个参数一变结论就翻

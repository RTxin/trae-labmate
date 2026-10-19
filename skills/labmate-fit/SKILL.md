---
name: labmate-fit
description: 数据拟合与参数反演工具（基于 lmfit）。当用户给出试验数据要拟合本构模型、回归材料参数（c-φ、E、蠕变参数）、曲线拟合、参数不确定性估计时使用。触发：「拟合」「回归」「反演参数」「帮我求 c 和 φ」「这条曲线用什么模型」。
---

# LabMate · 数据拟合（lmfit）

依赖：`pip install lmfit`（自带 numpy/scipy 依赖）

[lmfit](https://lmfit.github.io/lmfit-py/) 相比 scipy.optimize 的优势：**命名参数 + 物理边界约束 + 完整的不确定性报告**——科研拟合要的三样都有。

## 常用模型速查（力学场景）

| 场景 | 模型 | 表达式 |
|---|---|---|
| Mohr-Coulomb 回归 | 线性 | τ = c + σn·tanφ（对多组 σn-τ 数据线性回归求 c、φ） |
| 完整应力-应变 | 双曲线（Duncan-Chang） | σ = ε / (a + b·ε) |
| 蠕变 | 幂律 | ε(t) = A·tⁿ 或三元件模型 |
| 疲劳 S-N | Basquin | N = C·S⁻k |
| 应变硬化 | Hollomon | σ = K·εⁿ |
| 峰值后软化 | 应变软化组合模型 | 按用户描述选，找不到现成就自定义 |

## 标准流程

```python
import numpy as np
from lmfit import Model, Parameters

# 例：Mohr-Coulomb 参数回归（多组法向应力-峰值剪应力数据）
sigma_n = np.array([1.0, 2.0, 4.0, 6.0])   # MPa
tau     = np.array([3.2, 5.1, 9.8, 13.1])  # MPa

def mohr_coulomb(s, c, tan_phi):
    return c + s * tan_phi

model = Model(mohr_coulomb, independent_vars=['s'])
params = model.make_params(c=1.0, tan_phi=0.5)
params['tan_phi'].set(min=0, max=1.5)       # 物理边界：摩擦角 0~56°
params['c'].set(min=0)                       # 粘聚力不为负
result = model.fit(tau, params, s=sigma_n)
print(result.fit_report())                   # c、tanφ、标准差、相关系数全都有
```

## 输出规范

给用户的拟合结果必须包含：
1. **参数值 + 不确定性**（标准差/置信区间）——"φ = 32.5° ± 1.8°"而不是"φ = 32.5°"
2. **拟合优度**（R²、残差分布）
3. **拟合图**（数据点 + 拟合曲线 + 残差图，走 labmate-plot 出图）
4. **模型适用性判断**：残差有没有系统性偏移？数据点够不够支撑几个参数？（n 个数据点别拟合 n+1 个参数，要明说）

## 反模式（对领域专家特别重要）

- 不做物理边界约束就拟合（出来负粘聚力、摩擦角 89°）→ 必须给 `min/max`
- 不报告不确定性 → 必须给
- 数据点少于参数时硬拟合 → 拒绝，改为"给参数范围估计 + 建议补几组什么工况的数据"

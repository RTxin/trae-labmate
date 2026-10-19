---
name: labmate-units
description: 单位与量纲换算工具（基于 pint）。当用户需要单位换算（MPa↔psi、kN↔kgf、吨↔磅）、量纲一致性检查、或任何计算前需要确认单位时使用。触发：「换算单位」「量纲检查」「这个单位是多少」。
---

# LabMate · 单位与量纲（pint）

科研计算的事故一半出在单位上。本模块用 [pint](https://github.com/hgrecco/pint) 保证每次换算带量纲。

依赖：`pip install pint`

## 使用模式

### 1. 精确换算（必须走 pint，禁止心算）

```python
from pint import UnitRegistry
ureg = UnitRegistry()

F = (100 * ureg.kN).to(ureg.N)              # 100000 N
A = (4 * ureg.cm * 10 * ureg.cm).to(ureg.m**2)
tau = (F / A).to(ureg.MPa)                  # 剪应力，带量纲除法
print(f"tau = {tau:.2f}")                   # 2.50 MPa
```

### 2. 量纲自检（复杂推导前后必做）

把公式里的每个量都带量纲代入，pint 会在量纲不匹配时直接报错——这是最可靠的防错。

```python
# 量纲检查：弹性模量公式 E = σ/ε
sigma = 5 * ureg.MPa
strain = 0.002 * ureg.dimensionless
E = (sigma / strain).to(ureg.GPa)           # 量纲对，得到 2.5 GPa
```

### 3. 常用对照速查（供回复引用）

| 力 | 应力/压强 |
|---|---|
| 1 kN ≈ 101.97 kgf ≈ 224.81 lbf | 1 MPa = 10 bar ≈ 145.04 psi |
| 1 t（吨力）= 9.80665 kN | 1 GPa = 1000 MPa；1 kgf/mm² = 9.80665 MPa |

## 规则

- 涉及安全、设备吨位的换算，用 pint 算完后在结论里**复述换算链**（100 kN → 100000 N → ÷0.04 m² → 2.5 MPa）
- 用户数据没给单位时，追问单位优先于假设单位；实在要假设就显式声明"假设为 XX 单位"
- 遇到非常见单位（kgf、tf、kips、inHg…）直接交给 pint 处理，不要手换

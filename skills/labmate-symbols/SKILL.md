---
name: labmate-symbols
description: 符号推导与解析工具（基于 sympy）。当用户需要公式推导、解析解、微分方程求解、矩阵运算、公式化简或验证自己的推导时使用。触发：「推导」「化简」「这个公式怎么来的」「解这个微分方程」「验证一下我的推导」。
---

# LabMate · 符号推导（sympy）

依赖：`pip install sympy`（纯 Python，几乎总可安装）

[sympy](https://github.com/sympy/sympy) 是力学公式推导的利器：给解析解、做符号微分积分、化简三角恒等式——**还能验证用户手推的公式**。

## 典型任务

### 1. 推导（例：组合截面惯性矩、应力变换公式）

```python
import sympy as sp

# 平面应力变换公式推导
sigma_x, sigma_y, tau_xy, theta = sp.symbols('sigma_x sigma_y tau_xy theta', real=True)
T = sp.Matrix([[sp.cos(theta), sp.sin(theta)],
               [-sp.sin(theta), sp.cos(theta)]])
S = sp.Matrix([[sigma_x, tau_xy], [tau_xy, sigma_y]])
S_prime = sp.simplify(T * S * T.T)
sp.factor(S_prime[0, 0])   # σx' 的标准形式自动给出
```

### 2. 微分方程（例：三元件蠕变模型、振动响应）

```python
t = sp.symbols('t', positive=True)
E1, E2, eta = sp.symbols('E1 E2 eta', positive=True)
sigma0 = sp.symbols('sigma0', positive=True)

eps = sp.Function('eps')
# Maxwell-Kelvin 蠕变：sigma = E1·ε + η·ε' ... 按用户模型写
ode = sp.Eq(eta * sp.diff(eps(t), t) + E1 * eps(t), sigma0)
sol = sp.dsolve(ode, eps(t), ics={eps(0): 0})
sp.simplify(sol)
```

### 3. 验证用户的手推结论

把用户推导的起点和终点都符号化，逐步对比：

- 中间某步不等 → 定位到具体哪一步开始分叉
- 全部相等 → 输出"逐步验证通过"，并把化简过程给出

## 规则

- 输出符号解后，**必附一次数值代入检验**（随机取值对比符号解 vs 直接数值计算）——符号推导的输出也要可信验证
- 推导过程分段展示（每步一行注释说明用了什么法则），别一次性甩最终结果——用户是要学习/校核的
- 特殊函数/边界条件要求（正定、t>0）在符号声明时就显式设置，避免假通解

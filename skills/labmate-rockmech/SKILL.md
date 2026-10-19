---
name: labmate-rockmech
description: 岩石力学专项模块（领域模块示例）。Mohr-Coulomb 强度准则、Mohr 圆绘制、Hoek-Brown 准则、岩体分类（RMR/Q）。当用户涉及岩石强度参数、岩体质量评价、节理抗剪、结构面分析时使用。触发：「c 和 φ」「莫尔圆」「Hoek-Brown」「RMR」「岩体分类」「结构面」。
---

# LabMate · 岩石力学专项

> 这是 LabMate 的第一个**领域模块**——证明架构可按方向扩展。断裂力学、振动、流体等模块照 `TEMPLATE-SKILL.md` 添加即可。

依赖：`pip install numpy matplotlib`（通用）；RMR 可选装 `minelab`

## 1. Mohr-Coulomb 强度准则

```python
import numpy as np

def mc_shear_strength(sigma_n, c, phi_deg):
    """抗剪强度 τ = c + σn·tanφ"""
    return c + sigma_n * np.tan(np.radians(phi_deg))

# 多组试验数据回归 c、φ → 走 labmate-fit 的线性回归模板
```

## 2. Mohr 圆绘制（三轴/直剪数据）

```python
import numpy as np, matplotlib.pyplot as plt

def mohr_circles(stress_pairs, c=0, phi_deg=0, savefig=None):
    """stress_pairs: [(s1, s3), ...] 主应力对"""
    fig, ax = plt.subplots(figsize=(4, 3.2))
    th = np.linspace(0, np.pi, 200)
    for s1, s3 in stress_pairs:
        sc, r = (s1 + s3) / 2, (s1 - s3) / 2
        ax.plot(sc + r * np.cos(th), r * np.sin(th), 'k-', lw=0.8)
    if phi_deg:  # Mohr-Coulomb 包络线
        x = np.linspace(0, max(s1 for s1, _ in stress_pairs), 100)
        ax.plot(x, c + x * np.tan(np.radians(phi_deg)), 'r--', lw=1.0)
    ax.set_xlabel(r'$\sigma$ / MPa'); ax.set_ylabel(r'$\tau$ / MPa')
    ax.set_aspect('equal'); fig.tight_layout()
    if savefig: fig.savefig(savefig, dpi=600)
    return fig
```

## 3. Hoek-Brown 准则（岩体）

```python
def hoek_brown_sigma1(sigma3, sci, mb, s, a):
    """广义 Hoek-Brown：σ1 = σ3 + sci·(mb·σ3/sci + s)^a"""
    return sigma3 + sci * (mb * sigma3 / sci + s) ** a

# 参数来自 GSI：m_b = m_i·exp((GSI-100)/(28-14D))，s、a 同理由 GSI 与 D 推
# 用户给出 GSI、m_i、扰动因子 D 时按上式换算，缺 GSI 先追问岩体条件
```

## 4. RMR 分类（Bieniawski 1989）

五参数打分（UCS、RQD、节理间距、节理条件、地下水），结构面修正。可用 `minelab` 库，或直接按参数表给分——**打分依据逐项展示**（这是可校核的，不是黑箱打分）。

## 规则

- 强度参数必附条件：完整岩石（实验室）vs 岩体（工程尺度）差别巨大，用户没说清就先区分
- 结构面（节理）抗剪参数（JRC/JCS，Barton 准则）与岩石本体参数区分对待
- 出图走 labmate-plot 期刊模板；回归走 labmate-fit 带物理边界

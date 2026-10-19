---
name: labmate-plot
description: 论文级图表工具（matplotlib 期刊风格模板）。当用户需要发表可用的图表、试验曲线绘制、应力-应变全曲线、等高线图、双轴图，或抱怨"图不像论文里的"时使用。触发：「画图」「出图」「论文插图」「曲线图」「这张图能用于论文吗」。
---

# LabMate · 论文级图表

依赖：`pip install matplotlib`（中文字体：Windows 用 SimSun/SimHei，macOS 用 Songti/Heiti）

## 第〇步：期刊样式从 labmate_style 取（不要手写/凭记忆给 rcParams）

出图前先调 MCP 工具 `labmate_style(style=...)`，四种期刊样式（science/ieee/nature/cnjournal，SciencePlots 逆向，零依赖）：

- 用户没指定期刊 → 默认 `science`；IEEE 系 → `ieee`；Nature 系 → `nature`；中文学报/学位论文 → `cnjournal`
- 工具返回完整 rcParams 键值：让 AI 原样写入 `mpl.rcParams.update({...})`，或传 `save_mplstyle` 写文件后 `plt.style.use()`
- 用户给了目标期刊投稿指南 → 以指南为准，工具样式为基线微调（单双栏宽、字号），并说明改了哪几项

## 期刊风格模板（science 默认，参数以 labmate_style 返回为准）

```python
import matplotlib.pyplot as plt
import matplotlib as mpl

# 下面这组参数由 labmate_style(style="science") 返回后原样填入
mpl.rcParams.update({
    'font.family': 'serif', 'font.size': 8,
    'axes.linewidth': 0.8, 'xtick.direction': 'in', 'ytick.direction': 'in',
    'axes.labelsize': 9, 'legend.fontsize': 7.5,
    'figure.dpi': 300, 'savefig.dpi': 600, 'savefig.bbox': 'tight',
})

fig, ax = plt.subplots(figsize=(3.35, 2.6))   # 单栏图 8.5cm
ax.plot(disp, load, color='#1a1a1a', lw=1.2, label='试验')
ax.plot(disp, fitted, '--', color='#c0392b', lw=1.0, label='拟合')
ax.set_xlabel('Displacement / mm')
ax.set_ylabel('Load / kN')
ax.legend(frameon=False)
fig.savefig('fig1.pdf')   # 矢量 PDF，期刊首选；中文期刊同样适用
```

## 力学图表常用规范

| 图型 | 要点 |
|---|---|
| 应力-应变全曲线（多试样） | 每条线标注试样编号；峰值点可加记号 |
| 双轴图（AE 计数 + 应力-时间） | `ax2 = ax.twinx()`，两轴颜色与曲线对应 |
| Mohr 圆 + 包络线 | 半圆用参数方程 `σc + r·cosθ`，包络线标 c、φ 值 |
| 等值线（应力场/DIC 场） | `contourf` + `colorbar`，色标给单位 |
| 灰度可打印 | 期刊常要求灰度可辨：用线型区分（实/虚/点划），别只靠颜色 |

## 规则

- **先问目标期刊/学位论文的格式要求**（单栏双栏、字体、PDF/TIFF），没有要求就默认上述单栏 PDF
- 坐标轴带单位（`Displacement / mm` 的物理量斜杠格式是国际惯例；中文期刊用 `位移/mm`）
- 中文标签出现乱码方块时：`mpl.rcParams['font.sans-serif'] = ['SimHei']` + `mpl.rcParams['axes.unicode_minus'] = False`
- 出图后必须让用户看一眼（贴出 png 预览），坐标范围/刻度密度经常要微调——迭代一轮很正常

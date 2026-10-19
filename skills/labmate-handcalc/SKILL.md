---
name: labmate-handcalc
description: 教科书式手算排版。当用户需要"可以逐步校核的计算过程"、安全系数/应力校核、LaTeX 推导稿，或明确表达"我要看过程"时使用。优先调用 MCP 工具 labmate_handcalc（公式→代入→结果三段式，AST 安全求值，支持 fmt=latex 直接贴 Overleaf）。触发：「给我算一下」「校核」「要过程」「安全系数」「LaTeX 推导」。
---

# LabMate · 手算排版

领域专家不信任黑箱数字。把计算排成教科书式推导，每一步可校核——**透明产生信任**。

## 第〇步：优先调用 labmate_handcalc（不要现场写脚本）

MCP 工具 `labmate_handcalc` 零依赖、内置 AST 白名单（只放行算术，拒绝函数调用与名字注入）：

```json
{
  "vars": {"F": 150e3, "b": 0.10, "h_s": 0.025, "tau_u": 90e6},
  "steps": [
    {"symbol": "A_s", "formula": "b * h_s", "unit": "m^2", "note": "剪切面面积"},
    {"symbol": "tau", "formula": "F / A_s", "unit": "Pa", "note": "设备满载剪应力"},
    {"symbol": "F_req", "formula": "tau_u * A_s / 1e3", "unit": "kN", "note": "破坏所需载荷"}
  ]
}
```

输出：公式 → 代入 → 结果，三行一组；后面的 step 可以直接引用前面算出来的符号。

### LaTeX 输出（可贴 Overleaf）

加 `"fmt": "latex"`，返回 `align*` 环境：变量名自动转数学符号（`tau_u` → \tau_{u}，`A_s` → A_{s}），除法自动变 `\frac{}{}`，幂自动变上标，科学计数法变 `2.5\times10^{-3}`。适合写论文方法节、给学生发推导稿。

注意：LaTeX 模式的 note 按数学模式旁注处理，**单位用英文符号（m^2、Pa）；中文单位场景用默认 md 格式**。

## 备选：notebook 环境的 handcalcs 包

用户在 Jupyter 里且已装 handcalcs/pint 时，可用 `%%render` 单元格获得交互渲染：

依赖：`pip install handcalcs pint`

```python
import handcalcs.render as render  # notebook 中: %%render
F = 150e3      # N，试验机最大载荷
b = 0.10       # m，剪切面长度
h_s = 0.025    # m，剪切面高度
tau_u = 90e6   # Pa，脆性材料抗剪强度估计（下限）
A_s = b * h_s
tau = F / A_s
F_req = tau_u * A_s / 1e3
```

## 何时必须走本模块

- 安全系数、设备能力校核、破坏载荷预估——**必走**
- 试验咨询协议（labmate-consult）第 3 步的量级校核——**必走**
- 用户要把推导写进论文/报告——**必走，且用 fmt=latex**
- 快速估算且用户赶时间——可省，但结论附一行"详细过程可展开"

## 规则

- 每个符号首次出现时给一句注释（变量名、单位、来源是"给定"还是"假设"）
- 假设值与实测值分开标注：`note: 假设，τ_u = 90 MPa（文献下限）`
- 最终结论给敏感性：哪个参数一变结论就翻（如"面积只要减到 1.7×10⁻³ m² 以下结论就反转"）

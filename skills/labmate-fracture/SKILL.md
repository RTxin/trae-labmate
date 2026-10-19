---
name: labmate-fracture
description: 断裂力学与疲劳裂纹扩展专项。当用户提到应力强度因子 KI/KIC、断裂韧性、临界裂纹尺寸、裂纹扩展寿命、Paris 定律、CT/SENB 试样、脆断评估、E399 有效性时使用。计算优先走 labmate_handcalc（K 与临界裂纹尺寸三段式）与 labmate_fit_lite（Paris 参数 power 拟合）。触发：「会不会断」「裂纹还能扩展多久」「KIC 校核」「疲劳寿命」「临界裂纹」「断裂韧性试验」。
---

# LabMate · 断裂力学（labmate-fracture）

覆盖线弹性断裂力学（LEFM）的工程评估：应力强度因子 → 断裂判据 → 临界裂纹尺寸 → 疲劳扩展寿命。复杂构件/弹塑性/残余应力场景明确划出边界。

## 核心任务与标准做法

| 任务 | 方法/工具 | 要点 |
|---|---|---|
| 应力强度因子 K_I | `labmate_handcalc` 三段式 | 必带**几何因子 Y**；无限大板中心裂纹 K=σ√(πa)，边裂纹 K=1.12σ√(πa) |
| 断裂判据 | handcalc | K_I ≥ K_IC 即失稳；给安全系数 K_IC/K_I |
| 临界裂纹尺寸 | handcalc | a_c = (1/π)(K_IC/(Y·σ))²；反算临界应力同理 |
| Paris 参数 C、m | `labmate_fit_lite` model=power | da/dN = C(ΔK)^m，对 (ΔK, da/dN) 数据做幂律拟合，log-log 斜率即 m |
| 剩余寿命积分 | 一次性脚本（解析积分） | N = ∫da/[C(ΔK(a))^m]；m≠2 与 m=2 闭式不同，脚本里分情况 |
| K_IC 试验有效性 | handcalc | ASTM E399：B ≥ 2.5(K_IC/σ_y)² 且 a ≥ 同值，否则结果只能叫 K_Q |
| S-N 曲线拟合与寿命预测 | `labmate_stats` action=sn | Basquin σᵃ·N=C 双对数回归出指数 a/系数 C；`target_stress` 给定应力预测寿命；runout（未断试样）不能混入，低周（<10³）走 Coffin-Manson 应变法 |
| 塑性区/小范围屈服 | handcalc | r_p ≈ (1/2π)(K/σ_y)²（平面应力）；r_p 远小于 a 与韧带时 LEFM 才成立 |

## 代码模板

### 1. K 因子 + 临界裂纹尺寸（直接调 labmate_handcalc，零依赖）

```json
{
  "vars": {"sigma": 200e6, "a": 0.02, "Y": 1.12, "K_IC": 55e6, "sigma_y": 650e6},
  "steps": [
    {"symbol": "K_I", "formula": "Y * sigma * (pi * a) ** 0.5", "unit": "Pa*sqrt(m)",
     "note": "边裂纹无限大板近似，Y=1.12"},
    {"symbol": "SF", "formula": "K_IC / K_I", "note": "断裂安全系数，>1 安全"},
    {"symbol": "a_c", "formula": "(1 / pi) * (K_IC / (Y * sigma)) ** 2", "unit": "m",
     "note": "临界裂纹尺寸"},
    {"symbol": "B_min", "formula": "2.5 * (K_IC / sigma_y) ** 2", "unit": "m",
     "note": "E399 平面应变最小厚度"}
  ]
}
```

### 2. Paris 参数（labmate_fit_lite，幂律）

```python
# dK = 应力强度因子幅 ΔK（MPa√m），dadn = 每循环扩展量 m/cycle
# 直接调 MCP：labmate_fit_lite(x=dK, y=dadn, model="power")
# 返回 dadn = C * dK^m 的 C、m 与 R²；R² 低通常是跨过门槛区/瞬断区，先筛中段数据
```

寿命积分（handcalc 覆盖不了，写一次性脚本，m≠2 的闭式）：

```python
import math
# ΔK(a) = Y·Δσ·√(πa)，N = [a0^(1-m/2) - af^(1-m/2)] / [C·(Y·Δσ·√π)^m·(m/2-1)]，m≠2
def paris_life(C, m, Y, dsigma, a0, af):
    A = C * (Y * dsigma * math.pi ** 0.5) ** m
    return (a0 ** (1 - m / 2) - af ** (1 - m / 2)) / (A * (m / 2 - 1))
```

## 本领域的专业常识（模块的灵魂）

1. **K_IC 是有条件的材料常数**：厚度不够测的是平面应力 K_C 不是 K_IC；温度、加载速率、腐蚀环境都会改变它——回答前先确认材料状态（供货态/温度/厚度/R 比），不要拿一个 K_IC 数字包打所有工况
2. **几何因子 Y 最容易被漏掉**：用户口述"按 σ√(πa) 算"时，先问裂纹位置（中心/边裂/孔边/表面半椭圆）与构件几何，Y 从 1.0 到 2.x 都可能，漏了直接错一倍
3. **量级感**：高强钢 K_IC 约 30-80 MPa√m，中低强钢 100-300，铝合金 20-45，陶瓷 1-5；塑性区尺寸比裂纹和韧带小一个量级以上 LEFM 才有效，否则要走弹塑性（CTOD/J 积分）
4. **Paris 不是普适公式**：C、m 绑定应力比 R 与环境（空气/腐蚀介质差几个量级）；存在门槛 ΔK_th（近门槛扩展趋近零）和瞬断区（K_max→K_IC），中段双对数线性区才适用
5. **红线**：检测能力决定 a_0——用无损检测（UT/MT）检不出的裂纹尺寸当起始值，评估就是假的；应力腐蚀场景必须查 K_ISCC 门槛；出"安全/不安全"结论时标注依据标准（API 579、BS 7910、GB/T 19624），本模块给力学量，不替代合规评定

## 与其他模块的配合

- 计算过程排版/LaTeX 推导 → `labmate-handcalc`（fmt=latex 贴论文）
- 疲劳曲线拟合 → `labmate_fit_lite`；复杂本构拟合带不确定度 → `labmate-fit`（lmfit）
- da/dN 数据先体检 → `labmate-data` 第〇步 `labmate_table`
- 三维裂纹/残余应力/焊接结构 → `labmate-fem`（线弹性结论不可用时）
- 投稿前的判据表述与 AI 披露 → `labmate-disclosure`
- 通用约束 → 主 skill `labmate` 的工作流原则

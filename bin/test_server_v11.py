# -*- coding: utf-8 -*-
"""LabMate server 0.4.7 新增能力单测：多元线性回归（fit_lite model=multi，OLS + 系数 t 检验 + 调整 R² + 整体 F）。"""
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import labmate_server as srv  # noqa: E402

passed, failed = 0, 0
def ok(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print("  PASS  " + name)
    else:
        failed += 1
        print("  FAIL  %s  %s" % (name, str(detail)[:200]))

# ======================================================================
print("== 45. multi · 黄金用例（y = 2 + 3·x1 − 0.5·x2 零噪声精确还原）==")
G_X1 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
G_X2 = [3.0, 1.0, 4.0, 1.0, 5.0, 9.0]
G_Y = [2 + 3 * a - 0.5 * b for a, b in zip(G_X1, G_X2)]
r = srv.tool_fit({"model": "multi", "x": [G_X1, G_X2], "y": G_Y})
ok("标题行（OLS，n = 6，p = 2）",
   "**多元线性回归（OLS，n = 6 个样本，p = 2 个自变量，含截距）**" in r, r[:200])
ok("回归方程精确还原：y = 2 + 3·x1 - 0.5·x2",
   "回归方程：y = 2 + 3·x1 - 0.5·x2" in r, r[:300])
ok("b0 = 2 精确还原", "截距 b0 = 2" in r, r[:400])
ok("b1 = 3 精确还原（含 t 与显著标注）", "b1（x1） = 3（" in r and "显著" in r, r[:400])
ok("b2 = -0.5 精确还原（负号进方程）", "b2（x2） = -0.5（" in r, r[:400])
ok("R² = 1 精确", "R² = 1，调整 R² = 1（惩罚多余自变量）" in r, r[:500])
ok("t 检验声明自由度 df = n - p - 1 = 3", "H0: βi = 0，df = 3" in r, r[:400])
ok("样本量建议提示（n=6 < 5p=10）", "⚠ 样本量偏少（n = 6 < 5p = 10）" in r, r[-300:])
ok("共线警示尾注", "共线）会使系数不稳定" in r, r[-200:])

# ======================================================================
print("== 46. multi · 确定性噪声鲁棒性（固定扰动 ±0.05，精确断言）==")
EPS = [0.05, -0.04, 0.03, -0.02, 0.06, -0.03]
YN = [v + e for v, e in zip(G_Y, EPS)]
r2 = srv.tool_fit({"model": "multi", "x": [G_X1, G_X2], "y": YN})
ok("b0 ≈ 2.02371（t = 41.0551，p ≈ 3.1801e-05）",
   "截距 b0 = 2.02371（t = 41.0551，p ≈ 3.1801e-05，显著）" in r2, r2[:400])
ok("b1 ≈ 2.98935（t = 169.566）",
   "b1（x1） = 2.98935（t = 169.566，p ≈ 4.5227e-07，显著）" in r2, r2[:400])
ok("b2 ≈ -0.494291（t = -44.8772）",
   "b2（x2） = -0.494291（t = -44.8772，p ≈ 2.4357e-05，显著）" in r2, r2[:400])
ok("整体 F = 19570.6（df1 = 2，df2 = 3）",
   "整体 F = 19570.6（df1 = 2，df2 = 3，p ≈ 6.7093e-07）" in r2, r2[:500])
ok("R² = 0.999923", "R² = 0.999923" in r2, r2[:500])
ok("调整 R² = 0.999872（= 1 − (1−R²)(n−1)/(n−p−1) 精确验证）",
   "调整 R² = 0.999872（惩罚多余自变量）" in r2, r2[:500])
ok("调整 R² < R²（噪声下惩罚生效）", r2.find("R² = 0.999923") < r2.find("调整 R² = 0.999872"), r2)
ok("残差标准误 s = 0.0529429", "残差标准误 s = 0.0529429" in r2, r2[-300:])

# ======================================================================
print("== 47. multi · 形态兼容与无关变量判定 ==")
rows = [[a, b] for a, b in zip(G_X1, G_X2)]  # 每行一个样本（6 行 × 2 变量）
r3 = srv.tool_fit({"model": "multi", "x": rows, "y": G_Y})
ok("按样本分行自动转置：方程与按列传参一致",
   "回归方程：y = 2 + 3·x1 - 0.5·x2" in r3, r3[:300])
r4 = srv.tool_fit({"model": "multi", "x": G_X1, "y": [2 + 3 * a for a in G_X1]})
ok("一维 x 退化为单自变量 p = 1",
   "**多元线性回归（OLS，n = 6 个样本，p = 1 个自变量，含截距）**" in r4
   and "回归方程：y = 2 + 3·x1" in r4, r4[:300])
# 无关变量：y 只由 x1 决定，x2 应判"不显著"
X2_IRR = [2.0, 3.0, 5.0, 7.0, 11.0, 13.0]
Y_IRR = [2 + 3 * a + e for a, e in zip(G_X1, EPS)]
r5 = srv.tool_fit({"model": "multi", "x": [G_X1, X2_IRR], "y": Y_IRR})
ok("无关变量系数不显著（p = 0.342245 ≥ 0.05）",
   "b2（x2） = 0.0296012（t = 1.12563，p ≈ 0.342245，不显著）" in r5, r5[:500])
ok("有效变量仍显著（b1 p ≈ 2.0780e-05）", "p ≈ 2.0780e-05，显著" in r5, r5[:500])

# ======================================================================
print("== 48. multi · 边界与行为 ==")
ok("共线奇异拦截（x2 = 2·x1）",
   "❌ 奇异：自变量共线（如 x2 = 2·x1）或退化（无波动），无法求解"
   == srv.tool_fit({"model": "multi", "x": [G_X1, [2 * v for v in G_X1]], "y": G_Y}), "")
ok("样本量不足拦截（n = 3 < p + 2 = 4）",
   "❌ 样本量不足：n = 3，识别到 p = 2 个自变量；至少需要 p + 2 = 4 个样本"
   "（保证残差自由度 ≥ 1），建议 n ≥ 5p"
   == srv.tool_fit({"model": "multi", "x": [[1.0, 2.0, 3.0], [3.0, 1.0, 4.0]], "y": [1.0, 2.0, 3.1]}), "")
ok("形态无法对齐拦截",
   "❌ x 形态无法对齐 y（n = 3）：期望 x = [x1数组, x2数组, ...]（每个自变量与 y 等长），"
   "或每行一个样本（行数 = n 且各行等长，自动转置）"
   == srv.tool_fit({"model": "multi", "x": [[1.0, 2.0], [3.0, 1.0]], "y": [1.0, 2.0, 3.0]}), "")
ok("缺 y 拦截", "❌ multi 需要 x（自变量）与 y（因变量数组）"
   == srv.tool_fit({"model": "multi", "x": [1, 2], "y": []}), "")
ok("缺 x 拦截", "❌ multi 需要 x（自变量）与 y（因变量数组）"
   == srv.tool_fit({"model": "multi", "y": [1, 2, 3]}), "")
ok("x 含非数值元素拦截", "❌ x 含非数值元素"
   == srv.tool_fit({"model": "multi", "x": [[1, 2, "a"], [1, 2, 3]], "y": [1, 2, 3]}), "")
ok("y 含非数值元素拦截", "❌ y 含非数值元素"
   == srv.tool_fit({"model": "multi", "x": [[1, 2, 3], [4, 5, 6]], "y": [1, "b", 3]}), "")
r6 = srv.tool_fit({"model": "multi", "x": [G_X1, G_X2], "y": [5.0] * 6})
ok("y 无波动：R² 无定义 + 完美拟合分支（s = 0 不做 t 检验）",
   "R² 无定义（y 无波动）" in r6 and "残差为 0：数据完美落在模型上，t 检验无意义" in r6, r6)
ok("未知模型文案含 multi",
   "❌ 未知模型 xxx：支持 linear/poly、power、exp、multi（多元线性回归）"
   == srv.tool_fit({"model": "xxx", "x": [1, 2, 3], "y": [1, 2, 3]}), "")
ok("linear 老路径不受影响",
   "linear" in srv.tool_fit({"model": "linear", "x": [1, 2, 3, 4], "y": [2, 4, 6, 8]})
   and "R² = 1" in srv.tool_fit({"model": "linear", "x": [1, 2, 3, 4], "y": [2, 4, 6, 8]}), "")
ok("power 老路径不受影响",
   "幂律" in srv.tool_fit({"model": "power", "x": [1, 2, 4], "y": [3, 12, 48]}) or
   "x^" in srv.tool_fit({"model": "power", "x": [1, 2, 4], "y": [3, 12, 48]}), "")
ok("polyfit 重构后签名与行为不变（y = 2x + 2 → [截距, 斜率] = [2, 2]）",
   srv._polyfit([1.0, 2.0, 3.0], [4.0, 6.0, 8.0], 1) == [2.0, 2.0], "")
ok("polyfit 奇异返回 None（全同 x）",
   srv._polyfit([5.0, 5.0, 5.0], [1.0, 2.0, 3.0], 1) is None, "")
ok("gauss_solve 多右端列同解（A = [[2,1],[1,3]]，一次解出 A⁻¹ 两列）",
   (lambda ic: abs(ic[0][0] - 0.6) < 1e-12 and abs(ic[0][1] + 0.2) < 1e-12 and
               abs(ic[1][0] + 0.2) < 1e-12 and abs(ic[1][1] - 0.4) < 1e-12)
   (srv._gauss_solve([[2.0, 1.0, 1.0, 0.0], [1.0, 3.0, 0.0, 1.0]], 2, 4)), "")

# ======================================================================
print("== 49. 协议层与文档注册 ==")
ok("TOOLS 为 20 件（0.4.8 增 docx）", len(srv.TOOLS) == 20, len(srv.TOOLS))
sig = [t for t in srv.TOOLS if t["name"] == "labmate_fit_lite"][0]
ok("schema：model 枚举含 multi", "multi" in sig["inputSchema"]["properties"]["model"]["description"], "")
ok("schema：描述含多元线性回归", "多元线性回归" in sig["description"], sig["description"][:200])
ok("schema：描述含调整 R² 与整体 F", "调整 R²" in sig["description"] and "整体 F" in sig["description"], "")
ok("schema：x 描述说明两种形态", "自动转置" in sig["inputSchema"]["properties"]["x"]["description"], "")
ok("_DISPATCH 含 labmate_fit_lite", callable(srv._DISPATCH.get("labmate_fit_lite")), "")
main_skill = open(os.path.join(HERE, "..", "skills", "labmate", "SKILL.md"), encoding="utf-8").read()
ok("主路由版本行 = 0.4.8", "v0.4.8" in main_skill, "")
ok("主路由工具表含多元回归行", "多元" in main_skill and "multi" in main_skill, "")
fit_skill = os.path.join(HERE, "..", "skills", "labmate-fit", "SKILL.md")
fit_txt = open(fit_skill, encoding="utf-8").read() if os.path.exists(fit_skill) else ""
ok("fit skill 补 multi 调用说明", "multi" in fit_txt, fit_skill)

def rpc(msgs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "labmate_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode("utf-8"))
    return [json.loads(l) for l in out.decode("utf-8").splitlines() if l.strip()]

res = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
           {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "labmate_fit_lite",
                       "arguments": {"model": "multi", "x": [G_X1, G_X2], "y": G_Y}}}])
ok("initialize 版本 = 0.4.8", res[0]["result"]["serverInfo"]["version"] == "0.4.8", res[0])
ok("stdio multi 黄金用例（方程精确还原）",
   "回归方程：y = 2 + 3·x1 - 0.5·x2" in res[1]["result"]["content"][0]["text"],
   res[1]["result"]["content"][0]["text"][:150])

print("\n== v0.4.7 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

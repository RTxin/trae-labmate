# -*- coding: utf-8 -*-
"""LabMate server 0.4.6 新增能力单测：S-N 疲劳拟合（stats action=sn，Basquin 双对数回归）。"""
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
print("== 41. sn · 黄金用例（C=1e12, a=3 精确反解，零噪声应精确还原）==")
G_SIG = [100.0, 150.0, 200.0, 300.0]
G_CYC = [1e12 / s ** 3 for s in G_SIG]  # N = C·σ^(−a) 精确：1e6 / 296296.3 / 1.25e5 / 37037.0
r = srv.tool_stats({"action": "sn", "stress": G_SIG, "cycles": G_CYC,
                    "target_stress": 250.0})
ok("标题行（Basquin，n = 4）", "**S-N 疲劳拟合（Basquin σ^a·N = C，双对数线性回归，n = 4）**" in r, r[:200])
ok("指数 a = 3 精确还原", "疲劳强度指数 a = 3（钢典型" in r, r[:200])
ok("系数 C = 1.0000e+12 精确还原", "疲劳强度系数 C = 1.0000e+12" in r, r[:200])
ok("线性化 R² = 1", "线性化 R² = 1（< 0.9 时慎用外推）" in r, r[:300])
ok("方程回显：N = 1.0000e+12 · σ^(−3)", "方程：N = 1.0000e+12 · σ^(−3)" in r, r[:300])
ok("预测 σ=250 → N=64000 精确（1e12/250³）",
   "预测：σ = 250 → 疲劳寿命 N ≈ 64000 cycles" in r, r[:400])
ok("目标应力在试验范围内：无外推警告", "超出试验范围" not in r, r)
ok("适用域提示（runout 警示）", "runout" in r and "Coffin-Manson" in r, r[-200:])

# ======================================================================
print("== 42. sn · 确定性噪声鲁棒性（a=5, C=1e15，±3% 扰动）==")
N_SIG = [80.0, 100.0, 130.0, 160.0, 200.0, 250.0]
N_FAC = [1.02, 0.98, 1.01, 0.99, 1.03, 0.97]  # 固定扰动因子，测试可复现
N_CYC = [f * 1e15 / s ** 5 for s, f in zip(N_SIG, N_FAC)]
r2 = srv.tool_stats({"action": "sn", "stress": N_SIG, "cycles": N_CYC})
ok("a 还原 5.01477（5 ± 0.5 内）", "疲劳强度指数 a = 5.01477" in r2, r2[:200])
ok("R² > 0.99（0.999886）", "线性化 R² = 0.999886" in r2, r2[:300])
ok("n = 6 计入标题", "n = 6）**" in r2, r2[:200])

# ======================================================================
print("== 43. sn · 边界与行为 ==")
ok("缺 stress 拦截", "❌ sn 需要 stress（疲劳应力数组）与 cycles（对应寿命数组）"
   == srv.tool_stats({"action": "sn", "cycles": [1e5, 1e4, 1e3]}), "")
ok("缺 cycles 拦截", "❌ sn 需要 stress" in srv.tool_stats({"action": "sn", "stress": [100.0, 150.0]}), "")
ok("stress/cycles 不等长拦截",
   "❌ stress 与 cycles 需等长（每级应力对应一个寿命）"
   == srv.tool_stats({"action": "sn", "stress": [100.0, 150.0], "cycles": [1e5]}), "")
ok("n=2 拦截（至少 3 对）",
   "❌ S-N 拟合至少需要 3 对（应力, 寿命）数据"
   == srv.tool_stats({"action": "sn", "stress": [100.0, 150.0], "cycles": [1e6, 1e5]}), "")
ok("应力含 0 拦截（双对数定义域）",
   "❌ Basquin 拟合要求应力、寿命全部为正（双对数定义域）"
   == srv.tool_stats({"action": "sn", "stress": [0.0, 150.0, 200.0], "cycles": [1e5, 1e4, 1e3]}), "")
ok("寿命含负拦截",
   "❌ Basquin 拟合要求应力、寿命全部为正" in
   srv.tool_stats({"action": "sn", "stress": [100.0, 150.0, 200.0], "cycles": [1e5, -1e4, 1e3]}), "")
ok("传反拦截（寿命随应力升而升 → a ≤ 0）",
   "❌ 拟合出 a ≤ 0：S-N 规律不成立（寿命应随应力升高而降低），检查 stress/cycles 是否传反"
   == srv.tool_stats({"action": "sn", "stress": G_SIG, "cycles": [1e4, 2e4, 3e4, 5e4]}), "")
ok("退化拦截（应力全相同）",
   "❌ 数据退化（应力水平无波动），无法拟合"
   == srv.tool_stats({"action": "sn", "stress": [150.0, 150.0, 150.0], "cycles": [1e5, 1e4, 1e3]}), "")
ok("target_stress=0 拦截",
   "❌ target_stress 须为正应力值"
   == srv.tool_stats({"action": "sn", "stress": G_SIG, "cycles": G_CYC, "target_stress": 0}), "")
ok("target_stress 为负拦截",
   "❌ target_stress 须为正应力值"
   == srv.tool_stats({"action": "sn", "stress": G_SIG, "cycles": G_CYC, "target_stress": -5}), "")
r3 = srv.tool_stats({"action": "sn", "stress": G_SIG, "cycles": G_CYC, "target_stress": 500.0})
ok("外推明示（σ=500 超出 [100,300]）",
   "⚠ 目标应力 500 超出试验范围 [100, 300]：外推仅供量级参考" in r3, r3)
ok("未知 action 尾串含 sn",
   "❌ 未知 action：xxx（支持 describe / ttest / anova / normality / ci / power / outlier / weibull / sn）"
   == srv.tool_stats({"action": "xxx"}), "")
ok("weibull 旧路径不受影响（stress 单值语义）",
   "Weibull 强度分析" in srv.tool_stats(
       {"action": "weibull", "data": [200.0, 220.0, 240.0, 260.0, 280.0], "stress": 250.0}), "")

# ======================================================================
print("== 44. 协议层与文档注册 ==")
ok("TOOLS 仍为 19 件", len(srv.TOOLS) == 19, len(srv.TOOLS))
sig = [t for t in srv.TOOLS if t["name"] == "labmate_stats"][0]
ok("schema：action 枚举含 sn", "sn" in sig["inputSchema"]["properties"]["action"]["description"], "")
ok("schema：描述含 S-N 疲劳拟合", "S-N 疲劳拟合" in sig["description"], sig["description"][:200])
ok("schema：新增 cycles 参数",
   "cycles" in sig["inputSchema"]["properties"]
   and "疲劳寿命数组" in sig["inputSchema"]["properties"]["cycles"]["description"], "")
ok("schema：新增 target_stress 参数",
   "target_stress" in sig["inputSchema"]["properties"]
   and "预测疲劳寿命" in sig["inputSchema"]["properties"]["target_stress"]["description"], "")
ok("schema：stress 描述兼顾 weibull/sn 两用",
   "sn：疲劳应力数组" in sig["inputSchema"]["properties"]["stress"]["description"], "")
ok("_DISPATCH 含 labmate_stats", callable(srv._DISPATCH.get("labmate_stats")), "")
main_skill = open(os.path.join(HERE, "..", "skills", "labmate", "SKILL.md"), encoding="utf-8").read()
ok("主路由版本行 = 0.4.6", "v0.4.6" in main_skill, "")
ok("主路由工具表含 S-N 行", "S-N" in main_skill and "action=sn" in main_skill, "")
frac = os.path.join(HERE, "..", "skills", "labmate-fracture", "SKILL.md")
frac_txt = open(frac, encoding="utf-8").read() if os.path.exists(frac) else ""
ok("fracture skill 补 S-N 调用说明", "action=sn" in frac_txt, frac)

def rpc(msgs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "labmate_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode("utf-8"))
    return [json.loads(l) for l in out.decode("utf-8").splitlines() if l.strip()]

res = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
           {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "labmate_stats",
                       "arguments": {"action": "sn", "stress": G_SIG, "cycles": G_CYC}}}])
ok("initialize 版本 = 0.4.6", res[0]["result"]["serverInfo"]["version"] == "0.4.6", res[0])
ok("stdio sn 黄金用例（a = 3）", "疲劳强度指数 a = 3" in res[1]["result"]["content"][0]["text"],
   res[1]["result"]["content"][0]["text"][:150])

print("\n== v0.4.6 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

# -*- coding: utf-8 -*-
"""LabMate server 0.4.4 单测：labmate_stats 新增 outlier（GB/T 4883 异常值两级判定）
+ weibull（中位秩两参数强度分析）。
已知值验证：完美 Weibull 样本（m=8、σ₀=500，由中位秩公式反解生成）回归精确还原
m/σ₀/R²=1；σ=σ₀ 处破坏概率恒 63.2%（特征强度定义自检）；格拉布斯 n=3 双侧临界
与教科书表值 1.153 吻合（柯西解析可手算）；狄克松临界值锚点对表；边界覆盖
n<3、n>30 查表、无波动、歧离值保留、迭代多轮剔除、低端方向、stress 负值。"""
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

def approx(a, b, tol=1e-9):
    return abs(a - b) <= tol

# 完美 Weibull 样本：F_i=(i-0.3)/(n+0.4) 中位秩反解 σ_i=σ₀·(-ln(1-F_i))^(1/m)
# n=10、m=8、σ₀=500 → 回归应精确还原三个参数
W_N, W_M, W_S0 = 10, 8.0, 500.0
WS = [W_S0 * (-math.log(1.0 - (i - 0.3) / (W_N + 0.4))) ** (1.0 / W_M)
      for i in range(1, W_N + 1)]

# ====================== outlier：临界值已知锚点 ======================
print("== 32. outlier 临界值锚点 ==")
ok("格拉布斯 n=3 双侧 0.05 临界 ≈ 1.153（教科书表值，柯西解析）",
   abs(srv._grubbs_crit(3, 0.05) - 1.153) < 0.005, srv._grubbs_crit(3, 0.05))
ok("格拉布斯 n=7 双侧 0.05 临界 ≈ 2.020（教科书表值）",
   abs(srv._grubbs_crit(7, 0.05) - 2.020) < 0.005, srv._grubbs_crit(7, 0.05))
ok("格拉布斯临界随 n 单调增（3 < 10 < 30 < 100）",
   srv._grubbs_crit(3, 0.05) < srv._grubbs_crit(10, 0.05)
   < srv._grubbs_crit(30, 0.05) < srv._grubbs_crit(100, 0.05))
ok("格拉布斯 0.01 临界 > 0.05 临界（同 n=10）",
   srv._grubbs_crit(10, 0.01) > srv._grubbs_crit(10, 0.05),
   (srv._grubbs_crit(10, 0.05), srv._grubbs_crit(10, 0.01)))
ok("狄克松表锚点 n=3/10/14/30（0.05 档）",
   srv._DIXON_TABLE[0.05][3] == 0.941 and srv._DIXON_TABLE[0.05][10] == 0.477
   and srv._DIXON_TABLE[0.05][14] == 0.546 and srv._DIXON_TABLE[0.05][30] == 0.376)
ok("狄克松表锚点 n=3/10/14/30（0.01 档）",
   srv._DIXON_TABLE[0.01][3] == 0.988 and srv._DIXON_TABLE[0.01][10] == 0.597
   and srv._DIXON_TABLE[0.01][14] == 0.674 and srv._DIXON_TABLE[0.01][30] == 0.448)
ok("狄克松表覆盖 n=3..30 完整（两档各 28 项）",
   len(srv._DIXON_TABLE[0.05]) == 28 and len(srv._DIXON_TABLE[0.01]) == 28
   and sorted(srv._DIXON_TABLE[0.05]) == list(range(3, 31)))
ok("狄克松 r10 手算：[0,1,2,3,10] 高端 (10-3)/10 = 0.7",
   approx(srv._dixon_stat([0, 1, 2, 3, 10], True), 0.7),
   srv._dixon_stat([0, 1, 2, 3, 10], True))
ok("狄克松 r10 低端：[0,1,2,3,10] (1-0)/10 = 0.1",
   approx(srv._dixon_stat([0, 1, 2, 3, 10], False), 0.1))
ok("狄克松 r11 分段：[0..6,10] n=8 高端 (10-6)/(10-1) = 4/9",
   approx(srv._dixon_stat([0, 1, 2, 3, 4, 5, 6, 10], True), 4.0 / 9.0),
   srv._dixon_stat([0, 1, 2, 3, 4, 5, 6, 10], True))
ok("狄克松 r22 分段：[0..12,30] n=14 高端 (30-x12)/(30-x3) = 19/28",
   approx(srv._dixon_stat(list(range(13)) + [30], True), 19.0 / 28.0),
   srv._dixon_stat(list(range(13)) + [30], True))
ok("狄克松 n=21 分段 r22：[0..19,50] (50-18)/(50-2) = 2/3",
   approx(srv._dixon_stat(list(range(20)) + [50], True), 32.0 / 48.0))

# ====================== outlier：行为与两级判定 ======================
print("== 33. outlier 行为（歧离值 / 统计离群值）==")
r = srv.tool_stats({"action": "outlier",
                    "data": [9.9, 10, 10.05, 10.1, 10.2, 9.95, 10.15, 9.85, 10.25,
                             9.8, 13, 100]})
ok("格拉布斯迭代剔除两个极端值（先 100 暴露后剔 13）",
   "统计离群值" in r and "已剔除 2 个" in r and "100" in r and "13" in r, r)
ok("标题含准则与样本数变化（n = 12 → 10）", "n = 12 → 10" in r, r)
ok("保留统计行给出新均值标准差", "保留 n = 10" in r and "均值" in r, r)
ok("剔除交代提示（normality 复核 + 报告交代）", "normality" in r and "交代" in r, r)

r = srv.tool_stats({"action": "outlier", "data": [9.9, 10, 10.05, 10.1, 10.2]})
ok("无异常数据：未剔除任何值", "无异常，停止" in r and "未剔除任何值" in r, r)

r = srv.tool_stats({"action": "outlier", "data": [5, 10, 10.1, 10.2, 10.3, 10.4]})
ok("低端异常：判定方向为低端并剔除", "低端值 5" in r and "统计离群值，剔除" in r, r)

r = srv.tool_stats({"action": "outlier", "data": [0, 1, 2, 3, 10], "criterion": "dixon"})
ok("狄克松歧离值：r=0.7 落在 0.642~0.780 之间 → 保留",
   "歧离值，保留" in r and "未剔除任何值" in r and "D = 0.7" in r, r)
r = srv.tool_stats({"action": "outlier", "data": [0, 1, 2, 3, 20], "criterion": "dixon"})
ok("狄克松统计离群值：r=0.85 > 0.78 → 剔除后重检停",
   "统计离群值，剔除" in r and "已剔除 1 个（20）" in r, r)
r = srv.tool_stats({"action": "outlier", "data": [4, 10, 11, 12, 13], "criterion": "dixon"})
ok("狄克松低端方向：低端值 4 为歧离值", "低端值 4" in r and "歧离值" in r, r)
r = srv.tool_stats({"action": "outlier", "data": list(range(13)) + [30], "criterion": "dixon"})
ok("狄克松 n=14 用 r22：D=0.679 > 0.01 临界 0.674 → 统计离群值",
   "统计离群值，剔除" in r and "已剔除 1 个（30）" in r and "n = 14 → 13" in r, r)

r = srv.tool_stats({"action": "outlier", "data": [5, 5, 5, 5, 5]})
ok("无波动数据诚实停止", "无波动" in r, r)
r = srv.tool_stats({"action": "outlier", "data": [1, 2]})
ok("n < 3 拦截", "❌" in r and "n ≥ 3" in r, r)
r = srv.tool_stats({"action": "outlier", "data": ["a", "b", "c"]})
ok("非数值数据拦截", "❌" in r, r)
r = srv.tool_stats({"action": "outlier", "data": [1, 2, 3, 4], "criterion": "xyz"})
ok("未知 criterion 拦截", "❌" in r and "grubbs" in r and "dixon" in r, r)
r = srv.tool_stats({"action": "outlier", "data": [float(i) for i in range(31)],
                    "criterion": "dixon"})
ok("狄克松 n > 30 拦截（国标表范围）", "❌" in r and "n ≤ 30" in r, r)
r = srv.tool_stats({"action": "outlier", "data": [0, 1, 2, 3, 10],
                    "criterion": "dixon", "alpha": 0.03})
ok("狄克松检出水平仅 0.05/0.01 拦截", "❌" in r and "0.05 / 0.01" in r, r)
r = srv.tool_stats({"action": "outlier"})
ok("缺 data 拦截", "❌" in r and "data" in r, r)

# ====================== weibull：已知值（完美样本还原） ======================
print("== 34. weibull 已知值（m=8、σ₀=500 完美样本）==")
m, s0, r2 = srv._weibull_fit(WS)
ok("完美样本回归还原 m = 8（内部精确）", approx(m, W_M, 1e-6), m)
ok("完美样本回归还原 σ₀ = 500（内部精确）", approx(s0, W_S0, 1e-4), s0)
ok("完美样本 R² ≈ 1", r2 > 1 - 1e-9, r2)
m2, s02, _ = srv._weibull_fit(WS[::-1])
ok("乱序输入自动排序（m 不变）", approx(m2, m, 1e-12), (m, m2))

r = srv.tool_stats({"action": "weibull", "data": WS})
ok("输出模数 m = 8", "Weibull 模数 m = 8" in r, r)
ok("输出特征强度 σ₀ = 500", "特征强度 σ₀ = 500" in r, r)
ok("输出 R² = 1", "R² = 1" in r, r)
ok("输出 B10 强度 ≈ 377.4（500·(ln(10/9))^(1/8)）", "B10 强度" in r and "377.4" in r, r)
ok("标题含方法与样本数", "中位秩线性回归" in r and "n = 10" in r, r)
ok("小样本与体积效应提示", "n < 8" in r and "体积效应" in r, r)

r = srv.tool_stats({"action": "weibull", "data": WS, "stress": 500})
ok("σ=σ₀ 处破坏概率恒 63.2%（特征强度定义自检）",
   "P_f = 0.6321" in r and "存活率 0.3678" in r, r)
r = srv.tool_stats({"action": "weibull", "data": WS, "stress": 100})
pf100 = 1.0 - math.exp(-(100.0 / W_S0) ** W_M)
ok("低应力预测：P_f 数值与手算一致（科学计数分支）",
   ("P_f = " + srv._fmt(pf100)) in r, (r, pf100, srv._fmt(pf100)))

r = srv.tool_stats({"action": "weibull", "data": [500, 500, 500]})
ok("全同值数据退化拦截", "❌" in r and "退化" in r, r)
r = srv.tool_stats({"action": "weibull", "data": [100, 200, 300, 0]})
ok("含 0/负值拦截（ln 无定义）", "❌" in r and "全部为正" in r, r)
r = srv.tool_stats({"action": "weibull", "data": [100, 200]})
ok("n < 3 拦截", "❌" in r and "n ≥ 3" in r, r)
r = srv.tool_stats({"action": "weibull", "data": WS, "stress": -5})
ok("stress 非正拦截", "❌" in r and "正应力" in r, r)
r = srv.tool_stats({"action": "fitxyz", "data": WS})
ok("未知 action 提示包含 outlier / weibull",
   "❌" in r and "outlier" in r and "weibull" in r, r)

# ====================== 协议层：19 工具 + stdio 冒烟 ======================
print("== 35. 协议层 19 工具与 stdio 冒烟 ==")
ok("TOOLS 共 19 个（0.4.6 不新增工具）", len(srv.TOOLS) == 19, len(srv.TOOLS))
ok("_DISPATCH 覆盖全部 TOOLS 名称",
   all(t["name"] in srv._DISPATCH for t in srv.TOOLS)
   and len(srv._DISPATCH) == len(srv.TOOLS))
stats_schema = next(t for t in srv.TOOLS if t["name"] == "labmate_stats")
ok("stats schema 描述含 outlier/weibull",
   "outlier" in stats_schema["description"] and "weibull" in stats_schema["description"])
ok("stats schema 新参数 criterion/stress 声明",
   "criterion" in stats_schema["inputSchema"]["properties"]
   and "stress" in stats_schema["inputSchema"]["properties"])
ok("action 枚举含 outlier|weibull",
   "outlier|weibull" in stats_schema["inputSchema"]["properties"]["action"]["description"])

def rpc(msgs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "labmate_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode("utf-8"))
    return [json.loads(l) for l in out.decode("utf-8").splitlines() if l.strip()]

res = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
           {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "labmate_stats",
                       "arguments": {"action": "outlier", "data": [0, 1, 2, 3, 20],
                                     "criterion": "dixon"}}},
           {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "labmate_stats",
                       "arguments": {"action": "weibull", "data": WS}}}])
ok("initialize 版本 = 0.4.6", res[0]["result"]["serverInfo"]["version"] == "0.4.6", res[0])
ok("stdio outlier 剔除判定不丢",
   "统计离群值，剔除" in res[1]["result"]["content"][0]["text"], res[1]["result"]["content"][0]["text"][:150])
ok("stdio weibull 已知值不丢（m = 8）",
   "Weibull 模数 m = 8" in res[2]["result"]["content"][0]["text"], res[2]["result"]["content"][0]["text"][:150])

print("\n== v0.4.4 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

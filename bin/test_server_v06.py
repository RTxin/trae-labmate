# -*- coding: utf-8 -*-
"""LabMate server 0.4.2 单测：labmate_plot（论文级 SVG 绘图）+ labmate_curve（曲线特征提取）。
已知值验证：合成「线弹性(E=200)→理想塑性平台」曲线，E / 0.2% 偏移屈服点 /
Simpson 总能量均手工可算；SVG 断言结构与抽稀；边界覆盖长度不等、空数组、
errorbar 缺 y_err、log 轴负值、x 重复、弹性窗口非法、无屈服交点诚实提示。"""
import json
import os
import subprocess
import sys
import tempfile

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

# 合成曲线：x ∈ [0, 0.006] 步长 0.0005（13 点，12 段）；y = 200x 弹性段 + 0.4 平台
CX = [i * 0.0005 for i in range(13)]
CY = [min(200.0 * v, 0.4) for v in CX]
# 手工已知值：E=200；0.2% 偏移交点 (0.004, 0.4)；峰值 0.4 @ x=0.002；
# 总能量 = 三角 0.5*0.002*0.4 + 矩形 0.004*0.4 = 0.002（Simpson 精确）

# ====================== 底层引擎：刻度 / 抽稀 ======================
print("== 25. SVG 底层引擎 ==")
ok("nice ticks [0,1] → 0/0.2/…/1 步长 0.2",
   srv._nice_ticks(0, 1) == [0, 0.2, 0.4, 0.6, 0.8, 1.0], srv._nice_ticks(0, 1))
ok("nice ticks [0.35,3.7] → step 1，只含域内 [1,2,3]",
   srv._nice_ticks(0.35, 3.7) == [1, 2, 3], srv._nice_ticks(0.35, 3.7))
ok("nice ticks [0,10] → 步长 2", srv._nice_ticks(0, 10) == [0, 2, 4, 6, 8, 10])
ok("nice ticks 退化区间 [5,5] 不空且等距",
   len(srv._nice_ticks(5, 5)) >= 2)
ok("tick label 0.002/1234.5/2e5/1e-4 紧凑形式",
   srv._tick_label(0.002) == "0.002" and srv._tick_label(1234.5) == "1234.5"
   and srv._tick_label(2e5) == "2e5" and srv._tick_label(1e-4) == "0.0001",
   (srv._tick_label(2e5), srv._tick_label(1e-4)))
ok("log ticks [1,100] → 1/2/5/10/20/50/100",
   srv._log_ticks(1, 100) == [1, 2, 5, 10, 20, 50, 100])
ok("log ticks 跨 6 个数量级只给 10 的幂",
   srv._log_ticks(1, 1e6) == [10 ** d for d in range(7)])
ok("抽稀：2000 点保留首末且 ≤ 800",
   (lambda idx: len(idx) <= 800 and idx[0] == 0 and idx[-1] == 1999)(srv._decimate_idx(2000)))
ok("不抽稀：10 点全保留", srv._decimate_idx(10) == list(range(10)))
ok("XML 转义 &<>\" 防注入",
   srv._xml_escape('a<b>&"c"') == 'a&lt;b&gt;&amp;&quot;c&quot;')

# ====================== labmate_plot：SVG 结构 ======================
print("== 26. labmate_plot SVG 结构 ==")
r = srv.tool_plot({"x": CX, "y": CY, "labels": ["试验", "理论"],
                   "x2": [0, 0.006], "y2": [0, 0.45],
                   "title": "应力-应变曲线", "xlabel": "应变", "ylabel": "应力 (MPa)"})
ok("双组折线：viewBox + 双 polyline", "viewBox" in r and r.count("<polyline") >= 2, r[:120])
ok("图例框含两组文字", "试验" in r and "理论" in r and "legend" not in r)
ok("标题/轴标签渲染（中文）",
   "应力-应变曲线" in r and "应变" in r and "应力 (MPa)" in r)
ok("刻度标签存在（0 基线）", ">0<" in r and ">0.002<" in r, r[:400])
ok("网格线 stroke=#e4e4e4", "e4e4e4" in r)
ok("零基线加深（线性轴）", "#b8b8b8" in r)
ok("摘要行含点数与双系列", "试验：13 点" in r and "理论：2 点" in r)
ok("存图提示（未给 save_path）", "save_path" in r)

r = srv.tool_plot({"action": "scatter", "x": [1, 2, 3, 4], "y": [2, 3.5, 2.8, 5]})
ok("散点模式：只画 circle 无 polyline", r.count("<circle") == 4 and "<polyline" not in r, r[:200])
ok("散点无 labels 不出图例框", r.count('stroke="#999"') == 0)

r = srv.tool_plot({"action": "errorbar", "x": [1, 2, 3], "y": [10, 20, 15],
                   "y_err": [1, 2, 1.5]})
ok("误差棒：折线 + 每点竖线与上下端帽（9 条细线）",
   "<polyline" in r and r.count('stroke-width="1.1"') == 9, r.count('stroke-width="1.1"'))
ok("误差计入 y 值域（摘要不报错）", "errorbar" in r and "3 点" in r)

r = srv.tool_plot({"x": [1, 2, 3, 4, 5], "y": [10, 100, 500, 800, 950], "log_y": True})
ok("log_y 正常出图：1-2-5 对数刻度", ">100<" in r and ">10<" in r, r[:400])
r = srv.tool_plot({"x": [1, 2, 3], "y": [1, -2, 3], "log_y": True})
ok("log_y 含负值拦截", "❌" in r and "log_y" in r, r)
r = srv.tool_plot({"x": [0, 1, 2], "y": [1, 2, 3], "log_x": True})
ok("log_x 含 0 拦截", "❌" in r and "log_x" in r, r)
r = srv.tool_plot({"action": "errorbar", "x": [1, 2, 3], "y": [1, 2, 3]})
ok("errorbar 缺 y_err 拦截", "❌" in r and "y_err" in r, r)
r = srv.tool_plot({"x": [1, 2, 3], "y": [1, 2]})
ok("x/y 长度不等拦截", "❌" in r and "等长" in r, r)
r = srv.tool_plot({"x": [1], "y": [1]})
ok("单点拦截", "❌" in r and "至少 2" in r, r)
r = srv.tool_plot({"x": [1, 2], "y": [1, 2], "x2": [1, 2, 3]})
ok("第二组缺 y2 拦截", "❌" in r and "x2/y2" in r, r)
r = srv.tool_plot({"x": [1, 2, 3], "y": [1, 2, 3], "y_err": [0.1, -0.2, 0.1]})
ok("负误差拦截", "❌" in r and "非负" in r, r)
r = srv.tool_plot({"x": [1, 2, 3], "y": [1, 2, 3], "action": "pie"})
ok("未知 action 拦截", "❌" in r and "line" in r and "scatter" in r, r)
r = srv.tool_plot({"x": list(range(3000)), "y": [v * 1.5 for v in range(3000)]})
ok("3000 点自动抽稀并明示", "抽稀至" in r and "3000 点" in r, r[:200])

# save_path 落盘
svgt = os.path.join(tempfile.gettempdir(), "labmate_应力应变.svg")
r = srv.tool_plot({"x": CX, "y": CY, "save_path": svgt})
ok("save_path 写文件且内容为 SVG",
   "已保存" in r and os.path.exists(svgt) and open(svgt, encoding="utf-8").read(4) == "<svg")

# ====================== labmate_curve：已知值 ======================
print("== 27. labmate_curve 已知值（E=200 线弹性 + 平台）==")
r = srv.tool_curve({"x": CX, "y": CY})
ok("弹性模量 E = 200（前 20% 窗口回归）", "弹性模量 E = 200" in r, r)
ok("R² = 1（弹性段完全线性）", "R² = 1" in r, r)
ok("0.2% 偏移屈服 = 0.4 @ x = 0.004",
   "屈服强度 = 0.4" in r and "x = 0.004" in r, r)
ok("峰值强度 = 0.4（x = 0.002）", "峰值强度 = 0.4" in r and "x = 0.002" in r, r)
ok("总能量 = 0.002（Simpson 12 段等距）",
   "总能量（曲线下面积）= 0.002" in r and "Simpson" in r and "12 段等距" in r, r)
ok("弹性段窗口描述", "前 3 点" in r and "initial_frac=0.2" in r, r)
ok("末点报告", "末点（断裂/卸载）：x = 0.006，y = 0.4" in r, r)

# 变偏移量：0.1% → 交点 x = 0.004 - 0.001 = 0.003（平移线 y=200(x-0.001)）
r = srv.tool_curve({"x": CX, "y": CY, "yield_offset": 0.001})
ok("yield_offset=0.001：屈服 x 平移到 0.003", "x = 0.003" in r, r)

# 非均匀间距 → 梯形回退；能量 = 0.002（同曲线重排 x）
r = srv.tool_curve({"x": [0, 0.0005, 0.001, 0.002, 0.0035, 0.006],
                    "y": [0, 0.1, 0.2, 0.4, 0.4, 0.4]})
ok("间距不等自动回退梯形法", "梯形法" in r and "间距不等" in r, r)

# 脆性线弹性（无屈服）→ 诚实提示
r = srv.tool_curve({"x": [0, 0.001, 0.002, 0.003, 0.004],
                    "y": [0, 0.1, 0.2, 0.3, 0.4]})
ok("脆性无平台：偏移交点诚实提示「未找到」", "未找到" in r and "弹性模量 E = 100" in r, r)

# 下降曲线 → 斜率非正警告 + 跳过屈服
r = srv.tool_curve({"x": [0, 1, 2, 3, 4], "y": [5, 4, 3, 2, 1]})
ok("斜率为负：⚠ 警告 + 屈服跳过", "⚠" in r and "跳过" in r, r)

# initial_frac 窗口
r = srv.tool_curve({"x": CX, "y": CY, "initial_frac": 0.5})
ok("initial_frac=0.5：弹性段扩到 x ≤ 0.003（前 7 点）", "前 7 点" in r, r)
r = srv.tool_curve({"x": CX, "y": CY, "initial_frac": 0})
ok("initial_frac=0 拦截", "❌" in r and "(0, 1]" in r, r)
r = srv.tool_curve({"x": CX, "y": CY, "initial_frac": 1.5})
ok("initial_frac>1 拦截", "❌" in r and "(0, 1]" in r, r)

# 边界
r = srv.tool_curve({"x": [0, 1, 2, 3], "y": [0, 1, 2, 3, 4]})
ok("x/y 长度不等拦截（带长度数字）", "❌" in r and "4 / 5" in r, r)
r = srv.tool_curve({"x": [0, 1, 2], "y": [1, 2, 3]})
ok("点数 < 4 拦截", "❌" in r and "至少 4" in r, r)
r = srv.tool_curve({"x": [0, 1, 1, 2], "y": [0, 1, 2, 3]})
ok("x 重复值拦截", "❌" in r and "重复" in r, r)
r = srv.tool_curve({"x": [0, 1, 2, 3], "y": [0, 1, 2, 3], "action": "fit"})
ok("未知 action 拦截", "❌" in r and "features" in r, r)
r = srv.tool_curve({"x": CX[::-1], "y": CY[::-1]})
ok("乱序输入自动按 x 排序（E=200 不变）", "弹性模量 E = 200" in r, r)

# ====================== 协议层：19 工具 + stdio 冒烟 ======================
print("== 28. 协议层 19 工具与 stdio 冒烟 ==")
ok("TOOLS 共 19 个", len(srv.TOOLS) == 19, len(srv.TOOLS))
ok("labmate_plot/labmate_curve 均注册",
   any(t["name"] == "labmate_plot" for t in srv.TOOLS)
   and any(t["name"] == "labmate_curve" for t in srv.TOOLS))
ok("_DISPATCH 覆盖全部 TOOLS 名称",
   all(t["name"] in srv._DISPATCH for t in srv.TOOLS)
   and len(srv._DISPATCH) == len(srv.TOOLS))

def rpc(msgs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "labmate_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode("utf-8"))
    return [json.loads(l) for l in out.decode("utf-8").splitlines() if l.strip()]

res = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
           {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
           {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "labmate_curve",
                       "arguments": {"x": CX, "y": CY}}}])
ok("initialize 版本 = 0.4.4", res[0]["result"]["serverInfo"]["version"] == "0.4.4", res[0])
ok("stdio tools/list = 19", len(res[1]["result"]["tools"]) == 19, len(res[1]["result"]["tools"]))
curve_text = res[2]["result"]["content"][0]["text"]
ok("stdio tools/call labmate_curve 已知值不丢",
   "弹性模量 E = 200" in curve_text and "总能量" in curve_text, curve_text[:150])

print("\n== v0.4.2 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

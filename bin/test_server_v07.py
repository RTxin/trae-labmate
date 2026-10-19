# -*- coding: utf-8 -*-
"""LabMate server 0.4.3 新增能力单测：
labmate_plot 加 action=bar（分组柱状：类别轴/双系列并列/误差帽/负值柱）；
labmate_curve 加 action=batch（平行试样批量：逐条提取 + 均值±标准差汇总）。"""
import json
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

def svg_of(r):
    return r.split("```svg\n")[1].split("\n```")[0]

def mk_curve(e):
    """13 点等距（h=0.0005，12 段）：线弹性 min(e·x, 0.4) + 理想塑性平台。"""
    xs = [i * 0.0005 for i in range(13)]
    return xs, [min(e * v, 0.4) for v in xs]

CX, CY = mk_curve(200.0)   # E=200 已知值曲线（与 v06 一致）

# ====================== labmate_plot · action=bar ======================
print("== 29. labmate_plot · action=bar 分组柱状图 ==")
CATS = ["C30", "C40", "C50"]
r = srv.tool_plot({"action": "bar", "x": CATS, "y": [30.1, 41.5, 52.3],
                   "title": "各配合比抗压强度", "ylabel": "强度 MPa"})
ok("bar 基本出图（类型行）", "类型：bar" in r, r[:200])
s = svg_of(r)
ok("单系列 3 根柱（rect）", s.count('fill="#1a5276"') == 3, s.count('fill="#1a5276"'))
ok("类别名渲染为文本", ">C30<" in s and ">C50<" in s, "")
ok("带间浅灰分界线 2 条（3 组）", s.count('stroke="#efefef"') == 2,
   s.count('stroke="#efefef"'))
ok("零基线存在（y 域强制含 0）", s.count('stroke="#b8b8b8"') == 1, "")
ok("摘要单位用「组」（无名单系列默认名）", "系列1：3 组" in r, r[:400])
ok("X 轴默认类别描述", "类别（3 组）" in r, r[:400])
ok("无 labels 不出图例框（散点/折线同规则）", 'stroke="#999"' not in s, "")
ok("bar 无 polyline 连线", "<polyline" not in s, "")
ok("标题与 y 轴标签渲染", "各配合比抗压强度" in s and "强度 MPa" in s, "")

r = srv.tool_plot({"action": "bar", "x": CATS, "y": [30.1, 41.5, 52.3],
                   "y_err": [0.8, 1.2, 1.5], "labels": ["实测"],
                   "xlabel": "配合比设计强度等级"})
s = svg_of(r)
ok("误差帽：3 竖线 + 6 端帽 = 9 条细线", s.count('stroke-width="1.1"') == 9,
   s.count('stroke-width="1.1"'))
ok("图例框 + rect 色块", 'stroke="#999"' in s and 'width="16" height="10"' in s, "")
ok("用户 xlabel 优先于默认类别描述", "配合比设计强度等级（线性）" in r, r[:300])

r = srv.tool_plot({"action": "bar", "x": CATS, "y": [30.1, 41.5, 52.3],
                   "x2": CATS, "y2": [28.9, 40.2, 50.8], "labels": ["7d", "28d"]})
s = svg_of(r)
ok("双系列各 3 柱（含图例色块各 4 处着色）",
   s.count('fill="#1a5276"') == 4 and s.count('fill="#c0392b"') == 4,
   (s.count('fill="#1a5276"'), s.count('fill="#c0392b"')))
ok("图例两组文字", ">7d<" in s and ">28d<" in s, "")
ok("双系列摘要", "7d：3 组" in r and "28d：3 组" in r, r[:400])

r = srv.tool_plot({"action": "bar", "x": ["A", "B", "C"], "y": [5.0, -3.0, 7.0]})
s = svg_of(r)
ok("负值柱正常出图（柱向 0 基线下方）",
   "❌" not in r and s.count('fill="#1a5276"') == 3 and
   s.count('stroke="#b8b8b8"') == 1, r[:200])

r = srv.tool_plot({"action": "bar", "x": ["十二字的长组名测试一号", "B"], "y": [1.0, 2.0]})
ok("组名 >10 字截断加 …", "十二字的长组名测试…" in svg_of(r), svg_of(r)[-300:])

r = srv.tool_plot({"action": "bar", "x": ["solo"], "y": [3.0]})
ok("单组可出图", "类型：bar" in r and "1 组" in r, r[:200])

r = srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [10.0, 100.0], "log_y": True})
ok("bar log_y 正常出图", "（对数）" in r and "❌" not in r, r[:200])

ok("bar x/y 不等长拦截", "❌" in srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [1.0]}), "")
ok("bar x 空拦截", "❌" in srv.tool_plot({"action": "bar", "x": [], "y": [1.0]}), "")
ok("bar y_err 不等长拦截",
   "❌" in srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [1.0, 2.0], "y_err": [0.1]}), "")
ok("bar y_err 负值拦截",
   "❌" in srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [1.0, 2.0], "y_err": [-0.1, 0.2]}), "")
ok("bar x2 组数不匹配拦截",
   "❌" in srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [1.0, 2.0],
                          "x2": ["c"], "y2": [3.0]}), "")
ok("bar 只给 x2 缺 y2 拦截",
   "❌" in srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [1.0, 2.0],
                          "x2": ["c", "d"]}), "")
ok("bar log_y 含 0 拦截",
   "❌" in srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [0.0, 5.0], "log_y": True}), "")
ok("bar log_y 含误差下界 ≤0 拦截",
   "❌" in srv.tool_plot({"action": "bar", "x": ["a", "b"], "y": [0.5, 5.0],
                          "y_err": [0.6, 0.1], "log_y": True}), "")
ok("未知 action 文案含 bar 提示",
   "bar（分组柱状）" in srv.tool_plot({"action": "pie", "x": [1.0], "y": [1.0]}), "")

# ====================== labmate_curve · action=batch ======================
print("== 30. labmate_curve · action=batch 平行试样批量 ==")
CURVES = []
for nm, e in (("A-01", 190.0), ("A-02", 200.0), ("A-03", 210.0)):
    xs, ys = mk_curve(e)
    CURVES.append({"name": nm, "x": xs, "y": ys})
r = srv.tool_curve({"action": "batch", "curves": CURVES})
ok("批量标题（条数+参数）", "平行试样批量特征（3 条曲线，initial_frac=0.2，偏移 0.20%）" in r, r[:200])
ok("A-01 逐行（名字+点数+E）", "- **A-01**（13 点）：E = 190" in r, r[:400])
ok("A-02/A-03 逐行", "E = 200" in r and "E = 210" in r, "")
ok("逐行四特征齐全", "｜峰值 = 0.4｜总能量 = " in r, "")
ok("E 均值 ± std = 200 ± 10（190/200/210 已知值）", "**弹性模量 E = 200 ± 10**" in r, r[:600])
ok("屈服 0.4 ± 0（3/3 条找到交点）",
   "**屈服强度 = 0.4 ± 0**（3/3 条找到交点）" in r, r[:700])
ok("峰值 0.4 ± 0", "**峰值强度 = 0.4 ± 0**" in r, "")
feats = [srv._curve_features(c["x"], c["y"], 0.2, 0.002)[0] for c in CURVES]
m_e, sd_e = srv._curve_ms([f["energy"] for f in feats])
ok("总能量 = 单条 Simpson 能量均值±std（自洽）",
   ("**总能量 = %s ± %s**" % (srv._fmt(m_e), srv._fmt(sd_e))) in r,
   "%s ± %s" % (srv._fmt(m_e), srv._fmt(sd_e)))
ok("成功批次无跳过警告", "已跳过" not in r, "")

r = srv.tool_curve({"action": "batch", "curves": [
    {"name": "good", "x": CX, "y": CY},
    {"name": "short", "x": [0, 1], "y": [0, 1]},
    {"name": "mism", "x": [0, 1, 2], "y": [0, 1]},
    42,
    {"name": "badval", "x": [0, "a", 2, 3], "y": [0, 1, 2, 3]},
]})
ok("坏条目不拖垮整批（汇总 n=1）", "汇总（均值 ± 标准差，n=1）" in r, r[:500])
ok("4 条跳过明细", "⚠ 4 条已跳过" in r and "short：至少 4 个点" in r
   and "mism：x/y 不等长（3 / 2）" in r, r[-400:])
ok("非对象条目定位", "第 4 条不是对象" in r, "")
ok("非数值条目跳过", "badval：x/y 含非数值" in r, "")
ok("n=1 时 std = 0", "**弹性模量 E = 200 ± 0**" in r, "")

r = srv.tool_curve({"action": "batch", "curves": [
    {"name": "plastic", "x": CX, "y": CY},
    {"x": [i * 0.0005 for i in range(13)], "y": [200.0 * v for v in CX]},
]})
ok("未命名曲线默认「曲线2」", "**曲线2**" in r, r[:500])
ok("纯线弹性无平台 → 1/2 条找到交点", "（1/2 条找到交点）" in r, r[:600])
ok("部分缺失时屈服均值只算命中条目", "**屈服强度 = 0.4 ± 0**（1/2 条找到交点）" in r, r[:700])

r = srv.tool_curve({"action": "batch", "curves": [
    {"name": "b1", "x": [i * 0.0005 for i in range(13)], "y": [200.0 * v for v in CX]},
    {"name": "b2", "x": [i * 0.0005 for i in range(13)], "y": [200.0 * v for v in CX]}]})
ok("全部无交点 → 诚实提示均未找到", "均未找到偏移交点（脆性/数据未覆盖屈服段）" in r, r[:600])

ok("curves 空拦截", "❌" in srv.tool_curve({"action": "batch", "curves": []}), "")
ok("curves 非列表拦截", "❌" in srv.tool_curve({"action": "batch", "curves": "abc"}), "")
ok("curves 缺失拦截", "❌" in srv.tool_curve({"action": "batch"}), "")
ok("全部失败拦截（❌ + 明细）",
   "没有任何曲线提取成功" in srv.tool_curve({"action": "batch", "curves": [
       {"name": "s", "x": [0, 1], "y": [0, 1]}]}), "")
ok("batch 共享 frac 校验（0 拦截）",
   "❌" in srv.tool_curve({"action": "batch", "curves": CURVES, "initial_frac": 0}), "")
ok("batch 共享 offset 校验（负值拦截）",
   "❌" in srv.tool_curve({"action": "batch", "curves": CURVES, "yield_offset": -0.001}), "")
ok("乱序曲线自动按 x 排序（E=200 不变）",
   "**弹性模量 E = 200 ± 0**" in srv.tool_curve({"action": "batch", "curves": [
       {"name": "rev", "x": CX[::-1], "y": CY[::-1]}]}), "")
ok("默认 action=features 单条不回归（curves 不干扰）",
   "试验曲线特征" in srv.tool_curve({"x": CX, "y": CY, "curves": CURVES}), "")

# ====================== 协议层：19 工具 + stdio 冒烟 ======================
print("== 31. 协议层 19 工具与 stdio 冒烟 ==")
ok("TOOLS 共 19 个（bar/batch 不新增工具）", len(srv.TOOLS) == 19, len(srv.TOOLS))
ok("labmate_plot/labmate_curve 均注册",
   any(t["name"] == "labmate_plot" for t in srv.TOOLS)
   and any(t["name"] == "labmate_curve" for t in srv.TOOLS))
ok("_DISPATCH 覆盖全部 TOOLS 名称",
   all(t["name"] in srv._DISPATCH for t in srv.TOOLS)
   and len(srv._DISPATCH) == len(srv.TOOLS))
plot_schema = [t for t in srv.TOOLS if t["name"] == "labmate_plot"][0]
ok("plot schema：action 含 bar", "bar" in plot_schema["inputSchema"]["properties"]["action"]["description"], "")
curve_schema = [t for t in srv.TOOLS if t["name"] == "labmate_curve"][0]
ok("curve schema：action 含 batch + curves 参数",
   "batch" in curve_schema["inputSchema"]["properties"]["action"]["description"]
   and "curves" in curve_schema["inputSchema"]["properties"], "")

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
                       "arguments": {"action": "batch", "curves": CURVES}}}])
ok("initialize 版本 = 0.4.3", res[0]["result"]["serverInfo"]["version"] == "0.4.3", res[0])
ok("stdio tools/list = 19", len(res[1]["result"]["tools"]) == 19, len(res[1]["result"]["tools"]))
batch_text = res[2]["result"]["content"][0]["text"]
ok("stdio tools/call batch 已知值不丢（E=200 ± 10）",
   "平行试样批量特征" in batch_text and "**弹性模量 E = 200 ± 10**" in batch_text,
   batch_text[:150])

print("\n== v0.4.3 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

# -*- coding: utf-8 -*-
"""LabMate server 单元测试 + stdio 冒烟测试"""
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
        print("  FAIL  %s  %s" % (name, detail))

print("== 1. labmate_convert ==")
r = srv.tool_convert({"value": 100, "from": "kN", "to": "N"})
ok("100 kN -> 100000 N", "100000" in r, r)
r = srv.tool_convert({"value": 100, "from": "kN", "to": "kgf"})
ok("100 kN -> 约10197 kgf", "10197" in r, r)
r = srv.tool_convert({"value": 1, "from": "MPa", "to": "psi"})
ok("1 MPa -> 145.04 psi", "145" in r, r)
r = srv.tool_convert({"value": 1, "from": "kN", "to": "MPa"})
ok("量纲不匹配拦截", "量纲不匹配" in r, r)
r = srv.tool_convert({"value": 1, "from": "furlong", "to": "m"})
ok("未知单位拦截+提示可用单位", "未识别单位" in r and "力" in r, r)

print("== 2. labmate_handcalc ==")
r = srv.tool_handcalc({
    "vars": {"F": 150000, "b": 0.10, "h_s": 0.025},
    "steps": [
        {"symbol": "A_s", "formula": "b * h_s", "note": "剪切面积", "unit": "m2"},
        {"symbol": "tau", "formula": "F / A_s", "note": "试验机满载剪应力", "unit": "Pa"},
    ]})
ok("试验机案例：A_s=0.0025m2 → tau=6.0e7Pa(60MPa)", "tau = 6.0000e+07 Pa" in r, r)
ok("三段式含公式行", "**A_s = b * h_s**" in r, r)
try:
    srv._safe_eval("__import__('os').system('echo hacked')", {})
    ok("AST 拒绝注入", False, "未被拦截！")
except Exception:
    ok("AST 拒绝注入", True)
try:
    srv._safe_eval("F / A", {"F": 1.0})
    ok("AST 拒绝未声明变量", False)
except Exception:
    ok("AST 拒绝未声明变量", True)

print("== 3. labmate_mohr ==")
r = srv.tool_mohr({"stress_pairs": [[30, 5], [40, 10]], "c": 3, "phi_deg": 30})
ok("圆心/半径计算", "σc=17.5" in r and "r=12.5" in r, r)
ok("包络表达式", "tan(30.0°)" in r or "tan(30°)" in r, r)
ok("破坏初判输出", ("已破坏" in r or "未破坏" in r), r)
svg = srv._mohr_svg([(30, 5, 17.5, 12.5)], 3, 30)
ok("SVG 生成（含 ellipse/包络线）", "ellipse" in svg and "stroke-dasharray" in svg)

print("== 4. labmate_fit_lite ==")
r = srv.tool_fit({"x": [1, 2, 3, 4], "y": [2, 4, 6, 8], "model": "linear"})
ok("线性拟合 R2=1", "R² = 1" in r, r)
r = srv.tool_fit({"x": [1, 2, 3, 4], "y": [1, 4, 9, 16], "model": "power"})
ok("幂律 y=x^2 指数≈2", "x^(2)" in r, r)
r = srv.tool_fit({"x": [1, 2], "y": [1]})
ok("数据长度校验", "❌" in r, r)

print("== 5. labmate_deps ==")
r = srv.tool_deps({})
ok("体检报告输出", "体检" in r and ("✅" in r and "❌" in r), r[:200])

print("== 6. stdio 协议冒烟 ==")
def rpc(msgs):
    p = subprocess.run([sys.executable, os.path.join(HERE, "labmate_server.py")],
                       input="\n".join(msgs) + "\n", capture_output=True,
                       text=True, encoding="utf-8", timeout=30)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]

out = rpc([
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}',
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"labmate_convert","arguments":{"value":100,"from":"kN","to":"kgf"}}}',
])
ok("initialize 应答", out[0]["result"]["serverInfo"]["name"] == "labmate")
ok("tools/list 20 个工具（0.4.9）", len(out[1]["result"]["tools"]) == 20, str(len(out[1]["result"].get("tools", []))))
ok("tools/call 中文无乱码", "kgf" in out[2]["result"]["content"][0]["text"], out[2]["result"]["content"][0]["text"][:60])

print("\n========== %d 通过，%d 失败 ==========" % (passed, failed))
sys.exit(1 if failed else 0)

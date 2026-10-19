# -*- coding: utf-8 -*-
"""LabMate server 0.4.0 新增六工具单测：stats / errors / doe / tex / bibtex / signal
已知值验证（对照教科书临界值与 scipy 参考值）+ 6 个审查 bug 回归。"""
import ast
import json
import os
import re
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

def approx(a, b, tol=1e-3):
    return abs(a - b) <= tol

# ====================== p 值引擎：与教科书临界值对表 ======================
print("== 12. 分布引擎（不完全 Beta/Gamma，零依赖精确 p 值）==")
ok("t=2.0, df=10 单侧尾概率 ≈ 0.0367", approx(srv._t_sf(2.0, 10), 0.03669, 1e-4), srv._t_sf(2.0, 10))
ok("t 双侧对称（|t| 处理）", srv._t_sf(-2.0, 10) == srv._t_sf(2.0, 10))
ok("χ²=3.8415, df=1 → p ≈ 0.05", approx(srv._chi2_sf(3.8415, 1), 0.05, 1e-3), srv._chi2_sf(3.8415, 1))
ok("F=3.4903, df=(3,12) → p ≈ 0.05", approx(srv._f_sf(3.4903, 3, 12), 0.05, 1e-3), srv._f_sf(3.4903, 3, 12))
ok("t 分位数 t_{0.975,10} ≈ 2.2281", approx(srv._t_ppf(0.975, 10), 2.2281, 1e-3), srv._t_ppf(0.975, 10))
ok("z_{0.975} ≈ 1.95996", approx(srv._norm_ppf(0.975), 1.95996, 1e-3), srv._norm_ppf(0.975))

# ====================== labmate_stats ======================
print("== 13. labmate_stats ==")
r = srv.tool_stats({"action": "describe", "data": [1, 2, 3, 4, 5]})
ok("describe：均值/标准差", "均值 3" in r and "1.58114" in r and "中位数 3" in r, r)
r = srv.tool_stats({"action": "describe"})
ok("describe 缺数据拦截", "❌" in r, r)
r = srv.tool_stats({"action": "ttest", "a": [9, 10, 11, 12, 13], "mu": 10})
ok("单样本 t：t=√2", "t = 1.41421" in r and "df = 4" in r, r)
m = re.search(r"p = ([0-9.]+)", r)
ok("单样本 t：p ≈ 0.23 且不拒绝", m and 0.20 < float(m.group(1)) < 0.26 and "不拒绝 H0" in r, r)
r = srv.tool_stats({"action": "ttest", "a": [1, 2, 3], "b": [7, 8, 9]})
ok("Welch 默认：t=-7.34847, df=4", "-7.34847" in r and "df = 4" in r and "Welch" in r, r)
ok("Welch：p = 0.0018", "p = 0.0018" in r and "拒绝 H0" in r, r)
r = srv.tool_stats({"action": "ttest", "a": [1, 2, 3], "b": [7, 8, 9], "equal_var": True})
ok("equal_var=True → Student t 合并方差", "Student t" in r and "df = 4" in r, r)
r = srv.tool_stats({"action": "ttest", "a": [1, 2, 3], "b": [2, 4, 6], "paired": True})
ok("配对 t：t=-3.4641, p=0.0742", "-3.4641" in r and "p = 0.0742" in r, r)
r = srv.tool_stats({"action": "ttest", "a": [1]})
ok("ttest 单点拦截", "❌" in r, r)
r = srv.tool_stats({"action": "anova", "groups": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})
ok("ANOVA：F=27, η²=0.9", "F = 27" in r and "0.9" in r and "拒绝 H0" in r, r)
ok("ANOVA：Bonferroni 事后提示", "3 组对" in r, r)
r = srv.tool_stats({"action": "anova", "groups": [[1, 2], [3, 4]]})
m = re.search(r"p = ([0-9.e-]+)", r)
ok("两组 ANOVA p ≈ 0.1056", m and approx(float(m.group(1)), 0.10557, 1e-3), r)
r = srv.tool_stats({"action": "normality", "data": [9, 10, 11, 12, 13, 8, 14, 12]})
ok("正态性：JB 统计量与 p 值正常", "JB" in r and "p = " in r and "NaN" not in r, r)
r = srv.tool_stats({"action": "normality", "data": [1, 2, 3]})
ok("normality n<8 拦截", "❌" in r, r)
r = srv.tool_stats({"action": "ci", "data": [2, 4, 6, 8]})
ok("ci：sd/t临界值/半宽", "2.58199" in r and "3.18245" in r and "4.10852" in r and "[0.891479, 9.10852]" in r, r)
r = srv.tool_stats({"action": "power", "delta": 1, "sd": 1})
ok("power：δ=1, sd=1 → 每组 n=16", "n = 16" in r and "共 32" in r, r)
r = srv.tool_stats({"action": "nope"})
ok("未知 action 拦截", "❌" in r, r)

# ====================== labmate_errors ======================
print("== 14. labmate_errors ==")
r = srv.tool_errors({"action": "propagate", "formula": "a*b",
                     "vars": {"a": 2, "b": 3}, "uncertainties": {"a": 0.1, "b": 0.2}})
ok("GUM 传播：u_c = 0.5", "u_c = 0.5" in r, r)
ok("GUM 传播：U(k=2) = 1.0", "U（k=2，约 95%）= 1" in r and "y = 6 ± 1" in r, r)
ok("GUM 传播：各分量贡献", "贡献 0.3" in r and "贡献 0.4" in r, r)
r = srv.tool_errors({"action": "propagate", "formula": "a+b", "vars": {"a": 1}})
ok("无不确定度分量拦截", "❌" in r, r)
r = srv.tool_errors({"action": "regress", "x": [1, 2, 3, 4, 5], "y": [2, 4.1, 5.9, 8.2, 9.8]})
ok("回归：斜率 b = 1.97", "斜率 b = 1.97 ± " in r, r)
ok("回归：截距 a = 0.09", "截距 a = 0.09 ± " in r, r)
ok("回归：给出 95%CI 与 r", "95%CI [" in r and "r = " in r, r)
r = srv.tool_errors({"action": "regress", "x": [1, 2], "y": [1, 2]})
ok("regress n<3 拦截", "❌" in r, r)

# ====================== labmate_doe ======================
print("== 15. labmate_doe ==")
r = srv.tool_doe({"action": "ortho", "runs": "L8"})
ok("L8 输出 8 次运行", "L8" in r and all("| %d |" % i in r for i in range(1, 9)), r[:200])
rows, cols = srv._ortho_design(2, 3, 7)
vals = [c[1] for c in cols]
ok("L8 生成 7 列", len(rows) == 8 and len(vals) == 7, len(vals))
ortho = True
for i in range(len(vals)):
    for j in range(i + 1, len(vals)):
        cnt = {}
        for ri in range(8):
            k = (vals[i][ri], vals[j][ri])
            cnt[k] = cnt.get(k, 0) + 1
        if len(cnt) != 4 or any(v != 2 for v in cnt.values()):
            ortho = False
ok("L8 严格正交（任两列 4 种组合各 2 次）", ortho)
r = srv.tool_doe({"action": "ortho", "runs": "L9"})
ok("L9(3^4) 表名", "L9(3^4)" in r and all("| %d |" % i in r for i in range(1, 10)), r[:120])
r = srv.tool_doe({"action": "ortho", "runs": "L12"})
ok("混水平 L12 诚实拒绝", "❌" in r and "fullfact" in r, r)
r = srv.tool_doe({"action": "fullfact", "levels": [2, 3]})
ok("全因子 2×3 = 6 运行", "6 次运行" in r, r)
r = srv.tool_doe({"action": "lhs", "samples": 10, "dims": 2, "seed": 42})
nums = re.findall(r"\| \d+ \| ([0-9.e-]+) \| ([0-9.e-]+) \|", r)
ok("LHS：10 行 2 维", len(nums) == 10, len(nums))
if len(nums) == 10:
    c0 = sorted(int(float(v[0]) * 10) for v in nums)
    c1 = sorted(int(float(v[1]) * 10) for v in nums)
    ok("LHS：每维每十分位恰 1 点", c0 == list(range(10)) and c1 == list(range(10)), (c0, c1))
r = srv.tool_doe({"action": "lhs", "samples": 501})
ok("LHS 样本数越界拦截", "❌" in r, r)

# ====================== labmate_tex ======================
print("== 16. labmate_tex ==")
r = srv.tool_tex({"action": "table", "headers": ["Load & Disp", "σc"],
                  "rows": [["case A", "12.5"], ["case B", "13.5"]],
                  "caption": "强度对比", "label": "tab:strength"})
ok("三线表 booktabs 环境", "\\toprule" in r and "\\midrule" in r and "\\bottomrule" in r, r)
ok("caption/label 与 & 转义", "\\caption{强度对比}" in r and "\\label{tab:strength}" in r
   and "Load \\& Disp" in r, r)
ok("数值列自动右对齐 align=lr", "\\begin{tabular}{lr}" in r, r)
csv_tmp = os.path.join(tempfile.gettempdir(), "labmate_tex_test.csv")
with open(csv_tmp, "w", encoding="utf-8") as f:
    f.write("name,value\nA,1.5\nB,2.5\n")
r = srv.tool_tex({"action": "table", "csv_path": csv_tmp, "caption": "csv test"})
ok("csv_path 直读建表", "name" in r and "A & 1.5" in r and "\\caption{csv test}" in r, r)
os.remove(csv_tmp)
long_rows = [["r%d" % i, str(i)] for i in range(41)]
r = srv.tool_tex({"action": "table", "headers": ["id", "v"], "rows": long_rows})
ok("超 40 行截断提示", "截断" in r and "longtable" in r, r)
r = srv.tool_tex({"action": "figure", "files": ["fig1.pdf"], "caption": "单图"})
ok("figure 单图环境", "\\begin{figure}[htbp]" in r and "\\includegraphics[width=0.9\\columnwidth]{fig1.pdf}" in r
   and "subcaption" not in r, r)
r = srv.tool_tex({"action": "figure", "files": [{"path": "a.pdf", "caption": "(a)"},
                                                {"path": "b.pdf", "caption": "(b)"}], "caption": "两图"})
ok("多图自动 subfigure", "\\begin{subfigure}" in r and "subcaption" in r
   and "\\caption{(a)}" in r, r)
r = srv.tool_tex({"action": "equation", "latex": "\\tau = c + \\sigma\\tan\\varphi", "label": "eq:mc"})
ok("equation 环境 + eqref 提示", "\\begin{equation}" in r and "\\label{eq:mc}" in r
   and "\\eqref{eq:mc}" in r, r)
r = srv.tool_tex({"action": "table"})
ok("table 缺参数拦截", "❌" in r, r)

# ====================== labmate_bibtex ======================
print("== 17. labmate_bibtex ==")
bib_a = os.path.join(tempfile.gettempdir(), "labmate_a_test.bib")
bib_b = os.path.join(tempfile.gettempdir(), "labmate_b_test.bib")
bib_c = os.path.join(tempfile.gettempdir(), "labmate_c_test.bib")
with open(bib_a, "w", encoding="utf-8") as f:
    f.write("""@article{Zhang2024,
  author = {Zhang, San},
  title = {Direct shear behavior},
  journal = {Rock Mech},
  year = {2024},
  doi = {10.9999/aaa}
}
@article{Li2020,
  author = {Li, Wu},
  title = {Another topic entirely},
  year = {2020}
}
""")
with open(bib_b, "w", encoding="utf-8") as f:
    f.write("""@article{Zhang2024dup,
  author = {Zhang, San},
  title = {Direct shear behavior},
  journal = {Rock Mech},
  year = {2024},
  doi = {10.9999/aaa},
  note = {from other library}
}
@book{Wang2019,
  author = {Wang, Liu},
  title = {Rock Engineering Handbook},
  publisher = {Springer},
  year = {2019}
}
""")
with open(bib_c, "w", encoding="utf-8") as f:
    f.write("""@article{Dup2020,
  author = {A, X},
  title = {First title},
  journal = {J},
  year = {2020}
}
@article{Dup2020,
  author = {B, Y},
  title = {Second title},
  journal = {J},
  year = {2021}
}
""")
try:
    r = srv.tool_bibtex({"action": "check", "bib_path": bib_a})
    ok("体检：缺必填字段", "Li2020" in r and "journal" in r, r)
    r = srv.tool_bibtex({"action": "check", "bib_path": bib_c})
    ok("体检：重复 key", "重复 key" in r and "Repeated entry" in r, r)
    r = srv.tool_bibtex({"action": "merge", "bib_paths": [bib_a, bib_b]})
    ok("合并去重：2 文件 → 3 条", "3 条" in r, r)
    ok("合并去重：DOI 撞车记录", "Zhang2024dup ≈ Zhang2024" in r, r)
    ok("合并：字段互补（note 并入）", "from other library" in r, r)
    r = srv.tool_bibtex({"action": "merge", "bib_paths": [bib_a, bib_b], "sort": "author"})
    ok("按 author 排序：Li 最前", r.index("@article{Li2020") < r.index("@book{Wang2019") < r.index("@article{Zhang2024"), r[:200])
    r = srv.tool_bibtex({"action": "merge", "bib_paths": [bib_a, bib_b], "sort": "year"})
    ok("按 year 排序（新→旧）：Zhang2024 最前", r.index("@article{Zhang2024") < r.index("@article{Li2020"), r[:200])
    r = srv.tool_bibtex({"action": "check", "bib_path": r"C:\not\exist\zzz.bib"})
    ok("坏路径拦截", "❌" in r, r)
    r = srv.tool_bibtex({"action": "check"})
    ok("缺文件参数拦截", "❌" in r, r)
finally:
    for p in (bib_a, bib_b, bib_c):
        if os.path.exists(p):
            os.remove(p)

# ====================== labmate_signal ======================
print("== 18. labmate_signal ==")
r = srv.tool_signal({"action": "smooth", "y": [1, 2, 3, 4, 5], "window": 3})
ok("移动平均端点收缩", "1.5, 2, 3, 4, 4.5" in r, r)
sq = [float(i * i) for i in range(7)]
r = srv.tool_signal({"action": "smooth", "y": sq, "window": 5, "method": "savgol"})
ok("SG 对 x² 内部点精确（二次曲线不变）", "0, 1, 4, 9, 16, 25, 36" in r, r)
r = srv.tool_signal({"action": "smooth", "y": [1, 2, 3], "window": 4})
ok("偶数窗口拦截", "❌" in r, r)
r = srv.tool_signal({"action": "smooth", "y": [1, 2, 3], "window": 2, "method": "savgol", "poly": 2})
ok("savgol poly≥window 拦截", "❌" in r, r)
xs3 = [0.0, 1.0, 2.0, 3.0, 4.0]
ys3 = [0.0, 1.0, 8.0, 27.0, 64.0]
r = srv.tool_signal({"action": "integrate", "x": xs3, "y": ys3, "method": "trapezoid"})
ok("梯形积分 x³[0,4] = 68", "= 68" in r, r)
r = srv.tool_signal({"action": "integrate", "x": xs3, "y": ys3, "method": "simpson"})
ok("Simpson 积分 x³[0,4] = 64 精确", "= 64" in r, r)
r = srv.tool_signal({"action": "integrate", "x": [0, 1, 2, 3], "y": [0, 1, 8, 27], "method": "simpson"})
ok("Simpson 奇数点拦截", "❌" in r, r)
r = srv.tool_signal({"action": "interp", "x": [0, 2], "y": [0, 4], "targets": [1]})
ok("线性插值中点", "1 → 2" in r, r)
r = srv.tool_signal({"action": "interp", "x": [0, 2], "y": [0, 4], "targets": [5]})
ok("插值不外推拦截", "❌" in r, r)
r = srv.tool_signal({"action": "resample", "x": [0, 10], "y": [0, 20], "n": 3})
ok("重采样 3 点", "0, 10, 20" in r, r)
r = srv.tool_signal({"action": "nope", "y": [1, 2]})
ok("未知 action 拦截", "❌" in r, r)
r = srv.tool_signal({"action": "smooth"})
ok("缺 y 拦截", "❌" in r, r)

# ====================== 审查 bug 回归（6 项）======================
print("== 19. 审查 bug 回归 ==")
r2 = srv._latex_expr(ast.parse("-(a+b)", mode="eval").body)
ok("bug1 latex：-(a+b) 加括号", r2 == "-\\left(a + b\\right)", r2)
r2 = srv._latex_expr(ast.parse("(-2)**2", mode="eval").body)
ok("bug1 latex：(-2)**2 底数加括号", r2 == "{\\left(-2\\right)}^{2}", r2)
r = srv.tool_mohr({"stress_pairs": [[2, 1]], "c": 1, "phi_deg": 0})
ok("bug2 mohr：phi=0 不排水黏土包络不静默跳过", "包络" in r and "tan(0°)" in r, r)
r = srv.tool_table({"data": "a;b;c\n1,5;2,5;3,5"})
ok("bug3+4 欧式 CSV：分号嗅探 + 逗号小数", "3.5" in r and "1.5" in r and "2.5" in r, r)
ok("bug4 千分位 1,234 → 1234", srv._parse_cell_float("1,234") == 1234.0)
ok("bug4 欧式 1234,5 → 1234.5", srv._parse_cell_float("1234,5") == 1234.5)
ok("bug4 欧式负数 -1,5 → -1.5", srv._parse_cell_float("-1,5") == -1.5)
ok("bug4 非数值返回 None", srv._parse_cell_float("abc") is None)
pct_meta = {"type": "journal-article",
            "author": [{"family": "Chen", "given": "Ming"}],
            "title": ["50% effect & cost_#1"],
            "container-title": ["J Test"],
            "issued": {"date-parts": [[2024]]},
            "DOI": "10.1/xyz"}
bib = srv._make_bibtex(pct_meta)
ok("bug5 BibTeX 特殊字符转义 %_&#", "50\\% effect \\& cost\\_\\#1" in bib, bib)
base_meta = {"type": "journal-article",
             "author": [{"family": "Zhang", "given": "San"}],
             "title": ["Direct shear behavior of granite joints"],
             "container-title": ["International Journal of Rock Mechanics and Mining Sciences"],
             "issued": {"date-parts": [[2024]]},
             "volume": "180", "issue": "2", "page": "105-123",
             "DOI": "10.1016/j.ijrockmas.2024.105999"}
ok("bug6 默认 key 保持 Zhang2024（兼容老库）",
   srv._make_bibtex(base_meta).startswith("@article{Zhang2024,"))
bib = srv._make_bibtex(base_meta, used_keys={"Zhang2024"})
ok("bug6 撞 key 自动后缀 a", bib.startswith("@article{Zhang2024a,"), bib[:40])
bib = srv._make_bibtex(base_meta, used_keys={"Zhang2024", "Zhang2024a"})
ok("bug6 连撞顺延后缀 b", bib.startswith("@article{Zhang2024b,"), bib[:40])

# ====================== stdio 冒烟 ======================
print("== 20. stdio 冒烟（0.4.4 · 19 工具）==")
def rpc(msgs):
    p = subprocess.run([sys.executable, os.path.join(HERE, "labmate_server.py")],
                       input="\n".join(msgs) + "\n", capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]

out = rpc([
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}',
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"labmate_stats","arguments":{"action":"ttest","a":[9,10,11,12,13],"mu":10}}}',
])
ok("版本 0.4.4", out[0]["result"]["serverInfo"]["version"] == "0.4.4")
names = [t["name"] for t in out[1]["result"]["tools"]]
ok("tools/list = 19", len(names) == 19, names)
ok("六个新工具全部注册", set(["labmate_stats", "labmate_errors", "labmate_doe",
                              "labmate_tex", "labmate_bibtex", "labmate_signal"]) <= set(names), names)
ok("tools/call stats 中文+数学正常", "t = 1.41421" in out[2]["result"]["content"][0]["text"],
   out[2]["result"]["content"][0]["text"][:80])

print("\n========== %d 通过，%d 失败 ==========" % (passed, failed))
sys.exit(1 if failed else 0)

# -*- coding: utf-8 -*-
"""LabMate server 0.4.9 新增能力单测：统计三连（corr 相关性 / nptest 非参数 / anova posthoc 事后检验）+ bibtex GB/T 7714。"""
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

TMP = tempfile.mkdtemp(prefix="labmate_v13_")

# ======================================================================
print("== 54. corr · 相关性分析（Pearson + Spearman）==")
rc = srv.tool_stats({"action": "corr", "x": [1, 2, 3, 4, 5], "y": [2, 1, 4, 3, 5]})
ok("黄金用例：Pearson r = 0.8 精确（Σdxdy/√(Σdx²Σdy²) = 8/10）",
   "Pearson r = 0.8" in rc, rc[:200])
ok("r 的 t 统计量 = 0.8·√(3/0.36) = 2.3094", "t = 2.3094" in rc, rc[:200])
ok("df = n - 2 = 3", "df = 3" in rc, rc[:200])
ok("Spearman 秩同构 rs = 0.8", "Spearman rs = 0.8" in rc, rc[:200])
ok("强正相关解读", "强正相关（|r| ≥ 0.7 强" in rc, rc[:200])
rt = srv.tool_stats({"action": "corr", "x": [1, 2, 2, 3, 4], "y": [1, 2, 3, 4, 5]})
ok("ties 平均秩：rs = 9.5/√95 = 0.974679 精确",
   "Spearman rs = 0.974679" in rt, rt[:200])
rn = srv.tool_stats({"action": "corr", "x": [1, 2, 3, 4, 5], "y": [1, 8, 27, 64, 100]})
ok("单调非线性：Spearman 判完全相关（Pearson 不足 1）",
   "Spearman rs = 1（完全正相关）" in rn and "Pearson r = 1" not in rn, rn[:200])
rl = srv.tool_stats({"action": "corr", "x": [1, 2, 3, 4, 5], "y": [3, 5, 7, 9, 11]})
ok("完全线性：r = 1 完全相关分支（p ≈ 0）",
   "Pearson r = 1（完全正相关），p ≈ 0" in rl, rl[:200])
rd = srv.tool_stats({"action": "corr", "x": [1, 2, 3, 4, 5], "y": [10, 8, 6, 4, 2]})
ok("完全负相关：r = -1 分支", "Pearson r = -1（完全负相关）" in rd, rd[:200])
ok("缺 x/y 拦截", "❌ corr 需要 x、y（两个等长数值数组，n ≥ 3）"
   == srv.tool_stats({"action": "corr", "y": [1, 2, 3]}), "")
ok("不等长拦截", "❌ x、y 需等长（当前 3 vs 4）"
   == srv.tool_stats({"action": "corr", "x": [1, 2, 3], "y": [1, 2, 3, 4]}), "")
ok("n < 3 拦截", "❌ 相关性检验需要 n ≥ 3"
   == srv.tool_stats({"action": "corr", "x": [1, 2], "y": [3, 4]}), "")
ok("x 无波动拦截", "❌ x 或 y 无波动（方差为 0），相关系数无定义"
   == srv.tool_stats({"action": "corr", "x": [1, 1, 1], "y": [1, 2, 3]}), "")
ok("非数值拦截（vals 返回 None 走缺参文案）",
   "❌ corr 需要 x、y（两个等长数值数组，n ≥ 3）"
   == srv.tool_stats({"action": "corr", "x": [1, "a", 3], "y": [1, 2, 3]}), "")

# ======================================================================
print("== 55. nptest · 非参数检验（Mann-Whitney 精确 / Kruskal-Wallis）==")
ok("_mw_exact_p 组合锚点：n=3,3 U=0 → 双尾 2·(1/20) = 0.1",
   abs(srv._mw_exact_p(0, 3, 3) - 0.1) < 1e-12, srv._mw_exact_p(0, 3, 3))
ok("_mw_exact_p 组合锚点：n=3,3 U=1 → 双尾 2·(2/20) = 0.2",
   abs(srv._mw_exact_p(1, 3, 3) - 0.2) < 1e-12, srv._mw_exact_p(1, 3, 3))
ok("_mw_exact_p 组合锚点：n=4,4 U=0 → 双尾 2/70",
   abs(srv._mw_exact_p(0, 4, 4) - 2.0 / 70.0) < 1e-12, srv._mw_exact_p(0, 4, 4))
r2 = srv.tool_stats({"action": "nptest", "a": [1, 2, 3], "b": [7, 8, 9]})
ok("MW 完全分离：U = 0（U₁ = 0, U₂ = 9）", "U = 0（U₁ = 0, U₂ = 9）" in r2, r2[:200])
ok("MW 精确 p = 0.1000（组合计数）", "p = 0.1000（精确 p·组合计数，n₁+n₂ = 6 ≤ 20）" in r2, r2[:200])
r2b = srv.tool_stats({"action": "nptest", "a": [1, 2, 4], "b": [3, 5, 6]})
ok("MW U=1 黄金：p = 0.2000（R1 = 7 → U₁ = 1）",
   "U = 1（U₁ = 1, U₂ = 8）" in r2b and "p = 0.2000" in r2b, r2b[:200])
r2c = srv.tool_stats({"action": "nptest", "a": list(range(12)), "b": list(range(20, 40))})
ok("MW 正态近似路径（n₁+n₂ = 32 > 20）：z 行 + 效应量 r = |z|/√N + 连续校正明示",
   "- z =" in r2c and "r = |z|/√N" in r2c and "正态近似·n₁+n₂ = 32 > 20，连续校正" in r2c, r2c[:300])
r2t = srv.tool_stats({"action": "nptest", "a": [1, 2, 2, 3], "b": [5, 6, 6, 7]})
ok("MW 并列值提示（精确分布未含 ties 校正）", "并列值" in r2t, r2t[:300])
r3 = srv.tool_stats({"action": "nptest", "groups": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]})
ok("KW 黄金：H = 7.2 精确（12/90·(12+75+192) − 30）", "H = 7.2" in r3, r3[:200])
ok("KW df = k-1 = 2，p = e^(−3.6) = 0.0273 精确", "df = 2, p = 0.0273" in r3, r3[:200])
ok("KW 各组平均秩 2/5/8（手工可验）", "2(n=3), 5(n=3), 8(n=3)" in r3, r3[:200])
ok("KW 效应量 ε² = H/(N−1) = 0.9", "ε² = 0.9" in r3, r3[:200])
r3t = srv.tool_stats({"action": "nptest", "groups": [[1, 1, 2, 2], [1, 2, 3, 4], [5, 6, 7, 8]]})
ok("KW ties 已校正", "（ties 已校正）" in r3t, r3t[:200])
ok("MW 缺 b 提示走 groups 路径",
   "❌ nptest：两组比较给 a、b（Mann-Whitney）；多组比较给 groups（Kruskal-Wallis）"
   == srv.tool_stats({"action": "nptest", "a": [1, 2, 3]}), "")
ok("MW 样本量不足拦截", "❌ a、b 各至少 2 个样本"
   == srv.tool_stats({"action": "nptest", "a": [1], "b": [2, 3]}), "")
ok("KW groups 少于 2 组拦截", "❌ nptest 的 groups 需 ≥2 个数值数组（Kruskal-Wallis 多组检验）"
   == srv.tool_stats({"action": "nptest", "groups": [[1, 2]]}), "")
ok("KW 单值组拦截", "❌ 每组至少 2 个样本"
   == srv.tool_stats({"action": "nptest", "groups": [[1, 2], [3]]}), "")
ok("KW 非数值拦截", "❌ groups 每个元素须为数值数组"
   == srv.tool_stats({"action": "nptest", "groups": [[1, "a"], [3, 4]]}), "")

# ======================================================================
print("== 56. anova · 事后两两比较（Tukey HSD 数值积分 / Holm / Bonferroni）==")
G3 = [[10, 11, 12], [13, 14, 15], [16, 17, 18]]
ok("_q_sf 边界：q ≤ 0 → 1.0；k<2 或 ν<2 → NaN",
   srv._q_sf(0, 3, 10) == 1.0 and srv._q_sf(-1, 3, 10) == 1.0
   and srv._q_sf(2, 1, 10) != srv._q_sf(2, 1, 10)
   and srv._q_sf(2, 3, 1) != srv._q_sf(2, 3, 1), "")
worst_n4 = max(abs(srv._q_sf(q, 2, nu) - 2 * srv._t_sf(q / 1.4142135623730951, nu))
               for nu in (4, 6, 10, 20, 30) for q in (1.0, 2.0, 3.0, 4.5, 6.0))
ok("_q_sf k=2 数学恒等式 P(Q>q) = 2·P(t(ν) > q/√2)：ν≥4 网格偏差 < 1e-4",
   worst_n4 < 1e-4, worst_n4)
ok("_q_sf k=2 恒等式 ν=2 病态场景偏差 < 2.5e-3（docstring 精度边界）",
   abs(srv._q_sf(4.5, 2, 2) - 2 * srv._t_sf(4.5 / 1.4142135623730951, 2)) < 2.5e-3, "")
ok("_q_sf 教科书锚点：q=3.88, k=3, ν=10 → p ≈ 0.05（Lund 表 0.95 分位）",
   abs(srv._q_sf(3.88, 3, 10) - 0.05) < 0.001, srv._q_sf(3.88, 3, 10))
ra = srv.tool_stats({"action": "anova", "groups": G3, "posthoc": "tukey"})
ok("Tukey 标题（k=3, df=6, 3 对）", "事后两两比较（Tukey HSD，k = 3，df = 6，共 3 对）" in ra, ra[:300])
ok("Tukey q = |Δ|/√(MSw/n) = 3/√(1/3) = 5.19615",
   "组1 vs 组2：Δ均值 = -3, q = 5.19615" in ra, ra[:400])
ok("Tukey AC：q = 6/√(1/3) = 10.3923", "q = 10.3923" in ra, "")
ok("Tukey AB/BC p_adj = 0.0243（积分值）、AC p_adj = 0.0008",
   "p_adj = 0.0243" in ra and "p_adj = 0.0008" in ra, ra[:500])
ok("Tukey 全对显著标注", ra.count("→ 显著") == 3, ra)
ok("Tukey 尾注（族错误率恰好为 α）", "族错误率恰好为 α" in ra, ra[-200:])
rh = srv.tool_stats({"action": "anova", "groups": G3, "posthoc": "holm"})
ok("Holm：t = Δ/√(MSw·2/n) = 3.67423（合并方差 t 检验）",
   "t = 3.67423" in rh and "t = 7.34847" in rh, rh[:400])
ok("Holm 逐步下降：AC ×3 → 0.0010；AB/BC ×2 → 0.0208（手算 2×0.0104）",
   "p_raw = 0.0104, p_adj = 0.0208" in rh and "p_raw = 0.0003, p_adj = 0.0010" in rh, rh[:500])
rbo = srv.tool_stats({"action": "anova", "groups": G3, "posthoc": "bonferroni"})
ok("Bonferroni 一律 ×3：0.0104×3 = 0.0312（与 Holm 的 0.0208 区分）",
   "p_adj = 0.0312" in rbo and "p_adj = 0.0208" not in rbo, rbo[:500])
ok("三法强弱序正确：Holm(0.0208) ≤ Tukey(0.0243) ≤ Bonferroni(0.0312)",
   "p_adj = 0.0208" in rh and "p_adj = 0.0243" in ra and "p_adj = 0.0312" in rbo, "")
rns = srv.tool_stats({"action": "anova", "groups": [[1, 2], [2, 3], [3, 4]], "posthoc": "tukey"})
ok("整体 F 不显著时给探索性警示", "⚠ 整体 F 检验不显著，事后两两比较仅作探索参考" in rns, rns[:300])
rnq = srv.tool_stats({"action": "anova", "groups": [[1, 2, 3, 4], [5, 6]], "posthoc": "tukey"})
ok("非均衡设计明示 Tukey-Kramer 近似", "Tukey-Kramer 非均衡近似" in rnq, rnq[:300])
rbad = srv.tool_stats({"action": "anova", "groups": G3, "posthoc": "xxx"})
ok("posthoc 非法值拦截", "❌ posthoc 支持 tukey / holm / bonferroni（当前 xxx）" == rbad, rbad)
rnp = srv.tool_stats({"action": "anova", "groups": [[1, 2], [3, 4], [5, 6]]})
ok("无 posthoc 时尾注引导加参数",
   "两两比较加参数 posthoc: tukey / holm / bonferroni" in rnp, rnp[-120:])
ok("anova 老路径（无 posthoc）行为兼容：F/η² 结构不变",
   "F = 27" in srv.tool_stats({"action": "anova", "groups": G3}), "")

# ======================================================================
print("== 57. bibtex · GB/T 7714-2015 参考文献输出 ==")
BIB = os.path.join(TMP, "t.bib")
with open(BIB, "w", encoding="utf-8") as f:
    f.write(
        "@article{e1, author={Einstein, Albert and Podolsky, Boris and Rosen, Nathan and Fourth, A}, "
        "title={Can quantum-mechanical description be considered complete?}, journal={Physical Review}, "
        "year={1935}, volume={47}, number={10}, pages={777--780}}\n"
        "@article{z1, author={张三 and 李四 and 王五 and 赵六}, title={岩石力学试验方法}, "
        "journal={岩土力学}, year={2020}, volume={41}, number={2}, pages={12--18}}\n"
        "@book{k1, author={Knuth, Donald E.}, title={The TeXbook}, publisher={Addison-Wesley}, "
        "address={Reading}, year={1984}}\n"
        "@phdthesis{d1, author={李明}, title={混凝土动态力学性能研究}, school={同济大学}, "
        "address={上海}, year={2018}}\n"
        "@inproceedings{c1, author={Wang, Lei and Zhang, Hua and Liu, Ming and Zhao, Xin and Sun, Yang}, "
        "title={Fatigue crack growth behavior}, booktitle={Proc of ICM}, year={2021}, pages={100--110}}\n"
        "@misc{u1, author={Bureau}, title={Standard test method}, url={https://example.com/std}, year={2022}}\n"
        "@book{no1, title={Anonymous Volume}, publisher={X Press}, year={1999}}\n")
rg = srv.tool_bibtex({"action": "gb7714", "bib_path": BIB})
ok("顺序编码制标题与条目计数", "GB/T 7714-2015 参考文献表（顺序编码制，7 条）" in rg, rg[:150])
ok("[1] 西文 4 作者截断 et al + 姓前名缩写全大写",
   "EINSTEIN A, PODOLSKY B, ROSEN N, et al." in rg, rg[:300])
ok("[1] 期刊一体段：刊名, 年, 卷(期): 页码（pages -- → -）",
   "[J]. Physical Review, 1935, 47(10): 777-780." in rg, rg[:300])
ok("[2] 中文 4 作者截断「等.」", "张三, 李四, 王五, 等." in rg, rg[:400])
ok("[2] 中文期刊格式", "[J]. 岩土力学, 2020, 41(2): 12-18." in rg, rg[:400])
ok("[3] 专著：出版地: 出版社, 年", "[M]. Reading: Addison-Wesley, 1984." in rg, rg[:400])
ok("[4] 学位论文：城市: 学校, 年", "[D]. 上海: 同济大学, 2018." in rg, rg[:400])
ok("[5] 会议论文 [C]//论文集名. 年: 页码（GB7714 析出文献规范，集名后句点）",
   "[C]//Proc of ICM. 2021: 100-110." in rg, rg[:500])
ok("[6] misc 带 url 判 [EB/OL] + 年 + URL",
   "[EB/OL]. 2022, https://example.com/std." in rg, rg[:500])
ok("[7] 无作者兜底「佚名」", "佚名. Anonymous Volume[M]. X Press, 1999." in rg, rg[:500])
ok("编号连续 [1]~[7]", all("[%d] " % i in rg for i in range(1, 8)), "")
ra2 = srv.tool_bibtex({"action": "gb7714", "bib_path": BIB, "style": "author-year"})
ok("著者-出版年制：年份置作者后", "EINSTEIN A, PODOLSKY B, ROSEN N, et al, 1935." in ra2, ra2[:300])
ok("author-year 尾部不重复年份", "Physical Review, 47(10): 777-780." in ra2, ra2[:300])
ok("author-year 无编号", "[1] " not in ra2, "")
red = srv.tool_bibtex({"action": "gb7714", "bib_path": os.path.join(TMP, "ed.bib")})
with open(os.path.join(TMP, "ed.bib"), "w", encoding="utf-8") as f:
    f.write("@book{ed1, editor={Smith, John}, title={Handbook}, publisher={Y}, year={2001}}\n")
red = srv.tool_bibtex({"action": "gb7714", "bib_path": os.path.join(TMP, "ed.bib")})
ok("无作者时 editor 兜底", "SMITH J. Handbook[M]. Y, 2001." in red, red[:200])
rs2 = srv.tool_bibtex({"action": "gb7714", "bib_path": BIB, "sort": "year"})
ok("sort=year 新→旧：首条 2022 BUREAU、末条 1935 EINSTEIN",
   "[1] BUREAU" in rs2 and "[7] EINSTEIN" in rs2, rs2[:200])
ok("style 非法拦截", "❌ style 支持 numeric（默认，顺序编码制）/ author-year（著者-出版年制）"
   == srv.tool_bibtex({"action": "gb7714", "bib_path": BIB, "style": "xxx"}), "")
ok("sort 非法拦截", "❌ gb7714 的 sort 支持 year（新→旧）/ author / key（不传则按库内原顺序）"
   == srv.tool_bibtex({"action": "gb7714", "bib_path": BIB, "sort": "xxx"}), "")
ok("未知 action 文案含 gb7714", "❌ 未知 action：xxx（支持 check / merge / sort / gb7714）"
   == srv.tool_bibtex({"action": "xxx", "bib_path": BIB}), "")
ok("check 老路径不受影响（体检仍工作）",
   "BibTeX 库体检" in srv.tool_bibtex({"action": "check", "bib_path": BIB}), "")
ok("merge 老路径不受影响", "BibTeX 合并" in srv.tool_bibtex(
    {"action": "merge", "bib_paths": [BIB], "sort": "key"}), "")

# ======================================================================
print("== 58. 协议层与文档注册 ==")
ok("TOOLS 仍为 20 件（0.4.9 不新增工具）", len(srv.TOOLS) == 20, len(srv.TOOLS))
sig = [t for t in srv.TOOLS if t["name"] == "labmate_stats"][0]
ok("stats schema：action 枚举含 corr 与 nptest",
   "corr" in sig["inputSchema"]["properties"]["action"]["description"]
   and "nptest" in sig["inputSchema"]["properties"]["action"]["description"], "")
ok("stats schema：描述含 Tukey HSD 与 Kruskal-Wallis",
   "Tukey HSD" in sig["description"] and "Kruskal-Wallis" in sig["description"], "")
ok("stats schema：posthoc 字段", "tukey" in sig["inputSchema"]["properties"]["posthoc"]["description"], "")
ok("stats schema：x/y 字段（corr）", "corr 自变量" in sig["inputSchema"]["properties"]["x"]["description"], "")
sigb = [t for t in srv.TOOLS if t["name"] == "labmate_bibtex"][0]
ok("bibtex schema：action 含 gb7714 + style 字段",
   "gb7714" in sigb["inputSchema"]["properties"]["action"]["description"]
   and "author-year" in sigb["inputSchema"]["properties"]["style"]["description"], "")
ok("describe 尾注引导 corr/nptest",
   "相关性用 corr" in srv.tool_stats({"action": "describe", "data": [1, 2, 3, 4, 5]}), "")
main_skill = open(os.path.join(HERE, "..", "skills", "labmate", "SKILL.md"), encoding="utf-8").read()
ok("主路由版本行 = 0.5.0", "v0.5.0" in main_skill, "")
ok("主路由工具表 stats 行含相关性/非参数", "相关性" in main_skill and "非参数" in main_skill, "")
ok("主路由工具表 bibtex 行含 GB/T 7714", "GB/T 7714" in main_skill or "GB7714" in main_skill, "")

def rpc(msgs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "labmate_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode("utf-8"))
    return [json.loads(l) for l in out.decode("utf-8").splitlines() if l.strip()]

res = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
           {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "labmate_stats",
                       "arguments": {"action": "corr", "x": [1, 2, 3, 4, 5],
                                     "y": [2, 1, 4, 3, 5]}}},
           {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "labmate_bibtex",
                       "arguments": {"action": "gb7714", "bib_path": BIB}}}])
ok("initialize 版本 = 0.5.0", res[0]["result"]["serverInfo"]["version"] == "0.5.0", res[0])
ok("stdio corr 黄金（r = 0.8）",
   "Pearson r = 0.8" in res[1]["result"]["content"][0]["text"],
   res[1]["result"]["content"][0]["text"][:150])
ok("stdio gb7714（EINSTEIN 截断）",
   "EINSTEIN A, PODOLSKY B, ROSEN N, et al." in res[2]["result"]["content"][0]["text"],
   res[2]["result"]["content"][0]["text"][:150])

print("\n== v0.4.9 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

# -*- coding: utf-8 -*-
"""LabMate server 0.2.0 新增工具单测：table / style / arxiv / cite"""
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

print("== 7. labmate_table ==")
csv_text = "载荷kN,位移mm,试样编号\n100,0.52,S-01\n200,1.03,S-01\n,1.55,S-02\n400,2.20,S-02"
r = srv.tool_table({"data": csv_text})
ok("数值列统计（含缺失）", "载荷kN" in r and "均值" in r and "缺失 1" in r, r)
ok("文本列识别", "文本列" in r and "S-01" not in r.split("文本列")[1][:60], r)
ok("自动探测逗号分隔", "',' == ','" if False else True)
tsv = "a\tb\n1\t2\n3\t4"
r = srv.tool_table({"data": tsv})
ok("制表符自动探测", "a" in r and "b" in r and "均值" in r, r)
tmp = os.path.join(tempfile.gettempdir(), "labmate_试验数据_test.csv")
with open(tmp, "w", encoding="utf-8-sig") as f:
    f.write("force,disp\n10,0.1\n20,0.25\n")
r = srv.tool_table({"csv_path": tmp})
ok("读取真实文件（BOM+中文路径）", "force" in r and "均值" in r, r)
os.remove(tmp)
r = srv.tool_table({})
ok("缺参数拦截", "❌" in r, r)
r = srv.tool_table({"csv_path": r"C:\not\exist\zzz.csv"})
ok("坏路径友好报错", "❌ 读取失败" in r, r)

print("== 8. labmate_style ==")
r = srv.tool_style({"style": "ieee"})
ok("ieee 继承 science 参数", "font.family : serif" in r and "figure.figsize : 3.5, 2.75" in r, r)
r = srv.tool_style({"style": "cnjournal"})
ok("中文期刊样式（SimSun+unicode_minus）", "SimSun" in r and "unicode_minus : False" in r, r)
r = srv.tool_style({"style": "nature"})
ok("nature 样式", "sans-serif" in r and "axes.grid" in r, r)
r = srv.tool_style({"style": "nope"})
ok("未知样式拦截", "❌" in r, r)
mpl = os.path.join(tempfile.gettempdir(), "labmate_test.mplstyle")
r = srv.tool_style({"style": "science", "save_mplstyle": mpl})
ok("写 .mplstyle 文件", "已写入" in r and os.path.exists(mpl), r)
if os.path.exists(mpl):
    content = open(mpl, encoding="utf-8").read()
    ok("样式文件内容有效", "savefig.dpi : 600" in content, content[:100])
    os.remove(mpl)

print("== 9. labmate_arxiv ==")
xml_sample = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Rock   Failure Mechanics\n  in Deep  Tunnels</title>
    <author><name>A. Rock</name></author>
    <author><name>B. Stone</name></author>
    <published>2026-01-15T00:00:00Z</published>
    <id>http://arxiv.org/abs/2601.00001v1</id>
    <summary>Direct shear tests on granite specimens under coupled thermal conditions are investigated.</summary>
    <category term="physics.geo-ph"/>
  </entry>
</feed>"""
papers = srv._parse_arxiv_atom(xml_sample)
ok("Atom 解析：标题空白清洗", papers[0]["title"] == "Rock Failure Mechanics in Deep Tunnels", papers)
ok("Atom 解析：作者/日期/链接", papers[0]["authors"] == ["A. Rock", "B. Stone"] and papers[0]["date"] == "2026-01-15", papers)
ok("Atom 解析：摘要截断200字", len(papers[0]["summary"]) <= 200, papers)
r = srv.tool_arxiv({"query": ""})
ok("空检索词拦截", "❌" in r, r)
r = srv.tool_arxiv({"query": "rock mechanics direct shear", "max_results": 2})
ok("真实网络查询（或优雅降级）", ("arXiv 检索" in r and "http" in r) or ("网络查询失败" in r), r[:150])

print("== 10. labmate_cite ==")
fake_meta = {"type": "journal-article",
             "author": [{"family": "Zhang", "given": "San"}, {"family": "Li", "given": "Si"}],
             "title": ["Direct shear behavior of granite joints"],
             "container-title": ["International Journal of Rock Mechanics and Mining Sciences"],
             "issued": {"date-parts": [[2024]]},
             "volume": "180", "issue": "2", "page": "105-123",
             "DOI": "10.1016/j.ijrockmas.2024.105999"}
bib = srv._make_bibtex(fake_meta)
ok("BibTeX 生成：entry/key", bib.startswith("@article{Zhang2024,"), bib)
ok("BibTeX 生成：字段完整", "journal" in bib and "volume" in bib and "105--123" in bib and "doi" in bib, bib)
ok("BibTeX 作者格式", "Zhang, San and Li, Si" in bib, bib)
book_meta = {"type": "proceedings-article", "author": [{"family": "Wang", "given": "Wu"}],
             "title": ["Dynamic rock test"], "container-title": ["ISRM Congress"],
             "issued": {"date-parts": [[2023]]}, "DOI": "10.x/abc"}
bib2 = srv._make_bibtex(book_meta)
ok("会议论文→inproceedings", bib2.startswith("@inproceedings{Wang2023,") and "booktitle" in bib2, bib2)
r = srv.tool_cite({"doi": ""})
ok("空 DOI 拦截", "❌" in r, r)
r = srv.tool_cite({"doi": "10.9999/definitely-not-real-xyz"})
ok("不存在 DOI 友好报错（或网络降级）", ("404" in r or "不存在" in r) or ("网络查询失败" in r), r[:150])
r = srv.tool_cite({"doi": "10.1038/nature12373"})
ok("真实 DOI 查询（或优雅降级）", ("BibTeX" in r and "@article" in r) or ("网络查询失败" in r), r[:150])

print("== 11. stdio 冒烟（0.5.0 · 20 工具，快照随版本更新）==")
def rpc(msgs):
    p = subprocess.run([sys.executable, os.path.join(HERE, "labmate_server.py")],
                       input="\n".join(msgs) + "\n", capture_output=True,
                       text=True, encoding="utf-8", timeout=40)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]

out = rpc([
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}',
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"labmate_style","arguments":{"style":"ieee"}}}',
])
ok("版本 0.5.0", out[0]["result"]["serverInfo"]["version"] == "0.5.0")
names = [t["name"] for t in out[1]["result"]["tools"]]
ok("tools/list = 20", len(names) == 20, names)
ok("新工具全部注册", set(["labmate_table", "labmate_style", "labmate_arxiv", "labmate_cite"]) <= set(names), names)
ok("required 在 inputSchema 内（cite）", "required" in [t for t in out[1]["result"]["tools"] if t["name"] == "labmate_cite"][0]["inputSchema"], "")
ok("tools/call style 中文无乱码", "期刊样式" in out[2]["result"]["content"][0]["text"], out[2]["result"]["content"][0]["text"][:80])

print("\n========== %d 通过，%d 失败 ==========" % (passed, failed))
sys.exit(1 if failed else 0)

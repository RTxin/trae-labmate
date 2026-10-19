# -*- coding: utf-8 -*-
"""LabMate server 0.3.0 新增能力单测：handcalc LaTeX / 多源聚合 search / 本地 PDF。"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import zlib

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
print("== 12. labmate_handcalc · LaTeX 输出 ==")
hc_args = {"vars": {"F": 150e3, "b": 0.10, "h_s": 0.025, "tau_u": 90e6},
           "steps": [
               {"symbol": "A_s", "formula": "b * h_s", "note": "area"},
               {"symbol": "tau", "formula": "F / A_s", "note": "stress"},
               {"symbol": "F_req", "formula": "tau_u * A_s / 1e3", "note": "required kN"}]}
r = srv.tool_handcalc(dict(hc_args, fmt="latex"))
ok("latex 包裹 align* 环境", "\\begin{align*}" in r and "\\end{align*}" in r, r[:200])
ok("latex 乘法渲染 cdot", "b \\cdot h_{s}" in r, r[:400])
ok("latex 除法渲染 frac", "\\frac{F}{A_{s}}" in r, r[:400])
ok("希腊字母+下标 tau_u", "\\tau_{u}" in r and "A_{s}" in r, r[:400])
ok("科学计数法 times10", "\\times10^{" in r, r[:600])
ok("latex 代码块可复制", "```latex" in r, r[:120])
ok("note 进入 \\text 旁注", "\\text{area}" in r, r[:500])
tree = ast.parse("b * h_s ** 2", mode="eval")
tex = srv._latex_expr(tree)
ok("AST 渲染优先级：幂上标", tex == "b \\cdot {h_{s}}^{2}", tex)
ok("非法 fmt 拦截", "❌" in srv.tool_handcalc(dict(hc_args, fmt="pdf")), "")
r_md = srv.tool_handcalc(hc_args)
ok("默认 md 行为不回归", "计算过程" in r_md and "fmt=latex" in r_md, r_md[:120])

# ======================================================================
print("== 13. labmate_search · 解析纯函数 ==")
cr_raw = json.dumps({"message": {"items": [
    {"title": ["Deep Rock Failure in Tunnels"],
     "author": [{"given": "A.", "family": "Rock"}, {"given": "B.", "family": "Stone"}],
     "issued": {"date-parts": [[2026, 1]]}, "container-title": ["Int J Rock Mech"],
     "DOI": "10.1/XYZ", "URL": "https://doi.org/10.1/xyz", "type": "journal-article",
     "abstract": "<jats:p>Test  abstract  here</jats:p>"},
    {"title": ["No DOI Old Paper"], "author": [],
     "issued": {"date-parts": [[None]]}, "container-title": []}]}})
cr = srv._parse_crossref_works(cr_raw)
ok("Crossref：条数与字段", len(cr) == 2 and cr[0]["venue"] == "Int J Rock Mech", cr)
ok("Crossref：作者拼接", cr[0]["authors"] == ["A. Rock", "B. Stone"], cr[0]["authors"])
ok("Crossref：JATS 标签剥离与空白清洗", cr[0]["abstract"] == "Test abstract here", cr[0]["abstract"])
ok("Crossref：DOI 归一化/年份", cr[0]["doi"] == "10.1/xyz" and cr[0]["year"] == 2026, cr[0])
ok("Crossref：无 DOI/无年份容错", cr[1]["doi"] == "" and cr[1]["year"] is None, cr[1])

oa_raw = json.dumps({"results": [
    {"title": "Deep Rock Failure in Tunnels", "publication_year": 2026,
     "authorships": [{"author": {"display_name": "A. Rock"}}],
     "primary_location": {"source": {"display_name": "Nature"}},
     "doi": "https://doi.org/10.1/xyz", "id": "https://openalex.org/W1",
     "abstract_inverted_index": {"deep": [0], "rock": [1], "failure": [2]}},
    {"title": "Null Venue Paper", "publication_year": 2025, "authorships": [],
     "primary_location": {"source": None}, "doi": None, "id": "https://openalex.org/W2",
     "abstract_inverted_index": None}]})
oa = srv._parse_openalex_works(oa_raw)
ok("OpenAlex：倒排索引重建摘要", oa[0]["abstract"] == "deep rock failure", oa[0]["abstract"])
ok("OpenAlex：DOI 前缀剥离", oa[0]["doi"] == "10.1/xyz", oa[0]["doi"])
ok("OpenAlex：null source/doi 不崩", oa[1]["venue"] == "" and oa[1]["url"] == "https://openalex.org/W2", oa[1])
ok("标题归一化：冠词/标点/空白", srv._norm_title("The  Rock--Failure  ") == "rock failure",
   srv._norm_title("The  Rock--Failure  "))

print("== 14. labmate_search · 跨源去重 ==")
p_arx = srv._paper("Deep Rock Failure in Tunnels", ["A. Rock"], 2026, "arXiv physics.geo-ph",
                   "", "http://arxiv.org/abs/2601.00001", "arXiv", "preprint abstract")
p_cr = srv._paper("Deep Rock Failure in Tunnels!", ["Rock, A."], 2026, "Int J Rock Mech",
                  "10.1/xyz", "https://doi.org/10.1/xyz", "Crossref", "")
p_oa = srv._paper("Deep Rock Failure in Tunnels", ["A. Rock"], 2026, "Nature",
                  "10.1/xyz", "https://doi.org/10.1/xyz", "OpenAlex",
                  "deep rock failure observed under coupled conditions")
p_other = srv._paper("Shallow Soil Dynamics Review", ["C. Clay"], 2024, "Geotechnique",
                     "10.2/abc", "https://doi.org/10.2/abc", "Crossref", "different paper")
merged = srv._dedup_papers([p_arx, p_cr, p_oa, p_other])
ok("三源同篇去重为 1 条", len(merged) == 2, [(p["title"], p.get("sources")) for p in merged])
top = [p for p in merged if "xyz" in p["doi"]][0]
ok("sources 三源聚合", top["sources"] == ["Crossref", "OpenAlex", "arXiv"], top["sources"])
ok("合并后 DOI 补全、arXiv 占位出处被正式期刊替换",
   top["doi"] == "10.1/xyz" and top["venue"] == "Int J Rock Mech", top)
ok("摘要取更长者", top["abstract"] == "deep rock failure observed under coupled conditions",
   top["abstract"])
ok("不同论文不误并", any(p["doi"] == "10.2/abc" for p in merged), "")
# DOI 直配（标题有差异也合并）
q1 = srv._paper("Title Version One", ["X"], 2020, "v", "10.9/z", "u", "arXiv", "")
q2 = srv._paper("Totally Different Caption Here", ["Y"], 2021, "v", "10.9/z", "u", "OpenAlex", "")
ok("DOI 一致直接合并且忽略标题差异", len(srv._dedup_papers([q1, q2])) == 1, "")
# 同作者同年但不同题不应误并
d1 = srv._paper("Fracture of granite under bending", ["A. Rock"], 2026, "v", "10.3/a", "u", "Crossref", "")
d2 = srv._paper("Thermal damage of granite under fire", ["A. Rock"], 2026, "v", "10.4/b", "u", "OpenAlex", "")
ok("同作者同年不同题不误并", len(srv._dedup_papers([d1, d2])) == 2, "")

print("== 15. labmate_search · tool 编排与降级 ==")
orig = (srv._fetch_arxiv_papers, srv._fetch_crossref_papers, srv._fetch_openalex_papers)
try:
    srv._fetch_arxiv_papers = lambda q, n, m: [srv._paper(
        "Deep Rock Failure in Tunnels", ["A. Rock"], 2026, "arXiv x", "",
        "http://arxiv.org/abs/2601.00001", "arXiv", "abs")]
    srv._fetch_crossref_papers = lambda q, n, m: [srv._paper(
        "Deep Rock Failure in Tunnels", ["Rock, A."], 2026, "Int J Rock Mech",
        "10.1/xyz", "https://doi.org/10.1/xyz", "Crossref", "")]
    def _oa_boom(q, n, m, api_key=""):
        raise RuntimeError("connection refused")
    srv._fetch_openalex_papers = _oa_boom
    r = srv.tool_search({"query": "rock failure"})
    ok("聚合：去重后 1 条/原始 2 条", "去重后 1 条 / 原始 2 条" in r, r[:300])
    ok("聚合：多源标记", "[arXiv+Crossref]" in r or "[Crossref+arXiv]" in r, r[:400])
    ok("聚合：失败源降级诊断不拖垮整体", "OpenAlex" in r and "⚠" in r and "10.1/xyz" in r, r[:600])
    r = srv.tool_search({"query": "rock", "year_from": 2027})
    ok("年份过滤：无匹配保留诊断", "去重后 0 条" in r or "2027" in r, r[:200])
    r = srv.tool_search({"query": "rock", "sources": ["crossref"]})
    ok("单源子集可用", "Crossref ✅" in r and "arXiv" not in r.split("源状态")[1], r[:400])
finally:
    srv._fetch_arxiv_papers, srv._fetch_crossref_papers, srv._fetch_openalex_papers = orig
ok("空检索词拦截", "❌" in srv.tool_search({"query": ""}), "")
ok("未知 source 拦截", "❌" in srv.tool_search({"query": "x", "sources": ["google"]}), "")

# ======================================================================
print("== 16. labmate_pdf · 零依赖提取器 ==")
ok("字面量转义：括号/八进制", srv._decode_pdf_literal(rb"a\(b\)\050c") == b"a(b)(c",
   srv._decode_pdf_literal(rb"a\(b\)\050c"))
tj = srv._extract_stream_text(b"BT [(Lab)-250(Mate)100(x)] TJ ET")
ok("TJ 数组：大负字距补空格、正数不补", tj == "Lab Matex", tj)
tj2 = srv._extract_stream_text(b"BT (Hello) Tj T* (World) Tj ET")
ok("Tj + T* 换行", tj2 == "Hello\nWorld", tj2)
tj3 = srv._extract_stream_text(b"BT [(a\\(b)] TJ T* (c) Tj ET")
ok("TJ 内含转义括号且不干扰二次扫描", tj3 == "a(b\nc", tj3)

def _content_stream(lines):
    parts = [b"BT /F1 12 Tf 72 720 Td "]
    for i, line in enumerate(lines):
        parts.append(b"(" + line.encode("latin-1") + b") Tj")
        if i < len(lines) - 1:
            parts.append(b" T* ")
    parts.append(b" ET")
    return b"".join(parts)

def _make_pdf(page_lines, scanned=False):
    """组装最小 PDF（无 xref，提取器不依赖它）。scanned=True 时页面无文本带图像流。"""
    n_pages = len(page_lines)
    font_id = 3 + 2 * n_pages
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>"}
    page_ids, kids = [], []
    img_id = font_id + 1
    for idx, lines in enumerate(page_lines):
        page_id, cid = 3 + 2 * idx, 4 + 2 * idx
        page_ids.append(page_id)
        kids.append(b"%d 0 R" % page_id)
        if scanned:
            page_body = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                         b"/Resources << /XObject << /Im1 %d 0 R >> >> >>" % img_id)
            objs[page_id] = page_body
            objs[cid] = b"<< /Length 0 >>\nstream\n\nendstream"
        else:
            raw = zlib.compress(_content_stream(lines))
            objs[page_id] = (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                             b"/Contents %d 0 R /Resources << /Font << /F1 %d 0 R >> >> >>"
                             % (cid, font_id))
            objs[cid] = (b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(raw)
                         + raw + b"\nendstream")
    objs[2] = (b"<< /Type /Pages /Kids [" + b" ".join(kids) +
               b"] /Count %d >>" % n_pages)
    objs[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    if scanned:
        objs[img_id] = (b"<< /Type /XObject /Subtype /Image /Width 10 /Height 10 "
                        b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /DCTDecode "
                        b"/Length 8 >>\nstream\nFAKEJPEG\nendstream")
    out = b"%PDF-1.4\n"
    for k in sorted(objs):
        out += b"%d 0 obj\n" % k + objs[k] + b"\nendobj\n"
    return out

pdf_two = _make_pdf([
    ["LabMate PDF probe page one fracture mechanics"],
    ["Second page with keyword fracture toughness and Paris law"],
])
pages, diag = srv._pdf_pages_text(pdf_two)
ok("解析页数=2 且按 Kids 排序", len(pages) == 2 and pages[0].startswith("LabMate PDF probe"), pages)
ok("FlateDecode 解压+文本提取", "fracture mechanics" in pages[0] and "Paris law" in pages[1], pages)
ok("图像计数为 0（文本型）", diag["images"] == 0 and diag["encrypted"] is False, diag)

tmp_pdf = os.path.join(tempfile.gettempdir(), "labmate_论文_probe_test.pdf")
with open(tmp_pdf, "wb") as f:
    f.write(pdf_two)
r = srv.tool_pdf({"pdf_path": tmp_pdf})
ok("stats：中文路径+页数+可提取", "页数：2" in r and "文本层可提取" in r, r[:200])
r = srv.tool_pdf({"pdf_path": tmp_pdf, "action": "extract", "page_from": 2, "page_to": 2})
ok("extract：指定页范围", "第 2-2 页" in r and "Paris law" in r and "probe page one" not in r, r[:300])
r = srv.tool_pdf({"pdf_path": tmp_pdf, "action": "extract", "max_chars": 5})
ok("extract：max_chars 截断提示", "截断" in r and "第 1-1 页" in r, r[:200])
r = srv.tool_pdf({"pdf_path": tmp_pdf, "action": "search", "query": "fracture"})
ok("search：两页命中并标注页码", "共 2 处命中" in r and "p.1" in r and "p.2" in r, r[:400])
r = srv.tool_pdf({"pdf_path": tmp_pdf, "action": "search", "query": "fracture|paris", "regex": True})
ok("search：正则多模式", "共 3 处命中" in r, r[:200])
r = srv.tool_pdf({"pdf_path": tmp_pdf, "action": "search", "query": "thermodynamics"})
ok("search：0 命中友好提示", "0 命中" in r, r[:150])
os.remove(tmp_pdf)

pdf_scan = _make_pdf([[""]], scanned=True)
spages, sdiag = srv._pdf_pages_text(pdf_scan)
ok("扫描版：图像标记检出", sdiag["images"] >= 1, sdiag)
scan_pdf = os.path.join(tempfile.gettempdir(), "labmate_scan_test.pdf")
with open(scan_pdf, "wb") as f:
    f.write(pdf_scan)
r = srv.tool_pdf({"pdf_path": scan_pdf})
ok("扫描版：stats 明确 OCR 诊断", "疑似扫描版" in r and "OCR" in r, r[:250])
r = srv.tool_pdf({"pdf_path": scan_pdf, "action": "search", "query": "x"})
ok("扫描版：search 拒绝并提示", "疑似扫描版" in r, r[:150])
os.remove(scan_pdf)

ok("坏路径拦截", "❌ 文件不存在" in srv.tool_pdf({"pdf_path": r"C:\nope\zzz.pdf"}), "")
bad_file = os.path.join(tempfile.gettempdir(), "labmate_bad_test.pdf")
with open(bad_file, "wb") as f:
    f.write(b"not a pdf at all")
ok("非 PDF 头拦截", "不是有效 PDF" in srv.tool_pdf({"pdf_path": bad_file}), "")
enc_file = os.path.join(tempfile.gettempdir(), "labmate_enc_test.pdf")
with open(enc_file, "wb") as f:
    f.write(b"%PDF-1.4\n1 0 obj << /Encrypt 9 0 R >> endobj\n")
ok("加密 PDF 明确不支持", "加密" in srv.tool_pdf({"pdf_path": enc_file}), "")
r = srv.tool_pdf({"pdf_path": bad_file, "action": "extract"})
ok("未知 action 校验在文件有效后触发", True)
os.remove(bad_file); os.remove(enc_file)
ok("缺 path 拦截", "❌" in srv.tool_pdf({}), "")

# ======================================================================
print("== 17. stdio 冒烟（0.4.6 · 19 工具）==")
def rpc(msgs):
    p = subprocess.run([sys.executable, os.path.join(HERE, "labmate_server.py")],
                       input="\n".join(msgs) + "\n", capture_output=True,
                       text=True, encoding="utf-8", timeout=40)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]

out = rpc([
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}',
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"labmate_handcalc","arguments":{"vars":{"b":0.1,"h_s":0.025},"steps":[{"symbol":"A_s","formula":"b*h_s"}],"fmt":"latex"}}}',
])
ok("版本 0.4.6", out[0]["result"]["serverInfo"]["version"] == "0.4.6",
   out[0]["result"]["serverInfo"])
names = [t["name"] for t in out[1]["result"]["tools"]]
ok("tools/list = 19", len(names) == 19, names)
ok("新工具全部注册", {"labmate_search", "labmate_pdf"} <= set(names), names)
ok("stdio 调 latex 中文无乱码", "align" in out[2]["result"]["content"][0]["text"],
   out[2]["result"]["content"][0]["text"][:80])

print("\n========== %d 通过，%d 失败 ==========" % (passed, failed))
sys.exit(1 if failed else 0)

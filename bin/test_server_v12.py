# -*- coding: utf-8 -*-
"""LabMate server 0.4.8 新增能力单测：labmate_docx Word 文档生成（零依赖 OOXML 手工构造 + zipfile 打包 + 三线表）。"""
import json
import os
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

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

TMP = tempfile.mkdtemp(prefix="labmate_v12_")
CSV_PATH = os.path.join(TMP, "sn.csv")
with open(CSV_PATH, "w", encoding="utf-8-sig") as f:
    f.write("编号,直径(mm),荷载(kN)\nS-1,10.02,25.4\nS-2,9.98,24.9\n")

# ======================================================================
print("== 50. docx · 黄金用例（完整报告 + zipfile 回读逐部件断言）==")
DOCX = os.path.join(TMP, "report.docx")
r = srv.tool_docx({"save_path": DOCX, "title": "Q235 钢拉伸试验报告",
                   "sections": [
                       {"type": "heading", "text": "1 试验概况", "level": 1},
                       {"type": "heading", "text": "1.1 试样与设备", "level": 2},
                       {"type": "paragraph", "text": "试样为 Q235 钢，直径 10 mm，标距 50 mm。"},
                       {"type": "table", "csv_path": CSV_PATH, "caption": "表 1 尺寸与荷载"}]})
ok("生成成功摘要", "**Word 文档已生成**" in r and DOCX in r, r[:200])
ok("结构统计（主标题+4 区块：标题×2、正文×1、表格×1）",
   "主标题「Q235 钢拉伸试验报告」+ 4 个区块（标题 ×2、正文 ×1、表格 ×1）" in r, r[:300])
ok("表格摘要行（2 行 × 3 列）", "- 表 1：2 行 × 3 列（数值列右对齐、文本列居中）" in r, r)
ok("文件已落盘", os.path.isfile(DOCX), DOCX)
z = zipfile.ZipFile(DOCX)
names = sorted(z.namelist())
ok("五个部件齐全（最小 OOXML 结构）",
   names == ["[Content_Types].xml", "_rels/.rels", "word/_rels/document.xml.rels",
             "word/document.xml", "word/styles.xml"], names)
x = z.read("word/document.xml").decode("utf-8")
s = z.read("word/styles.xml").decode("utf-8")
ct = z.read("[Content_Types].xml").decode("utf-8")
rr = z.read("_rels/.rels").decode("utf-8")
dr = z.read("word/_rels/document.xml.rels").decode("utf-8")
ok("document.xml 良构（ET 可解析）", ET.fromstring(x) is not None, "")
ok("styles.xml 良构（ET 可解析）", ET.fromstring(s) is not None, "")
ok("Content_Types 两个 Override（document/styles）",
   'PartName="/word/document.xml"' in ct and 'PartName="/word/styles.xml"' in ct, ct)
ok("根 rels 指向 word/document.xml", 'Target="word/document.xml"' in rr, rr)
ok("document rels 挂 styles.xml", 'Target="styles.xml"' in dr, dr)
ok("主标题黑体 18pt（sz=36）居中", 'w:eastAsia="黑体"' in x and '<w:sz w:val="36"' in x, "")
ok("heading 挂 Heading1/Heading2 样式",
   '<w:pStyle w:val="Heading1"/>' in x and '<w:pStyle w:val="Heading2"/>' in x, "")
ok("正文首行缩进 2 字符（firstLineChars=200）",
   '<w:ind w:firstLineChars="200" w:firstLine="480"/>' in x, "")
ok("A4 版面 sectPr（11906×16838 twips）", '<w:pgSz w:w="11906" w:h="16838"/>' in x, "")
ok("表题在表格上方（五号 sz=21 加粗居中）",
   x.find("表 1 尺寸与荷载") < x.find("<w:tbl") and '<w:sz w:val="21"' in x, "")
ok("三线表顶/底线 1.5pt（sz=12）恰好 2 条", x.count('w:val="single" w:sz="12"') == 2,
   x.count('w:val="single" w:sz="12"'))
ok("行间无横线无竖线（left/right/insideH/insideV 全 none）", x.count('w:val="none"') == 4, "")
ok("表头行底线 0.5pt（sz=4）", '<w:tcBorders><w:bottom w:val="single" w:sz="4"' in x, "")
ok("表头行挂 tblHeader 跨页重复", "<w:tblHeader/>" in x, "")
ok("表头居中加粗（编号）",
   '<w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">编号' in x, "")
ok("文本列居中（S-1）",
   '<w:jc w:val="center"/></w:pPr><w:r><w:rPr></w:rPr><w:t xml:space="preserve">S-1' in x, "")
ok("数值列右对齐（10.02）",
   '<w:jc w:val="right"/></w:pPr><w:r><w:rPr></w:rPr><w:t xml:space="preserve">10.02' in x, "")
ok("单元格数据完整（25.4 与 9.98 均在）", "25.4" in x and "9.98" in x, "")
ok("列宽等分版心（8306/3 = 2768 × 3 列）", x.count('<w:gridCol w:w="2768"/>') == 3, "")
ok("表后空段（防相邻表格粘连）", "</w:tbl><w:p/><w:sectPr" in x, "")
ok("styles：docDefaults 宋体 + Times New Roman",
   'w:ascii="Times New Roman" w:hAnsi="Times New Roman" '
   'w:eastAsia="宋体" w:cs="Times New Roman"/>' in s, "")
ok("styles：正文默认小四（sz=24）", '<w:sz w:val="24"/>' in s, "")
ok("styles：1.5 倍行距（line=360 auto）", '<w:spacing w:line="360" w:lineRule="auto"/>' in s, "")
ok("styles：三级标题挂 outlineLvl 0/1/2（导航窗格）",
   '<w:outlineLvl w:val="0"/>' in s and '<w:outlineLvl w:val="1"/>' in s
   and '<w:outlineLvl w:val="2"/>' in s, "")
ok("styles：Heading1 三号加粗（sz=32）",
   'w:styleId="Heading1"' in s and '<w:sz w:val="32"/>' in s, "")
ok("styles：keepNext 标题不与正文分页", "<w:keepNext/>" in s, "")

# ======================================================================
print("== 51. docx · 内联 rows 三形态 / XML 转义 / 超长截断 ==")
D2 = os.path.join(TMP, "inline.docx")
r2 = srv.tool_docx({"save_path": D2, "sections": [
    {"type": "table", "rows": [["组别", "均值"], ["A", 12.5], ["B", 13.1]]}]})
ok("rows 首行作表头形态", os.path.isfile(D2)
   and "- 表 1：2 行 × 2 列（数值列右对齐、文本列居中）" in r2, r2[:300])
x2 = zipfile.ZipFile(D2).read("word/document.xml").decode("utf-8")
ok("内联数字直出（12.5）", '<w:t xml:space="preserve">12.5' in x2, "")
ok("内联数值列右对齐",
   '<w:jc w:val="right"/></w:pPr><w:r><w:rPr></w:rPr><w:t xml:space="preserve">12.5' in x2, "")
ok("内联文本列居中（A/B）",
   '<w:jc w:val="center"/></w:pPr><w:r><w:rPr></w:rPr><w:t xml:space="preserve">A<' in x2, "")
D3 = os.path.join(TMP, "hdr.docx")
r3 = srv.tool_docx({"save_path": D3, "sections": [
    {"type": "table", "headers": ["x", "y"], "rows": [[1, 2], [3, 4]]}]})
ok("headers+rows 形态（与 labmate_tex 心智兼容）",
   os.path.isfile(D3) and "- 表 1：2 行 × 2 列" in r3, r3[:300])
D4 = os.path.join(TMP, "esc.docx")
r4 = srv.tool_docx({"save_path": D4, "sections": [
    {"type": "paragraph", "text": "R&D <100% \"ok\" & 'y' > 5"}]})
x3 = zipfile.ZipFile(D4).read("word/document.xml").decode("utf-8")
ok("XML 五实体全转义",
   "R&amp;D &lt;100% &quot;ok&quot; &amp; &apos;y&apos; &gt; 5" in x3, x3[:400])
ok("& 不双重转义", "&amp;amp;" not in x3, "")
big_rows = [["i", "v"]] + [[str(i), "%.2f" % (i * 1.5)] for i in range(1050)]
r5 = srv.tool_docx({"save_path": os.path.join(TMP, "big.docx"), "sections": [
    {"type": "table", "rows": big_rows}]})
ok("超 1000 行截断并在摘要明示", "- 表 1：1000 行 × 2 列，超 1000 行已截断" in r5, r5)
xb = zipfile.ZipFile(os.path.join(TMP, "big.docx")).read("word/document.xml").decode("utf-8")
ok("截断后实际 1000 行（w:tr = 1001 含表头）", xb.count("<w:tr>") == 1001, xb.count("<w:tr>"))

# ======================================================================
print("== 52. docx · 边界与行为 ==")
ok("缺 save_path", "❌ 需要 save_path（.docx 输出路径，如 报告.docx）"
   == srv.tool_docx({"sections": []}), "")
p_auto = os.path.join(TMP, "auto")
ra = srv.tool_docx({"save_path": p_auto, "sections": [{"type": "paragraph", "text": "x"}]})
ok("save_path 自动补 .docx 后缀", os.path.isfile(p_auto + ".docx") and p_auto + ".docx" in ra, ra)
SEC_ERR = ("❌ sections 需为非空数组：[{type: heading, text, level} | "
           "{type: paragraph, text} | {type: table, csv_path 或 headers+rows 或 rows（首行表头）, caption?}]")
ok("sections 非 list 拦截", SEC_ERR == srv.tool_docx({"save_path": "x.docx", "sections": "abc"}), "")
ok("sections 空数组拦截", SEC_ERR == srv.tool_docx({"save_path": "x.docx", "sections": []}), "")
ok("section 非 dict 拦截", "❌ 第 1 个 section 需为对象（{type: heading|paragraph|table, ...}）"
   == srv.tool_docx({"save_path": "x.docx", "sections": ["oops"]}), "")
ok("未知 type 拦截", "❌ 第 1 个 section 未知 type：image（支持 heading / paragraph / table）"
   == srv.tool_docx({"save_path": "x.docx",
                     "sections": [{"type": "image", "path": "a.png"}]}), "")
ok("缺 type 拦截", "❌ 第 1 个 section 未知 type：（缺 type）（支持 heading / paragraph / table）"
   == srv.tool_docx({"save_path": "x.docx", "sections": [{"text": "x"}]}), "")
ok("heading 缺 text 拦截", "❌ 第 1 个 heading 需要 text（标题文字）"
   == srv.tool_docx({"save_path": "x.docx", "sections": [{"type": "heading", "level": 1}]}), "")
ok("level=0 拦截", "❌ 第 1 个 heading 的 level 需为 1-3 整数（当前 0）"
   == srv.tool_docx({"save_path": "x.docx",
                     "sections": [{"type": "heading", "text": "a", "level": 0}]}), "")
ok("level=4 拦截", "❌ 第 1 个 heading 的 level 需为 1-3 整数（当前 4）"
   == srv.tool_docx({"save_path": "x.docx",
                     "sections": [{"type": "heading", "text": "a", "level": 4}]}), "")
ok("level 非整数拦截", "❌ 第 1 个 heading 的 level 需为 1-3 整数"
   == srv.tool_docx({"save_path": "x.docx",
                     "sections": [{"type": "heading", "text": "a", "level": "x"}]}), "")
ok("paragraph 缺 text 拦截", "❌ 第 1 个 paragraph 需要 text（正文文字）"
   == srv.tool_docx({"save_path": "x.docx", "sections": [{"type": "paragraph"}]}), "")
ok("table 三源皆空拦截",
   "❌ 第 1 个 table 缺数据：给 csv_path（直读本机 CSV），或 headers + rows，或 rows（首行作表头）"
   == srv.tool_docx({"save_path": "x.docx", "sections": [{"type": "table"}]}), "")
ok("csv 不存在拦截（带 section 序号）",
   srv.tool_docx({"save_path": "x.docx", "sections": [
       {"type": "paragraph", "text": "x"},
       {"type": "table", "csv_path": os.path.join(TMP, "none.csv")}]})
   .startswith("❌ 第 2 个 table：❌ 文件不存在："), "")
blocker = os.path.join(TMP, "blocker")
with open(blocker, "w") as f:
    f.write("x")
rb = srv.tool_docx({"save_path": os.path.join(blocker, "sub", "x.docx"),
                    "sections": [{"type": "paragraph", "text": "x"}]})
ok("写盘失败诚实报错", rb.startswith("❌ docx 写入失败："), rb)
rk = srv.tool_docx({"save_path": DOCX, "title": "重复写入", "sections": [
    {"type": "paragraph", "text": "覆盖旧文件"}]})
ok("覆盖已有 docx 文件成功", "**Word 文档已生成**" in rk, rk[:150])

# ======================================================================
print("== 53. 协议层、共用链路与文档注册 ==")
ok("TOOLS 升为 20 件", len(srv.TOOLS) == 20, len(srv.TOOLS))
sig = [t for t in srv.TOOLS if t["name"] == "labmate_docx"][0]
ok("schema：required = save_path + sections",
   sig["inputSchema"]["required"] == ["save_path", "sections"], sig)
ok("schema：描述含三线表与导航窗格", "三线表" in sig["description"]
   and "导航窗格" in sig["description"], sig["description"][:200])
ok("schema：sections 说明三种 type", "heading" in sig["inputSchema"]["properties"]["sections"]["description"]
   and "csv_path" in sig["inputSchema"]["properties"]["sections"]["description"], "")
ok("_DISPATCH 含 labmate_docx", callable(srv._DISPATCH.get("labmate_docx")), "")
ok("_read_csv_rows 黄金返回（header, rows 元组）",
   srv._read_csv_rows(CSV_PATH) == (["编号", "直径(mm)", "荷载(kN)"],
                                     [["S-1", "10.02", "25.4"], ["S-2", "9.98", "24.9"]]), "")
ok("_read_csv_rows 缺文件文案", "❌ 文件不存在："
   == srv._read_csv_rows(os.path.join(TMP, "none.csv"))[:len("❌ 文件不存在：")], "")
tex_r = srv.tool_tex({"action": "table", "csv_path": CSV_PATH})
ok("labmate_tex csv_path 老路径不受抽取重构影响",
   "\\toprule" in tex_r and "S-1" in tex_r and "& 10.02 & 25.4 \\\\" in tex_r, tex_r[:200])
main_skill = open(os.path.join(HERE, "..", "skills", "labmate", "SKILL.md"), encoding="utf-8").read()
ok("主路由版本行 = 0.5.0", "v0.5.0" in main_skill, "")
ok("主路由工具表含 docx 行", "labmate_docx" in main_skill, "")

def rpc(msgs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "labmate_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode("utf-8"))
    return [json.loads(l) for l in out.decode("utf-8").splitlines() if l.strip()]

RPC_DOCX = os.path.join(TMP, "report_rpc.docx")
res = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
           {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "labmate_docx",
                       "arguments": {"save_path": RPC_DOCX, "title": "力学试验报告",
                                     "sections": [
                                         {"type": "heading", "text": "1 数据", "level": 1},
                                         {"type": "table", "csv_path": CSV_PATH}]}}}])
ok("initialize 版本 = 0.5.0", res[0]["result"]["serverInfo"]["version"] == "0.5.0", res[0])
txt = res[1]["result"]["content"][0]["text"]
ok("stdio 黄金用例生成摘要", "**Word 文档已生成**" in txt and "- 表 1：2 行 × 3 列" in txt,
   txt[:200])
ok("stdio 产物落盘", os.path.isfile(RPC_DOCX), RPC_DOCX)
zr = zipfile.ZipFile(RPC_DOCX)
ok("stdio 产物 XML 良构 + 标题样式挂载",
   ET.fromstring(zr.read("word/document.xml")) is not None
   and b"Heading1" in zr.read("word/styles.xml"), "")

print("\n== v0.4.8 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

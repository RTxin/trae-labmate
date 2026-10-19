# -*- coding: utf-8 -*-
"""LabMate server 0.4.1 单测：labmate_table 新增 Excel(.xlsx) 零依赖读取。
fixture 用 zipfile 现场构造标准 ECMA-376 工作簿（不依赖 openpyxl），
覆盖五个已知坑位：稀疏空位列对齐 / sharedStrings 富文本 / inlineStr / 布尔 /
日期序列号（内置+自定义+伪闰年边界）；另有科学计数解析与坏文件边界。"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import zipfile

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

TMP = tempfile.gettempdir()
XLSX = os.path.join(TMP, "labmate_试验数据.xlsx")

# ====================== fixture：现场构造标准 xlsx ======================
# 序列号与断言同源自洽：days(2026-10-19) 用 epoch 1899-12-30 现算
SERIAL_D19 = (datetime.date(2026, 10, 19) - datetime.date(1899, 12, 30)).days  # 2026-10-19
NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

def _sheet_xml(rows):
    """rows: [[(ref, attrs, v), ...], ...] 直接拼 worksheet XML。"""
    parts = [XML_HEAD + '<worksheet xmlns="%s"><sheetData>' % NS_MAIN]
    for row in rows:
        parts.append('<row r="%s">' % row[0][0][1:])
        for ref, attrs, v in row:
            parts.append('<c r="%s"%s>%s</c>' % (ref, (" " + attrs).rstrip(), v))
        parts.append("</row>")
    parts.append("</sheetData></worksheet>")
    return "".join(parts).encode("utf-8")

# 坑位⑤：第一个工作表故意不叫 sheet1.xml（rels 定位必须生效）
SHARED = (XML_HEAD +
    '<sst xmlns="%s" count="8" uniqueCount="8">'
    '<si><t>试样</t></si>'
    '<si><t>直径(mm)</t></si>'
    '<si><t>荷载(kN)</t></si>'
    '<si><t>试验日期</t></si>'
    '<si><t>合格</t></si>'
    '<si><t>应变</t></si>'
    '<si><t>A-01</t></si>'
    # 富文本：两段 <r><t> 拼接成「混合批次」
    '<si><r><rPr><b/></rPr><t>混合</t></r><r><t>批次</t></r></si>'
    '</sst>' % NS_MAIN).encode("utf-8")

STYLES = (XML_HEAD +
    '<styleSheet xmlns="%s">'
    '<numFmts count="2">'
    '<numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd hh:mm"/>'      # 自定义日期时间
    '<numFmt numFmtId="165" formatCode="0.00E+00"/>'                 # 科学计数显示（非日期）
    '</numFmts>'
    '<fonts count="1"><font><sz val="11"/></font></fonts>'
    '<fills count="1"><fill/></fills>'
    '<borders count="1"><border/></borders>'
    '<cellStyleXfs count="1"><xf numFmtId="0"/></cellStyleXfs>'
    '<cellXfs count="4">'
    '<xf numFmtId="0"/>'          # s=0 普通
    '<xf numFmtId="14"/>'         # s=1 内置日期
    '<xf numFmtId="164"/>'        # s=2 自定义日期时间
    '<xf numFmtId="165"/>'        # s=3 科学计数显示（仍非日期）
    '</cellXfs></styleSheet>' % NS_MAIN).encode("utf-8")

# 坑位①：B3/C4/D3/E4/F… 多处稀疏空位；坑位②③：shared/富文本/inlineStr；④：日期三种样式
SHEET1 = _sheet_xml([
    # 表头（全 shared string）
    [("A1", 't="s"', "<v>0</v>"), ("B1", 't="s"', "<v>1</v>"), ("C1", 't="s"', "<v>2</v>"),
     ("D1", 't="s"', "<v>3</v>"), ("E1", 't="s"', "<v>4</v>"), ("F1", 't="s"', "<v>5</v>")],
    # 行2：完整行；日期走内置格式 s=1
    [("A2", 't="s"', "<v>6</v>"), ("B2", "", "<v>50.5</v>"), ("C2", "", "<v>1234.5</v>"),
     ("D2", 's="1"', "<v>%d</v>" % SERIAL_D19), ("E2", 't="b"', "<v>1</v>"), ("F2", 's="3"', "<v>0.0025</v>")],
    # 行3：B3/D3 缺失（稀疏）；A3 富文本；F3 科学计数 v（0.4.1 新解析分支）
    [("A3", 't="s"', "<v>7</v>"), ("C3", "", "<v>250</v>"),
     ("E3", 't="b"', "<v>0</v>"), ("F3", 's="3"', "<v>1.5E-3</v>")],
    # 行4：C4/E4 缺失；A4 inlineStr；D4 自定义日期时间 s=2（46023.5 = 2026-01-01 12:00）
    [("A4", 't="inlineStr"', "<is><t>C-03</t></is>"), ("B4", "", "<v>75</v>"),
     ("D4", 's="2"', "<v>46023.5</v>"), ("F4", "", "<v>0.001</v>")],
])
SHEET2 = _sheet_xml([
    [("A1", 't="inlineStr"', "<is><t>项目</t></is>"), ("B1", 't="inlineStr"', "<is><t>均值</t></is>")],
    [("A2", 't="inlineStr"', "<is><t>alpha</t></is>"), ("B2", "", "<v>0.5</v>")],
])

WORKBOOK = (XML_HEAD +
    '<workbook xmlns="%s" xmlns:r="%s"><sheets>'
    '<sheet name="数据" sheetId="1" r:id="rId1"/>'
    '<sheet name="汇总" sheetId="2" r:id="rId2"/>'
    '</sheets></workbook>' % (NS_MAIN, NS_R)).encode("utf-8")
WB_RELS = (XML_HEAD +
    '<Relationships xmlns="%s">'
    '<Relationship Id="rId1" Type="%s/worksheet" Target="worksheets/zz9.xml"/>'
    '<Relationship Id="rId2" Type="%s/worksheet" Target="worksheets/aa1.xml"/>'
    '</Relationships>' % (NS_PKG, NS_R, NS_R)).encode("utf-8")
CT = (XML_HEAD +
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    '<Override PartName="/xl/worksheets/zz9.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    '<Override PartName="/xl/worksheets/aa1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    '</Types>').encode("utf-8")

with zipfile.ZipFile(XLSX, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", CT)
    z.writestr("xl/workbook.xml", WORKBOOK)
    z.writestr("xl/_rels/workbook.xml.rels", WB_RELS)
    z.writestr("xl/styles.xml", STYLES)
    z.writestr("xl/sharedStrings.xml", SHARED)
    z.writestr("xl/worksheets/zz9.xml", SHEET1)
    z.writestr("xl/worksheets/aa1.xml", SHEET2)

# ====================== 底层函数：列号 / 科学计数 / 日期引擎 ======================
print("== 21. xlsx 底层引擎 ==")
ok("列号 A→0 / Z→25 / AA→26 / AB→27",
   srv._xlsx_col_index("A") == 0 and srv._xlsx_col_index("Z") == 25
   and srv._xlsx_col_index("AA") == 26 and srv._xlsx_col_index("AB") == 27)
ok("科学计数 1.5E-3 → 0.0015", approx(srv._parse_cell_float("1.5E-3"), 0.0015), srv._parse_cell_float("1.5E-3"))
ok("科学计数 2E+3 → 2000；负数 -1.2e-4", approx(srv._parse_cell_float("2E+3"), 2000)
   and approx(srv._parse_cell_float("-1.2e-4"), -1.2e-4))
ok("千分位/欧式/纯文本回归不受影响", approx(srv._parse_cell_float("1,234.5"), 1234.5)
   and srv._parse_cell_float("abc") is None and approx(srv._parse_cell_float("1234,5"), 1234.5))
ok("serial 1 → 1900-01-01（前段起点 1899-12-31）", srv._xlsx_serial_date(1) == "1900-01-01", srv._xlsx_serial_date(1))
ok("serial 61 → 1900-03-01（伪闰年分界，起点切 1899-12-30）", srv._xlsx_serial_date(61) == "1900-03-01", srv._xlsx_serial_date(61))
ok("serial 46023.5 → 2026-01-01 12:00（自定义格式带时间）", srv._xlsx_serial_date(46023.5) == "2026-01-01 12:00", srv._xlsx_serial_date(46023.5))
secs = 12 * 3600 + 30 * 60 + 45
ok("带秒时间 %02d:%02d:%02d 保留到秒" % (secs // 3600, secs % 3600 // 60, secs % 60),
   srv._xlsx_serial_date(46023 + secs / 86400.0) == "2026-01-01 12:30:45", srv._xlsx_serial_date(46023 + secs / 86400.0))
ok("formatCode 日期判定：内置风格/带引号文本判 True，科学计数与普通数字 False",
   srv._xlsx_fmt_is_date("yyyy-mm-dd") and srv._xlsx_fmt_is_date('"年"yyyy"月"m"日"')
   and not srv._xlsx_fmt_is_date("0.00E+00") and not srv._xlsx_fmt_is_date("#,##0.00")
   and not srv._xlsx_fmt_is_date("General"))
ok("内置日期 numFmtId 14/22/45 命中、165 自定义不命中",
   14 in srv._XL_BUILTIN_DATE_FMTS and 22 in srv._XL_BUILTIN_DATE_FMTS and 45 in srv._XL_BUILTIN_DATE_FMTS)

# ====================== labmate_table xlsx 路径：主 fixture ======================
print("== 22. labmate_table 读取 xlsx（主 fixture）==")
r = srv.tool_table({"xlsx_path": XLSX})
ok("读取成功且来源描述含工作表名", "工作表『数据』" in r and "1/2" in r, r[:150])
ok("表头 6 列正确（shared string）", "试样" in r and "直径" in r and "荷载" in r
   and "试验日期" in r and "合格" in r and "应变" in r, r[:300])
ok("直径列：数值 n=2 缺失 1（B3 稀疏空位）", "直径" in r and "数值列，n=2，缺失 1" in r, r)
ok("荷载列：数值 n=2（C4 缺失）", "荷载" in r and ("n=2，缺失 1" in r), r)
ok("应变列：科学计数通吃，n=3 均值 0.00166667",
   "应变" in r and srv._fmt((0.0025 + 0.0015 + 0.001) / 3) in r, r)
ok("日期列：ISO 文本 + 缺失 1（D3 稀疏，未泄漏序列号）",
   "2026-10-19" in r and "2026-01-01 12:00" in r and str(SERIAL_D19) not in r, r)
ok("日期列是文本列统计", "试验日期**（文本列" in r, r)
ok("富文本段落拼接：混合批次", "混合批次" in r, r)
ok("inlineStr 读取：C-03", "C-03" in r, r)
ok("布尔列 TRUE/FALSE 文本化", "TRUE" in r and "FALSE" in r, r)
ok("坑位①列对齐：行2 预览顺序完整",
   "A-01,50.5,1234.5,2026-10-19,TRUE,0.0025" in r, r[-500:])
ok("坑位①列对齐：行3 B/D 稀疏位补空",
   "混合批次,,250,,FALSE,1.5E-3" in r, r[-500:])
ok("只读不写提示", "数据体检" in r, r[:100])

# ====================== 工作表选择 ======================
print("== 23. 工作表选择 ==")
r = srv.tool_table({"xlsx_path": XLSX, "sheet": "汇总"})
ok("按名称选『汇总』", "工作表『汇总』" in r and "alpha" in r and "0.5" in r, r[:200])
r = srv.tool_table({"xlsx_path": XLSX, "sheet": 2})
ok("按 1-based 序号 2 选表", "工作表『汇总』" in r, r[:120])
r = srv.tool_table({"xlsx_path": XLSX, "sheet": "2"})
ok("字符串序号 '2' 同样可用", "工作表『汇总』" in r, r[:120])
r = srv.tool_table({"xlsx_path": XLSX, "sheet": "不存在"})
ok("选错名称：报错并列出现有工作表", "❌" in r and "『数据』" in r and "『汇总』" in r, r)
r = srv.tool_table({"xlsx_path": XLSX, "sheet": 99})
ok("序号越界：明确总数", "❌" in r and "共 2 个" in r, r)

# ====================== 坏文件边界 ======================
print("== 24. 坏文件边界 ==")
r = srv.tool_table({"xlsx_path": os.path.join(TMP, "labmate_没有这个文件.xlsx")})
ok("文件不存在", "❌" in r and "文件不存在" in r, r)
fake_xls = os.path.join(TMP, "labmate_老格式.xls")
with open(fake_xls, "wb") as f:
    f.write(b"\xd0\xcf\x11\xe0hello-not-a-zip")
r = srv.tool_table({"xlsx_path": fake_xls})
ok("老式 .xls 二进制：明确引导另存为 .xlsx", "❌" in r and ".xlsx" in r and ".xls" in r, r)
r = srv.tool_table({"xlsx_path": XLSX + ".txt"})
with open(XLSX + ".txt", "w") as f:
    f.write("我是纯文本，不是 Excel")
r = srv.tool_table({"xlsx_path": XLSX + ".txt"})
ok("纯文本伪装 .xlsx：BadZipFile 诊断", "❌" in r and "有效" in r, r)
bad_zip = os.path.join(TMP, "labmate_缺workbook.xlsx")
with zipfile.ZipFile(bad_zip, "w") as z:
    z.writestr("hello.txt", "zip 但不是 xlsx")
r = srv.tool_table({"xlsx_path": bad_zip})
ok("zip 但缺 workbook.xml：结构诊断", "❌" in r and "workbook.xml" in r, r)
header_only = os.path.join(TMP, "labmate_只有表头.xlsx")
with zipfile.ZipFile(header_only, "w") as z:
    z.writestr("xl/workbook.xml", WORKBOOK.decode("utf-8"))
    z.writestr("xl/_rels/workbook.xml.rels", WB_RELS.decode("utf-8"))
    z.writestr("xl/worksheets/zz9.xml",
               (XML_HEAD + '<worksheet xmlns="%s"><sheetData>'
                '<row r="1"><c r="A1" t="inlineStr"><is><t>只有表头</t></is></c></row>'
                '</sheetData></worksheet>' % NS_MAIN))
r = srv.tool_table({"xlsx_path": header_only})
ok("只有表头行：数据不足诊断", "❌" in r and "只有表头一行" in r, r)

# ====================== CSV 路径回归（xlsx 改动不得破坏老行为） ======================
print("== 25. CSV 路径回归 ==")
csv_path = os.path.join(TMP, "labmate_v05_reg.csv")
with open(csv_path, "w", encoding="utf-8") as f:
    f.write("name,value\nA,1\nB,2\n")
r = srv.tool_table({"csv_path": csv_path})
ok("CSV 读取回归", "name" in r and "数值列" in r and "均值 1.5" in r, r)
r = srv.tool_table({"data": "a;b\n1;2\n3;4\n"})
ok("内联数据+分号分隔回归", "数值列" in r and "均值 2" in r and "均值 3" in r, r)
r = srv.tool_table({})
ok("空参数仍给使用引导", "❌" in r, r)

# ====================== stdio 冒烟 ======================
print("== 26. stdio 冒烟（0.4.3 · 19 工具）==")
def rpc(msgs):
    p = subprocess.run([sys.executable, os.path.join(HERE, "labmate_server.py")],
                       input="\n".join(msgs) + "\n", capture_output=True,
                       text=True, encoding="utf-8", timeout=60)
    return [json.loads(l) for l in p.stdout.splitlines() if l.strip()]

out = rpc([
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}',
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}',
    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"labmate_table","arguments":{"xlsx_path":"%s"}}}' % XLSX.replace("\\", "\\\\"),
])
ok("版本 0.4.3", out[0]["result"]["serverInfo"]["version"] == "0.4.3", out[0])
names = [t["name"] for t in out[1]["result"]["tools"]]
ok("tools/list = 19（0.4.2 新增 plot/curve）", len(names) == 19, names)
schema = [t for t in out[1]["result"]["tools"] if t["name"] == "labmate_table"][0]["inputSchema"]["properties"]
ok("labmate_table schema 含 xlsx_path/sheet", "xlsx_path" in schema and "sheet" in schema, schema)
body = out[2]["result"]["content"][0]["text"]
ok("stdio 全链路：xlsx 读取中文+统计正常", "工作表『数据』" in body and "2026-10-19" in body, body[:150])

print("\n========== %d 通过，%d 失败 ==========" % (passed, failed))
sys.exit(1 if failed else 0)

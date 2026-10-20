# -*- coding: utf-8 -*-
"""LabMate server 0.5.0 新增能力单测：labmate-grant 基金申请书引导 skill（第 17 个模块）+ consult 试验大纲 docx 出口。"""
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

SKILLS = os.path.join(HERE, "..", "skills")

# ======================================================================
print("== 59. labmate-grant · 基金申请书引导 skill（第 17 个模块）==")
grant_path = os.path.join(SKILLS, "labmate-grant", "SKILL.md")
ok("grant skill 文件存在", os.path.exists(grant_path), grant_path)
gtxt = open(grant_path, encoding="utf-8").read() if os.path.exists(grant_path) else ""
ok("frontmatter name = labmate-grant", "name: labmate-grant" in gtxt, gtxt[:100])
ok("description 触发词（基金申请/青基/立项依据/技术路线/开题）",
   all(k in gtxt for k in ("基金申请", "青基", "立项依据", "技术路线", "开题")), "")
ok("四问协议（科学问题/为什么是你/为什么是现在/为什么这样做）",
   all(k in gtxt for k in ("科学问题是什么", "为什么是你", "为什么是现在", "为什么这样做")), "")
ok("申请书结构表（立项依据/研究内容/关键科学问题/可行性分析/研究基础）",
   all(k in gtxt for k in ("立项依据", "研究内容", "关键科学问题", "可行性分析", "研究基础")), "")
ok("研究内容 3 条黄金结构", "3 条左右黄金结构" in gtxt, "")
ok("创新点 2~3 条红线", "2~3 条" in gtxt, "")
ok("评审死因清单（任务清单是第一大死因）", "任务清单" in gtxt and "第一大死因" in gtxt, "")
ok("科学问题 ≠ 技术任务分野", "科学问题" in gtxt and "任务" in gtxt, "")
ok("工具链配合（search/docx/disclosure/power/doe/handcalc/plot）",
   all(k in gtxt for k in ("labmate_search", "labmate_docx", "labmate-disclosure",
                           "labmate_stats", "labmate_doe", "labmate_handcalc", "labmate_plot")), "")
ok("AI 使用披露衔接（labmate-disclosure 声明模板）", "披露" in gtxt, "")
ok("边界声明（不代写学术内容）", "不代写" in gtxt, "")
ok("年份过滤与功效写法（立项依据检索与样本量进方案）",
   "年份过滤" in gtxt and "功效 0.8" in gtxt, "")

# ======================================================================
print("== 60. consult 试验大纲出口 + 主路由注册 ==")
ctext = open(os.path.join(SKILLS, "labmate-consult", "SKILL.md"), encoding="utf-8").read()
ok("consult 第 5 步：落成试验大纲", "第 5 步：落成试验大纲" in ctext, "")
ok("大纲出口走 labmate_docx + sections 模板",
   "labmate_docx" in ctext and "sections=[" in ctext, "")
ok("大纲五节结构（试验目的/试样与设备/加载方案/观测/安全边界）",
   all(k in ctext for k in ("试验目的", "试样与设备", "加载方案与量级校核", "观测与数据采集", "安全与边界")), "")
ok("大纲与既有工具衔接（power/outlier/采样定理）",
   "power" in ctext and "outlier" in ctext and "采样定理" in ctext, "")
main_skill = open(os.path.join(SKILLS, "labmate", "SKILL.md"), encoding="utf-8").read()
ok("主路由版本行 = 0.5.0", "v0.5.0" in main_skill, "")
ok("主路由声明 17 个 skills", "17 个科研引导 skills" in main_skill, "")
ok("主路由路由表含 grant 行（基金/课题申请书）", "基金/课题申请书" in main_skill
   and "labmate-grant" in main_skill, "")
ok("主路由 frontmatter 模块清单含 grant", "grant/literature/disclosure" in main_skill, "")
ok("主路由触发词含「基金申请书」「写本子」", "基金申请书" in main_skill and "写本子" in main_skill, "")
ok("主路由触发词含「Word 文档生成」", "Word 文档生成" in main_skill, "")
skill_dirs = sorted(d for d in os.listdir(SKILLS)
                    if os.path.exists(os.path.join(SKILLS, d, "SKILL.md")))
ok("skills 目录数 = 17", len(skill_dirs) == 17, skill_dirs)

# ======================================================================
print("== 61. 协议层与 stdio（server 行为不受 skill-only 迭代影响）==")
ok("TOOLS 仍为 20 件", len(srv.TOOLS) == 20, len(srv.TOOLS))
ok("corr 黄金回归（r = 0.8 精确）",
   "Pearson r = 0.8" in srv.tool_stats({"action": "corr", "x": [1, 2, 3, 4, 5], "y": [2, 1, 4, 3, 5]}), "")
ok("docx 黄金回归（生成成功）",
   "**Word 文档已生成**" in srv.tool_docx({"save_path": os.path.join(os.environ.get("TEMP", "."), "v14_regress.docx"),
                                              "sections": [{"type": "paragraph", "text": "x"}]}), "")

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
                                     "y": [2, 1, 4, 3, 5]}}}])
ok("initialize 版本 = 0.5.0", res[0]["result"]["serverInfo"]["version"] == "0.5.0", res[0])
ok("stdio corr 黄金（r = 0.8）",
   "Pearson r = 0.8" in res[1]["result"]["content"][0]["text"],
   res[1]["result"]["content"][0]["text"][:150])

print("\n== v0.5.0 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

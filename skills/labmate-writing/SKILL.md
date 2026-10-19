---
name: labmate-writing
description: 论文写作与 LaTeX 生产力引导。当用户需要生成论文表格（三线表）、figure/subfigure 图环境、编号公式、BibTeX 参考文献库管理（查重/体检/合并/排序）、把试验结果整理成投稿可用格式时使用。触发词：「做三线表」「生成表格」「这个表怎么排」「合并 bib 文件」「参考文献重复了」「图环境」「子图怎么排」「公式怎么编号」。计算一律调 MCP 工具 labmate_tex / labmate_bibtex，不手拼 LaTeX 字符串。
---

# LabMate · 论文写作与 LaTeX 生成（labmate-writing）

写作类需求**不要手敲 LaTeX 字符串，直接调工具**——转义（& % $ # _）、booktabs 规范、BibTeX 字段顺序这些细节工具已内置：

| 需求 | 调用 |
|---|---|
| booktabs 三线表（支持 csv_path 直读、数值列自动右对齐） | `labmate_tex`（action: table） |
| figure 图环境（多图自动 subfigure） | `labmate_tex`（action: figure） |
| 带编号公式（\label + \eqref 引用） | `labmate_tex`（action: equation） |
| .bib 库体检（缺字段/重复 key/DOI） | `labmate_bibtex`（action: check） |
| 跨库去重合并（DOI 优先、字段互补） | `labmate_bibtex`（action: merge） |
| 按年份/作者/ key 重排 | `labmate_bibtex`（action: merge + sort 参数） |

## 标准工作流（试验数据 → 投稿三件套）

1. **数据先体检**：`labmate_table(csv_path=...)` 确认列结构与数值范围，再进表格——表格里出现 1,234 与 1234 混排是审稿人一眼就抓的把柄
2. **三线表**：`labmate_tex(table, csv_path=..., caption="...", label="tab:xxx")`——数值列自动右对齐，文本列左对齐；超 40 行工具会提示分表或 longtable
3. **图环境**：`labmate_tex(figure, files=[...], caption="...", label="fig:xxx")`——多图自动 subfigure + subcaption 包提示；图本体用 matplotlib + `labmate_style` 生成
4. **参考文献**：新引用用 `labmate_cite(doi=...)` 生成真实 BibTeX；定期 `labmate_bibtex(check, bib_path=...)` 体检，从合作者/导师那里拿到杂库先 merge 去重再并入
5. **终稿前**：走 `labmate-disclosure` 做四类校验（数据真实引用/量纲/边界声明/AI 使用披露）

## 本领域的专业常识（模块的灵魂）

1. **三线表没有竖线**。booktabs 的 `\toprule\midrule\bottomrule` 是学术排版共识——加了竖线的表一稿就会被打回。表注放 caption 内还是表下、有效数字对齐规则（同一列统一小数位），期刊模板说了算，别按个人喜好。
2. **每个表和图都要能在正文被引用**：`label` 必须在 `caption` 之后定义，正文用 `\ref{tab:xxx}`/`\eqref{eq:xxx}` 引用——"图表零引用"是审稿人判定凑篇幅的经典信号。
3. **BibTeX 悲剧的三大来源**：同年同作者 key 撞车（Repeaated entry 编译错）、标题里的 & % 未转义（编译错或条目被吃）、同一篇文献多个 key（正文引用了 Wang2020 和 Wang2020a 实为同一篇）。工具的 check/merge 已覆盖三类，**合稿前必跑一次 check**。
4. **导言区依赖要一次说清**：三线表需要 `\usepackage{booktabs}`，多子图需要 `\usepackage{subcaption}`——工具输出会提示，收稿时集中加进导言区，别让合作者编译一次报一次错。
5. **公式给编号是给讨论留钩子**：审稿意见常指"式(12)中…"，无编号公式没法被引用讨论；只在推导中间步骤用 `equation*`/`align*` 省编号。
6. **诚实边界**：工具做排版与库管理，不替你写论述文字；英文润色、期刊选刊、Cover Letter 属写作策略问题，走通用对话，本模块不包装。

## 与其他模块的配合

- 数据来源与统计口径：`labmate-data`（清洗）/ `labmate-stats`（显著性表述：先效应量后 p 值）
- 图本体生成：`labmate-plot` + `labmate_style`（期刊级样式）
- 引用真实性：`labmate_cite`（DOI→真实 BibTeX），本模块只管库的秩序
- 交稿校验：`labmate-disclosure`

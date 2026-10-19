# LabMate 科研搭子 · 产品需求文档（PRD）

| | |
|---|---|
| 版本 | 0.4.1（P1/P2 全量落地 + P3 需求复核六工具补齐 + P4 Excel 数据入口） |
| 日期 | 2026-10-19 |
| 状态 | P0 已实施（0.2.0）；P1 全部完成（0.3.0）；P2 完成多源聚合+本地 PDF 两项（0.3.0）；P3 统计/不确定度/DOE/写作/BibTeX/信号六工具上线（0.4.0）；P4 labmate_table 增加 Excel 直读（0.4.1，17 工具/15 skills） |
| 产品形态 | Trae 插件（skills 脑 + Python MCP server 手） |

---

## 1. 产品概述

**一句话**：装在研究者本机 IDE 里的科研 AI 搭档——先把专家没说出口的参数问出来（引导协议），再用确定性工具把活干完（计算引擎 + 文献 + 数据）。

**定位（来自市场空白）**：现有 AI 科研产品（NotebookLM、Elicit、SciSpace、Consensus、scite、Jenni 等）全部围绕"文献"环节、全部云端、全部要求用户会提问。而研究者时间的大头——**试验 20-25% + 数据分析 15-20%——以及"AI 新手引导"环节，无人覆盖**。LabMate 的差异化：本地优先、对话引导、确定性计算工具、面向不会用 AI 的领域专家。

---

## 2. 调研结论摘要（本次升级的依据）

### 2.1 用户时间与信任数据
- 时间分配（your.phd 2023-24 汇总）：文献阅读 25-30% ＞ 试验/采集 20-25% ＞ 数据分析 15-20% ＞ 写作 15-20% ＞ 行政 10-15%
- Nature 研究生调查 2025（n=3785）：**60% 接受 AI 总结文献**（最高），仅 **33% 接受 AI 分析数据/写论文**（最低）——数据类任务需要"引导式低风险交互"来建立信任
- 2400 科学家调查：最大顾虑是**幻觉/编造文献**；Springer Nature：最大挑战是"披露差距"

### 2.2 试验学科（力学/材料/物理）特有痛点
- 仪器厂商专有二进制格式，元数据需逆向（arXiv 2511.01942）
- 数据滞留"本地笔记本/仪器文件夹"，Excel 中心工作流的转录错误与溯源断裂（Bassetti）
- 单次声发射试验数十万波形，人工处理不可行（Frontiers）
- 领域专家普遍缺编程能力（arXiv 2511.21920）——与 P1 画像完全吻合

### 2.3 工具生态查证（适合集成的排序）
| 方向 | 查证结论 | 集成方式 |
|---|---|---|
| arXiv 检索 | 官方 API **完全免费、无需 key**、Atom XML | **API 封装进 MCP server（P0）** |
| Crossref/DOI | 官方 API **免费无 key**（mailto 即 polite） | **API 封装：DOI→元数据→BibTeX（P0）** |
| SciencePlots | 本质是 .mplstyle 样式字典（IEEE/Nature/科学风） | **自研内置样式注入（P0）** |
| handcalcs | 符号替换+排版模板，核心可零依赖复刻 | 已自研（labmate_handcalc），P1 增强 LaTeX 输出 |
| 多源文献聚合 | paper-search-mcp（3.1k★ arxiv-mcp 同作者）思路：多源并发+去重 | P2（先单源做稳） |
| Zotero/pandoc | 依赖用户本地环境 | skill 指导（P2） |

---

## 3. 用户画像

**P1 资深研究者·领域专家（主画像）**——"能力极强的提问弱者"
- 特征：脑内知识完整（装置、工况、经验参数），但不会把它显性化；把 AI 当聊天框；对计算结果要求可校核
- 关键句："今天的 AI 没一个能打的"——真实原因是输入缺了 80% 隐含前提
- 需求：引导协议把参数问出来；教科书式计算过程；量级校核先于细节

**P2 博后/青年教师**——"效率优先的多面手"
- 时间被试验、数据、写作、基金本子撕碎；愿意用工具但没空学
- 需求：数据快速处理（CSV→统计→图）；文献快速侦察（arXiv 新论文）；投稿物快速产出（图表/引用）

**P3 博士生**——"AI 重度但方向迷茫"
- 愿意折腾，但缺乏领域量级感，容易被 AI 的自信误导
- 需求：诚实的不确定性标注；公式推导可验证；红线警示（"设备吨位不够"这类工程判断）

---

## 4. 用户旅程与痛点矩阵

```
读文献(25-30%) → 做试验(20-25%) → 处理数据(15-20%) → 分析论证 → 写作(15-20%) → 投稿/披露
```

| 环节 | 痛点 | 现有竞品 | LabMate 0.1 | 升级动作 |
|---|---|---|---|---|
| 读文献 | 单篇精读 30-40min；综述准备占 50-70% 时长 | 云端全覆盖 | 无 | **P0：arXiv 检索工具** + P1 精读 skill |
| 引用管理 | 手编 BibTeX 格式错；引用真实性焦虑（幻觉文献） | scite 验真（云端） | 无 | **P0：DOI→BibTeX（真实元数据，杜绝编造）** |
| 试验设计 | 隐含前提说不出口；设备/方案可行性靠拍脑袋 | 无 | consult 模块 ✓ | 保持 |
| 数据处理 | Excel 转录错误；仪器格式；缺编程能力 | **无人覆盖** | data skill（指导性） | **P0：labmate_table 本机数据工具**（零依赖 CSV 读取+统计摘要） |
| 分析计算 | 黑箱结果不可信（33% 信任率） | 无 | handcalc/mohr/fit ✓ | 保持 + P1 LaTeX 输出 |
| 写作出图 | 图不像期刊的；样式调半天 | 部分写作产品 | plot skill（指导性） | **P0：期刊样式注入工具** |
| 披露合规 | AI 使用声明的"披露差距" | 无 | 无 | P1：输出校验 + 声明模板 |

---

## 5. 竞品分析结论

九款产品（NotebookLM/Elicit/SciSpace/Consensus/scite/ResearchRabbit/Connected Papers/Jenni/Iris.ai）功能矩阵表明：
- **文献环节**：发现、图谱、综述、接地问答、写作、引文验证全部成熟——**不正面竞争**
- **空白 1**：本机试验数据（读取/清洗/统计/绘图）——LabMate 独占
- **空白 2**：AI 新手引导（参数结构化）——LabMate 独占（consult 协议）
- **差异化 3**：本地优先（数据不出机器）vs 全员云端——对涉密/未发表数据的研究者是硬需求

---

## 6. 需求清单与优先级

### P0（本轮实施 · MCP server 新增 4 工具）

| # | 工具 | 输入 | 输出 | 依据 |
|---|---|---|---|---|
| 1 | `labmate_arxiv` | query, max_results, category? | 结构化论文列表（标题/作者/日期/摘要前 200 字/链接） | 免费无 key；60% 接受度最高环节 |
| 2 | `labmate_cite` | doi | 元数据 + **规范 BibTeX**（从 Crossref 真实元数据生成，杜绝幻觉引用） | 幻觉文献是最大顾虑；写作刚需 |
| 3 | `labmate_table` | csv_path 或 data, delimiter? | 列摘要：行数/数值列的均值/极值/缺失 + 前几行预览 | 竞品空白；缺编程能力人群的"数据第一步" |
| 4 | `labmate_style` | style_name(ieee/nature/science/cnjournal), save_mplstyle? | 期刊样式参数字典（可直接写入 .mplstyle 文件）+ 用法说明 | SciencePlots 逆向自研；"结果→可发表片段" |

**P0 技术约束**：全部用 Python 标准库（urllib/csv/json/xml），保持零第三方依赖；网络工具失败时优雅降级并给诊断信息。

### P1（0.2.0~0.3.0 已全部落地）
- ✅ 新增 `labmate-literature` skill：文献工作流（检索→筛选→精读→引用），绑定真实数据源工具
- ✅ `labmate_handcalc` 增强：`fmt=latex` 输出 align* 推导（AST 递归渲染，希腊字母/下标/分式/科学计数自动转换，可贴 Overleaf）
- ✅ `labmate-data` 增强：第〇步铁律"先 labmate_table 摸底再写脚本"
- ✅ `labmate-plot` 增强：第〇步绑定 `labmate_style`，rcParams 必须来自工具返回
- ✅ 输出校验与 AI 使用声明：独立 `labmate-disclosure` skill（四类交付前校验清单 + 期刊/学位论文/基金中英双语声明模板）

### P2（Roadmap，0.3.0 已提前实施两项）
- ✅ 多源文献聚合检索：`labmate_search`（arXiv+Crossref+OpenAlex 线程并发 + DOI/标题相似度双策略去重 + 单源失败降级 + 年份过滤）
- ✅ 本地 PDF 接地问答：`labmate_pdf`（**坚持零依赖，未引入 pypdf**——zlib + 手写 PDF 文本算子解析；stats/extract/search 三动作，关键词命中带页码上下文；扫描版/CID 中文/加密 PDF 诚实诊断边界）
- ✅ Zotero/pandoc 对接：以指导形式写入 labmate-literature（依赖用户本机环境，不进 server）
- ✅ 新领域模块：`labmate-fracture`（断裂力学/疲劳：K/K_IC/临界裂纹/Paris/E399 有效性，复用 handcalc+fit_lite，验证 TEMPLATE 扩展路径）
- 后续：振动/流体领域模块按需复制 TEMPLATE；多源检索可加 Semantic Scholar（需 key）

### P3（0.4.0 · 需求复核后实施：17 工具 / 15 skills）

**复核结论**：对照科研人员时间分配数据（文献 25-30% / 写作 20-25% / 数据分析 15-20% / 实验设计 15-20% / 行政 10-15%），v0.3 的 P0-P2 视野集中在"文献+计算"，六类高频刚需完全空白：统计推断、不确定度评定、实验设计、论文写作生成、BibTeX 库管理、试验曲线信号处理——"功能太少"的用户反馈成立。0.4.0 用 6 个零依赖新工具补齐，每个都有明确的时间占比依据：

| # | 工具 | 覆盖刚需 | 零依赖实现要点 |
|---|---|---|---|
| 12 | `labmate_stats` | 数据分析 15-20%（显著性/样本量是试验论文审稿刚需） | 正则化不完全 Beta（Lentz 连分数）实现 t/F 精确 p 值；不完全 Gamma（级数+连分数）实现卡方；Lanczos lnΓ；输出 Cohen's d / η² 效应量优先 |
| 13 | `labmate_errors` | 数据分析（GUM 不确定度是测试报告/学位论文法定章节） | AST 公式 + 中心差分数值偏导 + 一阶合成 + k=2 扩展；OLS 斜率截距 t 区间 |
| 14 | `labmate_doe` | 实验设计 15-20%（正交表是三/四因素试验的标准答案） | GF(p) 素数域生成 L4-L32/L9/L27/L25（正交性有数学保证，可程序化验证），而非硬编码 Taguchi 表 |
| 15 | `labmate_tex` | 写作 20-25%（三线表/图环境是投稿高频机械劳动） | booktabs 规范、CSV 直读、数值列自动右对齐、多图自动 subfigure |
| 16 | `labmate_bibtex` | 写作（多库合并/重复引用是合作写稿的常态痛苦） | 花括号配平解析、DOI 优先+标题兜底去重、字段互补合并 |
| 17 | `labmate_signal` | 数据分析（试验曲线去噪/积分/重采样） | Savitzky-Golay 闭式系数（解 (AᵀA)z=e₀，复用高斯消元）、Simpson 精确积分 |

**新增 skills**：`labmate-stats`（方法选型表 + p 值误用防护六条军规——多次比较校正、效应量优先、JB 小样本局限、样本量事前算）、`labmate-writing`（数据→三线表→图→bib 库→disclosure 的投稿标准工作流 + LaTeX 排版共识）。

**独立代码审查修复 8 个 bug**（108 项旧测试全绿仍有漏网，证明"测试通过≠实现正确"）：
1. `_latex_expr` 负号括号：`-(a+b)` 曾渲染为 `-a + b`（公式与计算结果矛盾）
2. Mohr `phi=0`（不排水黏土 τ=c 包络）被 falsy 判断静默跳过
3. 欧式 CSV（分号分隔+逗号小数）分隔符误判
4. `float("1,5".replace(",",""))` → 15 的欧式小数灾难（新增 `_parse_cell_float` 按正则区分千分位/欧式）
5. BibTeX 标题含 `%` 截断条目、`&#_` 致 LaTeX 编译错（新增 `_tex_escape`）
6. 同年同作者 BibTeX key 撞车（`used_keys` 自动 a/b 后缀，默认 key 格式保持兼容）
7. 卡方分布连分数分支 `c` 初值错误导致 df=1 时 p 值爆炸为 1e297 量级（0.4.0 编码期引入，v04 已知值测试当场抓获）
8. Savitzky-Golay 系数矩阵行变量名错误（NameError，同上当场抓获）

验收：四套单测 194 项全绿（v04 新增 86 项已知值对表验证：χ²=3.84→p=0.05、F(3,12)临界值、√2 单样本 t、Simpson x³ 精确积分、L8 正交性穷举、LHS 分层性等）。

### P4（0.4.1 · 数据入口补强：Excel 直读）

**复核结论**：调研 2.2 已指出"试验数据滞留本地仪器文件夹，**Excel 中心工作流**的转录错误与溯源断裂"（Bassetti）——但 0.4.0 的 `labmate_table` 只吃 CSV，而科研试验数据的一大半躺在 .xlsx 里。数据进不来，table→stats→fit→plot 整条链路都白搭。这是"用户数据进不来"的硬卡点，优先级高于一切新分析功能。

**方案**：不新增工具，`labmate_table` 增加 `xlsx_path` + `sheet` 参数；内部新增 `_read_xlsx` 产出 `(header, rows)` 后**完全复用既有统计链路**（`_table_summary`/`_parse_cell_float`）。坚持零依赖（zipfile + ElementTree 手工解析 OOXML，与 PDF 的 zlib 方案同思路），不引入 openpyxl。

**ECMA-376 已知坑位全处理**（每条都有 fixture 断言守护）：
| # | 坑位 | 处理 |
|---|---|---|
| ① | 空单元格在 XML 中直接缺失 → 列错位 | 按 `<c r="B3">` 列字母定位，稀疏行补空字符串 |
| ② | t="s" 共享字符串 | 查 sharedStrings.xml，富文本 `<r><t>` 段落拼接（跳过注音 rPh） |
| ③ | 字符串形态分叉 | inlineStr 读 `<is><t>`；布尔 t="b" 转 TRUE/FALSE；公式文本 t="str" 直取 |
| ④ | 日期是序列号 + styles.xml 数字格式 | 内置 numFmtId 14-22/45-47 + 自定义 formatCode 判定；1900 系统伪闰年分两段起点（serial≥61 用 1899-12-30），转 ISO 文本 |
| ⑤ | 第一个 sheet 文件名不保证 sheet1.xml | 解析 workbook.xml + rels 的 rId→target 映射 |
| ⑥ | 数值科学计数 `1.5E-3` 被当文本 | `_parse_cell_float` 增加科学计数分支（CSV 同样受益） |

**验收**：五套单测 234 项全绿（v05 新增 40 项：fixture 用 zipfile 现场构造标准 xlsx——双工作表、第一个 sheet 故意命名 zz9.xml、稀疏空位、富文本、三种日期样式、科学计数；坏文件边界覆盖老式 .xls 引导另存、纯文本伪装、缺 workbook.xml、只有表头；CSV 老路径全回归）。

---

## 7. 架构升级方案

```
labmate/
├── bin/labmate_server.py     # MCP 计算引擎：5 → 9（0.2）→ 11（0.3）→ 17 工具（0.4）
│   ├─ 计算组：convert / handcalc(+LaTeX) / mohr / fit_lite / deps
│   ├─ 数据组：table / style / signal（0.4 平滑/插值/积分）
│   ├─ 统计组：stats / errors / doe（0.4 新增）
│   ├─ 写作组：tex / bibtex（0.4 新增）
│   ├─ 文献组：arxiv / cite / search（0.3 多源聚合）
│   └─ 本地组：pdf（0.3 零依赖 PDF 接地）
├── skills/
│   ├── labmate/               # 主路由：工具优先级表（17 工具）
│   ├── labmate-stats/         # 统计设计（方法选型+误用防护，0.4 新增）
│   ├── labmate-writing/       # 论文写作工作流（0.4 新增）
│   ├── labmate-literature/    # 文献工作流（聚合+PDF 接地+Zotero/pandoc 指导）
│   ├── labmate-disclosure/    # 输出校验 + AI 披露（0.3 新增）
│   ├── labmate-fracture/      # 断裂力学领域模块（0.3 新增）
│   └── data/plot/handcalc 等  # 第〇步绑定 MCP 工具
```

工具分组原则：**确定性可复现的进 server，需要判断力/上下文的进 skill**。

---

## 8. 非功能需求

1. **零第三方依赖**：server 必须在裸 Python 3.8+ 上运行；科学栈（numpy 等）仅作为可选增强
2. **离线降级**：网络类工具（arxiv/cite）失败时返回诊断 + 缓存建议；其余工具完全离线可用
3. **数据不出本机**：所有工具本地执行，无遥测；`labmate_table` 只读不写
4. **安全求值**：handcalc 保持 AST 白名单；网络工具的超时与响应大小限制
5. **中文与编码**：Windows GBK 控制台保护（reconfigure utf-8）已在 0.1 实现，保持

---

## 9. 验收标准

- 全量单测（含 4 个新工具各 ≥4 用例）通过；stdio 冒烟含 tools/list = 9
- `labmate_arxiv`：真实网络查询返回论文（离线时返回可读诊断）
- `labmate_cite`：真实 DOI（10.1038/nature...) 返回规范 BibTeX；错误 DOI 给明确提示
- `labmate_table`：对含缺失值/混合列的 CSV 正确输出统计；中文文件名
- `labmate_style`：4 种样式返回参数字典且可写 .mplstyle 文件

## 10. 成功指标

- P1 画像验收：试验能力校核类问题的引导式应答（consult + handcalc + 量级判断）全链路演示
- 工具可复现：同一输入跨次调用结果一致（确定性）
- 扩展成本：新领域模块按 TEMPLATE 从 0 到可用 ≤ 30 分钟

---

## 附录：调研来源

工具生态：arxiv-mcp-server（blazickjp，3.1k★）、paper-search-mcp、SciencePlots（PyPI 1.0.7）、Crossref/arXiv/OpenAlex/Semantic Scholar API 文档（OpenAlex 2026 起新版需免费 key，Crossref/arXiv 无 key）
用户需求：your.phd 时间统计、Nature 研究生调查 2025（n=3785，arXiv 2608.25678）、Springer Nature × WAIC 2026 白皮书（n=10400）、2400 科学家调查（AAS 引述）、材料试验实验室数据可靠性（Bassetti）、arXiv 2511.01942 / 2511.21920 / 2605.19802
竞品：NotebookLM、Elicit、SciSpace、Consensus、scite、ResearchRabbit、Connected Papers、Jenni AI、Iris.ai（2026 对比文）

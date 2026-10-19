# LabMate 科研搭子 · 产品需求文档（PRD）

| | |
|---|---|
| 版本 | 0.2.0（基于 0.1.0 升级） |
| 日期 | 2026-10-19 |
| 状态 | P0 已实施 |
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

### P1（skill 层增强）
- 新增 `labmate-literature` skill：文献工作流（检索→筛选→精读提问模板→引用管理），绑定 P0 的 2 个工具
- `labmate-handcalc` 增强：LaTeX 输出选项（可贴 Overleaf）
- `labmate-data` 增强：明确"先 labmate_table 摸底再写脚本"的两步流程
- `labmate-plot` 增强：绑定 `labmate_style`，AI 一键注入样式
- 输出校验与 AI 使用声明模板（写入 consult/plot 的输出规范）

### P2（Roadmap）
- 多源文献聚合检索（arXiv+Crossref+OpenAlex 并发+去重）
- 本地 PDF 接地问答（pypdf，页码溯源）
- Zotero 对接、pandoc 格式转换（skill 指导）
- 新领域模块（断裂/振动/流体）按 TEMPLATE 扩展

---

## 7. 架构升级方案

```
labmate/
├── bin/labmate_server.py     # MCP 计算引擎 0.1→0.2：5 工具 → 9 工具
│   ├─ 计算组：convert / handcalc / mohr / fit_lite / deps（原有）
│   └─ 新增组：arxiv / cite / table / style（本轮 P0）
├── skills/
│   ├── labmate/               # 主路由：新增工具优先级表更新
│   ├── labmate-literature/    # 新增：文献工作流
│   └── （其余 skills 增强）
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

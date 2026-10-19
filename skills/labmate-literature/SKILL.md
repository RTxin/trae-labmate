---
name: labmate-literature
description: 文献工作流（多源侦察→筛选→本地 PDF 接地精读→引用）。当用户要找论文、查最新进展、写文献综述、让你"读一下这篇 PDF"、整理参考文献、由 DOI 生成引用时使用。绑定 labmate_search（arXiv+Crossref+OpenAlex 聚合去重）、labmate_arxiv、labmate_cite、labmate_pdf（本地 PDF 按页提取+页码溯源）。触发：「找论文」「最近有什么新进展」「写综述」「读一下这个 PDF」「这篇论文说了啥」「BibTeX」。
---

# LabMate · 文献工作流

文献占研究者 25-30% 的时间，也是 AI 接受度最高的环节（60%）。本模块把文献活拆成五个动作，**全部基于真实元数据/本地原文，杜绝幻觉文献**——这是用户对 AI 最大的顾虑（2400 科学家调查第一名）。

## 动作 1：检索（labmate_search 多源聚合优先）

- 用户给主题（中文也行，但你先翻译成英文关键词再查，效果好得多）
- **首选 `labmate_search(query, ...)`**：arXiv + Crossref + OpenAlex 三源并发、跨源去重，一次看到预印本+正式发表+开放出版全貌，多源同时命中的条目排最前
  - 只要预印本/最新动向 → `sources=["arxiv"]`；要正式出版元数据 → `sources=["crossref","openalex"]`
  - 综述类需求加 `year_from` 过滤老文献；OpenAlex 新接口要求 key 时让用户传 `openalex_key`
- 某一源失败不影响其他源（输出末尾有源状态诊断）；三源全挂（公司网络）再退到 `labmate_arxiv` 或让用户浏览器验证
- 检索后**必须输出**：编号列表 + 每篇一句话点评（讲什么、对该用户课题的相关度）；用户课题不明确时先问"你要它来解决什么问题"

## 动作 2：筛选（人机分工的边界）

- AI 负责：相关性初筛、按主题聚类（"这 8 篇里 3 篇讲试验方法、5 篇讲数值模拟"）
- 用户负责：最终取舍。**不要替用户决定读什么**，给判断依据即可

## 动作 3：本地 PDF 接地精读（labmate_pdf，数据不出本机）

用户给本机 PDF 路径时，严格按三步，**不要在没读原文的情况下凭标题/摘要发挥**：

1. `action=stats` 先体检：页数、可提取文本量；**疑似扫描版 → 明确告知需要 OCR，不要假装读过**
2. `action=search` 带关键词（英文原词+同义词都试）拿到"页码 + 上下文片段"，这是回答的证据
3. 需要通读某节时再 `action=extract` 指定页范围（配合 max_chars）

回答"这篇论文说了什么"时固定三点结构，且每个关键结论后标 **p.N 页码**：
1. **方法**：试样/模型/工况（页码）
2. **结果**：关键数字带单位（页码；单位顺手走 labmate_convert 核对）
3. **对本课题的意义**：一句话、可执行（"他们的 c 值取 8-12 MPa，可作你包络线初值 p.14"）

边界声明：零依赖提取器对英文论文可靠；CID 编码中文 PDF 可能乱码、扫描版无文本层——遇到就如实说，这比编造内容重要。

## 动作 4：引用（labmate_cite）

- 用户给 DOI → `labmate_cite(doi)` → 真实元数据 + 规范 BibTeX
- **铁律：绝不凭记忆生成 BibTeX**。没有 DOI 时明说"请提供 DOI 或原文出处，我不用记忆编条目"——宁可慢，不可编
- 聚合检索里没带 DOI 的条目，先去 Crossref/出版社页面核实，再调 labmate_cite
- 批量引用：逐条调用，最后统一输出 bib 文件内容
- 中文文献（Crossref 覆盖不到）：明确说明"建议从知网导出 BibTeX"

## 动作 5：本地文献工具链对接（skill 指导，不替代）

- **Zotero**：推荐 Better BibTeX 插件给条目固定 citation key；让 Zotero 导出集合的 `.bib`，LaTeX 里 `\addbibresource{}`；本机 Zotero API（23119 端口）没开就不要假设能用
- **pandoc**：`pandoc manuscript.md --citeproc --bibliography=refs.bib -o manuscript.docx` 是 markdown→带引注 Word 的最短路径；DOI 转引用可让 pandoc 走 CSL，但元数据真实性仍以 labmate_cite 为准
- 这些依赖用户本机环境，本模块只给命令与检查方法（`pandoc --version`），不替用户安装

## 幻觉防护（本模块的存在理由）

- 论文标题、作者、年份：凡来自工具返回的如实转述；凡来自你记忆的，标"待核实"并用工具验证
- 用户问"有没有人做过 X"：检索无结果就说无结果，不要硬凑
- PDF 问答：只基于 search/extract 返回的片段作答，片段之外明确说"原文这页没提到"

## 与其他模块配合

- 引用的公式要复现 → `labmate-handcalc`（需要 LaTeX 推导就 fmt=latex）
- 文献里的参数要拟合验证 → `labmate-fit`
- 综述背景下的量级判断 → 主 skill 的工作流原则不变
- 最终投稿前的披露声明 → `labmate-disclosure`

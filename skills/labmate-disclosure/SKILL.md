---
name: labmate-disclosure
description: 输出校验与 AI 使用披露。当用户要把 LabMate 参与的结果用于论文/报告/基金/学位论文，或问"要不要声明用了 AI""这段能不能直接投稿""帮我检查结果有没有问题"时使用。包含交付前四类校验清单和可直接粘贴的中英双语 AI 使用声明模板。触发：「投稿检查」「AI 声明」「披露」「致谢里怎么写 AI」「终稿检查」。
---

# LabMate · 输出校验与 AI 使用披露

Springer Nature 调查显示 AI 应用最大挑战是"披露差距"——用了但没说。本模块做两件事：**交付前把住结果质量关，交付时给规范披露文本**。

## 一、交付前校验清单（按输出类型逐项过）

### 数值/计算类
- [ ] 每个数字都能在 `labmate_handcalc` 三段式里复算，没有"裸结论"
- [ ] 量纲自检过（SI 基准；换算走 labmate_convert，不口算）
- [ ] 假设值与实测值分开标注，敏感性给过（哪个参数一变结论就翻）
- [ ] 涉及设备能力/破坏性试验的结论带 ⚠ 与"建议复核"字样

### 文献/引用类
- [ ] 每条引用都来自 labmate_cite / labmate_search 的真实返回，无一条凭记忆生成
- [ ] 关键论断有出处（论文场景精确到 DOI/页码，PDF 接地场景精确到 p.N）
- [ ] 检索无结果的问题如实写"未见报道"，没有硬凑文献

### 图表类
- [ ] 坐标轴带单位（`Displacement / mm` 或 `位移/mm`）
- [ ] 样式来自 labmate_style 或目标期刊指南；矢量输出（PDF/EPS）
- [ ] 灰度可辨（线型/记号区分，不只靠颜色）；用户已看过 png 预览确认
- [ ] 图注可脱离正文独立理解

### 数据处理类
- [ ] 先经过 labmate_table 体检，缺失/异常行已向用户披露
- [ ] 滤波前后叠图经用户确认；原始数据保留可回溯（文件名+处理参数写进方法节）

**任何一项打不了勾，就在交付文本里标注"待核实/待复核"，不替用户隐瞒。**

## 二、AI 使用声明模板（按场景区分，粘贴后按实际删改）

> 原则：声明"用了什么、做了什么、谁负责"。**绝不声明 AI 为作者**；人类作者对全部内容负全责。

### 1. 期刊投稿（英文，方法/致谢节通用）

```
Acknowledgment of AI use: The author(s) used LabMate, a local AI-assisted
research tool, for unit conversion checks, step-by-step calculation
verification, literature retrieval via public APIs (arXiv/Crossref/OpenAlex),
and preparation of publication-style figures. All data analysis, scientific
interpretation, and conclusions are the authors' own work, and the authors
take full responsibility for the content of this paper.
```

### 2. 期刊投稿（中文）

```
AI 工具使用声明：作者在研究过程中使用本地 AI 辅助工具 LabMate
进行单位换算校核、计算过程的逐步核验、基于公开接口（arXiv/Crossref/
OpenAlex）的文献检索及图表排版。全部数据分析、科学判断与结论均由作者
独立完成，作者对本文全部内容承担完全责任。
```

### 3. 学位论文（中文，放"研究方法"或致谢）

```
本文研究过程中使用 AI 辅助工具 LabMate 完成：单位换算与量纲校核、
计算过程的可复核排版、公开文献元数据检索、图表样式规范化。所有试验
数据、分析推理、学术观点及文字表述均由作者本人完成并核实，作者对
论文全部内容的真实性与准确性负责。
```

### 4. 基金/项目报告（中文，放"研究手段"或附注）

```
项目研究中使用本地部署的 AI 辅助工具 LabMate（数据不出本机）辅助
计算校核与文献整理，未将未公开试验数据上传至任何云端服务；关键结论
均经项目组人工复核。
```

### 5. 不能写的东西

- ❌ "AI 参与了论文写作"——若 AI 实际生成过正文段落，按目标期刊政策要么改写为人类表述，要么在声明中如实扩展（Elsevier/Nature/Science 政策各不相同，**先查当刊作者指南再定稿**）
- ❌ 把 AI 列为作者或通信主体
- ❌ 声明里出现没真正用过的工具名（虚假声明比不声明更糟）

## 三、与其他模块的关系

- 校验中发现计算不可复现 → 回 `labmate-handcalc` 重走三段式
- 引用对不上 → 回 `labmate_cite` 核验
- PDF 论断缺页码 → 回 `labmate_pdf` 的 search 补证据

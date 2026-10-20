# LabMate 科研搭子 · Trae 插件

> 为"专注科研、不研究 AI"的领域专家设计——先把你没说出口的参数问出来，再用趁手的工具把活干完。

## 为什么做这个插件

领域专家用 AI 的最大障碍不是 AI 不行，而是**隐性知识没有显性化**：一张试验装置图发过去，图上只有符号没有数值；问"设备够不够"，脑子里有完整工况但说出来的只有半句。通用对话拿到这种输入只能瞎猜，专家于是得出"AI 没一个能打的"。

LabMate 的灵魂是一个**引导协议**：AI 像研究生一样先把缺失参数问清楚（先复述读图、再反问、同时给假设性量级判断），然后交给工具模块干活——每个计算给教科书式过程，可逐步校核，透明产生信任。

## 架构（可扩展是第一设计原则）

```
labmate/
├── .trae-plugin/plugin.json          # 插件清单（skills + MCP server 声明）
├── bin/
│   ├── labmate_server.py             # MCP 计算引擎（Python 零依赖，二十件套）
│   ├── test_server.py / test_server_v02.py / test_server_v03.py / test_server_v04.py / test_server_v05.py / test_server_v06.py / test_server_v07.py / test_server_v08.py / test_server_v09.py / test_server_v10.py / test_server_v11.py / test_server_v12.py / test_server_v13.py / test_server_v14.py  # 全量单测
├── skills/
│   ├── labmate/            # 主 skill：MCP 工具优先级 + 任务路由 + 工作流原则
│   ├── labmate-consult/    # 试验咨询引导协议（识图/参数补全/量级校核）
│   ├── labmate-units/      # 单位与量纲（pint）        labmate-handcalc/ 教科书式手算（含 LaTeX）
│   ├── labmate-fit/        # 数据拟合与参数反演（lmfit） labmate-data/     试验数据处理
│   ├── labmate-stats/      # 统计分析与实验设计（误用防护）
│   ├── labmate-writing/    # 论文写作与 LaTeX/BibTeX 生成
│   ├── labmate-symbols/    # 符号推导（sympy）           labmate-fem/       有限元工具链
│   ├── labmate-plot/       # 论文级图表                  labmate-rockmech/  岩石力学领域模块
│   ├── labmate-fracture/   # 断裂力学/疲劳领域模块       labmate-literature/ 文献工作流
│   ├── labmate-vibration/  # 振动领域模块（频谱/固有频率）
│   ├── labmate-grant/      # 基金申请书写作引导（四问协议/评审视角/工具链）
│   └── labmate-disclosure/ # 输出校验 + AI 使用披露模板
├── TEMPLATE-SKILL.md       # 新领域模块模板
└── README.md
```

**两层分工**：`bin/labmate_server.py` 是"手"——MCP 计算引擎（v0.5.0，二十件套，全部零第三方依赖，纯标准库可跑）：

- 计算/本地组（完全离线）：`labmate_convert` 单位换算、`labmate_handcalc` 三段式计算排版（AST 白名单安全求值，**fmt=latex 直接输出可贴 Overleaf 的 align\* 推导**）、`labmate_mohr` Mohr 圆+包络+SVG、`labmate_fit_lite` 内置最小二乘（linear/poly/power/exp + **multi 多元线性回归——系数 t 检验（显著/不显著）、调整 R²（惩罚多余变量）、整体 F 检验；x 按变量分组或按样本分行自动转置，共线自动拦截**）、`labmate_table` 本机 CSV/**Excel(.xlsx)** 数据体检（只读不写，美式/欧式/科学计数数字通吃；xlsx 零依赖解析 zipfile+XML：多工作表选择、稀疏空位防列错位、sharedStrings 富文本、日期序列号转 ISO）、`labmate_style` 期刊绘图样式（ieee/nature/science/中文期刊）、`labmate_deps` 科学栈体检、**`labmate_pdf` 本地 PDF 零依赖处理（stats 体检/extract 按页提取/search 关键词页码溯源，扫描版诚实诊断，数据不出本机）**
- 统计组（零依赖精确 p 值，与 scipy 对表验证）：**`labmate_stats` 统计推断（t 检验单样本/Welch/配对、ANOVA+事后两两比较——Tukey HSD 学生化极差零依赖数值积分/Holm/Bonferroni、corr 相关性 Pearson/Spearman、nptest 非参数检验——Mann-Whitney 组合计数精确 p/Kruskal-Wallis ties 校正、Jarque-Bera 正态性、t 置信区间、样本量功效估算；outlier 异常值剔除——GB/T 4883 格拉布斯 t 精确临界+狄克松国标表，歧离值/统计离群值两级判定、迭代剔除；weibull 脆性强度分析——中位秩线性回归出模数 m/特征强度 σ₀/B10/给定应力破坏概率；sn S-N 疲劳拟合——Basquin σᵃ·N=C 双对数回归出指数 a/系数 C，给定应力预测疲劳寿命，外推明示，runout 警示）**、**`labmate_errors` GUM 不确定度传播（公式合成 u_c+k=2 扩展、各分量贡献占比）与回归参数 95%CI**、**`labmate_doe` 实验设计（素数域 GF(p) 生成 L4-L32 正交表，正交性有数学保证；全因子；拉丁超立方分层抽样）**
- 数据/写作组（完全离线）：**`labmate_signal` 试验曲线信号处理（移动平均/Savitzky-Golay 保峰形平滑、线性插值不外推、梯形/Simpson 精确积分、均匀重采样；spectrum FFT 频谱——radix-2 零依赖实现，非二次幂自动零填充并明示，单边幅值谱+频率分辨率 Δf/Nyquist/主峰定位，振动测试的固有频率识别不再依赖 MATLAB）**、**`labmate_plot` 论文级 SVG 绘图（零依赖手写 SVG：折线/散点/误差棒/分组柱状、双组对比、对数轴、1-2-5 优雅刻度、图例框；bar 柱状支持类别轴、双系列并列与误差帽，可直接另存 .svg 嵌入论文）**、**`labmate_curve` 试验曲线特征提取（弹性模量 E 初始段回归+R²、0.2% 偏移屈服强度线性插值交点、峰值强度、断裂末点、总能量 Simpson/梯形自动选择；batch 模式平行试样批量出均值±标准差汇总——拉伸/压缩/直剪曲线一键出报告）**、**`labmate_tex` LaTeX 写作生成（booktabs 三线表 CSV 直读+数值列自动右对齐、多图自动 subfigure、带编号公式）**、**`labmate_docx` Word(.docx) 文档零依赖生成（手工构造 OOXML+zipfile 打包：标题挂大纲级别导航窗格可跳转可插目录、正文宋体+Times New Roman 小四 1.5 倍行距首行缩进 2 字符、三线表顶底线 1.5pt/表头线 0.5pt/无竖线/跨页自动重复表头/数值列自动右对齐，CSV 直读或内联 rows；Word/WPS 直接打开续写）**、**`labmate_bibtex` 参考文献库工作台（缺字段/重复 key/DOI 体检、跨库去重合并、按年/作者重排；gb7714 直出 GB/T 7714-2015 参考文献表——顺序编码制/著者-出版年制，西文姓前名缩写全大写，作者超 3 位截断等/et al）**
- 文献组（标准库 urllib）：`labmate_arxiv` arXiv 真实检索、`labmate_cite` Crossref DOI→真实 BibTeX（杜绝幻觉引用，撞 key 自动加 a/b 后缀）、**`labmate_search` 多源聚合（arXiv+Crossref+OpenAlex 线程并发+DOI/标题双策略跨源去重，单源失败自动降级并给诊断，支持年份过滤）**

skills 是"脑"——17 个科研引导模块：主路由、试验咨询（含试验大纲 docx 落盘出口）、单位、手算、拟合、数据、**统计设计（方法选型+p 值误用防护+DOE 常识）**、**写作（三线表/bib 库标准工作流+LaTeX 排版共识）**、符号、FEM、图表、岩石力学、断裂力学（按模板扩展的第二个领域实证）、**振动（采样定理/FFT 频谱/固有频率/混叠红线，与 labmate_signal 的 spectrum 动作配套，按模板扩展的第三个领域实证）**、**基金申请书（四问协议+评审视角死因清单+search/power/doe/handcalc/plot/docx/gb7714/disclosure 全工具链衔接，0.5.0 新增）**、文献工作流（聚合检索→本地 PDF 接地精读→真实引用→Zotero/pandoc 对接指导）、披露合规（交付前四类校验清单 + 中英双语 AI 使用声明模板）。AI 被指示优先调用 MCP 工具而非现场手写脚本。

**产品决策依据**：见 `docs/PRD.md`（基于双路调研：研究者时间分配与信任度数据 + 九款 AI 科研产品竞品矩阵；差异化定位 = 文献之外的两块空白——本机试验数据与 AI 新手引导，以及"本地优先/数据不出本机"）。全量单测见 `bin/test_server*.py`（含 PDF 解析、跨源去重、LaTeX 渲染、xlsx/docx 构造与 zipfile 回读的离线 fixture、SVG 结构与曲线已知值断言）。

**扩展方式（零改动主框架）**：
1. 复制 `TEMPLATE-SKILL.md`，填入新领域（振动、流体、热学……；断裂力学 `labmate-fracture` 是完整示例）
2. 放到 `skills/labmate-<domain>/`
3. 在主 skill 的路由表加一行

## 安装

把 `skills/` 下各目录复制到 `~/.trae-cn/skills/`（或作为标准插件包整体安装）：

```
~/.trae-cn/skills/labmate/SKILL.md
~/.trae-cn/skills/labmate-consult/SKILL.md
...（每个模块一个目录）
```

依赖按需安装（AI 会在用时提示）：

```bash
pip install pint handcalcs lmfit sympy scikit-fem gmsh meshio pyvista
```

## 使用示例

对着装置图问："用这个组合试样做直剪，试验机最大 150kN，需要给试样加侧向约束吗？"

LabMate 的应答方式：先复述读到的图（结构/符号/缺的数值）→ 反问剪切面尺寸、期望应力水平 → **同时**给假设性量级判断（"若剪切面积 250cm²，满载也只有 60MPa，低于这类脆性材料的抗剪强度量级——这不是约束问题，是吨位问题"）→ 你补上参数后走 handcalc 出教科书式校核过程。

## 设计原则

1. **先补全，再回答**——缺参数就问，但每次都附带假设性初步判断，不干等
2. **结论必带过程**——handcalcs 排版，每步可校核
3. **量纲自检**——pint 带量纲计算，拦截低级事故
4. **诚实边界**——工具链覆盖不了的明确说"建议商业软件"，不硬做
5. **照顾 AI 新手**——回答结构化，顺手教一句提问模板，不说教

## 使用许可

- ✅ 允许个人使用（学习 / 科研 / 个人非营利）
- ❌ 禁止商用
- ❌ 禁止政府单位使用（特别是那些爱搞人情世故与论资排辈的）

详见 [LICENSE](LICENSE)，需要商业或机构授权请通过仓库联系作者。

【1024Builder作品秀】· 模块化架构，欢迎按模板贡献新领域模块

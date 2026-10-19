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
│   ├── labmate_server.py             # MCP 计算引擎（Python 零依赖，五工具）
│   └── test_server.py                # 20 项单测 + stdio 冒烟（全部通过）
├── skills/
│   ├── labmate/            # 主 skill：MCP 工具优先级 + 任务路由 + 工作流原则
│   ├── labmate-consult/    # 试验咨询引导协议（识图/参数补全/量级校核）
│   ├── labmate-units/      # 单位与量纲（pint）        labmate-handcalc/ 教科书式手算
│   ├── labmate-fit/        # 数据拟合与参数反演（lmfit） labmate-data/     试验数据处理
│   ├── labmate-symbols/    # 符号推导（sympy）           labmate-fem/       有限元工具链
│   ├── labmate-plot/       # 论文级图表                  labmate-rockmech/  领域模块示例
├── TEMPLATE-SKILL.md       # 新领域模块模板
└── README.md
```

**两层分工**：`bin/labmate_server.py` 是"手"——MCP 计算引擎（v0.2.0，九件套，全部零第三方依赖）：计算组 `labmate_convert` 单位换算、`labmate_handcalc` 三段式计算排版（AST 安全求值）、`labmate_mohr` Mohr 圆+包络+SVG、`labmate_fit_lite` 内置最小二乘、`labmate_table` 本机试验数据体检（CSV 列统计，只读不写）、`labmate_style` 期刊绘图样式注入（SciencePlots 逆向：ieee/nature/science/中文期刊）、`labmate_deps` 科学栈体检；文献组 `labmate_arxiv`（官方免费 API 真实检索）、`labmate_cite`（Crossref DOI→真实 BibTeX，杜绝幻觉引用）。skills 是"脑"——科研引导协议与复杂分析（含新增的 labmate-literature 文献工作流：检索→筛选→精读→引用，幻觉防护铁律）。AI 被指示优先调用 MCP 工具而非现场手写脚本。

**产品决策依据**：见 `docs/PRD.md`（基于双路调研：研究者时间分配与信任度数据 + 九款 AI 科研产品竞品矩阵；本插件的差异化定位 = 文献之外的两块空白——本机试验数据与 AI 新手引导）。**50 项单测**（`bin/test_server.py` + `bin/test_server_v02.py`）全部通过。

**扩展方式（零改动主框架）**：
1. 复制 `TEMPLATE-SKILL.md`，填入新领域（断裂力学、振动、流体、热学……）
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

【1024Builder作品秀】· 模块化架构，欢迎按模板贡献新领域模块

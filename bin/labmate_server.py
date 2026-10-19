#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabMate MCP Server —— 科研搭子计算引擎

LabMate 插件的"手"：skills 层负责科研引导（脑），本 server 提供确定性计算工具，
让 AI 从"现场手写脚本"变成"调用真实工具"。

零第三方依赖（Python 3.8+），stdio newline-delimited JSON-RPC 2.0。

工具（0.4.2 · 十九件套）：
  计算组（零依赖，离线可用）：
  labmate_convert   力学单位换算（内置换算表）
  labmate_handcalc  三段式计算排版：公式 → 代入 → 结果（AST 白名单安全求值，支持 LaTeX 输出）
  labmate_mohr      Mohr 圆计算 + 纯 Python SVG 绘图
  labmate_fit_lite  内置最小二乘拟合（线性/二次/指数/幂律）+ R²
  labmate_errors    不确定度传播（GUM 一阶数值偏导）+ 线性回归参数区间
  统计组（零依赖，t/F/卡方分布精确尾概率）：
  labmate_stats     描述统计 / t 检验(单样本/两样本Welch/配对) / 单因素 ANOVA / JB 正态性 / 置信区间 / 样本量
                   异常值剔除(GB/T 4883 格拉布斯/狄克松，歧离值与统计离群值两级判定) / Weibull 强度分析
  设计组（零依赖）：
  labmate_doe       正交表(L4~L32/L9/L27/L25，素数域生成) / 全因子 / 拉丁超立方
  labmate_signal    移动平均与 Savitzky-Golay 平滑 / 线性插值 / 梯形与 Simpson 积分 / 重采样
                   FFT 频谱分析（radix-2 零依赖实现，非二次幂自动零填充并明示）
  数据组（零依赖，只读本机）：
  labmate_table    本机试验数据体检：CSV / Excel(.xlsx) 读取 + 列统计摘要（零依赖，xlsx 走 zipfile+XML）
  labmate_style    期刊绘图样式注入：ieee/nature/science/中文期刊（SciencePlots 逆向）
  labmate_deps     科学栈体检（探测 numpy/scipy/lmfit/sympy/matplotlib/pyvista）
  绘图组（零依赖 SVG，数据不出本机）：
  labmate_plot     论文级 SVG 绘图：折线/散点/误差棒、双组对比、对数轴、图例（1-2-5 优雅刻度）
  labmate_curve    试验曲线特征提取：弹性模量 E（含 R²）/ 0.2% 偏移屈服 / 峰值强度 / 总能量
  写作组（零依赖）：
  labmate_tex      LaTeX 三线表(booktabs)/图环境/公式环境生成
  labmate_bibtex   BibTeX 库体检（必填字段/重复 key/DOI/标题）与多文件去重合并
  文献组（标准库 urllib，需联网）：
  labmate_arxiv    arXiv 检索（官方免费 API，无需 key）
  labmate_cite     DOI → 真实元数据 + 规范 BibTeX（Crossref，杜绝幻觉引用；可对既有库 key 去重）
  labmate_search   多源文献聚合：arXiv + Crossref + OpenAlex 并发检索 + 跨源去重
  本地组（零依赖，离线可用，数据不出本机）：
  labmate_pdf      本地 PDF 按页文本提取 + 关键词页码溯源（接地问答素材，扫描版诚实诊断）

用法（注册为 MCP stdio server）：
  python labmate_server.py
"""

import ast
import bisect
import concurrent.futures
import csv
import datetime
import difflib
import io
import json
import math
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib

PROTOCOL_VERSION = "2024-11-05"
SERVER_VERSION = "0.4.5"

# ======================================================================
# 1. 单位换算引擎
# ======================================================================
# 每个量纲一张表：基准单位 -> {别名: 因子}。因子含义：1 别名单位 = 因子 × 基准单位
UNITS = {
    "force": {
        "base": "N", "label": "力",
        "factors": {
            "N": 1.0, "kN": 1e3, "MN": 1e6, "GN": 1e9,
            "kgf": 9.80665, "tf": 9806.65,
            "lbf": 4.4482216152605, "kip": 4448.2216152605, "dyn": 1e-5,
        },
    },
    "stress": {
        "base": "Pa", "label": "应力/压强",
        "factors": {
            "Pa": 1.0, "kPa": 1e3, "MPa": 1e6, "GPa": 1e9,
            "bar": 1e5, "atm": 101325.0,
            "psi": 6894.757293168, "ksi": 6894757.293168,
            "kgf/cm2": 98066.5, "kgf/mm2": 9806650.0,
        },
    },
    "length": {
        "base": "m", "label": "长度",
        "factors": {
            "m": 1.0, "cm": 0.01, "mm": 1e-3, "um": 1e-6, "km": 1e3,
            "in": 0.0254, "ft": 0.3048, "mile": 1609.344,
        },
    },
    "energy": {
        "base": "J", "label": "能量/功",
        "factors": {
            "J": 1.0, "kJ": 1e3, "MJ": 1e6,
            "cal": 4.184, "kcal": 4184.0,
            "Wh": 3600.0, "kWh": 3.6e6,
            "ft.lbf": 1.3558179483314, "BTU": 1055.05585262,
        },
    },
    "power": {
        "base": "W", "label": "功率",
        "factors": {"W": 1.0, "kW": 1e3, "MW": 1e6, "hp": 745.6998715823, "PS": 735.49875},
    },
    "pressure_rate": {
        "base": "Pa/s", "label": "加载速率（应力速率）",
        "factors": {"Pa/s": 1.0, "MPa/s": 1e6, "GPa/s": 1e9, "kPa/s": 1e3},
    },
}

def find_unit_dim(name):
    for dim, cfg in UNITS.items():
        if name in cfg["factors"]:
            return dim, cfg
    return None, None

def tool_convert(args):
    value = float(args["value"])
    src, dst = args["from"].strip(), args["to"].strip()
    d1, c1 = find_unit_dim(src)
    d2, c2 = find_unit_dim(dst)
    if d1 is None or d2 is None:
        unknown = [u for u in (src, dst) if find_unit_dim(u)[0] is None]
        known = {cfg["label"]: sorted(set(cfg["factors"])) for cfg in UNITS.values()}
        return ("❌ 未识别单位：%s\n支持的单位：\n%s" %
                (", ".join(unknown),
                 "\n".join("  %s: %s" % (k, ", ".join(v)) for k, v in known.items())))
    if d1 != d2:
        return ("❌ 量纲不匹配：%s（%s）与 %s（%s）不能互转" %
                (src, c1["label"], dst, c2["label"]))
    v_base = value * c1["factors"][src]
    v_out = v_base / c2["factors"][dst]
    chain = "%s %s = %g %s (基准) = %s %s" % (
        value, src, v_base, c1["base"], _fmt(v_out), dst)
    return "%s %s = **%s %s**\n\n换算链：%s" % (
        _fmt(value), src, _fmt(v_out), dst, chain)

def _fmt(x):
    """科学计数友好格式：大数小数用 4 位有效数字"""
    if x == 0:
        return "0"
    a = abs(x)
    if 1e-3 <= a < 1e6:
        s = "%.6g" % x
        return s
    return "%.4e" % x

# ======================================================================
# 2. 三段式计算排版（AST 白名单安全求值）
# ======================================================================
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Mod,
    ast.Name, ast.Load,
)
_MATH_NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau}

def _safe_eval(expr, variables):
    """白名单 AST 求值：只允许算术运算与已声明的变量/常数，杜绝 eval 注入。"""
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ValueError("不允许的语法元素：%s（只支持算术表达式）" % type(node).__name__)
        if isinstance(node, ast.Name) and node.id not in variables and node.id not in _MATH_NAMES:
            raise ValueError("未声明变量：%s（请先在 vars 中给出数值）" % node.id)
    return eval(  # noqa: S307 —— AST 已白名单校验，仅算术与已声明变量
        compile(tree, "<handcalc>", "eval"),
        {"__builtins__": {}}, {**_MATH_NAMES, **variables})

_GREEK = {"tau": r"\tau", "sigma": r"\sigma", "phi": r"\phi", "alpha": r"\alpha",
          "beta": r"\beta", "gamma": r"\gamma", "delta": r"\delta", "epsilon": r"\varepsilon",
          "theta": r"\theta", "mu": r"\mu", "nu": r"\nu", "rho": r"\rho",
          "pi": r"\pi", "lam": r"\lambda", "kappa": r"\kappa"}

def _latex_name(name):
    """Python 变量名 → LaTeX 数学符号：tau_u → \\tau_{u}，A_s → A_{s}。"""
    parts = name.split("_")
    head = _GREEK.get(parts[0], parts[0])
    if len(parts) > 1:
        return "%s_{%s}" % (head, "".join(parts[1:]))
    return head

def _latex_num(x):
    """数值 → LaTeX：2.5e-03 → 2.5\\times10^{-3}。"""
    s = _fmt(x)
    if "e" in s or "E" in s:
        m, e = re.split("[eE]", s)
        return "%s\\times10^{%d}" % (m, int(e))
    return s

def _latex_expr(node):
    """把已过白名单的算术 AST 渲染为 LaTeX（独立纯函数便于单测）。"""
    if isinstance(node, ast.Expression):
        return _latex_expr(node.body)
    if isinstance(node, ast.Constant):
        return _latex_num(float(node.value))
    if isinstance(node, ast.Name):
        return _latex_name(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        sign = "-" if isinstance(node.op, ast.USub) else "+"
        inner = _latex_expr(node.operand)
        if isinstance(node.operand, ast.BinOp) and isinstance(node.operand.op, (ast.Add, ast.Sub)):
            inner = "\\left(%s\\right)" % inner  # -(a+b) → -\left(a + b\right)
        return sign + inner
    if isinstance(node, ast.BinOp):
        l, r = _latex_expr(node.left), _latex_expr(node.right)
        if isinstance(node.op, ast.Add):
            return "%s + %s" % (l, r)
        if isinstance(node.op, ast.Sub):
            return "%s - %s" % (l, r)
        if isinstance(node.op, ast.Mult):
            return "%s \\cdot %s" % (l, r)
        if isinstance(node.op, ast.Div):
            return "\\frac{%s}{%s}" % (l, r)
        if isinstance(node.op, ast.Pow):
            if isinstance(node.left, (ast.BinOp, ast.UnaryOp)):
                l = "\\left(%s\\right)" % l  # (-2)**2 → \left(-2\right)^{2}
            return "{%s}^{%s}" % (l, r)
        if isinstance(node.op, ast.Mod):
            return "%s \\bmod %s" % (l, r)
    raise ValueError("LaTeX 渲染不支持的节点：%s" % type(node).__name__)

def tool_handcalc(args):
    """输入符号与表达式，输出"公式 → 代入 → 结果"三段式；fmt=latex 输出可贴 Overleaf 的 align*。"""
    variables = {k: float(v) for k, v in args.get("vars", {}).items()}
    steps = args.get("steps", [])
    fmt = str(args.get("fmt", "md")).lower()
    if fmt not in ("md", "latex"):
        return "❌ fmt 仅支持 md（默认）或 latex"
    if not steps:
        return "❌ steps 为空：每个元素 {symbol, formula, note?, unit?}，formula 为 Python 算术表达式"
    if fmt == "latex":
        out = ["**可直接粘贴到 Overleaf 的 LaTeX 推导**\n", "\\begin{align*}"]
        if variables:
            out.append("\\intertext{已知量}")
            out.append(" & ".join("%s = %s" % (_latex_name(k), _latex_num(v))
                                  for k, v in variables.items()) + r" \\")
        defined = dict(variables)
        for i, st in enumerate(steps, 1):
            sym, formula, note = st.get("symbol"), st.get("formula", ""), st.get("note", "")
            if not sym or not formula:
                return "❌ 第 %d 步缺 symbol 或 formula" % i
            try:
                tree = ast.parse(formula, mode="eval")
                val = _safe_eval(formula, defined)
                expr_tex = _latex_expr(tree)
            except Exception as exc:
                return "❌ 第 %d 步求值失败：%s" % (i, exc)
            tail = " \\quad (\\text{%s})" % note.replace("}", "\\}").replace("{", "\\{") if note else ""
            out.append("%s &= %s = %s%s \\\\" %
                       (_latex_name(sym), expr_tex, _latex_num(val), tail))
            defined[sym] = val
        out.append("\\end{align*}")
        out.append("\n```latex\n" + "\n".join(out[2:]) + "\n```")
        out.append("（unit 为可选纯文本注释；中文单位建议用 md 格式。假设值请在 note 标来源。）")
        return "\n".join(out)
    out, defined = [], dict(variables)
    out.append("**计算过程（可逐步校核）**\n")
    for i, st in enumerate(steps, 1):
        sym, formula, note = st.get("symbol"), st.get("formula", ""), st.get("note", "")
        if not sym or not formula:
            return "❌ 第 %d 步缺 symbol 或 formula" % i
        try:
            val = _safe_eval(formula, defined)
        except Exception as exc:
            return "❌ 第 %d 步求值失败：%s" % (i, exc)
        subs = ", ".join("%s=%s" % (k, _fmt(v)) for k, v in variables.items()) if i == 1 else ""
        unit = st.get("unit", "")
        line = "%d. **%s = %s**" % (i, sym, formula)
        if note:
            line += "    # %s" % note
        out.append(line)
        if subs:
            out.append("   代入：%s" % subs)
        out.append("   **%s = %s%s**\n" % (sym, _fmt(val), (" " + unit) if unit else ""))
        defined[sym] = val
    out.append("（假设值请在 note 中标注来源；每步均可复算校核。需要 LaTeX 版可传 fmt=latex）")
    return "\n".join(out)

# ======================================================================
# 3. Mohr 圆计算 + SVG
# ======================================================================
def tool_mohr(args):
    pairs = args.get("stress_pairs", [])
    c, phi = args.get("c"), args.get("phi_deg")
    if not pairs:
        return "❌ stress_pairs 为空：主应力对列表，如 [[s1, s3], ...]（MPa）"
    circles = []
    for p in pairs:
        s1, s3 = float(p[0]), float(p[1])
        if s1 < s3:
            s1, s3 = s3, s1
        circles.append((s1, s3, (s1 + s3) / 2.0, (s1 - s3) / 2.0))
    lines = ["**Mohr 圆计算结果**\n"]
    for s1, s3, sc, r in circles:
        lines.append("- σ1=%s, σ3=%s → 圆心 σc=%s, 半径 r=%s（最大剪应力 τmax = %s）" %
                     (_fmt(s1), _fmt(s3), _fmt(sc), _fmt(r), _fmt(r)))
    if c is not None and phi is not None:
        phi_r = math.radians(phi)
        lines.append("\n**Mohr-Coulomb 包络**：τ = %s + σn·tan(%s°)，tanφ = %s" %
                     (_fmt(c), phi, _fmt(math.tan(phi_r))))
        # 判断每个圆与包络的关系（教学级初判：圆是否被包络穿过）
        for s1, s3, sc, r in circles:
            # 包络线到圆心的距离（直线 τ = c + σ·tanφ 的一般式距离）
            A, B, C = -math.tan(phi_r), 1.0, -c
            dist = abs(A * sc + B * 0.0 + C) / math.hypot(A, B)
            state = "已破坏（圆与包络相交/相切）" if r >= dist else "未破坏"
            lines.append("- 圆(σc=%s, r=%s)：距包络 %s，r=%s → **%s**" %
                         (_fmt(sc), _fmt(r), _fmt(dist), _fmt(r), state))
    svg = _mohr_svg(circles, c, phi)
    save = args.get("save_svg")
    if save:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(save)), exist_ok=True)
            with open(save, "w", encoding="utf-8") as f:
                f.write(svg)
            lines.append("\nSVG 已保存：%s" % save)
        except Exception as exc:
            lines.append("\n⚠ SVG 保存失败：%s" % exc)
    else:
        lines.append("\n（如需保存图：加参数 save_svg=<路径>）")
    return "\n".join(lines)

def _mohr_svg(circles, c, phi, w=520, h=400):
    """纯字符串模板生成 Mohr 圆 SVG（零依赖绘图）。"""
    if not circles:
        return ""
    allv = [v for s1, s3, _, _ in circles for v in (s1, s3)]
    xmax = max(allv) * 1.15 or 1.0
    ymin = -max(r for _, _, _, r in circles) * 1.15
    ymax = max(r for _, _, _, r in circles) * 1.15
    ymin = min(ymin, 0)
    def X(v): return 40 + (v / xmax) * (w - 80)
    def Y(v): return h / 2 - (v / (ymax - ymin + 1e-9)) * (h - 60)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" font-family="serif">' % (w, h)]
    parts.append('<line x1="40" y1="%f" x2="%d" y2="%f" stroke="#333" stroke-width="1.2"/>' % (Y(0), w - 20, Y(0)))
    parts.append('<line x1="%f" y1="20" x2="%f" y2="%d" stroke="#333" stroke-width="1.2"/>' % (X(0), X(0), h - 20))
    for i, (_, _, sc, r) in enumerate(circles):
        rx = abs(X(sc + r) - X(sc - r))
        ry = abs(Y(0) - Y(r))
        parts.append('<ellipse cx="%f" cy="%f" rx="%f" ry="%f" fill="none" stroke="#1a5276" stroke-width="1.4"/>' %
                     (X(sc), Y(0), rx, ry))
        parts.append('<text x="%f" y="%f" font-size="11" fill="#555" text-anchor="middle">σc=%g, r=%g</text>' %
                     (X(sc), Y(-r) + 14, sc, r))
    if c is not None and phi is not None:
        phi_r = math.radians(phi)
        x2 = xmax
        y2 = c + x2 * math.tan(phi_r)
        parts.append('<line x1="%f" y1="%f" x2="%f" y2="%f" stroke="#c0392b" stroke-width="1.6" stroke-dasharray="6 4"/>' %
                     (X(0), Y(c), X(x2), Y(y2)))
        parts.append('<text x="%f" y="%f" font-size="12" fill="#c0392b">τ = %.2f + σ·tan(%.1f°)</text>' %
                     (w - 210, Y(y2) - 6, c, phi))
    parts.append('<text x="%d" y="%d" font-size="12">σ / MPa</text></svg>' % (w - 80, Y(0) - 10))
    return "".join(parts)

# ======================================================================
# 4. 内置最小二乘拟合
# ======================================================================
def _polyfit(xs, ys, deg):
    n, m = len(xs), deg + 1
    A = [[math.pow(x, p) for p in range(m)] + [y] for x, y in zip(xs, ys)]
    # 高斯消元解正规方程（零依赖）
    M = [[sum(A[k][i] * A[k][j] for k in range(n)) for j in range(m)] + [sum(A[k][i] * A[k][m] for k in range(n))] for i in range(m)]
    for i in range(m):
        piv = max(range(i, m), key=lambda r: abs(M[r][i]))
        if abs(M[piv][i]) < 1e-12:
            return None
        M[i], M[piv] = M[piv], M[i]
        for r in range(i + 1, m):
            f = M[r][i] / M[i][i]
            for c2 in range(i, m + 1):
                M[r][c2] -= f * M[i][c2]
    coef = [0.0] * m
    for i in range(m - 1, -1, -1):
        s = M[i][m] - sum(M[i][j] * coef[j] for j in range(i + 1, m))
        coef[i] = s / M[i][i]
    return coef

def tool_fit(args):
    xs = [float(v) for v in args.get("x", [])]
    ys = [float(v) for v in args.get("y", [])]
    model = args.get("model", "linear")
    n = len(xs)
    if n < 2 or n != len(ys):
        return "❌ x/y 需等长且至少 2 个点"
    if model in ("linear", "poly", "polynomial"):
        deg = int(args.get("degree", 1))
        coef = _polyfit(xs, ys, deg)
        if coef is None:
            return "❌ 奇异：数据退化（如全部同 x），请检查"
        yh = [sum(coef[p] * math.pow(x, p) for p in range(deg + 1)) for x in xs]
        expr = " + ".join("%s·x^%d" % (_fmt(c2), p) for p, c2 in enumerate(coef[::-1]))
    elif model in ("power",):
        if any(v <= 0 for v in xs + ys):
            return "❌ 幂律拟合要求 x、y 全部为正"
        lx, ly = [math.log(v) for v in xs], [math.log(v) for v in ys]
        coef = _polyfit(lx, ly, 1)
        if coef is None:
            return "❌ 拟合失败"
        a, b = coef[1], coef[0]
        yh = [math.exp(b) * math.pow(x, a) for x in xs]
        expr = "y = %s·x^(%s)" % (_fmt(math.exp(b)), _fmt(a))
    elif model in ("exp", "exponential"):
        if any(v <= 0 for v in ys):
            return "❌ 指数拟合要求 y 全部为正"
        lx, ly = xs, [math.log(v) for v in ys]
        coef = _polyfit(lx, ly, 1)
        if coef is None:
            return "❌ 拟合失败"
        yh = [math.exp(coef[0]) * math.exp(coef[1] * x) for x in xs]
        expr = "y = %s·exp(%s·x)" % (_fmt(math.exp(coef[0])), _fmt(coef[1]))
    else:
        return "❌ 未知模型 %s：支持 linear/poly、power、exp" % model
    ybar = sum(ys) / n
    ss_res = sum((y - yh2) ** 2 for y, yh2 in zip(ys, yh))
    ss_tot = sum((y - ybar) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    if model in ("linear", "poly", "polynomial"):
        term = "拟合表达式：" + expr
    else:
        term = "拟合表达式：" + expr
    return ("**%s**\n%s\n\n数据点 n = %d，R² = %s\n\n（物理边界约束、参数不确定性请升级 lmfit："
            "pip install lmfit；本工具适合快速量级判断）" % (model, term, n, _fmt(r2)))

# ======================================================================
# 4.5 本机试验数据体检（csv 零依赖）
# ======================================================================
def _sniff_delimiter(sample):
    """探测分隔符（逗号/制表/分号/竖线）：优先每行列数一致的候选，其次列数多者。"""
    lines = [l for l in sample.splitlines()[:5] if l.strip()]
    if not lines:
        return ","
    cands = []
    for d in [",", "\t", ";", "|"]:
        counts = [l.count(d) for l in lines]
        if max(counts) == 0:
            continue
        cands.append((len(set(counts)) == 1, max(counts), d))
    if not cands:
        return ","
    cands.sort(reverse=True)
    return cands[0][2]

_THOUS_RE = re.compile(r"\d{1,3}(,\d{3})+(\.\d+)?$")
_EURO_RE = re.compile(r"\d+,\d{1,2}$")
_SCI_RE = re.compile(r"\d+(\.\d+)?[eE][+-]?\d+")

def _parse_cell_float(s):
    """单元格 → float：识别美式千分位（1,234.5）、欧式小数（1234,5）与科学计数（1.5E-3）。
    "1,234" 按千分位（1234）而非欧式（1.234）处理——两者歧义时取更常见的。
    返回 None 表示非数值。"""
    s = str(s).strip()
    if not s:
        return None
    neg = s.startswith("-")
    core = s[1:] if neg else s
    v = None
    if _THOUS_RE.fullmatch(core) or re.fullmatch(r"\d+(\.\d+)?", core):
        v = float(core.replace(",", ""))
    elif _SCI_RE.fullmatch(core):
        v = float(core)
    elif _EURO_RE.fullmatch(core):
        v = float(core.replace(",", "."))
    if v is None:
        return None
    return -v if neg else v

def _table_summary(rows, header):
    """对已解析的行集做列统计。数值列给 n/均值/标准差/极值/缺失，文本列给唯一值/缺失。"""
    ncols = len(header)
    lines = ["**数据体检**（%d 行 × %d 列）\n" % (len(rows), ncols)]
    for ci in range(ncols):
        name = header[ci]
        vals, missing = [], 0
        for r in rows:
            if ci >= len(r) or str(r[ci]).strip() == "":
                missing += 1
                continue
            vals.append(r[ci])
        # 判断整列是否数值（存在非数值则不是）
        is_num, nums, euro = True, [], False
        for v in vals:
            fv = _parse_cell_float(v)
            if fv is None:
                is_num = False
                break
            if _EURO_RE.fullmatch(str(v).strip().lstrip("-")):
                euro = True
            nums.append(fv)
        if is_num and nums:
            n = len(nums)
            mean = sum(nums) / n
            std = math.sqrt(sum((x - mean) ** 2 for x in nums) / (n - 1)) if n > 1 else 0.0
            note = "，检测到欧式小数（逗号作小数点）已按此解析" if euro else ""
            lines.append("- **%s**（数值列，n=%d，缺失 %d%s）：均值 %s，标准差 %s，min %s，max %s" %
                         (name, n, missing, note, _fmt(mean), _fmt(std), _fmt(min(nums)), _fmt(max(nums))))
        else:
            uniq = len(set(str(v) for v in vals))
            lines.append("- **%s**（文本列，n=%d，缺失 %d，唯一值 %d）" % (name, len(vals), missing, uniq))
    lines.append("\n提示：列类型可作为后续处理依据；数值列可接 labmate_fit_lite 拟合或交给绘图脚本。")
    return "\n".join(lines)

# ----------------------------------------------------------------------
# 4.5a Excel(.xlsx) 零依赖读取（zipfile + ElementTree，按 ECMA-376 解析）
# ----------------------------------------------------------------------
# 与 PDF 同思路：不引入 openpyxl，手工解析 OOXML 容器。已知坑位全部处理：
#   ① 空单元格在 XML 中直接缺失——按 <c r="B3"> 的列字母定位补空位，防列错位
#   ② t="s" 共享字符串查 sharedStrings.xml（含富文本 <r><t> 段落拼接，跳过注音 rPh）
#   ③ t="inlineStr" 读 <is><t>；t="b" 布尔转 TRUE/FALSE；t="str" 公式文本直取
#   ④ 日期是序列号 + styles.xml 数字格式（内置 14-22/45-47 + 自定义看 formatCode），
#      1900 系统起点分两段处理伪闰年（serial≥61 用 1899-12-30，1-59 用 1899-12-31）
#   ⑤ 第一个工作表文件名不保证是 sheet1.xml——查 workbook.xml + rels 的 rId→target
_XL_RID_KEY = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
_XL_BUILTIN_DATE_FMTS = set(range(14, 23)) | {45, 46, 47}

def _xl_local(tag):
    """剥离 XML 命名空间：'{http://…main}c' → 'c'。"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag

def _xlsx_col_index(letters):
    """列字母 → 0-based 序号：'A'→0，'Z'→25，'AA'→26。"""
    n = 0
    for ch in letters.upper():
        n = n * 26 + ord(ch) - 64
    return n - 1

def _xlsx_text_under(el):
    """递归拼接 el 子树内所有 <t> 文本（覆盖 <t> 直存与富文本 <r><t>，跳过注音 <rPh>）。"""
    parts = []
    for child in el:
        ln = _xl_local(child.tag)
        if ln == "rPh":
            continue
        if ln == "t":
            parts.append(child.text or "")
        else:
            parts.append(_xlsx_text_under(child))
    return "".join(parts)

def _xlsx_fmt_is_date(fmt):
    """formatCode 是否日期/时间格式：去掉 [方括号块] 与 \"引号文本\" 后含 y/m/d/h/s。"""
    fmt = re.sub(r"\[[^\]]*\]", "", fmt or "")
    fmt = re.sub(r'"[^"]*"', "", fmt)
    fmt = fmt.replace("AM/PM", "").replace("A/P", "")
    return bool(re.search(r"[ymdhs]", fmt, re.IGNORECASE))

def _xlsx_date_styles(styles_bytes):
    """解析 styles.xml → cellXfs 索引表 [是否日期]。缺文件/无 cellXfs 返回 []。"""
    try:
        root = ET.fromstring(styles_bytes)
    except Exception:
        return []
    custom = {}
    for el in root.iter():
        if _xl_local(el.tag) == "numFmt":
            fid = el.get("numFmtId")
            if fid is not None:
                custom[fid] = _xlsx_fmt_is_date(el.get("formatCode"))
    xfs = []
    for el in root.iter():
        if _xl_local(el.tag) == "cellXfs":
            for xf in el:
                if _xl_local(xf.tag) != "xf":
                    continue
                fid = xf.get("numFmtId") or "0"
                if fid in custom:
                    xfs.append(custom[fid])
                elif fid.isdigit():
                    xfs.append(int(fid) in _XL_BUILTIN_DATE_FMTS)
                else:
                    xfs.append(False)
    return xfs

def _xlsx_is_date_cell(s_attr, date_xfs):
    """单元格样式索引是否指向日期格式。"""
    if s_attr is None or not date_xfs:
        return False
    try:
        return date_xfs[int(s_attr)]
    except (ValueError, IndexError):
        return False

def _xlsx_serial_date(serial):
    """Excel 1900 系统序列号 → 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM[:SS]'。
    serial≥61 起点 1899-12-30（吸收 1900 伪闰日），1-59 起点 1899-12-31；小数部分是时间。"""
    days = int(serial)
    frac = serial - days
    if days >= 61:
        d = datetime.date(1899, 12, 30) + datetime.timedelta(days=days)
    elif days >= 1:
        d = datetime.date(1899, 12, 31) + datetime.timedelta(days=days)
    else:
        d = datetime.date(1899, 12, 31)  # serial<1：仅时间（挂 1899-12-31），现实数据罕见
    if frac >= 1e-9:
        secs = int(round(frac * 86400))
        if secs % 60:
            return "%s %02d:%02d:%02d" % (d.isoformat(), secs // 3600, secs % 3600 // 60, secs % 60)
        return "%s %02d:%02d" % (d.isoformat(), secs // 3600, secs % 3600 // 60)
    return d.isoformat()

def _xlsx_shared_strings(zf):
    """读 xl/sharedStrings.xml → 共享字符串列表（富文本已拼接）。缺文件返回 None。"""
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return None
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    out = []
    for si in root:
        if _xl_local(si.tag) == "si":
            out.append(_xlsx_text_under(si))
    return out

def _read_xlsx(path, sheet=None):
    """零依赖解析 .xlsx 的工作表 → (header, rows, 来源描述)，失败返回错误字符串。
    第一行按表头（与 CSV 一致）；空单元格补空字符串；日期列转 ISO 文本。"""
    if not os.path.isfile(path):
        return "❌ 文件不存在：%s（检查路径；.xlsx 支持中文文件名）" % path
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return "❌ 不是有效的 .xlsx（zip 容器损坏；老式 .xls 二进制不支持，请在 Excel/WPS 里另存为 .xlsx）"
    with zf:
        # 1) workbook.xml：工作表清单（文档顺序 = 显示顺序）
        try:
            wb = ET.fromstring(zf.read("xl/workbook.xml"))
        except KeyError:
            return "❌ 缺少 xl/workbook.xml：不是标准 .xlsx 结构"
        except ET.ParseError as exc:
            return "❌ workbook.xml 解析失败：%s" % exc
        sheets = [el for el in wb.iter() if _xl_local(el.tag) == "sheet"]
        if not sheets:
            return "❌ 工作簿中没有工作表"
        # 2) 选择工作表：名称或 1-based 序号，默认第 1 个
        idx = 0
        if sheet is not None:
            names = [s.get("name") or "" for s in sheets]
            if str(sheet) in names:
                idx = names.index(str(sheet))
            elif str(sheet).isdigit():
                idx = int(sheet) - 1
            else:
                return "❌ 找不到工作表 %r；现有：%s" % (sheet, "、".join("『%s』" % n for n in names))
        if not 0 <= idx < len(sheets):
            return "❌ 工作表序号越界：共 %d 个（1-%d）" % (len(sheets), len(sheets))
        target_el = sheets[idx]
        rid = target_el.get(_XL_RID_KEY)
        if rid is None:  # 兜底：有些生成器用别名前缀（URI 相同则 ET 已归一）
            for k, v in target_el.attrib.items():
                if k.endswith("}id") or k == "id":
                    rid = v
                    break
        # 3) rels：rId → 工作表 XML 路径
        try:
            rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        except KeyError:
            return "❌ 缺少 xl/_rels/workbook.xml.rels：无法定位工作表文件"
        spath = None
        for rel in rels:
            if _xl_local(rel.tag) == "Relationship" and rel.get("Id") == rid:
                t = rel.get("Target") or ""
                spath = t[1:] if t.startswith("/") else (t if t.startswith("xl/") else "xl/" + t)
                break
        if not spath:
            return "❌ 关系 rId=%s 在 rels 中找不到（非标准 xlsx）" % rid
        try:
            sheet_xml = zf.read(spath)
        except KeyError:
            return "❌ 工作表文件 %s 缺失（非标准 xlsx）" % spath
        # 4) 共享字符串与日期样式（均可缺失）
        shared = _xlsx_shared_strings(zf)
        try:
            date_xfs = _xlsx_date_styles(zf.read("xl/styles.xml"))
        except KeyError:
            date_xfs = []
        # 5) 逐行解析：按 r 属性列字母定位，空位补 ""
        try:
            root = ET.fromstring(sheet_xml)
        except ET.ParseError as exc:
            return "❌ 工作表 XML 解析失败：%s" % exc
        all_rows = []
        for row_el in root.iter():
            if _xl_local(row_el.tag) != "row":
                continue
            cells, maxc = {}, -1
            for c in row_el:
                if _xl_local(c.tag) != "c":
                    continue
                m = re.match(r"([A-Za-z]+)", c.get("r") or "")
                ci = _xlsx_col_index(m.group(1)) if m else len(cells)
                tattr = c.get("t")
                if tattr == "inlineStr":
                    val = ""
                    for sub in c:
                        if _xl_local(sub.tag) == "is":
                            val = _xlsx_text_under(sub)
                            break
                else:
                    raw = ""
                    for sub in c:
                        if _xl_local(sub.tag) == "v":
                            raw = sub.text or ""
                            break
                    if tattr == "s":
                        try:
                            val = shared[int(raw)] if shared else ""
                        except (ValueError, IndexError):
                            val = raw
                    elif tattr == "b":
                        val = "TRUE" if raw.strip() == "1" else "FALSE"
                    elif tattr in (None, "n") and raw and _xlsx_is_date_cell(c.get("s"), date_xfs):
                        try:
                            val = _xlsx_serial_date(float(raw))
                        except ValueError:
                            val = raw
                    else:  # "str" 公式文本 / "e" 错误码 / 普通数值
                        val = raw
                cells[ci] = val
                if ci > maxc:
                    maxc = ci
            if cells:
                all_rows.append([cells.get(i, "") for i in range(maxc + 1)])
        if not all_rows:
            return "❌ 工作表『%s』没有任何数据" % (target_el.get("name") or "")
        header, rows = all_rows[0], all_rows[1:]
        if not rows:
            return "❌ 数据不足：『%s』只有表头一行，至少需要 1 行数据" % (target_el.get("name") or "")
        origin = "Excel 工作簿『%s』第 %d/%d 个工作表『%s』（日期列已转 ISO 文本）" % (
            os.path.basename(path), idx + 1, len(sheets), target_el.get("name") or "")
        return header, rows, origin

def tool_table(args):
    """读取本机 CSV / Excel(.xlsx) 或内联数据，输出列级统计体检。只读不写，数据不出本机。"""
    xlsx_path = args.get("xlsx_path")
    if xlsx_path:
        res = _read_xlsx(xlsx_path, args.get("sheet"))
        if isinstance(res, str):
            return res
        header, rows, origin = res
        out = _table_summary(rows, header)
        preview = "\n".join(",".join(r) for r in ([header] + rows)[:4])
        return out + "\n\n前几行预览（来源：%s）：\n```\n%s\n```" % (origin, preview)
    path = args.get("csv_path")
    data = args.get("data")
    text = None
    if path:
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
                text = f.read()
        except Exception as exc:
            return "❌ 读取失败：%s（检查路径与编码；中文文件名需加引号）" % exc
    elif data:
        text = str(data)
    else:
        return "❌ 请给 csv_path（本机文件路径）或 data（内联 CSV 文本）"
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return "❌ 数据不足：至少需要表头 + 1 行数据"
    delim = args.get("delimiter") or _sniff_delimiter(text)
    reader = csv.reader(lines, delimiter=delim)
    parsed = list(reader)
    header, rows = parsed[0], parsed[1:]
    out = _table_summary(rows, header)
    preview = "\n".join(",".join(r) for r in parsed[:4])
    return out + "\n\n前几行预览（分隔符 %r）：\n```\n%s\n```" % (delim, preview)

# ======================================================================
# 4.6 期刊绘图样式注入（SciencePlots 逆向，零依赖）
# ======================================================================
MPL_STYLES = {
    "science": {
        "font.family": "serif", "font.size": 8,
        "axes.labelsize": 9, "axes.linewidth": 0.5,
        "xtick.direction": "in", "ytick.direction": "in",
        "xtick.minor.visible": "True", "ytick.minor.visible": "True",
        "xtick.top": "True", "ytick.right": "True",
        "lines.linewidth": 1.0, "lines.markersize": 3,
        "figure.figsize": "3.35, 2.6", "figure.dpi": "150",
        "savefig.dpi": "600", "savefig.bbox": "tight",
    },
    "ieee": {
        "__extends__": "science", "font.size": 8,
        "axes.labelsize": 8, "figure.figsize": "3.5, 2.75",
    },
    "nature": {
        "font.family": "sans-serif", "font.size": 7,
        "axes.labelsize": 8, "axes.linewidth": 0.6, "axes.grid": "True",
        "grid.linestyle": ":", "grid.linewidth": 0.4,
        "xtick.direction": "out", "ytick.direction": "out",
        "lines.linewidth": 1.2, "figure.figsize": "3.5, 2.5",
        "savefig.dpi": "600",
    },
    "cnjournal": {
        "font.family": "sans-serif", "font.sans-serif": "SimSun, SimHei, serif",
        "axes.unicode_minus": "False", "font.size": 10.5,
        "axes.labelsize": 10.5, "axes.linewidth": 0.8,
        "xtick.direction": "in", "ytick.direction": "in",
        "lines.linewidth": 1.2, "figure.figsize": "8, 6", "figure.dpi": "300",
        "savefig.dpi": "600",
    },
}

def _flatten_style(name):
    base = dict(MPL_STYLES["science"])
    cfg = dict(MPL_STYLES.get(name, {}))
    parent = cfg.pop("__extends__", None)
    if parent:
        base.update(MPL_STYLES.get(parent, {}))
    base.update(cfg)
    return base

def tool_style(args):
    name = str(args.get("style", "science")).lower()
    if name not in MPL_STYLES:
        return "❌ 未知样式 %s：支持 %s" % (name, ", ".join(MPL_STYLES))
    flat = _flatten_style(name)
    body = "\n".join("%s : %s" % (k, v) for k, v in sorted(flat.items()))
    save = args.get("save_mplstyle")
    saved = ""
    if save:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(save)), exist_ok=True)
            with open(save, "w", encoding="utf-8") as f:
                f.write("# LabMate 期刊样式（%s）\n" % name + body + "\n")
            saved = "\n已写入样式文件：%s\n使用：plt.style.use(r'%s')" % (save, save)
        except Exception as exc:
            saved = "\n⚠ 样式文件写入失败：%s" % exc
    usage = ("\n\n两种用法：\n"
             "1. 让 AI 按上述参数直接配置 mpl.rcParams（无需 matplotlib 装样式文件）\n"
             "2. 或写入 .mplstyle 文件后 plt.style.use(路径)")
    return ("**%s 期刊样式参数**（SciencePlots 逆向，直接可用于 matplotlib）\n\n```\n%s\n```%s%s"
            % (name, body, saved, usage))

# ======================================================================
# 4.7 文献组：arXiv 检索（官方免费 API）与 Crossref DOI→BibTeX
# ======================================================================
_ARXIV_NS = "{http://www.w3.org/2005/Atom}"

def _parse_arxiv_atom(xml_text):
    """解析 arXiv Atom 响应为结构化列表（独立函数便于离线单测）。"""
    root = ET.fromstring(xml_text)
    out = []
    for e in root.findall("%sentry" % _ARXIV_NS):
        title = " ".join((e.findtext("%stitle" % _ARXIV_NS) or "").split())
        authors = [a.findtext("%sname" % _ARXIV_NS) for a in e.findall("%sauthor" % _ARXIV_NS)]
        published = (e.findtext("%spublished" % _ARXIV_NS) or "")[:10]
        summary = " ".join((e.findtext("%ssummary" % _ARXIV_NS) or "").split())[:200]
        link = e.findtext("%sid" % _ARXIV_NS) or ""
        cat = ""
        for c in e.findall("%scategory" % _ARXIV_NS):
            cat = c.get("term", "")
            break
        out.append({"title": title, "authors": authors, "date": published,
                    "category": cat, "summary": summary, "link": link})
    return out

def _http_get(url, timeout=15, headers=None):
    hdrs = {"User-Agent": "LabMate/%s (research-assistant; mailto:labmate@local)" % SERVER_VERSION}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")

def tool_arxiv(args):
    query = (args.get("query") or "").strip()
    n = int(args.get("max_results", 5) or 5)
    if not query:
        return "❌ 请给检索词（query），如 'rock mechanics direct shear'"
    if not (1 <= n <= 20):
        n = 5
    url = ("http://export.arxiv.org/api/query?search_query=%s&start=0&max_results=%d&sortBy=relevance"
           % (urllib.parse.quote("all:" + query), n))
    try:
        xml_text = _http_get(url)
    except Exception as exc:
        return ("⚠ 网络查询失败：%s\n\n诊断建议：确认本机可访问 export.arxiv.org；"
                "公司网络可能拦截，可改用 data 参数环境或让用户在浏览器验证。本工具其余部分不依赖网络。" % exc)
    papers = _parse_arxiv_atom(xml_text)
    if not papers:
        return "检索完成但无结果：尝试换关键词（英文检索效果更好）。"
    lines = ["**arXiv 检索：\"%s\"（%d 条）**\n" % (query, len(papers))]
    for i, p in enumerate(papers, 1):
        lines.append("%d. **%s**\n   %s | %s | 分类 %s\n   %s\n   %s" %
                     (i, p["title"], ", ".join(p["authors"][:4]) + ("等" if len(p["authors"]) > 4 else ""),
                      p["date"], p["category"], p["summary"], p["link"]))
    lines.append("\n（来源：arXiv 官方 API，真实元数据。精读建议让 AI 提取方法/样本量/结论三点结构。）")
    return "\n".join(lines)

def _tex_escape(s):
    """LaTeX/BibTeX 特殊字符转义：& % $ # _。"""
    return re.sub(r"([&%$#_])", r"\\\1", str(s))

def _make_bibtex(meta, used_keys=None):
    """Crossref 元数据 → 规范 BibTeX。used_keys 传入既有库的 key 集合时自动加 a/b 后缀防撞。"""
    kind = meta.get("type", "journal-article")
    entry = {"journal-article": "article", "proceedings-article": "inproceedings",
             "book-chapter": "incollection", "book": "book",
             "report": "techreport"}.get(kind, "misc")
    authors = [a for a in meta.get("author", []) if a.get("family")]
    au = " and ".join("%s, %s" % (a["family"], a.get("given", "")) for a in authors) or "Unknown"
    year = None
    try:
        year = (meta.get("issued", {}).get("date-parts") or [[None]])[0][0]
    except Exception:
        pass
    key = (authors[0]["family"] if authors else "anon") + str(year or "xxxx")
    if used_keys:
        base, suf, i = key, "abcdefghijklmnopqrstuvwxyz", 0
        while key in used_keys and i < 26:
            key = base + suf[i]
            i += 1
    f = []
    def add(field, val):
        if val:
            f.append("  %-14s = {%s}" % (field, val))
    add("author", au)
    add("title", _tex_escape(meta.get("title", [""])[0] if meta.get("title") else ""))
    if entry == "article":
        add("journal", _tex_escape(meta.get("container-title", [""])[0] if meta.get("container-title") else ""))
        add("volume", meta.get("volume", ""))
        add("number", meta.get("issue", ""))
        add("pages", (meta.get("page", "") or "").replace("-", "--"))
    elif entry == "inproceedings":
        add("booktitle", _tex_escape(meta.get("container-title", [""])[0] if meta.get("container-title") else ""))
    add("publisher", meta.get("publisher", ""))
    add("year", year)
    add("doi", meta.get("DOI", ""))
    return "@%s{%s,\n%s\n}" % (entry, key, ",\n".join(f))

def tool_cite(args):
    doi = (args.get("doi") or "").strip()
    if not doi:
        return "❌ 请给 DOI，如 10.1016/j.ijrockmas.2019.104123"
    used, bib_note = None, ""
    bib_file = args.get("bib_file")
    if bib_file:
        used = set()
        if os.path.exists(bib_file):
            try:
                with open(bib_file, "r", encoding="utf-8", errors="replace") as f:
                    used = set(re.findall(r"@\w+\s*\{\s*([^,\s{}]+)\s*,", f.read()))
                bib_note = "\n（已读取你的库文件，自动避开 %d 个既有 key 防撞。）" % len(used)
            except Exception as exc:
                return "⚠ 读取 bib_file 失败：%s" % exc
        else:
            bib_note = "\n（bib_file 尚不存在，将作为你的第一个库文件。）"
    url = "https://api.crossref.org/works/%s?mailto=labmate@local" % urllib.parse.quote(doi)
    try:
        raw = _http_get(url)
        meta = json.loads(raw)["message"]
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "❌ DOI 不存在（Crossref 404）：请检查编号。用真实 DOI 生成的引用不会是幻觉文献。"
        return "⚠ 网络查询失败（HTTP %s）：确认可访问 api.crossref.org。" % exc.code
    except Exception as exc:
        return "⚠ 网络查询失败：%s" % exc
    bib = _make_bibtex(meta, used_keys=used)
    title = meta.get("title", ["(无题)"])[0]
    lines = ["**DOI 元数据**（Crossref，真实数据）",
             "标题：%s" % title,
             "类型：%s | DOI: %s" % (meta.get("type", "?"), meta.get("DOI", "")),
             "\n**BibTeX**：\n```\n%s\n```" % bib,
             bib_note,
             "\n（元数据来自 Crossref 官方库，可放心用于 LaTeX；格式可再让 AI 按目标期刊微调。）"]
    return "\n".join([l for l in lines if l])

# ======================================================================
# 4.8 多源文献聚合：arXiv + Crossref + OpenAlex 并发检索 + 跨源去重
# ======================================================================
def _paper(title, authors, year, venue, doi, url, source, abstract):
    return {"title": title or "", "authors": authors or [], "year": year,
            "venue": venue or "", "doi": _norm_doi(doi) if doi else "", "url": url or "",
            "source": source, "abstract": abstract or ""}

def _norm_doi(doi):
    d = (doi or "").strip().lower()
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d)

def _norm_title(t):
    t = (t or "").lower()
    t = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", t)
    t = re.sub(r"^(the|a|an) ", "", t.strip())
    return re.sub(r"\s+", " ", t).strip()

def _first_surname(p):
    au = (p.get("authors") or [""])[0]
    return (au.split(",")[0].split()[-1] if au else "").lower()

def _parse_crossref_works(raw):
    """Crossref /works 响应 JSON → 统一论文 schema（独立纯函数便于离线单测）。"""
    items = ((json.loads(raw).get("message") or {}).get("items")) or []
    out = []
    for it in items:
        try:
            year = (it.get("issued", {}).get("date-parts") or [[None]])[0][0]
        except Exception:
            year = None
        authors = []
        for a in it.get("author") or []:
            if a.get("family"):
                authors.append(((a.get("given") or "").strip() + " " + a["family"]).strip())
        doi = it.get("DOI") or ""
        out.append(_paper(
            title=(it.get("title") or [""])[0], authors=authors, year=year,
            venue=(it.get("container-title") or [""])[0], doi=doi,
            url=("https://doi.org/" + doi) if doi else (it.get("URL") or ""),
            source="Crossref",
            abstract=" ".join(re.sub(r"<[^>]+>", "", it.get("abstract") or "").split())))
    return out

def _inverted_index_to_text(inv):
    """OpenAlex 倒排摘要索引 → 正常文本。"""
    if not inv:
        return ""
    pos = {}
    for word, places in inv.items():
        for p in places:
            pos[p] = word
    return " ".join(pos[i] for i in sorted(pos))

def _parse_openalex_works(raw):
    """OpenAlex /works 响应 JSON → 统一论文 schema（独立纯函数便于离线单测）。"""
    data = json.loads(raw)
    items = data.get("results", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    out = []
    for it in items:
        authors = [a.get("author", {}).get("display_name", "") for a in it.get("authorships") or []]
        venue = (((it.get("primary_location") or {}).get("source") or {}).get("display_name")) or ""
        doi = it.get("doi") or ""
        out.append(_paper(
            title=it.get("title") or "", authors=[a for a in authors if a],
            year=it.get("publication_year"), venue=venue, doi=doi,
            url=("https://doi.org/" + _norm_doi(doi)) if doi else it.get("id", ""),
            source="OpenAlex",
            abstract=_inverted_index_to_text(it.get("abstract_inverted_index"))))
    return out

def _fetch_arxiv_papers(query, n, mailto):
    url = ("http://export.arxiv.org/api/query?search_query=%s&start=0&max_results=%d&sortBy=relevance"
           % (urllib.parse.quote("all:" + query), n))
    entries = _parse_arxiv_atom(_http_get(url))
    return [_paper(e["title"], e["authors"], (e["date"][:4] or None),
                   "arXiv " + e["category"], "", e["link"], "arXiv", e["summary"]) for e in entries]

def _fetch_crossref_papers(query, n, mailto):
    url = ("https://api.crossref.org/works?query=%s&rows=%d&mailto=%s"
           % (urllib.parse.quote(query), n, urllib.parse.quote(mailto)))
    return _parse_crossref_works(_http_get(url))

def _fetch_openalex_papers(query, n, mailto, api_key=""):
    url = ("https://api.openalex.org/works?search=%s&per-page=%d&mailto=%s"
           % (urllib.parse.quote(query), n, urllib.parse.quote(mailto)))
    if api_key:
        url += "&api_key=" + urllib.parse.quote(api_key)
    return _parse_openalex_works(_http_get(url))

def _merge_paper(base, add):
    base["sources"] = sorted(set(base.get("sources", [base["source"]])) | {add["source"]})
    if not base["doi"] and add["doi"]:
        base["doi"] = add["doi"]
    if add["doi"] and (not base["url"] or "arxiv.org" in base["url"]):
        base["url"] = "https://doi.org/" + add["doi"]
    if add["venue"] and (not base["venue"] or base["venue"].startswith("arXiv")):
        base["venue"] = add["venue"]
    if len(add.get("abstract", "")) > len(base.get("abstract", "")):
        base["abstract"] = add["abstract"]
    if not base["year"] and add["year"]:
        base["year"] = add["year"]
    if len(add["authors"]) > len(base["authors"]):
        base["authors"] = add["authors"]
    return base

def _dedup_papers(papers, sim=0.90):
    """跨源去重：DOI 一致直接合并；否则标题高相似且（首作者+年份一致，或近乎完全同名同年）才合并。"""
    kept = []
    for p in papers:
        p.setdefault("sources", [p["source"]])
        nt, matched = _norm_title(p["title"]), None
        for k in kept:
            if p["doi"] and k["doi"] and p["doi"] == k["doi"]:
                matched = k
                break
            kt = _norm_title(k["title"])
            ratio = difflib.SequenceMatcher(None, nt, kt).ratio() if nt and kt else 0.0
            if ratio >= sim and (
                    (ratio >= 0.97 and p["year"] and p["year"] == k["year"]) or
                    (_first_surname(p) and _first_surname(p) == _first_surname(k)
                     and p["year"] and p["year"] == k["year"])):
                matched = k
                break
        if matched:
            _merge_paper(matched, p)
        else:
            kept.append(p)
    return kept

_SOURCE_LABELS = {"arxiv": "arXiv", "crossref": "Crossref", "openalex": "OpenAlex"}

def tool_search(args):
    query = (args.get("query") or "").strip()
    if not query:
        return "❌ 请给检索词（query），如 'hydraulic fracture toughness granite'"
    sources = [str(s).lower() for s in (args.get("sources") or ["arxiv", "crossref", "openalex"])]
    known = {"arxiv": _fetch_arxiv_papers, "crossref": _fetch_crossref_papers}
    n = int(args.get("max_results", 5) or 5)
    if not (1 <= n <= 15):
        n = 5
    mailto = args.get("mailto") or "labmate@local"
    api_key = args.get("openalex_key") or ""
    jobs = {}
    for src in sources:
        if src in known:
            jobs[src] = (known[src], (query, n, mailto))
        elif src == "openalex":
            jobs[src] = (_fetch_openalex_papers, (query, n, mailto, api_key))
    if not jobs:
        return "❌ sources 仅支持：arxiv / crossref / openalex"
    raw_papers, status = [], {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futs = {pool.submit(fn, *a): name for name, (fn, a) in jobs.items()}
        for fut in concurrent.futures.as_completed(futs):
            name = futs[fut]
            try:
                got = fut.result()
                raw_papers.extend(got)
                status[name] = "✅ %d 条" % len(got)
            except urllib.error.HTTPError as exc:
                hint = "（OpenAlex 新版接口可能要求免费 api_key，可传 openalex_key 参数）" if name == "openalex" else ""
                status[name] = "⚠ HTTP %s%s" % (exc.code, hint)
            except Exception as exc:
                status[name] = "⚠ %s" % str(exc)[:120]
    if not raw_papers:
        return ("**多源文献聚合：\"%s\"——全部源均未返回结果**\n源状态：%s\n\n"
                "诊断：检查网络；所选源都失败通常是公司网络拦截。单源可改用 labmate_arxiv。"
                % (query, " | ".join("%s %s" % (_SOURCE_LABELS[k], status.get(k, "未启用"))
                                     for k in jobs)))
    papers = _dedup_papers(raw_papers)
    yf, yt = args.get("year_from"), args.get("year_to")
    if yf or yt:
        def in_year(p):
            return (not p["year"]) or ((not yf or p["year"] >= int(yf)) and (not yt or p["year"] <= int(yt)))
        papers = [p for p in papers if in_year(p)]
    papers.sort(key=lambda p: (len(p.get("sources", [])), p["year"] or 0), reverse=True)
    span = "（%s-%s）" % (yf, yt) if yf or yt else ""
    lines = ["**多源文献聚合：\"%s\"%s（去重后 %d 条 / 原始 %d 条）**\n"
             % (query, span, len(papers), len(raw_papers))]
    for i, p in enumerate(papers[:max(n * 3, 10)], 1):
        authors = ", ".join(p["authors"][:4]) + ("等" if len(p["authors"]) > 4 else "")
        lines.append("%d. **%s** `[%s]`" % (i, p["title"], "+".join(p.get("sources", [p["source"]]))))
        lines.append("   %s | %s | %s" % (authors or "作者不详", p["year"] or "年份不详", p["venue"] or "出处不详"))
        if p["abstract"]:
            lines.append("   %s" % p["abstract"][:300])
        link = ("DOI: %s" % p["doi"]) if p["doi"] else ""
        if p["url"]:
            link = (link + " | " if link else "") + p["url"]
        if link:
            lines.append("   %s" % link)
    lines.append("\n源状态：%s" % " | ".join(
        "%s %s" % (_SOURCE_LABELS[k], status.get(k, "未启用")) for k in jobs))
    lines.append("（全部为真实元数据；多源同时命中的条目排在前面。无 DOI 的条目不要凭记忆补 BibTeX，用 labmate_cite 核验。）")
    return "\n".join(lines)

# ======================================================================
# 5. 科学栈体检
# ======================================================================
_OPTIONAL_DEPS = [
    ("numpy", "ndarray", "试验数据批量处理"),
    ("scipy", "scipy", "滤波/峰值/统计"),
    ("lmfit", "lmfit", "带物理约束的拟合+不确定性"),
    ("sympy", "sympy", "符号推导"),
    ("matplotlib", "matplotlib", "论文级图表"),
    ("pint", "pint", "带量纲单位运算"),
    ("handcalcs", "handcalcs", "教科书式手算渲染"),
    ("gmsh", "gmsh", "网格生成"),
    ("pyvista", "pyvista", "3D 可视化"),
    ("skfem", "skfem", "轻量有限元"),
]

def tool_deps(_args):
    ok, missing = [], []
    for mod, _, use in _OPTIONAL_DEPS:
        try:
            __import__(mod)
            ok.append(mod)
        except ImportError:
            missing.append((mod, use))
    lines = ["**LabMate 科学栈体检**\n"]
    lines.append("✅ 可用：%s" % (", ".join(ok) if ok else "（无）"))
    lines.append("\n❌ 缺失（按需安装）：")
    for mod, use in missing:
        lines.append("  - `%s`（%s）：`pip install %s`" % (mod, use, mod))
    lines.append("\n内置零依赖工具（本 server）始终可用：单位换算 / 手算排版 / Mohr 圆 / 基础拟合")
    return "\n".join(lines)

# ======================================================================
# 6. 本地 PDF 文本提取（零依赖：zlib + 文本算子解析，按页/溯源/扫描版诊断）
# ======================================================================
_PDF_OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj(.*?)endobj", re.DOTALL)
_PDF_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_PDF_SIMPLE_ESC = {ord("n"): b"\n", ord("r"): b"\r", ord("t"): b"\t", ord("b"): b"\b",
                   ord("f"): b"\f", ord("("): b"(", ord(")"): b")", ord("\\"): b"\\"}

def _decode_pdf_literal(raw):
    """解码 PDF 字面量字符串（不含外层括号）：\\( \\) 八进制 \\n 等转义。"""
    out, i, n = bytearray(), 0, len(raw)
    while i < n:
        c = raw[i]
        if c == 0x5C and i + 1 < n:
            i += 1
            e = raw[i]
            if e in _PDF_SIMPLE_ESC:
                out += _PDF_SIMPLE_ESC[e]
                i += 1
            elif 48 <= e <= 55:
                digits, j = bytes([e]), i + 1
                while j < n and j < i + 3 and 48 <= raw[j] <= 55:
                    digits += bytes([raw[j]])
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
            else:
                out.append(e)
                i += 1
        else:
            out.append(c)
            i += 1
    return bytes(out)

def _decode_hex_text(hex_raw):
    """hex 字符串 → 文本。优先按 UTF-16BE（ToUnicode/CID 常见），可信度低则弃用。"""
    try:
        packed = bytes.fromhex(re.sub(rb"\s+", b"", hex_raw).decode("ascii", "ignore"))
    except Exception:
        return ""
    if not packed:
        return ""
    t16 = packed.decode("utf-16-be", "ignore")
    if t16 and sum(c.isprintable() or c.isspace() for c in t16) / len(t16) > 0.8:
        return t16
    latin = packed.decode("latin-1", "ignore")
    if latin and sum(c.isprintable() for c in latin) / len(latin) > 0.85:
        return latin
    return ""

def _read_literal(content, i):
    """从 '(' 位置读取完整字面量，返回 (解码文本, 下一位置)。"""
    n, depth, j, buf = len(content), 1, i + 1, bytearray()
    while j < n and depth > 0:
        cj = content[j]
        if cj == 0x5C and j + 1 < n:
            buf += content[j:j + 2]
            j += 2
            continue
        if cj == 0x28:
            depth += 1
        elif cj == 0x29:
            depth -= 1
            if depth == 0:
                break
        buf.append(cj)
        j += 1
    return _decode_pdf_literal(bytes(buf)).decode("latin-1", "replace"), j + 1

def _parse_tj_array(inner):
    """解析 TJ 数组内部：字符串拼接，大负字距（<-80/1000 em）补空格。数组内除字符串外只有数字。"""
    parts, i, n = [], 0, len(inner)
    while i < n:
        c = inner[i]
        if c == 0x28:
            txt, i = _read_literal(inner, i)
            parts.append(txt)
        elif c == 0x3C and inner[i:i + 2] != b"<<":
            j = inner.find(b">", i + 1)
            parts.append(_decode_hex_text(inner[i + 1:j]) if j > 0 else "")
            i = j + 1 if j > 0 else i + 1
        elif c in b"0123456789-":
            m = re.match(rb"-?\d+(?:\.\d+)?", inner[i:i + 24])
            if m:
                try:
                    if float(m.group(0)) < -80:
                        parts.append(" ")
                except ValueError:
                    pass
                i += len(m.group(0))
            else:
                i += 1
        else:
            i += 1
    return "".join(parts)

def _extract_stream_text(content):
    """单个 content stream → 纯文本：TJ 数组按区间摘出解析，其余扫 Tj 字面量；Td/TD/T*/ET 换行。"""
    spans = []
    for m in re.finditer(rb"\[(?:[^\[\]])*?\]\s*TJ", content, re.DOTALL):
        inner = m.group(0)[1:m.group(0).rfind(b"]")]
        spans.append((m.start(), m.end(), _parse_tj_array(inner)))
    parts, i, n, si = [], 0, len(content), 0
    while i < n:
        if si < len(spans) and i == spans[si][0]:
            parts.append(spans[si][2])
            i = spans[si][1]
            si += 1
            continue
        c = content[i]
        if c == 0x28:
            txt, i = _read_literal(content, i)
            parts.append(txt)
        elif c == 0x3C and content[i:i + 2] != b"<<":
            j = content.find(b">", i + 1)
            if j > 0:
                parts.append(_decode_hex_text(content[i + 1:j]))
                i = j + 1
            else:
                i += 1
        else:
            two = content[i:i + 2]
            if two in (b"Td", b"TD") or two == b"T*" or two == b"ET" or c == 0x27:
                parts.append("\n")
            i += 1
    text = "".join(parts)
    text = re.sub(r"[ \t\f]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def _collect_page_order(data, objs):
    """从 Catalog→Pages 树按 Kids 顺序收集页对象 id（不依赖 xref 表）。"""
    root = re.search(rb"/Root\s+(\d+)\s+(\d+)\s+R", data)
    if not root:
        return [k for k, b in objs.items() if re.search(rb"/Type\s*/Page(?![A-Za-z])", b)]
    catalog = objs.get((int(root.group(1)), int(root.group(2))))
    if not catalog:
        return [k for k, b in objs.items() if re.search(rb"/Type\s*/Page(?![A-Za-z])", b)]
    pm = re.search(rb"/Pages\s+(\d+)\s+(\d+)\s+R", catalog)
    order = []
    def walk(key, seen):
        if key in seen or key not in objs:
            return
        seen.add(key)
        body = objs[key]
        if re.search(rb"/Type\s*/Pages(?![A-Za-z])", body):
            km = re.search(rb"/Kids\s*\[(.*?)\]", body, re.DOTALL)
            for r in re.findall(rb"(\d+)\s+(\d+)\s+R", km.group(1) if km else b""):
                walk((int(r[0]), int(r[1])), seen)
        else:
            order.append(key)
    if pm:
        walk((int(pm.group(1)), int(pm.group(2))), set())
    return order or [k for k, b in objs.items() if re.search(rb"/Type\s*/Page(?![A-Za-z])", b)]

def _pdf_pages_text(data):
    """解析 PDF 字节 → (按页文本列表, 诊断 dict)。纯函数，输入字节便于离线单测。"""
    if b"/Encrypt" in data:
        return [], {"encrypted": True, "images": 0, "unsupported": 0}
    objs = {}
    for m in _PDF_OBJ_RE.finditer(data):
        objs[(int(m.group(1)), int(m.group(2)))] = m.group(3)
    page_ids = _collect_page_order(data, objs)
    pages, unsupported = [], 0
    for key in page_ids:
        body = objs.get(key, b"")
        cm = re.search(rb"/Contents\s*(\[.*?\]|\d+\s+\d+\s+R)", body, re.DOTALL)
        refs = (re.findall(rb"(\d+)\s+(\d+)\s+R", cm.group(1)) if cm else [])
        chunks = []
        for r in refs:
            sbody = objs.get((int(r[0]), int(r[1])), b"")
            sm = _PDF_STREAM_RE.search(sbody)
            if not sm:
                continue
            raw_stream = sm.group(1)
            if b"FlateDecode" in sbody:
                try:
                    raw_stream = zlib.decompress(raw_stream)
                except Exception:
                    try:
                        raw_stream = zlib.decompressobj().decompress(raw_stream)
                    except Exception:
                        unsupported += 1
                        continue
            elif re.search(rb"/Filter\s*/(?!FlateDecode)[A-Za-z]+", sbody):
                unsupported += 1
                continue
            chunks.append(_extract_stream_text(raw_stream))
        pages.append("\n".join(c for c in chunks if c))
    images = len(re.findall(rb"/Subtype\s*/Image|/DCTDecode|/CCITTFaxDecode", data))
    return pages, {"encrypted": False, "images": images, "unsupported": unsupported}

def tool_pdf(args):
    path = (args.get("pdf_path") or "").strip()
    action = str(args.get("action", "stats")).lower()
    if not path:
        return "❌ 请给 pdf_path（本机 PDF 路径）。工具只读，文件不会离开本机。"
    if not os.path.exists(path):
        return "❌ 文件不存在：%s" % path
    if not path.lower().endswith(".pdf"):
        return "❌ 不是 .pdf 文件：%s" % path
    max_mb = float(args.get("max_mb", 50) or 50)
    if os.path.getsize(path) > max_mb * 1024 * 1024:
        return "❌ 文件超过 %.0f MB 上限（可传 max_mb 调大）。大 PDF 请先按章节拆分。" % max_mb
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as exc:
        return "❌ 读取失败：%s" % exc
    if not data.startswith(b"%PDF"):
        return "❌ 文件头不是 %PDF——可能不是有效 PDF 或已损坏。"
    pages, diag = _pdf_pages_text(data)
    if diag["encrypted"]:
        return "⚠ 该 PDF 已加密/带权限口令：零依赖提取器不支持解密，请先用 PDF 工具去除口令后再试。"
    total = sum(len(p) for p in pages)
    avg = total / len(pages) if pages else 0
    scanned = bool(pages) and avg < 100 and diag["images"] >= len(pages)
    if action == "stats":
        lines = ["**PDF 体检：%s**" % os.path.basename(path),
                 "页数：%d | 可提取文本：%d 字符 | 平均每页 %.0f 字符 | 内嵌图像标记：%d 处"
                 % (len(pages), total, avg, diag["images"])]
        if scanned:
            lines.append("\n⚠ **疑似扫描版/图片型 PDF**：页面几乎没有文本层。"
                         "本工具不做 OCR，请用 OCR 工具（如 tesseract）转文字后再分析。")
        else:
            lines.append("\n✅ 文本层可提取，可用 action=extract 读页、action=search 做关键词页码溯源。")
        if diag["unsupported"]:
            lines.append("⚠ 有 %d 个内容流使用了非 Flate 压缩（如 LZW），已跳过；如文本明显缺失请改用 pypdf。"
                         % diag["unsupported"])
        lines.append("（零依赖提取器：英文/数字论文可靠；CID 编码的中文 PDF 可能乱码，属已知边界。）")
        return "\n".join(lines)
    if action == "extract":
        pf, pt = int(args.get("page_from", 1) or 1), int(args.get("page_to", len(pages)) or len(pages))
        pf, pt = max(1, pf), min(len(pages), pt)
        mc = int(args.get("max_chars", 6000) or 6000)
        if pf > pt:
            return "❌ 页码范围无效：%d-%d（共 %d 页）" % (pf, pt, len(pages))
        if scanned:
            return "⚠ 疑似扫描版，无文本层可提取（先跑 action=stats 查看诊断）。"
        lines, used, last_no = [], 0, pf
        for no in range(pf, pt + 1):
            chunk = pages[no - 1] or "（本页无文本层）"
            lines.append("\n## p.%d\n%s" % (no, chunk))
            last_no = no
            used += len(chunk)
            if used >= mc:
                lines.append("\n…（达到 max_chars=%d 截断，缩小页码范围或调大上限继续）" % mc)
                break
        return "**PDF 文本提取：%s（第 %d-%d 页）**%s" % (os.path.basename(path), pf,
                                                  last_no, "\n".join(lines))
    if action == "search":
        kw = (args.get("query") or "").strip()
        if not kw:
            return "❌ search 动作需要 query（关键词；regex=true 时为正则）"
        if scanned:
            return "⚠ 疑似扫描版，无法在文本层检索（先跑 action=stats 查看诊断）。"
        use_re = bool(args.get("regex", False))
        ci = bool(args.get("ignore_case", True))
        ctx = int(args.get("context", 80) or 80)
        flags = re.IGNORECASE if ci else 0
        try:
            pat = re.compile(kw if use_re else re.escape(kw), flags)
        except re.error as exc:
            return "❌ 正则无效：%s" % exc
        hits, total_hits = [], 0
        for no, text in enumerate(pages, 1):
            for m in pat.finditer(text):
                total_hits += 1
                if len(hits) < 20:
                    a, b = max(0, m.start() - ctx), min(len(text), m.end() + ctx)
                    snippet = ("…" if a else "") + text[a:b].replace("\n", " ") + ("…" if b < len(text) else "")
                    hits.append((no, snippet))
        if not hits:
            return "**PDF 内检索：\"%s\"——0 命中**（%d 页）。换同义词/英文原词再试；扫描版无法检索。" % (kw, len(pages))
        lines = ["**PDF 页码溯源：\"%s\"（共 %d 处命中，展示前 %d 处）**\n" % (kw, total_hits, len(hits))]
        for no, snippet in hits:
            lines.append("- p.%d：%s" % (no, snippet))
        lines.append("\n（引用文中说法时带上 p.N 页码；这些片段就是接地问答的依据，不要超出片段内容发挥。）")
        return "\n".join(lines)
    return "❌ 未知 action：%s（支持 stats / extract / search）" % action

# ======================================================================
# 7. 统计推断（零依赖：t/F 分布经正则化不完全 Beta，卡方经不完全 Gamma）
# ======================================================================
def _gammln(x):
    """ln Γ(x)，Lanczos 近似（g=7），|误差| < 1e-13。"""
    coef = [0.99999999999980993, 676.5203681218851, -1259.1392167224028,
            771.32342877765313, -176.61502916214059, 12.507343278686905,
            -0.13857109526572012, 9.9843695780195716e-6, 1.5056327351493116e-7]
    if x < 0.5:
        return math.log(math.pi / math.sin(math.pi * x)) - _gammln(1.0 - x)
    x -= 1.0
    a, t = coef[0], x + 7.5
    for i in range(1, 9):
        a += coef[i] / (x + i)
    return 0.5 * math.log(2 * math.pi) + (x + 0.5) * math.log(t) - t + math.log(a)

def _betacf(a, b, x):
    """正则化不完全 Beta 的修正 Lentz 连分数（Numerical Recipes）。"""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-12:
            break
    return h

def _betai(a, b, x):
    """正则化不完全 Beta 函数 I_x(a,b)。"""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    ln_bt = (_gammln(a + b) - _gammln(a) - _gammln(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b

def _t_sf(t, df):
    """t 分布上侧尾概率 P(T > t)（t 取绝对值）。"""
    if df <= 0:
        return float("nan")
    t = abs(float(t))
    return 0.5 * _betai(df / 2.0, 0.5, df / (df + t * t))

def _f_sf(f, df1, df2):
    """F 分布上侧尾概率 P(F > f)。"""
    if f <= 0:
        return 1.0
    return _betai(df2 / 2.0, df1 / 2.0, df2 / (df2 + df1 * f))

def _chi2_sf(x, df):
    """卡方分布上侧尾概率（级数 + 修正 Lentz 连分数）。"""
    if x <= 0:
        return 1.0
    a, half = df / 2.0, x / 2.0
    front = math.exp(-half + a * math.log(half) - _gammln(a))
    if half < a + 1.0:
        summ, term, ap = 0.0, front / a, a
        for _ in range(1000):
            summ += term
            ap += 1.0
            term *= half / ap
            if abs(term) < abs(summ) * 1e-15:
                break
        return 1.0 - summ
    tiny = 1e-30
    b, d = half + 1.0 - a, 1.0 / (half + 1.0 - a)
    if abs(d) < tiny:
        d = tiny
    c, h = 1.0 / tiny, d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-15:
            break
    return front * h

def _t_ppf(p, df):
    """t 分布分位数（P(T ≤ t) = p），二分法。"""
    lo, hi = -1e3, 1e3
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 1.0 - _t_sf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

def _norm_ppf(p):
    """标准正态分位数，二分法（erf 为 math 内置）。"""
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if 0.5 * (1.0 + math.erf(mid / math.sqrt(2.0))) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)

def _sstd(xs):
    """样本标准差（n-1 分母）。"""
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))

def _quantile(sx, q):
    """有序数组分位数（线性插值，与 numpy 默认一致）。"""
    n = len(sx)
    if n == 1:
        return sx[0]
    pos = q * (n - 1)
    lo = int(math.floor(pos))
    frac = pos - lo
    hi = min(lo + 1, n - 1)
    return sx[lo] * (1 - frac) + sx[hi] * frac

# 狄克松检验临界值 D(α, n)，摘自 GB/T 4883-2008 表（单侧）。
# r 公式随 n 分四段：n≤7 用 r10，8~10 用 r11，11~13 用 r21，14~30 用 r22，
# 故临界值序列在段界处（8、11、14）不单调，属表本身的性质而非笔误。
_DIXON_TABLE = {
    0.05: {3: 0.941, 4: 0.765, 5: 0.642, 6: 0.560, 7: 0.507,
           8: 0.554, 9: 0.512, 10: 0.477,
           11: 0.576, 12: 0.546, 13: 0.521,
           14: 0.546, 15: 0.525, 16: 0.507, 17: 0.490, 18: 0.475, 19: 0.462,
           20: 0.450, 21: 0.440, 22: 0.430, 23: 0.421, 24: 0.413, 25: 0.406,
           26: 0.399, 27: 0.393, 28: 0.387, 29: 0.381, 30: 0.376},
    0.01: {3: 0.988, 4: 0.889, 5: 0.780, 6: 0.698, 7: 0.637,
           8: 0.683, 9: 0.635, 10: 0.597,
           11: 0.705, 12: 0.679, 13: 0.648,
           14: 0.674, 15: 0.647, 16: 0.624, 17: 0.605, 18: 0.589, 19: 0.575,
           20: 0.561, 21: 0.547, 22: 0.534, 23: 0.521, 24: 0.509, 25: 0.498,
           26: 0.487, 27: 0.477, 28: 0.467, 29: 0.457, 30: 0.448},
}

def _dixon_stat(sx, high=True):
    """狄克松比值（sx 升序）。高端检 x_n、低端检 x_1，公式分段随 n（GB/T 4883-2008）。"""
    n = len(sx)
    if n < 3:
        return None
    if high:
        if n <= 7:
            return (sx[-1] - sx[-2]) / (sx[-1] - sx[0])          # r10
        if n <= 10:
            return (sx[-1] - sx[-2]) / (sx[-1] - sx[1])          # r11
        if n <= 13:
            return (sx[-1] - sx[-3]) / (sx[-1] - sx[1])          # r21
        return (sx[-1] - sx[-3]) / (sx[-1] - sx[2])              # r22
    if n <= 7:
        return (sx[1] - sx[0]) / (sx[-1] - sx[0])                # r10'
    if n <= 10:
        return (sx[1] - sx[0]) / (sx[-2] - sx[0])                # r11'
    if n <= 13:
        return (sx[2] - sx[0]) / (sx[-2] - sx[0])                 # r21'
    return (sx[2] - sx[0]) / (sx[-3] - sx[0])                     # r22'

def _grubbs_crit(n, alpha):
    """格拉布斯双侧临界值（Grubbs & Beck 1972 精确式，NIST/SEMATECH 手册采用）：
    G = (n-1)/√n · √(t²/(n-2+t²))，t 为 t(n-2) 的 1-α/(2n) 分位数——由 _t_ppf 精确生成，
    与教科书查表值一致（如 n=3 双侧 0.05 → 1.153），无需硬编码临界值表。"""
    t = _t_ppf(1.0 - alpha / (2.0 * n), n - 2)
    return (n - 1.0) / math.sqrt(n) * math.sqrt(t * t / (n - 2.0 + t * t))

def _weibull_fit(xs):
    """两参数 Weibull 拟合：中位秩（Bernard 公式 F_i=(i-0.3)/(n+0.4)）线性化最小二乘。
    ln ln(1/(1-F)) = m·ln σ − m·ln σ₀ → 形状 m=斜率，尺度 σ₀=exp(−截距/m)。
    返回 (m, sigma0, r2)；退化数据返回 None。"""
    s = sorted(xs)
    n = len(s)
    lx = [math.log(v) for v in s]
    ly = [math.log(math.log(1.0 / (1.0 - (i - 0.3) / (n + 0.4))))
          for i in range(1, n + 1)]
    coef = _polyfit(lx, ly, 1)
    if coef is None or coef[1] <= 0:
        return None
    m = coef[1]
    s0 = math.exp(-coef[0] / m)
    my = sum(ly) / n
    sst = sum((v - my) ** 2 for v in ly)
    if sst <= 0:
        return None
    ssr = sum((y - (coef[0] + coef[1] * x)) ** 2 for x, y in zip(lx, ly))
    return m, s0, 1.0 - ssr / sst

def tool_stats(args):
    """统计分析：describe / ttest / anova / normality / ci / power / outlier / weibull。"""
    action = str(args.get("action", "describe")).lower()
    alpha = float(args.get("alpha", 0.05))

    def vals(key):
        raw = args.get(key)
        if isinstance(raw, list) and raw:
            try:
                return [float(v) for v in raw]
            except (TypeError, ValueError):
                return None
        return None

    def p_line(p):
        if p is None or math.isnan(p):
            return "p = NaN"
        if p < 1e-4:
            return "p = %.2e" % p
        return "p = %.4f" % p

    if action == "describe":
        xs = vals("data")
        if xs is None:
            return "❌ 请给 data 数组（数值）"
        n = len(xs)
        mean = sum(xs) / n
        sd = _sstd(xs)
        s = sorted(xs)
        lines = ["**描述统计（n = %d）**" % n,
                 "- 均值 %s | 样本标准差 %s | 标准误 %s" %
                 (_fmt(mean), _fmt(sd), _fmt(sd / math.sqrt(n))),
                 "- 中位数 %s | Q1 %s | Q3 %s" %
                 (_fmt(_quantile(s, 0.5)), _fmt(_quantile(s, 0.25)), _fmt(_quantile(s, 0.75))),
                 "- min %s | max %s | 极差 %s" % (_fmt(s[0]), _fmt(s[-1]), _fmt(s[-1] - s[0]))]
        if n >= 3 and sd > 0:
            m2 = sum((x - mean) ** 2 for x in xs) / n
            lines.append("- 偏度 %s | 超额峰度 %s（总体矩，未做小样本校正）" %
                         (_fmt(sum((x - mean) ** 3 for x in xs) / n / m2 ** 1.5),
                          _fmt(sum((x - mean) ** 4 for x in xs) / n / m2 ** 2 - 3.0)))
        lines.append("\n（正态性判断用 action=normality；组间比较用 ttest / anova；区间估计用 ci；"
                     "异常值剔除用 outlier；强度散布 Weibull 用 weibull）")
        return "\n".join(lines)

    if action == "ttest":
        a = vals("a")
        if a is None or len(a) < 2:
            return "❌ ttest 需要 a 数组（n ≥ 2）"
        na, ma = len(a), sum(a) / len(a)
        b = vals("b")
        if b is None:
            mu = float(args.get("mu", 0.0))
            sd = _sstd(a)
            if sd == 0:
                return "❌ a 的方差为 0，无法检验"
            t = (ma - mu) / (sd / math.sqrt(na))
            df, p = na - 1, 2 * _t_sf(t, na - 1)
            return ("**单样本 t 检验**（n = %d）\nH0: μ = %s\n- t = %s, df = %d, %s\n"
                    "- 均值 %s, 标准差 %s, Cohen's d = %s\n- 结论：%s（α = %s）"
                    % (na, _fmt(mu), _fmt(t), df, p_line(p), _fmt(ma), _fmt(sd),
                       _fmt((ma - mu) / sd), "拒绝 H0" if p < alpha else "不拒绝 H0", _fmt(alpha)))
        if args.get("paired"):
            if len(b) != na:
                return "❌ 配对检验要求 a、b 等长"
            dd = [x - y for x, y in zip(a, b)]
            nd, md = len(dd), sum(dd) / len(dd)
            sdd = _sstd(dd)
            if sdd == 0:
                return "❌ 差值方差为 0，无法检验"
            t = md / (sdd / math.sqrt(nd))
            p = 2 * _t_sf(t, nd - 1)
            return ("**配对 t 检验**（n = %d 对）\n- 差值均值 %s，差值标准差 %s\n"
                    "- t = %s, df = %d, %s\n- 结论：%s（α = %s）"
                    % (nd, _fmt(md), _fmt(sdd), _fmt(t), nd - 1, p_line(p),
                       "拒绝 H0" if p < alpha else "不拒绝 H0", _fmt(alpha)))
        nb, mb = len(b), sum(b) / len(b)
        va = sum((x - ma) ** 2 for x in a) / (na - 1)
        vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
        if va <= 0 or vb <= 0:
            return "❌ 某组方差为 0，无法检验"
        if args.get("equal_var"):
            sp2 = ((na - 1) * va + (nb - 1) * vb) / (na + nb - 2)
            se, df = math.sqrt(sp2 * (1.0 / na + 1.0 / nb)), na + nb - 2
            kind = "合并方差 Student t"
        else:
            se = math.sqrt(va / na + vb / nb)
            df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
            kind = "Welch（默认，不假设方差齐性）"
        t = (ma - mb) / se
        p = 2 * _t_sf(t, df)
        sp = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
        return ("**两独立样本 t 检验（%s）**\nH0: μ1 = μ2\n- A: n=%d，均值 %s；B: n=%d，均值 %s\n"
                "- t = %s, df = %s, %s\n- Cohen's d = %s\n- 结论：%s（α = %s）"
                % (kind, na, _fmt(ma), nb, _fmt(mb), _fmt(t), _fmt(df), p_line(p),
                   _fmt((ma - mb) / sp) if sp > 0 else "N/A",
                   "拒绝 H0" if p < alpha else "不拒绝 H0", _fmt(alpha)))

    if action == "anova":
        groups = args.get("groups")
        if not isinstance(groups, list) or len(groups) < 2:
            return "❌ anova 需要 groups（≥2 个数值数组的数组）"
        try:
            gs = [[float(v) for v in g] for g in groups]
        except (TypeError, ValueError):
            return "❌ groups 每个元素须为数值数组"
        if any(len(g) < 2 for g in gs):
            return "❌ 每组至少 2 个样本"
        N, k = sum(len(g) for g in gs), len(gs)
        grand = sum(sum(g) for g in gs) / N
        ssb = sum(len(g) * (sum(g) / len(g) - grand) ** 2 for g in gs)
        ssw = sum(sum((x - sum(g) / len(g)) ** 2 for x in g) for g in gs)
        msw = ssw / (N - k)
        if msw == 0:
            return "❌ 组内方差为 0（各组内部无波动），无法检验"
        F, p = (ssb / (k - 1)) / msw, _f_sf((ssb / (k - 1)) / msw, k - 1, N - k)
        return ("**单因素方差分析（k = %d 组，N = %d）**\nH0: 各组总体均值相等\n"
                "- 组均值：%s\n- F = %s, df = (%d, %d), %s\n- 效应量 η² = %s\n- 结论：%s（α = %s）\n"
                "（显著 ≠ 两两都不同；事后比较请用 Bonferroni 校正：α ÷ %d 组对）"
                % (k, N, ", ".join("%s(n=%d)" % (_fmt(sum(g) / len(g)), len(g)) for g in gs),
                   _fmt(F), k - 1, N - k, p_line(p), _fmt(ssb / (ssb + ssw)),
                   "拒绝 H0（至少一组均值不同）" if p < alpha else "不拒绝 H0", _fmt(alpha),
                   k * (k - 1) // 2))

    if action == "normality":
        xs = vals("data")
        if xs is None or len(xs) < 8:
            return "❌ normality 建议 n ≥ 8（JB 检验小样本功效低）"
        n = len(xs)
        mean = sum(xs) / n
        m2 = sum((x - mean) ** 2 for x in xs) / n
        if m2 == 0:
            return "❌ 数据无波动"
        skew = sum((x - mean) ** 3 for x in xs) / n / m2 ** 1.5
        kurt = sum((x - mean) ** 4 for x in xs) / n / m2 ** 2
        jb = n / 6.0 * (skew ** 2 + (kurt - 3) ** 2 / 4.0)
        p = _chi2_sf(jb, 2)
        return ("**正态性检验（Jarque-Bera）**\n- 偏度 %s（正态为 0）| 峰度 %s（正态为 3）\n"
                "- JB = %s, %s\n- 结论：%s（α = %s）\n"
                "（n < 30 时 JB 功效有限：p > α 只是'未测出非正态'，不是'证明正态'；"
                "严格场景用 scipy.stats.shapiro 复核）"
                % (_fmt(skew), _fmt(kurt), _fmt(jb), p_line(p),
                   "拒绝正态假设" if p < alpha else "未发现偏离正态", _fmt(alpha)))

    if action == "ci":
        xs = vals("data")
        if xs is None or len(xs) < 2:
            return "❌ ci 需要 data（n ≥ 2）"
        conf = float(args.get("confidence", 0.95))
        if not (0.5 < conf < 0.999):
            return "❌ confidence 取值 (0.5, 0.999)"
        n, mean = len(xs), sum(xs) / len(xs)
        sd = _sstd(xs)
        tc = _t_ppf(1 - (1 - conf) / 2, n - 1)
        half = tc * sd / math.sqrt(n)
        return ("**均值的置信区间（t 区间，置信水平 %g%%）**\n- n = %d, 均值 %s, 标准差 %s, t 临界值 %s\n"
                "- CI = [%s, %s]（半宽 %s）\n（方差未知用 t 不用 z；sd=0 时区间退化为点）"
                % (conf * 100, n, _fmt(mean), _fmt(sd), _fmt(tc),
                   _fmt(mean - half), _fmt(mean + half), _fmt(half)))

    if action == "power":
        delta, sd = args.get("delta"), args.get("sd")
        if delta is None or sd is None:
            return "❌ power 需要 delta（要检出的均值差）与 sd（合并标准差）"
        delta, sd = float(delta), float(sd)
        if sd <= 0 or delta == 0:
            return "❌ delta、sd 须 > 0"
        pw, alpha = float(args.get("power", 0.8)), float(args.get("alpha", 0.05))
        if not (0.5 < pw < 0.999) or not (0.001 < alpha < 0.5):
            return "❌ power 取值 (0.5, 0.999)，alpha 取值 (0.001, 0.5)"
        n1 = math.ceil(2 * ((_norm_ppf(1 - alpha / 2) + _norm_ppf(pw)) * sd / delta) ** 2)
        return ("**两独立样本 t 检验的样本量估算（正态近似）**\n"
                "- δ = %s, 合并 sd = %s, 功效 %g, α = %g\n- 每组约需 **n = %d**（共 %d）\n"
                "（正态近似，比精确 t 略保守；配对设计把 sd 换成差值标准差）"
                % (_fmt(delta), _fmt(sd), pw, alpha, n1, 2 * n1))

    if action == "outlier":
        # GB/T 4883 两级判定：≥ 0.01 临界 → 统计离群值（剔除）；
        # 仅 ≥ 检出水平（alpha，默认 0.05）→ 歧离值（保留，提示查物理原因）
        xs = vals("data")
        if xs is None or len(xs) < 3:
            return "❌ outlier 需要 data 数组（n ≥ 3）"
        crit_name = str(args.get("criterion", "grubbs")).lower()
        if crit_name not in ("grubbs", "dixon"):
            return "❌ criterion 取 grubbs（默认，n 不限）| dixon（n ≤ 30，GB/T 4883 查表法）"
        if crit_name == "dixon" and len(xs) > 30:
            return "❌ 狄克松准则仅适用 n ≤ 30（国标表范围），请用 criterion=grubbs"
        n0, cur = len(xs), list(xs)
        lines, removed, rnd = [], [], 0
        while len(cur) >= 3:
            rnd += 1
            s = sorted(cur)
            n = len(s)
            if crit_name == "grubbs":
                mean, sd = sum(s) / n, _sstd(s)
                if sd == 0:
                    lines.append("- 第 %d 轮：数据无波动，停止" % rnd)
                    break
                hi, lo = s[-1] - mean, mean - s[0]
                if hi >= lo:
                    g, side, cand = hi / sd, "高", s[-1]
                else:
                    g, side, cand = lo / sd, "低", s[0]
                c_hi, c_out = _grubbs_crit(n, 0.01), _grubbs_crit(n, alpha)
                stat_name = "G = %s" % _fmt(g)
            else:
                rh, rl = _dixon_stat(s, True), _dixon_stat(s, False)
                if rh is None or rl is None or s[-1] == s[0]:
                    lines.append("- 第 %d 轮：数据无波动，停止" % rnd)
                    break
                if rh >= rl:
                    d, side, cand = rh, "高", s[-1]
                else:
                    d, side, cand = rl, "低", s[0]
                c_hi, c_out = _DIXON_TABLE[0.01][n], _DIXON_TABLE.get(round(alpha, 2), {}).get(n)
                if c_out is None:
                    return "❌ 狄克松表只支持检出水平 0.05 / 0.01，当前 alpha = %s" % _fmt(alpha)
                stat_name = "D = %s" % _fmt(d)
            stat_val = g if crit_name == "grubbs" else d
            if stat_val >= c_hi:
                removed.append(cand)
                lines.append("- 第 %d 轮：%s端值 %s，%s ≥ 0.01 临界 %s → **统计离群值，剔除**"
                             % (rnd, side, _fmt(cand), stat_name, _fmt(c_hi)))
                cur.remove(cand)
                continue
            if stat_val >= c_out:
                lines.append("- 第 %d 轮：%s端值 %s，%s ≥ %s 临界 %s 但 < 0.01 临界 %s → **歧离值，保留**（找不到物理原因就不剔除）"
                             % (rnd, side, _fmt(cand), stat_name, _fmt(alpha), _fmt(c_out), _fmt(c_hi)))
                break
            lines.append("- 第 %d 轮：%s，小于 %s 临界 %s → 无异常，停止"
                         % (rnd, stat_name, _fmt(alpha), _fmt(c_out)))
            break
        kept_n = len(cur)
        lines.insert(0, "**异常值检验（GB/T 4883 · %s，n = %d → %d）**"
                     % ("格拉布斯双侧（t 精确临界）" if crit_name == "grubbs" else "狄克松", n0, kept_n))
        if removed:
            lines.append("- 已剔除 %d 个（%s）" % (len(removed), ", ".join(_fmt(v) for v in removed)))
            lines.append("- 保留 n = %d：均值 %s，标准差 %s（原：均值 %s，标准差 %s）"
                         % (kept_n, _fmt(sum(cur) / kept_n), _fmt(_sstd(cur)),
                            _fmt(sum(xs) / n0), _fmt(_sstd(xs))))
            if len(removed) > max(1, n0 // 10):
                lines.append("⚠ 剔除比例超过 1/10：优先怀疑测量系统或数据录入问题，不要机械剔除")
            lines.append("（剔除后再做 normality 检验正态性；被剔除值务必在报告中交代）")
        else:
            lines.append("- 未剔除任何值，保留 n = %d" % kept_n)
        return "\n".join(lines)

    if action == "weibull":
        xs = vals("data")
        if xs is None or len(xs) < 3:
            return "❌ weibull 需要 data（强度数组，n ≥ 3）"
        if any(v <= 0 for v in xs):
            return "❌ Weibull 拟合要求强度值全部为正"
        fit = _weibull_fit(xs)
        if fit is None:
            return "❌ 数据退化（全部相同或无波动），无法拟合"
        m, s0, r2 = fit
        b10 = s0 * (-math.log(0.9)) ** (1.0 / m)
        lines = ["**Weibull 强度分析（两参数，中位秩线性回归，n = %d）**" % len(xs),
                 "- Weibull 模数 m = %s（散布越小越大；陶瓷/岩石典型 5~20）" % _fmt(m),
                 "- 特征强度 σ₀ = %s（破坏概率 63.2%% 对应的应力水平）" % _fmt(s0),
                 "- 线性化 R² = %s（< 0.95 时慎用两参数外推）" % _fmt(r2),
                 "- B10 强度（破坏概率 10%%）= %s" % _fmt(b10)]
        if args.get("stress") is not None:
            sig = float(args["stress"])
            if sig <= 0:
                return "❌ stress 须为正应力值"
            pf = 1.0 - math.exp(-((sig / s0) ** m))
            lines.append("- 预测：σ = %s → 破坏概率 P_f = %s，存活率 %s"
                         % (_fmt(sig), _fmt(pf), _fmt(1.0 - pf)))
        lines.append("（n < 8 时 m 的估计误差大；未建模体积效应——不同尺寸试件的结果不能直接换算）")
        return "\n".join(lines)

    return "❌ 未知 action：%s（支持 describe / ttest / anova / normality / ci / power / outlier / weibull）" % action

# ======================================================================
# 8. 不确定度与误差传播（GUM 一阶，AST 数值偏导）
# ======================================================================
def tool_errors(args):
    action = str(args.get("action", "propagate")).lower()
    if action == "propagate":
        formula = (args.get("formula") or "").strip()
        vs, us = args.get("vars") or {}, args.get("uncertainties") or {}
        if not formula or not vs:
            return "❌ propagate 需要 formula 与 vars={符号: 数值}，uncertainties={符号: u(x)}"
        try:
            variables = {str(k): float(v) for k, v in vs.items()}
        except (TypeError, ValueError):
            return "❌ vars 的值须为数值"
        uncs = {}
        for k, v in us.items():
            try:
                uncs[str(k)] = float(v)
            except (TypeError, ValueError):
                return "❌ uncertainties 的值须为数值：%s" % k
        try:
            base = _safe_eval(formula, variables)
        except Exception as exc:
            return "❌ 公式求值失败：%s" % exc
        lines = ["**不确定度传播（GUM 一阶）**：y = %s" % formula, "y = %s" % _fmt(base)]
        total, contribs = 0.0, []
        for name in sorted(uncs):
            ux = uncs[name]
            if ux < 0:
                return "❌ %s 的不确定度为负" % name
            if name not in variables:
                continue
            h = max(abs(variables[name]), 1.0) * 1e-6
            up, lo = dict(variables), dict(variables)
            up[name] = variables[name] + h
            lo[name] = variables[name] - h
            try:
                deriv = (_safe_eval(formula, up) - _safe_eval(formula, lo)) / (2 * h)
            except Exception:
                deriv = float("nan")
            c = deriv * ux
            contribs.append((name, ux, deriv, c))
            total += c * c
        if not contribs:
            return "❌ 公式中的符号没有对应不确定度：%s" % formula
        uc = math.sqrt(total)
        rel = abs(uc / base) if base else float("nan")
        for name, ux, deriv, c in contribs:
            lines.append("- %s = %s ± %s → ∂y/∂%s = %s → 贡献 %s"
                          % (name, _fmt(variables[name]), _fmt(ux), name, _fmt(deriv), _fmt(abs(c))))
        lines.append("\n**合成标准不确定度 u_c = %s**（相对 %s）"
                     % (_fmt(uc), _fmt(rel) if not math.isnan(rel) else "∞"))
        lines.append("**扩展不确定度 U（k=2，约 95%%）= %s**" % _fmt(2 * uc))
        lines.append("结果：**y = %s ± %s**（k=2）" % (_fmt(base), _fmt(2 * uc)))
        lines.append("（一阶传播忽略高阶项与相关性；强相关输入须人工合成协方差项）")
        return "\n".join(lines)
    if action == "regress":
        xs = [float(v) for v in (args.get("x") or [])]
        ys = [float(v) for v in (args.get("y") or [])]
        n = len(xs)
        if n < 3 or n != len(ys):
            return "❌ regress 需要 x / y 等长且 n ≥ 3"
        xbar, ybar = sum(xs) / n, sum(ys) / n
        sxx = sum((x - xbar) ** 2 for x in xs)
        if sxx == 0:
            return "❌ x 无波动"
        sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
        slope, intercept = sxy / sxx, ybar - (sxy / sxx) * xbar
        sse = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        s_res = math.sqrt(sse / (n - 2))
        sb, sa = s_res / math.sqrt(sxx), s_res * math.sqrt(1.0 / n + xbar * xbar / sxx)
        tc = _t_ppf(0.975, n - 2)
        sst = sum((y - ybar) ** 2 for y in ys)
        r = sxy / math.sqrt(sxx * sst) if sst > 0 else float("nan")
        return ("**线性回归不确定度（OLS，95%% CI）**\n- 斜率 b = %s ± %s（95%%CI [%s, %s]）\n"
                "- 截距 a = %s ± %s（95%%CI [%s, %s]）\n- 残差标准差 s = %s | 相关系数 r = %s\n"
                "（n-2 = %d；x 重复测量或 x 有误差时此区间偏乐观——请用正交回归）"
                % (_fmt(slope), _fmt(sb), _fmt(slope - tc * sb), _fmt(slope + tc * sb),
                   _fmt(intercept), _fmt(sa), _fmt(intercept - tc * sa), _fmt(intercept + tc * sa),
                   _fmt(s_res), _fmt(r), n - 2))
    return "❌ 未知 action：%s（支持 propagate / regress）" % action

# ======================================================================
# 9. 实验设计（零依赖：素数域生成正交表 / 全因子 / 拉丁超立方）
# ======================================================================
def _gf_runs(p, k):
    """p^k 个运行的基因素水平组合（标准序：因子 A 变化最慢）。"""
    runs = []
    for i in range(p ** k):
        v, row = i, [0] * k
        for j in range(k - 1, -1, -1):
            row[j] = v % p
            v //= p
        runs.append(row)
    return runs

def _coeff_vectors(p, k):
    """按（最高非零位置，字典序）枚举 GF(p)^k 非零向量：A; B,A+B,2A+B; C,..."""
    out = []
    for hi in range(k):
        lowers = [[]]
        for _ in range(hi):
            lowers = [pre + [v] for pre in lowers for v in range(p)]
        for lead in range(1, p):
            for pre in lowers:
                out.append(tuple(pre + [lead] + [0] * (k - hi - 1)))
    return out

def _vec_norm(vec, p):
    """系数向量按首非零元归一（去比例重复）。"""
    lead = 0
    for v in vec:
        if v % p:
            lead = v % p
            break
    if lead == 0:
        return tuple(vec)
    inv = next(i for i in range(1, p) if (lead * i) % p == 1)
    return tuple((x * inv) % p for x in vec)

def _ortho_design(p, k, max_cols):
    """GF(p) 上生成正交表列（与经典 Taguchi 表等价：任两列正交）。"""
    runs = _gf_runs(p, k)
    cols, seen = [], set()
    for vec in _coeff_vectors(p, k):
        nv = _vec_norm(vec, p)
        if nv in seen:
            continue
        seen.add(nv)
        col = tuple(sum(vec[j] * r[j] for j in range(k)) % p for r in runs)
        cols.append((vec, col))
        if len(cols) >= max_cols:
            break
    return runs, cols

def tool_doe(args):
    action = str(args.get("action", "ortho")).lower()
    if action == "ortho":
        runs_name = args.get("runs")
        if runs_name:
            m = re.match(r"L(\d+)", str(runs_name).upper())
            if not m:
                return "❌ runs 应形如 L8 / L9 / L16"
            spec = {4: (2, 2), 8: (2, 3), 9: (3, 2), 16: (2, 4),
                    25: (5, 2), 27: (3, 3), 32: (2, 5)}
            n_runs = int(m.group(1))
            if n_runs not in spec:
                return ("❌ 支持 L4/L8/L16/L32/L9/L27/L25（素数幂标准表）；"
                        "混水平表 L12/L18 不在零依赖范围内，改用 fullfact 筛选")
            p, k = spec[n_runs]
        elif args.get("p"):
            p, k = int(args["p"]), int(args.get("factors", 2))
            if p not in (2, 3, 5, 7) or k < 2 or p ** k > 128:
                return "❌ p 支持 2/3/5/7，factors ≥ 2，且运行数 p^factors ≤ 128"
            n_runs = p ** k
        else:
            return "❌ ortho 需要 runs=L8 这类标准表名，或 p=2/3/5/7 + factors"
        want = int(args.get("max_factors") or min(15, n_runs - 1))
        want = max(1, min(want, n_runs - 1))
        base_rows, cols = _ortho_design(p, k, want)
        lines = ["**正交表 L%d(%d^%d)**（%d 次运行 × %d 列因素，素数域生成保证正交性）"
                 % (n_runs, p, len(cols), n_runs, len(cols)),
                 "\n| Run | %s |" % " | ".join("F%d" % (i + 1) for i in range(len(cols))),
                 "|---|%s|" % ("---|" * len(cols))]
        col_vals = [c[1] for c in cols]
        for ri in range(n_runs):
            lines.append("| %d | %s |" % (ri + 1, " | ".join(str(col_vals[ci][ri] + 1)
                                                            for ci in range(len(cols)))))
        lines.append("\n正交性：任两列的水平组合各出现 %d 次。水平用 1 起编号。"
                     "用法：可控因素放前几列，空列留作误差估计；交互列=两列水平组合另算。"
                     % (n_runs // (p * p)))
        return "\n".join(lines)
    if action == "fullfact":
        levels = args.get("levels")
        if not isinstance(levels, list) or not levels:
            return "❌ fullfact 需要 levels（各因素水平数，如 [2, 2, 3]）"
        try:
            levels = [int(v) for v in levels]
        except (TypeError, ValueError):
            return "❌ levels 须为整数数组"
        if any(v < 2 for v in levels) or len(levels) > 8:
            return "❌ 每因素 ≥ 2 水平且因素 ≤ 8"
        total = 1
        for v in levels:
            total *= v
        if total > 1296:
            return "❌ 全因子 %d 组合过多（上限 1296）——因素多时改用 ortho 正交表" % total
        rows = []
        def rec(i, cur):
            if i == len(levels):
                rows.append(tuple(cur))
                return
            for v in range(1, levels[i] + 1):
                cur.append(v)
                rec(i + 1, cur)
                cur.pop()
        rec(0, [])
        return ("**全因子设计 %s**（%d 次运行）\n组合：%s\n（全部主效应与交互效应可估；"
                "运行数随水平数指数增长）"
                % (" × ".join(str(v) for v in levels), len(rows),
                   "；".join("(%s)" % ",".join(map(str, r)) for r in rows)))
    if action == "lhs":
        n, dims, seed = int(args.get("samples", 20) or 20), int(args.get("dims", 3) or 3), \
            int(args.get("seed", 42) or 42)
        if not (2 <= n <= 500) or not (1 <= dims <= 10):
            return "❌ samples 2-500，dims 1-10"
        state = [seed & 0x7FFFFFFF or 1]
        def rnd():
            state[0] = (1103515245 * state[0] + 12345) % 2147483648
            return state[0] / 2147483648.0
        cols = []
        for _ in range(dims):
            perm = list(range(n))
            for i in range(n - 1, 0, -1):
                j = int(rnd() * (i + 1))
                perm[i], perm[j] = perm[j], perm[i]
            cols.append([(perm[i] + rnd()) / n for i in range(n)])
        lines = ["**拉丁超立方抽样 LHS(n=%d, dims=%d, seed=%d)**（每维 [0,1) 均分 n 层、每层恰 1 点）"
                 % (n, dims, seed),
                 "\n| Run | %s |" % " | ".join("x%d" % (d + 1) for d in range(dims)),
                 "|---|%s|" % ("---|" * dims)]
        for i in range(n):
            lines.append("| %d | %s |" % (i + 1, " | ".join(_fmt(cols[d][i]) for d in range(dims))))
        lines.append("\n（把 [0,1) 线性映射到各参数区间；改 seed 得不同但同等均匀的方案）")
        return "\n".join(lines)
    return "❌ 未知 action：%s（支持 ortho / fullfact / lhs）" % action

# ======================================================================
# 10. LaTeX 写作生成（booktabs 三线表 / 图环境 / 公式环境）
# ======================================================================
def tool_tex(args):
    action = str(args.get("action", "table")).lower()
    if action == "table":
        headers, rows = args.get("headers") or [], args.get("rows")
        csv_path = args.get("csv_path")
        if csv_path:
            if not os.path.exists(csv_path):
                return "❌ 文件不存在：%s" % csv_path
            try:
                with open(csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
                    text = f.read()
                parsed = list(csv.reader(text.splitlines(),
                                         delimiter=_sniff_delimiter(text[:2048])))
                parsed = [r for r in parsed if any(c.strip() for c in r)]
                if not parsed:
                    return "❌ CSV 为空：%s" % csv_path
                headers, rows = parsed[0], parsed[1:]
            except Exception as exc:
                return "❌ CSV 读取失败：%s" % exc
        if not headers or not rows:
            return "❌ table 需要 headers + rows（或给 csv_path 直读数据）"
        align = args.get("align")
        if not align:
            def col_type(ci):
                cells = [r[ci] if ci < len(r) and str(r[ci]).strip() else None for r in rows]
                return "r" if all(c is not None and _parse_cell_float(c) is not None for c in cells) else "l"
            align = "".join(col_type(i) for i in range(len(headers)))
        caption, label = args.get("caption", ""), args.get("label", "")
        truncated = False
        if len(rows) > 40:
            rows, truncated = rows[:40], True
        out = ["\\begin{table}[htbp]", "\\centering"]
        cap = "\\caption{%s}" % _tex_escape(caption) if caption else ""
        if caption and label:
            cap += "\\label{%s}" % label
        if cap:
            out.append(cap)
        elif label:
            out.append("\\label{%s}" % label)
        out.append("\\begin{tabular}{%s}" % align)
        out.append("\\toprule")
        out.append(" & ".join(_tex_escape(str(h)) for h in headers) + " \\\\")
        out.append("\\midrule")
        for r in rows:
            out.append(" & ".join(_tex_escape(str(r[i]) if i < len(r) else "")
                                  for i in range(len(headers))) + " \\\\")
        out.append("\\bottomrule")
        out.append("\\end{tabular}")
        out.append("\\end{table}")
        note = ("\n（数据超过 40 行已截断展示，全量请分表或用长表 longtable）" if truncated else "")
        return ("**LaTeX 三线表**（需导言区 \\usepackage{booktabs}）\n\n```latex\n%s\n```%s\n"
                "（数值列已自动右对齐、文本列左对齐；可传 align 覆盖，如 \"lccr\"）"
                % ("\n".join(out), note))
    if action == "figure":
        files = args.get("files") or []
        if not files:
            return "❌ figure 需要 files（图片路径数组，或 [{path, caption}] 子图）"
        caption, label = args.get("caption", ""), args.get("label", "")
        width = args.get("width", r"0.9\columnwidth")
        norm = [(f["path"], f.get("caption", "")) if isinstance(f, dict) else (str(f), "")
                for f in files]
        out = ["\\begin{figure}[htbp]", "\\centering"]
        if len(norm) == 1:
            out.append("\\includegraphics[width=%s]{%s}" % (width, norm[0][0]))
            cap = "\\caption{%s}" % _tex_escape(caption)
            if label:
                cap += "\\label{%s}" % label
            out.append(cap)
            pkg = ""
        else:
            subw = args.get("subwidth", r"0.48\textwidth")
            for i, (p, cap_sub) in enumerate(norm, 1):
                out.append("\\begin{subfigure}{%s}" % subw)
                out.append("    \\centering")
                out.append("    \\includegraphics[width=\\linewidth]{%s}" % p)
                out.append("    \\caption{%s}" % _tex_escape(cap_sub))
                out.append("\\end{subfigure}%s" % ("" if i == len(norm) else "\n"))
            cap = "\\caption{%s}" % _tex_escape(caption)
            if label:
                cap += "\\label{%s}" % label
            out.append(cap)
            pkg = "（多图需 \\usepackage{subcaption}）"
        out.append("\\end{figure}")
        return "**LaTeX 图环境%s**\n\n```latex\n%s\n```" % (pkg, "\n".join(out))
    if action == "equation":
        expr = (args.get("latex") or args.get("expr") or "").strip()
        if not expr:
            return "❌ equation 需要 latex（公式体，不含 begin/end 环境）"
        label = args.get("label", "")
        out = ["\\begin{equation}", expr]
        if label:
            out.append("\\label{%s}" % label)
        out.append("\\end{equation}")
        hint = "（正文引用：\\eqref{%s}）" % label if label else "（不要编号用 equation*）"
        return "```latex\n%s\n```\n%s" % ("\n".join(out), hint)
    return "❌ 未知 action：%s（支持 table / figure / equation）" % action

# ======================================================================
# 11. BibTeX 库工作台（解析 / 体检 / 去重合并 / 排序）
# ======================================================================
_BIB_REQUIRED = {"article": ["author", "title", "journal", "year"],
                 "inproceedings": ["author", "title", "booktitle", "year"],
                 "incollection": ["author", "title", "booktitle", "year"],
                 "book": ["author", "title", "publisher", "year"],
                 "phdthesis": ["author", "title", "school", "year"],
                 "mastersthesis": ["author", "title", "school", "year"],
                 "techreport": ["author", "title", "institution", "year"]}

_BIB_FIELD_ORDER = ["author", "title", "journal", "booktitle", "institution", "school",
                    "publisher", "year", "volume", "number", "pages", "editor", "doi", "url", "note"]

def _split_top_level(s):
    """按顶层逗号切分（忽略 {} 内与引号内的逗号）。"""
    parts, cur, depth, in_q = [], [], 0, False
    for ch in s:
        if depth == 0:
            if ch == '"' and not in_q:
                in_q = True
            elif ch == '"' and in_q:
                in_q = False
            elif ch == "," and not in_q:
                parts.append("".join(cur))
                cur = []
                continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        cur.append(ch)
    tail = "".join(cur)
    if tail.strip():
        parts.append(tail)
    return parts

def _parse_bib_text(text):
    """解析 BibTeX 文本 → [{type, key, fields}]。跳过 @comment/@string/@preamble。"""
    entries, i, n = [], 0, len(text)
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        m = re.match(r"@(\w+)\s*\{", text[at:])
        if not m or m.group(1).lower() in ("comment", "string", "preamble"):
            i = at + 1
            continue
        typ, j = m.group(1).lower(), at + m.end()
        km = re.match(r"\s*([^,\s{}]+)\s*,", text[j:])
        if not km:
            i = at + 1
            continue
        key, j = km.group(1), j + km.end()
        depth, k = 1, j
        while k < n and depth > 0:
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        fields = {}
        for part in _split_top_level(text[j:k - 1]):
            fm = re.match(r"\s*(\w+)\s*=\s*(.*?)\s*$", part, re.DOTALL)
            if fm:
                name, val = fm.group(1).lower(), fm.group(2).strip()
                if val.startswith("{") and val.endswith("}"):
                    val = val[1:-1]
                elif val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                fields[name] = " ".join(val.split())
        entries.append({"type": typ, "key": key, "fields": fields})
        i = k
    return entries

def _bib_health(entries):
    """库体检：缺失必填 / 重复 key / 重复 DOI / 重复标题 / DOI 格式。"""
    issues, seen_keys, seen_dois, seen_titles = [], set(), {}, {}
    for e in entries:
        f = e["fields"]
        req = _BIB_REQUIRED.get(e["type"])
        if req is None:
            issues.append("⚠ %s（%s）：类型少见，未按标准必填字段检查" % (e["key"], e["type"]))
        else:
            missing = [r for r in req if r not in f or not f[r].strip()]
            if missing:
                issues.append("⚠ %s（%s）：缺必填字段 %s" % (e["key"], e["type"], ", ".join(missing)))
        if "title" in f and f["title"].strip():
            nt = _norm_title(f["title"])
            if nt and nt in seen_titles:
                issues.append("⚠ 疑似重复条目：%s 与 %s（标题相同）" % (e["key"], seen_titles[nt]))
            else:
                seen_titles[nt] = e["key"]
        if f.get("doi", "").strip():
            d = _norm_doi(f["doi"])
            if d in seen_dois:
                issues.append("❌ 重复 DOI：%s 与 %s 均为 %s" % (e["key"], seen_dois[d], d))
            else:
                seen_dois[d] = e["key"]
            if not re.match(r"^10\.\d{4,9}/\S+$", d):
                issues.append("⚠ %s：DOI 格式可疑（应为 10.xxxx/后缀）" % e["key"])
        else:
            issues.append("ℹ %s：无 DOI（可用 labmate_cite 查真实元数据补全）" % e["key"])
        if e["key"] in seen_keys:
            issues.append("❌ 重复 key：%s（BibTeX 会报 Repeated entry）" % e["key"])
        else:
            seen_keys.add(e["key"])
    return issues

def _format_bib_entry(e):
    f = e["fields"]
    ordered = [k for k in _BIB_FIELD_ORDER if k in f] + \
              [k for k in f if k not in _BIB_FIELD_ORDER]
    body = ",\n".join("  %-12s = {%s}" % (k, f[k]) for k in ordered)
    return "@%s{%s,\n%s\n}" % (e["type"], e["key"], body)

def _bib_year(e):
    m = re.search(r"\d{4}", e["fields"].get("year", ""))
    return int(m.group(0)) if m else 0

def tool_bibtex(args):
    action = str(args.get("action", "check")).lower()
    if action not in ("check", "merge", "sort"):
        return "❌ 未知 action：%s（支持 check / merge / sort）" % action
    paths = args.get("bib_paths") or ([args["bib_path"]] if args.get("bib_path") else [])
    paths = [str(p) for p in paths if p]
    if not paths:
        return "❌ 需要 bib_path 或 bib_paths（一个或多个 .bib 文件）"
    all_entries = []
    for p in paths:
        if not os.path.exists(p):
            return "❌ 文件不存在：%s" % p
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            entries = _parse_bib_text(f.read())
        if not entries:
            return "❌ 未解析到 BibTeX 条目（检查 @type{key, 格式）：%s" % p
        all_entries.extend((p, e) for e in entries)
    if action == "check":
        issues = _bib_health([e for _, e in all_entries])
        lines = ["**BibTeX 库体检（%d 个条目）**\n" % len(all_entries)]
        lines.extend("- " + s for s in issues) if issues else lines.append("✅ 未发现问题：必填字段齐全，key/DOI/标题无重复")
        lines.append("\n（只查元数据完整性与重复；条目真伪用 labmate_cite 按 DOI 抽验）")
        return "\n".join(lines)
    merged, dropped = {}, []
    for p, e in all_entries:
        doi = _norm_doi(e["fields"].get("doi", "")) if e["fields"].get("doi") else ""
        nt = _norm_title(e["fields"].get("title", ""))
        dup_key = None
        for k in merged:
            if doi and _norm_doi(merged[k]["fields"].get("doi", "")) == doi:
                dup_key = k
                break
        if dup_key is None and nt:
            for k in merged:
                if _norm_title(merged[k]["fields"].get("title", "")) == nt:
                    dup_key = k
                    break
        if dup_key is not None:
            for fld, val in e["fields"].items():
                if fld not in merged[dup_key]["fields"] and val.strip():
                    merged[dup_key]["fields"][fld] = val
            dropped.append((e["key"], dup_key))
        else:
            if e["key"] in merged:
                base, suf, idx = e["key"], "abcdefghijklmnopqrstuvwxyz", 0
                while e["key"] in merged:
                    e["key"] = base + suf[idx]
                    idx += 1
            merged[e["key"]] = e
    entries = list(merged.values())
    sort_key = str(args.get("sort", "year")).lower()
    if sort_key == "year":
        entries.sort(key=lambda e: -_bib_year(e))
    elif sort_key == "author":
        entries.sort(key=lambda e: e["fields"].get("author", "").lower())
    elif sort_key == "key":
        entries.sort(key=lambda e: e["key"].lower())
    else:
        return "❌ sort 支持 year（默认，新→旧）/ author / key"
    header = "**BibTeX 合并**：%d 个文件 → %d 条（按 %s 排序）" % (len(paths), len(entries), sort_key)
    if dropped:
        header += "\n去重记录：" + "；".join("%s ≈ %s" % (a, b) for a, b in dropped)
    out = "\n\n".join(_format_bib_entry(e) for e in entries)
    return ("%s\n\n```bibtex\n%s\n```\n\n（重复条目已按 DOI/标题合并、字段互补；"
            "写回文件让 AI 直接存盘即可）" % (header, out))

# ======================================================================
# 12. 信号与序列处理（移动平均 / Savitzky-Golay / 插值 / 数值积分）
# ======================================================================
def _solve_linear(M, b):
    """带行主元的高斯消元解 Mx = b（小型稠密系统）。"""
    n = len(M)
    A = [row[:] + [bv] for row, bv in zip(M, b)]
    for i in range(n):
        piv = max(range(i, n), key=lambda r: abs(A[r][i]))
        if abs(A[piv][i]) < 1e-12:
            return None
        A[i], A[piv] = A[piv], A[i]
        for r in range(i + 1, n):
            f = A[r][i] / A[i][i]
            for c2 in range(i, n + 1):
                A[r][c2] -= f * A[i][c2]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = A[i][n] - sum(A[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / A[i][i]
    return x

def _sg_coeffs(window, poly):
    """Savitzky-Golay 平滑系数（deriv=0）：c = (AᵀA)⁻¹Aᵀ 第 0 行。"""
    h = window // 2
    offs = list(range(-h, h + 1))
    m = poly + 1
    At = [[float(o) ** p_ for o in offs] for p_ in range(m)]
    AtA = [[sum(At[p_][j] * At[q][j] for j in range(window)) for q in range(m)] for p_ in range(m)]
    z = _solve_linear(AtA, [1.0] + [0.0] * (m - 1))
    if z is None:
        return None
    return [sum(z[p_] * At[p_][j] for p_ in range(m)) for j in range(window)]

def _fft(a):
    """radix-2 迭代 FFT（位反转置换 + 蝶形合并，O(N log N)）。n 需为 2 的幂。"""
    n = len(a)
    if n == 0:
        return []
    if n & (n - 1):
        raise ValueError("_fft 需 2 的幂长度")
    bits = n.bit_length() - 1
    rev = [0] * n
    for i in range(1, n):
        rev[i] = (rev[i >> 1] >> 1) | ((i & 1) << (bits - 1))
    x = [complex(v, 0.0) for v in a]
    for i in range(n):
        if i < rev[i]:
            x[i], x[rev[i]] = x[rev[i]], x[i]
    size = 2
    while size <= n:
        ang = -2.0 * math.pi / size
        wl = complex(math.cos(ang), math.sin(ang))
        half = size // 2
        for start in range(0, n, size):
            w = complex(1.0, 0.0)
            for k in range(start, start + half):
                u, v = x[k], x[k + half] * w
                x[k], x[k + half] = u + v, u - v
                w *= wl
        size *= 2
    return x

def _dft_naive(a):
    """朴素 O(N²) DFT（测试对拍基准）。"""
    n = len(a)
    out = []
    for k in range(n):
        s = complex(0.0, 0.0)
        for i in range(n):
            ang = -2.0 * math.pi * k * i / n
            s += complex(a[i] * math.cos(ang), a[i] * math.sin(ang))
        out.append(s)
    return out

def tool_signal(args):
    action = str(args.get("action", "smooth")).lower()
    ys = [float(v) for v in (args.get("y") or [])]
    if not ys:
        return "❌ 需要 y 数组（等间距数据可不给 x）"
    if action == "smooth":
        method = str(args.get("method", "ma")).lower()
        w = int(args.get("window", 5) or 5)
        if w < 3 or w > len(ys) or w % 2 == 0:
            return "❌ window 需为奇数且 3 ≤ window ≤ 数据长度（当前 %d 点）" % len(ys)
        if method == "ma":
            h = w // 2
            out = []
            for i in range(len(ys)):
                seg = ys[max(0, i - h): i + h + 1]
                out.append(sum(seg) / len(seg))
            return ("**移动平均平滑（window=%d；端点收缩窗口，长度不变）**\n%s\n"
                    "（简单去噪但会压低峰谷；要保峰形改用 method=savgol）"
                    % (w, ", ".join(_fmt(v) for v in out)))
        if method == "savgol":
            poly = int(args.get("poly", 2) or 2)
            if poly < 1 or poly >= w:
                return "❌ poly 需满足 1 ≤ poly < window"
            c = _sg_coeffs(w, poly)
            if c is None:
                return "❌ 系数求解失败（window/poly 组合退化）"
            h = w // 2
            out = list(ys)
            for i in range(h, len(ys) - h):
                out[i] = sum(c[j] * ys[i - h + j] for j in range(w))
            return ("**Savitzky-Golay 平滑（window=%d, poly=%d；内部点卷积，两端保留原值）**\n%s\n"
                    "（局部多项式拟合：保峰形与峰位，优于移动平均）"
                    % (w, poly, ", ".join(_fmt(v) for v in out)))
        return "❌ method 支持 ma（移动平均）/ savgol"
    if action == "interp":
        xs = [float(v) for v in (args.get("x") or [])]
        targets = [float(v) for v in (args.get("targets") or [])]
        if not xs or len(xs) != len(ys) or not targets:
            return "❌ interp 需要 x（与 y 等长）与 targets"
        pts = sorted(zip(xs, ys))
        if any(pts[i][0] == pts[i - 1][0] for i in range(1, len(pts))):
            return "❌ x 存在重复值"
        out = []
        for t in targets:
            if t < pts[0][0] or t > pts[-1][0]:
                return "❌ target %s 超出数据范围 [%s, %s]（本工具不做外推）" % (
                    _fmt(t), _fmt(pts[0][0]), _fmt(pts[-1][0]))
            j = bisect.bisect_right(pts, (t, float("inf")))
            j = min(max(j, 1), len(pts) - 1)
            x0, y0, x1, y1 = pts[j - 1][0], pts[j - 1][1], pts[j][0], pts[j][1]
            out.append(y0 if x1 == x0 else y0 + (y1 - y0) * (t - x0) / (x1 - x0))
        return "**线性插值**\n" + ", ".join("%s → %s" % (_fmt(t), _fmt(v))
                                        for t, v in zip(targets, out))
    if action == "integrate":
        xs = [float(v) for v in (args.get("x") or [])]
        method = str(args.get("method", "trapezoid")).lower()
        if len(xs) < 2 or len(xs) != len(ys):
            return "❌ integrate 需要 x、y 等长且 ≥ 2 点"
        pts = sorted(zip(xs, ys))
        px, py = [p[0] for p in pts], [p[1] for p in pts]
        if any(px[i] == px[i - 1] for i in range(1, len(px))):
            return "❌ x 存在重复值"
        if method == "trapezoid":
            area = sum((px[i + 1] - px[i]) * (py[i] + py[i + 1]) / 2 for i in range(len(px) - 1))
            return "**梯形法数值积分（%d 段）= %s**\n（曲线弯曲剧烈时加密采样或改用 simpson）" % (
                len(px) - 1, _fmt(area))
        if method == "simpson":
            if (len(px) - 1) % 2 == 1:
                return "❌ Simpson 需偶数段（奇数个点）：当前 %d 点，截掉或补 1 点" % len(px)
            h = (px[-1] - px[0]) / (len(px) - 1)
            if any(abs(px[i + 1] - px[i] - h) > 1e-9 * max(abs(h), 1.0)
                   for i in range(len(px) - 1)):
                return "❌ Simpson 需等距采样（先用 resample 均匀化）"
            area = h / 3 * (py[0] + py[-1] + 4 * sum(py[1:-1:2]) + 2 * sum(py[2:-2:2]))
            return "**Simpson 数值积分（%d 段等距）= %s**\n（二次/三次曲线可达机器精度）" % (
                len(px) - 1, _fmt(area))
        return "❌ method 支持 trapezoid（默认）/ simpson"
    if action == "resample":
        xs = [float(v) for v in (args.get("x") or [])]
        n = int(args.get("n", 100) or 100)
        if len(xs) < 2 or len(xs) != len(ys):
            return "❌ resample 需要 x、y 等长且 ≥ 2 点"
        if not (2 <= n <= 10000):
            return "❌ n 取值 2-10000"
        pts = sorted(zip(xs, ys))
        px, py = [p[0] for p in pts], [p[1] for p in pts]
        if px[0] == px[-1]:
            return "❌ x 无范围"
        step = (px[-1] - px[0]) / (n - 1)
        out = []
        for i in range(n):
            t = px[0] + i * step
            j = min(max(bisect.bisect_right(px, t), 1), len(px) - 1)
            x0, y0, x1, y1 = px[j - 1], py[j - 1], px[j], py[j]
            out.append(y0 if x1 == x0 else y0 + (y1 - y0) * (t - x0) / (x1 - x0))
        shown = ", ".join(_fmt(v) for v in out[:50]) + ("…" if n > 50 else "")
        return "**重采样 %d 点（线性插值，范围 [%s, %s]）**\n%s" % (n, _fmt(px[0]), _fmt(px[-1]), shown)
    if action == "spectrum":
        fs = float(args.get("fs") or 0)
        if fs <= 0:
            return "❌ spectrum 需要 fs（采样率，单位 Hz，正数）"
        if len(ys) < 2:
            return "❌ spectrum 至少 2 个采样点"
        n = len(ys)
        nfft = 1 << (n - 1).bit_length()  # ≥ n 的最小二次幂
        padded = nfft > n
        X = _fft(list(ys) + [0.0] * (nfft - n))
        half = nfft // 2
        # 单边幅值谱：k=1..half-1 幅值×2（正负频率对称折叠），直流与 Nyquist 不翻倍
        amp = [abs(X[0]) / nfft]
        amp += [2.0 * abs(X[k]) / nfft for k in range(1, half)]
        amp += [abs(X[half]) / nfft] if nfft > 2 else []
        df = fs / nfft
        pk = []
        for k in range(1, half):
            if amp[k] > amp[k - 1] and amp[k] > amp[k + 1]:
                pk.append(k)
        if pk:
            mx = max(amp[k] for k in pk)
            pk = sorted((k for k in pk if amp[k] >= 0.01 * mx), key=lambda k: -amp[k])[:5]
        head = "**FFT 频谱（fs = %s Hz，N = %d%s）**" % (
            _fmt(fs), n, "，已零填充至 %d 点" % nfft if padded else "")
        lines = [head,
                 "频率分辨率 Δf = fs/N = %s Hz；Nyquist = %s Hz（更高的频率分量已混叠，事后不可恢复）"
                 % (_fmt(df), _fmt(fs / 2.0)),
                 "直流分量（均值）= %s" % _fmt(sum(ys) / n)]
        if pk:
            lines.append("主峰（单边幅值谱，降序前 %d 个局部极大）：" % len(pk))
            lines += ["  %d. %s Hz    幅值 %s" % (i + 1, _fmt(k * df), _fmt(amp[k]))
                      for i, k in enumerate(pk)]
        else:
            lines.append("主峰：未检出局部极大（数据太短或接近纯直流）")
        lines.append("（整周期采样时幅值 = 该频率正弦的峰值；非整周期截断有少量泄漏，峰位仍可靠）")
        return "\n".join(lines)
    return "❌ 未知 action：%s（支持 smooth / interp / integrate / resample / spectrum）" % action

# ======================================================================
# 13. 论文级 SVG 绘图与试验曲线特征提取（零依赖，数据不出本机）
# ======================================================================
_PLOT_COLORS = ("#1a5276", "#c0392b")  # 深蓝 / 砖红（与 Mohr 圆同色系）

def _xml_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def _nice_ticks(lo, hi, target=6):
    """1-2-5 优雅刻度序列（毫米纸习惯），返回覆盖 [lo, hi] 的刻度列表。"""
    if not hi > lo:
        hi = lo + (abs(lo) or 1.0)
    raw = (hi - lo) / max(target - 1, 1)
    mag = math.floor(math.log10(raw))
    step = None
    for m in (1.0, 2.0, 5.0, 10.0):
        if m * 10.0 ** mag >= raw:
            step = m * 10.0 ** mag
            break
    if step is None:
        step = 10.0 ** (mag + 1)
    ticks, v = [], math.floor(lo / step) * step
    while v <= hi + step * 1e-9:
        if v >= lo - step * 1e-9:
            ticks.append(0.0 if abs(v) < step * 1e-9 else round(v, 12))  # 消除累加浮点噪声
        v += step
    return ticks

def _log_ticks(lo, hi):
    """对数轴刻度：10 的幂次；跨 ≤ 2 个数量级时补 2×/5× 中间刻度。"""
    d0, d1 = math.floor(math.log10(lo)), math.ceil(math.log10(hi))
    mult = (1, 2, 5) if d1 - d0 <= 2 else (1,)
    ticks = []
    for d in range(d0, d1 + 1):
        for m in mult:
            v = m * 10.0 ** d
            if lo * 0.999 <= v <= hi * 1.001:
                ticks.append(v)
    return ticks

def _tick_label(v):
    """刻度数字：常规范围 %.6g；超大/超小用 2e5 / 1e-4 紧凑形式。"""
    if v == 0:
        return "0"
    if 1e-4 <= abs(v) < 1e5:
        return "%.6g" % v
    return ("%.0e" % v).replace("e+0", "e+").replace("e-0", "e-").replace("e+", "e")

def _decimate_idx(n, cap=800):
    """大数据抽稀索引（保留首末点），SVG 体积可控且不丢端点信息。"""
    if n <= cap:
        return list(range(n))
    step = int(math.ceil(n / float(cap - 1)))
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return idx

def _plot_domain(vals, log):
    """值域（含 4% 呼吸边距）：线性在原空间、对数在 log10 空间取边距。"""
    lo, hi = min(vals), max(vals)
    if log:
        if hi <= lo:
            hi = lo * 10.0
        l0, l1 = math.log10(lo), math.log10(hi)
        pad = (l1 - l0) * 0.04 or 0.05
        return l0 - pad, l1 + pad
    if hi <= lo:
        hi = lo + (abs(lo) or 1.0)
    pad = (hi - lo) * 0.04
    return lo - pad, hi + pad

def _svg_axes_plot(series, title, xlabel, ylabel, log_x, log_y, w=600, h=420):
    """
    论文级 SVG 坐标图：白底黑字衬线、浅灰网格、坐标框、图例框。
    series: [{x, y, y_err(可None), color, mode(line|scatter|errorbar|bar), name}]
    mode=bar 时用 cats（组名列表）替代 x，画分组并列柱 + 可选误差帽。
    返回 (svg 文本, 各系列摘要行列表)。
    """
    ML, MR, MT, MB = 66, 26, 40, 58          # 左右上下边距（含刻度/轴标签空间）
    cat_mode = bool(series[0].get("cats"))   # bar：x 为类别轴
    allx = [v for s in series for v in (s.get("x") or [])]
    ally = []
    for s in series:
        if s.get("y_err"):
            ally.extend(v + e for v, e in zip(s["y"], s["y_err"]))
            ally.extend(v - e for v, e in zip(s["y"], s["y_err"]))
        else:
            ally.extend(s["y"])
    if cat_mode:                              # 柱状图：无 x 数值域，y 域强制含 0 基线（log 轴除外）
        xd0 = xd1 = 0.0
        yd0, yd1 = _plot_domain(ally + ([] if log_y else [0.0]), log_y)
    else:
        xd0, xd1 = _plot_domain(allx, log_x)
        yd0, yd1 = _plot_domain(ally, log_y)
    ngroups = len(series[0]["cats"]) if cat_mode else 0

    def PX(v):
        if cat_mode:                          # v 为组序号 → 组中心横坐标
            return ML + (v + 0.5) / ngroups * (w - ML - MR)
        u = (math.log10(v) if log_x else v) - xd0
        u = min(max(u / (xd1 - xd0), 0.0), 1.0)
        return ML + u * (w - ML - MR)

    def PY(v):
        u = (math.log10(v) if log_y else v) - yd0
        u = min(max(u / (yd1 - yd0), 0.0), 1.0)
        return h - MB - u * (h - MT - MB)

    xticks = ([] if cat_mode else
              (_log_ticks(10.0 ** xd0, 10.0 ** xd1) if log_x
               else _nice_ticks(xd0, xd1)))
    yticks = (_log_ticks(10.0 ** yd0, 10.0 ** yd1) if log_y
              else _nice_ticks(yd0, yd1))

    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
             'font-family="Georgia, \'Times New Roman\', serif">' % (w, h)]
    parts.append('<rect x="0" y="0" width="%d" height="%d" fill="#ffffff"/>' % (w, h))
    if cat_mode:                              # 类别名 + 带间浅灰分界线（不画数值刻度）
        for g in range(ngroups):
            if g:
                gx = ML + g / ngroups * (w - ML - MR)
                parts.append('<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#efefef" stroke-width="1"/>'
                             % (gx, MT, gx, h - MB))
            cname = str(series[0]["cats"][g])
            cname = cname if len(cname) <= 10 else cname[:9] + "…"
            parts.append('<text x="%.2f" y="%d" font-size="11" fill="#333" text-anchor="middle">%s</text>'
                         % (PX(g), h - MB + 17, _xml_escape(cname)))
    for tv in xticks:
        gx = PX(tv)
        parts.append('<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#e4e4e4" stroke-width="1"/>'
                     % (gx, MT, gx, h - MB))
        parts.append('<text x="%.2f" y="%d" font-size="11" fill="#333" text-anchor="middle">%s</text>'
                     % (gx, h - MB + 17, _xml_escape(_tick_label(tv))))
    for tv in yticks:
        gy = PY(tv)
        parts.append('<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#e4e4e4" stroke-width="1"/>'
                     % (ML, gy, w - MR, gy))
        parts.append('<text x="%d" y="%.2f" font-size="11" fill="#333" text-anchor="end">%s</text>'
                     % (ML - 8, gy + 4, _xml_escape(_tick_label(tv))))
    if not log_x and not cat_mode and xd0 <= 0 <= xd1:   # 零基线加深（线性轴）
        parts.append('<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#b8b8b8" stroke-width="1"/>'
                     % (PX(0.0), MT, PX(0.0), h - MB))
    if not log_y and yd0 <= 0 <= yd1:
        parts.append('<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#b8b8b8" stroke-width="1"/>'
                     % (ML, PY(0.0), w - MR, PY(0.0)))
    parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="#333" stroke-width="1.2"/>'
                 % (ML, MT, w - ML - MR, h - MT - MB))
    summary = []
    nser = len(series)
    for si, s in enumerate(series):
        col, mode = s["color"], s["mode"]
        name = s.get("name") or "系列%d" % (si + 1)
        if mode == "bar":                     # 分组并列柱 + 可选误差帽
            band = (w - ML - MR) / float(ngroups)
            bw = band * 0.56 / nser           # 柱宽：带宽的 56% 均分给各系列
            for g, v in enumerate(s["y"]):
                xx = PX(g) + (si - (nser - 1) / 2.0) * (bw + band * 0.04)
                y0 = h - MB if log_y else PY(0.0)   # log 轴无 0 基线：柱底落在绘图区底边
                y1 = PY(v)
                parts.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="%s"/>'
                             % (xx - bw / 2, min(y0, y1), bw, abs(y1 - y0), col))
                if s.get("y_err"):
                    ee = s["y_err"][g]
                    yt, yb = PY(v + ee), PY(v - ee)
                    parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.1"/>'
                                 % (xx, yt, xx, yb, col))
                    for yg in (yt, yb):
                        parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.1"/>'
                                     % (xx - 4, yg, xx + 4, yg, col))
            summary.append("%s：%d 组" % (name, len(s["y"])))
            continue
        idx = _decimate_idx(len(s["x"]))
        pts = [(s["x"][i], s["y"][i]) for i in idx]
        if s.get("y_err"):                   # 误差棒：竖线 + 端帽
            for i in idx:
                xx, yy, ee = s["x"][i], s["y"][i], s["y_err"][i]
                yt, yb = PY(yy + ee), PY(yy - ee)
                parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.1"/>'
                             % (PX(xx), yt, PX(xx), yb, col))
                for yg in (yt, yb):
                    parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="1.1"/>'
                                 % (PX(xx) - 4, yg, PX(xx) + 4, yg, col))
        if mode == "scatter":
            for xx, yy in pts:
                parts.append('<circle cx="%.2f" cy="%.2f" r="2.6" fill="%s"/>' % (PX(xx), PY(yy), col))
        else:                                # line / errorbar 都连线
            pstr = " ".join("%.2f,%.2f" % (PX(xx), PY(yy)) for xx, yy in pts)
            parts.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="1.6"/>'
                         % (pstr, col))
        summary.append("%s：%d 点%s" % (name, len(s["x"]),
                     "（抽稀至 %d 点绘制）" % len(idx) if len(idx) < len(s["x"]) else ""))
    shown = [s for s in series if s.get("name")]
    if shown:
        lw = int(max(len(_xml_escape(s["name"])) for s in shown) * 7.3 + 44)
        lh = 10 + 20 * len(shown)
        bx, by = ML + 14, MT + 12
        parts.append('<rect x="%d" y="%d" width="%d" height="%d" fill="#ffffff" '
                     'fill-opacity="0.92" stroke="#999" stroke-width="1"/>' % (bx, by, lw, lh))
        for k, s in enumerate(shown):
            yy = by + 14 + 20 * k
            if s["mode"] == "scatter":
                parts.append('<circle cx="%d" cy="%d" r="3.2" fill="%s"/>' % (bx + 16, yy - 4, s["color"]))
            elif s["mode"] == "bar":
                parts.append('<rect x="%d" y="%d" width="16" height="10" fill="%s"/>' % (bx + 8, yy - 9, s["color"]))
            else:
                parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="1.8"/>'
                            % (bx + 8, yy - 4, bx + 24, yy - 4, s["color"]))
            parts.append('<text x="%d" y="%d" font-size="11.5" fill="#222">%s</text>'
                         % (bx + 30, yy, _xml_escape(s["name"])))
    if title:
        parts.append('<text x="%d" y="24" font-size="15" fill="#111" text-anchor="middle" '
                     'font-weight="bold">%s</text>' % (w // 2, _xml_escape(title)))
    if xlabel:
        parts.append('<text x="%d" y="%d" font-size="13" fill="#111" text-anchor="middle">%s</text>'
                     % ((ML + w - MR) // 2, h - 20, _xml_escape(xlabel)))
    if ylabel:
        cy = (MT + h - MB) // 2
        parts.append('<text x="18" y="%d" font-size="13" fill="#111" text-anchor="middle" '
                     'transform="rotate(-90 18 %d)">%s</text>' % (cy, cy, _xml_escape(ylabel)))
    parts.append("</svg>")
    return "".join(parts), summary

def tool_plot(args):
    action = str(args.get("action", "line")).lower()
    if action == "bar":
        return _plot_bar(args)
    if action not in ("line", "scatter", "errorbar"):
        return "❌ action 支持 line（默认折线）/ scatter（散点）/ errorbar（折线+误差棒）/ bar（分组柱状）"
    x1 = [float(v) for v in (args.get("x") or [])]
    y1 = [float(v) for v in (args.get("y") or [])]
    if not x1 or len(x1) != len(y1):
        return "❌ x/y 需等长且非空"
    if len(x1) < 2:
        return "❌ 至少 2 个点"
    x2 = [float(v) for v in (args.get("x2") or [])]
    y2 = [float(v) for v in (args.get("y2") or [])]
    has2 = bool(x2 or y2)
    if has2 and (not x2 or len(x2) != len(y2) or len(x2) < 2):
        return "❌ x2/y2 需成对给出、等长且 ≥ 2 点"
    yerr = [float(v) for v in (args.get("y_err") or [])]
    if action == "errorbar" and not yerr:
        return "❌ errorbar 需要 y_err（与 y 等长的 ± 误差幅值数组）"
    if yerr and len(yerr) != len(y1):
        return "❌ y_err 长度 %d ≠ y 长度 %d" % (len(yerr), len(y1))
    if yerr and any(e < 0 for e in yerr):
        return "❌ y_err 需为非负（± 幅值）"
    log_x, log_y = bool(args.get("log_x")), bool(args.get("log_y"))
    if log_x and min(x1 + x2) <= 0:
        return "❌ log_x 要求所有 x > 0（当前最小值 %s）" % _fmt(min(x1 + x2))
    if log_y:
        yv = list(y1) + list(y2)
        if yerr:
            yv += [v - e for v, e in zip(y1, yerr)]
        if yv and min(yv) <= 0:
            return "❌ log_y 要求所有 y（含误差下界）> 0"
    labels = [str(v) for v in (args.get("labels") or [])]
    name1 = labels[0] if labels and labels[0] else ("系列1" if has2 else "")
    name2 = labels[1] if len(labels) > 1 and labels[1] else "系列2"
    series = [{"x": x1, "y": y1, "y_err": yerr or None,
               "color": _PLOT_COLORS[0], "mode": action, "name": name1}]
    if has2:
        series.append({"x": x2, "y": y2, "y_err": None,
                        "color": _PLOT_COLORS[1], "mode": action, "name": name2})
    return _plot_render(series, args, action,
                        args.get("xlabel") or "（未命名）",
                        args.get("ylabel") or "（未命名）", log_x, log_y)


def _plot_render(series, args, action, x_desc, y_desc, log_x, log_y):
    """出图公共尾部：SVG 引擎调用 + 摘要 + 存图 + 代码块（四种 action 共用）。"""
    svg, sums = _svg_axes_plot(series, args.get("title") or "",
                               args.get("xlabel") or "", args.get("ylabel") or "",
                               log_x, log_y)
    lines = ["**论文级 SVG 绘图（零依赖，600×420 单栏尺寸）**"]
    lines.append("- 类型：%s｜%s" % (action, " + ".join(sums)))
    lines.append("- X 轴：%s（%s）｜Y 轴：%s（%s）"
                 % (x_desc, "对数" if log_x else "线性", y_desc, "对数" if log_y else "线性"))
    save = args.get("save_path")
    if save:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(save)), exist_ok=True)
            with open(save, "w", encoding="utf-8") as f:
                f.write(svg)
            lines.append("- 已保存：%s" % save)
        except Exception as exc:  # noqa: BLE001 —— 保存失败不吞错
            lines.append("⚠ 保存失败：%s" % exc)
    else:
        lines.append("- 如需存图：加参数 save_path=<路径.svg>")
    lines.append("\n```svg\n%s\n```\n" % svg)
    lines.append("用法：把代码块另存为 .svg 文件——浏览器/Word/浏览器插件可直接打开，"
                 "LaTeX 用 svg 宏包 \\includesvg 排版；也可交给 AI 继续改样式。")
    return "\n".join(lines)


def _plot_bar(args):
    """action=bar：分组柱状图——各配合比/处理组对比（双系列并列 + 可选误差帽）。"""
    cats = [str(c) for c in (args.get("x") or [])]
    y1 = [float(v) for v in (args.get("y") or [])]
    if not cats or len(cats) != len(y1):
        return "❌ bar 的 x 为组名列表（字符串），需与 y 等长且非空"
    x2 = [str(c) for c in (args.get("x2") or [])]
    y2 = [float(v) for v in (args.get("y2") or [])]
    has2 = bool(x2 or y2)
    if has2 and (not x2 or len(x2) != len(y2) or len(x2) != len(cats)):
        return "❌ bar 双系列：x2/y2 需成对给出且与第一组同为 %d 组" % len(cats)
    yerr = [float(v) for v in (args.get("y_err") or [])]
    if yerr and len(yerr) != len(y1):
        return "❌ y_err 长度 %d ≠ y 长度 %d" % (len(yerr), len(y1))
    if yerr and any(e < 0 for e in yerr):
        return "❌ y_err 需为非负（± 幅值）"
    log_y = bool(args.get("log_y"))
    if log_y:
        yv = list(y1) + list(y2)
        if yerr:
            yv += [v - e for v, e in zip(y1, yerr)]
        if min(yv) <= 0:
            return "❌ log_y 要求所有 y（含误差下界）> 0"
    labels = [str(v) for v in (args.get("labels") or [])]
    name1 = labels[0] if labels and labels[0] else ("系列1" if has2 else "")
    name2 = labels[1] if len(labels) > 1 and labels[1] else "系列2"
    series = [{"cats": cats, "y": y1, "y_err": yerr or None,
               "color": _PLOT_COLORS[0], "mode": "bar", "name": name1}]
    if has2:
        series.append({"cats": x2, "y": y2, "y_err": None,
                       "color": _PLOT_COLORS[1], "mode": "bar", "name": name2})
    return _plot_render(series, args, "bar",
                        args.get("xlabel") or "类别（%d 组）" % len(cats),
                        args.get("ylabel") or "（未命名）", False, log_y)

def _curve_features(px, py, frac, off):
    """单条曲线特征提取（px/py 已升序排序），单条与批量共用。
    返回 (特征 dict, None) 或 (None, 错误信息)。"""
    n = len(px)
    if n < 4:
        return None, "至少 4 个点（弹性段回归 + 偏移交点插值都需要余量）"
    if any(px[i] == px[i - 1] for i in range(1, n)):
        return None, "x 存在重复值"
    # ── 弹性段：x ≤ xmin + frac·Δx，不足 3 点回退前 3 点 ──
    xcut = px[0] + frac * (px[-1] - px[0])
    seg = [i for i in range(n) if px[i] <= xcut]
    if len(seg) < 3:
        seg = list(range(3))
    ex, ey = [px[i] for i in seg], [py[i] for i in seg]
    coef = _polyfit(ex, ey, 1)
    if coef is None:
        return None, "弹性段拟合退化（x 无变化），请检查数据"
    b0, a1 = coef[0], coef[1]
    ybar = sum(ey) / len(ey)
    ss_res = sum((v - (b0 + a1 * u)) ** 2 for u, v in zip(ex, ey))
    ss_tot = sum((v - ybar) ** 2 for v in ey)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-30 else 1.0
    feat = {"nseg": len(seg), "xcut": ex[-1], "e": a1, "b": b0, "r2": r2,
            "yield": None, "peak_y": 0.0, "peak_x": 0.0,
            "end": (px[-1], py[-1]), "energy": 0.0, "method": ""}
    # ── 偏移法屈服：y = E(x−off)+b 与曲线首个交点（线性插值）──
    if off > 0 and a1 > 0:
        d = [py[i] - (b0 + a1 * (px[i] - off)) for i in range(n)]
        for i in range(1, n):
            if d[i - 1] > 0 and d[i] <= 0:
                t = d[i - 1] / (d[i - 1] - d[i])
                feat["yield"] = (px[i - 1] + t * (px[i] - px[i - 1]),
                                 py[i - 1] + t * (py[i] - py[i - 1]))
                break
    # ── 峰值 / 能量 ──
    ymax = max(py)
    feat["peak_y"], feat["peak_x"] = ymax, px[py.index(ymax)]
    segs = n - 1
    energy, method = None, ""
    if segs % 2 == 0:
        hh = (px[-1] - px[0]) / segs
        if all(abs(px[i + 1] - px[i] - hh) <= 1e-9 * max(abs(hh), 1.0) for i in range(segs)):
            energy = hh / 3 * (py[0] + py[-1] + 4 * sum(py[1:-1:2]) + 2 * sum(py[2:-2:2]))
            method = "Simpson，%d 段等距" % segs
    if energy is None:
        energy = sum((px[i + 1] - px[i]) * (py[i] + py[i + 1]) / 2 for i in range(segs))
        method = "梯形法，%d 段（间距不等，Simpson 不适用）" % segs
    feat["energy"], feat["method"] = energy, method
    return feat, None

def _curve_ms(vals):
    """均值 ± 样本标准差（n=1 时 std=0），批量汇总用。
    相对 1e-12 以下的标准差视为浮点求和噪声归零（如 sum([0.4]*3)≠1.2 产生的 6.8e-17 伪精度）。"""
    m = sum(vals) / len(vals)
    if len(vals) == 1:
        return m, 0.0
    sd = math.sqrt(sum((v - m) ** 2 for v in vals) / (len(vals) - 1))
    if abs(sd) <= 1e-12 * max(abs(m), 1e-30):
        sd = 0.0
    return m, sd

def _curve_batch(args, frac, off):
    curves = args.get("curves") or []
    if not isinstance(curves, list) or not curves:
        return '❌ batch 需要 curves：[{"name": "A-01", "x": [...], "y": [...]}, ...]（≥1 条）'
    lines = ["**平行试样批量特征（%d 条曲线，initial_frac=%s，偏移 %.2f%%）**"
             % (len(curves), _fmt(frac), off * 100)]
    rows, bad = [], []
    for i, c in enumerate(curves):
        if not isinstance(c, dict):
            bad.append("第 %d 条不是对象" % (i + 1))
            continue
        name = str(c.get("name") or "曲线%d" % (i + 1))
        try:
            xs = [float(v) for v in (c.get("x") or [])]
            ys = [float(v) for v in (c.get("y") or [])]
        except (TypeError, ValueError):
            bad.append("%s：x/y 含非数值" % name)
            continue
        if len(xs) != len(ys):
            bad.append("%s：x/y 不等长（%d / %d）" % (name, len(xs), len(ys)))
            continue
        pts = sorted(zip(xs, ys))
        feat, err = _curve_features([p[0] for p in pts], [p[1] for p in pts], frac, off)
        if feat is None:
            bad.append("%s：%s" % (name, err))
            continue
        rows.append((name, feat))
        ytxt = _fmt(feat["yield"][1]) if feat["yield"] else "—"
        lines.append("- **%s**（%d 点）：E = %s｜屈服 = %s｜峰值 = %s｜总能量 = %s"
                     % (name, len(pts), _fmt(feat["e"]), ytxt,
                        _fmt(feat["peak_y"]), _fmt(feat["energy"])))
    if not rows:
        return "❌ 没有任何曲线提取成功：" + "；".join(bad)
    lines.append("\n**汇总（均值 ± 标准差，n=%d）**" % len(rows))
    m, sd = _curve_ms([f["e"] for _, f in rows])
    lines.append("- **弹性模量 E = %s ± %s**" % (_fmt(m), _fmt(sd)))
    yv = [f["yield"][1] for _, f in rows if f["yield"]]
    if yv:
        m, sd = _curve_ms(yv)
        lines.append("- **屈服强度 = %s ± %s**（%d/%d 条找到交点）"
                     % (_fmt(m), _fmt(sd), len(yv), len(rows)))
    else:
        lines.append("- 屈服强度：均未找到偏移交点（脆性/数据未覆盖屈服段）")
    m, sd = _curve_ms([f["peak_y"] for _, f in rows])
    lines.append("- **峰值强度 = %s ± %s**" % (_fmt(m), _fmt(sd)))
    m, sd = _curve_ms([f["energy"] for _, f in rows])
    lines.append("- **总能量 = %s ± %s**" % (_fmt(m), _fmt(sd)))
    if bad:
        lines.append("\n⚠ %d 条已跳过：%s" % (len(bad), "；".join(bad)))
    return "\n".join(lines)

def tool_curve(args):
    action = str(args.get("action", "features")).lower()
    if action not in ("features", "batch"):
        return "❌ action 当前支持 features（单条曲线）/ batch（平行试样批量）"
    frac = args.get("initial_frac", 0.2)
    frac = 0.2 if frac is None else float(frac)
    if not 0.0 < frac <= 1.0:
        return "❌ initial_frac 需在 (0, 1]（默认 0.2：取曲线前 20% 的 x 范围做弹性段）"
    off = args.get("yield_offset", 0.002)
    off = 0.002 if off is None else float(off)
    if off < 0:
        return "❌ yield_offset 需为非负（默认 0.002 即 0.2% 偏移）"
    if action == "batch":
        return _curve_batch(args, frac, off)
    xs = [float(v) for v in (args.get("x") or [])]
    ys = [float(v) for v in (args.get("y") or [])]
    if len(xs) != len(ys):
        return "❌ x/y 需等长（当前 %d / %d）" % (len(xs), len(ys))
    pts = sorted(zip(xs, ys))
    px, py = [p[0] for p in pts], [p[1] for p in pts]
    feat, err = _curve_features(px, py, frac, off)
    if feat is None:
        return "❌ " + err
    lines = ["**试验曲线特征（%d 点，x ∈ [%s, %s]）**" % (len(px), _fmt(px[0]), _fmt(px[-1]))]
    lines.append("- 弹性段：前 %d 点（x ≤ %s，initial_frac=%s）"
                 % (feat["nseg"], _fmt(feat["xcut"]), _fmt(frac)))
    sign = "+" if feat["b"] >= 0 else "-"
    lines.append("- 线性回归：y = %s·x %s %s，R² = %s"
                 % (_fmt(feat["e"]), sign, _fmt(abs(feat["b"])), "%.4g" % feat["r2"]))
    lines.append("- **弹性模量 E = %s**（弹性段斜率）" % _fmt(feat["e"]))
    if feat["e"] <= 0:
        lines.append("  ⚠ 斜率非正：弹性段窗口可能混入非弹性数据，请调小 initial_frac 后重试")
    if feat["yield"]:
        lines.append("- **屈服强度 = %s**（%.2f%% 偏移，对应 x = %s）"
                     % (_fmt(feat["yield"][1]), off * 100, _fmt(feat["yield"][0])))
    elif off > 0 and feat["e"] > 0:
        lines.append("- 偏移交点：未找到（曲线未明显屈服或数据未覆盖屈服段）")
    else:
        lines.append("- 偏移交点：跳过（偏移量为 0 或斜率非正）")
    lines.append("- **峰值强度 = %s**（x = %s）"
                 % (_fmt(feat["peak_y"]), _fmt(feat["peak_x"])))
    lines.append("- 末点（断裂/卸载）：x = %s，y = %s"
                 % (_fmt(feat["end"][0]), _fmt(feat["end"][1])))
    lines.append("- **总能量（曲线下面积）= %s**（%s）" % (_fmt(feat["energy"]), feat["method"]))
    lines.append("\n（屈服判定假设曲线有清晰上升段；R² 偏低时可调小 initial_frac 纯化弹性段，"
                 "改 yield_offset 可适配 0.1%/0.05% 偏移标准）")
    return "\n".join(lines)

# ======================================================================
# MCP 协议层（newline-delimited JSON-RPC 2.0）
# ======================================================================
TOOLS = [
    {"name": "labmate_convert",
     "description": "力学单位换算：力(kN/kgf/lbf…)、应力(MPa/psi/kgf·mm²…)、长度、能量、功率。带换算链展示。",
     "inputSchema": {"type": "object", "properties": {
         "value": {"type": "number"}, "from": {"type": "string"}, "to": {"type": "string"}},
         "required": ["value", "from", "to"]}},
    {"name": "labmate_handcalc",
     "description": "三段式计算排版（公式→代入→结果）。输入符号与算术表达式，输出可逐步校核的计算过程，fmt=latex 可输出 Overleaf 版。适合应力/载荷/安全系数校核。",
     "inputSchema": {"type": "object", "properties": {
         "vars": {"type": "object", "description": "已知量 {符号: 数值}"},
         "steps": {"type": "array", "description": "[{symbol, formula, note?, unit?}]"},
         "fmt": {"type": "string", "description": "md（默认）| latex（输出 align* 环境，可贴 Overleaf）"}},
     "required": ["steps"]}},
    {"name": "labmate_mohr",
     "description": "Mohr 圈计算与 SVG 绘图：输入主应力对，计算圆心/半径/τmax；给 c、φ 时画包络并初判破坏状态。可保存 SVG。",
     "inputSchema": {"type": "object", "properties": {
         "stress_pairs": {"type": "array", "description": "[[σ1, σ3], ...] MPa"},
         "c": {"type": "number", "description": "粘聚力 MPa（可选）"},
         "phi_deg": {"type": "number", "description": "摩擦角°（可选）"},
         "save_svg": {"type": "string", "description": "SVG 保存路径（可选）"}},
     "required": ["stress_pairs"]}},
    {"name": "labmate_fit_lite",
     "description": "快速最小二乘拟合：linear/poly（degree）、power、exp，返回表达式与 R²。物理约束拟合请用 lmfit。",
     "inputSchema": {"type": "object", "properties": {
         "x": {"type": "array"}, "y": {"type": "array"},
         "model": {"type": "string", "description": "linear|power|exp"},
         "degree": {"type": "integer"}},
     "required": ["x", "y"]}},
    {"name": "labmate_deps",
     "description": "科学栈体检：探测 numpy/scipy/lmfit/sympy/matplotlib 等是否可用，给出缺失项与安装命令。",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "labmate_table",
     "description": "本机试验数据体检：读取 CSV / Excel(.xlsx) 文件或内联数据，自动探测分隔符，输出每列统计摘要（数值列均值/标准差/极值/缺失，文本列唯一值）。xlsx 零依赖解析（多工作表/日期/稀疏空位）。只读不写，数据不出本机。",
     "inputSchema": {"type": "object", "properties": {
         "csv_path": {"type": "string", "description": "本机 CSV 文件路径（推荐，支持 utf-8/GBK-BOM）"},
         "xlsx_path": {"type": "string", "description": "本机 Excel(.xlsx) 文件路径（零依赖解析；老式 .xls 请先另存为 .xlsx）"},
         "sheet": {"type": "string", "description": "xlsx 工作表：名称或 1-based 序号，默认第 1 个"},
         "data": {"type": "string", "description": "内联 CSV 文本（无文件时）"},
         "delimiter": {"type": "string", "description": "分隔符（默认自动探测）"}},
     }},
    {"name": "labmate_style",
     "description": "期刊绘图样式注入（SciencePlots 逆向）：ieee/nature/science/cnjournal 四种样式参数，可写 .mplstyle 文件，配合 matplotlib 出论文级图表。",
     "inputSchema": {"type": "object", "properties": {
         "style": {"type": "string", "description": "ieee|nature|science|cnjournal"},
         "save_mplstyle": {"type": "string", "description": ".mplstyle 文件保存路径（可选）"}},
     }},
    {"name": "labmate_arxiv",
     "description": "arXiv 文献检索（官方免费 API，无需 key）：返回标题/作者/日期/摘要/链接的真实元数据。适合科研文献侦察。",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "检索词（英文效果更好）"},
         "max_results": {"type": "integer", "description": "1-20，默认 5"}},
     "required": ["query"]}},
    {"name": "labmate_cite",
     "description": "DOI → 真实元数据 + 规范 BibTeX（Crossref 官方库）。从真实 DOI 生成的引用杜绝幻觉文献。",
     "inputSchema": {"type": "object", "properties": {
         "doi": {"type": "string", "description": "如 10.1016/j.ijrockmas.2019.104123"}},
     "required": ["doi"]}},
    {"name": "labmate_search",
     "description": "多源文献聚合检索：arXiv + Crossref + OpenAlex 并发查询并跨源去重，统一输出标题/作者/年份/出处/DOI/摘要。单源失败自动降级并给诊断；支持年份过滤。文献侦察首选。",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string", "description": "检索词（英文效果更好）"},
         "sources": {"type": "array", "description": "子集，如 [\"arxiv\",\"crossref\"]；默认三源"},
         "max_results": {"type": "integer", "description": "每源 1-15，默认 5"},
         "year_from": {"type": "integer"}, "year_to": {"type": "integer"},
         "mailto": {"type": "string", "description": "你的邮箱（Crossref/OpenAlex polite pool，可选）"},
         "openalex_key": {"type": "string", "description": "OpenAlex 免费 api_key（2026 新版接口可能需要）"}},
     "required": ["query"]}},
    {"name": "labmate_pdf",
     "description": "本地 PDF 零依赖文本处理（只读、数据不出本机）：stats 体检（页数/文本量/扫描版诊断）、extract 按页提取文本、search 关键词页码溯源（接地问答素材）。英文论文可靠，CID 中文 PDF 属已知边界。",
     "inputSchema": {"type": "object", "properties": {
         "pdf_path": {"type": "string", "description": "本机 PDF 路径"},
         "action": {"type": "string", "description": "stats（默认）| extract | search"},
         "page_from": {"type": "integer"}, "page_to": {"type": "integer"},
         "max_chars": {"type": "integer", "description": "extract 单次字符上限，默认 6000"},
         "query": {"type": "string", "description": "search 的关键词或正则"},
         "regex": {"type": "boolean"}, "ignore_case": {"type": "boolean", "description": "默认 true"},
         "context": {"type": "integer", "description": "命中上下文半径字符数，默认 80"},
         "max_mb": {"type": "number", "description": "文件大小上限 MB，默认 50"}},
     "required": ["pdf_path"]}},
    {"name": "labmate_stats",
     "description": "统计分析（零依赖精确 p 值）：describe 描述统计 / ttest 单样本·两样本（默认 Welch）·配对 t 检验（附 Cohen's d）/ anova 单因素方差分析（η²+事后比较校正提示）/ normality Jarque-Bera 正态性 / ci 均值 t 置信区间 / power 样本量估算 / outlier 异常值检验（GB/T 4883 格拉布斯 t 精确临界 + 狄克松查表，歧离值/统计离群值两级判定，迭代剔除）/ weibull 强度分析（中位秩线性回归：模数 m、特征强度 σ₀、B10、给定应力破坏概率）。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "describe|ttest|anova|normality|ci|power|outlier|weibull"},
         "data": {"type": "array", "description": "describe/normality/ci/outlier/weibull 的样本数组"},
         "a": {"type": "array", "description": "ttest 第一组"},
         "b": {"type": "array", "description": "ttest 第二组；不给则对 a 做 mu 单样本检验"},
         "mu": {"type": "number", "description": "单样本假设均值，默认 0"},
         "paired": {"type": "boolean", "description": "配对设计（a、b 等长）"},
         "equal_var": {"type": "boolean", "description": "两样本方差齐性假设（默认 false= Welch）"},
         "groups": {"type": "array", "description": "anova：≥2 组数值数组"},
         "alpha": {"type": "number", "description": "显著性水平，默认 0.05（outlier 中作歧离值检出水平）"},
         "confidence": {"type": "number", "description": "ci 置信水平，默认 0.95"},
         "delta": {"type": "number", "description": "power：要检出的均值差"},
         "sd": {"type": "number", "description": "power：合并标准差"},
         "power": {"type": "number", "description": "power：目标功效，默认 0.8"},
         "criterion": {"type": "string", "description": "outlier：grubbs（默认，n 不限）| dixon（n ≤ 30）"},
         "stress": {"type": "number", "description": "weibull：给定应力，返回破坏概率与存活率"}},
     "required": ["action"]}},
    {"name": "labmate_errors",
     "description": "不确定度分析（GUM）：propagate 一阶合成不确定度（公式+各分量贡献+k=2 扩展）/ regress OLS 斜率截距 95% 置信区间。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "propagate（默认）| regress"},
         "formula": {"type": "string", "description": "propagate：y=f(x1,x2,..) 算术表达式"},
         "vars": {"type": "object", "description": "propagate：{符号: 数值}"},
         "uncertainties": {"type": "object", "description": "propagate：{符号: u(符号)}"},
         "x": {"type": "array", "description": "regress 自变量"},
         "y": {"type": "array", "description": "regress 因变量"}},
     "required": ["action"]}},
    {"name": "labmate_doe",
     "description": "实验设计（零依赖）：ortho 素数域生成正交表（L4/L8/L16/L32/L9/L27/L25，正交性有数学保证）/ fullfact 全因子组合 / lhs 拉丁超立方抽样（每维分层、改 seed 换方案）。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "ortho（默认）| fullfact | lhs"},
         "runs": {"type": "string", "description": "ortho：L8 这类标准表名"},
         "p": {"type": "integer", "description": "ortho：素数水平 2/3/5/7"},
         "factors": {"type": "integer", "description": "ortho：基本列数（p^factors=运行数）"},
         "max_factors": {"type": "integer", "description": "ortho：输出列数上限"},
         "levels": {"type": "array", "description": "fullfact：各因素水平数如 [2,2,3]"},
         "samples": {"type": "integer", "description": "lhs：样本数，默认 20"},
         "dims": {"type": "integer", "description": "lhs：维度，默认 3"},
         "seed": {"type": "integer", "description": "lhs：随机种子，默认 42"}},
     "required": ["action"]}},
    {"name": "labmate_tex",
     "description": "LaTeX 写作生成：table booktabs 三线表（支持 csv_path 直读，数值列自动右对齐，>40 行截断提示）/ figure 图环境（多图自动 subfigure）/ equation 带编号公式（\\eqref 引用）。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "table（默认）| figure | equation"},
         "headers": {"type": "array", "description": "table 表头"},
         "rows": {"type": "array", "description": "table 数据行"},
         "csv_path": {"type": "string", "description": "table：直读本机 CSV（首行表头）"},
         "align": {"type": "string", "description": "table：列对齐如 lccr（默认数值右对齐）"},
         "caption": {"type": "string"}, "label": {"type": "string"},
         "files": {"type": "array", "description": "figure：图片路径数组，或 [{path, caption}] 子图"},
         "width": {"type": "string", "description": "figure：默认 0.9\\columnwidth"},
         "subwidth": {"type": "string", "description": "figure：子图宽，默认 0.48\\textwidth"},
         "latex": {"type": "string", "description": "equation：公式体（不含 begin/end）"}},
     "required": ["action"]}},
    {"name": "labmate_bibtex",
     "description": "BibTeX 库工作台：check 元数据体检（必填字段/重复 key/DOI/标题）/ merge 跨库去重合并（DOI 优先、标题兜底）/ sort 按作者-年份排序规范化输出。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "check（默认）| merge | sort"},
         "bib_path": {"type": "string", "description": "单个 .bib 文件路径"},
         "bib_paths": {"type": "array", "description": "多个 .bib 文件（merge 跨库合并）"}},
     "required": ["action"]}},
    {"name": "labmate_signal",
     "description": "试验曲线信号处理（零依赖）：smooth 移动平均 / Savitzky-Golay 保峰形平滑、interp 线性插值（不外推）、integrate 梯形 / Simpson 数值积分、resample 均匀重采样、spectrum FFT 频谱（radix-2，非二次幂自动零填充并明示；单边幅值谱 + Δf/Nyquist/主峰）。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "smooth（默认）| interp | integrate | resample | spectrum"},
         "y": {"type": "array", "description": "因变量数组"},
         "x": {"type": "array", "description": "自变量（smooth 可省略视为等间距）"},
         "window": {"type": "integer", "description": "smooth：窗口（奇数），默认 5"},
         "method": {"type": "string", "description": "smooth：ma|savgol；integrate：trapezoid（默认）|simpson"},
         "poly": {"type": "integer", "description": "savgol：多项式阶数，默认 2"},
         "targets": {"type": "array", "description": "interp：目标 x 值"},
         "n": {"type": "integer", "description": "resample：目标点数，默认 100"},
         "fs": {"type": "number", "description": "spectrum：采样率（Hz，正数）"}},
     "required": ["y"]}},
    {"name": "labmate_plot",
     "description": "论文级 SVG 绘图（零依赖，数据不出本机）：折线/散点/误差棒/分组柱状，双组数据对比、对数轴、图例、1-2-5 优雅刻度，可直接存 .svg 嵌入论文。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "line（默认折线）| scatter（散点）| errorbar（折线+误差棒）| bar（分组柱状，x 为组名）"},
         "x": {"type": "array", "description": "第一组 x 数组；bar 时为组名字符串数组"},
         "y": {"type": "array", "description": "第一组 y 数组"},
         "x2": {"type": "array", "description": "第二组 x（对比曲线，可选）"},
         "y2": {"type": "array", "description": "第二组 y（可选）"},
         "y_err": {"type": "array", "description": "errorbar：± 误差幅值（与 y 等长）"},
         "labels": {"type": "array", "description": "图例文字，如 [\"试验\", \"拟合\"]"},
         "title": {"type": "string", "description": "图标题"},
         "xlabel": {"type": "string", "description": "x 轴标签"},
         "ylabel": {"type": "string", "description": "y 轴标签"},
         "log_x": {"type": "boolean", "description": "X 对数轴（要求所有 x > 0）"},
         "log_y": {"type": "boolean", "description": "Y 对数轴（要求所有 y 及误差下界 > 0）"},
         "save_path": {"type": "string", "description": "SVG 保存路径（可选）"}},
     "required": ["x", "y"]}},
    {"name": "labmate_curve",
     "description": "试验曲线特征提取（零依赖）：弹性模量 E（初始段线性回归+R²）、0.2% 偏移屈服强度（平移线与曲线交点线性插值）、峰值强度及位置、断裂末点、总能量（Simpson/梯形自动选择）。features 单条 / batch 平行试样批量（逐条提取+均值±标准差汇总，GB/T 类报告标准动作）。适配拉伸/压缩/直剪等 x 递增曲线。",
     "inputSchema": {"type": "object", "properties": {
         "action": {"type": "string", "description": "features（默认，单条）| batch（平行试样批量）"},
         "x": {"type": "array", "description": "自变量：应变/位移/加载点变形（features）"},
         "y": {"type": "array", "description": "因变量：应力/荷载（features）"},
         "curves": {"type": "array", "description": "batch：[{name, x, y}, ...] 平行试样曲线数组"},
         "initial_frac": {"type": "number", "description": "弹性段窗口（曲线前段 x 范围占比），默认 0.2"},
         "yield_offset": {"type": "number", "description": "屈服偏移量，默认 0.002（0.2%）"}},
     "required": ["x", "y"]}},
]

_DISPATCH = {
    "labmate_convert": tool_convert,
    "labmate_handcalc": tool_handcalc,
    "labmate_mohr": tool_mohr,
    "labmate_fit_lite": tool_fit,
    "labmate_deps": tool_deps,
    "labmate_table": tool_table,
    "labmate_style": tool_style,
    "labmate_arxiv": tool_arxiv,
    "labmate_cite": tool_cite,
    "labmate_search": tool_search,
    "labmate_pdf": tool_pdf,
    "labmate_stats": tool_stats,
    "labmate_errors": tool_errors,
    "labmate_doe": tool_doe,
    "labmate_tex": tool_tex,
    "labmate_bibtex": tool_bibtex,
    "labmate_signal": tool_signal,
    "labmate_plot": tool_plot,
    "labmate_curve": tool_curve,
}

def handle(msg):
    mid, method, params = msg.get("id"), msg.get("method"), msg.get("params") or {}
    if method == "initialize":
        return send(mid, {"protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "labmate", "version": SERVER_VERSION}})
    if method in ("notifications/initialized", "initialized"):
        return
    if method == "ping":
        return send(mid, {})
    if method == "tools/list":
        return send(mid, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        fn = _DISPATCH.get(name)
        if fn is None:
            return send(mid, {"content": [{"type": "text", "text": "❌ 未知工具：%s" % name}], "isError": True})
        try:
            text = fn(params.get("arguments") or {})
            return send(mid, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:  # noqa: BLE001 —— 工具层异常统一回传
            return send(mid, {"content": [{"type": "text", "text": "❌ %s: %s" % (type(exc).__name__, exc)}],
                              "isError": True})
    if mid is not None:
        return send(mid, {"error": {"code": -32601, "message": "未知方法: %s" % method}})

def send(mid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}, ensure_ascii=False) + "\n")
    sys.stdout.flush()

def main():
    if sys.stdin.encoding and sys.stdin.encoding.lower().replace("-", "") != "utf8":
        try:
            sys.stdin.reconfigure(encoding="utf-8")  # Windows GBK 控制台保护
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    buf = ""
    for chunk in sys.stdin:
        buf += chunk
        while "\n" in buf:
            line, buf = buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                handle(json.loads(line))
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write("[labmate] 消息处理异常: %s\n" % exc)
    sys.stderr.write("[labmate] stdin closed, exit.\n")

if __name__ == "__main__":
    main()

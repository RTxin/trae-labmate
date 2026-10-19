#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LabMate MCP Server —— 科研搭子计算引擎

LabMate 插件的"手"：skills 层负责科研引导（脑），本 server 提供确定性计算工具，
让 AI 从"现场手写脚本"变成"调用真实工具"。

零第三方依赖（Python 3.8+），stdio newline-delimited JSON-RPC 2.0。

工具（0.3.0 · 十一件套）：
  计算组（零依赖，离线可用）：
  labmate_convert   力学单位换算（内置换算表）
  labmate_handcalc  三段式计算排版：公式 → 代入 → 结果（AST 白名单安全求值，支持 LaTeX 输出）
  labmate_mohr      Mohr 圆计算 + 纯 Python SVG 绘图
  labmate_fit_lite  内置最小二乘拟合（线性/二次/指数/幂律）+ R²
  labmate_table    本机试验数据体检：CSV 读取 + 列统计摘要（csv 模块，零依赖）
  labmate_style    期刊绘图样式注入：ieee/nature/science/中文期刊（SciencePlots 逆向）
  labmate_deps     科学栈体检（探测 numpy/scipy/lmfit/sympy/matplotlib/pyvista）
  文献组（标准库 urllib，需联网）：
  labmate_arxiv    arXiv 检索（官方免费 API，无需 key）
  labmate_cite     DOI → 真实元数据 + 规范 BibTeX（Crossref，杜绝幻觉引用）
  labmate_search   多源文献聚合：arXiv + Crossref + OpenAlex 并发检索 + 跨源去重
  本地组（零依赖，离线可用，数据不出本机）：
  labmate_pdf      本地 PDF 按页文本提取 + 关键词页码溯源（接地问答素材，扫描版诚实诊断）

用法（注册为 MCP stdio server）：
  python labmate_server.py
"""

import ast
import concurrent.futures
import csv
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
import zlib

PROTOCOL_VERSION = "2024-11-05"
SERVER_VERSION = "0.3.0"

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
        return ("-" if isinstance(node.op, ast.USub) else "+") + _latex_expr(node.operand)
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
    if c is not None and phi:
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
    if c is not None and phi:
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
    """从文本样本自动探测分隔符（逗号/制表/分号/竖线）"""
    best, best_n = ",", 0
    for d in [",", "\t", ";", "|"]:
        n = max(line.count(d) for line in sample.splitlines()[:5] if line.strip())
        if n > best_n:
            best, best_n = d, n
    return best

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
        is_num = True
        nums = []
        for v in vals:
            try:
                nums.append(float(str(v).replace(",", "")))
            except ValueError:
                is_num = False
                break
        if is_num and nums:
            n = len(nums)
            mean = sum(nums) / n
            std = math.sqrt(sum((x - mean) ** 2 for x in nums) / (n - 1)) if n > 1 else 0.0
            lines.append("- **%s**（数值列，n=%d，缺失 %d）：均值 %s，标准差 %s，min %s，max %s" %
                         (name, n, missing, _fmt(mean), _fmt(std), _fmt(min(nums)), _fmt(max(nums))))
        else:
            uniq = len(set(str(v) for v in vals))
            lines.append("- **%s**（文本列，n=%d，缺失 %d，唯一值 %d）" % (name, len(vals), missing, uniq))
    lines.append("\n提示：列类型可作为后续处理依据；数值列可接 labmate_fit_lite 拟合或交给绘图脚本。")
    return "\n".join(lines)

def tool_table(args):
    """读取本机 CSV 或内联数据，输出列级统计体检。只读不写，数据不出本机。"""
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

def _make_bibtex(meta):
    """Crossref 元数据 → 规范 BibTeX（独立函数便于离线单测）。"""
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
    f = []
    def add(field, val):
        if val:
            f.append("  %-14s = {%s}" % (field, val))
    add("author", au)
    add("title", meta.get("title", [""])[0] if meta.get("title") else "")
    if entry == "article":
        add("journal", meta.get("container-title", [""])[0] if meta.get("container-title") else "")
        add("volume", meta.get("volume", ""))
        add("number", meta.get("issue", ""))
        add("pages", (meta.get("page", "") or "").replace("-", "--"))
    elif entry == "inproceedings":
        add("booktitle", meta.get("container-title", [""])[0] if meta.get("container-title") else "")
    add("publisher", meta.get("publisher", ""))
    add("year", year)
    add("doi", meta.get("DOI", ""))
    return "@%s{%s,\n%s\n}" % (entry, key, ",\n".join(f))

def tool_cite(args):
    doi = (args.get("doi") or "").strip()
    if not doi:
        return "❌ 请给 DOI，如 10.1016/j.ijrockmas.2019.104123"
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
    bib = _make_bibtex(meta)
    title = meta.get("title", ["(无题)"])[0]
    lines = ["**DOI 元数据**（Crossref，真实数据）",
             "标题：%s" % title,
             "类型：%s | DOI: %s" % (meta.get("type", "?"), meta.get("DOI", "")),
             "\n**BibTeX**：\n```\n%s\n```" % bib,
             "\n（元数据来自 Crossref 官方库，可放心用于 LaTeX；格式可再让 AI 按目标期刊微调。）"]
    return "\n".join(lines)

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
     "description": "本机试验数据体检：读取 CSV 文件或内联数据，自动探测分隔符，输出每列统计摘要（数值列均值/标准差/极值/缺失，文本列唯一值）。只读不写，数据不出本机。",
     "inputSchema": {"type": "object", "properties": {
         "csv_path": {"type": "string", "description": "本机 CSV 文件路径（推荐，支持 utf-8/GBK-BOM）"},
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

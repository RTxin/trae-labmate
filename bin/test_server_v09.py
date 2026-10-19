# -*- coding: utf-8 -*-
"""LabMate server 0.4.5 新增能力单测：FFT 频谱分析（spectrum）+ 振动领域 skill 上线。"""
import json
import math
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

# ======================================================================
print("== 36. _fft / _dft_naive · 纯函数正确性 ==")
ok("N=1 直通", abs(srv._fft([3.14])[0] - 3.14) < 1e-12, srv._fft([3.14]))
f2 = srv._fft([1.0, 2.0])
d2 = srv._dft_naive([1.0, 2.0])
ok("N=2 解析值 [3, -1]", abs(f2[0].real - 3.0) < 1e-12 and abs(f2[1].real + 1.0) < 1e-12
   and abs(f2[0].imag) < 1e-12 and abs(d2[1].real + 1.0) < 1e-12, (f2, d2))
r4 = [1.0, 3.0, -2.0, 0.5]
ff4, dn4 = srv._fft(r4), srv._dft_naive(r4)
ok("N=4 FFT 与朴素 DFT 对拍（实部/虚部）",
   all(abs(ff4[k].real - dn4[k].real) < 1e-9 and abs(ff4[k].imag - dn4[k].imag) < 1e-9
       for k in range(4)), (ff4, dn4))
r8 = [((i * 37) % 13) - 6 + 0.25 * ((i * 11) % 7) for i in range(8)]  # 确定性伪随机
ff8, dn8 = srv._fft(r8), srv._dft_naive(r8)
ok("N=8 对拍（确定性伪随机）",
   all(abs(ff8[k] - dn8[k]) < 1e-9 for k in range(8)), (ff8, dn8))
r16 = [math.sin(0.7 * i) + 0.3 * math.cos(2.1 * i) for i in range(16)]
ff16, dn16 = srv._fft(r16), srv._dft_naive(r16)
ok("N=16 对拍（混合正余弦）",
   all(abs(ff16[k] - dn16[k]) < 1e-9 for k in range(16)), "")
def _raises_value_error():
    try:
        srv._fft([1.0, 2.0, 3.0])
        return False
    except ValueError:
        return True
ok("非二次幂拦截 ValueError", _raises_value_error(), "")
pars = srv._fft(r16)
ok("Parseval 定理 Σ|X|² = N·Σ|x|²",
   abs(sum(abs(v) ** 2 for v in pars) - 16 * sum(v * v for v in r16)) < 1e-9, "")
cs8 = srv._fft([math.cos(2.0 * math.pi * i / 8) for i in range(8)])
ok("cos 单频解析：X[1]=X[7]=4，其余 0",
   abs(cs8[1] - 4) < 1e-9 and abs(cs8[7] - 4) < 1e-9
   and all(abs(cs8[k]) < 1e-9 for k in (0, 2, 3, 4, 5, 6)), cs8)
sn8 = srv._fft([math.sin(2.0 * math.pi * i / 8) for i in range(8)])
ok("sin 单频解析：X[1] = -4j（共轭对称）",
   abs(sn8[1].imag + 4.0) < 1e-9 and abs(sn8[1].real) < 1e-9
   and abs(sn8[7].imag - 4.0) < 1e-9, sn8)
imp = srv._fft([1.0] + [0.0] * 7)
ok("单位脉冲：全谱为 1（平坦幅值谱）",
   all(abs(v - 1.0) < 1e-12 for v in imp), imp)

# ======================================================================
print("== 37. spectrum · 黄金用例（fs=512，N=512，50/120Hz 整周期精确命中）==")
S_FS, S_N = 512.0, 512
ys = [2.0 + math.sin(2 * math.pi * 50 * i / S_FS) + 0.5 * math.sin(2 * math.pi * 120 * i / S_FS)
      for i in range(S_N)]
r = srv.tool_signal({"action": "spectrum", "y": ys, "fs": S_FS})
ok("主峰 50 Hz 精确命中", "50 Hz" in r, r[:300])
ok("次峰 120 Hz 精确命中", "120 Hz" in r, r[:300])
ok("幅值精确：50Hz→1、120Hz→0.5", "幅值 1" in r and "幅值 0.5" in r, r[:400])
ok("频率分辨率 Δf = 1 Hz", "Δf = fs/N = 1 Hz" in r, r[:200])
ok("Nyquist = 256 Hz", "Nyquist = 256 Hz" in r, r[:200])
ok("直流分量（均值）= 2", "直流分量（均值）= 2" in r, r[:200])
ok("二次幂不零填充（无明示）", "零填充" not in r, r[:200])
ok("峰按幅值降序（50 行先于 120 行）",
   r.index("50 Hz") < r.index("120 Hz"), "")

# ======================================================================
print("== 38. spectrum · 零填充路径（fs=1000，N=1000 → 1024）==")
ys2 = [math.sin(2 * math.pi * 50 * i / 1000.0) + 0.5 * math.sin(2 * math.pi * 120 * i / 1000.0)
       for i in range(1000)]
r2 = srv.tool_signal({"action": "spectrum", "y": ys2, "fs": 1000})
ok("零填充明示至 1024 点", "已零填充至 1024 点" in r2, r2[:200])
ok("Δf 以填充后计（0.976562 Hz）", "Δf = fs/N = 0.976562 Hz" in r2, r2[:200])
ok("主峰位置可靠（50Hz → 49.8047，偏差 <0.5Hz）", "49.8047 Hz" in r2, r2[:400])
ok("次峰 120.117 Hz（120Hz 泄漏后近邻 bin）", "120.117 Hz" in r2, r2[:400])
ok("泄漏幅值 < 理想值（0.92 < 1）", "幅值 0.919892" in r2, r2[:400])

# ======================================================================
print("== 39. spectrum · 边界与行为 ==")
ok("缺 fs 拦截", "❌" in srv.tool_signal({"action": "spectrum", "y": [1, 2, 3]}), "")
ok("fs=0 拦截", "❌" in srv.tool_signal({"action": "spectrum", "y": [1, 2, 3], "fs": 0}), "")
ok("fs 负数拦截", "❌" in srv.tool_signal({"action": "spectrum", "y": [1, 2, 3], "fs": -5}), "")
ok("单点数据拦截", "❌" in srv.tool_signal({"action": "spectrum", "y": [1], "fs": 100}), "")
r3c = srv.tool_signal({"action": "spectrum", "y": [3.0, 3.0, 3.0, 3.0], "fs": 10})
ok("纯直流无峰不崩", "未检出局部极大" in r3c and "直流分量（均值）= 3" in r3c, r3c)
r2p = srv.tool_signal({"action": "spectrum", "y": [1.0, -1.0], "fs": 10})
ok("两点数据走通（nfft=2，无峰）", "未检出局部极大" in r2p and "Nyquist = 5 Hz" in r2p, r2p)
ok("未知 action 提示含 spectrum",
   "❌ 未知 action：bad（支持 smooth / interp / integrate / resample / spectrum）"
   == srv.tool_signal({"action": "bad", "y": [1, 2]}), "")
ys3 = [math.sin(2 * math.pi * 50 * i / 512.0) + 0.01 * (((i * 37) % 13) - 6) / 6.0
       for i in range(512)]
r3 = srv.tool_signal({"action": "spectrum", "y": ys3, "fs": 512})
ok("小噪声不撼动主峰（首峰仍 50 Hz）", "  1. 50 Hz" in r3, r3[:300])
ok("fs 字符串 \"512\" 兼容",
   "50 Hz" in srv.tool_signal({"action": "spectrum", "y": ys3, "fs": "512"}), "")

# ======================================================================
print("== 40. 协议层与 vibration skill 注册 ==")
ok("TOOLS 仍为 19 件", len(srv.TOOLS) == 19, len(srv.TOOLS))
sig = [t for t in srv.TOOLS if t["name"] == "labmate_signal"][0]
ok("schema：action 枚举含 spectrum", "spectrum" in sig["inputSchema"]["properties"]["action"]["description"], "")
ok("schema：新增 fs 参数", "fs" in sig["inputSchema"]["properties"]
   and "采样率" in sig["inputSchema"]["properties"]["fs"]["description"], "")
ok("schema：描述含 FFT 频谱", "FFT 频谱" in sig["description"], sig["description"])
ok("_DISPATCH 含 labmate_signal", callable(srv._DISPATCH.get("labmate_signal")), "")
vib = os.path.join(HERE, "..", "skills", "labmate-vibration", "SKILL.md")
vib_txt = open(vib, encoding="utf-8").read() if os.path.exists(vib) else ""
ok("vibration skill 已创建（frontmatter name）", "name: labmate-vibration" in vib_txt, vib)
main_skill = open(os.path.join(HERE, "..", "skills", "labmate", "SKILL.md"), encoding="utf-8").read()
ok("主路由表含 vibration 行", "labmate-vibration" in main_skill, "")
ok("主路由版本行 = 0.4.6", "v0.4.6" in main_skill, "")

def rpc(msgs):
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "labmate_server.py")],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    out, _ = p.communicate(("\n".join(json.dumps(m) for m in msgs) + "\n").encode("utf-8"))
    return [json.loads(l) for l in out.decode("utf-8").splitlines() if l.strip()]

ysm = [math.sin(2.0 * math.pi * 2 * i / 8) for i in range(8)]
res = rpc([{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
           {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "labmate_signal",
                       "arguments": {"action": "spectrum", "y": ysm, "fs": 8}}}])
ok("initialize 版本 = 0.4.6", res[0]["result"]["serverInfo"]["version"] == "0.4.6", res[0])
ok("stdio spectrum 不丢（2 Hz 峰）", "2 Hz" in res[1]["result"]["content"][0]["text"],
   res[1]["result"]["content"][0]["text"][:150])

print("\n== v0.4.5 结果：%d 通过 / %d 失败 ==" % (passed, failed))
sys.exit(1 if failed else 0)

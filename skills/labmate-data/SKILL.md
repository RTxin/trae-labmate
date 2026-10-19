---
name: labmate-data
description: 试验数据处理工具（numpy/scipy）。当用户有试验原始数据需要清洗、滤波、找峰值、算模量、提取特征点、格式转换（设备导出文件→可用数据）时使用。触发：「处理试验数据」「荷载位移曲线」「求弹性模量」「找峰值」「滤波」「去噪」。
---

# LabMate · 试验数据处理（numpy/scipy）

依赖：`pip install numpy scipy`（几乎总已安装）

## 试验数据处理的标准作业

### 1. 荷载-位移/应力-应变曲线特征提取

```python
import numpy as np
from scipy.signal import find_peaks
from scipy.stats import linregress

disp, load = np.loadtxt('test_data.csv', delimiter=',', skiprows=1, unpack=True)

# 峰值（破坏载荷）
peaks, _ = find_peaks(load, prominence=0.05 * load.max())
F_peak = load[peaks[0]]

# 弹性模量：取 20%~50% 峰值载荷段做割线（按用户试验规程调整区间）
mask = (load > 0.2 * F_peak) & (load < 0.5 * F_peak)
E_sec = linregress(disp[mask], load[mask]).slope / area  # 斜率/截面积

# 残余强度：峰值后 80% 曲线均值平台
tail = load[int(0.8 * len(load)):]
tau_res = tail[tail < F_peak].mean()
```

### 2. 滤波去噪（按数据特征选方法）

| 数据 | 推荐方法 | 代码 |
|---|---|---|
| 高频噪声、保峰值形态 | 中值滤波 | `scipy.signal.medfilt(x, k)` |
| 平滑趋势、可视化 | Savitzky-Golay | `scipy.signal.savgol_filter(x, w, p)`（w 取奇数窗口，p=2~3） |
| 低频漂移去除 | 减基线/高通 | `x - scipy.ndimage.gaussian_filter1d(x, sigma=大)` |
| 声发射类脉冲计数 | 阈值+脉冲分离 | `find_peaks(x, height=θ, distance=d)` |

**原则：滤波前后必须叠图对比展示（走 labmate-plot），让用户确认没滤掉真实物理信号。**

### 3. 设备导出文件的处理

试验机导出的格式五花八门（CSV 表头、多列、单位行、时间戳）。处理流程：
1. 先 `head` 看前 5 行结构再写解析——不要猜
2. 无表头/中文表头 → 直接问用户每列是什么（列名截图发来）
3. 数据量大时用 `np.loadtxt`/`pandas.read_csv`，别逐行 read

### 4. 数据质量检查（处理前先报告）

- 采样率与时长是否合理（点数×间隔）
- 有无丢步、跳变、削顶（载荷超量程会削平）
- 多通道是否同步（时间戳对齐）

发现问题先报告再处理——**用户看到"你的数据在 312s 处有一段削顶，疑似超量程"会很惊喜**，这比拟合本身更体现价值。

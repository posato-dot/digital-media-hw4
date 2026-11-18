# 数字媒体程序基础第四次作业

## 题目

Scaled Dot-Product 计算与 Python、C、Rust 效率对比

## 文件清单

| 文件 | 说明 |
|---|---|
| `dot.py` | Python 版点积，仅标准库，`dot(a, b) -> float` |
| `dot.c` | C 版点积，`zig cc -O2`（等价 `gcc -O2`），导出 `double dot(const double*, const double*, size_t)` |
| `dot.rs` | Rust 版点积，`rustc -C opt-level=2`，`extern "C"` 导出给 ctypes |
| `gen_data.py` | 生成三语言共用的 float64 随机向量，固定种子 `SEED = 20261118` |
| `benchmark.py` | 统一计时基准：ctypes 进程内调用、预热 3 轮、正式 5 轮取中位数、两轮偏差 < 5% |
| `test_dot.py` | 5 个边界用例：n=0 / n=1 / 长度不匹配 / 全零向量 / 含 NaN |
| `bench_results.json` | 两轮正式基准的完整结果 JSON |
| `耗时对比表.md` | 3 规模 × 3 语言耗时与加速比 |
| `benchmark_terminal.txt` | 基准运行终端输出 |

## 实测结果

单次点积耗时（毫秒，5 轮中位数；加速比相对 Python）：

| N | Python | C | C 加速 | Rust | Rust 加速 |
|---|---|---|---|---|---|
| 10⁴ | 0.8852 | 0.0162 | 54.57× | 0.0122 | 72.45× |
| 10⁵ | 8.8491 | 0.1696 | 52.18× | 0.1256 | 70.44× |
| 10⁶ | 88.1240 | 1.6633 | 52.98× | 1.2707 | 69.35× |

- 正确性：三版与 Python 基准最大相对误差 ≤ 2.8e-14（验收线 1e-9）。
- 边界测试：5/5 ALL PASS。
- 稳定性：两轮 9/9 偏差 < 5%，最大 3.63%。

## 复现方法

```bash
# 1. 生成共用数据（三语言读同一份 .bin）
python gen_data.py --out data --sizes 1000,10000,100000,1000000

# 2. 编译 C 与 Rust 为 DLL（Windows 示例）
zig cc -O2 -shared -o dot_c.dll dot.c
rustc -C opt-level=2 --crate-type cdylib -o dot_rust.dll dot.rs

# 3. 跑正确性核对与边界测试
python benchmark.py --data data --verify-small
python test_dot.py

# 4. 跑正式基准
python benchmark.py --data data --bin . --out results
```

计时口径：数据一次性预读内存；C/Rust 编成 DLL 由 `ctypes` 在同一进程内调用，计时不含文件 IO 与进程启动；循环内用 `volatile` / `black_box` 消费结果，防止 `-O2` 优化消除。

## 说明

源码与实测数据由课程实验真实运行产生，未使用模拟数值。报告正文、截图、提示词与修错记录见同次提交的实验报告文档。

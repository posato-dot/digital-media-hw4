"""第04讲 · 统一计时基准（仅标准库）。

设计要点（对应实验指南「计时规范 25 分」）：
  1. 三种语言读同一份 data/*.bin，数据由本脚本一次性读入内存，之后不再有任何 IO；
  2. C / Rust 编译成 DLL，由 ctypes 在**本进程内**调用，消除「进程启动 + 文件读取」
     被计入耗时的经典错误；Python 版直接 import 调用；
  3. 计时统一由外层 Python 的 time.perf_counter() 完成，预热 3 轮、正式 5 轮取中位数；
  4. 每轮循环内用 dot_reps(..., reps) 重复计算并把结果累加进 volatile / black_box
     sink，返回值被本脚本检查，保证结果真的被消费、不会被 -O2 / opt-level=2 优化掉；
  5. 正确性：三版 dot() 与 Python 基准相对误差 <= 1e-9；
  6. 连续跑两轮基准，各语言中位数偏差 < 5% 才算计时口径稳定。

用法：
  python benchmark.py --data <data目录> --bin <DLL/EXE所在目录> [--out <结果目录>]
  python benchmark.py --data <data目录> --verify-small      # 仅做 N=1000 小数据核对
"""
import argparse
import ctypes
import gc
import json
import math
import os
import statistics
import sys
import time
from array import array

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dot as py_dot  # noqa: E402

SIZES = [10_000, 100_000, 1_000_000]
# 修错记录第 3 轮：初版三语言共用同一 reps，C 在 N=10^6 时每轮仅约 16 ms，
# OS 调度抖动主导，实测两轮偏差 6.70% > 5% 判失败。改为按「每轮 >= 100 ms」
# 对编译型语言自适应增加重复次数；单次耗时口径（总时间 / reps）保持一致。
REPS_PY = {10_000: 200, 100_000: 50, 1_000_000: 10}
REPS_NATIVE = {10_000: 2000, 100_000: 500, 1_000_000: 100}
WARMUP = 3
ROUNDS = 5
LANG_ORDER = ["Python", "C", "Rust"]
CDOUBLE_P = ctypes.POINTER(ctypes.c_double)


def load_arrays(folder, n):
    a = array("d")
    b = array("d")
    with open(os.path.join(folder, "a_f64_N%d.bin" % n), "rb") as f:
        a.fromfile(f, n)
    with open(os.path.join(folder, "b_f64_N%d.bin" % n), "rb") as f:
        b.fromfile(f, n)
    if len(a) != n or len(b) != n:
        raise ValueError("short read: %d / %d, expected %d" % (len(a), len(b), n))
    return a, b


def naive_dot_2d(a, b):
    """步骤 5 的独立基准：手写双重循环算出全部 a[i]*b[j]，只累加对角线。

    与被测实现（sum 生成器 / C for / Rust for）不同源，可用来逐位核对。
    """
    s = 0.0
    for i in range(len(a)):
        for j in range(len(b)):
            if i == j:
                s += a[i] * b[j]
    return s


def load_dll(path):
    lib = ctypes.CDLL(path)
    lib.dot.argtypes = [CDOUBLE_P, CDOUBLE_P, ctypes.c_size_t]
    lib.dot.restype = ctypes.c_double
    lib.dot_reps.argtypes = [CDOUBLE_P, CDOUBLE_P, ctypes.c_size_t, ctypes.c_int]
    lib.dot_reps.restype = ctypes.c_double
    return lib


def rel_err(x, ref):
    return abs(x - ref) / max(abs(ref), 1e-300)


def measure_all(fns, reps_map):
    """预热 3 轮 + 正式 5 轮；三语言交错执行，返回各语言的 (5 轮, 中位数, 校验和)。

    修错记录第 3 轮的补充措施：
      - 交错执行：避免连跑同一语言 5 轮造成 CPU 频率/缓存热漂移；
      - 计时期间关闭分代 GC：消除解释器偶发停顿；
      - 每个语言的单次耗时口径仍是「该轮总时间 / 该语言自己的 reps」。
    """
    for lang in LANG_ORDER:
        for _ in range(WARMUP):
            fns[lang]()
    times_by = {lang: [] for lang in LANG_ORDER}
    sinks = {}
    gc.collect()
    gc.disable()
    try:
        for _ in range(ROUNDS):
            for lang in LANG_ORDER:
                t0 = time.perf_counter()
                sinks[lang] = fns[lang]()
                t1 = time.perf_counter()
                times_by[lang].append((t1 - t0) / reps_map[lang] * 1000.0)
    finally:
        gc.enable()
    return {lang: (times_by[lang], statistics.median(times_by[lang]), sinks[lang])
            for lang in LANG_ORDER}


def run_once(data, libs, sizes, run_label):
    out = {}
    for n in sizes:
        a, b = load_arrays(data, n)                 # IO 在计时之外
        na = (ctypes.c_double * n).from_buffer(a)
        nb = (ctypes.c_double * n).from_buffer(b)
        reps_map = {"Python": REPS_PY[n], "C": REPS_NATIVE[n], "Rust": REPS_NATIVE[n]}
        ref = py_dot.dot(a, b)
        checks = {"Python": 0.0}
        for name in ("C", "Rust"):
            val = libs[name].dot(na, nb, n)
            checks[name] = rel_err(val, ref)
            if checks[name] > 1e-9:
                raise AssertionError("%s N=%d 相对误差 %.3g 超限" % (name, n, checks[name]))

        fns = {
            "Python": lambda: py_dot.dot_reps(a, b, reps_map["Python"]),
            "C": lambda: libs["C"].dot_reps(na, nb, n, reps_map["C"]),
            "Rust": lambda: libs["Rust"].dot_reps(na, nb, n, reps_map["Rust"]),
        }
        measured = measure_all(fns, reps_map)
        row = {}
        for lang in LANG_ORDER:
            times, med, sink = measured[lang]
            if not math.isfinite(sink):
                raise AssertionError("%s 校验和非法，结果可能被优化掉" % lang)
            row[lang] = {"reps": reps_map[lang],
                         "rounds_ms": [round(t, 6) for t in times],
                         "median_ms": round(med, 6), "checksum": sink}
        base = row["Python"]["median_ms"]
        for lang in LANG_ORDER:
            row[lang]["speedup"] = round(base / row[lang]["median_ms"], 2)
        out[str(n)] = {"reps_per_round": reps_map, "reference": ref,
                       "rel_err": checks, "langs": row}
        print("[%s] N=%-8d Python %9.4f ms | C %9.4f ms (%.1fx) | Rust %9.4f ms (%.1fx) | relerr<=%.1e"
              % (run_label, n, row["Python"]["median_ms"], row["C"]["median_ms"],
                 row["C"]["speedup"], row["Rust"]["median_ms"], row["Rust"]["speedup"],
                 max(checks.values())))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--bin", default=".")
    ap.add_argument("--out", default=".")
    ap.add_argument("--verify-small", action="store_true")
    args = ap.parse_args()

    if args.verify_small:
        a, b = load_arrays(args.data, 1000)
        ref = naive_dot_2d(a, b)
        got = py_dot.dot(a, b)
        print("N=1000 手写双重循环基准 = %.17g" % ref)
        print("N=1000 Python dot()      = %.17g" % got)
        print("N=1000 相对误差          = %.3g  -> %s"
              % (rel_err(got, ref), "PASS" if rel_err(got, ref) <= 1e-9 else "FAIL"))
        return

    libs = {
        "C": load_dll(os.path.join(args.bin, "dot_c.dll")),
        "Rust": load_dll(os.path.join(args.bin, "dot_rs.dll")),
    }
    print("=== 计时协议：预热 %d 轮 / 正式 %d 轮中位数 / 计时不含 IO 与进程启动 ==="
          % (WARMUP, ROUNDS))
    print("=== 编译：C -O2 / Rust -C opt-level=2，循环内消费 volatile(black_box) 校验和 ===")
    run1 = run_once(args.data, libs, SIZES, "第1轮")
    run2 = run_once(args.data, libs, SIZES, "第2轮")

    print()
    print("=== 两轮基准稳定性（要求偏差 < 5%） ===")
    stability = {}
    for n in SIZES:
        for lang in LANG_ORDER:
            m1 = run1[str(n)]["langs"][lang]["median_ms"]
            m2 = run2[str(n)]["langs"][lang]["median_ms"]
            d = abs(m1 - m2) / m1 * 100
            stability["%d_%s" % (n, lang)] = round(d, 2)
            print("  N=%-8d %-6s 第1轮 %9.4f ms / 第2轮 %9.4f ms / 偏差 %.2f%% %s"
                  % (n, lang, m1, m2, d, "PASS" if d < 5 else "FAIL"))

    os.makedirs(args.out, exist_ok=True)
    result = {"protocol": {"warmup": WARMUP, "rounds": ROUNDS, "median": True,
                           "io_excluded": True, "process_startup_excluded": True,
                           "timer": "Python time.perf_counter (outer)",
                           "build": {"C": "-O2", "Rust": "-C opt-level=2"}},
              "run1": run1, "run2": run2, "stability_percent": stability}
    with open(os.path.join(args.out, "bench_results.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    lines = ["# 耗时对比表（3 规模 × 3 语言）", "",
             "计时协议：外层 Python `perf_counter`；预热 3 轮、正式 5 轮取中位数；"
             "计时不含文件读取与进程启动；每轮结果由 volatile / black_box 校验和消费。", "",
             "| N | 语言 | 每轮重复 | 5 轮耗时 (ms) | 中位数 (ms) | 相对 Python 加速 | 两轮偏差 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for n in SIZES:
        r = run1[str(n)]["langs"]
        for lang in LANG_ORDER:
            rounds = " / ".join("%.3f" % x for x in r[lang]["rounds_ms"])
            lines.append("| %d | %s | %d | %s | %.4f | %.2f× | %.2f%% |"
                         % (n, lang, r[lang]["reps"], rounds, r[lang]["median_ms"],
                            r[lang]["speedup"], stability["%d_%s" % (n, lang)]))
    lines += ["", "正确性：三版 `dot()` 与 Python 基准相对误差 ≤ 1e-9（详见 bench_results.json）。", ""]
    with open(os.path.join(args.out, "耗时对比表.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print()
    print("\n".join(lines))
    print()
    print("结果已写入：bench_results.json / 耗时对比表.md")


if __name__ == "__main__":
    main()

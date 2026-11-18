"""第04讲 · test_dot.py：5 个边界用例（仅标准库）。

用例：n=0 / n=1 / 长度不匹配 / 全零向量 / 含 NaN 输入。
对 Python 版逐项验证；C / Rust 通过 ctypes 调用同一个 dot() 接口做交叉验证
（extern "C" 接口只有一个长度参数 n，等长校验由 Python 调用层负责）。
"""
import ctypes
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dot as py_dot  # noqa: E402

CDOUBLE_P = ctypes.POINTER(ctypes.c_double)
CASES = [
    ("n=0", [], [], 0.0),
    ("n=1", [3.0], [4.0], 12.0),
    ("长度不匹配", [1.0, 2.0], [1.0], ValueError),
    ("全零向量", [0.0] * 8, [0.0] * 8, 0.0),
    ("含 NaN 输入", [1.0, float("nan"), 3.0], [2.0, 3.0, 4.0], float("nan")),
]


def native_dot(lib, a, b):
    n = len(a)
    buf_a = (ctypes.c_double * max(n, 1))(*a)
    buf_b = (ctypes.c_double * max(n, 1))(*b)
    return lib.dot(buf_a, buf_b, n)


def load_lib(path):
    if not os.path.exists(path):
        return None
    lib = ctypes.CDLL(path)
    lib.dot.argtypes = [CDOUBLE_P, CDOUBLE_P, ctypes.c_size_t]
    lib.dot.restype = ctypes.c_double
    return lib


def check_py(name, a, b, expect):
    try:
        got = py_dot.dot(a, b)
    except ValueError:
        return ("PASS", "ValueError（已显式拦截）") if expect is ValueError else ("FAIL", "误抛异常")
    if expect is ValueError:
        return "FAIL", "未校验长度不匹配"
    if math.isnan(expect):
        return ("PASS", "NaN（如实传播）") if math.isnan(got) else ("FAIL", "NaN 被吞掉")
    return ("PASS", "%.17g" % got) if abs(got - expect) <= 1e-12 else ("FAIL", "%.17g" % got)


def main():
    bin_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    libs = {"C": load_lib(os.path.join(bin_dir, "dot_c.dll")),
            "Rust": load_lib(os.path.join(bin_dir, "dot_rs.dll"))}
    print("=== 5 个边界用例（Python 版 + C/Rust 交叉验证） ===")
    all_pass = True
    for name, a, b, expect in CASES:
        status, detail = check_py(name, a, b, expect)
        extra = []
        for lang, lib in libs.items():
            if lib is None:
                extra.append("%s=未加载" % lang)
                continue
            if len(a) != len(b):
                extra.append("%s=由调用层拦截" % lang)
                continue
            v = native_dot(lib, a, b)
            if math.isnan(expect):
                ok = math.isnan(v)
            else:
                ok = abs(v - expect) <= 1e-12
            extra.append("%s=%s" % (lang, "OK" if ok else "MISMATCH"))
            if not ok:
                all_pass = False
        if status != "PASS":
            all_pass = False
        print("  %-12s %-4s %-28s %s" % (name, status, detail, " / ".join(extra)))
    print("=== 总计：%s ===" % ("ALL PASS (5/5)" if all_pass else "有失败项"))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

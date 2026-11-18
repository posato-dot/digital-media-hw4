"""第04讲 · Python 版点积（仅标准库，无 numpy / numba / BLAS）。

接口：dot(a, b) -> float64 标量
约束：只用标准库与原生语法；计时不含文件读取；sum(...) 生成器表达式为单循环实现。
示例：dot([1,2,3],[4,5,6]) == 32.0

CLI：python dot.py <data目录> <N>   （读同一份二进制文件，打印结果与校验和）
"""
import os
import sys
import time
from array import array


def dot(a, b) -> float:
    """返回两个等长序列的点积。长度不匹配时显式抛错，不做静默截断。"""
    if len(a) != len(b):
        raise ValueError("length mismatch: %d != %d" % (len(a), len(b)))
    return sum(x * y for x, y in zip(a, b))


def dot_reps(a, b, reps: int) -> float:
    """重复 reps 次并累加结果，保证循环确实被消费、不会被优化掉。"""
    sink = 0.0
    for _ in range(reps):
        sink += dot(a, b)
    return sink


def load_arrays(folder: str, n: int):
    a = array("d")
    b = array("d")
    with open(os.path.join(folder, "a_f64_N%d.bin" % n), "rb") as f:
        a.fromfile(f, n)
    with open(os.path.join(folder, "b_f64_N%d.bin" % n), "rb") as f:
        b.fromfile(f, n)
    if len(a) != n or len(b) != n:
        raise ValueError("short read: %d / %d, expected %d" % (len(a), len(b), n))
    return a, b


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python dot.py <data_dir> <N>")
        sys.exit(2)
    folder, n = sys.argv[1], int(sys.argv[2])
    a, b = load_arrays(folder, n)          # 文件读取，不计入计时
    t0 = time.perf_counter()
    result = dot(a, b)
    t1 = time.perf_counter()
    checksum = dot_reps(a, b, 5)
    print("lang=Python  N=%d  result=%.17g  checksum=%.17g  compute=%.6f ms"
          % (n, result, checksum, (t1 - t0) * 1000))


if __name__ == "__main__":
    main()

"""第04讲 · 生成三语言共用的同一组 float64 随机向量（仅标准库）。

用法：
    python gen_data.py --out <data目录> [--sizes 1000,10000,100000,1000000]

输出：<out>/a_f64_N<n>.bin 与 b_f64_N<n>.bin，每个元素为小端 float64。
三种语言一律读同一份二进制文件，绝不各算各的随机数。
"""
import argparse
import os
import random
from array import array

SEED = 20261118


def generate(n: int, out: str) -> None:
    rng = random.Random(SEED + n)
    a = array("d", (rng.uniform(-1.0, 1.0) for _ in range(n)))
    b = array("d", (rng.uniform(-1.0, 1.0) for _ in range(n)))
    os.makedirs(out, exist_ok=True)
    pa = os.path.join(out, "a_f64_N%d.bin" % n)
    pb = os.path.join(out, "b_f64_N%d.bin" % n)
    with open(pa, "wb") as f:
        a.tofile(f)
    with open(pb, "wb") as f:
        b.tofile(f)
    print("N=%-8d a=%s b=%s  (%d bytes each)" % (n, pa, pb, n * 8))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--sizes", default="1000,10000,100000,1000000")
    args = ap.parse_args()
    for s in args.sizes.split(","):
        generate(int(s), args.out)


if __name__ == "__main__":
    main()

/* 第04讲 · C 版点积（zig cc -O2，等价于 gcc -O2；仅标准库）
 *
 * 接口：double dot(const double *a, const double *b, size_t n) -> float64 标量
 * 编译：
 *   zig cc -O2 -shared -DDOT_NO_MAIN -o dot_c.dll dot.c      (供 benchmark.py 用 ctypes 进程内调用)
 *   zig cc -O2 -o dot_c.exe dot.c                            (命令行正确性核对)
 *
 * 关键：dot_reps 把结果累加到 volatile sink 并返回，调用方必须消费返回值，
 *       否则 -O2 会把整段循环优化掉，得到「C 快得离谱」的假数据。
 */
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>

#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif

EXPORT double dot(const double *a, const double *b, size_t n) {
    double s = 0.0;
    for (size_t i = 0; i < n; ++i) s += a[i] * b[i];
    return s;
}

EXPORT double dot_reps(const double *a, const double *b, size_t n, int reps) {
    volatile double sink = 0.0;
    for (int r = 0; r < reps; ++r) sink += dot(a, b, n);
    return sink;
}

#ifndef DOT_NO_MAIN
static double *load_vec(const char *folder, const char *tag, size_t n) {
    char path[512];
    snprintf(path, sizeof(path), "%s/%s_f64_N%zu.bin", folder, tag, n);
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    double *p = (double *)malloc(n * sizeof(double));
    if (!p) { fprintf(stderr, "out of memory\n"); exit(1); }
    size_t got = fread(p, sizeof(double), n, f);
    fclose(f);
    if (got != n) {
        fprintf(stderr, "short read: %zu != %zu from %s\n", got, n, path);
        exit(1);
    }
    return p;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: dot_c <data_dir> <N>\n");
        return 2;
    }
    size_t n = (size_t)strtoull(argv[2], NULL, 10);
    double *a = load_vec(argv[1], "a", n);   /* 文件读取，不计入计时 */
    double *b = load_vec(argv[1], "b", n);
    double result = dot(a, b, n);
    double checksum = dot_reps(a, b, n, 5);
    printf("lang=C  N=%zu  result=%.17g  checksum=%.17g\n", n, result, checksum);
    free(a);
    free(b);
    return 0;
}
#endif

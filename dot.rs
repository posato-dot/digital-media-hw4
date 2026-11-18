/* 第04讲 · Rust 版点积（rustc -C opt-level=2，等价 --release；仅标准库）
 *
 * 接口：extern "C" fn dot(a, b, n) -> f64，导出给 benchmark.py 的 ctypes 调用
 * 编译：
 *   rustc -C opt-level=2 --crate-type cdylib --cfg dot_dll -o dot_rs.dll dot.rs
 *   rustc -C opt-level=2 -o dot_rs.exe dot.rs
 *
 * 关键：dot_reps 用 std::hint::black_box 消费结果，防止优化器消除整段循环。
 */
#![allow(unexpected_cfgs)]

#[no_mangle]
pub extern "C" fn dot(a: *const f64, b: *const f64, n: usize) -> f64 {
    let (sa, sb) = unsafe {
        (
            std::slice::from_raw_parts(a, n),
            std::slice::from_raw_parts(b, n),
        )
    };
    let mut s = 0.0f64;
    for i in 0..n {
        s += sa[i] * sb[i];
    }
    s
}

#[no_mangle]
pub extern "C" fn dot_reps(a: *const f64, b: *const f64, n: usize, reps: i32) -> f64 {
    let mut sink = 0.0f64;
    for _ in 0..reps {
        sink += dot(a, b, n);
    }
    std::hint::black_box(sink)
}

#[cfg(not(dot_dll))]
use std::convert::TryInto;

#[cfg(not(dot_dll))]
fn read_f64(folder: &str, tag: &str, n: usize) -> Vec<f64> {
    let path = format!("{}/{}_f64_N{}.bin", folder, tag, n);
    let bytes = std::fs::read(&path).unwrap_or_else(|e| panic!("cannot open {}: {}", path, e));
    assert_eq!(bytes.len(), n * 8, "short read from {}", path);
    let mut v = Vec::with_capacity(n);
    for chunk in bytes.chunks_exact(8) {
        let arr: [u8; 8] = chunk.try_into().unwrap();
        v.push(f64::from_le_bytes(arr));
    }
    v
}

#[cfg(not(dot_dll))]
fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 3 {
        eprintln!("usage: dot_rs <data_dir> <N>");
        std::process::exit(2);
    }
    let n: usize = args[2].parse().expect("N must be an integer");
    let a = read_f64(&args[1], "a", n);   /* 文件读取，不计入计时 */
    let b = read_f64(&args[1], "b", n);
    let result = dot(a.as_ptr(), b.as_ptr(), n);
    let checksum = dot_reps(a.as_ptr(), b.as_ptr(), n, 5);
    println!("lang=Rust  N={}  result={:.17e}  checksum={:.17e}", n, result, checksum);
}

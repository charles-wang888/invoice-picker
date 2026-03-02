# -*- coding: utf-8 -*-
"""
生成原始发票数据：10000 张，面额以 100 块、1000 块左右为主（金额偏小），
便于凑 40 万等较小目标；保留 2 位小数，20 位发票号码，不排序，写入 raw_data.txt。
"""
import random


def make_invoice_code(index: int) -> str:
    """
    生成 20 位发票编码，参考中国增值税发票规则：
    发票代码 12 位 + 发票号码 8 位，用序号保证唯一。
    """
    code12 = f"0440{index // 10**4:08d}"
    number8 = f"{index % 10**4:08d}"
    return code12 + number8


def sample_amount(rng: random.Random) -> float:
    """按比例生成 100 左右、1000 左右及少量稍大面额，金额尽可能偏小。"""
    band = rng.choices(
        ["small", "medium", "large"],
        weights=[0.45, 0.45, 0.10],  # 约 45% 一百档、45% 一千档、10% 两千档
        k=1,
    )[0]
    if band == "small":
        return round(rng.uniform(80.0, 280.0), 2)   # 约 100 块左右
    if band == "medium":
        return round(rng.uniform(450.0, 1650.0), 2)  # 约 1000 块左右
    return round(rng.uniform(1600.0, 3500.0), 2)    # 少量 2000 块左右


def main():
    rng = random.Random(2024)
    n = 10000
    lines = []
    for i in range(n):
        code = make_invoice_code(i)
        amount = sample_amount(rng)
        lines.append(f"{code} {amount:.2f}")
    random.shuffle(lines)
    with open("raw_data.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"已生成 {n} 张发票并保存到 raw_data.txt（面额以 100/1000 档为主，未排序）")


if __name__ == "__main__":
    main()

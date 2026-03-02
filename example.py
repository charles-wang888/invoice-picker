# -*- coding: utf-8 -*-
"""
发票凑单内核 - 调用示例
演示如何作为内核被产品层调用（列表、字典、自定义配置等）。
"""
import random
from invoice_selector import (
    select_invoices,
    Invoice,
    SolverConfig,
    DEFAULT_CONFIG,
)


def demo_list_of_tuples():
    """入参为 (id, amount) 元组列表"""
    rows = [
        ("FP001", 1200.50),
        ("FP002", 800.00),
        ("FP003", 3500.00),
        ("FP004", 600.25),
        ("FP005", 2100.00),
        ("FP006", 450.00),
        ("FP007", 980.00),
        ("FP008", 1500.00),
        ("FP009", 720.00),
        ("FP010", 3100.00),
    ]
    result = select_invoices(rows, select_count=4, target_amount=5000.0)
    print("demo_list_of_tuples:")
    print(f"  选中: {result.selected_ids}, 总金额: {result.total_amount:.2f}, 超出: {result.gap:.2f}")
    print()


def demo_list_of_dicts():
    """入参为字典列表（如从数据库/Excel 查出的行）"""
    rows = [
        {"id": "A001", "amount": 1000.0, "date": "2024-01-01"},
        {"id": "A002", "amount": 2000.0, "date": "2024-01-02"},
        {"id": "A003", "amount": 500.0, "date": "2024-01-03"},
        {"id": "A004", "amount": 1500.0, "date": "2024-01-04"},
        {"id": "A005", "amount": 3000.0, "date": "2024-01-05"},
    ]
    result = select_invoices(
        rows,
        select_count=3,
        target_amount=4000.0,
        id_key="id",
        amount_key="amount",
    )
    print("demo_list_of_dicts:")
    print(f"  选中: {result.selected_ids}, 总金额: {result.total_amount:.2f}, 可行: {result.is_feasible()}")
    print()


def demo_large_scale():
    """模拟 X=10000, Y=1000, Z=100万 场景"""
    random.seed(42)
    # 生成 10000 张发票，面额 100～5000 元，两位小数
    rows = [
        (f"INV{i:06d}", round(random.uniform(100, 5000), 2))
        for i in range(10000)
    ]
    target = 1_000_000.0
    count = 1000
    config = SolverConfig(max_swap_rounds=2000, min_improvement=0.01)
    result = select_invoices(rows, select_count=count, target_amount=target, config=config)
    print("demo_large_scale (X=10000, Y=1000, Z=100万):")
    print(f"  选中张数: {len(result.selected)}, 总金额: {result.total_amount:,.2f}")
    print(f"  目标: {target:,.2f}, 超出: {result.gap:,.2f}, 可行: {result.is_feasible()}")
    if result.meta:
        print(f"  耗时: {result.meta.get('elapsed_seconds')}s, 交换轮数: {result.iterations}")
    print()


if __name__ == "__main__":
    demo_list_of_tuples()
    demo_list_of_dicts()
    demo_large_scale()

# -*- coding: utf-8 -*-
"""
发票凑单内核 - 求解器
算法：先排序，再贪心取 Y 张使总金额 >= Z，再通过交换在保持 >= Z 的前提下尽量逼近 Z。
时间复杂度：O(X log X) + O(R * X * Y)，R 为交换轮数，典型 R = O(X)。
"""
from __future__ import annotations

import random
import time
from typing import List, Optional, Tuple

from .config import SolverConfig, DEFAULT_CONFIG
from .types import Invoice, SelectResult


def _total(invoices: List[Invoice]) -> float:
    return sum(inv.amount for inv in invoices)


def _select_greedy_sorted(
    sorted_invoices: List[Invoice],
    target: float,
    count: int,
) -> Tuple[List[Invoice], List[Invoice], float]:
    """
    在已按金额降序的列表上，贪心选取 count 张使总金额 >= target。
    若前 count 张不足 target，则尽量多取直到 >= target（可能超过 count 张则截断为 count）。
    返回 (已选, 未选, 已选总金额)。
    约定：若无论如何都无法 >= target，则仍返回选 count 张（前 count 大）及总金额。
    """
    n = len(sorted_invoices)
    if count <= 0 or n == 0:
        return [], list(sorted_invoices), 0.0
    if count >= n:
        chosen = list(sorted_invoices)
        return chosen, [], _total(chosen)

    # 先取前 count 张（最大的 count 张）
    chosen = list(sorted_invoices[:count])
    unchosen = list(sorted_invoices[count:])
    total = _total(chosen)

    if total >= target:
        return chosen, unchosen, total

    # 不足 target：从未选中依次加入最大的，直到 >= target，再删掉多出来的（删最小的已选）
    for inv in unchosen[:]:
        chosen.append(inv)
        unchosen.remove(inv)
        total += inv.amount
        if total >= target:
            break

    # 若 chosen 多于 count，去掉金额最小的若干张，使总数仍 >= target
    chosen.sort(key=lambda x: x.amount, reverse=True)
    while len(chosen) > count and (total - chosen[-1].amount) >= target:
        total -= chosen[-1].amount
        unchosen.append(chosen.pop())

    return chosen, unchosen, total


def _swap_round(
    chosen: List[Invoice],
    unchosen: List[Invoice],
    target: float,
    total: float,
    tol: float,
    min_improvement: float,
    descending: bool,
) -> Tuple[bool, float]:
    """
    执行一轮交换：用未选中的一张换掉已选中的一张，使总金额仍 >= target 且尽量变小。
    返回 (是否有过交换, 当前总金额)。
    """
    improved = False
    # 要减小总金额：用 unchosen 中较小的换 chosen 中较大的；已选按降序、未选按升序以优先大额换出、小额换入
    chosen_sorted = sorted(chosen, key=lambda x: x.amount, reverse=True)
    unchosen_sorted = sorted(unchosen, key=lambda x: x.amount, reverse=(not descending))

    for i, out_c in enumerate(chosen_sorted):
        if total - out_c.amount < target - tol:
            continue
        for j, in_c in enumerate(unchosen_sorted):
            if in_c.amount >= out_c.amount - tol:
                continue
            new_total = total - out_c.amount + in_c.amount
            if new_total < target - tol:
                continue
            if new_total >= total - min_improvement:
                continue
            # 执行交换
            total = new_total
            chosen.remove(out_c)
            chosen.append(in_c)
            unchosen.remove(in_c)
            unchosen.append(out_c)
            improved = True
            return improved, total

    return improved, total


def solve(
    invoices: List[Invoice],
    select_count: int,
    target_amount: float,
    config: Optional[SolverConfig] = None,
) -> SelectResult:
    """
    从 invoices 中选出 select_count 张，使总金额 >= target_amount 且尽可能接近。

    :param invoices: 发票列表，每张 amount > 0
    :param select_count: 需要选出的张数 Y
    :param target_amount: 目标金额 Z（元）
    :param config: 求解配置，None 使用 DEFAULT_CONFIG
    :return: SelectResult，含 selected、total_amount、gap、selected_ids 等
    """
    cfg = config or DEFAULT_CONFIG
    tol = cfg.amount_tolerance
    target = float(target_amount)
    count = int(select_count)
    n = len(invoices)

    if n < count:
        return SelectResult(
            selected=[],
            total_amount=0.0,
            target=target,
            gap=target,
            selected_ids=[],
            iterations=0,
            meta={"error": "发票总数不足 select_count"},
        )

    start = time.perf_counter()

    # 1. 排序：按金额；同金额时用 tie_break_seed 生成固定次要键以得到不同组合
    seed = getattr(cfg, "sort_tie_break_seed", None)
    if seed is not None:
        rng = random.Random(seed)
        tie_keys = {id(inv): rng.random() for inv in invoices}
        sorted_invoices = sorted(
            invoices,
            key=lambda x: (x.amount, tie_keys[id(x)], x.id),
            reverse=cfg.sort_descending,
        )
    else:
        sorted_invoices = sorted(
            invoices,
            key=lambda x: x.amount,
            reverse=cfg.sort_descending,
        )

    # 2. 贪心初始解
    chosen, unchosen, total = _select_greedy_sorted(sorted_invoices, target, count)

    if total < target - tol:
        elapsed = time.perf_counter() - start
        return SelectResult(
            selected=chosen,
            total_amount=total,
            target=target,
            gap=target - total,
            selected_ids=[inv.id for inv in chosen],
            iterations=0,
            meta={"error": "无法凑到目标金额", "elapsed_seconds": elapsed},
        )

    # 3. 交换改进
    max_rounds = cfg.max_swap_rounds
    min_imp = cfg.min_improvement
    rounds = 0
    while True:
        improved, total = _swap_round(
            chosen, unchosen, target, total, tol, min_imp, cfg.sort_descending
        )
        rounds += 1
        if not improved:
            break
        if max_rounds is not None and rounds >= max_rounds:
            break

    elapsed = time.perf_counter() - start
    gap = total - target

    return SelectResult(
        selected=chosen,
        total_amount=total,
        target=target,
        gap=gap,
        selected_ids=[inv.id for inv in chosen],
        iterations=rounds,
        meta={"elapsed_seconds": round(elapsed, 4), "algorithm": "sort_greedy_swap"},
    )

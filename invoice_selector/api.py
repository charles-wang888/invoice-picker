# -*- coding: utf-8 -*-
"""
发票凑单内核 - 对外 API
产品层仅依赖此模块即可完成凑单调用。
"""
from __future__ import annotations

from typing import Any, List, Optional, Union

from .config import SolverConfig, DEFAULT_CONFIG
from .solver import solve
from .types import Invoice, SelectResult, invoice_from_value


def select_invoices(
    invoices: Union[List[Invoice], List[tuple], List[dict]],
    select_count: int,
    target_amount: float,
    *,
    config: Optional[SolverConfig] = None,
    id_key: str = "id",
    amount_key: str = "amount",
) -> SelectResult:
    """
    从多张发票中选出指定张数，使总金额 >= target_amount 且尽可能接近目标。

    入参支持三种形式：
    - List[Invoice]：直接使用内核类型
    - List[tuple]：每项为 (id, amount) 或 (amount,)（缺省 id 用下标）
    - List[dict]：每项含 id_key、amount_key 的字典

    :param invoices: 发票列表
    :param select_count: 需要选出的张数 Y
    :param target_amount: 目标金额 Z（元）
    :param config: 求解配置，None 使用默认配置
    :param id_key: 当 invoices 为 List[dict] 时使用的 id 键名
    :param amount_key: 当 invoices 为 List[dict] 时使用的金额键名
    :return: SelectResult，包含 selected、total_amount、gap、selected_ids 等
    """
    inv_list = _normalize_invoices(invoices, id_key=id_key, amount_key=amount_key)
    return solve(inv_list, select_count, target_amount, config=config)


def _normalize_invoices(
    raw: List[Any],
    id_key: str = "id",
    amount_key: str = "amount",
) -> List[Invoice]:
    if not raw:
        return []
    first = raw[0]
    if isinstance(first, Invoice):
        return list(raw)
    if isinstance(first, (list, tuple)):
        out = []
        for i, item in enumerate(raw):
            if len(item) >= 2:
                out.append(Invoice(id=str(item[0]), amount=float(item[1])))
            else:
                out.append(Invoice(id=str(i), amount=float(item[0])))
        return out
    if isinstance(first, dict):
        return [
            Invoice(
                id=str(item.get(id_key, i)),
                amount=float(item[amount_key]),
                extra=dict(item),
            )
            for i, item in enumerate(raw)
        ]
    raise TypeError("invoices 须为 List[Invoice] / List[tuple] / List[dict]")


__all__ = [
    "select_invoices",
    "Invoice",
    "SelectResult",
    "SolverConfig",
    "DEFAULT_CONFIG",
    "invoice_from_value",
]

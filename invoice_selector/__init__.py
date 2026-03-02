# -*- coding: utf-8 -*-
"""
发票凑单内核 - 从 X 张发票中选 Y 张，使总金额 >= Z 且尽可能接近 Z。
算法：排序 + 贪心 + 交换，时间复杂度 O(X log X) + O(R·X·Y)，R 为交换轮数。
"""
from .api import (
    DEFAULT_CONFIG,
    Invoice,
    SelectResult,
    SolverConfig,
    select_invoices,
    invoice_from_value,
)
from .solver import solve

__all__ = [
    "select_invoices",
    "solve",
    "Invoice",
    "SelectResult",
    "SolverConfig",
    "DEFAULT_CONFIG",
    "invoice_from_value",
]
__version__ = "0.1.0"

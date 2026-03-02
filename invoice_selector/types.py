# -*- coding: utf-8 -*-
"""
发票凑单内核 - 数据模型与类型定义
供产品层直接使用或序列化。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


@dataclass(frozen=True)
class Invoice:
    """单张发票（不可变，便于哈希与缓存）"""

    id: str
    """业务主键，如发票号码"""
    amount: float
    """面额，正数，建议精确到小数点后 2 位"""
    extra: Optional[dict] = None
    """扩展字段，产品层可存原始行数据"""

    def __post_init__(self) -> None:
        if self.amount <= 0:
            raise ValueError("发票面额须为正数")

    def amount_cents(self) -> int:
        """面额转为分（整数），避免浮点误差"""
        return round(self.amount * 100)


@dataclass
class SelectResult:
    """凑单结果（内核输出）"""

    selected: List[Invoice]
    """选中的发票列表"""
    total_amount: float
    """选中发票总金额"""
    target: float
    """目标金额 Z"""
    gap: float
    """超出目标的金额，即 total_amount - target（>=0）"""
    selected_ids: List[str] = field(default_factory=list)
    """选中发票的 id 列表，便于产品层按 id 回表"""
    iterations: int = 0
    """交换改进轮数（调试/监控用）"""
    meta: Optional[dict] = None
    """扩展信息：耗时、算法名等"""

    def __post_init__(self) -> None:
        if not self.selected_ids and self.selected:
            self.selected_ids = [inv.id for inv in self.selected]

    def is_feasible(self) -> bool:
        """是否满足 >= Z"""
        return self.total_amount >= self.target


def invoice_from_value(id_or_index: Union[str, int], amount: float, **extra: Any) -> Invoice:
    """从 (id/下标, 金额) 构造 Invoice；无 id 时用下标作为 str(id)。"""
    return Invoice(id=str(id_or_index), amount=float(amount), extra=extra if extra else None)

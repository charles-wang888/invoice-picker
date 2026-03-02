# -*- coding: utf-8 -*-
"""
发票凑单内核 - 运行配置
产品层可通过此处或 API 参数覆盖。
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SolverConfig:
    """求解器配置"""

    max_swap_rounds: Optional[int] = None
    """最大交换轮数，None 表示直到无改进"""
    min_improvement: float = 0.01
    """单次交换至少改善的金额（元），过小可提前设为 0 以加速"""
    amount_tolerance: float = 1e-6
    """金额比较容差（浮点）"""
    sort_descending: bool = True
    """True：按面额从大到小，先取大额再往下换；False：从小到大"""
    sort_tie_break_seed: Optional[int] = None
    """排序时同金额的次要键随机种子，不同种子可得到不同组合；None 表示不随机"""

    def with_max_rounds(self, n: int) -> "SolverConfig":
        c = SolverConfig(
            max_swap_rounds=n,
            min_improvement=self.min_improvement,
            amount_tolerance=self.amount_tolerance,
            sort_descending=self.sort_descending,
            sort_tie_break_seed=self.sort_tie_break_seed,
        )
        return c


# 默认配置：适合 1e4 发票、1e3 张、目标 1e6 量级
DEFAULT_CONFIG = SolverConfig(
    max_swap_rounds=500,
    min_improvement=0.01,
    amount_tolerance=1e-6,
    sort_descending=True,
)

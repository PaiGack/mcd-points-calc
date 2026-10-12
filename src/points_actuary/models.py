"""领域模型。

只用标准库 dataclass，不引入第三方依赖，方便任何人都能跑起来。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class LotteryPrize:
    """抽奖奖池里的一个奖品。"""

    name: str
    #: 该奖品在官方渠道可折算的现金价值（元）。未知则为 None，会被保守估计跳过。
    value_cny: Optional[float] = None
    #: 中奖概率，0~1。官方若只给数量/权重，由 planner 归一化后填入。
    probability: float = 0.0
    #: 需要的积分（有些奖池按「抽一次 20 积分」计）。0 表示不额外扣积分。
    points_cost: int = 0
    is_thanks: bool = False  # 是否「谢谢参与 / 未中奖」


@dataclass(frozen=True)
class MallProduct:
    """麦麦商城里的一个可兑换商品。"""

    name: str
    points_price: int
    #: 商品的现金/等价价值（元）。用于算「每积分换回多少钱」。
    value_cny: float
    stock: Optional[int] = None
    category: str = "unknown"
    #: 有效期天数，None 表示不限期。用来判断兑换优先级。
    valid_days: Optional[int] = None


@dataclass(frozen=True)
class Account:
    """积分账户快照。"""

    available_points: int
    expiring_points: int = 0
    expiring_days: int = 0  # 还有多少天到期
    total_points: int = 0

    @property
    def points_at_risk(self) -> int:
        """真正有到期风险的积分：不超过可用积分。"""
        return min(self.available_points, self.expiring_points)


@dataclass
class Verdict:
    """一个「怎么花」方案及其算术结论。"""

    action: str
    label: str
    cost_points: float
    expected_value_cny: float
    note: str = ""
    risk: str = ""

    @property
    def value_per_100_points(self) -> float:
        """每 100 积分的期望回报（元）。跨方案可比的统一尺子。"""
        if self.cost_points <= 0:
            return 0.0
        return self.expected_value_cny / self.cost_points * 100


@dataclass
class Report:
    """最终给用户看的完整报告。"""

    account: Account
    verdicts: list[Verdict] = field(default_factory=list)
    best: Optional[Verdict] = None
    warnings: list[str] = field(default_factory=list)

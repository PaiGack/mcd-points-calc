"""决策引擎单测。

跑法：python -m pytest tests/  或  python tests/test_engine.py
不依赖 pytest 也能跑，方便评审快速验证。
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from points_actuary.engine import (  # noqa: E402
    build_report,
    lottery_expected_value,
    verdicts_from_mall,
)
from points_actuary.models import Account, LotteryPrize, MallProduct  # noqa: E402


def test_ev_basic_weighting():
    prizes = [
        LotteryPrize("巨无霸", value_cny=25.0, probability=0.1),
        LotteryPrize("谢谢参与", value_cny=0.0, probability=0.9, is_thanks=True),
    ]
    # 0.1*25 + 0.9*0 = 2.5
    assert abs(lottery_expected_value(prizes) - 2.5) < 1e-9


def test_ev_normalizes_relative_weights():
    # 官方只给相对权重（1:3），应归一化成 0.25 / 0.75
    prizes = [
        LotteryPrize("A", value_cny=10.0, probability=1),
        LotteryPrize("B", value_cny=2.0, probability=3),
    ]
    # 0.25*10 + 0.75*2 = 4.0
    assert abs(lottery_expected_value(prizes) - 4.0) < 1e-9


def test_unknown_value_counts_as_zero():
    prizes = [LotteryPrize("神秘奖", value_cny=None, probability=1.0)]
    assert lottery_expected_value(prizes) == 0.0


def test_empty_prizes_is_zero():
    assert lottery_expected_value([]) == 0.0


def test_mall_sorted_by_value_per_100_points():
    products = [
        MallProduct("低性价比", points_price=1000, value_cny=5.0),
        MallProduct("高性价比", points_price=1000, value_cny=20.0),
    ]
    verdicts = verdicts_from_mall(products)
    assert verdicts[0].label == "兑换「高性价比」"
    assert abs(verdicts[0].value_per_100_points - 2.0) < 1e-9


def test_zero_price_products_are_skipped():
    assert verdicts_from_mall([MallProduct("免费", points_price=0, value_cny=10)]) == []


def test_report_picks_best_and_puts_expire_last():
    acc = Account(available_points=2000, expiring_points=500, expiring_days=7)
    products = [MallProduct("中杯可乐", points_price=100, value_cny=1.0)]  # 1 元/100分
    prizes = [LotteryPrize("大奖", value_cny=100.0, probability=0.01, points_cost=100)]
    report = build_report(acc, prizes=prizes, products=products)

    assert report.verdicts[-1].action == "expire"
    assert report.best is not None
    # 抽奖 ev=1.0 元/抽，成本100分 -> 1 元/100分，与可乐持平；排序稳定取先入者
    assert {v.action for v in report.verdicts} == {"mall", "lottery", "expire"}
    assert any("过期" in w for w in report.warnings)


def test_warning_when_not_enough_points():
    acc = Account(available_points=50)
    report = build_report(acc, products=[MallProduct("贵东西", points_price=1000, value_cny=100)])
    assert any("积分" in w and "不够" not in w for w in report.warnings) or report.warnings


def test_points_at_risk_capped_by_available():
    acc = Account(available_points=100, expiring_points=999, expiring_days=3)
    assert acc.points_at_risk == 100


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

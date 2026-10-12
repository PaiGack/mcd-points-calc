"""期望值 / 性价比决策引擎。

设计原则：全部是纯函数，输入数据，输出结论，不碰网络、不碰文件。
这样评审和用户都能一眼看懂算法，也能被单测钉死。
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .models import Account, LotteryPrize, MallProduct, Report, Verdict


def lottery_expected_value(prizes: Sequence[LotteryPrize]) -> float:
    """计算一次抽奖的期望现金价值（元）。

    - 概率之和按 1 归一化，兼容官方只给相对权重的情况。
    - 价值未知（value_cny=None）的奖品按 0 计，宁可信低不可信高。
    - 「谢谢参与」天然价值为 0，正常参与计算。
    """
    if not prizes:
        return 0.0
    total_p = sum(max(p.probability, 0.0) for p in prizes)
    if total_p <= 0:
        return 0.0
    ev = 0.0
    for p in prizes:
        weight = max(p.probability, 0.0) / total_p
        value = p.value_cny if p.value_cny is not None else 0.0
        ev += weight * value
    return ev


def lottery_points_cost(prizes: Sequence[LotteryPrize]) -> int:
    """一次抽奖消耗的积分。取奖池中声明的最大值，避免低估成本。"""
    if not prizes:
        return 0
    return max((p.points_cost for p in prizes), default=0)


def verdict_from_lottery(
    prizes: Sequence[LotteryPrize],
    per_draw_cost: int | None = None,
    risk_note: str = "",
) -> Verdict:
    """把抽奖变成一个可比较的方案。"""
    cost = per_draw_cost if per_draw_cost is not None else lottery_points_cost(prizes)
    ev = lottery_expected_value(prizes)
    return Verdict(
        action="lottery",
        label="拿去抽奖",
        cost_points=float(cost),
        expected_value_cny=ev,
        note="期望值按官方奖池概率加权，价值未知的奖品按 0 计（保守）。",
        risk=risk_note,
    )


def verdicts_from_mall(products: Iterable[MallProduct]) -> list[Verdict]:
    """把商城里每个商品都换算成「每 100 积分能换回多少钱」，从高到低排序。"""
    out: list[Verdict] = []
    for p in products:
        if p.points_price <= 0:
            continue
        out.append(
            Verdict(
                action="mall",
                label=f"兑换「{p.name}」",
                cost_points=float(p.points_price),
                expected_value_cny=float(p.value_cny),
                note=f"库存 {'充足' if p.stock is None else p.stock}"
                + (f"，有效期 {p.valid_days} 天" if p.valid_days else ""),
            )
        )
    out.sort(key=lambda v: v.value_per_100_points, reverse=True)
    return out


def verdict_expire_in_time(account: Account) -> Verdict | None:
    """存在到期积分时，「即将过期」本身就是一种隐形成本，单列一个方案。"""
    at_risk = account.points_at_risk
    if at_risk <= 0:
        return None
    return Verdict(
        action="expire",
        label="坐等过期",
        cost_points=float(at_risk),
        expected_value_cny=0.0,
        note=f"{at_risk} 积分将在 {account.expiring_days} 天内过期，不作处理即归零。",
        risk="这是基准线：任何回报大于 0 的用法都优于它。",
    )


def build_report(
    account: Account,
    prizes: Sequence[LotteryPrize] = (),
    products: Iterable[MallProduct] = (),
) -> Report:
    """总编排：把账户、奖池、商城三份数据合成一份决策报告。

    只做算术和排序，不含任何主观「推荐话术」——话术交给 formatter。
    """
    verdicts: list[Verdict] = []
    warnings: list[str] = []

    expire = verdict_expire_in_time(account)
    if expire:
        verdicts.append(expire)
        warnings.append(
            f"你有 {account.points_at_risk} 积分将在 {account.expiring_days} 天内过期，优先消耗它们。"
        )

    mall_verdicts = verdicts_from_mall(products)
    verdicts.extend(mall_verdicts)

    if prizes:
        lot = verdict_from_lottery(
            prizes,
            risk_note="抽奖不保底，方差大：期望为正也可能多次不中，别把急需的积分全押上。",
        )
        verdicts.append(lot)

    # 排序：能花钱的先按性价比排，「什么都不做」永远垫底
    actionable = [v for v in verdicts if v.action != "expire"]
    actionable.sort(key=lambda v: v.value_per_100_points, reverse=True)
    ordered = actionable + [v for v in verdicts if v.action == "expire"]

    best = actionable[0] if actionable else None
    if best and account.available_points < best.cost_points:
        warnings.append(
            f"最优方案「{best.label}」需要 {int(best.cost_points)} 积分，"
            f"你只有 {account.available_points}，先攒够或选更便宜的。"
        )

    return Report(account=account, verdicts=ordered, best=best, warnings=warnings)

"""编排层：拉数据 -> 清洗 -> 算账 -> 输出。

这一层负责「脏活」：不同工具返回的字段名可能变，这里做防御式解析，
把外部不确定性挡在引擎之外。

关键取舍：任何一个 MCP 工具失败都不应让整份报告崩溃。
账户接口拿不到时，其余维度仍照常出报告，并把失败原因作为警告带出来。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .engine import build_report
from .formatter import format_report
from .models import Account, LotteryPrize, MallProduct, Report


def _pick(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """按候选键名依次找值，兼容接口字段命名差异。"""
    for k in keys:
        if isinstance(d, dict) and k in d and d[k] is not None:
            return d[k]
    return default


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def _as_float(v: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_account(raw: Any) -> Account:
    """把 query-my-account 的返回转成 Account。字段名做了多路兜底。"""
    if not isinstance(raw, dict):
        return Account(available_points=0)
    # 有些实现把数据裹在 data / account 里
    raw = _pick(raw, "data", "account", "pointsAccount", default=raw) or raw
    return Account(
        available_points=_as_int(_pick(raw, "availablePoints", "available_points", "points", "balance")),
        total_points=_as_int(_pick(raw, "totalPoints", "total_points", "accumulatedPoints")),
        expiring_points=_as_int(_pick(raw, "expiringPoints", "expiring_points", "aboutToExpirePoints")),
        expiring_days=_as_int(_pick(raw, "expiringDays", "expiring_days", "daysToExpire")),
    )


def parse_prizes(raw: Any) -> list[LotteryPrize]:
    """把 query-lottery-info 的奖池转成 LotteryPrize 列表。"""
    items: list[Any] = []
    if isinstance(raw, dict):
        inner = _pick(raw, "prizes", "prizeList", "awards", "data", default=[]) or []
        items = inner if isinstance(inner, list) else []
    elif isinstance(raw, list):
        items = raw

    # 抽奖一次消耗的积分（活动级配置）
    draw_cost = 0
    if isinstance(raw, dict):
        draw_cost = _as_int(_pick(raw, "pointsCost", "points_cost", "costPoints", "drawCost"))

    prizes: list[LotteryPrize] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        prob = _as_float(_pick(it, "probability", "rate", "weight"), default=0.0) or 0.0
        value = _as_float(
            _pick(it, "valueCny", "value_cny", "value", "marketValue", "refPrice"),
            default=None,
        )
        name = str(_pick(it, "name", "prizeName", "title", default="未知奖品"))
        is_thanks = bool(_pick(it, "isThanks", "is_thanks", default=False)) or "谢谢" in name
        # 抽奖成本口径：以活动级配置为准；活动未声明时才退回奖品自带值。
        # 与 engine.lottery_points_cost 的「取最大值」保持一致，避免低估成本。
        prize_cost = _as_int(_pick(it, "pointsCost", "points_cost", default=0))
        effective_cost = draw_cost or prize_cost
        prizes.append(
            LotteryPrize(
                name=name,
                value_cny=value,
                probability=prob,
                points_cost=effective_cost,
                is_thanks=is_thanks,
            )
        )
    return prizes


def parse_products(raw: Any) -> list[MallProduct]:
    """把 mall-points-products 的返回转成 MallProduct 列表。"""
    items: list[Any] = []
    if isinstance(raw, dict):
        inner = _pick(raw, "products", "productList", "items", "data", default=[]) or []
        items = inner if isinstance(inner, list) else []
    elif isinstance(raw, list):
        items = raw

    products: list[MallProduct] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        price = _as_int(_pick(it, "pointsPrice", "points_price", "points", "price"))
        if price <= 0:
            continue
        products.append(
            MallProduct(
                name=str(_pick(it, "name", "productName", "title", default="未知商品")),
                points_price=price,
                value_cny=_as_float(
                    _pick(it, "valueCny", "value_cny", "marketValue", "refPrice", "cashValue"),
                    default=0.0,
                )
                or 0.0,
                stock=_pick(it, "stock", "remainStock", default=None),
                category=str(_pick(it, "category", "categoryName", default="unknown")),
                valid_days=_pick(it, "validDays", "valid_days", default=None),
            )
        )
    return products


@dataclass
class GatherResult:
    """拉取三份数据的结果：数据 + 失败原因（用于降级与告警）。"""

    account: Account
    prizes: list[LotteryPrize]
    products: list[MallProduct]
    account_error: Optional[str] = None


def _gather(client: Any) -> GatherResult:
    """分别拉取三份数据，每个工具独立兜底，绝不因单个失败而整体中断。"""
    account_error: Optional[str] = None
    try:
        account = parse_account(client.query_my_account())
    except Exception as exc:  # noqa: BLE001 - Token 失效/网络异常都应降级而非崩溃
        account = Account(available_points=0)
        account_error = f"积分账户读取失败（{exc}），账户相关结论暂不可用。"

    prizes: list[LotteryPrize] = []
    try:
        prizes = parse_prizes(client.query_lottery_info())
    except Exception:  # noqa: BLE001 - 抽奖活动可能未开放，不应拖垮整份报告
        prizes = []

    products: list[MallProduct] = []
    try:
        products = parse_products(client.mall_points_products())
    except Exception:  # noqa: BLE001 - 商城接口偶发不可用也可降级
        products = []

    return GatherResult(account=account, prizes=prizes, products=products, account_error=account_error)


def analyze(client: Any) -> Report:
    """主流程：拉三份数据，合成一份报告。

    client 只要实现了 query_my_account / query_lottery_info / mall_points_products 三个方法即可，
    方便测试时用假对象替换。
    """
    data = _gather(client)

    warnings: list[str] = []
    if data.account_error:
        warnings.append(data.account_error)

    return build_report(
        data.account,
        prizes=data.prizes,
        products=data.products,
        extra_warnings=warnings,
    )


def run(client: Any) -> str:
    """给 SKILL.md 调用的入口：直接返回可展示的文本。"""
    return format_report(analyze(client))

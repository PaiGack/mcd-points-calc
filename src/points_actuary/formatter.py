"""把算术结论翻译成「人话」。

分开写的原因：数字要严谨，表达要有温度，两者改动的理由不一样。
"""

from __future__ import annotations

from .models import Report, Verdict


def _cny(v: float) -> str:
    return f"¥{v:.2f}"


def format_verdict_line(idx: int, v: Verdict) -> str:
    if v.action == "expire":
        return f"{idx}. ❌ {v.label} —— 白丢 {int(v.cost_points)} 分"
    unit = f"{_cny(v.value_per_100_points)}/100分"
    return (
        f"{idx}. {v.label} —— 花 {int(v.cost_points)} 分，"
        f"期望回本 {_cny(v.expected_value_cny)}（{unit}）"
    )


def format_report(report: Report) -> str:
    acc = report.account
    lines: list[str] = []

    lines.append("🍟 麦麦积分精算报告")
    lines.append("")
    lines.append(
        f"账户：可用 {acc.available_points} 分"
        + (f"，其中 {acc.points_at_risk} 分将在 {acc.expiring_days} 天内过期" if acc.points_at_risk else "")
    )
    lines.append("")

    if report.verdicts:
        lines.append("📊 各种花法的性价比（按每 100 积分换回的期望价值排序）：")
        for i, v in enumerate(report.verdicts, 1):
            lines.append(format_verdict_line(i, v))
        lines.append("")

    if report.best:
        lines.append(f"✅ 建议：{report.best.label}")
        if report.best.note:
            lines.append(f"   理由：{report.best.note}")
        if report.best.risk:
            lines.append(f"   风险：{report.best.risk}")
    else:
        lines.append("✅ 暂无可用积分或可兑换项，先攒着。")

    if report.warnings:
        lines.append("")
        lines.append("⚠️ 注意：")
        for w in report.warnings:
            lines.append(f"   - {w}")

    lines.append("")
    lines.append("（数值基于官方实时接口，价值折算为估算，仅供参考。）")
    return "\n".join(lines)

"""命令行入口：python -m points_actuary

有 MCP Token 时走真实接口；没有时用 --demo 跑一份内置样例，
方便任何人在没有 Token 的情况下也能看到产品长什么样。
"""

from __future__ import annotations

import argparse
import sys

from .formatter import format_report
from .planner import analyze


class _DemoClient:
    """内置样例数据，用于离线演示。"""

    def query_my_account(self):
        return {"availablePoints": 680, "totalPoints": 3200, "expiringPoints": 300, "expiringDays": 9}

    def query_lottery_info(self):
        return {
            "pointsCost": 50,
            "prizes": [
                {"name": "巨无霸免费券", "valueCny": 25.0, "weight": 1},
                {"name": "中薯免费券", "valueCny": 12.0, "weight": 4},
                {"name": "麦旋风立减3元", "valueCny": 3.0, "weight": 10},
                {"name": "谢谢参与", "valueCny": 0.0, "weight": 85},
            ],
        }

    def mall_points_products(self):
        return {
            "products": [
                {"name": "中杯可乐", "pointsPrice": 300, "valueCny": 9.0, "validDays": 30},
                {"name": "麦乐鸡5块", "pointsPrice": 500, "valueCny": 13.5, "validDays": 30},
                {"name": "巨无霸", "pointsPrice": 900, "valueCny": 25.0, "validDays": 30},
            ]
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="points_actuary", description="麦麦积分精算师")
    parser.add_argument("--demo", action="store_true", help="用内置样例数据演示，不连网")
    args = parser.parse_args(argv)

    if args.demo:
        client = _DemoClient()
    else:
        from .mcp_client import McDonaldMCPClient

        client = McDonaldMCPClient()

    print(format_report(analyze(client)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

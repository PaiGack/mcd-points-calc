"""麦当劳 MCP 客户端（Streamable HTTP）。

只依赖标准库 urllib，不装任何包就能连。Token 一律从环境变量读，
绝不落盘、绝不写进代码。限流 600 次/分钟，这里做了个轻量的间隔控制。
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

MCP_ENDPOINT = "https://mcp.mcd.cn"
TOKEN_ENV = "MCD_MCP_TOKEN"
#: MCP 协议版本。官方文档未锁定版本，允许通过环境变量跟随服务端更新，
#: 默认值仅为兜底，不代表官方固定要求。
PROTOCOL_VERSION_ENV = "MCD_MCP_PROTOCOL_VERSION"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
_MIN_INTERVAL = 0.12  # 秒，约 500 次/分钟，留出安全余量


class MCPError(RuntimeError):
    pass


class McDonaldMCPClient:
    """极简 MCP 客户端：只实现本项目需要的 initialize / tools-call 两步。"""

    def __init__(self, token: Optional[str] = None, endpoint: str = MCP_ENDPOINT) -> None:
        self.token = token or os.environ.get(TOKEN_ENV, "")
        if not self.token:
            raise MCPError(
                f"缺少 MCP Token。请先设置环境变量 {TOKEN_ENV}，"
                "Token 申请见 https://open.mcd.cn/mcp"
            )
        self.endpoint = endpoint.rstrip("/")
        self.protocol_version = (
            os.environ.get(PROTOCOL_VERSION_ENV, "").strip() or DEFAULT_PROTOCOL_VERSION
        )
        self._last_call = 0.0
        self._session_id: Optional[str] = None
        self._req_id = 0

    # ---- 底层传输 ----

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _throttle(self) -> None:
        delta = time.time() - self._last_call
        if delta < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - delta)
        self._last_call = time.time()

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._throttle()
        self._req_id += 1
        payload = {"jsonrpc": "2.0", "id": self._req_id, **payload}
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self._session_id = sid
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise MCPError("MCP Token 无效或已过期（401），请重新申请。") from e
            if e.code == 429:
                raise MCPError("触发限流（429），请降低调用频率后再试。") from e
            raise MCPError(f"MCP 请求失败：HTTP {e.code}") from e
        except urllib.error.URLError as e:
            raise MCPError(f"无法连接 MCP 服务：{e.reason}") from e
        return _parse_body(body)

    def initialize(self) -> dict[str, Any]:
        return self._post(
            {
                "method": "initialize",
                "params": {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {},
                    "clientInfo": {"name": "mcd-points-actuary", "version": "0.1.0"},
                },
            }
        )

    # ---- 业务工具 ----

    def call_tool(self, name: str, arguments: Optional[dict[str, Any]] = None) -> Any:
        if self._session_id is None:
            self.initialize()
        result = self._post(
            {"method": "tools/call", "params": {"name": name, "arguments": arguments or {}}}
        )
        return _unwrap(result)

    # 下面几个是「精算师」实际会用到的工具，包一层让 planner 更好读
    def query_my_account(self) -> Any:
        """我的积分账户：可用 / 累计 / 冻结 / 即将过期。"""
        return self.call_tool("query-my-account")

    def query_lottery_info(self) -> Any:
        """积分抽奖活动信息：奖池、消耗规则、可用次数。"""
        return self.call_tool("query-lottery-info")

    def mall_points_products(self, **kw: Any) -> Any:
        """麦麦商城可兑换商品列表。"""
        return self.call_tool("mall-points-products", kw or None)

    def mall_product_detail(self, **kw: Any) -> Any:
        """商城商品详情，含有效期与库存。"""
        return self.call_tool("mall-product-detail", kw or None)

    def now_time_info(self) -> Any:
        """当前时间，用于算积分到期天数。"""
        return self.call_tool("now-time-info")


def _parse_body(body: str) -> dict[str, Any]:
    """兼容 SSE 与纯 JSON 两种响应形态。"""
    body = body.strip()
    if not body:
        return {}
    if body.startswith("{"):
        return json.loads(body)
    for line in body.splitlines():
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if chunk and chunk != "[DONE]":
                return json.loads(chunk)
    return {}


def _unwrap(resp: dict[str, Any]) -> Any:
    """剥掉 JSON-RPC 外壳，尽量交给调用方结构化数据。"""
    if "error" in resp:
        raise MCPError(f"MCP 工具调用出错：{resp['error']}")
    result = resp.get("result", resp)
    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list):
        texts = [c.get("text", "") for c in content if isinstance(c, dict)]
        joined = "\n".join(t for t in texts if t)
        try:
            return json.loads(joined)
        except (json.JSONDecodeError, TypeError):
            return joined
    return result

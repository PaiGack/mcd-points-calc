# MCP 集成说明

## 一、接入的 Server

| 项 | 值 |
|---|---|
| Server 名称 | `mcd-mcp` |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权 | 请求头 `Authorization: Bearer ${MCD_MCP_TOKEN}` |
| 限流 | 600 次/分钟（超限返回 429） |
| 配置示例 | [`mcp-config.example.json`](./mcp-config.example.json) |

本 Skill 使用麦当劳中国官方托管的远程 MCP Server，未自建、未代理任何服务。

## 二、使用的 Tool 及其角色

| Tool | 用途 | 在本项目中的角色 |
|---|---|---|
| `query-my-account` | 查询积分账户：可用 / 累计 / 冻结 / 即将过期积分 | **输入①**：确定「有多少分可花」与「多少分有到期风险」 |
| `query-lottery-info` | 查询积分抽奖活动：奖池、奖品权重、单次消耗规则 | **输入②**：算抽奖的期望值，是「抽奖值不值」的唯一依据 |
| `mall-points-products` | 查询麦麦商城可积分兑换的商品与所需积分 | **输入③**：算每个商品的「每 100 积分回本」，形成兑换候选集 |
| `now-time-info` | 返回当前完整时间 | **辅助**：对齐时间基准，判断积分到期紧迫度 |

> 设计取舍：本项目**只读不写**。刻意不调用 `draw-lottery` / `mall-create-order`
> 等有副作用的工具 —— 精算师负责「算清楚」，把「花不花」的决定权留给用户。

## 三、真实调用流程

```text
用户提问「我积分怎么花最划算？」
        │
        ▼
SKILL.md 识别意图，编排工具调用
        │
        ├─→ now-time-info            （拿当前时间，建立时间基准）
        ├─→ query-my-account         （账户快照）
        ├─→ query-lottery-info       （奖池与消耗规则）
        └─→ mall-points-products     （可兑换商品列表）
        │
        ▼
src/points_actuary/planner.py
   parse_account / parse_prizes / parse_products
     └─ 防御式字段解析（多键名兜底，隔离接口差异）
        │
        ▼
src/points_actuary/engine.py        （纯函数，无副作用）
   ├─ lottery_expected_value()   Σ(概率×价值)，权重归一化
   ├─ verdicts_from_mall()        价值 ÷ 积分 × 100，按性价比排序
   └─ verdict_expire_in_time()    「坐等过期」= 0 回报基准线
        │
        ▼
src/points_actuary/formatter.py     （翻译成人话）
        │
        ▼
输出：排序后的方案表 + 建议 + 风险提示 + 到期警告
```

### 失败兜底策略

| 场景 | 处理 |
|---|---|
| `query-my-account` 报错（Token 失效/网络异常） | `planner._gather` 捕获异常，账户降级为「可用 0 分」，**其余维度照常出报告**；失败原因转为可读警告展示给用户 |
| `query-lottery-info` 报错（活动未开放） | `planner._gather` 捕获异常，抽奖维度置空，其余照常出报告 |
| `mall-points-products` 报错 | 同上，降级为「只有抽奖 vs 过期」的对比 |
| 抽奖成本为 0 或缺失 | 不静默垫底：`engine.lottery_data_warnings` 输出可读提示，说明「性价比 0 不代表不划算」 |
| 奖池价值全未知 | 输出「期望值恒为 0，结论仅供占位」提示 |
| 401 Token 失效 | `mcp_client` 抛出可读错误：「MCP Token 无效或已过期，请重新申请」 |
| 429 触发限流 | 客户端内置 ≥0.12s 调用间隔（约 500 次/分钟），并抛可读错误 |
| 接口字段名变化 | `planner` 层多键名兜底解析，不让字段差异穿透到引擎 |
| 协议版本变更 | `mcp_client` 默认 `2024-11-05`，可用环境变量 `MCD_MCP_PROTOCOL_VERSION` 覆盖（官方未锁定版本） |
| 奖品价值未知 | 保守按 0 计，宁可信低不可信高 |

## 四、业务价值

1. **把决策从玄学变成算术**：积分抽奖长期是「黑箱」，本项目用期望值把它拆开，
   用户第一次能看见「抽一次到底值多少钱」。
2. **统一的比较尺子**：抽奖、兑换、过期三种形态本不可比，
   折算成「每 100 积分回本多少元」后可以同表排序。
3. **真实的痛点**：麦当劳积分有有效期，「即将过期」是高频焦虑；
   本项目把到期积分单列为风险项，并在建议中优先消耗。
4. **只读、可验证、可复现**：算法是三个纯函数，配单测；
   离线 `--demo` 不需要 Token 就能跑，任何人都能验证结论怎么来的。
5. **零依赖零门槛**：只用 Python 标准库，评审 `git clone` 后一条命令即可运行。

## 五、安全与合规

- MCP Token **仅从环境变量 `MCD_MCP_TOKEN` 读取**，不写入代码、不落盘、不打印。
- 仓库内配置示例只用环境变量占位符 `${MCD_MCP_TOKEN}`。
- 不采集、不存储、不上传任何用户个人信息；所有请求实时发生、用完即弃。
- 仅按「个人非商业用途」连接官方麦当劳 MCP 服务，遵守其《使用条款》与《MCP 服务规则》。

# 🍟 麦麦积分精算师 (mcd-points-calc)

> 把「积分该抽奖还是该兑换」从**玄学**变成**算术**。

麦当劳会员的积分只有三条路：抽奖、兑换商城商品、放过期。官方从不告诉你哪条划算。
**这个 Skill 把它算清楚** —— 把每种花法都换算成同一把尺子：**每 100 积分，能换回多少元**。

```
🍟 麦麦积分精算报告

账户：可用 680 分，其中 300 分将在 9 天内过期

📊 各种花法的性价比（按每 100 积分换回的期望价值排序）：
1. 兑换「中杯可乐」 —— 花 300 分，期望回本 ¥9.00（¥3.00/100分）
2. 兑换「巨无霸」 —— 花 900 分，期望回本 ¥25.00（¥2.78/100分）
3. 兑换「麦乐鸡5块」 —— 花 500 分，期望回本 ¥13.50（¥2.70/100分）
4. 拿去抽奖 —— 花 50 分，期望回本 ¥1.03（¥2.06/100分）
5. ❌ 坐等过期 —— 白丢 300 分

✅ 建议：兑换「中杯可乐」
   理由：库存 充足，有效期 30 天

⚠️ 注意：
   - 你有 300 积分将在 9 天内过期，优先消耗它们。
```

---

## 为什么值得做

| 痛点 | 现状 | 精算师怎么解 |
|---|---|---|
| 积分要过期了 | 慌，随便换点什么 | 精确算出「即将过期多少分、还剩几天」，优先消耗 |
| 抽奖很诱人 | 只看到「巨无霸免费券」，看不到概率 | 用奖池权重算**期望值**，告诉你抽一次真值多少钱 |
| 商城商品太多 | 攒了半天换了个不划算的 | 每个商品都标出「每 100 积分回本多少」，一眼排序 |
| 价值无法比较 | 抽奖 vs 兑换，没法比 | 统一折算成元，同一把尺子排序 |

## 目标用户

- 手里攒着几百到几千积分、纠结怎么花的**麦当劳会员**
- 积分快到期（麦当劳积分有有效期）却发现毫无对策的人
- 想抽奖但怕「沉没积分」的谨慎型用户
- 喜欢用数据做决定的理性派

## 安装

无需任何第三方依赖，只要有 Python 3.9+：

```bash
git clone <本仓库地址>
cd mcd-points-calc
# 可选：安装为命令
pip install -e .
```

## 配置 MCP Token

1. 访问 <https://open.mcd.cn/mcp>，手机号登录
2. 点右上角「控制台」→「激活」，复制 MCP Token
3. 设置环境变量（**Token 绝不写进代码或提交到仓库**）：

```bash
export MCD_MCP_TOKEN="你的 Token"
```

4. 在你的 MCP Client（WorkBuddy / Cursor / Cherry Studio 等）里导入 [`mcp-config.example.json`](./mcp-config.example.json)。

> [`mcp-config.example.json`](./mcp-config.example.json) 是**脱敏**的配置模板，只含环境变量占位符 `${MCD_MCP_TOKEN}`，
> 不含任何真实 Token。导入后请把占位符替换为你自己的 Token（或在客户端里读取同名环境变量）。
> 该文件名与格式为大赛要求的**标准命名**，请勿改名。

## 使用示例

**离线演示**（无需 Token，立刻看到产品形态）：

```bash
PYTHONPATH=src python -m points_actuary --demo
```

**真实账户**：

```bash
PYTHONPATH=src python -m points_actuary
```

**作为 Skill 被 AI 调用**：把 [`SKILL.md`](./SKILL.md) 放进你的 Skill 目录，AI 会在用户问「积分怎么花划算」时自动编排 MCP 工具并调用本项目引擎。详见 [`SKILL.md`](./SKILL.md)。

## 算法说明（可验证）

核心是三个纯函数，见 [`src/points_actuary/engine.py`](./src/points_actuary/engine.py)：

1. **抽奖期望值** `E = Σ(pᵢ × vᵢ)`，概率按奖池权重归一化；未知价值保守按 0 计
2. **商城性价比** `每100积分回本 = 商品价值 ÷ 所需积分 × 100`
3. **过期基准线**：坐等过期回报恒为 0，任何正回报方案都优于它

跑单测：

```bash
python tests/test_engine.py
# 或 python -m pytest tests/
```

## 项目结构

```
.
├── SKILL.md                    # Skill 说明书（AI 读这个）
├── README.md                   # 你正在看的
├── MCP_INTEGRATION.md          # 用了哪些 MCP Tool、怎么调
├── CONTEST_DECLARATION.md      # 参赛声明（官方原文，未改动）
├── mcp-config.example.json     # 脱敏配置示例（大赛标准命名）
├── workbuddy.md                # WorkBuddy 对话上下文（WorkBuddy 专项奖励要求）
├── src/points_actuary/
│   ├── engine.py               # 期望值/性价比算法（纯函数）
│   ├── models.py               # 领域模型
│   ├── mcp_client.py           # 麦当劳 MCP 客户端（Streamable HTTP）
│   ├── planner.py              # 编排：拉数据 → 算账
│   ├── formatter.py            # 输出成人话
│   └── __main__.py             # CLI 入口
└── tests/test_engine.py        # 单测
```

## 边界与免责

- 奖品价值为**估算的市场参考价**，非官方定价；结果**仅供参考**。
- 抽奖不保底：期望为正也可能连抽不中，报告会明确提示风险。
- 餐品、价格、库存以麦当劳官方渠道实时结果为准。
- **降级不崩溃**：任一 MCP 工具失败（含账户接口 Token 失效）都不会中断报告，
  失败维度会被跳过并以可读警告提示，其余结论照常给出。
- 本项目为 2026 麦当劳程序员节创意开发大赛参赛作品，非麦当劳官方产品。

## License

MIT

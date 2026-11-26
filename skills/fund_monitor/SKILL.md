---
name: fund_monitor
description: 基金「回撤吸筹 + 移动止盈」每日监控：拉净值、算回撤/加仓/止盈、渲染信号图（浅色+深色）、邮件推送、Windows 定时唤醒。支持 fetch/backtest/yearly/signal/notify/buy/sell。
user-invocable: true
---

# 基金每日信号监控（回撤吸筹 + 移动止盈）

一套自包含的 Python 工具：每天按「基线定投 + 回撤分档加仓」给买入信号，按「收益≥15% 且高点回撤≥5%」给移动止盈信号，渲染成图发邮件，并用 Windows 计划任务在固定时点唤醒发送。

## 0. 何时用
- 用户说「基金定投 / 回撤加仓 / 止盈 / 每日信号 / 基金提醒」。
- 需要跑回测、看分年收益、记录持仓买卖、配置邮件推送。

## 1. 依赖
- **Python 3.12**（DSH 内置：`C:\Users\24962\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`）
- 首次需 `pip install matplotlib`（画饼图）；`pandas` / `Pillow` 已内置
- 网络（东方财富天天基金，无需 API Key）
- 调度（可选）：Windows 计划任务 + 休眠唤醒（S4）

## 2. 文件结构
```
<工作目录>/
├── monitor.py            # 主脚本（reference/monitor.py 是模板）
├── config.json           # 参数（基金、金额、档位、止盈、通知）
├── holdings.json         # 持仓 {code: {shares, cost, peak_nav}}
└── cache/*.csv           # 净值缓存（自动拉取）
```
首次使用：把 `reference/monitor.py`、`reference/config.example.json`（改名 `config.json`）、`reference/holdings.example.json`（改名 `holdings.json`）复制到工作目录。

## 3. 命令
```powershell
$py = 'C:\Users\24962\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
cd <工作目录>

& $py monitor.py fetch         # 拉净值缓存
& $py monitor.py backtest      # 5 年回测（对比纯定投）
& $py monitor.py yearly        # 分年 TWR + 区间 IRR
& $py monitor.py signal        # 当日信号（含盘中预估、持仓、卖出建议）
& $py monitor.py notify        # 信号 + 邮件推送（3 张图：深色信号 / 深色日历 / 浅色日历）
& $py monitor.py buy 006131 1000   # 记录买入（金额）
& $py monitor.py sell 006131 500   # 记录卖出（份额）

# 可选参数
--estimate   # 普通仓 + 预估加仓（盘中估算净值重算回撤）
--confirm    # 普通仓 + 确认加仓（按实际净值）
--normal     # 只提示普通仓
--force      # 绕过去重（仅测试用）
--skip-if-dsh  # DSH 在运行则跳过（历史参数，现以去重锁为主）
```

## 4. 配置字段（config.json）
| 字段 | 说明 |
|---|---|
| `daily_amount` | 默认每日基线（被 `strategy.base` 覆盖） |
| `lookback_days` | 回撤回看天数（默认 90） |
| `max_buy` | 单日单基金买入上限 |
| `total_budget` | 单基金累计投入上限（0=不限） |
| `auto_apply` | `true` = 每日 confirm 买入自动登记，待当天净值公布后按实际净值结算进持仓 |
| `holidays` | 节假日列表（`YYYY-MM-DD`），周末+节假日跳过 |
| `take_profit` / `peak_drawdown_sell` | 止盈：收益≥15% 且高点回撤≥5% |
| `smtp_*` | 邮件（授权码非登录密码）；留空则只本地输出 |
| `wechat_webhook` | 企业微信群机器人（可选） |
| `funds[].index` | 跟踪指数 `{secid, name}`，用于盘中预估与分时曲线 |
| `funds[].strategy` | `pyr`（金字塔）/ `dca`（分档）/ `zone`（区间） |

**策略语义**
- `pyr`：回撤≥`entry_dd` 建仓，每再跌 `step` 加 `add`；`sell: normal`。
- `dca`：基线 `base` + 回撤档 `tiers`/`mults`；`max_extra` 封顶加仓；`sell: optimal`。
- 止盈 `optimal`：收益≥15% 且从持有高点回撤≥5% → 卖 2/3 留 1/3；收益≥50% 清底仓。

## 5. 调度（Windows 计划任务，推荐）
7 个时间点：`10:00 / 11:00 / 13:30 / 14:00 / 14:30 / 14:40 / 15:00`（周一至周五）。
- 任务：`monitor.py notify --estimate`（10:00~14:00）或 `--confirm`（14:30~15:00）。
- **必须设 `-WakeToRun`**，否则睡眠中不会执行。
- **去重**：`claim_slot()` 用 10 分钟时段原子锁 + 3 分钟最小间隔，防止唤醒后连发。
- 也可用 DSH `schedule_create` 定时（target=this_session），但需 DSH 常开。

## 6. 已知坑
- **Modern Standby（S0）不能被定时任务唤醒**：必须先 `powercfg /hibernate on`（需管理员），再把空闲设为休眠 S4（`hibernate-timeout-ac 5`），任务才能唤醒。
- **QDII 净值滞后一天**（如标普500 的净值日是 T-1）。
- **`--force` 只用于测试**，会绕过去重。
- 回撤标签口径：`近期回撤(90天)` 用于买入信号；`距历史高点` = 相对累计最高；`最大回撤` = 峰谷最大回撤。
- C 类基金 7 天内赎回收 1.5% 惩罚费，短期别频繁卖。

## 7. 校验
1. `monitor.py fetch` 成功拉到 CSV。
2. `monitor.py signal` 每只基金都有：昨日涨跌、盘中预估、回撤、买入金额、持仓、卖出建议。
3. `monitor.py notify` 邮件含 3 张图（深色信号 / 深色日历 / 浅色日历），日历只显示今天和昨天，饼图为红绿甜甜圈。

## 8. 示例（本机）
工作目录 `E:\uvm_ppt\tools\fund`，配置了 5 只基金 + 7 个 Windows 任务 + 7 个 DSH schedule。

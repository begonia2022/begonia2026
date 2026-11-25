# dsh-plugins

我的 DSH 插件 / skill 仓库（remote：`github.com/begonia2022/begonia2026`）。

## 目录结构

```
.
├── plugins/                 # DSH 插件，每个插件一个子目录
│   ├── dsh-np-ppt/          # 原生 PPT 演示文稿专家插件（PPTD DSL + Python-PPTX 离线编译内核）
│   └── dsh-token-caveman/   # Terse prose 输出风格：更少 token、改风格不改实质
├── skills/                  # DSH skill，每个 skill 一个子目录
│   ├── ocean_ppt/           # 技术学习分享 PPT 制作方法论（科技蓝、代码对比式课件）
│   ├── distilly/            # 同事蒸馏器：把一个人蒸馏成可复用的 DSH skill
│   └── fund_monitor/        # 基金每日信号监控（回撤吸筹 + 移动止盈 + 邮件/定时）
├── examples/                # 可跑样例
│   └── uvm-share/           # ocean_ppt 的 28 页示例（生成器 + 书文本 + deck 输出）
└── README.md
```

## 依赖说明

| 资产 | 依赖 |
|------|------|
| `plugins/dsh-np-ppt` | Node.js；编译 PPTX 需 Python 3.10+（`pyyaml`、`python-pptx`） |
| `skills/ocean_ppt` | 前置依赖 `dsh-np-ppt` 插件；Python 3.10+（`pyyaml` / `python-pptx` / `pdfminer.six`）；可选 LibreOffice Kit 渲染预览 |
| `skills/distilly` | 无（纯 prompt 驱动） |
| `skills/fund_monitor` | Python 3.10+（`pandas` / `Pillow` / `matplotlib`）；邮件推送需 SMTP；定时需 Windows 计划任务 + 休眠唤醒 |

## 安装 / 使用

- **插件**：把 `plugins/<name>/` 链接或安装进 DSH profile（见各插件 README）。本机 `dsh-np-ppt` 已通过 profile 链接到 `E:\uvm_ppt\dsh-np-ppt`。
- **skill**：把 `skills/<name>/` 复制到 `~/.dsh/skills/<name>/`，DSH 会自动发现。
- **示例**：`examples/uvm-share/build_share_deck.py` 生成 `deck.pptd` + `pages/*.page`，再用 `dsh-np-ppt` 编译器导出 PPTX（命令见 `skills/ocean_ppt/SKILL.md` 的「命令」节）。

## 常用命令

```bash
git add -A
git commit -m "说明"
git push
```

> 提交前请设置真实身份：`git config user.name` / `git config user.email`。

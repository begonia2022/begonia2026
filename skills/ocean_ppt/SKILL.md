---
name: ocean_ppt
description: 用 dsh-np-ppt 制作「技术学习分享」PPT（科技蓝风格、代码对比式课件）。含配色规范、页面布局 helper、16px 字号经验、编译/渲染/校验流程与踩坑清单。适用于组内技术分享、技术书章节精读类课件。
user-invocable: true
---

# 技术分享 PPT 制作（dsh-np-ppt · 科技蓝）

把一本技术书/一个主题的章节，做成「组内学习分享」课件：科技蓝封面 + 灰底正文 + 白卡片 + 浅绿代码块，代码用「原书写法 vs 改进写法」对比，每页顶部一句「本页讲」，代码块带文件名与「原书页码」。

---

## 依赖（先装好）
- **dsh-np-ppt 插件**（编译引擎）——本仓库 `plugins/dsh-np-ppt/`，或经 DSH 插件市场安装。
- **Python 3.10+**：需 `pyyaml`、`python-pptx`、`pdfminer.six`（提取 PDF 原文）。
- **LibreOffice Kit**：可选，仅用于渲染预览。

## 0. 何时用
- 用户说「做 PPT / 演示文稿 / 幻灯片」，主题是技术书章节精读、知识点分享（如《UVM实战》factory/callback）。
- 运行环境已有 dsh-np-ppt 插件（PPTD DSL + `compiler/export_pptx.py`）。

## 1. 设计系统（照抄）

### 画布与版心
- 画布 960×540pt。正文页背景 `#ECEFF4`（浅灰）。内容区 `y≈128..496`，页脚规则线 `y=500`。
- 封面单独深蓝：底 `#08101E`、青 `#22D3EE` 竖条/高亮。

### 配色
- 章节主色：蓝 `#2F6FD0`（机制/实现）、青 `#2E8CA6`（callback）、绿 `#2F8F62`（可重用性）。
- 文字层级：`INK #10263D` → `BODY #44586F` → `MUTED #7A8A9E` → `DIM #9AACBF`。
- 卡片白 `#FFFFFF` + 描边 `#D8E1EC`。
- 代码块：浅绿底 `#E6F7EF` + 边框 `#C4E2D3` + 文件名头 `#4B6C86`（偏浅勿过深）+ 圆角 5% + 阴影 0.8。
- **绿色是唯一高亮色，必须「淡、不刺眼」**；不要多种荧光色混用。

### 字号（最重要）
- 全局 `fs(size) = size * 1.26`；正文 `p()` 再 ×1.08；标题 `p(..., raw=True)` 不放大。
- 代码 `code()` 字号 = `fs(size) * 1.20`（codebox 有文件名头时再 ×0.94）。
- **代码正文目标 16px（16号）**：宁可拆页、删冗余注释，也不要用 <12px。
- 每页代码行数上限：满宽 1 块 ≤ 12 行；两列每块 ≤ 5~6 行；三列每块 ≤ 6 行。超了就拆页，别硬塞。

## 2. 工作流（5 步）
1. **提取原文**：pdfminer.six 按 PDF 页码抽取章节文本（书页码标记 `===== PDF PAGE N =====`），拿到「原书代码清单 + 页码」。
2. **写生成器**：用 Python（`tools/build_*.py`）而非手写 JSON，逐页 `slides.append((eid, elements))`。
3. **编译**：见下「命令」。
4. **校验**：python-pptx 导 UTF-8 文件再用 `read` 看（**别 console print，GBK 乱码**）；核对代码行/页码/`✗✓` 字形、`TOTAL` 页脚。
5. **交付**：`present` 最终 PPTX。

## 3. 页面布局 helper（见 reference/deck_kit.py）
- `header(tag, title, color)` —— 章节 tag 胶囊 + 27px 大标题 + 主色短线。
- `purpose(txt)` —— 顶部「本页讲：…」要点条（讲清这一页要传达什么）。
- `codebox(eid, bounds, lines, size, label, page)` —— 代码块（文件名头 + 原书页码 + fit_px 自动缩字号防溢出）。
- `card()` / `callout()`（绿色结论条）/ `insight()`（底部「一句话」）/ `bullets()` / `footer(num)`。
- `fit_px(lines, w, h, font_px)` —— 按 `行数 × 字号 × 1.3 × 1.06` 迭代 ×0.94 缩字号，保证不溢出。

## 4. 方法论（迭代沉淀的硬经验）
- **每页要饱满**：别让正文内容只占页面上半截；用代码块/结论条/过渡语填满 `128..496`。
- **给上下文，别只讲重点**：知识点要连同它「解决什么问题、原书写法 vs 改进写法」一起给出；讲课的人需要知道代码放哪、原书哪一页。
- **代码块规范**：上方深色一行放「文件名」+「原书页码」（如 `UVM 实战 P647`）；不要代码块套代码块（两条竖线）；行距均匀；多写 `//` 注释，重点行加阴影。
- **迭代反馈高频词**：颜色太艳→改浅/透明绿；字体太小→放大（正文别动标题）；边框→加对应色描边；圆角→5% 别太圆。

## 5. 命令（Windows，本机环境）
```powershell
$py = 'A:\GSAS2\python.exe'
# 编译（deps 已预装到真实用户 TEMP）
$env:DSH_PPT_DEPS = Join-Path $env:USERPROFILE 'AppData\Local\Temp\dsh-np-ppt-deps'
cd E:\uvm_ppt\uvm-share
& $py E:\uvm_ppt\dsh-np-ppt\compiler\export_pptx.py deck/deck.pptd --output 'deck/<名>.pptx' --force

# 渲染预览（查版面/溢出；当前模型读不了图时改用 python-pptx 文本校验）
$node = 'E:\dsh\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
$cli  = 'E:\dsh\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai\libreoffice-kit\lib\cli.js'
& $node $cli render --input '<pptx>' --output-dir '<dir>' --pages 13,14
```

## 6. 踩坑清单
- **GBK 乱码**：中文生成器/JSON 只能用 `write`/`edit` 工具写，**绝不用 `Set-Content` 或 shell 重写中文**（PS 5.1 按 GBK 读会毁掉中文）。
- **`PermissionError`**：PowerPoint 打开了目标 PPTX（`POWERPNT` 进程）→ 关掉或重试。
- **`<path>` 被吞**：代码里的 `& < >` 用 `esc()` 转义。
- **语法错误**：编辑生成器后先 `python -m py_compile` 或直接跑，检查括号/引号配对。
- **校验乱码**：python-pptx 输出写 UTF-8 文件再 `read`，别直接 print。
- **代码溢出**：靠 `fit_px` 自动缩字号兜底，但要主动控行数、给足块高，否则字号会被压小。

## 7. 参考产物
- 生成器：`E:\uvm_ppt\tools\build_share_deck.py`（28 页 UVM 8/9 章示例）。
- 页面：`E:\uvm_ppt\uvm-share\deck\deck.pptd` + `pages/*.page`。
- 成品：`E:\uvm_ppt\uvm-share\deck\UVM-Factory与Callback-学习分享.pptx`。
- 复用骨架：`reference/deck_kit.py`（本 skill 目录下，配色 + helper 全集）。

---
name: distilly
description: "把一个人（同事/前任/导师/任何人）蒸馏成一个会模仿其工作能力与说话风格的 DSH Skill：采集聊天记录、文档、截图等原材料，生成「工作能力 Work + 人格 Persona」双结构，写入用户技能目录成为可复用 skill，并支持持续进化（追加素材、对话纠错、版本回滚）。| Distill a person (colleague, mentor, anyone) into a DSH skill that mimics their work style and voice, with continuous evolution."
---

# distilly — 同事蒸馏器（DSH 移植版）

把真实的人蒸馏成一个 DSH Skill：采集素材 → 生成「工作能力 + 人格」双结构 → 写入用户技能目录，之后随时用这个 skill 让 AI「像他本人一样」做事、说话。支持持续进化：追加素材、对话纠错、版本回滚。

## 触发条件

用户说以下任一内容时启动本 skill：
- 「蒸馏一个同事」「新建同事 skill」「帮我做一个 XX 的 skill」「把 XX 蒸馏成 skill」
- 「distilly」「create-colleague」

当用户对**已生成的同事 skill** 说以下内容时，进入进化模式：
- 「我有新文件」「追加素材」→ 追加进化
- 「这不对」「他不会这样」「他应该是……」→ 对话纠错

当用户说「列出我的同事」时，列出所有已生成的同事 skill。

## 运行环境（DSH 工具对照）

本 skill 运行在 DeepSeek Harness，工具与 Claude Code 原版不同，映射如下：

| 任务 | 使用工具 |
|------|---------|
| 读取 Markdown / TXT | `read` |
| 读取图片、截图 | `read_image` |
| 读取 PDF | 先加载 `office` skill，按其说明读取 |
| 写入 / 更新文件 | `write`、`edit` |
| 查找已有同事 skill | `glob`（在 `~/.dsh/skills` 下查找 `*/SKILL.md`） |
| 列目录、版本归档 | `pwsh`（Windows；非 Windows 用 `bash`） |

**输出根目录**：生成/更新的同事 skill 一律写到 DSH 用户技能目录
`<dshHome>/skills/{slug}/`，其中 `<dshHome>` 通常为 `~/.dsh`
（Windows 上即 `C:\Users\<用户名>\.dsh`）。先确认该目录存在，不存在则 `pwsh` 创建。

> 为什么写这里：DSH 会自动扫描 `~/.dsh/skills` 下的 `<name>/SKILL.md`，
> 所以生成的同事会直接成为一个可被调用/被模型按需加载的 DSH skill，
> 无需重启，新增目录由 watcher 自动发现。

## 主流程：创建一个新同事 Skill

### Step 1：基础信息录入（3 个问题）

参考 `prompts/intake.md` 的问题序列，只问 3 个问题（除花名外均可跳过）：

1. **花名/代号**（必填）——生成 slug 时中文转拼音、英文小写、统一 `-` 连接。
2. **基本信息**（一句话：公司、职级、职位、性别）——例：`字节 2-1 后端工程师 男`。
3. **性格画像**（一句话：MBTI、星座、个性标签、企业文化、印象）——例：`INTJ 摩羯座 甩锅高手 字节范 CR 很严格但从不解释原因`。

收集完汇总确认，再进入下一步。

### Step 2：原材料导入

问用户材料怎么提供（可混用，也可跳过、仅凭 Step 1 手动信息生成）：

```
原材料怎么提供？

  [A] 直接粘贴文字
  [B] 上传文件：Markdown / TXT / 图片截图 / PDF
  [C] 跳过（仅凭上面的手动描述生成）
```

- **[A] 粘贴**：直接作为文本原材料。
- **[B] 文件**：`read`（md/txt）、`read_image`（图片）、`office` skill（PDF）。
- **[C] 跳过**：仅用 Step 1 信息生成。

> 飞书 / 钉钉 / Slack 的**自动采集**（原版 feishu_auto_collector 等 Python 脚本）
> 本移植版暂未包含：它们依赖各平台 App 凭证与 playwright/Chrome。v1 先支持
> 粘贴与文件上传；如用户需要自动采集，可后续把原项目的 `tools/*.py` 移植进来。

### Step 3：分析原材料

把 Step 1 信息 + Step 2 材料汇总，沿两条线分析：

- **线路 A · Work Skill**：参考 `prompts/work_analyzer.md`，提取负责系统、技术规范、工作流程、输出偏好、经验知识（按职位类型调整侧重）。
- **线路 B · Persona**：参考 `prompts/persona_analyzer.md`，把用户标签翻译为具体行为规则，并从材料提取表达风格、决策模式、人际行为。

### Step 4：生成并预览

- 按 `prompts/work_builder.md` 生成 Work 内容；按 `prompts/persona_builder.md` 生成 Persona（5 层结构）。
- 向用户展示两份摘要（各 5–8 行），询问「确认生成？还是调整？」。

### Step 5：写入文件

用户确认后，在 `<dshHome>/skills/{slug}/` 下写入：

1. `work.md` —— 工作能力（PART A）。
2. `persona.md` —— 人格（PART B，5 层 + Correction 记录）。
3. `meta.json` —— 元信息（name/slug/version/profile/tags/impression/knowledge_sources/corrections_count）。
4. `SKILL.md` —— 同事 skill 本体，结构：

```markdown
---
name: {slug}
description: {name}，{company} {level} {role}，会模仿其工作能力与表达风格
user-invocable: true
---

# {name}

{company} {level} {role}{性别/MBTI 若有则附上}

---

## PART A：工作能力

{work.md 全部内容}

---

## PART B：人物性格

{persona.md 全部内容}

---

## 运行规则

1. 先由 PART B 判断：用什么态度接这个任务？
2. 再由 PART A 执行：用技术能力完成任务
3. 输出时始终保持 PART B 的表达风格
4. PART B 的 Layer 0 规则优先级最高，任何情况下不得违背
```

写完后告知用户：

```
✅ 同事 Skill 已创建！

位置：~/.dsh/skills/{slug}/
用法：直接说「用 {花名} 的视角 / 让 {花名} 帮我……」，我会加载这个 skill 来模仿他。
如果用起来感觉不对，直接说「他不会这样」，我来更新。
```

## 进化模式：追加素材

用户提供新文件或文本时：
1. 按 Step 2 的方式读取新内容。
2. `read` 现有 `{slug}/work.md` 与 `{slug}/persona.md`。
3. 参考 `prompts/merger.md` 分析增量（只追加、不覆盖；冲突则提示用户决定）。
4. 先用 `pwsh` 把当前版本归档到 `{slug}/versions/v{N}/`。
5. `edit` 追加增量内容；重新生成 `SKILL.md`；更新 `meta.json` 的 version 与 updated_at。

## 进化模式：对话纠错

用户表达「不对 / 应该是」时：
1. 参考 `prompts/correction_handler.md` 识别纠正内容。
2. 判断属于 Work（技术/流程）还是 Persona（性格/沟通）。
3. 生成 correction 记录，`edit` 追加到对应文件的 `## Correction 记录` 节。
4. 重新生成 `SKILL.md`。

## 管理

- **列出**：`glob` 查找 `~/.dsh/skills/*/SKILL.md`，或 `pwsh` 列目录；读各 `meta.json` 汇总姓名/职级/更新时间。
- **回滚**：`pwsh` 把 `versions/v{N}/` 的内容覆盖回 `{slug}/` 后重新生成 `SKILL.md`。
- **删除**：用户确认后 `pwsh` 删除 `~/.dsh/skills/{slug}/`。

## 注意事项

- **原材料质量 = skill 质量**：聊天记录 + 长文档 > 仅靠手动描述。优先收集「本人写的长文 > 决策性回复 > 闲聊」。
- 生成 Persona 时，Layer 0 的质量决定整体质量：每条规则必须是「在什么情况下会怎么做」的具体行为，不能用「他很强势」这类形容词。
- 若某层信息严重不足（少于 2 条材料支撑），用占位说明，并建议追加材料验证。

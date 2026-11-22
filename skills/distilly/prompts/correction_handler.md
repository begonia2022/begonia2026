# 对话纠错处理

## 任务

用户对已生成的同事 skill 表达「这不对」「他不会这样」「他应该是……」时，
识别纠错内容并把它写进对应文件的 Correction 记录。

## Step 1：识别纠错内容

从用户的话里提取：
- **纠错对象**：指的是哪条行为/规则/结论（引用现有 work.md 或 persona.md 里的原句）
- **纠正为**：用户认为正确/真实的样子
- **纠错理由**（如有）：为什么之前不对

## Step 2：分类

| 纠错内容 | 归入 |
|---------|------|
| 技术判断、流程、规范、经验结论 | → work.md 的 `## Correction 记录` |
| 性格、表达、决策、人际行为 | → persona.md 的 `## Correction 记录` |
| 两者都有 | → 分别写入 |

## Step 3：生成 correction 记录

追加到对应文件的 `## Correction 记录` 节，格式：

```markdown
- [{日期}] {原描述} → 修正为：{新描述}（理由：{用户理由，若有}）
```

## Step 4：重新生成 SKILL.md

用更新后的 work.md + persona.md 重新生成 `SKILL.md`（保证 PART A / PART B 与源文件一致），
并更新 `meta.json` 的 `corrections_count` 与 `updated_at`。

## 注意事项

- Correction 记录的规则优先级最高，生成后的 `SKILL.md` 运行规则里应保留
  「Correction 层有规则时优先遵守」这一条。
- 纠错不覆盖原结论，而是追加一条「覆盖记录」，保留可追溯性。

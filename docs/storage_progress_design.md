# StoryForge 当前存储设计与后续计划

## 当前实现

当前实现将进展维护下沉到每本小说目录：

1. `index.json` 只维护小说清单和路径，不再维护章节进展字段。
2. 章节总数、当前章节、已通过章节、进度百分比等，统一从 `novel_meta.json` 与章节明细计算。
3. 根索引变轻量，便于重排、迁移与快速修复。

## 2. 目录与相对位置

以下路径均相对于 `storage.data_dir`（默认 `~/.storyforge/data`）：

1. 小说索引（根）
- `index.json`

2. 单本小说目录
- `novels/<novel_id>/novel_meta.json`
- `novels/<novel_id>/chapters.json`
- `novels/<novel_id>/reviews.json`
- `novels/<novel_id>/proofreads.json`
- 其他业务文件（如 `outline.json`、`characters.json`）

## 3. 文件职责

### 3.1 `index.json`

职责：仅做小说清单与定位，不承担进展统计。

数据类型：`List[IndexEntry]`

`IndexEntry` key 约定：

1. `novel_id` (`string`)
- 小说唯一标识。
- 必填。

2. `novel_path` (`string`)
- 小说目录相对路径。
- 格式约定：`novels/<novel_id>`。
- 必填。

示例：

```json
[
  {
    "novel_id": "novel_demo_001",
    "novel_path": "novels/novel_demo_001"
  }
]
```

### 3.2 `novels/<novel_id>/novel_meta.json`

职责：单本小说的主进展文件（全局进展聚合）。

关键 key 约定：

1. `novel_id` (`string`)
- 与目录 ID 一致。

2. `novel_title` (`string`)
- 小说名称（展示主标题来源）。

3. `genre` (`string`)
- 类型。

4. `concept` (`string`)
- 一句话概念。

5. `current_stage` (`string`)
- 流程阶段。
- 枚举约定：`creation` | `extraction` | `ip_generation` | `video_generation` | `completed`。

6. `current_chapter` (`number`)
- 当前推进到的章节号（通常用于下一章生成入口）。

7. `total_chapters` (`number`)
- 当前已存在章节总数。

8. `approved_chapters` (`number`)
- 已通过章节数量。

9. `draft_chapters` (`number`)
- 草稿章节数量。

10. `review_chapters` (`number`)
- 审稿中章节数量。

11. `rejected_chapters` (`number`)
- 驳回章节数量。

12. `target_word_count` (`number`)
- 目标字数。

13. `created_at` (`string`)
- 创建时间（ISO8601）。

14. `updated_at` (`string`)
- 最近更新时间（ISO8601）。

### 3.3 `novels/<novel_id>/chapters.json`

职责：章节正文与逐章状态明细（章节级进展来源）。

数据类型：`Dict[str, Chapter]`（key 为章节号字符串，如 `"1"`）

`Chapter` 关键 key 约定：

1. `chapter_num` (`number`)
- 章节号。

2. `title` (`string`)
- 章节标题。

3. `content` (`string`)
- 章节正文。

4. `status` (`string`)
- 章节状态。
- 枚举约定：`pending` | `draft` | `in_review` | `revising` | `proofreading` | `approved` | `rejected`。

5. `word_count` (`number`)
- 章节字数。

6. `version` (`number`)
- 内容版本号。

7. `review_round` (`number`)
- 当前已审稿轮次。

8. `review_scores` (`number[]`)
- 历次评分。

9. `latest_review_comment` (`string`)
- 最近审稿意见摘要。

10. `created_at` / `updated_at` / `published_at` (`string`)
- 时间戳字段。

11. `history` (`array`)
- 版本记录。

### 3.4 `novels/<novel_id>/reviews.json`

职责：章节审稿明细（轮次、评分、问题）。

数据类型：`Dict[str, Review]`

`Review` 关键 key：

1. `chapter_num` (`number`)
- 对应章节号。

2. `records` (`ReviewRecord[]`)
- 审稿轮次明细。

3. `best_score` (`number`)
- 当前最佳分。

4. `final_verdict` (`string|null`)
- 最终结论：`pass` | `revise` | `rewrite`。

`ReviewRecord` 关键 key：

1. `round` (`number`)
2. `reviewer` (`string`)
3. `total_score` (`number`)
4. `dimensions` (`array`)
5. `issues` (`array`)
6. `verdict` (`string`)
7. `summary` (`string`)
8. `passed` (`boolean`)
9. `timestamp` (`string`)

### 3.5 `novels/<novel_id>/proofreads.json`

职责：章节校对明细（问题类型与通过状态）。

数据类型：`Dict[str, Proofread]`

`Proofread` 关键 key：

1. `chapter_num` (`number`)
2. `records` (`ProofreadRecord[]`)
3. `total_issues` (`number`)
4. `final_passed` (`boolean`)

`ProofreadRecord` 关键 key：

1. `round` (`number`)
2. `proofreader` (`string`)
3. `issues` (`array`)
4. `passed` (`boolean`)
5. `summary` (`string`)
6. `scope` (`string`): `chapter` | `volume` | `book` | `project_docs`
7. `timestamp` (`string`)

## 4. 进展计算约定

1. 小说总章节
- 来源：`novel_meta.total_chapters`。
- 可由 `chapters.json` 的 key 数校验。

2. 已通过章节
- 主来源：`novel_meta.approved_chapters`。
- 可由 `chapters.json` 中 `status == approved` 回算校验。

3. 进度百分比
- 公式：`approved_chapters / max(total_chapters, 1) * 100`。

4. 当前推进章节
- 来源：`novel_meta.current_chapter`。

## 5. 更新规则

1. 创建小说
- 写入 `novel_meta.json`。
- 在 `index.json` 增加 `{novel_id, novel_path}`。

2. 推进章节/审稿/校对
- 仅更新对应小说目录内明细 JSON。
- 必要时同步更新 `novel_meta.json` 聚合字段。
- 不改动 `index.json` 的业务进展字段（因该字段已下沉）。

3. 重建索引
- 扫描 `novels/*/novel_meta.json`。
- 重新生成 `index.json` 最小条目。

## 当前约束

1. 接口层可继续返回进展字段（如 `total_chapters`、`approved_chapters`），但这些值来自每本小说明细，不来自根索引。
2. `index.json` 只作为轻量索引，不再承载章节进展统计。

## 后续计划

1. 为 Web Console 增加更多从 `novel_meta.json` 派生出的进展摘要视图。
2. 继续减少根索引中的冗余字段，保持 `index.json` 轻量和稳定。
3. 为存储层补充更多一致性校验与恢复工具。

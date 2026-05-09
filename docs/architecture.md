# 系统架构

## 整体架构

StoryForge 是一个多 Agent 小说创作与 IP 衍生平台，基于 LangGraph 流程编排与 CrewAI 风格角色系统构建：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Web 前端层                                   │
├─────────────────────────────────────────────────────────────────────┤
│  web_console/  (FastAPI, 端口 8787)                                 │
│  - 任务管理界面                                                      │
│  - 创作进度监控                                                      │
│  - 人物 IP 操作区                                                    │
│  - 日志查看                                                          │
│                                                                      │
│  backend/  (Flask, 端口 5089)                                        │
│  - 小说清单/详情 API                                                 │
│  - 静态文件服务                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                         存储层                                       │
│  - ~/.storyforge/data/  (小说数据, YAML 配置决定)                    │
│  - local_store/vector_store.jsonl  (向量库)                         │
│  - local_store/ip_assets/  (IP 资产)                                │
│  - debug_output/  (调试输出)                                        │
│  - video_assets/  (视频生成中间产物：剧本、视觉圣经、渲染计划、检查报告) │
├─────────────────────────────────────────────────────────────────────┤
│                       Pipeline 层 (LangGraph)                         │
┌─────────────────────────────────────────────────────────────────────┐
│  创作阶段：outline_refiner → writer → reviewer → reviser → proofread │
│  萃取阶段：knowledge_extractor  (从章节提取知识 → memory)            │
│  IP 阶段：ip_designer  (生成 story bible + 人物 IP)                  │
│  视频阶段（可选）：video_script → visual_bible → video_assets → video_consistency → video_generate │
│  支持：checkpoint 断点续跑、条件路由、AI 味检测                       │
├─────────────────────────────────────────────────────────────────────┤
│                        Agent 层                                      │
┌─────────────────────────────────────────────────────────────────────┐
│  Writer(墨川) | Reviewer(青锋) | Reviser(墨川) | Proofreader(砚清)  │
│  支持：MessageBus (Agent 间通讯)、memory、JSON 结构化输出            │
├─────────────────────────────────────────────────────────────────────┤
│                        Core 层                                       │
┌─────────────────────────────────────────────────────────────────────┐
│  core/state.py           NovelState, ChapterStatus, ReviewRecord     │
│  core/agent.py           BaseAgent, AgentPersona, MessageBus         │
│  core/schema.py          ReviewResult, ProofreadResult, ChapterContent│
│  core/memory.py          StoryMemory (事件/人物/世界状态)            │
│  core/prompt_assembler.py  PromptAssembler (动态Prompt+人味化)       │
│  core/config.py          ~/.storyforge/storyforge.yaml  (全系统配置)  │
├─────────────────────────────────────────────────────────────────────┤
│                       stages/ 模块                                   │
│  stages/outline/         OutlineGenerator (章级细纲生成)            │
│  stages/extraction/      KnowledgeExtractor (知识萃取)              │
│  stages/ip_generation/   IPGenerator (IP 资产生成)                 │
└─────────────────────────────────────────────────────────────────────┘
```

## 配置系统说明

StoryForge 使用单一配置文件：

- 文件位置：`~/.storyforge/storyforge.yaml`
- 加载入口：`core/config.py`
- 用途：Flask API、FastAPI 操作界面、Pipeline 与存储路径

## 设计原则

### 状态驱动
所有 Agent 节点读写同一个 `NovelState` 对象：
- 输入：当前全局状态
- 输出：更新后的全局状态
- LangGraph 负责状态的流转和持久化
- `to_dict()` / `from_dict()` 支持完整的 JSON 序列化与反序列化（含枚举、嵌套 dataclass、int 章节键）

### 角色即提示词工程
`AgentPersona` 的每个字段都有明确的工程用途：
- `backstory`：影响 LLM 语气和知识倾向
- `expertise`：影响任务分配和工具使用
- `tone`：影响输出文本的调性
- `principles`：影响决策逻辑
- `constraints`：影响输出边界

### 结构化输出 + 人味化
- 审稿/校对使用 JSON Schema 确保可解析
- PromptAssembler 自动集成人味化规则：禁用 AI 常见句式、提升文本自然度
- AI 味检测（low/medium/high）：high 等级自动触发重写

### 记忆系统
- StoryMemory：事件时间线 + 人物状态 + 世界设定
- 一致性检查：自动检测人物名字、设定、时间线矛盾
- 用于创作上下文注入

### Agent 间通讯 (MessageBus)
- 发布/订阅模式
- 按类型过滤
- 定向投递
- 消息持久化

## 阶段详解

### 阶段一：创作 (Creation)
1. **大纲细化** (outline_refiner)：从卷纲生成章级细纲
2. **写作** (writer)：基于细纲创作章节
3. **审稿** (reviewer)：8维度结构化评分 + AI味评估
4. **修改** (reviser)：根据审稿意见修改
5. **校对** (proofreader)：6层级检查 + 终审判定（可发布/可交付/需返修）

### 阶段二：萃取 (Extraction)
- 从章节提取事件、人物、伏笔
- 构建知识图谱
- 更新 memory

### 阶段三：IP 生成 (IP Generation)
- 生成 story bible
- 人物 IP 资产（人设、台词、画像提示词）
- 存入 `local_store/ip_assets/`

## 状态字段分组

`NovelState` 按阶段分组：

```python
# 元数据
novel_id, novel_title, genre, target_word_count, current_stage

# 创作层
concept, outline, volume_outline, characters
chapters, chapter_status, current_chapter, review_round
reviews, structured_reviews, proofread_results, proofread_records
proofread_scope, proofread_context

# 萃取层
knowledge_base, chapter_analyses

# IP 层
character_ips, visual_assets, story_bible

# 兼容容器（仅存非章节辅助数据）
creation: {chapter_outlines, chapter_summaries, extraction_notes}

# 控制字段
error_message, human_feedback, should_pause
```

## 相关文档

- [Agent 系统设计](agent-system.md)
- [Pipeline 流程详解](pipeline.md)
- [API 参考](api-reference.md)
- [配置说明](config.md)

# StoryForge 核心实现现状

## 当前实现

### 1. 知识萃取阶段 (stages/extraction/)

- `knowledge_extractor.py`: `KnowledgeExtractor` 类
  - 自动从章节中提取关键事件
  - 识别并记录新登场人物
  - 检测和记录新伏笔（契诃夫之枪）
  - 更新角色状态
  - 维护世界设定变更
  - 与 `StoryMemory` 集成

### 2. IP 生成阶段 (stages/ip_generation/)

- `ip_generator.py`: `IPGenerator` 类
  - 为每个角色生成完整 IP 档案（外貌、性格、经典语录、成长弧线）
  - 生成关系图谱
  - 生成场景设定集
  - 生成衍生设定（道具、法术、势力等）
  - 生成 Story Bible 文档
  - 支持导出 JSON

### 3. 大纲生成器 (stages/outline/)

- `outline_generator.py`: `OutlineGenerator` 类（完整实现）
  - 从核心概念自动生成全书大纲
  - 从卷纲自动生成卷级大纲
  - 生成章级写作计划
  - 管理伏笔、角色、世界观
  - 支持 Pipeline 调用的 `generate_chapter_outline()` 方法

### 4. Pipeline 增强 (pipeline/novel_pipeline.py)

- 集成了知识萃取和 IP 生成阶段
- 修复了断点续跑逻辑：
  - 保存 Agent 引用到 `self._writer_agent` 等
  - 在 `resume()` 中正确恢复 Agent 实例
  - 节点映射使用已保存的引用
- 新增配置选项：
  - `use_extraction`: 是否启用知识萃取
  - `use_ip_generation`: 是否启用 IP 生成
  - `ip_output_dir`: IP 资产输出目录

### 5. State 扩展 (core/state.py)

- 新增 `chapter_analyses` 字段保存知识萃取结果
- 新增 `story_bible` 字段保存 Story Bible 对象

## 当前使用方式

```python
from pipeline.novel_pipeline import NovelPipeline
from core.state import NovelState

# 创建 Pipeline（启用所有阶段）
pipeline = NovelPipeline(
    llm_client=my_llm_callable,
    use_memory=True,
    use_outline_refinement=True,
    use_extraction=True,
    use_ip_generation=True,
    checkpoint_dir="./checkpoints",
    ip_output_dir="./ip_assets"
)

# 创建初始状态
state = NovelState(
    novel_id="my_novel_001",
    novel_title="我的小说",
    genre="玄幻",
    target_word_count=100000,
    current_chapter=1
)

# 运行 Pipeline
final_state = pipeline.run(state)

# 断点续跑
# resumed_state = pipeline.resume(novel_id="my_novel_001", chapter=1)
```

## 当前涉及模块

```
StoryForge/
├── stages/
│   ├── extraction/
│   │   ├── __init__.py
│   │   └── knowledge_extractor.py
│   ├── ip_generation/
│   │   ├── __init__.py
│   │   └── ip_generator.py
│   └── outline/
│       ├── __init__.py
│       └── outline_generator.py
├── pipeline/
│   └── novel_pipeline.py (更新)
└── core/
    └── state.py (更新)
```

## 当前约束

1. 核心功能都已实现占位符逻辑（即使没有 LLM 也不会崩溃）
2. `OutlineGenerator` 与 `ProgressivePlanner` 位于 `stages/outline/`，由 Pipeline 直接调用
3. IP 相关共享逻辑现在统一走 `core/ip_workflow.py`
4. 检查点仍然保存到 `./checkpoints` 目录

## 后续计划

1. 继续把视频链路、视觉链路和提案链路的摘要能力补到 Web Console。
2. 为 Pipeline 的反馈回写和 proposal 审批补充更明确的操作文档。
3. 继续收口文档里的旧路径和兼容表述，保持文档与代码同步。

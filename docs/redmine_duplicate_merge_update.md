# 当前实现整理说明

## 当前实现

本文件用于概括当前已经落地的代码整理结果，而不是记录一次性变更过程。

当前已经完成的收口内容：

1. Agent 通信模型
- `AgentMessage` 统一由 `core/models/agent/agent_comm.py` 定义。
- `core/agent.py` 仅保留 Agent 基类与消息总线实现。

2. 视觉服务公共逻辑
- `web_console/services/visual_common.py` 承担图片本地 URL 和 prompt optimizer client 的共享逻辑。
- `novel_cover.py` 与 `character_visuals.py` 不再维护重复 helper。

3. IP 入口
- `core/ip_workflow.py` 统一管理 StoryBible 生成与角色导出逻辑。
- `pipeline` 与 `web_console` 已统一复用这套入口。

4. Video 入口
- `core/video/workflow.py` 统一管理 script / bible / assets / consistency 的共享落盘逻辑。
- `pipeline` 与 `web_console` 仅保留各自的编排职责。

5. 模型导入路径
- 代码已统一使用 `core.models.content / world / agent / extraction / ip / video`。
- `core/models` 根目录旧兼容包装文件已删除。

## 后续计划

1. 继续清理剩余文档中的旧路径和过时表述。
2. 评估是否还需要进一步瘦身 `NovelState.creation` 兼容字段。
3. 把 `web_console/services/novels.py` 中通用文本 helper 进一步抽离。
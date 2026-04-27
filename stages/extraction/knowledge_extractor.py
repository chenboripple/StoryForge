"""
StoryForge - 知识萃取器

职责：
1. 自动从章节中提取关键事件
2. 识别并记录新登场的人物
3. 检测和记录新伏笔（契诃夫之枪）
4. 更新角色状态
5. 维护世界设定变更
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
import json
import re

from core.memory import StoryMemory, StoryEvent


@dataclass
class ExtractedEntity:
    """提取出的实体基类"""
    entity_type: str  # "character" | "location" | "foreshadowing" | "item"
    name: str
    description: str
    source_chapter: int
    confidence: float = 0.8  # 置信度


@dataclass
class ExtractedCharacter(ExtractedEntity):
    """提取出的新人物"""
    entity_type: str = "character"
    appearance: str = ""
    personality: str = ""
    role: str = "supporting"  # "protagonist" | "supporting" | "antagonist" | "cameo"
    relationships: List[Dict] = field(default_factory=list)


@dataclass
class ExtractedForeshadowing(ExtractedEntity):
    """提取出的伏笔"""
    entity_type: str = "foreshadowing"
    foreshadowing_type: str = "plot"  # "plot" | "character" | "world"
    expected_payoff: str = ""  # 预期回收方式
    urgency: str = "medium"  # "low" | "medium" | "high"


@dataclass
class ExtractedLocation(ExtractedEntity):
    """提取出的新地点"""
    entity_type: str = "location"
    location_type: str = "place"  # "place" | "building" | "region" | "world"
    status: str = ""  # 地点状态（如"被摧毁"、"被占领"）
    controlling_faction: str = ""


@dataclass
class ChapterAnalysis:
    """单章节分析结果"""
    chapter: int
    events: List[StoryEvent] = field(default_factory=list)
    new_characters: List[ExtractedCharacter] = field(default_factory=list)
    new_locations: List[ExtractedLocation] = field(default_factory=list)
    new_foreshadowings: List[ExtractedForeshadowing] = field(default_factory=list)
    character_updates: List[Dict] = field(default_factory=list)  # 角色状态变更
    world_updates: List[Dict] = field(default_factory=list)  # 世界设定变更
    resolved_foreshadowings: List[str] = field(default_factory=list)  # 回收的伏笔
    summary: str = ""


class KnowledgeExtractor:
    """
    知识萃取器

    工作流程：
    1. LLM 分析章节内容 → 结构化提取结果
    2. 验证提取结果与已有记忆的一致性
    3. 更新 StoryMemory
    4. 返回分析结果供后续阶段使用
    """

    def __init__(
        self,
        llm_client: Callable = None,
        memory: StoryMemory = None
    ):
        self.llm_client = llm_client
        self.memory = memory

    def extract(
        self,
        chapter: int,
        chapter_content: str,
        previous_context: Optional[Dict] = None
    ) -> ChapterAnalysis:
        """
        从单章中萃取知识

        Args:
            chapter: 章节号
            chapter_content: 章节内容
            previous_context: 前序章节上下文（可选）
        """
        if not self.llm_client:
            # 无 LLM 时返回空结果（不阻塞流程）
            return ChapterAnalysis(chapter=chapter)

        # 1. 构建提取提示词
        prompt = self._build_extraction_prompt(
            chapter_content=chapter_content,
            previous_context=previous_context
        )

        # 2. 调用 LLM 提取
        try:
            extracted_json_str = self.llm_client(prompt, temperature=0.3)
            extracted_data = self._parse_extraction_result(extracted_json_str)
        except Exception as e:
            print(f"  ⚠️ LLM 提取失败: {e}")
            return ChapterAnalysis(chapter=chapter)

        # 3. 转换为结构化对象
        analysis = self._build_chapter_analysis(chapter, extracted_data)

        # 4. 更新记忆（如果有）
        if self.memory:
            self._update_memory(analysis)

        return analysis

    def _build_extraction_prompt(
        self,
        chapter_content: str,
        previous_context: Optional[Dict] = None
    ) -> str:
        """构建知识提取提示词"""

        # 记忆上下文（如有）
        memory_context = ""
        if self.memory:
            memory_context = f"""
【已有记忆】
- 已知人物: {', '.join(self.memory.character_arcs.keys()) if self.memory.character_arcs else '无'}
- 已知地点: {', '.join(self.memory.world_state.locations.keys()) if self.memory.world_state.locations else '无'}
- 未回收伏笔: {len([g for g in self.memory.chekhovs_guns if not g.get('resolved')])}个
"""

        # 前序章节上下文
        prev_context_str = ""
        if previous_context:
            prev_context_str = f"""
【前序章节上下文】
{json.dumps(previous_context, ensure_ascii=False, indent=2)[:500]}
"""

        return f"""你是一位小说知识萃取专家。请仔细阅读以下章节内容，提取关键信息。

【任务要求】
请从章节中提取以下信息，以严格的JSON格式返回：

1. chapter_summary: 本章内容摘要（100-200字）

2. key_events: 本章关键事件列表，每个事件包含：
   - timestamp: 故事内时间（如"末日历47年3月"，无法确定则为空字符串）
   - description: 事件描述
   - characters_involved: 涉及的人物名列表
   - location: 发生地点
   - significance: 事件类型（"plot"| "character" | "world"）

3. new_characters: 本章新登场人物列表，每个包含：
   - name: 人物姓名
   - appearance: 外貌描述
   - personality: 性格/行为特点
   - role: 角色定位（"protagonist"| "supporting" | "antagonist" | "cameo"）
   - description: 简要介绍

4. new_locations: 本章新出现地点列表，每个包含：
   - name: 地点名称
   - location_type: 地点类型（"place"| "building" | "region" | "world"）
   - status: 地点状态（如"完好"、"被摧毁"、"被占领"等）
   - description: 详细描述

5. new_foreshadowings: 本章埋下的伏笔列表，每个包含：
   - name: 伏笔标识名（简短，如"神秘信件"）
   - description: 伏笔内容描述
   - foreshadowing_type: 伏笔类型（"plot"| "character" | "world"）
   - expected_payoff: 预期回收方式（推测）
   - urgency: 紧迫性（"low"| "medium" | "high"）

6. character_updates: 已有角色的状态变更列表，每个包含：
   - character_name: 角色名
   - update_type: 变更类型（"state"| "relationship" | "goal" | "death" | "injury"）
   - old_value: 原值
   - new_value: 新值
   - description: 变更说明

7. world_updates: 世界设定变更列表，每个包含：
   - update_type: 变更类型（"location_status"| "faction_change" | "rule_add"）
   - target: 变更目标（地点名/势力名等）
   - old_value: 原值
   - new_value: 新值
   - description: 变更说明

8. resolved_foreshadowings: 本章回收的伏笔名称列表（字符串列表）

{memory_context}
{prev_context_str}

【章节内容】
{chapter_content}

【输出要求】
- 只输出JSON，不包含任何额外说明
- 如果某项没有内容，返回空列表
- 确保JSON格式正确，可被解析

现在开始提取：
"""

    def _parse_extraction_result(self, llm_output: str) -> Dict:
        """解析 LLM 返回的提取结果"""
        # 清理输出（只保留 JSON 部分）
        json_str = llm_output.strip()

        # 尝试找到第一个 { 和最后一个 }
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}')

        if start_idx >= 0 and end_idx > start_idx:
            json_str = json_str[start_idx:end_idx + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 尝试修复常见的 JSON 错误
            fixed = self._fix_json(json_str)
            try:
                return json.loads(fixed)
            except:
                print("  ⚠️ JSON 解析失败，返回空结果")
                return {}

    def _fix_json(self, json_str: str) -> str:
        """尝试修复 JSON 格式"""
        # 常见修复：
        # 1. 替换单引号为双引号
        # 2. 移除末尾多余的逗号
        # 3. 补全缺失的括号
        fixed = json_str.replace("'", '"')

        # 移除 trailing commas
        fixed = re.sub(r',\s*([}\]])', r'\1', fixed)

        return fixed

    def _build_chapter_analysis(
        self,
        chapter: int,
        extracted_data: Dict
    ) -> ChapterAnalysis:
        """从提取数据构建章节分析"""
        analysis = ChapterAnalysis(
            chapter=chapter,
            summary=extracted_data.get('chapter_summary', '')
        )

        # 1. 关键事件
        for event_data in extracted_data.get('key_events', []):
            event = StoryEvent(
                chapter=chapter,
                timestamp=event_data.get('timestamp', ''),
                description=event_data.get('description', ''),
                characters_involved=event_data.get('characters_involved', []),
                location=event_data.get('location', ''),
                significance=event_data.get('significance', 'plot')
            )
            analysis.events.append(event)

        # 2. 新人物
        for char_data in extracted_data.get('new_characters', []):
            char = ExtractedCharacter(
                name=char_data.get('name', ''),
                description=char_data.get('description', ''),
                source_chapter=chapter,
                appearance=char_data.get('appearance', ''),
                personality=char_data.get('personality', ''),
                role=char_data.get('role', 'supporting')
            )
            analysis.new_characters.append(char)

        # 3. 新地点
        for loc_data in extracted_data.get('new_locations', []):
            loc = ExtractedLocation(
                name=loc_data.get('name', ''),
                description=loc_data.get('description', ''),
                source_chapter=chapter,
                location_type=loc_data.get('location_type', 'place'),
                status=loc_data.get('status', ''),
                controlling_faction=loc_data.get('controlling_faction', '')
            )
            analysis.new_locations.append(loc)

        # 4. 新伏笔
        for foreshadow_data in extracted_data.get('new_foreshadowings', []):
            foreshadow = ExtractedForeshadowing(
                name=foreshadow_data.get('name', ''),
                description=foreshadow_data.get('description', ''),
                source_chapter=chapter,
                foreshadowing_type=foreshadow_data.get('foreshadowing_type', 'plot'),
                expected_payoff=foreshadow_data.get('expected_payoff', ''),
                urgency=foreshadow_data.get('urgency', 'medium')
            )
            analysis.new_foreshadowings.append(foreshadow)

        # 5. 角色状态更新
        analysis.character_updates = extracted_data.get('character_updates', [])

        # 6. 世界设定更新
        analysis.world_updates = extracted_data.get('world_updates', [])

        # 7. 回收的伏笔
        analysis.resolved_foreshadowings = extracted_data.get('resolved_foreshadowings', [])

        return analysis

    def _update_memory(self, analysis: ChapterAnalysis):
        """根据分析结果更新记忆"""
        if not self.memory:
            return

        # 1. 记录事件
        self.memory.record_chapter_events(analysis.chapter, analysis.events)

        # 2. 添加新伏笔
        for foreshadow in analysis.new_foreshadowings:
            self.memory.add_chekhovs_gun(
                chapter=analysis.chapter,
                description=foreshadow.description
            )

        # 3. 回收伏笔
        for resolved_name in analysis.resolved_foreshadowings:
            self.memory.resolve_chekhovs_gun(resolved_name)

        # 4. 更新世界状态 - 新地点
        for loc in analysis.new_locations:
            if loc.name not in self.memory.world_state.locations:
                self.memory.world_state.locations[loc.name] = {
                    'status': loc.status,
                    'controlled_by': loc.controlling_faction,
                    'description': loc.description,
                    'first_appearance': analysis.chapter
                }

        # 5. 更新世界状态 - 地点变更
        for update in analysis.world_updates:
            if update.get('update_type') == 'location_status':
                target = update.get('target')
                if target in self.memory.world_state.locations:
                    self.memory.world_state.locations[target]['status'] = update.get('new_value', '')

        print(f"  ✅ 记忆已更新：{len(analysis.events)}个事件，"
              f"{len(analysis.new_foreshadowings)}个新伏笔，"
              f"{len(analysis.resolved_foreshadowings)}个伏笔回收")

    def batch_extract(
        self,
        chapters: Dict[int, str]
    ) -> Dict[int, ChapterAnalysis]:
        """批量提取多章知识"""
        results = {}
        prev_context = None

        for chapter_num in sorted(chapters.keys()):
            results[chapter_num] = self.extract(
                chapter=chapter_num,
                chapter_content=chapters[chapter_num],
                previous_context=prev_context
            )
            prev_context = {
                'chapter': chapter_num,
                'summary': results[chapter_num].summary
            }

        return results

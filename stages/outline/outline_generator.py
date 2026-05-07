"""
StoryForge - 大纲生成器（完整实现）

职责：
1. 从核心设定自动生成全书大纲
2. 从卷纲自动生成章级细纲
3. 管理伏笔、人物、世界观
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
import json
import re


@dataclass
class VolumeOutline:
    """卷级大纲"""
    volume_id: int
    name: str
    words: int
    chapters: int
    goal: str
    arc: str  # 起始状态→结束状态
    start_end_table: Dict[str, Dict[str, str]] = field(default_factory=dict)
    acts: List[Dict] = field(default_factory=list)
    chapter_outlines: List[Dict] = field(default_factory=list)
    character_growth: Dict[str, List[Dict]] = field(default_factory=dict)
    foreshadowing_setup: List[Dict] = field(default_factory=list)


@dataclass
class ChapterPlan:
    """章级写作计划"""
    chapter_id: int
    title: str
    theme: str
    plot: str
    scenes: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    words_target: int = 3000
    status: str = "not_started"
    characters_involved: List[str] = field(default_factory=list)
    key_events: List[str] = field(default_factory=list)
    foreshadowing: List[str] = field(default_factory=list)


@dataclass
class NovelOutline:
    """全书大纲"""
    title: str
    meta: Dict[str, Any] = field(default_factory=dict)
    selling_points: List[str] = field(default_factory=list)
    main_conflicts: Dict[str, List[Dict]] = field(default_factory=dict)
    volumes: List[VolumeOutline] = field(default_factory=list)
    creation_principles: Dict[str, str] = field(default_factory=dict)
    key_reversals: List[Dict] = field(default_factory=list)


@dataclass
class CharacterProfile:
    """人物档案"""
    id: str  # 拼音+下划线
    name: str
    role: str
    age: Optional[int] = None
    appearance: str = ""
    tags: List[str] = field(default_factory=list)
    motivation: str = ""
    fear: str = ""
    arc: Dict = field(default_factory=dict)
    intro_chapter: int = 0
    current_location: str = ""
    location_log: List[Dict] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    personal_timeline: List[Dict] = field(default_factory=list)


@dataclass
class Foreshadowing:
    """伏笔追踪"""
    id: str  # F001 格式
    content: str
    setup_chapter: str = ""
    payoff_volume: str = ""
    status: str = "未回收"  # 未回收/部分回收/已回收/持续使用
    note: str = ""


@dataclass
class WorldSetting:
    """世界观设定"""
    world_name: str
    background: str
    power_structure: Dict = field(default_factory=dict)
    key_locations: Dict = field(default_factory=dict)
    rules: Dict = field(default_factory=dict)


@dataclass
class ProjectProgress:
    """项目进度"""
    current: Dict = field(default_factory=dict)
    completed: Dict = field(default_factory=dict)
    volumes: List[Dict] = field(default_factory=list)
    chapter_status: Dict[str, List[int]] = field(default_factory=dict)


class OutlineGenerator:
    """
    大纲生成器（完整实现）

    职责：
    1. 从概念生成全书大纲
    2. 从卷纲生成章级细纲
    3. 管理伏笔、人物、世界观
    """

    def __init__(self, llm_client: Callable = None):
        self.llm_client = llm_client

    def generate_novel_outline(
        self,
        title: str,
        concept: str,
        genre: str,
        total_words: int,
        total_volumes: int = 1,
        chapters_per_volume: int = 30,
        words_per_chapter: int = 3000
    ) -> NovelOutline:
        """
        生成全书大纲

        Args:
            title: 小说标题
            concept: 核心创意/一句话梗概
            genre: 类型
            total_words: 总字数
            total_volumes: 卷数
            chapters_per_volume: 每卷章数
            words_per_chapter: 每章字数
        """
        if not self.llm_client:
            # 无 LLM 时返回基础结构
            return self._create_basic_outline(
                title, genre, total_words, total_volumes,
                chapters_per_volume, words_per_chapter
            )

        print(f"📖 生成全书大纲: {title}")

        # 调用 LLM 生成全书大纲
        prompt = self._build_novel_outline_prompt(
            title=title,
            concept=concept,
            genre=genre,
            total_words=total_words,
            total_volumes=total_volumes,
            chapters_per_volume=chapters_per_volume
        )

        try:
            result = self.llm_client(prompt, temperature=0.5)
            outline_data = self._parse_json(result)

            # 构建 NovelOutline
            outline = self._build_novel_outline_from_data(
                title, outline_data, genre, total_words,
                total_volumes, chapters_per_volume, words_per_chapter
            )

            print(f"  ✅ 全书大纲生成完成: {len(outline.volumes)} 卷")
            return outline

        except Exception as e:
            print(f"  ⚠️ 生成全书大纲失败: {e}")
            return self._create_basic_outline(
                title, genre, total_words, total_volumes,
                chapters_per_volume, words_per_chapter
            )

    def generate_volume_outline(
        self,
        volume_id: int,
        novel_outline: NovelOutline,
        characters: List[CharacterProfile]
    ) -> VolumeOutline:
        """
        生成卷级大纲

        Args:
            volume_id: 卷号
            novel_outline: 全书大纲
            characters: 人物列表
        """
        if not self.llm_client:
            return self._create_basic_volume(volume_id, novel_outline)

        print(f"📚 生成第 {volume_id} 卷大纲...")

        # 调用 LLM 生成卷纲
        prompt = self._build_volume_outline_prompt(
            volume_id=volume_id,
            novel_outline=novel_outline,
            characters=characters
        )

        try:
            result = self.llm_client(prompt, temperature=0.5)
            volume_data = self._parse_json(result)

            # 构建 VolumeOutline
            volume = self._build_volume_outline_from_data(
                volume_id, volume_data, novel_outline
            )

            print(f"  ✅ 第 {volume_id} 卷大纲生成完成: {len(volume.chapter_outlines)} 章")
            return volume

        except Exception as e:
            print(f"  ⚠️ 生成卷纲失败: {e}")
            return self._create_basic_volume(volume_id, novel_outline)

    def generate_chapter_plan(
        self,
        chapter_id: int,
        volume_outline: VolumeOutline,
        characters: List[CharacterProfile],
        previous_chapters: List[ChapterPlan] = None
    ) -> ChapterPlan:
        """
        生成章级写作计划

        Args:
            chapter_id: 章节号
            volume_outline: 卷级大纲
            characters: 人物列表
            previous_chapters: 之前章节的计划
        """
        if not self.llm_client:
            return self._create_basic_chapter(chapter_id, volume_outline)

        print(f"📝 生成第 {chapter_id} 章写作计划...")

        # 调用 LLM 生成章级细纲
        prompt = self._build_chapter_plan_prompt(
            chapter_id=chapter_id,
            volume_outline=volume_outline,
            characters=characters,
            previous_chapters=previous_chapters
        )

        try:
            result = self.llm_client(prompt, temperature=0.5)
            chapter_data = self._parse_json(result)

            # 构建 ChapterPlan
            plan = self._build_chapter_plan_from_data(chapter_id, chapter_data)

            print(f"  ✅ 第 {chapter_id} 章计划生成完成")
            return plan

        except Exception as e:
            print(f"  ⚠️ 生成章级计划失败: {e}")
            return self._create_basic_chapter(chapter_id, volume_outline)

    def generate_chapter_outline(
        self,
        novel_title: str,
        volume_outline: str,
        current_chapter: int,
        characters: List[Any],
        target_words: int = 3000
    ) -> Dict:
        """
        生成单章细纲（Pipeline 调用接口）

        Args:
            novel_title: 小说标题
            volume_outline: 卷级大纲文本
            current_chapter: 当前章节号
            characters: 角色列表
            target_words: 目标字数
        """
        if not self.llm_client:
            return {
                "title": f"第{current_chapter}章",
                "theme": "",
                "plot": "",
                "scenes": [],
                "hooks": [],
                "words_target": target_words
            }

        prompt = f"""你是一位小说大纲专家。请为以下小说生成第{current_chapter}章的详细写作大纲。

【小说标题】
{novel_title}

【卷级大纲】
{volume_outline}

【角色列表】
{self._format_characters(characters)}

【任务】
请生成第{current_chapter}章的详细写作计划，以JSON格式返回：

{{
    "title": "章节标题",
    "theme": "本章主题",
    "plot": "情节概要（200-300字）",
    "scenes": [
        "场景1描述",
        "场景2描述"
    ],
    "hooks": [
        "钩子1（吸引读者继续阅读的元素）",
        "钩子2"
    ],
    "characters_involved": ["角色1", "角色2"],
    "key_events": ["关键事件1", "关键事件2"],
    "foreshadowing": ["伏笔1", "伏笔2"],
    "words_target": {target_words}
}}

只输出JSON，不包含其他说明：
"""

        try:
            result = self.llm_client(prompt, temperature=0.5)
            return self._parse_json(result)
        except Exception as e:
            print(f"  ⚠️ 生成章细纲失败: {e}")
            return {
                "title": f"第{current_chapter}章",
                "theme": "",
                "plot": "",
                "scenes": [],
                "hooks": [],
                "words_target": target_words
            }

    # ========== 提示词构建 ==========

    def _build_novel_outline_prompt(
        self,
        title: str,
        concept: str,
        genre: str,
        total_words: int,
        total_volumes: int,
        chapters_per_volume: int
    ) -> str:
        """构建全书大纲生成提示词"""
        return f"""你是一位资深小说策划。请根据以下信息，生成完整的小说大纲。

【基本信息】
- 标题: {title}
- 核心创意: {concept}
- 类型: {genre}
- 总字数: {total_words}
- 卷数: {total_volumes}
- 每卷章数: {chapters_per_volume}

【任务要求】
请生成完整的小说大纲，以JSON格式返回：

{{
    "selling_points": ["卖点1", "卖点2", "卖点3"],
    "main_conflicts": {{
        "external": [
            {{"description": "外部冲突描述", "parties": ["方1", "方2"], "stakes": "赌注/代价"}}
        ],
        "internal": [
            {{"description": "内心冲突描述", "character": "角色名"}}
        ],
        "deep_theme": [
            {{"theme": "主题", "exploration": "如何展开"}}
        ]
    }},
    "creation_principles": {{
        "narrative_style": "叙事风格",
        "pacing": "节奏控制",
        "tone": "基调",
        "target_audience": "目标读者"
    }},
    "key_reversals": [
        {{"volume": 1, "chapter": 10, "description": "关键反转描述", "impact": "影响"}}
    ],
    "volumes": [
        {{
            "volume_id": 1,
            "name": "卷名",
            "goal": "本卷目标",
            "arc": "起始状态→结束状态",
            "start_end_table": {{
                "角色A": {{"start": "初始状态", "end": "结束状态"}}
            }},
            "acts": [
                {{"name": "幕名", "chapters": "1-10", "goal": "幕目标"}}
            ],
            "character_growth": {{
                "角色A": [{{"chapter": 1, "change": "变化描述"}}]
            }},
            "foreshadowing_setup": [
                {{"description": "伏笔描述", "expected_payoff": "预期回收"}}
            ],
            "chapter_outlines": [
                {{"chapter_id": 1, "title": "章标题", "theme": "主题", "key_events": ["事件1"], "words_target": 3000}}
            ]
        }}
    ]
}}

只输出JSON，不包含其他说明：
"""

    def _build_volume_outline_prompt(
        self,
        volume_id: int,
        novel_outline: NovelOutline,
        characters: List[CharacterProfile]
    ) -> str:
        """构建卷级大纲生成提示词"""
        # 获取全书大纲信息
        outline_json = self.to_json(novel_outline)

        # 格式化人物信息
        char_info = "\n".join([
            f"- {c.name} ({c.role}): {c.motivation}, 恐惧: {c.fear}"
            for c in characters[:5]  # 限制前5个主要角色
        ])

        return f"""你是一位小说策划。请为以下小说生成第{volume_id}卷的详细大纲。

【全书大纲】
{json.dumps(outline_json, ensure_ascii=False, indent=2)[:2000]}

【主要角色】
{char_info}

【任务】
请生成第{volume_id}卷的详细大纲，以JSON格式返回：

{{
    "name": "卷名",
    "goal": "本卷目标（100字以内）",
    "arc": "起始状态→结束状态",
    "start_end_table": {{
        "角色A": {{"start": "初始状态", "end": "结束状态"}}
    }},
    "acts": [
        {{"name": "幕名", "chapters": "1-5", "goal": "幕目标"}}
    ],
    "character_growth": {{
        "角色A": [{{"chapter": 1, "change": "变化描述"}}]
    }},
    "foreshadowing_setup": [
        {{"description": "伏笔描述", "expected_payoff": "预期回收"}}
    ],
    "chapter_outlines": [
        {{
            "chapter_id": 1,
            "title": "章标题",
            "theme": "主题",
            "key_events": ["事件1"],
            "words_target": 3000
        }}
    ]
}}

只输出JSON，不包含其他说明：
"""

    def _build_chapter_plan_prompt(
        self,
        chapter_id: int,
        volume_outline: VolumeOutline,
        characters: List[CharacterProfile],
        previous_chapters: Optional[List[ChapterPlan]]
    ) -> str:
        """构建章级计划生成提示词"""
        # 格式化卷纲信息
        vol_info = f"""
卷名: {volume_outline.name}
卷目标: {volume_outline.goal}
卷弧线: {volume_outline.arc}
"""

        # 格式化前序章节
        prev_info = ""
        if previous_chapters:
            prev_info = "\n【前序章节】\n"
            for prev in previous_chapters[-3:]:  # 最近3章
                prev_info += f"- 第{prev.chapter_id}章: {prev.title}\n  {prev.plot[:100]}...\n"

        return f"""你是一位小说写作专家。请为以下章节生成详细的写作计划。

【卷级信息】
{vol_info}

【章节信息】
章节号: 第{chapter_id}章

{prev_info}

【任务】
请生成第{chapter_id}章的详细写作计划，以JSON格式返回：

{{
    "title": "章节标题",
    "theme": "本章主题",
    "plot": "情节概要（200-300字）",
    "scenes": [
        "场景1: 详细描述",
        "场景2: 详细描述"
    ],
    "hooks": [
        "钩子1（吸引读者继续阅读的元素）",
        "钩子2"
    ],
    "characters_involved": ["角色1", "角色2"],
    "key_events": ["关键事件1", "关键事件2"],
    "foreshadowing": ["伏笔1", "伏笔2"],
    "words_target": 3000
}}

只输出JSON，不包含其他说明：
"""

    # ========== 数据构建 ==========

    def _build_novel_outline_from_data(
        self,
        title: str,
        data: Dict,
        genre: str,
        total_words: int,
        total_volumes: int,
        chapters_per_volume: int,
        words_per_chapter: int
    ) -> NovelOutline:
        """从解析数据构建 NovelOutline"""
        outline = NovelOutline(
            title=title,
            meta={
                "type": genre,
                "total_words": total_words,
                "total_volumes": total_volumes,
                "chapters_per_volume": chapters_per_volume,
                "words_per_chapter": words_per_chapter,
                "total_chapters": total_volumes * chapters_per_volume
            },
            selling_points=data.get('selling_points', []),
            main_conflicts=data.get('main_conflicts', {
                "external": [],
                "internal": [],
                "deep_theme": []
            }),
            creation_principles=data.get('creation_principles', {}),
            key_reversals=data.get('key_reversals', [])
        )

        # 构建卷级大纲
        for vol_data in data.get('volumes', []):
            volume = VolumeOutline(
                volume_id=vol_data.get('volume_id', 1),
                name=vol_data.get('name', f"第{vol_data.get('volume_id', 1)}卷"),
                words=vol_data.get('words', chapters_per_volume * words_per_chapter),
                chapters=vol_data.get('chapters', chapters_per_volume),
                goal=vol_data.get('goal', ''),
                arc=vol_data.get('arc', ''),
                start_end_table=vol_data.get('start_end_table', {}),
                acts=vol_data.get('acts', []),
                chapter_outlines=vol_data.get('chapter_outlines', []),
                character_growth=vol_data.get('character_growth', {}),
                foreshadowing_setup=vol_data.get('foreshadowing_setup', [])
            )
            outline.volumes.append(volume)

        return outline

    def _build_volume_outline_from_data(
        self,
        volume_id: int,
        data: Dict,
        novel_outline: NovelOutline
    ) -> VolumeOutline:
        """从解析数据构建 VolumeOutline"""
        return VolumeOutline(
            volume_id=volume_id,
            name=data.get('name', f"第{volume_id}卷"),
            words=data.get('words', 0),
            chapters=data.get('chapters', 0),
            goal=data.get('goal', ''),
            arc=data.get('arc', ''),
            start_end_table=data.get('start_end_table', {}),
            acts=data.get('acts', []),
            chapter_outlines=data.get('chapter_outlines', []),
            character_growth=data.get('character_growth', {}),
            foreshadowing_setup=data.get('foreshadowing_setup', [])
        )

    def _build_chapter_plan_from_data(
        self,
        chapter_id: int,
        data: Dict
    ) -> ChapterPlan:
        """从解析数据构建 ChapterPlan"""
        return ChapterPlan(
            chapter_id=chapter_id,
            title=data.get('title', f"第{chapter_id}章"),
            theme=data.get('theme', ''),
            plot=data.get('plot', ''),
            scenes=data.get('scenes', []),
            hooks=data.get('hooks', []),
            words_target=data.get('words_target', 3000),
            characters_involved=data.get('characters_involved', []),
            key_events=data.get('key_events', []),
            foreshadowing=data.get('foreshadowing', [])
        )

    # ========== 基础结构（无 LLM 时）==========

    def _create_basic_outline(
        self,
        title: str,
        genre: str,
        total_words: int,
        total_volumes: int,
        chapters_per_volume: int,
        words_per_chapter: int
    ) -> NovelOutline:
        """创建基础大纲结构"""
        outline = NovelOutline(
            title=title,
            meta={
                "type": genre,
                "total_words": total_words,
                "total_volumes": total_volumes,
                "chapters_per_volume": chapters_per_volume,
                "words_per_chapter": words_per_chapter,
                "total_chapters": total_volumes * chapters_per_volume
            }
        )

        # 为每卷创建基础结构
        for i in range(1, total_volumes + 1):
            volume = VolumeOutline(
                volume_id=i,
                name=f"第{i}卷",
                words=chapters_per_volume * words_per_chapter,
                chapters=chapters_per_volume,
                goal=f"第{i}卷的故事目标",
                arc=f"起始状态 → 结束状态"
            )
            outline.volumes.append(volume)

        return outline

    def _create_basic_volume(
        self,
        volume_id: int,
        novel_outline: NovelOutline
    ) -> VolumeOutline:
        """创建基础卷级大纲"""
        chapters_per_volume = novel_outline.meta.get('chapters_per_volume', 30)
        words_per_chapter = novel_outline.meta.get('words_per_chapter', 3000)

        return VolumeOutline(
            volume_id=volume_id,
            name=f"第{volume_id}卷",
            words=chapters_per_volume * words_per_chapter,
            chapters=chapters_per_volume,
            goal=f"第{volume_id}卷的故事目标",
            arc="起始状态 → 结束状态"
        )

    def _create_basic_chapter(
        self,
        chapter_id: int,
        volume_outline: VolumeOutline
    ) -> ChapterPlan:
        """创建基础章级计划"""
        return ChapterPlan(
            chapter_id=chapter_id,
            title=f"第{chapter_id}章",
            theme="",
            plot="",
            words_target=3000
        )

    # ========== 工具方法 ==========

    def _parse_json(self, text: str) -> Dict:
        """解析 JSON（带错误修复）"""
        text = text.strip()

        # 找到 JSON 部分
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end+1]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 简单修复
            text = text.replace("'", '"')
            text = re.sub(r',\s*([}\]])', r'\1', text)
            try:
                return json.loads(text)
            except:
                return {}

    def _format_characters(self, characters: List[Any]) -> str:
        """格式化角色列表为字符串"""
        if not characters:
            return "无"

        parts = []
        for char in characters[:10]:  # 限制前10个
            if hasattr(char, 'name'):
                parts.append(f"- {char.name}")
            elif isinstance(char, dict):
                parts.append(f"- {char.get('name', '未知')}")
            else:
                parts.append(f"- {str(char)}")

        return "\n".join(parts)

    def to_json(self, outline: NovelOutline) -> Dict:
        """转换为大纲 JSON"""
        return {
            "title": outline.title,
            "meta": outline.meta,
            "selling_points": outline.selling_points,
            "main_conflicts": outline.main_conflicts,
            "volumes": [
                {
                    "volume_id": v.volume_id,
                    "name": v.name,
                    "words": v.words,
                    "chapters": v.chapters,
                    "goal": v.goal,
                    "arc": v.arc,
                    "start_end_table": v.start_end_table,
                    "acts": v.acts,
                    "chapter_outlines": v.chapter_outlines,
                    "character_growth": v.character_growth,
                    "foreshadowing_setup": v.foreshadowing_setup
                }
                for v in outline.volumes
            ],
            "creation_principles": outline.creation_principles,
            "key_reversals": outline.key_reversals
        }

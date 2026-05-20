"""
StoryForge - IP 生成器

职责：
1. 为每个角色生成完整的 IP 档案（外貌、性格、经典语录、成长弧线）
2. 生成关系图谱（人物关系矩阵、关系演变）
3. 生成场景设定集（关键场景详细描述、视觉参考）
4. 生成衍生设定（道具、法术、势力、世界观补充）
5. 生成故事 bible 文档
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
import json
import os
from datetime import datetime

from core.models.ip import (
    CharacterIP,
    RelationshipEdge,
    SceneSetting,
    DerivedSetting,
    StoryBible,
)


class IPGenerator:
    """
    IP 生成器

    工作流程：
    1. 聚合所有已完成章节
    2. 为每个角色生成完整 IP 档案
    3. 构建关系图谱
    4. 生成关键场景设定
    5. 收集衍生设定
    6. 输出 Story Bible
    """

    def __init__(
        self,
        llm_client: Callable = None,
        output_dir: str = "./ip_assets"
    ):
        self.llm_client = llm_client
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(
        self,
        title: str,
        chapters: Dict[int, str],
        chapter_analyses: Optional[Dict[int, Any]] = None,
        existing_characters: Optional[List[Dict]] = None
    ) -> StoryBible:
        """
        生成完整 IP 资产

        Args:
            title: 小说标题
            chapters: 章节内容 {章节号: 内容}
            chapter_analyses: 知识萃取结果（可选）
            existing_characters: 已有人物设定（可选）
        """
        print(f"🎨 开始生成 IP 资产...")

        # 1. 创建 Story Bible
        bible = StoryBible(
            title=title,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )

        # 2. 生成故事核心信息
        if self.llm_client:
            self._generate_story_core(bible, chapters)

        # 3. 生成人物 IP
        print("  👤 生成人物 IP...")
        if self.llm_client:
            bible.characters = self._generate_character_ips(
                chapters, chapter_analyses, existing_characters
            )

        # 4. 生成关系图谱
        print("  🔗 生成关系图谱...")
        if self.llm_client:
            bible.relationships = self._generate_relationship_graph(
                bible.characters, chapters
            )

        # 5. 生成关键场景设定
        print("  🎬 生成关键场景设定...")
        if self.llm_client:
            bible.key_scenes = self._generate_scene_settings(chapters)

        # 6. 生成衍生设定
        print("  ✨ 生成衍生设定...")
        if self.llm_client:
            bible.derived_settings = self._generate_derived_settings(
                chapters, chapter_analyses
            )

        # 7. 生成章节摘要
        print("  📝 生成章节摘要...")
        bible.chapter_summaries = self._generate_chapter_summaries(chapters)

        # 8. 保存
        self._save_bible(bible)

        print(f"  ✅ IP 生成完成！共 {len(bible.characters)} 个人物，"
              f"{len(bible.key_scenes)} 个场景，"
              f"{len(bible.derived_settings)} 个衍生设定")

        return bible

    def _generate_story_core(self, bible: StoryBible, chapters: Dict[int, str]):
        """生成故事核心信息（logline、主题等）"""
        if not self.llm_client:
            return

        # 聚合内容
        sample_content = self._sample_chapters(chapters, max_chars=5000)

        prompt = f"""你是一位 IP 策划专家。请根据以下小说内容，生成核心设定。

【小说内容样例】
{sample_content}

【任务】
请生成以下内容，以 JSON 格式返回：

{{
    "logline": "一句话梗概（30-50字）",
    "core_concept": "核心概念说明（100-200字）",
    "themes": ["主题1", "主题2", "主题3"],
    "tone": "整体基调（如"严肃"、"轻松"、"悬疑"等）",
    "world_overview": "世界观概述（200-300字）"
}}

只输出 JSON，不包含其他说明：
"""

        try:
            result = self.llm_client(prompt, temperature=0.4)
            data = self._parse_json(result)

            bible.logline = data.get('logline', '')
            bible.core_concept = data.get('core_concept', '')
            bible.themes = data.get('themes', [])
            bible.tone = data.get('tone', '')
            bible.world_overview = data.get('world_overview', '')

        except Exception as e:
            print(f"    ⚠️ 生成故事核心失败: {e}")

    def _generate_character_ips(
        self,
        chapters: Dict[int, str],
        chapter_analyses: Optional[Dict[int, Any]],
        existing_characters: Optional[List[Dict]]
    ) -> List[CharacterIP]:
        """生成人物 IP 档案"""
        if not self.llm_client:
            return []

        # 1. 先提取所有角色名
        character_names = self._extract_all_character_names(chapters, chapter_analyses)

        if existing_characters:
            for char in existing_characters:
                name = char.get('name', '')
                if name and name not in character_names:
                    character_names.append(name)

        if not character_names:
            print("    ⚠️ 未发现任何人物")
            return []

        print(f"    发现 {len(character_names)} 个人物")

        # 2. 逐个生成 IP
        character_ips = []
        sample_content = self._sample_chapters(chapters, max_chars=8000)

        for i, name in enumerate(character_names[:10]):  # 限制最多10个主要角色
            print(f"    生成 {name} 的 IP ({i+1}/{min(len(character_names), 10)})...")
            char_ip = self._generate_single_character_ip(name, sample_content)
            if char_ip:
                character_ips.append(char_ip)

        return character_ips

    def _generate_single_character_ip(
        self,
        character_name: str,
        sample_content: str
    ) -> Optional[CharacterIP]:
        """为单个角色生成 IP"""
        prompt = f"""你是一位人物 IP 策划专家。请根据以下小说内容，为 "{character_name}" 生成完整的人物档案。

【小说内容样例】
{sample_content}

【任务】
请为 "{character_name}" 生成详细的人物档案，以 JSON 格式返回：

{{
    "character_id": "拼音标识（如 zhang_san）",
    "name": "{character_name}",
    "role": "角色定位（protagonist|supporting|antagonist|cameo）",
    "appearance": {{
        "basic": "基本外貌描述",
        "face": "面部特征",
        "clothing": "服饰特点",
        "posture": "姿态/气质",
        "visual_tags": ["视觉关键词1", "视觉关键词2", "视觉关键词3"]
    }},
    "personality": {{
        "core": "核心性格",
        "traits": ["性格特质1", "特质2", "特质3"],
        "strengths": ["优点1", "优点2"],
        "weaknesses": ["缺点1", "缺点2"],
        "fears": ["恐惧1"],
        "motivations": ["动机1"]
    }},
    "background": "背景故事",
    "character_arc": {{
        "start": "初始状态",
        "end": "最终状态",
        "key_moments": ["关键时刻1", "关键时刻2"]
    }},
    "famous_quotes": ["经典语录1（如果有）", "经典语录2"],
    "tags": ["标签1", "标签2", "标签3"],
    "first_appearance": 1,
    "last_appearance": 1
}}

只输出 JSON，不包含其他说明：
"""

        try:
            result = self.llm_client(prompt, temperature=0.4)
            data = self._parse_json(result)

            # 构建 CharacterIP
            return CharacterIP(
                character_id=data.get('character_id', character_name),
                name=data.get('name', character_name),
                role=data.get('role', 'supporting'),
                appearance=data.get('appearance', {}),
                personality=data.get('personality', {}),
                background=data.get('background', ''),
                character_arc=data.get('character_arc', {}),
                famous_quotes=data.get('famous_quotes', []),
                tags=data.get('tags', []),
                first_appearance=data.get('first_appearance', 1),
                last_appearance=data.get('last_appearance', 1)
            )

        except Exception as e:
            print(f"      ⚠️ 生成 {character_name} IP 失败: {e}")
            return None

    def _generate_relationship_graph(
        self,
        characters: List[CharacterIP],
        chapters: Dict[int, str]
    ) -> List[RelationshipEdge]:
        """生成关系图谱"""
        if not self.llm_client or len(characters) < 2:
            return []

        sample_content = self._sample_chapters(chapters, max_chars=6000)
        char_list_str = "\n".join([f"- {c.name} ({c.role})" for c in characters])

        prompt = f"""你是一位人物关系分析专家。请根据以下内容，分析人物关系。

【人物列表】
{char_list_str}

【小说内容样例】
{sample_content}

【任务】
请分析上述人物之间的关系，以 JSON 格式返回：

{{
    "relationships": [
        {{
            "source": "人物 A 的 name",
            "target": "人物 B 的 name",
            "relation_type": "关系类型（friend|enemy|family|romantic|mentor|rival）",
            "description": "关系详细描述",
            "intensity": 5
        }}
    ]
}}

只输出 JSON，不包含其他说明：
"""

        try:
            result = self.llm_client(prompt, temperature=0.3)
            data = self._parse_json(result)

            edges = []
            for rel_data in data.get('relationships', []):
                edges.append(RelationshipEdge(
                    source=rel_data.get('source', ''),
                    target=rel_data.get('target', ''),
                    relation_type=rel_data.get('relation_type', 'friend'),
                    description=rel_data.get('description', ''),
                    intensity=rel_data.get('intensity', 5)
                ))

            return edges

        except Exception as e:
            print(f"    ⚠️ 生成关系图谱失败: {e}")
            return []

    def _generate_scene_settings(
        self,
        chapters: Dict[int, str]
    ) -> List[SceneSetting]:
        """生成关键场景设定"""
        if not self.llm_client:
            return []

        sample_content = self._sample_chapters(chapters, max_chars=8000)

        prompt = f"""你是一位场景设计专家。请从以下小说内容中提取关键场景。

【小说内容样例】
{sample_content}

【任务】
请提取 3-5 个最关键的场景，以 JSON 格式返回：

{{
    "scenes": [
        {{
            "scene_id": "场景标识",
            "name": "场景名称",
            "location": "地点",
            "chapter": 1,
            "description": "场景详细描述",
            "atmosphere": "氛围描述",
            "visual_references": ["视觉参考1", "视觉参考2"],
            "significance": "场景重要性说明",
            "props_in_scene": ["关键道具1", "关键道具2"],
            "characters_present": ["在场角色1", "在场角色2"]
        }}
    ]
}}

只输出 JSON，不包含其他说明：
"""

        try:
            result = self.llm_client(prompt, temperature=0.4)
            data = self._parse_json(result)

            scenes = []
            for scene_data in data.get('scenes', []):
                scenes.append(SceneSetting(
                    scene_id=scene_data.get('scene_id', ''),
                    name=scene_data.get('name', ''),
                    location=scene_data.get('location', ''),
                    chapter=scene_data.get('chapter', 1),
                    description=scene_data.get('description', ''),
                    atmosphere=scene_data.get('atmosphere', ''),
                    visual_references=scene_data.get('visual_references', []),
                    significance=scene_data.get('significance', ''),
                    props_in_scene=scene_data.get('props_in_scene', []),
                    characters_present=scene_data.get('characters_present', [])
                ))

            return scenes

        except Exception as e:
            print(f"    ⚠️ 生成场景设定失败: {e}")
            return []

    def _generate_derived_settings(
        self,
        chapters: Dict[int, str],
        chapter_analyses: Optional[Dict[int, Any]]
    ) -> List[DerivedSetting]:
        """生成衍生设定（道具、法术、势力等）"""
        if not self.llm_client:
            return []

        sample_content = self._sample_chapters(chapters, max_chars=6000)

        prompt = f"""你是一位世界观设定专家。请从以下小说内容中提取衍生设定。

【小说内容样例】
{sample_content}

【任务】
请提取重要的衍生设定（道具、法术、势力、生物、规则等），以 JSON 格式返回：

{{
    "settings": [
        {{
            "setting_type": "类型（item|spell|faction|creature|rule）",
            "name": "名称",
            "description": "详细描述",
            "origin": "来源/起源",
            "properties": {{"key": "value"}},
            "related_characters": ["相关角色1"],
            "first_appearance": 1,
            "tags": ["标签1"]
        }}
    ]
}}

只输出 JSON，不包含其他说明：
"""

        try:
            result = self.llm_client(prompt, temperature=0.4)
            data = self._parse_json(result)

            settings = []
            for setting_data in data.get('settings', []):
                settings.append(DerivedSetting(
                    setting_type=setting_data.get('setting_type', 'item'),
                    name=setting_data.get('name', ''),
                    description=setting_data.get('description', ''),
                    origin=setting_data.get('origin', ''),
                    properties=setting_data.get('properties', {}),
                    related_characters=setting_data.get('related_characters', []),
                    first_appearance=setting_data.get('first_appearance', 1),
                    tags=setting_data.get('tags', [])
                ))

            return settings

        except Exception as e:
            print(f"    ⚠️ 生成衍生设定失败: {e}")
            return []

    def _generate_chapter_summaries(self, chapters: Dict[int, str]) -> Dict[int, str]:
        """生成章节摘要（简单版，不调用 LLM 避免耗时）"""
        summaries = {}

        for chapter_num, content in chapters.items():
            # 简单截取前 100 字符作为摘要
            # 生产环境可以用 LLM 生成更优美的摘要
            summaries[chapter_num] = content[:100].strip() + "..."

        return summaries

    def _sample_chapters(self, chapters: Dict[int, str], max_chars: int = 5000) -> str:
        """从多个章节中采样内容"""
        sampled_parts = []
        total_length = 0

        # 按顺序采样
        for chapter_num in sorted(chapters.keys()):
            content = chapters[chapter_num]
            part = f"\n=== 第{chapter_num}章 ===\n{content}"

            if total_length + len(part) <= max_chars:
                sampled_parts.append(part)
                total_length += len(part)
            else:
                # 取部分内容填满
                remaining = max_chars - total_length
                if remaining > 100:
                    sampled_parts.append(f"\n=== 第{chapter_num}章 ===\n{content[:remaining]}")
                break

        return "".join(sampled_parts)

    def _extract_all_character_names(
        self,
        chapters: Dict[int, str],
        chapter_analyses: Optional[Dict[int, Any]]
    ) -> List[str]:
        """提取所有出现的角色名"""
        names = set()

        # 从分析结果中提取
        if chapter_analyses:
            for analysis in chapter_analyses.values():
                if hasattr(analysis, 'new_characters'):
                    for char in analysis.new_characters:
                        names.add(char.name)
                if hasattr(analysis, 'events'):
                    for event in analysis.events:
                        if isinstance(event, dict):
                            names.update(event.get('characters_involved', []))
                        else:
                            names.update(getattr(event, 'characters_involved', []))

        # 如果没有分析结果或结果太少，用简单启发式
        if len(names) < 3 and self.llm_client:
            sample = self._sample_chapters(chapters, max_chars=3000)
            names.update(self._extract_names_with_llm(sample))

        return sorted(list(names))

    def _extract_names_with_llm(self, sample_content: str) -> List[str]:
        """用 LLM 提取角色名"""
        prompt = f"""请从以下文本中提取所有人物姓名，只返回 JSON 列表：

{sample_content}

输出格式：{{"names": ["姓名1", "姓名2"]}}
"""

        try:
            result = self.llm_client(prompt, temperature=0.1)
            data = self._parse_json(result)
            return data.get('names', [])
        except:
            return []

    def _parse_json(self, text: str) -> Dict:
        """解析 JSON（带错误修复）"""
        import re
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

    def _save_bible(self, bible: StoryBible):
        """保存 Story Bible 到文件"""
        bible_path = os.path.join(self.output_dir, f"{bible.title}_story_bible.json")

        # 使用 BaseModel 的 to_dict 方法
        try:
            bible_dict = bible.to_dict()
            with open(bible_path, 'w', encoding='utf-8') as f:
                json.dump(bible_dict, f, ensure_ascii=False, indent=2)
            print(f"  💾 Story Bible 已保存: {bible_path}")
        except Exception as e:
            print(f"  ⚠️ 保存 Story Bible 失败: {e}")

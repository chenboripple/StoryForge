"""
StoryForge - Outline Generator
从卷纲生成章级细纲
"""
from typing import Dict, Optional, Any, Callable, List
import json
import re


class OutlineGenerator:
    """
    Outline Generator

    职责：
    1. 从卷纲生成章级细纲
    """

    def __init__(self, llm_client: Callable = None):
        self.llm_client = llm_client

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

        prompt = f"""你是一位小说大纲专家。请为以下小说生成第{current_chapter}章的详细写作计划。

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

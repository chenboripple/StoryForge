"""Progressive planners for volume briefs and chapter briefs."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import json
import re


class ProgressivePlanner:
    """Generates hierarchical planning artifacts with LLM + fallback."""

    def __init__(self, llm_client: Optional[Callable] = None):
        self.llm_client = llm_client

    def generate_volume_brief(
        self,
        book_outline: str,
        volume_id: int,
        current_chapter: int,
        existing_brief: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.llm_client:
            return self._fallback_volume_brief(book_outline, volume_id, current_chapter, existing_brief)

        prompt = f"""你是小说策划编辑。请根据全书大纲，产出第{volume_id}卷的卷纲摘要。

【全书大纲】
{book_outline[:4000]}

【当前章节】
第{current_chapter}章

请输出 JSON：
{{
  "volume_id": {volume_id},
  "goal": "本卷目标",
  "core_conflict": "核心冲突",
  "milestones": ["里程碑1", "里程碑2", "里程碑3"],
  "chapter_span": "本卷预计章节范围，如1-10",
  "summary": "本卷摘要（200字内）"
}}
仅输出 JSON。
"""
        try:
            raw = self.llm_client(prompt, temperature=0.4)
            data = self._parse_json(raw)
            if data:
                return data
        except Exception:
            pass

        return self._fallback_volume_brief(book_outline, volume_id, current_chapter, existing_brief)

    def generate_chapter_brief(
        self,
        book_outline: str,
        volume_brief: Dict[str, Any],
        chapter_id: int,
        target_words: int = 3000,
        neighbors: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        neighbors = neighbors or []
        if not self.llm_client:
            return self._fallback_chapter_brief(book_outline, volume_brief, chapter_id, target_words, neighbors)

        prompt = f"""你是章节策划编辑。请生成第{chapter_id}章章节概述。

【全书大纲】
{book_outline[:2500]}

【卷纲摘要】
{volume_brief}

【邻近章节概述】
{neighbors[:4]}

请输出 JSON：
{{
  "chapter_id": {chapter_id},
  "title": "章节标题",
  "theme": "本章主题",
  "plot": "本章情节概述（150-250字）",
  "scenes": ["场景1", "场景2", "场景3"],
  "hooks": ["钩子1", "钩子2"],
  "characters_involved": ["角色A", "角色B"],
  "constraints": ["必须满足的约束1", "约束2"],
  "words_target": {target_words}
}}
仅输出 JSON。
"""
        try:
            raw = self.llm_client(prompt, temperature=0.5)
            data = self._parse_json(raw)
            if data:
                return data
        except Exception:
            pass

        return self._fallback_chapter_brief(book_outline, volume_brief, chapter_id, target_words, neighbors)

    def _fallback_volume_brief(
        self,
        book_outline: str,
        volume_id: int,
        current_chapter: int,
        existing_brief: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        chapter_start = (volume_id - 1) * 10 + 1
        chapter_end = volume_id * 10
        base = {
            "volume_id": volume_id,
            "goal": f"推进主线并完成第{volume_id}卷阶段目标",
            "core_conflict": "主角目标与外部阻力持续升级",
            "milestones": [
                "引入本卷关键冲突",
                "中段发生不可逆转折",
                "卷末形成新悬念",
            ],
            "chapter_span": f"{chapter_start}-{chapter_end}",
            "summary": (book_outline or "").strip()[:220],
            "current_chapter": current_chapter,
        }
        if isinstance(existing_brief, dict):
            base.update({k: v for k, v in existing_brief.items() if v})
        return base

    def _fallback_chapter_brief(
        self,
        book_outline: str,
        volume_brief: Dict[str, Any],
        chapter_id: int,
        target_words: int,
        neighbors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "chapter_id": chapter_id,
            "title": f"第{chapter_id}章",
            "theme": volume_brief.get("goal", "阶段推进")[:40],
            "plot": (book_outline or "").strip()[:220],
            "scenes": [
                "开场建立局面并承接上章",
                "冲突升级并暴露关键问题",
                "结尾抛出新悬念",
            ],
            "hooks": ["冲突悬念", "关系悬念"],
            "characters_involved": self._neighbors_characters(neighbors),
            "constraints": [
                "保持人物动机一致",
                "不得破坏卷级里程碑",
            ],
            "words_target": target_words,
        }

    def _neighbors_characters(self, neighbors: List[Dict[str, Any]]) -> List[str]:
        names: List[str] = []
        for item in neighbors:
            brief = item.get("brief", {}) if isinstance(item, dict) else {}
            chars = brief.get("characters_involved", [])
            for c in chars:
                if isinstance(c, str) and c not in names:
                    names.append(c)
        return names[:6]

    def _parse_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        raw = str(text).strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            raw = raw.replace("'", '"')
            raw = re.sub(r",\s*([}\]])", r"\1", raw)
            try:
                return json.loads(raw)
            except Exception:
                return {}

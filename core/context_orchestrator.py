"""Progressive disclosure context orchestration for agent prompts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


class ContextOrchestrator:
	"""Builds minimal default context and escalates when needed."""

	DEFAULT_BUDGETS = {
		"writer": 12000,
		"reviewer": 14000,
		"reviser": 14000,
		"proofreader": 14000,
	}

	def build_writer_bundle(self, state: Any, memory_context: str = "") -> Dict[str, Any]:
		chapter = getattr(state, "current_chapter", 1)
		budget = self._get_budget(state, "writer")
		chapter_brief = self._get_chapter_brief(state, chapter)
		neighbors = self._neighbor_briefs(state, chapter, window=2)
		messages = self._messages_text(state, chapter, limit=5)

		relevant_chars = self._select_related_characters(
			state,
			seeds=[chapter_brief.get("plot", ""), chapter_brief.get("theme", "")],
			limit=6,
		)

		sections: List[Tuple[str, str]] = [
			("novel_meta", self._novel_meta(state)),
			("chapter_brief", self._fmt("当前章节概述", chapter_brief)),
			("neighbor_briefs", self._fmt("前后章节概述", neighbors)),
			("relevant_characters", self._fmt_characters(relevant_chars)),
			("agent_messages", messages),
			("memory_context", memory_context or ""),
		]

		escalated = False
		# Trigger escalation on repeated review rounds.
		if getattr(state, "review_round", 0) >= 2:
			prev_excerpt = self._chapter_excerpt(state, chapter - 1, size=900)
			sections.append(("previous_chapter_excerpt", self._fmt("前章正文片段", prev_excerpt)))
			escalated = bool(prev_excerpt)

		context, loaded, used_chars = self._budget_join(sections, budget)
		self._record_decision(state, "writer", chapter, loaded, escalated, budget, used_chars)

		return {
			"context": context,
			"chapter_plan": chapter_brief,
			"memory_context": "",
			"characters": relevant_chars,
			"loaded_sections": loaded,
			"escalated": escalated,
		}

	def build_reviewer_bundle(self, state: Any, chapter_text: str) -> Dict[str, Any]:
		chapter = getattr(state, "current_chapter", 1)
		budget = self._get_budget(state, "reviewer")
		chapter_brief = self._get_chapter_brief(state, chapter)
		prev_excerpt = self._chapter_excerpt(state, chapter - 1, size=800)
		messages = self._messages_text(state, chapter, limit=5)

		relevant_chars = self._select_related_characters(
			state,
			seeds=[chapter_text[:1200], chapter_brief.get("plot", "")],
			limit=8,
		)

		sections: List[Tuple[str, str]] = [
			("chapter_brief", self._fmt("章节概述", chapter_brief)),
			("previous_chapter_excerpt", self._fmt("前章结尾", prev_excerpt)),
			("relevant_characters", self._fmt_characters(relevant_chars)),
			("agent_messages", messages),
		]

		escalated = False
		if len(chapter_text) > budget * 0.75:
			# If chapter is very long, keep full text but drop low-priority sections by budget join.
			escalated = True

		context, loaded, used_chars = self._budget_join(sections, budget)
		self._record_decision(state, "reviewer", chapter, loaded, escalated, budget, used_chars)

		return {
			"context": context,
			"chapter_content": chapter_text,
			"chapter_plan": chapter_brief,
			"characters": relevant_chars,
			"previous_chapter": prev_excerpt,
			"loaded_sections": loaded,
			"escalated": escalated,
		}

	def build_reviser_bundle(
		self,
		state: Any,
		chapter_text: str,
		latest_review: Any,
		structured_review: Any,
	) -> Dict[str, Any]:
		chapter = getattr(state, "current_chapter", 1)
		budget = self._get_budget(state, "reviser")
		chapter_brief = self._get_chapter_brief(state, chapter)
		messages = self._messages_text(state, chapter, limit=6)

		review_summary = getattr(latest_review, "comments", "") if latest_review else ""
		actionable = self._structured_issues(structured_review)

		sections: List[Tuple[str, str]] = [
			("chapter_content", self._fmt("当前章节正文", chapter_text[:4500])),
			("chapter_brief", self._fmt("章节概述", chapter_brief)),
			("review_summary", self._fmt("审稿摘要", review_summary)),
			("actionable_issues", self._fmt("必须修改项", actionable)),
			("agent_messages", messages),
		]

		escalated = bool(actionable)
		context, loaded, used_chars = self._budget_join(sections, budget)
		self._record_decision(state, "reviser", chapter, loaded, escalated, budget, used_chars)

		return {
			"context": context,
			"chapter_plan": chapter_brief,
			"memory_context": "",
			"loaded_sections": loaded,
			"escalated": escalated,
		}

	def build_proofreader_bundle(self, state: Any, chapter_text: str) -> Dict[str, Any]:
		chapter = getattr(state, "current_chapter", 1)
		budget = self._get_budget(state, "proofreader")
		chapter_brief = self._get_chapter_brief(state, chapter)
		messages = self._messages_text(state, chapter, limit=5)

		relevant_chars = self._select_related_characters(
			state,
			seeds=[chapter_text[:1500], chapter_brief.get("plot", "")],
			limit=8,
		)
		scope = getattr(state, "proofread_scope", "chapter")
		proofread_context = getattr(state, "proofread_context", {}) or {}

		project_docs = None
		escalated = False
		if scope == "project_docs":
			project_docs = self._limited_project_docs(proofread_context)
			escalated = True

		sections: List[Tuple[str, str]] = [
			("chapter_brief", self._fmt("章节概述", chapter_brief)),
			("relevant_characters", self._fmt_characters(relevant_chars)),
			("agent_messages", messages),
			("project_docs", self._fmt("综合项目文档", project_docs) if project_docs else ""),
		]

		context, loaded, used_chars = self._budget_join(sections, budget)
		self._record_decision(state, "proofreader", chapter, loaded, escalated, budget, used_chars)

		return {
			"context": context,
			"chapter_content": chapter_text,
			"chapter_plan": chapter_brief,
			"characters": relevant_chars,
			"world_setting": proofread_context.get("world_setting"),
			"project_docs": project_docs,
			"scope": scope,
			"loaded_sections": loaded,
			"escalated": escalated,
		}

	def _get_budget(self, state: Any, agent_name: str) -> int:
		budgets = getattr(state, "context_budgets", {}) or {}
		return int(budgets.get(agent_name, self.DEFAULT_BUDGETS[agent_name]))

	def _get_chapter_brief(self, state: Any, chapter: int) -> Dict[str, Any]:
		if hasattr(state, "get_chapter_brief"):
			brief = state.get_chapter_brief(chapter)
			if isinstance(brief, dict):
				return brief
		if hasattr(state, "creation") and isinstance(state.creation, dict):
			outlines = state.creation.get("chapter_outlines", {})
			if isinstance(outlines, dict):
				return outlines.get(chapter, {}) or outlines.get(str(chapter), {}) or {}
		return {}

	def _neighbor_briefs(self, state: Any, chapter: int, window: int = 2) -> List[Dict[str, Any]]:
		out: List[Dict[str, Any]] = []
		for c in range(max(1, chapter - window), chapter + window + 1):
			if c == chapter:
				continue
			brief = self._get_chapter_brief(state, c)
			if brief:
				out.append({"chapter": c, "brief": brief})
		return out

	def _chapter_excerpt(self, state: Any, chapter: int, size: int = 800) -> str:
		if chapter <= 0:
			return ""
		chapters = getattr(state, "chapters", {}) or {}
		if chapter not in chapters:
			return ""
		obj = chapters[chapter]
		text = getattr(obj, "text", obj)
		if not isinstance(text, str):
			text = str(text)
		return text[-size:]

	def _messages_text(self, state: Any, chapter: int, limit: int = 5) -> str:
		if not hasattr(state, "get_agent_messages"):
			return ""
		messages = state.get_agent_messages(chapter=chapter, limit=limit)
		if not messages:
			return ""
		lines = ["【来自其他 Agent 的反馈】"]
		for m in messages:
			sender = m.get("sender", "未知")
			msg_type = m.get("msg_type", "info")
			content = (m.get("content", "") or "")[:200]
			lines.append(f"[{sender}] {msg_type}: {content}")
		return "\n".join(lines)

	def _select_related_characters(self, state: Any, seeds: List[str], limit: int = 6) -> List[Any]:
		all_chars = list(getattr(state, "characters", []) or [])
		if not all_chars:
			return []
		merged_seed = "\n".join(s for s in seeds if s)
		if not merged_seed:
			return all_chars[:limit]

		selected = []
		for c in all_chars:
			name = getattr(c, "name", "")
			if name and name in merged_seed:
				selected.append(c)
		if not selected:
			selected = all_chars[:limit]
		return selected[:limit]

	def _structured_issues(self, structured_review: Any) -> List[str]:
		if not structured_review or not hasattr(structured_review, "issues"):
			return []
		issues = []
		for issue in getattr(structured_review, "issues", []):
			sev = str(getattr(issue, "severity", "B")).upper()
			if sev not in {"S", "A", "CRITICAL"}:
				continue
			location = getattr(issue, "location", "")
			desc = getattr(issue, "description", "")
			sugg = getattr(issue, "suggestion", "")
			text = f"[{sev}] {location} {desc}".strip()
			if sugg:
				text = f"{text} | 建议: {sugg}"
			issues.append(text[:220])
		return issues[:12]

	def _limited_project_docs(self, docs: Dict[str, Any]) -> Dict[str, Any]:
		out: Dict[str, Any] = {}
		for key in ["outline", "volume_outline", "timeline", "character_profiles", "worldview"]:
			value = docs.get(key)
			if not value:
				continue
			if isinstance(value, str):
				out[key] = value[:1800]
			else:
				out[key] = value
		return out

	def _novel_meta(self, state: Any) -> str:
		title = getattr(state, "novel_title", "")
		genre = getattr(state, "genre", "")
		chapter = getattr(state, "current_chapter", 1)
		return f"【小说信息】\n标题: {title}\n类型: {genre}\n当前章节: 第{chapter}章"

	def _fmt_characters(self, chars: List[Any]) -> str:
		if not chars:
			return ""
		lines = ["【相关角色画像】"]
		for c in chars:
			name = getattr(c, "name", "未知")
			personality = getattr(c, "personality", "")
			background = getattr(c, "background", "")
			lines.append(f"- {name}: {personality}")
			if background:
				lines.append(f"  背景: {background[:120]}")
		return "\n".join(lines)

	def _fmt(self, title: str, obj: Any) -> str:
		if not obj:
			return ""
		return f"【{title}】\n{obj}"

	def _budget_join(self, sections: List[Tuple[str, str]], budget: int) -> Tuple[str, List[str], int]:
		chunks: List[str] = []
		loaded: List[str] = []
		used = 0
		for name, text in sections:
			if not text:
				continue
			piece = str(text)
			reserve = 2
			if used + len(piece) + reserve > budget:
				remaining = budget - used - reserve
				if remaining > 120:
					piece = piece[:remaining]
					chunks.append(piece)
					loaded.append(f"{name}:truncated")
					used += len(piece) + reserve
				continue
			chunks.append(piece)
			loaded.append(name)
			used += len(piece) + reserve
		return "\n\n".join(chunks), loaded, used

	def _record_decision(
		self,
		state: Any,
		agent: str,
		chapter: int,
		loaded_sections: List[str],
		escalated: bool,
		budget: int,
		used_chars: int,
	):
		if hasattr(state, "record_context_decision"):
			state.record_context_decision(
				agent=agent,
				chapter=chapter,
				loaded_sections=loaded_sections,
				escalated=escalated,
				budget=budget,
				used_chars=used_chars,
			)

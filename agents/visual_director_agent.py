"""视觉导演 Agent：负责封面与角色主图提示词设计，并吸收其他 Agent 的反馈。"""

from __future__ import annotations

from typing import Dict, Optional

from core.agent import AgentPersona, BaseAgent


class VisualDirectorPersona(AgentPersona):
    """插画/原画协同人设。"""

    def __init__(self) -> None:
        super().__init__(
            name="丹青",
            role="视觉导演（插画师/原画师）",
            goal="将小说文本、抽象主题与多 Agent 反馈转化为可执行的高质量视觉提示词",
            backstory="擅长在叙事一致性与视觉冲击力之间取平衡，能将 Writer 与校对反馈落到具体画面语言。",
            expertise=[
                "封面叙事构图",
                "角色主视觉设计",
                "风格统一与可迭代提示词",
                "跨 Agent 反馈融合",
            ],
            tone="审美明确、结构化、可执行",
            principles=[
                "先保证叙事一致性，再追求视觉亮点",
                "角色主图必须强调身份识别",
                "封面必须体现小说冲突与主题",
            ],
            constraints=[
                "输出只给最终提示词本体",
                "避免空泛形容词堆砌",
            ],
        )


class VisualDirectorAgent(BaseAgent):
    """面向封面与角色主图的提示词生成 Agent。"""

    def __init__(self, llm_client=None, memory=None, error_handler=None, message_bus=None, state=None):
        super().__init__(
            persona=VisualDirectorPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=False,
            message_bus=message_bus,
            state=state,
        )

    def invoke(self, state):
        raise NotImplementedError("VisualDirectorAgent uses specialized prompt methods")

    @staticmethod
    def _extract_sections(text: str) -> Dict[str, str]:
        sections: Dict[str, str] = {}
        for raw in str(text or "").splitlines():
            line = raw.strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value and key not in sections:
                sections[key] = value
        return sections

    @staticmethod
    def _take(text: str, n: int = 80) -> str:
        s = str(text or "").strip()
        if len(s) <= n:
            return s
        return s[: n - 1].rstrip() + "..."

    @staticmethod
    def _clean_value(text: str) -> str:
        s = str(text or "").strip()
        if not s:
            return ""
        bad_tokens = {
            "{", "}", "[]", "[", "]", "null", "none", "n/a", "-", "#", "# world.json",
        }
        if s.lower() in bad_tokens:
            return ""
        if s.startswith("#"):
            return ""
        if s.endswith(".json"):
            return ""
        if len(s) <= 2 and any(ch in s for ch in "{}[]#"):
            return ""
        return s

    @staticmethod
    def _prompt_spec(target: str) -> str:
        if target == "cover":
            return (
                "提示词规范：\n"
                "1) 只输出一段中文提示词，不要解释、不要标题、不要键值对标签。\n"
                "2) 必须包含：主体、场景、构图、光线、材质、色彩、情绪、叙事冲突。\n"
                "3) 用户反馈优先，其次编辑一致性约束，再其次作者创作意图。\n"
                "4) 避免空泛词堆砌，尽量具体、可视化、可执行。"
            )
        return (
            "提示词规范：\n"
            "1) 只输出一段中文提示词，不要解释、不要标题、不要键值对标签。\n"
            "2) 必须包含：角色身份识别特征、外观/服饰、姿态、镜头、光线、质感、氛围。\n"
            "3) 用户反馈优先，其次编辑一致性约束，再其次作者创作意图。\n"
            "4) 提示词应便于主形象一致性延展。"
        )

    def _fallback_cover_prompt(
        self,
        *,
        user_intent: str,
        primary_subject: str,
        world: str,
        theme: str,
        conflict: str,
        consistency: str,
        taboo: str,
        style: str,
    ) -> str:
        core = self._clean_value(user_intent) or primary_subject or "小说核心冲突"
        scene = world or "故事主场景"
        mood = theme or "科幻悬疑氛围"
        style_text = self._clean_value(style) or "电影海报"
        lines = [
            f"{style_text}风格小说封面，主视觉聚焦{self._take(core, 120)}，",
            f"场景设定在{self._take(scene, 100)}，整体呈现{self._take(mood, 80)}，",
            "采用前中后景分层与中心叙事构图，主体清晰，",
            "主光与环境辅光形成对比，强调体积光与材质细节，",
        ]
        if conflict:
            lines.append(f"画面冲突点体现{self._take(conflict, 90)}，")
        if consistency:
            lines.append(f"并保持{self._take(consistency, 80)}，")
        if taboo:
            lines.append(f"避免出现{self._take(taboo, 70)}。")
        else:
            lines.append("突出叙事张力与可读性。")
        return "".join(lines)

    def _fallback_character_prompt(
        self,
        *,
        user_intent: str,
        role_name: str,
        appearance: str,
        clothing: str,
        posture: str,
        vtags: str,
        mood: str,
        consistency: str,
        taboo: str,
        style: str,
    ) -> str:
        core = self._clean_value(user_intent) or role_name or "角色主形象"
        style_text = self._clean_value(style) or "电影级写实"
        lines = [
            f"{style_text}角色主形象，主体为{self._take(core, 100)}，",
            f"突出身份识别与面部辨识度，",
        ]
        if appearance:
            lines.append(f"外观特征体现{self._take(appearance, 90)}，")
        if clothing:
            lines.append(f"服饰设计为{self._take(clothing, 80)}，")
        if posture:
            lines.append(f"姿态表现{self._take(posture, 70)}，")
        if vtags:
            lines.append(f"视觉标签包含{self._take(vtags, 80)}，")
        if mood:
            lines.append(f"融入小说氛围{self._take(mood, 70)}，")
        lines.append("镜头语言清晰，光影层次分明，材质细节可见，")
        if consistency:
            lines.append(f"保持{self._take(consistency, 80)}，")
        if taboo:
            lines.append(f"避免出现{self._take(taboo, 70)}。")
        else:
            lines.append("便于后续一致性扩展。")
        return "".join(lines)

    def design_cover_prompt(
        self,
        *,
        novel_context: str,
        user_intent: str = "",
        style: str = "",
        collaboration_notes: str = "",
    ) -> str:
        task = (
            "请输出一条可直接用于文生图的中文封面提示词。"
            "必须包含：主体、场景、构图、光线、色彩、材质、氛围与叙事冲突。"
            "只输出提示词本体，不要解释。"
        )
        context = (
            f"小说上下文:\n{novel_context}\n\n"
            f"协作反馈(来自 writer/reviewer/proofreader):\n{collaboration_notes or '暂无'}\n\n"
            f"用户意图: {user_intent or '自动生成高质量小说封面'}\n"
            f"风格偏好: {style or '未指定'}"
        )

        if self.llm_client:
            try:
                polished = str(
                    self._call_llm(
                        task=task + "\n\n" + self._prompt_spec("cover"),
                        context=context,
                        json_schema=None,
                    )
                ).strip()
                if polished:
                    return polished
            except Exception:
                pass

        sec = self._extract_sections(novel_context)
        primary_subject = self._clean_value(sec.get("核心概念") or sec.get("大纲核心概念") or sec.get("一句话梗概") or "")
        world = self._clean_value(sec.get("世界观") or sec.get("世界视觉风格") or "")
        theme = self._clean_value(sec.get("主题") or sec.get("基调") or sec.get("类型") or "")

        notes = self._extract_sections(collaboration_notes)
        conflict = self._clean_value(notes.get("叙事冲突", ""))
        consistency = self._clean_value(notes.get("一致性约束", ""))
        taboo = self._clean_value(notes.get("禁忌元素", ""))

        return self._fallback_cover_prompt(
            user_intent=user_intent,
            primary_subject=primary_subject,
            world=world,
            theme=theme,
            conflict=conflict,
            consistency=consistency,
            taboo=taboo,
            style=style,
        )

    def design_character_main_prompt(
        self,
        *,
        novel_context: str,
        character_context: str,
        user_intent: str = "",
        style: str = "",
        collaboration_notes: str = "",
    ) -> str:
        task = (
            "请输出一条可直接用于文生图的中文角色主形象提示词(main)。"
            "必须强调身份识别，包含外观、服饰、姿态、镜头、光线、质感，"
            "并吸收小说主题氛围。只输出提示词本体，不要解释。"
        )
        context = (
            f"小说上下文:\n{novel_context}\n\n"
            f"角色上下文:\n{character_context}\n\n"
            f"协作反馈(来自 writer/reviewer/proofreader):\n{collaboration_notes or '暂无'}\n\n"
            f"用户意图: {user_intent or '自动生成角色主形象提示词'}\n"
            f"风格偏好: {style or '未指定'}"
        )

        if self.llm_client:
            try:
                polished = str(
                    self._call_llm(
                        task=task + "\n\n" + self._prompt_spec("character_main"),
                        context=context,
                        json_schema=None,
                    )
                ).strip()
                if polished:
                    return polished
            except Exception:
                pass

        n_sec = self._extract_sections(novel_context)
        c_sec = self._extract_sections(character_context)
        notes = self._extract_sections(collaboration_notes)

        role_name = self._clean_value(c_sec.get("角色名", ""))
        appearance = self._clean_value(c_sec.get("外貌", ""))
        clothing = self._clean_value(c_sec.get("服饰", ""))
        posture = self._clean_value(c_sec.get("体态", ""))
        vtags = self._clean_value(c_sec.get("视觉标签", ""))
        mood = self._clean_value(n_sec.get("主题") or n_sec.get("基调") or "")
        consistency = self._clean_value(notes.get("一致性约束", ""))
        taboo = self._clean_value(notes.get("禁忌元素", ""))

        return self._fallback_character_prompt(
            user_intent=user_intent,
            role_name=role_name,
            appearance=appearance,
            clothing=clothing,
            posture=posture,
            vtags=vtags,
            mood=mood,
            consistency=consistency,
            taboo=taboo,
            style=style,
        )

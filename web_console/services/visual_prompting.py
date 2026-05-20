"""视觉提示词增强：基于小说上下文和多 Agent 反馈生成封面与主图提示词草稿。"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from agents.visual_director_agent import VisualDirectorAgent
from core.models.agent import AgentMessage
from core.storage import StorageManager


def _clip(text: str, limit: int = 600) -> str:
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "..."


def _looks_like_placeholder(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True

    low = s.lower()
    if low in {"{", "}", "[]", "[", "]", "null", "none", "n/a", "-", "#", "# world.json"}:
        return True
    if low.endswith(".json") or low.endswith(".yaml") or low.endswith(".yml"):
        return True
    if s.startswith("#"):
        return True
    if s.startswith("{") or s.startswith("["):
        # 裸 JSON 结构不能直接作为画面语义。
        return True
    if re.fullmatch(r"[\[\]{}#\-_/\\.\s]+", s):
        return True
    return False


def _extract_json_semantics(text: str) -> str:
    s = str(text or "").strip()
    if not s or (not s.startswith("{") and not s.startswith("[")):
        return ""

    # 先尝试从 JSON 片段中抓关键字段，避免把整段对象当场景。
    picks: list[str] = []
    patterns = [
        r'"title"\s*:\s*"([^"]+)"',
        r'"type"\s*:\s*"([^"]+)"',
        r'"theme"\s*:\s*"([^"]+)"',
        r'"tone"\s*:\s*"([^"]+)"',
        r'"concept"\s*:\s*"([^"]+)"',
        r'"logline"\s*:\s*"([^"]+)"',
        r'"overview"\s*:\s*"([^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, s)
        if not m:
            continue
        value = m.group(1).strip()
        if value and not _looks_like_placeholder(value):
            picks.append(value)
        if len(picks) >= 3:
            break

    if picks:
        return "，".join(picks)
    return ""


def _safe_text(text: Any, limit: int = 600) -> str:
    s = str(text or "").strip()
    if s.startswith("{") or s.startswith("["):
        s = _extract_json_semantics(s)
    if _looks_like_placeholder(s):
        return ""
    # 清理常见的文件名残片，防止被当成画面内容。
    s = re.sub(r"#\s*[\w\-./\\]+\.(json|ya?ml)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\b[\w\-./\\]+\.(json|ya?ml)\b", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip(" ,;；")
    if _looks_like_placeholder(s):
        return ""
    return _clip(s, limit)


def _compact_anchor_subject(text: str) -> str:
    s = _safe_text(text, 120)
    if not s:
        return ""
    parts = [p.strip() for p in re.split(r"[，,;；|/]+", s) if p.strip()]
    if not parts:
        return s
    first = parts[0]
    return _clip(first, 28)


def _compact_anchor_scene(text: str) -> str:
    s = _safe_text(text, 140)
    if not s:
        return ""
    parts = [p.strip() for p in re.split(r"[，,;；|/]+", s) if p.strip()]
    if not parts:
        return _clip(s, 40)

    place_markers = ("城", "塔", "站", "港", "星", "轨道", "基地", "街区", "荒原", "废墟", "神殿", "宫")
    for p in parts:
        if any(m in p for m in place_markers):
            return _clip(p, 40)

    if len(parts) >= 2:
        return _clip(parts[1], 40)
    return _clip(parts[0], 40)


def _join_items(items: Any, limit: int = 6) -> str:
    if not isinstance(items, list):
        return ""
    values = [_safe_text(x, 120) for x in items]
    values = [x for x in values if x]
    if not values:
        return ""
    return "; ".join(values[:limit])


def _find_character(sm: StorageManager, novel_id: str, character_id: str) -> Optional[Any]:
    graph = sm.load_characters(novel_id)
    if not graph or not getattr(graph, "characters", None):
        return None

    cid = str(character_id or "").strip()
    for c in graph.characters:
        c_id = str(getattr(c, "character_id", "") or "").strip()
        c_name = str(getattr(c, "name", "") or "").strip()
        if cid and (cid == c_id or cid == c_name):
            return c
    return None


def _novel_context(sm: StorageManager, novel_id: str) -> str:
    meta = sm.load_novel_meta(novel_id)
    outline = sm.load_outline(novel_id)
    world = sm.load_world(novel_id)

    lines: list[str] = []
    if meta:
        title = _safe_text(meta.novel_title or novel_id, 120) or str(novel_id)
        lines.append(f"小说名: {title}")
        genre = _safe_text(getattr(meta, "genre", ""), 80)
        if genre:
            lines.append(f"类型: {genre}")
        concept = _safe_text(getattr(meta, "concept", ""), 220)
        if concept:
            lines.append(f"核心概念: {concept}")

    if outline:
        logline = _safe_text(getattr(outline, "logline", ""), 220)
        if logline:
            lines.append(f"一句话梗概: {logline}")
        core = _safe_text(getattr(outline, "core_concept", ""), 220)
        if core:
            lines.append(f"大纲核心概念: {core}")
        overall = _safe_text(getattr(outline, "overall_outline", ""), 420)
        if overall:
            lines.append(f"总大纲: {overall}")
        themes = _join_items(getattr(outline, "themes", []), limit=8)
        if themes:
            lines.append(f"主题: {_safe_text(themes, 200)}")
        tone = _safe_text(getattr(outline, "tone", ""), 120)
        if tone:
            lines.append(f"基调: {tone}")

    if world:
        overview = _safe_text(getattr(world, "overview", ""), 260)
        if overview:
            lines.append(f"世界观: {overview}")
        visual_style = _safe_text(getattr(world, "visual_style", ""), 120)
        if visual_style:
            lines.append(f"世界视觉风格: {visual_style}")
        tech = _safe_text(getattr(world, "technology_level", ""), 80)
        if tech:
            lines.append(f"科技水平: {tech}")
        magic = _safe_text(getattr(world, "magic_system", ""), 100)
        if magic:
            lines.append(f"能力体系: {magic}")

    if not lines:
        lines.append(f"小说名: {novel_id}")

    return "\n".join(lines)


def _section_map(text: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        k = key.strip()
        v = _safe_text(value.strip(), 220)
        if k and v and k not in data:
            data[k] = v
    return data


def _pick_first(data: Dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = _safe_text(data.get(key, ""), 200)
        if value:
            return value
    return ""


def _is_abstract_mode(user_prompt: str, style: str) -> bool:
    text = f"{str(user_prompt or '').lower()} {str(style or '').lower()}"
    keywords = ["抽象", "意象", "symbolic", "abstract", "概念化", "几何", "色块", "彩色"]
    return any(k in text for k in keywords)


def _visual_anchors(
    *,
    novel_context: str,
    character_context: str = "",
    user_prompt: str = "",
    target: str,
) -> Dict[str, str]:
    novel = _section_map(novel_context)
    character = _section_map(character_context)

    subject = ""
    if target == "character_main":
        subject = _pick_first(character, ["角色名", "角色定位", "外貌", "视觉标签"]) or "角色主体"
    else:
        subject = _pick_first(novel, ["核心概念", "大纲核心概念", "一句话梗概", "小说名"]) or "故事核心主体"

    scene = _pick_first(novel, ["世界观", "总大纲", "世界视觉风格"]) or "小说关键场景"
    mood = _pick_first(novel, ["基调", "主题", "类型"]) or "强叙事情绪"

    user = str(user_prompt or "").strip()
    if user:
        if not subject or len(subject) < 6:
            subject = user
        if "在" in user or "于" in user or "外太空" in user or "塔" in user:
            scene = user

    subject = _compact_anchor_subject(subject) or ("角色主体" if target == "character_main" else "小说核心意象")
    scene = _compact_anchor_scene(scene) or ("角色关键冲突场景" if target == "character_main" else "故事关键冲突场景")

    if scene == subject:
        alt_scene_src = _pick_first(novel, ["世界观", "总大纲", "一句话梗概"]) or ""
        alt_scene = _compact_anchor_scene(alt_scene_src)
        if alt_scene and alt_scene != subject:
            scene = alt_scene
        elif target == "cover":
            scene = "外层轨道区"
        else:
            scene = "关键冲突现场"
    mood = _safe_text(mood, 60) or "叙事张力"

    return {"subject": subject, "scene": scene, "mood": mood}


def _ensure_concrete(note: str, *, subject: str, scene: str, mood: str, abstract_mode: bool = False) -> str:
    s = _safe_text(note, 260)
    subject = _safe_text(subject, 80)
    scene = _safe_text(scene, 100)
    mood = _safe_text(mood, 60)
    additions: list[str] = []
    if abstract_mode:
        if subject and subject not in s:
            additions.append(f"核心意象围绕{subject}")
        if mood and mood not in s:
            additions.append(f"色彩叙事表达{mood}")
        if "构成" not in s and "几何" not in s and "色块" not in s:
            additions.append("采用抽象构成与层叠色块组织画面")
    else:
        if subject and subject not in s:
            additions.append(f"主体为{subject}")
        if scene and scene not in s:
            additions.append(f"场景位于{scene}")
        if mood and mood not in s:
            additions.append(f"整体情绪为{mood}")
    if not s:
        s = "，".join(additions)
    elif additions:
        s = s.rstrip("。；;，,") + "，" + "，".join(additions)
    if not s.endswith("。"):
        s += "。"
    return _safe_text(s, 260)


def _too_generic(text: str) -> bool:
    s = _safe_text(text, 260)
    if not s:
        return True
    generic_tokens = [
        "叙事冲突主体", "故事核心冲突", "情绪集中", "动作明确", "叙事钩子", "一致性同时成立",
        "画面前景聚焦", "中景交代", "背景保留", "首屏可读", "抽象构成",
    ]
    hit = sum(1 for t in generic_tokens if t in s)
    return len(s) < 48 or hit >= 2


def _rewrite_if_generic(
    text: str,
    *,
    role: str,
    subject: str,
    scene: str,
    mood: str,
    abstract_mode: bool,
) -> str:
    subject = _safe_text(subject, 80) or "小说核心意象"
    scene = _safe_text(scene, 100) or "故事关键冲突场景"
    mood = _safe_text(mood, 60) or "叙事张力"
    if not _too_generic(text):
        return _safe_text(text, 260)

    if abstract_mode:
        if role == "writer":
            return _clip(
                f"以{subject}作为主意象，将其拆成多层半透明色块与断裂线条，"
                f"中心区域形成高亮对撞，边缘以低饱和冷色回收空间，"
                f"让整体情绪稳定落在{mood}，并保留故事推进的压迫感。",
                260,
            )
        if role == "proofreader":
            return _clip(
                f"保持{subject}意象语义一致，不混入与设定无关符号；"
                f"主色与辅色按冲突强弱分层，避免装饰性噪点遮蔽主题，"
                f"整体维持{mood}的叙事方向。",
                260,
            )
        return _clip(
            f"最终方案以{subject}意象为中心核，采用非对称构成与层叠色域，"
            f"用一处高能亮色做叙事爆点，其余区域用克制色温托住{mood}，"
            "形成可读且可延展的封面主视觉。",
            260,
        )

    if role == "writer":
        return _clip(
            f"画面设定在{scene}，{subject}占据前景三分之二区域，"
            "身体朝向冲突源，手部或关键道具形成明确动作线；"
            f"背景出现与剧情相关的秩序崩解痕迹，整体情绪为{mood}。",
            260,
        )
    if role == "proofreader":
        return _clip(
            f"场景限定在{scene}的设定边界内，前景仅保留{subject}与核心冲突道具，"
            "中景交代规则系统，背景删除无关现代符号；"
            f"光色收束到{mood}对应的主辅对比，避免视觉叙事跑题。",
            260,
        )
    return _clip(
        f"最终画面以{subject}为视觉锚点，地点明确为{scene}；"
        "构图采用前压后透的层次组织，主体受主光切割形成高反差轮廓，"
        f"辅以环境体积光强化{mood}，并把冲突信息集中在首屏可读区域。",
        260,
    )


def _character_context(sm: StorageManager, novel_id: str, character_id: str) -> str:
    char = _find_character(sm, novel_id, character_id)
    if not char:
        return f"角色ID: {character_id}"

    lines = [
        f"角色ID: {_safe_text(getattr(char, 'character_id', ''), 60) or str(character_id)}",
        f"角色名: {_safe_text(getattr(char, 'name', ''), 60) or str(character_id)}",
        f"角色定位: {_safe_text(getattr(char, 'role', ''), 60) or 'supporting'}",
    ]

    for key, label, limit in [
        ("appearance", "外貌", 180),
        ("personality", "性格", 180),
        ("background", "背景", 240),
        ("face_description", "面部特征", 120),
        ("clothing_style", "服饰", 120),
        ("posture", "体态", 100),
    ]:
        value = _safe_text(getattr(char, key, ""), limit)
        if value:
            lines.append(f"{label}: {value}")

    visual_tags = _join_items(getattr(char, "visual_tags", []), limit=10)
    if visual_tags:
        lines.append(f"视觉标签: {_safe_text(visual_tags, 160)}")

    goals = _join_items(getattr(char, "goals", []), limit=6)
    if goals:
        lines.append(f"目标: {_safe_text(goals, 160)}")

    return "\n".join(lines)


def _extract_structured_feedback(sm: StorageManager, novel_id: str) -> Dict[str, list[str]]:
    structured: Dict[str, list[str]] = {
        "narrative_conflicts": [],
        "consistency_constraints": [],
        "taboo_elements": [],
        "style_notes": [],
    }

    try:
        reviews = sm.load_reviews(novel_id)
    except Exception:
        reviews = {}

    for _, review in (reviews or {}).items():
        latest = review.get_latest() if hasattr(review, "get_latest") else None
        if not latest:
            continue
        summary = str(getattr(latest, "summary", "") or "").strip()
        if summary:
            structured["narrative_conflicts"].append(_clip(summary, 140))
        for issue in getattr(latest, "issues", [])[:6]:
            desc = str(getattr(issue, "description", "") or "").strip()
            sugg = str(getattr(issue, "suggestion", "") or "").strip()
            severity = str(getattr(issue, "severity", "") or "").lower()
            issue_type = str(getattr(issue, "issue_type", "") or "").lower()
            merged = _clip(f"{desc}；建议:{sugg}" if sugg else desc, 160)
            if not merged:
                continue
            if severity == "fatal":
                structured["taboo_elements"].append(merged)
            elif "consistency" in issue_type or "logic" in issue_type:
                structured["consistency_constraints"].append(merged)
            else:
                structured["style_notes"].append(merged)

    try:
        proofreads = sm.load_proofreads(novel_id)
    except Exception:
        proofreads = {}

    for _, proof in (proofreads or {}).items():
        latest = proof.get_latest() if hasattr(proof, "get_latest") else None
        if not latest:
            continue
        summary = str(getattr(latest, "summary", "") or "").strip()
        if summary:
            structured["consistency_constraints"].append(_clip(summary, 140))
        for issue in getattr(latest, "issues", [])[:6]:
            issue_type = str(getattr(issue, "issue_type", "") or "").lower()
            corr = str(getattr(issue, "correction", "") or "").strip()
            expl = str(getattr(issue, "explanation", "") or "").strip()
            merged = _clip(f"{corr}；{expl}" if expl else corr, 160)
            if not merged:
                continue
            if issue_type in {"consistency", "logic"}:
                structured["consistency_constraints"].append(merged)
            elif issue_type == "style":
                structured["style_notes"].append(merged)

    try:
        messages = sm.load_messages(novel_id)
    except Exception:
        messages = []

    trusted = {"writer", "reviewer", "proofreader", "墨川", "青锋", "砚清", "editor"}
    for m in (messages or [])[-20:]:
        sender = str(getattr(m, "sender", "") or "").strip()
        if sender and sender not in trusted and sender.lower() not in trusted:
            continue
        text = str(getattr(m, "content", "") or "").strip()
        if not text:
            continue
        low = text.lower()
        if any(k in low for k in ["不要", "禁", "avoid", "forbid"]):
            structured["taboo_elements"].append(_clip(text, 140))
        elif any(k in low for k in ["一致", "统一", "consisten", "逻辑", "world"]):
            structured["consistency_constraints"].append(_clip(text, 140))
        elif any(k in low for k in ["冲突", "矛盾", "climax", "张力"]):
            structured["narrative_conflicts"].append(_clip(text, 140))
        else:
            structured["style_notes"].append(_clip(text, 140))

    for key, values in structured.items():
        dedup: list[str] = []
        seen = set()
        for v in values:
            if not v or v in seen:
                continue
            dedup.append(v)
            seen.add(v)
            if len(dedup) >= 8:
                break
        structured[key] = dedup

    return structured


def _structured_feedback_text(structured: Dict[str, list[str]]) -> str:
    lines = []
    mapping = [
        ("narrative_conflicts", "叙事冲突"),
        ("consistency_constraints", "一致性约束"),
        ("taboo_elements", "禁忌元素"),
        ("style_notes", "风格备注"),
    ]
    for key, title in mapping:
        values = structured.get(key) or []
        if values:
            lines.append(f"{title}: {' | '.join(values)}")
    return "\n".join(lines)


def _virtual_collaboration(
    *,
    target: str,
    novel_context: str,
    character_context: str = "",
    user_prompt: str = "",
    style: str = "",
    llm_client=None,
) -> Dict[str, str]:
    """模拟一次原画师主导协作：作者方案 + 校对方案 -> 原画师专业裁决。"""

    collaboration_plan = ["writer", "proofreader"]
    writer_note = ""
    editor_note = ""
    extra_note = ""
    art_brief = ""
    art_note = ""
    abstract_mode = _is_abstract_mode(user_prompt, style)
    anchors = _visual_anchors(
        novel_context=novel_context,
        character_context=character_context,
        user_prompt=user_prompt,
        target=target,
    )

    if llm_client:
        try:
            plan_prompt = (
                "你扮演原画师(视觉导演)。请先决定本轮需要协作的agent，"
                "仅可从 writer, proofreader, world_builder, cinematographer 中选择，"
                "返回英文逗号分隔列表，不要解释。"
                "若信息已充分可只选 writer。\n\n"
                f"目标:{target}\n"
                f"小说上下文:\n{novel_context}\n"
                f"角色上下文:\n{character_context or '无'}\n"
                f"用户意图:{user_prompt or '自动'} 风格:{style or '未指定'}"
            )
            plan_raw = str(llm_client(plan_prompt) or "").strip().lower()
            picked = [x.strip() for x in plan_raw.replace("\n", ",").split(",") if x.strip()]
            allowed = {"writer", "proofreader", "world_builder", "cinematographer"}
            plan = [p for p in picked if p in allowed]
            if "writer" not in plan:
                plan.insert(0, "writer")
            collaboration_plan = plan[:4] if plan else ["writer", "proofreader"]
        except Exception:
            collaboration_plan = ["writer", "proofreader"]

        try:
            art_brief_prompt = (
                "你扮演原画师(视觉导演)。先输出 3-5 条画面设计框架（中文短句）。"
                "这些框架将提供给作者与校对参考。"
                "请覆盖：主体焦点、场景边界、构图策略、光线与色彩、禁用元素。不要解释。\n\n"
                "禁止输出任何文件名、路径名、占位符（如 world.json、{、#）。\n"
                "权重规则：user:0.3, writer:0.3, proofreader:0.2, art_director:0.2。\n"
                f"目标:{target}\n"
                f"小说上下文:\n{novel_context}\n"
                f"角色上下文:\n{character_context or '无'}\n"
                f"用户意图:{user_prompt or '自动'} 风格:{style or '未指定'}"
            )
            art_brief = str(llm_client(art_brief_prompt) or "").strip()
        except Exception:
            art_brief = ""

        try:
            writer_requirement = (
                "若用户要求抽象风格，请给出主题意象与色彩构成，不强制地点。\n"
                if abstract_mode
                else "必须明确写出主体与场景地点。\n"
            )
            writer_prompt = (
                "你扮演小说作者。请在原画师给定的画面约束下，给出一段画面描述（中文，80-140字）。"
                "内容要体现小说冲突、人物命运与情绪推进；要像一张可被绘制的画面，而不是抽象概念。\n\n"
                "禁止输出任何文件名、路径名、占位符（如 world.json、{、#）。\n"
                "注意：必须遵守原画师约束；用户反馈优先级最高；"
                + writer_requirement
                +
                f"目标:{target}\n"
                f"原画师约束:\n{art_brief or '无'}\n"
                f"建议锚点: 主体={anchors['subject']} 场景={anchors['scene']} 情绪={anchors['mood']}\n"
                f"小说上下文:\n{novel_context}\n"
                f"角色上下文:\n{character_context or '无'}\n"
                f"用户意图:{user_prompt or '自动'} 风格:{style or '未指定'}"
            )
            writer_note = str(llm_client(writer_prompt) or "").strip()
        except Exception:
            writer_note = ""

        if "proofreader" in collaboration_plan:
            try:
                proofreader_requirement = (
                    "若用户要求抽象风格，请给出主题意象与色彩构成，不强制地点。\n"
                    if abstract_mode
                    else ""
                )
                editor_prompt = (
                    "你扮演审校编辑(校对Agent)。请基于小说设定与原画师框架，"
                    "给出一段相对具体的画面描述（中文，80-140字），"
                    "并在描述中体现你认为必须避免的设定冲突。\n\n"
                    "禁止输出任何文件名、路径名、占位符（如 world.json、{、#）。\n"
                    "注意：你的输出是可被绘制的画面方案，不是抽象点评；必须明确写出主体与场景地点。\n"
                    + proofreader_requirement
                    +
                    f"目标:{target}\n"
                    f"原画师约束:\n{art_brief or '无'}\n"
                    f"作者画面描述:\n{writer_note or '无'}\n"
                    f"建议锚点: 主体={anchors['subject']} 场景={anchors['scene']} 情绪={anchors['mood']}\n"
                    f"小说上下文:\n{novel_context}\n"
                    f"角色上下文:\n{character_context or '无'}\n"
                    f"用户意图:{user_prompt or '自动'} 风格:{style or '未指定'}"
                )
                editor_note = str(llm_client(editor_prompt) or "").strip()
            except Exception:
                editor_note = ""

        if "world_builder" in collaboration_plan:
            try:
                world_prompt = (
                    "你扮演世界观顾问(world_builder)。请给出 2-3 条可视化建议，"
                    "用于强化设定辨识度与场景可信度（中文短句）。不要解释。\n\n"
                    f"目标:{target}\n"
                    f"小说上下文:\n{novel_context}\n"
                    f"角色上下文:\n{character_context or '无'}"
                )
                extra_note = str(llm_client(world_prompt) or "").strip()
            except Exception:
                extra_note = ""

        if not extra_note and "cinematographer" in collaboration_plan:
            try:
                cine_prompt = (
                    "你扮演镜头指导(cinematographer)。请给出 2-3 条镜头与光影建议，"
                    "用于提升叙事可读性（中文短句）。不要解释。\n\n"
                    f"目标:{target}\n"
                    f"原画师框架:\n{art_brief or '无'}\n"
                    f"作者方案:\n{writer_note or '无'}"
                )
                extra_note = str(llm_client(cine_prompt) or "").strip()
            except Exception:
                extra_note = ""

        try:
            art_requirement = (
                "必须包含主题意象、色彩策略、构成关键词与情绪，不要解释。\n\n"
                if abstract_mode
                else "必须包含主体、场景地点、情绪、构图关键词。不要解释。\n\n"
            )
            art_prompt = (
                "你扮演原画师(视觉导演)。请基于你的专业判断，综合用户诉求、作者方案、校对方案，"
                "给出 1 段最终视觉决策（中文，120字内）。"
                + art_requirement
                +
                "禁止输出任何文件名、路径名、占位符（如 world.json、{、#），"
                "也不要输出'读取某文件'这类过程描述，只输出画面结论。\n"
                "权重规则：user:0.3, writer:0.3, proofreader:0.2, art_director:0.2；由原画师基于专业判断作最终输出。\n"
                f"用户反馈:{user_prompt or '无'}\n"
                f"目标:{target}\n"
                f"建议锚点: 主体={anchors['subject']} 场景={anchors['scene']} 情绪={anchors['mood']}\n"
                f"原画师框架:{art_brief or '无'}\n"
                f"作者方案:{writer_note or '无'}\n"
                f"校对方案:{editor_note or '无'}\n"
                f"附加agent建议:{extra_note or '无'}\n"
            )
            art_note = str(llm_client(art_prompt) or "").strip()
        except Exception:
            art_note = ""

    if not art_brief:
        if abstract_mode:
            art_brief = (
                f"核心意象围绕{anchors['subject']}；以主题驱动抽象构成；"
                f"通过高对比彩色层次表达{anchors['mood']}；禁用与设定冲突符号。"
            )
        else:
            art_brief = (
                f"主体焦点锁定{anchors['subject']}并首屏可读；画面场景定位在{anchors['scene']}；"
                "采用明确前中后景构图；光线服务叙事冲突；禁用与设定冲突元素。"
            )
    if not writer_note:
        if abstract_mode:
            writer_note = (
                f"以{anchors['subject']}为核心意象，将故事冲突拆解为层叠色块与符号轨迹，"
                f"用强对比彩色关系推进叙事，整体情绪呈现{anchors['mood']}。"
            )
        else:
            writer_note = (
                f"在{anchors['scene']}中，{anchors['subject']}被卷入"
                f"{('角色命运冲突' if target == 'character_main' else '故事核心冲突')}的爆发瞬间，"
                f"动作明确、对抗关系清晰，整体情绪呈现{anchors['mood']}。"
            )
    if not editor_note:
        if abstract_mode:
            editor_note = (
                f"在主题设定边界内，以{anchors['subject']}相关符号做抽象变形，"
                "保持符号语义一致，避免无关符号混入，色彩层次需服务叙事而非纯装饰。"
            )
        else:
            editor_note = (
                f"在{anchors['scene']}的设定边界内，前景聚焦{anchors['subject']}与冲突道具，"
                "中景交代环境秩序，背景保留压迫感符号，避免与设定冲突的现代元素。"
            )
    if not extra_note:
        extra_note = ""
    if not art_note:
        art_note = (
            f"以{anchors['subject']}为视觉锚点，在{anchors['scene']}中组织画面，"
            "在既定构图与光色约束内突出冲突瞬间，确保主题、情绪与设定一致性同时成立。"
        )

    writer_note = _ensure_concrete(
        writer_note,
        subject=anchors["subject"],
        scene=anchors["scene"],
        mood=anchors["mood"],
        abstract_mode=abstract_mode,
    )
    writer_note = _rewrite_if_generic(
        writer_note,
        role="writer",
        subject=anchors["subject"],
        scene=anchors["scene"],
        mood=anchors["mood"],
        abstract_mode=abstract_mode,
    )
    editor_note = _ensure_concrete(
        editor_note,
        subject=anchors["subject"],
        scene=anchors["scene"],
        mood=anchors["mood"],
        abstract_mode=abstract_mode,
    )
    editor_note = _rewrite_if_generic(
        editor_note,
        role="proofreader",
        subject=anchors["subject"],
        scene=anchors["scene"],
        mood=anchors["mood"],
        abstract_mode=abstract_mode,
    )
    art_note = _ensure_concrete(
        art_note,
        subject=anchors["subject"],
        scene=anchors["scene"],
        mood=anchors["mood"],
        abstract_mode=abstract_mode,
    )
    art_note = _rewrite_if_generic(
        art_note,
        role="art_director",
        subject=anchors["subject"],
        scene=anchors["scene"],
        mood=anchors["mood"],
        abstract_mode=abstract_mode,
    )

    return {
        "collaboration_plan": ", ".join(collaboration_plan),
        "art_brief": _clip(art_brief, 260),
        "writer": _clip(writer_note, 260),
        "proofreader": _clip(editor_note, 260),
        "editor": _clip(editor_note, 260),
        "extra": _clip(extra_note, 260),
        "art_director": _clip(art_note, 260),
        "anchors": anchors,
        "abstract_mode": abstract_mode,
        "weights": "user:0.3, writer:0.3, proofreader:0.2, art_director:0.2",
    }


def _log_visual_suggestion(sm: StorageManager, novel_id: str, content: str) -> None:
    try:
        sm.add_message(
            novel_id,
            AgentMessage(
                sender="丹青",
                msg_type="suggestion",
                content=_clip(content, 260),
                target=None,
                priority="normal",
            ),
        )
    except Exception:
        pass


def generate_cover_prompt_draft(
    sm: StorageManager,
    novel_id: str,
    user_prompt: str,
    style: str,
    llm_client,
) -> Dict[str, Any]:
    user_prompt = str(user_prompt or "").strip()
    style = str(style or "").strip()
    novel_context = _novel_context(sm, novel_id)
    structured = _extract_structured_feedback(sm, novel_id)
    collab = _virtual_collaboration(
        target="cover",
        novel_context=novel_context,
        user_prompt=user_prompt,
        style=style,
        llm_client=llm_client,
    )

    director = VisualDirectorAgent(llm_client=llm_client)
    collab_notes = _structured_feedback_text(structured)
    collab_notes += (
        ("\n" if collab_notes else "")
        + (
            f"协作对象: {collab.get('collaboration_plan', 'writer, proofreader')}\n"
            f"用户反馈(高优先级): {user_prompt or '无'}\n"
            f"原画约束: {collab.get('art_brief', '无')}\n"
            f"作者意见: {collab['writer']}\n"
            f"校对方案: {collab.get('proofreader', '')}\n"
            f"附加建议: {collab.get('extra', '')}\n"
            f"原画结论: {collab['art_director']}\n"
            f"权重: {collab.get('weights', 'user:0.3, writer:0.3, proofreader:0.2, art_director:0.2')}"
        )
    )
    prompt = director.design_cover_prompt(
        novel_context=novel_context,
        user_intent=user_prompt,
        style=style,
        collaboration_notes=collab_notes,
    )

    _log_visual_suggestion(sm, novel_id, f"封面提示词草稿：{prompt}")
    return {
        "target": "cover",
        "suggested_prompt": prompt,
        "structured_feedback": structured,
        "collaboration": collab,
        "context_debug": {
            "novel_context_present": bool(novel_context.strip()),
            "novel_context_preview": _clip(novel_context, 260),
            "llm_enabled": llm_client is not None,
        },
    }


def generate_character_main_prompt_draft(
    sm: StorageManager,
    novel_id: str,
    character_id: str,
    user_prompt: str,
    style: str,
    llm_client,
) -> Dict[str, Any]:
    user_prompt = str(user_prompt or "").strip()
    style = str(style or "").strip()

    novel_context = _novel_context(sm, novel_id)
    character_context = _character_context(sm, novel_id, character_id)
    structured = _extract_structured_feedback(sm, novel_id)
    collab = _virtual_collaboration(
        target="character_main",
        novel_context=novel_context,
        character_context=character_context,
        user_prompt=user_prompt,
        style=style,
        llm_client=llm_client,
    )

    director = VisualDirectorAgent(llm_client=llm_client)
    collab_notes = _structured_feedback_text(structured)
    collab_notes += (
        ("\n" if collab_notes else "")
        + (
            f"协作对象: {collab.get('collaboration_plan', 'writer, proofreader')}\n"
            f"用户反馈(高优先级): {user_prompt or '无'}\n"
            f"原画约束: {collab.get('art_brief', '无')}\n"
            f"作者意见: {collab['writer']}\n"
            f"校对方案: {collab.get('proofreader', '')}\n"
            f"附加建议: {collab.get('extra', '')}\n"
            f"原画结论: {collab['art_director']}\n"
            f"权重: {collab.get('weights', 'user:0.3, writer:0.3, proofreader:0.2, art_director:0.2')}"
        )
    )
    prompt = director.design_character_main_prompt(
        novel_context=novel_context,
        character_context=character_context,
        user_intent=user_prompt,
        style=style,
        collaboration_notes=collab_notes,
    )

    _log_visual_suggestion(sm, novel_id, f"角色主图提示词草稿：{prompt}")
    return {
        "target": "character_main",
        "suggested_prompt": prompt,
        "structured_feedback": structured,
        "collaboration": collab,
        "context_debug": {
            "novel_context_present": bool(novel_context.strip()),
            "character_context_present": bool(character_context.strip()),
            "novel_context_preview": _clip(novel_context, 220),
            "character_context_preview": _clip(character_context, 220),
            "llm_enabled": llm_client is not None,
        },
    }


def generate_cover_prompt(
    sm: StorageManager,
    novel_id: str,
    user_prompt: str,
    style: str,
    llm_client,
) -> str:
    return str(
        generate_cover_prompt_draft(
            sm=sm,
            novel_id=novel_id,
            user_prompt=user_prompt,
            style=style,
            llm_client=llm_client,
        ).get("suggested_prompt")
        or ""
    )


def generate_character_main_prompt(
    sm: StorageManager,
    novel_id: str,
    character_id: str,
    user_prompt: str,
    style: str,
    llm_client,
) -> str:
    return str(
        generate_character_main_prompt_draft(
            sm=sm,
            novel_id=novel_id,
            character_id=character_id,
            user_prompt=user_prompt,
            style=style,
            llm_client=llm_client,
        ).get("suggested_prompt")
        or ""
    )

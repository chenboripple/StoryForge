"""Progressive pipeline flow test.

Covers: chapter_planner -> writer -> feedback_synthesizer
"""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure project root importable when invoked directly.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.state import NovelState, ReviewRecord  # noqa: E402
from pipeline.novel_pipeline import NovelPipeline  # noqa: E402


class DummyIssue:
    def __init__(self, severity="A", location="第2段", description="设定冲突", suggestion="修正"):
        self.severity = severity
        self.location = location
        self.description = description
        self.suggestion = suggestion


class DummyReviewResult:
    def __init__(self):
        self.summary = "本章核心冲突成立，但设定口径有偏差"
        self.issues = [DummyIssue()]


def _mock_llm(prompt: str, temperature: float = 0.7):
    if "请输出 JSON" in prompt or "只输出JSON" in prompt or "仅输出 JSON" in prompt:
        # Return a valid JSON for planner calls.
        return (
            '{"chapter_id": 1, "title": "第一章", "theme": "开端", '
            '"plot": "主角卷入冲突", "scenes": ["场景A", "场景B"], '
            '"hooks": ["悬念"], "characters_involved": ["林川"], '
            '"constraints": ["保持设定一致"], "words_target": 1200}'
        )

    # Writer call: return normal chapter text.
    return "林川站在雨里，想起昨夜那句警告。街角的灯闪了两次，像某种倒计时。"


def test_progressive_flow_chapter_plan_write_feedback():
    pipeline = NovelPipeline(
        llm_client=_mock_llm,
        use_outline_refinement=True,
        use_extraction=False,
        use_ip_generation=False,
        use_video_generation=False,
    )

    state = NovelState(
        novel_id="progressive_demo",
        novel_title="渐进式测试",
        genre="科幻",
        outline="主角在城市异象中逐步接近真相。",
        current_chapter=1,
        target_word_count=1200,
    )

    # 1) chapter planner should create chapter brief
    state = pipeline._chapter_planner(state)
    brief = state.get_chapter_brief(1)
    assert brief, "chapter brief should be generated"
    assert "plot" in brief

    # 2) writer should write chapter based on brief
    state = pipeline._writer_agent.invoke(state)
    assert 1 in state.chapters
    chapter_obj = state.chapters[1]
    chapter_text = getattr(chapter_obj, "text", chapter_obj)
    assert isinstance(chapter_text, str) and chapter_text

    # 3) feedback synthesizer should fold feedback into chapter brief
    # Inject synthetic review feedback as reviewer output.
    state.structured_reviews[1] = [DummyReviewResult()]
    state.reviews[1] = [
        ReviewRecord(
            round=1,
            reviewer="青锋",
            score=72,
            comments="存在设定冲突",
            passed=False,
            timestamp="",
        )
    ]

    state = pipeline._feedback_synthesizer(state)
    updated = state.get_chapter_brief(1)
    assert "feedback_history" in updated
    assert len(updated["feedback_history"]) >= 1
    assert "revision_focus" in updated

    # severe setting issue should create proposal (pending)
    assert state.proposals, "expected proposal generated for severe cross-layer issue"
    assert state.proposals[-1]["status"] == "pending"

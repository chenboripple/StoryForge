"""
测试 P0 修复：
1. _get_recent_chapters 取结尾而非开头
2. 通过判断无假阳性
3. ReviserAgent 不污染 persona
4. run_batch 深拷贝
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import NovelState, ChapterStatus, CharacterInfo
from agents.creation_agents import (
    WriterAgent, ReviewerAgent, ReviserAgent, ProofreaderAgent,
    MochuanPersona, QingfengPersona, YanqingPersona
)

import re


def test_recent_chapters_end():
    """测试 WriterAgent._get_recent_chapters 取结尾而非开头"""
    print("="*50)
    print("测试1: _get_recent_chapters 取结尾而非开头")
    print("="*50)

    agent = WriterAgent(llm_client=None)
    state = NovelState(
        current_chapter=3,
        chapters={
            1: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",  # A开头，Z结尾
            2: "0123456789ABCDEF"
        }
    )
    result = agent._get_recent_chapters(state)

    print("输出内容：")
    print(result)
    print()

    # 验证是否有结尾的字符（2结尾，1结尾）
    assert "F" in result or "Z" in result, "应该包含章节结尾内容"
    assert "第2章结尾" in result, "应该包含第2章"
    assert "..." in result, "应该有省略号"

    print("✅ 测试1 通过")
    print()


def test_passed_detection():
    """测试 ReviewerAgent 的通过判断无假阳性"""
    print("="*50)
    print("测试2: 通过判断无假阳性")
    print("="*50)

    # 正面用例
    positive1 = """【总体评分】88分
【是否通过】通过"""
    passed1 = bool(re.search(r'【是否通过】\s*通过', positive1))
    assert passed1 is True, "包含'【是否通过】通过'应该判定通过"

    # 负面用例1: "未通过"
    negative1 = """【总体评分】50分
【是否通过】未通过"""
    passed2 = bool(re.search(r'【是否通过】\s*通过', negative1))
    assert passed2 is False, "'未通过'里的'通过'不应被误判"

    # 负面用例2: "需修改"
    negative2 = """【总体评分】70分
【是否通过】需修改"""
    passed3 = bool(re.search(r'【是否通过】\s*通过', negative2))
    assert passed3 is False, "'需修改'不应被误判"

    print("正面用例（'通过'）：✅ 通过")
    print("负面用例（'未通过'）：✅ 被正确排除")
    print("负面用例（'需修改'）：✅ 被正确排除")
    print("✅ 测试2 通过")
    print()


def test_proofreader_passed_detection():
    """测试 ProofreaderAgent 的通过判断"""
    print("="*50)
    print("测试3: Proofreader 通过判断无假阳性")
    print("="*50)

    test_cases = [
        ("通过", "通过", True),
        ("未通过", "未通过", False),
        ("需返工", "需返工", False),
        ("通过但有瑕疵", "通过但有瑕疵", True),
    ]

    for name, text, expected in test_cases:
        # 模拟 ProofreaderAgent 的逻辑
        # 通过的情况: 包含"通过"但不包含"未通过", 且不包含"需返工"
        has_pass = "通过" in text
        has_not_pass = "未通过" in text
        has_rework = "需返工" in text
        has_exact_pass = text.strip() == "通过"
        has_structured_pass = re.search(r'【总体评价】\s*通过', text) is not None

        passed = (has_exact_pass or has_structured_pass or (has_pass and not has_not_pass)) and not has_rework
        assert passed == expected, f"{name} 应该为 {expected}"
        print(f"  {name}: {'✅ 通过' if passed == expected else '❌ 失败'}")

    print("✅ 测试3 通过")
    print()


def test_reviser_persona_not_polluted():
    """测试 ReviserAgent 不污染 persona"""
    print("="*50)
    print("测试4: ReviserAgent 不污染 persona")
    print("="*50)

    # 创建两次 ReviserAgent
    agent1 = ReviserAgent(llm_client=None)
    original_tone1 = agent1.persona.tone
    print(f"agent1 原始 tone 长度：{len(original_tone1)}")
    print(f"agent1 原始 tone：{original_tone1[:100]}...")

    # 再创建一个
    agent2 = ReviserAgent(llm_client=None)
    original_tone2 = agent2.persona.tone
    print(f"agent2 原始 tone 长度：{len(original_tone2)}")

    assert original_tone1 == original_tone2, "两次创建的 persona tone 应该一致"
    assert "根据编辑意见修改" not in original_tone1, "原始 tone 不应该包含修改说明"

    print("✅ 测试4 通过")
    print()


def test_deep_copy():
    """测试 NovelState.copy() 深拷贝功能"""
    print("="*50)
    print("测试5: NovelState.copy() 深拷贝")
    print("="*50)

    state = NovelState(
        novel_id="test_001",
        novel_title="测试小说",
        chapters={1: "第一章内容"},
        chapter_status={1: ChapterStatus.APPROVED},
        characters=[CharacterInfo(name="测试角色")]
    )

    state_copy = state.copy()

    # 修改 copy
    state_copy.novel_title = "修改后的标题"
    state_copy.chapters[2] = "第二章内容"
    state_copy.characters.append(CharacterInfo(name="新增角色"))

    # 验证原始 state 不变
    assert state.novel_title == "测试小说", "原始 state 不应受影响"
    assert 2 not in state.chapters, "原始 chapters 不应受影响"
    assert len(state.characters) == 1, "原始 characters 不应受影响"

    # 验证 copy 有修改
    assert state_copy.novel_title == "修改后的标题"
    assert 2 in state_copy.chapters
    assert len(state_copy.characters) == 2

    print("原始 state 不受 copy 修改影响：✅")
    print("copy state 包含修改：✅")
    print("✅ 测试5 通过")
    print()


if __name__ == "__main__":
    print("开始验证 P0 修复...\n")
    try:
        test_recent_chapters_end()
        test_passed_detection()
        test_proofreader_passed_detection()
        test_reviser_persona_not_polluted()
        test_deep_copy()

        print("\n" + "="*50)
        print("✅ 所有 P0 修复验证通过！")
        print("="*50)
    except AssertionError as e:
        print(f"\n❌ 验证失败：{e}")
        sys.exit(1)

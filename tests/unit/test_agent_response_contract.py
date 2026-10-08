from backend.agent.chat_service import CHAT_SYSTEM_PROMPT


def test_chat_prompt_fixes_sections_and_internal_news_id_format():
    expected_sections = ["## 核心结论", "## 新闻依据", "## 传导逻辑", "## 风险与限制"]
    positions = [CHAT_SYSTEM_PROMPT.index(section) for section in expected_sections]

    assert positions == sorted(positions)
    assert "新闻标题（新闻ID：123）" in CHAT_SYSTEM_PROMPT
    assert "不要把新闻标题或新闻 ID 做成外部网页链接" in CHAT_SYSTEM_PROMPT
    assert "source_url 只用于数据溯源" in CHAT_SYSTEM_PROMPT

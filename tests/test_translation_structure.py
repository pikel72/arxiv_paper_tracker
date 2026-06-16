#!/usr/bin/env python3

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import translator


class DummyAuthor:
    def __init__(self, name):
        self.name = name


class DummyPaper:
    def __init__(self, title="Test Paper"):
        self.title = title
        self.authors = [DummyAuthor("Tester")]
        self.summary = "We prove a theorem."
        self.categories = ["math.AP"]

    def get_short_id(self):
        return "test.12345"


def test_translate_title_uses_structured_result():
    paper = DummyPaper()
    structured = translator.StructuredTitleTranslation(chinese_title="测试标题")

    mock_client = MagicMock()
    mock_client.structured_chat_completion_with_usage.return_value = (structured, {})
    with patch("translator.get_cached_translation", return_value=None), patch("translator.cache_translation"), patch(
        "translator.get_ai_client", return_value=mock_client,
    ):
        result = translator.translate_abstract_with_deepseek(paper, translate_title_only=True, use_cache=True)

    assert result == "**中文标题**: 测试标题"
    assert mock_client.structured_chat_completion_with_usage.call_args.kwargs["json_schema_prompt"] is True


def test_translate_abstract_falls_back_to_text_mode():
    paper = DummyPaper()
    fallback = "**中文标题**: 测试标题\n\n**摘要翻译**: 我们证明了一个定理。"

    mock_client = MagicMock()
    mock_client.structured_chat_completion_with_usage.side_effect = Exception("json schema unsupported")
    mock_client.chat_completion.return_value = fallback
    with patch("translator.get_cached_translation", return_value=None), patch("translator.cache_translation"), patch(
        "translator.get_ai_client", return_value=mock_client,
    ):
        result = translator.translate_abstract_with_deepseek(paper, translate_title_only=False, use_cache=True)

    assert result == fallback


def test_translation_prompts_require_verbatim_formula_preservation():
    paper = DummyPaper(title="On $L^p$ bounds for $\\partial_t u + \\Delta u = 0$")
    paper.summary = "We prove $\\|u(t)\\|_{L^2} \\le C \\|u_0\\|_{L^2}$ and $u_t + \\Delta u = 0$."

    structured_messages = translator._build_translation_messages(paper, translate_title_only=False)
    fallback_prompt = translator._build_translation_fallback_prompt(paper, translate_title_only=False)

    structured_prompt = "\n".join(message["content"] for message in structured_messages)
    assert "逐字符保留" in structured_prompt
    assert "不能改动公式内部任何字符" in structured_prompt
    assert "\\alpha" in structured_prompt
    assert "$u_t + \\Delta u = 0$" in structured_prompt
    assert "逐字符保留" in fallback_prompt
    assert "不能改动公式内部任何字符" in fallback_prompt


if __name__ == "__main__":
    test_translate_title_uses_structured_result()
    test_translate_abstract_falls_back_to_text_mode()
    test_translation_prompts_require_verbatim_formula_preservation()
    print("translation structure tests passed")

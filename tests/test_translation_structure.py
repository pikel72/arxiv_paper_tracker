#!/usr/bin/env python3

import os
import sys
from unittest.mock import patch

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

    with patch("translator.get_cached_translation", return_value=None), patch("translator.cache_translation"), patch(
        "translator.ai_client.structured_chat_completion_with_usage",
        return_value=(structured, {}),
    ):
        result = translator.translate_abstract_with_deepseek(paper, translate_title_only=True, use_cache=True)

    assert result == "**中文标题**: 测试标题"


def test_translate_abstract_falls_back_to_text_mode():
    paper = DummyPaper()
    fallback = "**中文标题**: 测试标题\n\n**摘要翻译**: 我们证明了一个定理。"

    with patch("translator.get_cached_translation", return_value=None), patch("translator.cache_translation"), patch(
        "translator.ai_client.structured_chat_completion_with_usage",
        side_effect=Exception("json schema unsupported"),
    ), patch("translator.ai_client.chat_completion", return_value=fallback):
        result = translator.translate_abstract_with_deepseek(paper, translate_title_only=False, use_cache=True)

    assert result == fallback


if __name__ == "__main__":
    test_translate_title_uses_structured_result()
    test_translate_abstract_falls_back_to_text_mode()
    print("translation structure tests passed")

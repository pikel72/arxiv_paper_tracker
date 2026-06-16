#!/usr/bin/env python3

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analyzer import StructuredTopicClassification, check_topic_relevance


class DummyAuthor:
    def __init__(self, name):
        self.name = name


class DummyPaper:
    def __init__(self, title):
        self.title = title
        self.authors = [DummyAuthor("Tester")]
        self.summary = "abstract"
        self.categories = ["math.AP"]

    def get_short_id(self):
        return "test.12345"


def test_check_topic_relevance_uses_structured_result():
    paper = DummyPaper("Asymptotic stability of shear flows for 2D Euler equations")

    mock_client = MagicMock()
    mock_client.structured_chat_completion_with_usage.return_value = (
        StructuredTopicClassification(priority=1, reason="涉及Euler方程与无粘阻尼"),
        {},
    )
    with patch("analyzer.get_cached_classification", return_value=None), patch("analyzer.cache_classification"), patch(
        "analyzer.get_ai_client", return_value=mock_client,
    ):
        priority, reason = check_topic_relevance(paper)

    assert priority == 1
    assert reason == "涉及Euler方程与无粘阻尼"
    assert mock_client.structured_chat_completion_with_usage.call_args.kwargs["json_schema_prompt"] is True


def test_check_topic_relevance_falls_back_to_text_mode():
    paper = DummyPaper("Asymptotic stability of shear flows for 2D Euler equations")

    mock_client = MagicMock()
    mock_client.structured_chat_completion_with_usage.side_effect = Exception("json schema unsupported")
    mock_client.chat_completion.return_value = "\n\n优先级1 - 涉及Euler方程与无粘阻尼\n"
    with patch("analyzer.get_cached_classification", return_value=None), patch("analyzer.cache_classification"), patch(
        "analyzer.get_ai_client", return_value=mock_client,
    ):
        priority, reason = check_topic_relevance(paper)

    assert priority == 1
    assert reason == "涉及Euler方程与无粘阻尼"


def test_structured_topic_classification_truncates_long_reason():
    result = StructuredTopicClassification(priority=2, reason="双曲拟线性方程组、加权Sobolev空间、Goursat问题、Einstein方程的谐波规范")

    assert result.priority == 2
    assert len(result.reason) <= 40


if __name__ == "__main__":
    test_check_topic_relevance_uses_structured_result()
    test_check_topic_relevance_falls_back_to_text_mode()
    print("topic classification tests passed")

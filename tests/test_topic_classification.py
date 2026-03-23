#!/usr/bin/env python3

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analyzer import check_topic_relevance


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


def test_check_topic_relevance_trims_model_output():
    paper = DummyPaper("Asymptotic stability of shear flows for 2D Euler equations")

    with patch("analyzer.get_cached_classification", return_value=None), \
         patch("analyzer.cache_classification"), \
         patch("analyzer.ai_client.chat_completion", return_value="\n\n优先级1 - 涉及Euler方程与无粘阻尼\n"):
        priority, reason = check_topic_relevance(paper)

    assert priority == 1
    assert reason == "涉及Euler方程与无粘阻尼"


if __name__ == "__main__":
    test_check_topic_relevance_trims_model_output()
    print("topic classification tests passed")

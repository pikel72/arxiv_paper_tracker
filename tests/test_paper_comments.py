#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import models
import utils


def _build_entry():
    return SimpleNamespace(
        title="Test Paper Title",
        authors=[SimpleNamespace(name="Alice"), SimpleNamespace(name="Bob")],
        published="2025-01-02T03:04:05Z",
        tags=[SimpleNamespace(term="math.AP")],
        id="http://arxiv.org/abs/2501.00001v1",
        summary="Test summary",
        arxiv_comment="12 pages, comments welcome",
    )


def test_simple_paper_preserves_arxiv_comment():
    paper = models.SimplePaper(_build_entry())

    assert paper.comment == "12 pages, comments welcome"
    assert paper.arxiv_comment == "12 pages, comments welcome"


def test_write_to_conclusion_includes_comment():
    paper = models.SimplePaper(_build_entry())
    analysis = """### 详细分析

测试标题

## 详细分析

### 1. 研究对象和背景
背景内容
"""
    translation = """**中文标题**: 测试标题

**摘要翻译**: 测试摘要
"""

    with TemporaryDirectory() as tmpdir:
        with patch.object(utils, "RESULTS_DIR", Path(tmpdir)), patch(
            "translator.translate_abstract_with_deepseek", return_value=translation
        ):
            output_file = utils.write_to_conclusion([(paper, analysis)], [], filename="daily.md")

        content = output_file.read_text(encoding="utf-8")

    assert "**Comment**: 12 pages, comments welcome" in content


if __name__ == "__main__":
    test_simple_paper_preserves_arxiv_comment()
    test_write_to_conclusion_includes_comment()
    print("paper comments tests passed")

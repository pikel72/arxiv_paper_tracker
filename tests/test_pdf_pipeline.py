#!/usr/bin/env python3

import datetime
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import analyzer
import utils


class DummyAuthor:
    def __init__(self, name):
        self.name = name


class DummyPaper:
    def __init__(self, title="Test Paper"):
        self.title = title
        self.authors = [DummyAuthor("Tester")]
        self.summary = "abstract"
        self.categories = ["math.AP"]
        self.entry_id = "https://arxiv.org/abs/test.12345"
        self.published = datetime.datetime(2026, 4, 1)

    def get_short_id(self):
        return "test.12345"


class FakeFitzPage:
    def __init__(self, text):
        self.text = text

    def get_text(self, mode):
        assert mode == "text"
        return self.text


class FakeFitzDocument:
    def __init__(self, page_texts):
        self.page_texts = page_texts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __len__(self):
        return len(self.page_texts)

    def __getitem__(self, index):
        return FakeFitzPage(self.page_texts[index])


class FakePlumberPage:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class FakePlumberDocument:
    def __init__(self, page_texts):
        self.pages = [FakePlumberPage(text) for text in page_texts]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def cleanup_disabled_request():
    return {
        "cleanup_requested": False,
        "cleanup_attempted": False,
        "cleanup_applied": False,
        "cleanup_provider": "",
        "cleanup_effective_model": "",
        "cleanup_thinking_requested": False,
        "cleanup_thinking_applied": False,
        "cleanup_budget": None,
        "cleanup_effort": None,
        "cleanup_fallback_used": False,
        "cleanup_reasoning_content_present": False,
        "cleanup_structured_validated": False,
    }


def test_extract_pdf_text_prefers_pymupdf():
    fake_fitz = SimpleNamespace(open=lambda _: FakeFitzDocument(["First page", "Second page"]))

    with patch.object(analyzer, "fitz", fake_fitz), patch.object(
        analyzer.pdfplumber,
        "open",
        side_effect=AssertionError("pdfplumber should not be used"),
    ):
        text = analyzer.extract_pdf_text("paper.pdf", max_pages=2)

    assert "First page" in text
    assert "Second page" in text
    assert text.count("=== 第") == 2


def test_extract_pdf_text_falls_back_to_pdfplumber_when_pymupdf_fails():
    fake_fitz = SimpleNamespace(open=lambda _: (_ for _ in ()).throw(RuntimeError("fitz failed")))
    fake_plumber = FakePlumberDocument(["Fallback page"])

    with patch.object(analyzer, "fitz", fake_fitz), patch.object(analyzer.pdfplumber, "open", return_value=fake_plumber):
        text = analyzer.extract_pdf_text("paper.pdf", max_pages=1)

    assert "Fallback page" in text
    assert text.count("=== 第") == 1


def test_analyze_paper_records_prompt_budget_estimate():
    paper = DummyPaper()
    pdf_text = "\n=== 第1页 ===\npdf text\n"
    structured_result = analyzer.StructuredPaperAnalysis(
        chinese_title="测试标题",
        research_background="背景内容",
        main_results="结果内容",
        methods_and_tools="方法内容",
        comparison_with_previous_work="比较内容",
    )

    def fake_get_request_config(thinking_mode=False):
        return {
            "provider": "qwen",
            "effective_model": "qwen-turbo",
            "thinking_requested": thinking_mode,
            "thinking_applied": thinking_mode,
            "thinking_budget": None,
            "thinking_effort": None,
            "structured_mode": "json",
        }

    def fake_structured_completion(messages, response_model, thinking_mode=False, return_response_state=False, **kwargs):
        response_state = {
            **fake_get_request_config(thinking_mode=thinking_mode),
            "fallback_used": False,
            "fallback_reason": "",
            "reasoning_content_present": False,
            "reasoning_content_length": 0,
        }
        result = (structured_result, {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}, response_state)
        if return_response_state:
            return result
        return result[:2]

    with patch.object(analyzer, "extract_pdf_text", return_value=pdf_text), patch.object(
        analyzer.ai_client, "get_analysis_request_config", side_effect=fake_get_request_config
    ), patch.object(
        analyzer, "get_analysis_cleanup_request_config", side_effect=cleanup_disabled_request
    ), patch.object(
        analyzer.ai_client, "structured_chat_completion_with_usage", side_effect=fake_structured_completion
    ):
        _, _, analysis_meta = analyzer.analyze_paper(
            "paper.pdf",
            paper,
            use_cache=False,
            thinking_mode=False,
            include_prompt_estimate=True,
        )

    assert analysis_meta["estimated_prompt_tokens"] > 0
    assert analysis_meta["pdf_text_length"] == len(pdf_text)
    assert analysis_meta["pdf_text_pages"] == 1


def test_analyze_paper_skips_prompt_budget_estimate_by_default():
    paper = DummyPaper()
    structured_result = analyzer.StructuredPaperAnalysis(
        chinese_title="测试标题",
        research_background="背景内容",
        main_results="结果内容",
        methods_and_tools="方法内容",
        comparison_with_previous_work="比较内容",
    )

    def fake_get_request_config(thinking_mode=False):
        return {
            "provider": "qwen",
            "effective_model": "qwen-turbo",
            "thinking_requested": thinking_mode,
            "thinking_applied": thinking_mode,
            "thinking_budget": None,
            "thinking_effort": None,
            "structured_mode": "json",
        }

    def fake_structured_completion(messages, response_model, thinking_mode=False, return_response_state=False, **kwargs):
        response_state = {
            **fake_get_request_config(thinking_mode=thinking_mode),
            "fallback_used": False,
            "fallback_reason": "",
            "reasoning_content_present": False,
            "reasoning_content_length": 0,
        }
        result = (structured_result, {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}, response_state)
        if return_response_state:
            return result
        return result[:2]

    with patch.object(analyzer, "extract_pdf_text", return_value="pdf text"), patch.object(
        analyzer.ai_client, "get_analysis_request_config", side_effect=fake_get_request_config
    ), patch.object(
        analyzer, "get_analysis_cleanup_request_config", side_effect=cleanup_disabled_request
    ), patch.object(
        analyzer.ai_client, "structured_chat_completion_with_usage", side_effect=fake_structured_completion
    ):
        _, _, analysis_meta = analyzer.analyze_paper("paper.pdf", paper, use_cache=False, thinking_mode=False)

    assert analysis_meta["estimated_prompt_tokens"] is None
    assert analysis_meta["pdf_text_length"] is None
    assert analysis_meta["pdf_text_pages"] is None


def test_write_single_analysis_includes_prompt_estimate_metadata():
    paper = DummyPaper()
    analysis = """# 测试标题

## 详细分析

### 1. 研究对象和背景
背景内容
"""
    analysis_meta = {
        "provider": "qwen",
        "effective_model": "qwen-turbo",
        "thinking_requested": False,
        "thinking_applied": False,
        "fallback_used": False,
        "reasoning_content_present": False,
        "structured_output_validated": True,
        "structured_output_fallback": False,
        "cleanup_requested": False,
        "cleanup_attempted": False,
        "cleanup_applied": False,
        "cleanup_thinking_applied": False,
        "cleanup_fallback_used": False,
        "cleanup_reasoning_content_present": False,
        "cleanup_structured_validated": False,
        "from_cache": False,
        "estimated_prompt_tokens": 1234,
        "pdf_text_length": 5678,
        "pdf_text_pages": 10,
    }

    with TemporaryDirectory() as tmpdir:
        with patch.object(utils, "RESULTS_DIR", Path(tmpdir)), patch(
            "translator.translate_abstract_with_deepseek", return_value="**中文标题**: 测试标题"
        ):
            output_file = utils.write_single_analysis(
                paper,
                analysis,
                filename="single.md",
                usage={},
                analysis_meta=analysis_meta,
                thinking_mode=False,
            )

        content = output_file.read_text(encoding="utf-8")

    assert "estimated_prompt_tokens: 1234" in content
    assert "pdf_text_length: 5678" in content
    assert "pdf_text_pages: 10" in content

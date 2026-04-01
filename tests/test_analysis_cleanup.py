#!/usr/bin/env python3

import datetime
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import analyzer
import cache


class DummyAuthor:
    def __init__(self, name):
        self.name = name


class DummyPaper:
    def __init__(self, title="Test Paper"):
        self.title = title
        self.authors = [DummyAuthor("Tester")]
        self.summary = "We prove global regularity under an $H^1$ assumption."
        self.categories = ["math.AP"]
        self.entry_id = "https://arxiv.org/abs/test.12345"
        self.published = datetime.datetime(2026, 4, 1)

    def get_short_id(self):
        return "test.12345"


class FakeCleanupClient:
    def __init__(self, cleaned_result):
        self.cleaned_result = cleaned_result
        self.calls = []

    def structured_chat_completion_with_usage(self, **kwargs):
        self.calls.append(kwargs)
        response_state = {
            "provider": "openrouter",
            "effective_model": "editor-model",
            "thinking_requested": False,
            "thinking_applied": False,
            "thinking_budget": None,
            "thinking_effort": None,
            "fallback_used": False,
            "fallback_reason": "",
            "reasoning_content_present": False,
            "reasoning_content_length": 0,
            "structured_output_mode": "json",
        }
        result = (self.cleaned_result, {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11}, response_state)
        if kwargs.get("return_response_state"):
            return result
        return result[:2]


class SequenceCleanupClient:
    def __init__(self, cleaned_results):
        self.cleaned_results = list(cleaned_results)
        self.calls = []

    def structured_chat_completion_with_usage(self, **kwargs):
        self.calls.append(kwargs)
        cleaned_result = self.cleaned_results[min(len(self.calls) - 1, len(self.cleaned_results) - 1)]
        response_state = {
            "provider": "openrouter",
            "effective_model": "editor-model",
            "thinking_requested": False,
            "thinking_applied": False,
            "thinking_budget": None,
            "thinking_effort": None,
            "fallback_used": False,
            "fallback_reason": "",
            "reasoning_content_present": False,
            "reasoning_content_length": 0,
            "structured_output_mode": "json",
        }
        result = (cleaned_result, {"prompt_tokens": 5, "completion_tokens": 6, "total_tokens": 11}, response_state)
        if kwargs.get("return_response_state"):
            return result
        return result[:2]


def cleanup_enabled_request():
    return {
        "cleanup_requested": True,
        "cleanup_attempted": False,
        "cleanup_applied": False,
        "cleanup_provider": "openrouter",
        "cleanup_effective_model": "editor-model",
        "cleanup_thinking_requested": False,
        "cleanup_thinking_applied": False,
        "cleanup_budget": None,
        "cleanup_effort": None,
        "cleanup_fallback_used": False,
        "cleanup_reasoning_content_present": False,
        "cleanup_structured_validated": False,
    }


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


def test_build_analysis_cache_key_separates_cleanup_and_plain():
    plain_key = cache.build_analysis_cache_key(
        "test.12345",
        {
            "provider": "deepseek",
            "effective_model": "deepseek-chat",
            "thinking_applied": False,
            "cleanup_requested": False,
        },
    )
    cleaned_key = cache.build_analysis_cache_key(
        "test.12345",
        {
            "provider": "deepseek",
            "effective_model": "deepseek-chat",
            "thinking_applied": False,
            "cleanup_requested": True,
            "cleanup_provider": "openrouter",
            "cleanup_effective_model": "editor-model",
            "cleanup_thinking_applied": False,
        },
    )

    assert plain_key != cleaned_key


def test_analyze_paper_applies_cleanup_blocks_and_aggregates_usage():
    paper = DummyPaper()
    original_result = analyzer.StructuredPaperAnalysis(
        chinese_title="原始标题",
        research_background="原始背景",
        main_results="原始结果",
        methods_and_tools="原始方法",
        comparison_with_previous_work="原始比较",
    )
    cleaned_result = analyzer.StructuredPaperAnalysis(
        chinese_title="清洗后标题",
        research_background="清洗后背景\n\n1. 补齐段落结构。",
        main_results="清洗后结果",
        methods_and_tools="清洗后方法",
        comparison_with_previous_work="清洗后比较",
    )
    cleanup_client = FakeCleanupClient(cleaned_result)

    def fake_get_request_config(thinking_mode=False):
        return {
            "provider": "deepseek",
            "effective_model": "deepseek-chat",
            "thinking_requested": thinking_mode,
            "thinking_applied": False,
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
        result = (original_result, {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}, response_state)
        if return_response_state:
            return result
        return result[:2]

    with patch.object(analyzer, "extract_pdf_text", return_value="pdf text"), patch.object(
        analyzer.ai_client, "get_analysis_request_config", side_effect=fake_get_request_config
    ), patch.object(
        analyzer, "get_analysis_cleanup_request_config", side_effect=cleanup_enabled_request
    ), patch.object(
        analyzer.ai_client, "structured_chat_completion_with_usage", side_effect=fake_structured_completion
    ), patch.object(analyzer, "analysis_cleanup_client", cleanup_client):
        analysis, usage, analysis_meta = analyzer.analyze_paper("paper.pdf", paper, use_cache=False, thinking_mode=False)

    assert analysis.startswith("# 清洗后标题")
    assert "清洗后背景" in analysis
    assert "1. 补齐段落结构。" in analysis
    assert usage["total_tokens"] == 18
    assert analysis_meta["cleanup_requested"] is True
    assert analysis_meta["cleanup_attempted"] is True
    assert analysis_meta["cleanup_applied"] is True
    assert analysis_meta["cleanup_provider"] == "openrouter"
    assert analysis_meta["cleanup_effective_model"] == "editor-model"
    assert analysis_meta["cleanup_structured_validated"] is True
    cleanup_prompt = cleanup_client.calls[0]["messages"][1]["content"]
    assert "论文元数据" in cleanup_prompt
    assert "[research_background]" in cleanup_prompt
    assert "英文标题: Test Paper" in cleanup_prompt


def test_analyze_paper_retries_cleanup_when_output_fails_validation():
    paper = DummyPaper()
    original_result = analyzer.StructuredPaperAnalysis(
        chinese_title="原始标题",
        research_background="原始背景",
        main_results="原始结果",
        methods_and_tools="原始方法",
        comparison_with_previous_work="原始比较",
    )
    invalid_cleanup = analyzer.StructuredPaperAnalysis(
        chinese_title="清洗后标题",
        research_background="$$\\nE(w)=1\n$$",
        main_results="清洗后结果",
        methods_and_tools="清洗后方法",
        comparison_with_previous_work="清洗后比较",
    )
    valid_cleanup = analyzer.StructuredPaperAnalysis(
        chinese_title="清洗后标题",
        research_background="$$\nE(w)=1\n$$",
        main_results="清洗后结果",
        methods_and_tools="清洗后方法",
        comparison_with_previous_work="清洗后比较",
    )
    cleanup_client = SequenceCleanupClient([invalid_cleanup, valid_cleanup])

    def fake_get_request_config(thinking_mode=False):
        return {
            "provider": "deepseek",
            "effective_model": "deepseek-chat",
            "thinking_requested": thinking_mode,
            "thinking_applied": False,
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
        result = (original_result, {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}, response_state)
        if return_response_state:
            return result
        return result[:2]

    with patch.object(analyzer, "extract_pdf_text", return_value="pdf text"), patch.object(
        analyzer.ai_client, "get_analysis_request_config", side_effect=fake_get_request_config
    ), patch.object(
        analyzer, "get_analysis_cleanup_request_config", side_effect=cleanup_enabled_request
    ), patch.object(
        analyzer.ai_client, "structured_chat_completion_with_usage", side_effect=fake_structured_completion
    ), patch.object(analyzer, "analysis_cleanup_client", cleanup_client):
        analysis, usage, analysis_meta = analyzer.analyze_paper("paper.pdf", paper, use_cache=False, thinking_mode=False)

    assert analysis.startswith("# 清洗后标题")
    assert "$$\nE(w)=1\n$$" in analysis
    assert "$$\\nE(w)=1\n$$" not in analysis
    assert usage["total_tokens"] == 29
    assert len(cleanup_client.calls) == 2
    retry_prompt = cleanup_client.calls[1]["messages"][1]["content"]
    assert "上一次输出未通过格式校验" in retry_prompt
    assert "存在非法块公式转义: $$\\n" in retry_prompt
    assert analysis_meta["cleanup_applied"] is True
    assert analysis_meta["cleanup_structured_validated"] is True


def test_analyze_paper_keeps_original_when_cleanup_fails():
    paper = DummyPaper()
    original_result = analyzer.StructuredPaperAnalysis(
        chinese_title="原始标题",
        research_background="原始背景",
        main_results="原始结果",
        methods_and_tools="原始方法",
        comparison_with_previous_work="原始比较",
    )

    def fake_get_request_config(thinking_mode=False):
        return {
            "provider": "deepseek",
            "effective_model": "deepseek-chat",
            "thinking_requested": thinking_mode,
            "thinking_applied": False,
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
        result = (original_result, {"total_tokens": 7}, response_state)
        if return_response_state:
            return result
        return result[:2]

    with patch.object(analyzer, "extract_pdf_text", return_value="pdf text"), patch.object(
        analyzer.ai_client, "get_analysis_request_config", side_effect=fake_get_request_config
    ), patch.object(
        analyzer, "get_analysis_cleanup_request_config", side_effect=cleanup_enabled_request
    ), patch.object(
        analyzer.ai_client, "structured_chat_completion_with_usage", side_effect=fake_structured_completion
    ), patch.object(
        analyzer, "analysis_cleanup_client"
    ) as cleanup_client:
        cleanup_client.structured_chat_completion_with_usage.side_effect = Exception("cleanup unavailable")
        analysis, usage, analysis_meta = analyzer.analyze_paper("paper.pdf", paper, use_cache=False, thinking_mode=False)

    assert analysis.startswith("# 原始标题")
    assert usage["total_tokens"] == 7
    assert analysis_meta["cleanup_requested"] is True
    assert analysis_meta["cleanup_attempted"] is True
    assert analysis_meta["cleanup_applied"] is False
    assert "cleanup unavailable" in analysis_meta["cleanup_error"]

#!/usr/bin/env python3

import datetime
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import analyzer
import cache
import config
import main


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


class DummyFuture:
    def __init__(self, value):
        self.value = value

    def result(self):
        return self.value


class CapturingExecutor:
    submissions = []

    def __init__(self, *args, **kwargs):
        type(self).submissions = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, *args):
        type(self).submissions.append((fn, args))
        return DummyFuture((-1, None))


class FakeCompletion:
    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise Exception("unsupported parameter: enable_thinking")
        usage = SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3)
        message = SimpleNamespace(content="analysis result", reasoning_content=None)
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice], usage=usage, model=kwargs["model"])


class FakeStructuredClient:
    def __init__(self):
        self.calls = []

    def create_with_completion(self, **kwargs):
        self.calls.append(kwargs)
        usage = SimpleNamespace(prompt_tokens=4, completion_tokens=5, total_tokens=9)
        message = SimpleNamespace(content="{}", reasoning_content="chain")
        choice = SimpleNamespace(message=message)
        raw_response = SimpleNamespace(choices=[choice], usage=usage, model=kwargs["model"])
        result = analyzer.StructuredPaperAnalysis(
            chinese_title="结构化标题",
            research_background="背景",
            main_results="结果",
            methods_and_tools="方法",
            comparison_with_previous_work="比较",
        )
        return result, raw_response


class BrokenStructuredClient:
    def __init__(self, error):
        self.error = error
        self.calls = []

    def create_with_completion(self, **kwargs):
        self.calls.append(kwargs)
        raise self.error


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


def test_batch_mode_threads_thinking_flag():
    paper = DummyPaper()
    argv = ["main.py", "--thinking"]

    with patch.object(sys, "argv", argv), patch.object(main, "configure_logging"), patch.object(
        main, "get_recent_papers", return_value=[paper]
    ), patch.object(main, "ThreadPoolExecutor", CapturingExecutor):
        main.main()

    assert CapturingExecutor.submissions
    submitted_args = CapturingExecutor.submissions[0][1]
    assert submitted_args[-1] is True


def test_batch_mode_without_cli_override_passes_none():
    paper = DummyPaper()
    argv = ["main.py"]

    with patch.object(sys, "argv", argv), patch.object(main, "configure_logging"), patch.object(
        main, "get_recent_papers", return_value=[paper]
    ), patch.object(main, "ThreadPoolExecutor", CapturingExecutor):
        main.main()

    assert CapturingExecutor.submissions
    submitted_args = CapturingExecutor.submissions[0][1]
    assert submitted_args[-1] is None


def test_qwen_thinking_request_falls_back_to_plain_mode():
    completion_fn = FakeCompletion()
    client = config.AIClient.__new__(config.AIClient)
    client.provider = "qwen"
    client.model = "qwen-turbo"
    client.provider_config = config.PROVIDER_CONFIG["qwen"]
    client.thinking_support = client.provider_config["thinking_support"]
    client.completion_fn = completion_fn

    content, usage, response_state = client.chat_completion_with_usage(
        messages=[{"role": "user", "content": "hello"}],
        thinking_mode=True,
        return_response_state=True,
    )

    assert content == "analysis result"
    assert usage["total_tokens"] == 3
    assert len(completion_fn.calls) == 2
    assert completion_fn.calls[0]["extra_body"]["enable_thinking"] is True
    assert "extra_body" not in completion_fn.calls[1]
    assert response_state["thinking_applied"] is False
    assert response_state["fallback_used"] is True


def test_structured_completion_returns_reasoning_metadata():
    structured_client = FakeStructuredClient()
    client = config.AIClient.__new__(config.AIClient)
    client.provider = "deepseek"
    client.model = "deepseek-chat"
    client.provider_config = config.PROVIDER_CONFIG["deepseek"]
    client.thinking_support = client.provider_config["thinking_support"]
    client.completion_fn = None

    with patch.object(client, "_get_structured_client", return_value=structured_client):
        result, usage, response_state = client.structured_chat_completion_with_usage(
            messages=[{"role": "user", "content": "hello"}],
            response_model=analyzer.StructuredPaperAnalysis,
            thinking_mode=True,
            return_response_state=True,
        )

    assert result.chinese_title == "结构化标题"
    assert usage["total_tokens"] == 9
    assert response_state["reasoning_content_present"] is True
    assert structured_client.calls[0]["messages"][0]["content"] == "hello"


def test_structured_completion_can_recover_json_from_reasoning_content():
    broken_client = BrokenStructuredClient(Exception("1 validation error for StructuredPaperAnalysis"))
    client = config.AIClient.__new__(config.AIClient)
    client.provider = "qwen"
    client.model = "qwen3-max"
    client.provider_config = config.PROVIDER_CONFIG["qwen"]
    client.thinking_support = client.provider_config["thinking_support"]

    def fake_completion(**kwargs):
        usage = SimpleNamespace(prompt_tokens=7, completion_tokens=8, total_tokens=15)
        message = SimpleNamespace(
            content="",
            reasoning_content='{"chinese_title":"恢复标题","research_background":"背景","main_results":"结果","methods_and_tools":"方法","comparison_with_previous_work":"比较"}',
        )
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice], usage=usage, model=kwargs["model"])

    client.completion_fn = fake_completion

    with patch.object(client, "_get_structured_client", return_value=broken_client):
        result, usage, response_state = client.structured_chat_completion_with_usage(
            messages=[{"role": "user", "content": "hello"}],
            response_model=analyzer.StructuredPaperAnalysis,
            thinking_mode=True,
            return_response_state=True,
        )

    assert result.chinese_title == "恢复标题"
    assert usage["total_tokens"] == 15
    assert response_state["thinking_applied"] is True
    assert response_state["fallback_used"] is False
    assert response_state["reasoning_content_present"] is True


def test_build_analysis_cache_key_separates_thinking_and_plain():
    plain_key = cache.build_analysis_cache_key(
        "test.12345",
        {"provider": "qwen", "effective_model": "qwen-turbo", "thinking_applied": False},
    )
    thinking_key = cache.build_analysis_cache_key(
        "test.12345",
        {"provider": "qwen", "effective_model": "qwen-turbo", "thinking_applied": True},
    )

    assert plain_key != thinking_key


def test_analyze_paper_uses_isolated_cache_keys_and_metadata():
    paper = DummyPaper()
    seen_cache_keys = []
    written_cache_entries = []
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
            "reasoning_content_present": thinking_mode,
            "reasoning_content_length": 10 if thinking_mode else 0,
        }
        result = (structured_result, {"total_tokens": 3}, response_state)
        if return_response_state:
            return result
        return result[:2]

    def fake_get_cached_analysis(key):
        seen_cache_keys.append(key)
        return None

    def fake_cache_analysis(key, value, metadata=None):
        written_cache_entries.append((key, value, metadata))
        return True

    with patch.object(analyzer, "extract_pdf_text", return_value="pdf text"), patch.object(
        analyzer.ai_client, "get_analysis_request_config", side_effect=fake_get_request_config
    ), patch.object(
        analyzer, "get_analysis_cleanup_request_config", side_effect=cleanup_disabled_request
    ), patch.object(
        analyzer.ai_client, "structured_chat_completion_with_usage", side_effect=fake_structured_completion
    ), patch.object(
        analyzer, "get_cached_analysis", side_effect=fake_get_cached_analysis
    ), patch.object(
        analyzer, "cache_analysis", side_effect=fake_cache_analysis
    ):
        _, _, plain_meta = analyzer.analyze_paper("paper.pdf", paper, use_cache=True, thinking_mode=False)
        _, _, thinking_meta = analyzer.analyze_paper("paper.pdf", paper, use_cache=True, thinking_mode=True)

    assert len(seen_cache_keys) == 2
    assert seen_cache_keys[0] != seen_cache_keys[1]
    assert written_cache_entries[0][0] != written_cache_entries[1][0]
    assert written_cache_entries[0][2]["structured_output_validated"] is True
    assert plain_meta["reasoning_content_present"] is False
    assert thinking_meta["reasoning_content_present"] is True


def test_analyze_paper_falls_back_to_prompt_when_structured_path_fails():
    paper = DummyPaper()
    seen_thinking_modes = []

    def fake_get_request_config(thinking_mode=False):
        return {
            "provider": "deepseek",
            "effective_model": "deepseek-reasoner" if thinking_mode else "deepseek-chat",
            "thinking_requested": thinking_mode,
            "thinking_applied": thinking_mode,
            "thinking_budget": None,
            "thinking_effort": None,
            "structured_mode": "json",
        }

    def fake_raw_completion(messages, thinking_mode=False, return_response_state=False, **kwargs):
        seen_thinking_modes.append(thinking_mode)
        response_state = {
            **fake_get_request_config(thinking_mode=thinking_mode),
            "fallback_used": False,
            "fallback_reason": "",
            "reasoning_content_present": True,
            "reasoning_content_length": 12,
        }
        result = (
            "# 测试标题\n\n## 详细分析\n\n### 1. 研究对象和背景\n背景\n\n### 2. 主要定理或主要结果\n结果",
            {"total_tokens": 6},
            response_state,
        )
        if return_response_state:
            return result
        return result[:2]

    with patch.object(analyzer, "extract_pdf_text", return_value="pdf text"), patch.object(
        analyzer.ai_client, "get_analysis_request_config", side_effect=fake_get_request_config
    ), patch.object(
        analyzer, "get_analysis_cleanup_request_config", side_effect=cleanup_disabled_request
    ), patch.object(
        analyzer.ai_client,
        "structured_chat_completion_with_usage",
        side_effect=Exception("json schema unsupported"),
    ), patch.object(
        analyzer.ai_client, "chat_completion_with_usage", side_effect=fake_raw_completion
    ):
        analysis, _, analysis_meta = analyzer.analyze_paper("paper.pdf", paper, use_cache=False, thinking_mode=True)

    assert analysis.startswith("# 测试标题")
    assert analysis_meta["structured_output_validated"] is False
    assert analysis_meta["structured_output_fallback"] is True
    assert analysis_meta["reasoning_content_present"] is True
    assert analysis_meta["thinking_applied"] is False
    assert seen_thinking_modes == [False]


def test_deepseek_thinking_uses_reasoner_model():
    client = config.AIClient.__new__(config.AIClient)
    client.provider = "deepseek"
    client.model = "deepseek-chat"
    client.provider_config = config.PROVIDER_CONFIG["deepseek"]
    client.thinking_support = client.provider_config["thinking_support"]
    client.completion_fn = None

    with patch.object(config, "ANALYSIS_THINKING_MODEL", None):
        request_config = client.get_analysis_request_config(thinking_mode=True)

    assert request_config["thinking_applied"] is True
    assert request_config["effective_model"] == "deepseek-reasoner"


def test_analysis_request_config_respects_env_default_thinking_mode():
    client = config.AIClient.__new__(config.AIClient)
    client.provider = "deepseek"
    client.model = "deepseek-chat"
    client.provider_config = config.PROVIDER_CONFIG["deepseek"]
    client.thinking_support = client.provider_config["thinking_support"]
    client.completion_fn = None

    with patch.object(config, "ANALYSIS_THINKING_MODE", True), patch.object(config, "ANALYSIS_THINKING_MODEL", None):
        request_config = client.get_analysis_request_config(thinking_mode=None)

    assert request_config["thinking_requested"] is True
    assert request_config["thinking_applied"] is True
    assert request_config["effective_model"] == "deepseek-reasoner"

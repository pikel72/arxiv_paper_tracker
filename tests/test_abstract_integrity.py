import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import translator
import utils
from models import SimplePaper


def test_daily_report_keeps_multiline_abstract_and_formulas():
    # 重现 SQG 日报：第一行以“使得”结尾，真正结论与唯一性位于后续行。
    abstract = "我们构造解，使得\n\n$$\n\\theta(t)\\notin H^\\sigma.\n$$\n\n该解在指定类别中唯一。"
    translation = f"**中文标题**: 测试标题\n\n**摘要翻译**: {abstract}"
    paper = SimplePaper(SimpleNamespace(
        title="Test Paper", authors=[], published="2026-10-08T14:10:59Z",
        tags=[], id="http://arxiv.org/abs/2610.12011v1", summary="Original abstract",
    ))
    with TemporaryDirectory() as directory:
        with patch.object(utils, "RESULTS_DIR", Path(directory)), patch(
            "utils.translate_abstract_with_deepseek", return_value=translation,
        ):
            path = utils.write_to_conclusion([(paper, "# 测试标题")], [], filename="daily.md")
        report = path.read_text(encoding="utf-8")
    assert f"**摘要翻译**: {abstract}" in report


def test_abstract_extraction_stops_before_next_field():
    translation = "**摘要翻译**:\n第一段。\n\n第二段。\n\n**备注**: 其他内容"
    assert utils._extract_abstract_translation(translation) == "第一段。\n\n第二段。"


def test_structured_translation_restores_original_math_without_model_escaping():
    paper = SimpleNamespace(
        title=r"On $H^s$", summary=r"We prove $\theta_0\in H^s$ and \[\theta(t)\notin H^\sigma.\]",
        get_short_id=lambda: "2610.12011v1",
    )
    client = MagicMock()
    client.structured_chat_completion_with_usage.return_value = (
        translator.StructuredAbstractTranslation(
            chinese_title="关于 ARXIV_MATH_0000",
            abstract_translation="我们证明 ARXIV_MATH_0001。\n\nARXIV_MATH_0002",
        ), {},
    )
    with patch("translator.get_ai_client", return_value=client):
        result = translator.translate_abstract_with_deepseek(paper, use_cache=False)
    prompt = client.structured_chat_completion_with_usage.call_args.kwargs["messages"][-1]["content"]
    assert paper.summary not in prompt
    assert "ARXIV_MATH_0002" in prompt
    assert result == "**中文标题**: 关于 $H^s$\n\n**摘要翻译**: 我们证明 $\\theta_0\\in H^s$。\n\n\\[\\theta(t)\\notin H^\\sigma.\\]"


def test_missing_formula_triggers_text_fallback_with_same_protection():
    paper = SimpleNamespace(title="SQG", summary=r"For $1<s<2$, we prove a theorem.", get_short_id=lambda: "sqg")
    client = MagicMock()
    client.structured_chat_completion_with_usage.return_value = (
        translator.StructuredAbstractTranslation(chinese_title="SQG", abstract_translation="被截断的摘要。"), {},
    )
    client.chat_completion.return_value = "**中文标题**: SQG\n\n**摘要翻译**: 对 ARXIV_MATH_0000，我们证明定理。"
    with patch("translator.get_ai_client", return_value=client):
        result = translator.translate_abstract_with_deepseek(paper, use_cache=False)
    assert "$1<s<2$" in result
    assert "ARXIV_MATH_0000" in client.chat_completion.call_args.kwargs["messages"][-1]["content"]


@pytest.mark.parametrize("text", ["公式遗漏", "ARXIV_MATH_0000 ARXIV_MATH_0000", "\x05mathbb ARXIV_MATH_0000"])
def test_rejects_incomplete_or_corrupt_translation(text):
    with pytest.raises(ValueError):
        translator._restore_translation_math(text, {"ARXIV_MATH_0000": r"$\mathbb R^2$"})


def test_math_protection_handles_display_inline_and_escaped_dollar():
    summary = r"Cost \$5; $x$; $$\theta\in H^s$$; \(y\); \[z\]."
    paper = SimpleNamespace(title="ARXIV_MATH_ is literal text", summary=summary)
    protected, fragments = translator._protect_translation_math(paper)
    assert len(fragments) == 4
    assert r"\$5" in protected.summary
    assert translator._restore_translation_math(protected.summary, fragments) == summary


def test_old_translation_cache_is_not_reused():
    paper = SimpleNamespace(title="SQG", summary="A theorem.", get_short_id=lambda: "sqg")
    with patch("translator.get_cached_translation", return_value="valid new cache") as get_cache:
        assert translator.translate_abstract_with_deepseek(paper) == "valid new cache"
    assert get_cache.call_args.args == ("sqg:translation_v2_verbatim_math",)

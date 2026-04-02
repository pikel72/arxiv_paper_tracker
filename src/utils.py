# utils.py - 工具函数模块

import datetime
import logging
from pathlib import Path

from analyzer import extract_analysis_title, render_analysis_body
from config import RESULTS_DIR

logger = logging.getLogger(__name__)


def _extract_chinese_title(text: str) -> str:
    return extract_analysis_title(text, "").strip()


def _extract_abstract_translation(text: str) -> str:
    if not text or "**摘要翻译**:" not in text:
        return ""
    lines = text.split("\n")
    for idx, line in enumerate(lines):
        if line.startswith("**摘要翻译**:"):
            content = line.replace("**摘要翻译**:", "").strip()
            if content:
                return content
            tail = []
            for rest in lines[idx + 1:]:
                if rest.startswith("**") and rest.endswith("**:"):
                    break
                if rest.strip():
                    tail.append(rest.strip())
            return "\n".join(tail).strip()
    return ""


def _get_paper_comment(paper) -> str:
    comment = getattr(paper, "comment", None) or getattr(paper, "comments", None) or getattr(paper, "arxiv_comment", None)
    if comment:
        return str(comment).strip()
    return ""


def _strip_analysis_heading(text: str) -> str:
    return render_analysis_body(text)


def _resolve_priority_title(title: str, analysis: str, translation: str) -> str:
    return _extract_chinese_title(translation) or _extract_chinese_title(analysis) or title


def _split_priority_entry(entry):
    if len(entry) >= 3 and isinstance(entry[2], dict):
        return entry[0], entry[1], entry[2]
    return entry[0], entry[1], {}


def _write_analysis_metadata_block(f, analysis_meta, ai_model):
    if not analysis_meta:
        return
    if analysis_meta.get("provider"):
        f.write(f"ai_provider: {analysis_meta.get('provider')}\n")
    if analysis_meta.get("effective_model"):
        f.write(f"effective_model: {analysis_meta.get('effective_model')}\n")
    else:
        f.write(f"effective_model: {ai_model}\n")
    f.write(f"thinking_applied: {bool(analysis_meta.get('thinking_applied'))}\n")
    f.write(f"fallback_used: {bool(analysis_meta.get('fallback_used'))}\n")
    f.write(f"reasoning_content_present: {bool(analysis_meta.get('reasoning_content_present'))}\n")
    f.write(f"structured_output_validated: {bool(analysis_meta.get('structured_output_validated'))}\n")
    f.write(f"structured_output_fallback: {bool(analysis_meta.get('structured_output_fallback'))}\n")
    f.write(f"cleanup_requested: {bool(analysis_meta.get('cleanup_requested'))}\n")
    f.write(f"cleanup_attempted: {bool(analysis_meta.get('cleanup_attempted'))}\n")
    f.write(f"cleanup_applied: {bool(analysis_meta.get('cleanup_applied'))}\n")
    if analysis_meta.get("cleanup_provider"):
        f.write(f"cleanup_provider: {analysis_meta.get('cleanup_provider')}\n")
    if analysis_meta.get("cleanup_effective_model"):
        f.write(f"cleanup_effective_model: {analysis_meta.get('cleanup_effective_model')}\n")
    f.write(f"cleanup_thinking_applied: {bool(analysis_meta.get('cleanup_thinking_applied'))}\n")
    f.write(f"cleanup_fallback_used: {bool(analysis_meta.get('cleanup_fallback_used'))}\n")
    f.write(f"cleanup_reasoning_content_present: {bool(analysis_meta.get('cleanup_reasoning_content_present'))}\n")
    f.write(f"cleanup_structured_validated: {bool(analysis_meta.get('cleanup_structured_validated'))}\n")
    if analysis_meta.get("cleanup_validation_error"):
        f.write(f"cleanup_validation_error: |\n")
        for line in str(analysis_meta.get("cleanup_validation_error")).splitlines():
            f.write(f"  {line}\n")
    f.write(f"from_cache: {bool(analysis_meta.get('from_cache'))}\n")
    if analysis_meta.get("estimated_prompt_tokens") is not None:
        f.write(f"estimated_prompt_tokens: {analysis_meta.get('estimated_prompt_tokens')}\n")
    if analysis_meta.get("pdf_text_length") is not None:
        f.write(f"pdf_text_length: {analysis_meta.get('pdf_text_length')}\n")
    if analysis_meta.get("pdf_text_pages") is not None:
        f.write(f"pdf_text_pages: {analysis_meta.get('pdf_text_pages')}\n")


def _write_usage_block(f, usage):
    if not usage:
        return
    f.write("token_usage:\n")
    f.write(f"  prompt_tokens: {usage.get('prompt_tokens', 0)}\n")
    f.write(f"  completion_tokens: {usage.get('completion_tokens', 0)}\n")
    f.write(f"  total_tokens: {usage.get('total_tokens', 0)}\n")
    if "reasoning_tokens" in usage:
        f.write(f"  reasoning_tokens: {usage.get('reasoning_tokens', 0)}\n")


def write_single_analysis(
    paper,
    analysis,
    filename: str = None,
    usage: dict = None,
    analysis_meta: dict = None,
    thinking_mode: bool = None,
):
    import re

    today = datetime.datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    time_str = today.strftime("%H-%M-%S")
    if filename:
        md_file = RESULTS_DIR / filename
    else:
        md_file = RESULTS_DIR / f"arxiv_{paper.get_short_id().replace('/', '_')}_{date_str}_{time_str}.md"
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    author_names = [author.name for author in paper.authors]
    title = re.sub(r"\s+", " ", paper.title).strip()
    from translator import translate_abstract_with_deepseek
    translation = translate_abstract_with_deepseek(paper, translate_title_only=False, use_cache=True)
    chinese_title = _resolve_priority_title(title, analysis, translation)
    analysis_body = _strip_analysis_heading(analysis)
    abstract_translation = _extract_abstract_translation(translation)
    paper_comment = _get_paper_comment(paper)
    datetime_str = today.strftime("%Y-%m-%d %H:%M:%S")
    from config import AI_MODEL
    resolved_thinking_mode = bool((analysis_meta or {}).get("thinking_requested", thinking_mode))

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"title: \"{chinese_title if chinese_title else title}\"\n")
        f.write(f"date: {datetime_str}\n")
        f.write(f"description: {', '.join(author_names)}\n")
        f.write(f"ai_model: {AI_MODEL}\n")
        f.write(f"arxiv_id: {paper.get_short_id()}\n")
        f.write(f"thinking_mode: {resolved_thinking_mode}\n")
        _write_analysis_metadata_block(f, analysis_meta or {}, AI_MODEL)
        _write_usage_block(f, usage or {})
        f.write("---\n")
        f.write(f"# {chinese_title if chinese_title else title}\n")
        if chinese_title != title:
            f.write(f"{title}\n\n")
        f.write(f"**作者**: {', '.join(author_names)}\n\n")
        f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
        f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
        f.write(f"**arXiv ID**: {paper.get_short_id()}\n\n")
        if abstract_translation:
            f.write(f"**摘要翻译**: {abstract_translation}\n\n")
        else:
            f.write(f"**摘要**: {paper.summary}\n\n")
        f.write(f"**Comment**: {paper_comment if paper_comment else '无'}\n\n")
        f.write(f"**链接**: {paper.entry_id}\n\n")
        f.write(f"{analysis_body}\n\n")
    logger.info("单论文分析结果已写入 %s", md_file.absolute())
    return md_file


def write_pdf_analysis(
    pdf_path,
    analysis,
    filename: str = None,
    usage: dict = None,
    analysis_meta: dict = None,
    thinking_mode: bool = None,
):
    pdf_path = Path(pdf_path)
    today = datetime.datetime.now()
    time_str = today.strftime("%H-%M-%S")
    if filename:
        md_file = RESULTS_DIR / filename
    else:
        md_file = RESULTS_DIR / f"pdf_{pdf_path.stem}_{today.strftime('%Y-%m-%d')}_{time_str}.md"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    chinese_title = _extract_chinese_title(analysis) or pdf_path.stem
    analysis_body = _strip_analysis_heading(analysis)
    datetime_str = today.strftime("%Y-%m-%d %H:%M:%S")
    from config import AI_MODEL
    resolved_thinking_mode = bool((analysis_meta or {}).get("thinking_requested", thinking_mode))

    with open(md_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"title: \"{chinese_title}\"\n")
        f.write(f"date: {datetime_str}\n")
        f.write("source: local_pdf\n")
        f.write(f"pdf_file: {pdf_path.name}\n")
        f.write(f"ai_model: {AI_MODEL}\n")
        f.write(f"thinking_mode: {resolved_thinking_mode}\n")
        _write_analysis_metadata_block(f, analysis_meta or {}, AI_MODEL)
        _write_usage_block(f, usage or {})
        f.write("---\n\n")
        f.write(f"# {chinese_title}\n\n")
        f.write(f"{analysis_body}\n")

    logger.info("PDF 分析结果已写入 %s", md_file.absolute())
    return md_file


def write_to_conclusion(priority_analyses, secondary_analyses, irrelevant_papers=None, filename: str = None):
    today = datetime.datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    time_str = today.strftime("%H-%M-%S")
    datetime_str = today.strftime("%Y-%m-%d %H:%M:%S")
    from config import AI_MODEL

    if filename:
        conclusion_file = RESULTS_DIR / filename
    else:
        filename = f"arxiv_analysis_{date_str}_{time_str}.md"
        conclusion_file = RESULTS_DIR / filename

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(conclusion_file, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"title: \"{today.strftime('%Y年%m月%d日')}论文分析\"\n")
        f.write(f"date: {datetime_str}\n")
        f.write(f"description: 共有 {len(priority_analyses)} 篇重点关注论文, {len(secondary_analyses)} 篇论文可以了解")
        if irrelevant_papers:
            f.write(f", {len(irrelevant_papers)} 篇不相关论文")
        f.write(f"\nai_model: {AI_MODEL}\n---\n\n")
        f.write(f"**生成时间**: {today.strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
        f.write(f"**重点关注论文数量**: {len(priority_analyses)}\n\n")
        f.write(f"**了解领域论文数量**: {len(secondary_analyses)}\n\n")
        if irrelevant_papers:
            f.write(f"**不相关论文数量**: {len(irrelevant_papers)}\n")
        f.write("\n")

        if priority_analyses:
            f.write("# 重点关注论文（完整分析）\n\n")
            for i, entry in enumerate(priority_analyses, 1):
                paper, analysis, analysis_meta = _split_priority_entry(entry)
                author_names = [author.name for author in paper.authors]
                import re
                title = re.sub(r"\s+", " ", paper.title).strip()

                from translator import translate_abstract_with_deepseek
                translation = translate_abstract_with_deepseek(paper, translate_title_only=False, use_cache=True)
                chinese_title = _resolve_priority_title(title, analysis, translation)
                analysis_body = _strip_analysis_heading(analysis)
                abstract_translation = _extract_abstract_translation(translation)
                paper_comment = _get_paper_comment(paper)

                f.write(f"## {i}. {chinese_title if chinese_title else title}\n\n")
                if chinese_title != title:
                    f.write(f"{title}\n\n")

                f.write(f"**作者**: {', '.join(author_names)}\n\n")
                f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
                f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
                f.write(f"**arXiv ID**: {paper.get_short_id()}\n\n")
                if abstract_translation:
                    f.write(f"**摘要翻译**: {abstract_translation}\n\n")
                else:
                    f.write(f"**摘要**: {paper.summary}\n\n")
                f.write(f"**Comment**: {paper_comment if paper_comment else '无'}\n\n")
                f.write(f"**链接**: {paper.entry_id}\n\n")
                f.write(f"{analysis_body}\n\n")
                f.write("---\n\n")

        if secondary_analyses:
            f.write("# 了解领域论文（摘要翻译）\n\n")
            for i, (paper, translation) in enumerate(secondary_analyses, 1):
                author_names = [author.name for author in paper.authors]
                import re
                title = re.sub(r"\s+", " ", paper.title).strip()
                chinese_title = _extract_chinese_title(translation)

                f.write(f"## {i}. {chinese_title if chinese_title else title}\n\n")
                if chinese_title:
                    f.write(f"**{title}**\n\n")

                f.write(f"**作者**: {', '.join(author_names)}\n\n")
                f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
                f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
                f.write(f"**arXiv ID**: {paper.get_short_id()}\n\n")
                f.write(f"**链接**: {paper.entry_id}\n\n")
                f.write(f"### 摘要翻译\n\n{translation}\n\n")
                f.write("---\n\n")

        if irrelevant_papers:
            f.write("# 不相关论文（基本信息）\n\n")
            for i, (paper, reason, title_translation) in enumerate(irrelevant_papers, 1):
                author_names = [author.name for author in paper.authors]
                import re
                title = re.sub(r"\s+", " ", paper.title).strip()
                chinese_title = _extract_chinese_title(title_translation)

                f.write(f"## {i}. {chinese_title if chinese_title else title}\n\n")
                if chinese_title:
                    f.write(f"**{title}**\n\n")

                f.write(f"**作者**: {', '.join(author_names)}\n\n")
                f.write(f"**类别**: {', '.join(paper.categories)}\n\n")
                f.write(f"**发布日期**: {paper.published.strftime('%Y-%m-%d')}\n\n")
                f.write(f"**arXiv ID**: {paper.get_short_id()}\n\n")
                f.write(f"**链接**: {paper.entry_id}\n\n")
                f.write(f"**摘要**: {paper.summary}\n\n")
                f.write("---\n\n")

    logger.info("分析结果已写入 %s", conclusion_file.absolute())
    return conclusion_file


def delete_pdf(pdf_path):
    try:
        if pdf_path.exists():
            pdf_path.unlink()
            logger.info("已删除PDF文件: %s", pdf_path)
        else:
            logger.info("PDF文件不存在，无需删除: %s", pdf_path)
    except Exception as e:
        logger.error("删除PDF文件失败 %s: %s", pdf_path, str(e))


def download_paper(paper, output_dir):
    import random
    import time

    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{paper.get_short_id().replace('/', '_')}.pdf"

    if pdf_path.exists():
        logger.info("论文已下载: %s", pdf_path)
        return pdf_path

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info("正在下载 (尝试 %s/%s): %s", attempt + 1, max_retries, paper.title)
            paper.download_pdf(str(pdf_path))
            logger.info("已下载到 %s", pdf_path)
            return pdf_path
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 5 + random.uniform(0, 2)
                logger.warning("下载论文失败 %s: %s。将在 %.1fs 后重试...", paper.title, str(e), wait_time)
                time.sleep(wait_time)
            else:
                logger.error("下载论文在 %s 次尝试后仍然失败 %s: %s", max_retries, paper.title, str(e))
                return None

# analyzer.py - 分析论文模块

import logging
import re

import pdfplumber
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cache import (
    build_analysis_cache_key,
    cache_analysis,
    cache_classification,
    get_cached_analysis,
    get_cached_classification,
)
from config import PRIORITY_TOPICS, SECONDARY_TOPICS, ai_client

logger = logging.getLogger(__name__)

ANALYSIS_SCHEMA_VERSION = "paper_analysis_v1"

SECTION_SPECS = [
    ("研究对象和背景", ["研究对象和背景", "研究对象与背景", "背景与研究对象", "研究背景", "背景"]),
    ("主要定理或主要结果", ["主要定理或主要结果", "主要结果", "主要定理", "核心结果", "关键结果"]),
    (
        "研究方法、关键技术和核心工具",
        ["研究方法、关键技术和核心工具", "研究方法与关键技术", "方法与工具", "研究方法", "方法", "技术路线"],
    ),
    (
        "与之前工作的比较",
        ["与之前工作的比较", "与已有工作比较", "与先前工作比较", "与相关工作比较", "对比已有工作", "相关工作比较", "对比"],
    ),
]


class StructuredPaperAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chinese_title: str = Field(description="论文标题的学术化中文翻译，只输出标题文本。")
    research_background: str = Field(description="自然段说明研究对象、数学背景、问题动机与研究意义。")
    main_results: str = Field(description="自然段总结主要定理、核心结论与适用条件。")
    methods_and_tools: str = Field(description="自然段说明研究方法、关键技术、证明工具或分析框架。")
    comparison_with_previous_work: str = Field(description="自然段比较本文与既有工作的差异、推进与局限。")

    @field_validator("chinese_title", mode="before")
    @classmethod
    def normalize_title(cls, value):
        text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
        if not text:
            raise ValueError("中文标题不能为空")
        return text

    @field_validator(
        "research_background",
        "main_results",
        "methods_and_tools",
        "comparison_with_previous_work",
        mode="before",
    )
    @classmethod
    def normalize_section(cls, value):
        text = str(value or "").replace("\r\n", "\n").strip()
        if not text:
            raise ValueError("分析章节不能为空")
        return text


class StructuredTopicClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    priority: int = Field(description="分类优先级，只能是 0、1、2。0 表示不相关，1 表示优先级1，2 表示优先级2。")
    reason: str = Field(description="分类原因。priority 为 1 或 2 时应简洁解释；priority 为 0 时可写不相关。")

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value):
        priority = int(value)
        if priority not in (0, 1, 2):
            raise ValueError("priority 必须是 0、1 或 2")
        return priority

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value):
        text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
        return text or "不相关"

    @model_validator(mode="after")
    def validate_reason_length(self):
        if self.priority in (1, 2) and len(self.reason) > 40:
            raise ValueError("priority 1/2 的 reason 应保持简洁")
        return self


def _clean_heading_candidate(line: str):
    candidate = re.sub(r"^[#\s>*-]+", "", line)
    candidate = re.sub(r"^\d+\s*[.\、]\s*", "", candidate)
    candidate = candidate.replace("**", "").replace("__", "").strip()
    return candidate


def _match_section_heading(line: str):
    candidate = _clean_heading_candidate(line)
    if not candidate:
        return None, ""
    for canonical, aliases in SECTION_SPECS:
        for alias in aliases:
            if candidate == alias:
                return canonical, ""
            if candidate.startswith(alias):
                tail = candidate[len(alias):]
                if not tail:
                    return canonical, ""
                if tail[0] in " :：（(":
                    return canonical, tail.lstrip(" :：").strip()
    return None, ""


def extract_analysis_sections(raw_text: str):
    text = (raw_text or "").replace("\r\n", "\n")
    lines = text.split("\n")
    headings = []
    seen = set()

    for idx, line in enumerate(lines):
        canonical, inline_content = _match_section_heading(line)
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        headings.append((idx, canonical, inline_content))

    sections = {canonical: "" for canonical, _ in SECTION_SPECS}
    for index, (line_idx, canonical, inline_content) in enumerate(headings):
        next_idx = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
        content_lines = []
        if inline_content:
            content_lines.append(inline_content)
        content_lines.extend(lines[line_idx + 1:next_idx])
        sections[canonical] = "\n".join(content_lines).strip()

    return sections


def extract_analysis_title(raw_text: str, fallback: str):
    text = (raw_text or "").replace("\r\n", "\n")
    lines = text.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title

    match = re.search(r"\*{0,2}中文标题\*{0,2}\s*[:：]\s*(.+)", text)
    if match:
        title = match.group(1).strip()
        if title:
            return title

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(
            (
                "## ",
                "### ",
                "**作者**",
                "**类别**",
                "**摘要**",
                "论文标题:",
                "作者:",
                "类别:",
                "发布时间:",
                "摘要:",
                "论文PDF内容:",
            )
        ):
            continue
        next_nonempty = ""
        for next_line in lines[idx + 1:]:
            next_nonempty = next_line.strip()
            if next_nonempty:
                break
        if next_nonempty.startswith("## 详细分析"):
            return stripped.replace("**", "").strip()

    return fallback


def render_analysis_body(raw_text: str):
    sections = extract_analysis_sections(raw_text)

    def section_or_placeholder(key: str):
        content = (sections.get(key) or "").strip()
        return content if content else "（模型未给出相关内容）"

    return (
        "### 1. 研究对象和背景\n"
        f"{section_or_placeholder('研究对象和背景')}\n\n"
        "### 2. 主要定理或主要结果\n"
        f"{section_or_placeholder('主要定理或主要结果')}\n\n"
        "### 3. 研究方法、关键技术和核心工具\n"
        f"{section_or_placeholder('研究方法、关键技术和核心工具')}\n\n"
        "### 4. 与之前工作的比较\n"
        f"{section_or_placeholder('与之前工作的比较')}\n"
    )


def normalize_analysis_markdown(raw_text: str, zh_title: str):
    return f"# {zh_title}\n\n## 详细分析\n\n{render_analysis_body(raw_text)}"


def render_structured_analysis_markdown(analysis: StructuredPaperAnalysis):
    return (
        f"# {analysis.chinese_title}\n\n"
        "## 详细分析\n\n"
        "### 1. 研究对象和背景\n"
        f"{analysis.research_background.strip()}\n\n"
        "### 2. 主要定理或主要结果\n"
        f"{analysis.main_results.strip()}\n\n"
        "### 3. 研究方法、关键技术和核心工具\n"
        f"{analysis.methods_and_tools.strip()}\n\n"
        "### 4. 与之前工作的比较\n"
        f"{analysis.comparison_with_previous_work.strip()}\n"
    )


def extract_pdf_text(pdf_path, max_pages=10):
    try:
        text_content = ""
        with pdfplumber.open(pdf_path) as pdf:
            if max_pages is None:
                pages_to_read = len(pdf.pages)
            else:
                pages_to_read = min(len(pdf.pages), max_pages)

            for i in range(pages_to_read):
                page = pdf.pages[i]
                page_text = page.extract_text()
                if page_text:
                    text_content += f"\n=== 第{i + 1}页 ===\n{page_text}\n"

        logger.info("成功从PDF提取文本，共%s页", pages_to_read)
        return text_content
    except Exception as e:
        logger.error("PDF文本提取失败 %s: %s", pdf_path, str(e))
        return f"PDF文本提取失败: {str(e)}"


def _build_structured_analysis_messages(pdf_content, paper=None, title=None):
    if paper is not None:
        author_names = [author.name for author in paper.authors]
        paper_context = (
            f"论文标题: {paper.title}\n"
            f"作者: {', '.join(author_names)}\n"
            f"类别: {', '.join(paper.categories)}\n"
            f"发布时间: {paper.published}\n\n"
            f"论文摘要: {paper.summary}\n"
        )
    else:
        paper_context = ""
        if title:
            paper_context += f"文件标题提示: {title}\n"

    prompt = (
        "请严格按照给定的结构化 schema 返回论文分析。\n\n"
        "内容要求：\n"
        "1. 所有字段都必须使用中文。\n"
        "2. `research_background`、`main_results`、`methods_and_tools`、`comparison_with_previous_work` 都必须使用自然段，不要使用列表。\n"
        "3. 公式格式：行内公式用 $...$，行间公式用 $$...$$，不要使用 \\[...\\]。\n"
        "4. 如果 PDF 摘录中无法支持某个判断，请明确说明“从提供内容中无法确认”或“作者未显式展开比较”，不要编造。\n"
        "5. `chinese_title` 只放中文标题，不要附加前缀、解释或换行。\n\n"
        "请基于以下论文信息与 PDF 文本完成结构化分析：\n\n"
        f"{paper_context}\n"
        "论文PDF内容:\n"
        f"{pdf_content}\n"
    )
    return [
        {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复，并严格遵守返回 schema。"},
        {"role": "user", "content": prompt},
    ]


def _build_fallback_analysis_messages(pdf_content, paper=None, title=None):
    if paper is not None:
        author_names = [author.name for author in paper.authors]
        context = (
            f"论文标题: {paper.title}\n"
            f"作者: {', '.join(author_names)}\n"
            f"类别: {', '.join(paper.categories)}\n"
            f"发布时间: {paper.published}\n\n"
            f"论文摘要: {paper.summary}\n"
        )
    else:
        title_hint = title or "请根据 PDF 首页自行识别论文标题"
        context = f"文件标题提示: {title_hint}\n"

    prompt = (
        "请使用中文回答，并以 Markdown 格式输出。\n\n"
        "# 中文标题\n\n"
        "## 详细分析\n\n"
        "### 1. 研究对象和背景\n"
        "[自然段内容]\n\n"
        "### 2. 主要定理或主要结果\n"
        "[自然段内容]\n\n"
        "### 3. 研究方法、关键技术和核心工具\n"
        "[自然段内容]\n\n"
        "### 4. 与之前工作的比较\n"
        "[自然段内容]\n\n"
        "要求：\n"
        "1. 标题必须按以上层级输出。\n"
        "2. 不要把章节标题加粗。\n"
        "3. 章节内容使用自然段，不要列表。\n"
        "4. 行内公式使用 $...$，行间公式使用 $$...$$，不要使用 \\[...\\]。\n\n"
        "请分析以下论文：\n\n"
        f"{context}\n"
        "论文PDF内容:\n"
        f"{pdf_content}\n"
    )
    return [
        {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复。"},
        {"role": "user", "content": prompt},
    ]


def _finalize_analysis_meta(response_state, structured_validated, structured_fallback, from_cache=False, structured_error=""):
    meta = dict(response_state or {})
    meta["analysis_schema_version"] = ANALYSIS_SCHEMA_VERSION
    meta["structured_output_validated"] = bool(structured_validated)
    meta["structured_output_fallback"] = bool(structured_fallback)
    meta["from_cache"] = bool(from_cache)
    if structured_error:
        meta["structured_error"] = structured_error
    return meta


def _prepare_cached_analysis(request_state, cached_payload):
    analysis_text, cached_meta = cached_payload
    if cached_meta:
        meta = dict(cached_meta)
    else:
        meta = _finalize_analysis_meta(
            {
                **request_state,
                "fallback_used": False,
                "fallback_reason": "",
                "reasoning_content_present": False,
                "reasoning_content_length": 0,
                "structured_output_mode": request_state.get("structured_mode"),
            },
            structured_validated=False,
            structured_fallback=False,
        )
    meta["from_cache"] = True
    return analysis_text, {}, meta


def _build_classification_messages(paper, abstract):
    author_names = [author.name for author in paper.authors]
    prompt = (
        "请严格按照给定的结构化 schema 返回分类结果。\n\n"
        "你需要判断论文与我关注主题的相关性，并返回：\n"
        "1. `priority`: 只能是 0、1、2。0 表示不相关，1 表示重点关注，2 表示了解领域。\n"
        "2. `reason`: 给出简短原因。priority 为 1 或 2 时尽量控制在 20 字左右。\n\n"
        f"论文标题: {paper.title}\n"
        f"作者: {', '.join(author_names)}\n"
        f"摘要: {abstract}\n"
        f"类别: {', '.join(paper.categories)}\n\n"
        "我关注以下研究主题：\n\n"
        "重点关注领域（优先级1）：\n"
        f"{chr(10).join([f'- {topic}' for topic in PRIORITY_TOPICS])}\n\n"
        "了解领域（优先级2）：\n"
        f"{chr(10).join([f'- {topic}' for topic in SECONDARY_TOPICS])}\n"
    )
    return [
        {"role": "system", "content": "你是一位专业的学术论文分类专家。请严格遵守返回 schema。"},
        {"role": "user", "content": prompt},
    ]


def _build_classification_fallback_prompt(paper, abstract):
    author_names = [author.name for author in paper.authors]
    return f"""
        论文标题: {paper.title}
        作者: {', '.join(author_names)}
        摘要: {abstract}
        类别: {', '.join(paper.categories)}

        我关注以下研究主题：

        重点关注领域（优先级1）：
        {chr(10).join([f"- {topic}" for topic in PRIORITY_TOPICS])}

        了解领域（优先级2）：
        {chr(10).join([f"- {topic}" for topic in SECONDARY_TOPICS])}

        请判断这篇论文是否与上述主题相关，并指定优先级。

        请只回答以下格式之一：
        优先级1 - 简述原因（不超过20字）
        优先级2 - 简述原因（不超过20字）
        不相关

        格式示例：
        优先级1 - 研究了Navier-Stokes方程的存在性
        优先级2 - 涉及椭圆方程的正则性理论
        不相关
        """


def _parse_legacy_classification_result(result: str):
    text = (result or "").strip()
    if text.startswith("优先级1"):
        return 1, text.replace("优先级1", "").strip(" -") or "相关"
    if text.startswith("优先级2"):
        return 2, text.replace("优先级2", "").strip(" -") or "相关"
    return 0, "不符合主题要求"


def check_topic_relevance(paper):
    arxiv_id = paper.get_short_id()

    cached = get_cached_classification(arxiv_id)
    if cached is not None:
        priority, reason = cached
        logger.info("[缓存命中] 分类结果: %s -> 优先级%s", paper.title, priority)
        return priority, reason

    try:
        abstract = paper.summary if hasattr(paper, "summary") else "无摘要"

        logger.info("正在检查主题相关性: %s", paper.title)
        try:
            structured, _ = ai_client.structured_chat_completion_with_usage(
                messages=_build_classification_messages(paper, abstract),
                response_model=StructuredTopicClassification,
            )
            priority = structured.priority
            reason = structured.reason
            logger.info("主题相关性检查结果(结构化): priority=%s, reason=%s", priority, reason)
        except Exception as structured_error:
            logger.warning("结构化分类失败，将回退到普通文本模式: %s", str(structured_error))
            result = ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "你是一位专业的学术论文分类专家。请严格按照要求的格式回答。"},
                    {"role": "user", "content": _build_classification_fallback_prompt(paper, abstract)},
                ]
            )
            priority, reason = _parse_legacy_classification_result(result)
            logger.info("主题相关性检查结果(回退): priority=%s, reason=%s", priority, reason)

        if priority == 1:
            logger.info("论文符合重点关注主题: %s - %s", paper.title, reason)
        elif priority == 2:
            logger.info("论文符合了解主题: %s - %s", paper.title, reason)
        else:
            logger.info("论文不符合主题要求，跳过: %s", paper.title)
            reason = reason or "不符合主题要求"

        cache_classification(arxiv_id, priority, reason)
        return priority, reason
    except Exception as e:
        logger.error("检查主题相关性失败 %s: %s", paper.title, str(e))
        return 2, f"检查出错，默认处理: {str(e)}"


def analyze_paper(pdf_path, paper, max_pages=10, use_cache=True, thinking_mode=False):
    arxiv_id = paper.get_short_id()

    request_state = ai_client.get_analysis_request_config(thinking_mode=thinking_mode)
    cache_key = build_analysis_cache_key(arxiv_id, request_state)
    effective_model = request_state.get("effective_model")

    if use_cache:
        cached = get_cached_analysis(cache_key)
        if cached is not None:
            logger.info("[缓存命中] 分析结果: %s", paper.title)
            return _prepare_cached_analysis(request_state, cached)

    try:
        pdf_content = extract_pdf_text(pdf_path, max_pages=max_pages)
        structured_messages = _build_structured_analysis_messages(pdf_content, paper=paper)
        effective_thinking = request_state.get("thinking_applied")
        mode_str = " (深度思考模式)" if effective_thinking else ""
        logger.info("正在分析论文%s: %s", mode_str, paper.title)

        try:
            structured_result, usage, response_state = ai_client.structured_chat_completion_with_usage(
                messages=structured_messages,
                response_model=StructuredPaperAnalysis,
                thinking_mode=thinking_mode,
                return_response_state=True,
            )
            normalized = render_structured_analysis_markdown(structured_result)
            analysis_meta = _finalize_analysis_meta(
                response_state,
                structured_validated=True,
                structured_fallback=False,
            )
        except Exception as structured_error:
            logger.warning("结构化分析失败，将回退到普通文本模式: %s", str(structured_error))
            fallback_messages = _build_fallback_analysis_messages(pdf_content, paper=paper)
            analysis, usage, response_state = ai_client.chat_completion_with_usage(
                messages=fallback_messages,
                thinking_mode=thinking_mode,
                return_response_state=True,
            )
            normalized = normalize_analysis_markdown(analysis, extract_analysis_title(analysis, paper.title))
            analysis_meta = _finalize_analysis_meta(
                {**response_state, "structured_output_mode": "prompt_fallback"},
                structured_validated=False,
                structured_fallback=True,
                structured_error=str(structured_error),
            )

        logger.info("论文分析完成: %s", paper.title)
        logger.info(
            "分析请求配置: provider=%s, model=%s, thinking=%s, fallback=%s, reasoning=%s, structured=%s",
            analysis_meta.get("provider"),
            analysis_meta.get("effective_model"),
            analysis_meta.get("thinking_applied"),
            analysis_meta.get("fallback_used"),
            analysis_meta.get("reasoning_content_present"),
            analysis_meta.get("structured_output_validated"),
        )
        if usage:
            logger.info(
                "Token用量: 输入=%s, 输出=%s, 总计=%s",
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
            )

        if use_cache:
            final_cache_key = build_analysis_cache_key(arxiv_id, analysis_meta)
            cache_analysis(final_cache_key, normalized, analysis_meta)
        return normalized, usage, analysis_meta
    except Exception as e:
        logger.error("分析论文失败 %s (%s): %s", paper.title, effective_model, str(e))
        return f"**论文分析出错**: {str(e)}", {}, {}


def analyze_pdf_only(pdf_path, max_pages=10, title: str = None, use_cache=True, thinking_mode=False):
    from pathlib import Path

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error("PDF 文件不存在: %s", pdf_path)
        return f"**错误**: PDF 文件不存在: {pdf_path}", {}, {}

    request_state = ai_client.get_analysis_request_config(thinking_mode=thinking_mode)
    cache_key = build_analysis_cache_key(pdf_path.stem, request_state)
    effective_model = request_state.get("effective_model")

    if use_cache:
        cached = get_cached_analysis(cache_key)
        if cached is not None:
            logger.info("[缓存命中] 分析结果: %s", pdf_path.name)
            return _prepare_cached_analysis(request_state, cached)

    try:
        pdf_content = extract_pdf_text(str(pdf_path), max_pages=max_pages)

        if not title:
            title = pdf_path.stem.replace("_", " ").replace("-", " ")

        structured_messages = _build_structured_analysis_messages(pdf_content, title=title)
        effective_thinking = request_state.get("thinking_applied")
        mode_str = " (深度思考模式)" if effective_thinking else ""
        logger.info("正在分析 PDF%s: %s", mode_str, pdf_path.name)

        try:
            structured_result, usage, response_state = ai_client.structured_chat_completion_with_usage(
                messages=structured_messages,
                response_model=StructuredPaperAnalysis,
                thinking_mode=thinking_mode,
                return_response_state=True,
            )
            normalized = render_structured_analysis_markdown(structured_result)
            analysis_meta = _finalize_analysis_meta(
                response_state,
                structured_validated=True,
                structured_fallback=False,
            )
        except Exception as structured_error:
            logger.warning("结构化 PDF 分析失败，将回退到普通文本模式: %s", str(structured_error))
            fallback_messages = _build_fallback_analysis_messages(pdf_content, title=title)
            analysis, usage, response_state = ai_client.chat_completion_with_usage(
                messages=fallback_messages,
                thinking_mode=thinking_mode,
                return_response_state=True,
            )
            normalized = normalize_analysis_markdown(analysis, extract_analysis_title(analysis, title))
            analysis_meta = _finalize_analysis_meta(
                {**response_state, "structured_output_mode": "prompt_fallback"},
                structured_validated=False,
                structured_fallback=True,
                structured_error=str(structured_error),
            )

        logger.info("PDF 分析完成: %s", pdf_path.name)
        logger.info(
            "分析请求配置: provider=%s, model=%s, thinking=%s, fallback=%s, reasoning=%s, structured=%s",
            analysis_meta.get("provider"),
            analysis_meta.get("effective_model"),
            analysis_meta.get("thinking_applied"),
            analysis_meta.get("fallback_used"),
            analysis_meta.get("reasoning_content_present"),
            analysis_meta.get("structured_output_validated"),
        )
        if usage:
            logger.info(
                "Token用量: 输入=%s, 输出=%s, 总计=%s",
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
            )

        if use_cache:
            final_cache_key = build_analysis_cache_key(pdf_path.stem, analysis_meta)
            cache_analysis(final_cache_key, normalized, analysis_meta)
        return normalized, usage, analysis_meta
    except Exception as e:
        logger.error("分析 PDF 失败 %s (%s): %s", pdf_path, effective_model, str(e))
        return f"**PDF 分析出错**: {str(e)}", {}, {}

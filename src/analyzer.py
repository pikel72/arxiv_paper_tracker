# analyzer.py - 分析论文模块

import logging
import re

try:
    import fitz
except Exception:
    fitz = None

import pdfplumber
try:
    import tiktoken
except Exception:
    tiktoken = None

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cache import (
    build_analysis_cache_key,
    cache_analysis,
    cache_classification,
    get_cached_analysis,
    get_cached_classification,
)
from config import (
    ANALYSIS_CLEANUP_THINKING_MODE,
    PRIORITY_TOPICS,
    SECONDARY_TOPICS,
    ai_client,
    analysis_cleanup_client,
    get_analysis_cleanup_request_config,
)

logger = logging.getLogger(__name__)

ANALYSIS_SCHEMA_VERSION = "paper_analysis_v2_cleanup"
CLEANUP_MAX_ATTEMPTS = 2

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

    chinese_title: str = Field(description="论文标题的学术化中文翻译, 只输出标题文本, 不要解释性副标题. ")
    research_background: str = Field(
        description="面向偏微分方程与分析理论读者, 说明研究对象、方程或模型、关键未知量、问题设定、已有理论背景以及本文试图推进的空白. "
    )
    main_results: str = Field(
        description="按照“在什么假设下证明了什么结论”来概述主要结果, 尽量保留函数空间、参数范围、定理编号、误差阶、增长率、尺度关系与代表性公式. "
    )
    methods_and_tools: str = Field(
        description="说明证明中的核心障碍、作者的真正创新点、关键估计、关键引理或分析框架, 不要泛泛罗列方法名. "
    )
    comparison_with_previous_work: str = Field(
        description="比较本文与既有 PDE/分析理论文献的推进、假设差异、时间尺度、适用范围、代价与局限, 优先点名文中明确提到的前人工作. "
    )

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

    priority: int = Field(description="分类优先级, 只能是 0、1、2. 0 表示不相关, 1 表示优先级1, 2 表示优先级2. ")
    reason: str = Field(
        description="分类原因. priority 为 1 或 2 时应尽量点出具体方程、估计、函数空间、理论主题或技术关键词, 不要泛泛写成“与分析相关”. "
    )

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


ANALYSIS_CONTENT_REQUIREMENTS = """
内容要求：
1. 输出面向真正阅读论文的研究者, 而不是宣传式摘要. 内容要真实可靠, 并且尽量具体详细. 你应当假设读者具有偏微分方程与分析理论的基本素养, 但不假设他们了解这篇论文相关的领域和背景. 
2. `research_background` 需要交代研究对象、所处方程/模型/问题设定、问题为什么重要, 以及本文试图补哪块空白. 应使用行间公式明确地列出研究对象和方程, 不要只写“研究了Navier-Stokes方程”或“研究了椭圆方程的正则性”. 约 2000 字左右.
3. `main_results` 需要优先写作者真正证明了什么. 应完整列出主要定理的结论, 包括关键假设、尺度关系、误差阶、增长率或代表性公式等技术细节.
4. `methods_and_tools` 需要说明主要技术障碍是什么, 作者的真正创新点是什么, 证明框架如何推进; 避免泛泛写成“使用能量估计、紧性方法”等空话, 除非文中确实只有这些信息. 应该具体写出作者使用了哪些关键技术、核心工具或分析框架, 以及它们在证明中的作用. 约 2000 字左右. 如果有多个重要技术点, 分段说明.
5. `comparison_with_previous_work` 需要尽量探讨本文与已有工作的差别: 推进了什么、放宽了什么假设、把时间尺度/适用范围推进到哪里、代价是什么. 尽可能详细, 把读者当做具有相关背景, 但不熟悉该领域该问题的研究者. 如果有多个维度层面可以比较, 分段说明. 约 2000 字左右.
6. 如果 PDF 摘录中无法支持某个判断, 请明确说明“从提供内容中无法确认”或“作者未显式展开比较”, 不要编造. 
7. 所有字段都必须使用中文, 除人名或特定术语外尽量避免使用英文.
8. 公式格式：行内公式用 $...$, 行间公式用 $$...$$, 不要使用 \\[...\\]. 
9. 应当多使用公式, 尽可能准确地表达数学内容; 避免过度使用文字描述, 以免引入不必要的歧义.
10. 如果作者区分“严格证明的结论”和“启发式解释/物理图像/未来方向”, 请在表述上区分清楚, 不要混为一谈. 
""".strip()

ANALYSIS_FALLBACK_REQUIREMENTS = """
内容要求：
1. 回答对象始终是偏微分方程与分析理论方向的研究者, 而不是泛科学读者或宣传稿读者.
2. 研究对象和背景：说明研究对象、方程/模型设定、关键未知量、问题背景、本文试图解决的核心空白；尽量写出具体方程或核心表达式, 不要停留在方向标签.
3. 主要定理或主要结果：尽量写出作者真正证明的核心结论、关键假设、函数空间、尺度关系、误差阶、增长率或代表性公式；不要把 theorem、estimate、instability、scattering 等强结论弱化成“讨论了”.
4. 研究方法、关键技术和核心工具：解释主要技术障碍、关键创新和证明框架；如果文中出现新的泛函、单调量、能量方法、bootstrap、紧性、Carleman 估计、Strichartz 估计、频率分解等工具, 尽量具体点明它们起什么作用.
5. 与之前工作的比较：比较本文相对前人工作的推进、适用范围、时间尺度、附加假设与局限；如果文中没有足够信息, 请明确说明.
6. 尽量多用数学上可核对的表述与公式, 减少空泛修辞；不能确认的内容要明确说无法确认.
""".strip()

CLASSIFICATION_CONTENT_REQUIREMENTS = """
分类要求：
1. 请以偏微分方程与分析理论研究者的眼光判断相关性, 不要按学科大类或应用场景机械归类.
2. 优先关注论文是否真正涉及存在唯一性、正则性、爆破、散射、衰减、稳定性、渐近行为、先验估计、函数空间理论、调和分析工具、边界层、无粘极限、色散估计等理论问题.
3. 如果论文主要是数值模拟、算法实现、工程建模、机器学习应用或实验现象描述, 而缺少明确的 PDE/分析理论推进, 应降低优先级或判为不相关.
4. `reason` 应尽量点出具体对象或技术关键词, 如“Navier-Stokes 正则性”“Strichartz 估计与散射”“椭圆边界正则性”“无粘极限”, 避免泛泛写成“与分析有关”.
5. 分类要克制；如果只是在背景中提到某个方程, 但正文不是理论分析, 应谨慎处理.
""".strip()

ANALYSIS_CLEANUP_REQUIREMENTS = """
清洗要求：
1. 你是学术文本清洗助手, 不是重新分析论文的助手. 你只能整理现有内容, 不能新增事实判断、不能补充原文未提供的数学结论.
2. 输入会分成两部分：论文元数据与分析 blocks. 你必须 block in, block out 地返回同样的五个字段, 不得遗漏.
3. 不要改变结论强度、定理适用条件、函数空间、参数范围、误差阶、增长率、时间尺度、参考文献编号、变量名与公式含义.
4. 允许做的事情仅包括：修复乱码、修复错误转义、修复 Markdown 友好性、重新分段、在 block 内保留或整理分点、去掉重复表述、让论述更清楚.
5. 像 \\boldsymbol, \\nabla, \\theta, \\lesssim, \\infty, \\partial_t, \\mathrm, \\mathbb 等 LaTeX 命令必须保留并修复, 不能被破坏.
6. 如果 block 中混入了字面量 \\n、\\t、\\r、控制字符或错误的反斜杠转义, 请你自行改正, 不要把这些坏格式原样保留下来.
7. 如果使用行间公式, 必须输出为真正的 Markdown 块公式格式, 即 $$ 独占一行、公式内容单独成行、结尾 $$ 独占一行; 不要输出 $$\\nE(w) 这类字面量转义.
8. 不要把“### 1.”这类主章节标题写回字段内容; 字段中只放该 section 的正文. 允许保留块内的小标题、编号分点和多个自然段.
9. 输出应继续面向偏微分方程与分析理论研究者, 语言保持学术、克制、可核对, 不要改成科普或宣传口吻.
""".strip()


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
        content = normalize_analysis_block_text(sections.get(key) or "")
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


def normalize_analysis_block_text(text: str):
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def validate_analysis_markdown(markdown_text: str):
    text = markdown_text or ""
    issues = []

    if not text.startswith("# "):
        issues.append("缺少一级标题")
    if "## 详细分析" not in text:
        issues.append("缺少“## 详细分析”标题")

    expected_sections = [
        "### 1. 研究对象和背景",
        "### 2. 主要定理或主要结果",
        "### 3. 研究方法、关键技术和核心工具",
        "### 4. 与之前工作的比较",
    ]
    for section_title in expected_sections:
        count = text.count(section_title)
        if count != 1:
            issues.append(f"章节标题异常: {section_title} (出现 {count} 次)")

    for bad_literal in ("$$\\n", "$$\\t", "$$\\r"):
        if bad_literal in text:
            issues.append(f"存在非法块公式转义: {bad_literal}")

    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
        issues.append("存在未清理的控制字符")

    return issues


def render_structured_analysis_markdown(analysis: StructuredPaperAnalysis):
    return (
        f"# {analysis.chinese_title}\n\n"
        "## 详细分析\n\n"
        "### 1. 研究对象和背景\n"
        f"{normalize_analysis_block_text(analysis.research_background)}\n\n"
        "### 2. 主要定理或主要结果\n"
        f"{normalize_analysis_block_text(analysis.main_results)}\n\n"
        "### 3. 研究方法、关键技术和核心工具\n"
        f"{normalize_analysis_block_text(analysis.methods_and_tools)}\n\n"
        "### 4. 与之前工作的比较\n"
        f"{normalize_analysis_block_text(analysis.comparison_with_previous_work)}\n"
    )


def _merge_usage(primary_usage, secondary_usage):
    merged = {}
    for usage in (primary_usage or {}, secondary_usage or {}):
        for key, value in usage.items():
            if isinstance(value, int):
                merged[key] = merged.get(key, 0) + value
            elif key not in merged:
                merged[key] = value
    return merged


def _structured_analysis_from_markdown(raw_text: str, fallback_title: str):
    sections = extract_analysis_sections(raw_text)
    return StructuredPaperAnalysis(
        chinese_title=extract_analysis_title(raw_text, fallback_title),
        research_background=normalize_analysis_block_text(sections.get("研究对象和背景") or "（模型未给出相关内容）"),
        main_results=normalize_analysis_block_text(sections.get("主要定理或主要结果") or "（模型未给出相关内容）"),
        methods_and_tools=normalize_analysis_block_text(sections.get("研究方法、关键技术和核心工具") or "（模型未给出相关内容）"),
        comparison_with_previous_work=normalize_analysis_block_text(sections.get("与之前工作的比较") or "（模型未给出相关内容）"),
    )


def _build_analysis_cleanup_metadata(paper=None, title=None, source_name="analysis"):
    metadata = [f"来源: {source_name}"]
    if paper is not None:
        author_names = [author.name for author in paper.authors]
        metadata.extend(
            [
                f"英文标题: {paper.title}",
                f"作者: {', '.join(author_names)}",
                f"类别: {', '.join(paper.categories)}",
                f"发布时间: {paper.published}",
                f"摘要: {paper.summary}",
            ]
        )
    elif title:
        metadata.append(f"标题提示: {title}")
    return "\n".join(metadata)


def _build_analysis_cleanup_messages(
    analysis_blocks: StructuredPaperAnalysis,
    paper=None,
    title=None,
    source_name="analysis",
    validation_feedback="",
):
    feedback_block = ""
    if validation_feedback:
        feedback_block = f"上一次输出未通过格式校验, 请重点修复以下问题并重新给出完整 blocks:\n{validation_feedback}\n\n"

    prompt = (
        "请严格按照给定的结构化 schema 返回清洗后的分析 blocks. \n\n"
        f"{ANALYSIS_CLEANUP_REQUIREMENTS}\n\n"
        f"{feedback_block}"
        "论文元数据:\n"
        f"{_build_analysis_cleanup_metadata(paper=paper, title=title, source_name=source_name)}\n\n"
        "当前 block 输入:\n"
        f"[chinese_title]\n{analysis_blocks.chinese_title}\n\n"
        f"[research_background]\n{normalize_analysis_block_text(analysis_blocks.research_background)}\n\n"
        f"[main_results]\n{normalize_analysis_block_text(analysis_blocks.main_results)}\n\n"
        f"[methods_and_tools]\n{normalize_analysis_block_text(analysis_blocks.methods_and_tools)}\n\n"
        f"[comparison_with_previous_work]\n{normalize_analysis_block_text(analysis_blocks.comparison_with_previous_work)}\n"
    )
    return [
        {"role": "system", "content": "你是一位偏微分方程与分析理论方向的学术文本清洗助手. 请严格遵守返回 schema, 只做清洗和整理, 不重新分析论文. "},
        {"role": "user", "content": prompt},
    ]


def _apply_analysis_cleanup(analysis_blocks: StructuredPaperAnalysis, paper=None, title=None, source_name="analysis"):
    cleanup_request = get_analysis_cleanup_request_config()
    cleanup_meta = dict(cleanup_request)
    cleanup_meta["cleanup_attempted"] = False
    cleanup_meta["cleanup_applied"] = False
    cleanup_meta["cleanup_structured_validated"] = False
    cleanup_meta["cleanup_validation_error"] = ""
    if not cleanup_request.get("cleanup_requested") or analysis_cleanup_client is None:
        return analysis_blocks, {}, cleanup_meta

    cleanup_meta["cleanup_attempted"] = True
    total_cleanup_usage = {}
    current_blocks = analysis_blocks
    validation_feedback = ""

    for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
        try:
            cleaned_blocks, cleanup_usage, cleanup_state = analysis_cleanup_client.structured_chat_completion_with_usage(
                messages=_build_analysis_cleanup_messages(
                    current_blocks,
                    paper=paper,
                    title=title,
                    source_name=source_name,
                    validation_feedback=validation_feedback,
                ),
                response_model=StructuredPaperAnalysis,
                thinking_mode=ANALYSIS_CLEANUP_THINKING_MODE,
                return_response_state=True,
            )
            total_cleanup_usage = _merge_usage(total_cleanup_usage, cleanup_usage)
            cleanup_meta.update(
                {
                    "cleanup_provider": cleanup_state.get("provider") or cleanup_meta.get("cleanup_provider"),
                    "cleanup_effective_model": cleanup_state.get("effective_model") or cleanup_meta.get("cleanup_effective_model"),
                    "cleanup_thinking_requested": cleanup_state.get("thinking_requested", cleanup_meta.get("cleanup_thinking_requested")),
                    "cleanup_thinking_applied": cleanup_state.get("thinking_applied", cleanup_meta.get("cleanup_thinking_applied")),
                    "cleanup_budget": cleanup_state.get("thinking_budget", cleanup_meta.get("cleanup_budget")),
                    "cleanup_effort": cleanup_state.get("thinking_effort", cleanup_meta.get("cleanup_effort")),
                    "cleanup_fallback_used": bool(cleanup_state.get("fallback_used")),
                    "cleanup_reasoning_content_present": bool(cleanup_state.get("reasoning_content_present")),
                }
            )

            rendered = render_structured_analysis_markdown(cleaned_blocks)
            validation_issues = validate_analysis_markdown(rendered)
            if not validation_issues:
                cleanup_meta.update(
                    {
                        "cleanup_applied": True,
                        "cleanup_structured_validated": True,
                        "cleanup_error": "",
                        "cleanup_validation_error": "",
                    }
                )
                return cleaned_blocks, total_cleanup_usage, cleanup_meta

            cleanup_meta["cleanup_validation_error"] = "; ".join(validation_issues)
            validation_feedback = "\n".join([f"- {issue}" for issue in validation_issues])
            logger.warning(
                "分析 cleanup 输出未通过校验，将请求模型重试: attempt=%s/%s, provider=%s, model=%s, issues=%s",
                attempt,
                CLEANUP_MAX_ATTEMPTS,
                cleanup_meta.get("cleanup_provider"),
                cleanup_meta.get("cleanup_effective_model"),
                cleanup_meta["cleanup_validation_error"],
            )
            current_blocks = cleaned_blocks
        except Exception as e:
            cleanup_meta["cleanup_error"] = str(e)
            logger.warning(
                "分析 cleanup 失败，将保留原分析结果: provider=%s, model=%s, error=%s",
                cleanup_meta.get("cleanup_provider"),
                cleanup_meta.get("cleanup_effective_model"),
                str(e),
            )
            return analysis_blocks, total_cleanup_usage, cleanup_meta

    cleanup_meta["cleanup_error"] = cleanup_meta["cleanup_validation_error"] or "cleanup 输出未通过校验"
    return analysis_blocks, total_cleanup_usage, cleanup_meta


def extract_pdf_text(pdf_path, max_pages=10):
    pymupdf_error = None

    if fitz is not None:
        try:
            text_parts = []
            with fitz.open(pdf_path) as pdf:
                if max_pages is None:
                    pages_to_read = len(pdf)
                else:
                    pages_to_read = min(len(pdf), max_pages)

                for i in range(pages_to_read):
                    page_text = (pdf[i].get_text("text") or "").strip()
                    if page_text:
                        text_parts.append(f"\n=== 第{i + 1}页 ===\n{page_text}\n")

            text_content = "".join(text_parts)
            if text_content.strip():
                logger.info("成功从PDF提取文本, 共%s页, backend=PyMuPDF", pages_to_read)
                return text_content

            logger.warning("PyMuPDF 未提取到可用文本，将回退到 pdfplumber: %s", pdf_path)
        except Exception as e:
            pymupdf_error = str(e)
            logger.warning("PyMuPDF 文本提取失败，将回退到 pdfplumber: %s", pymupdf_error)

    try:
        text_parts = []
        with pdfplumber.open(pdf_path) as pdf:
            if max_pages is None:
                pages_to_read = len(pdf.pages)
            else:
                pages_to_read = min(len(pdf.pages), max_pages)

            for i in range(pages_to_read):
                page = pdf.pages[i]
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    text_parts.append(f"\n=== 第{i + 1}页 ===\n{page_text}\n")

        text_content = "".join(text_parts)
        logger.info("成功从PDF提取文本, 共%s页, backend=pdfplumber", pages_to_read)
        return text_content
    except Exception as e:
        error_message = str(e)
        if pymupdf_error:
            error_message = f"PyMuPDF: {pymupdf_error}; pdfplumber: {error_message}"
        logger.error("PDF文本提取失败 %s: %s", pdf_path, error_message)
        return f"PDF文本提取失败: {error_message}"


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
        "请严格按照给定的结构化 schema 返回论文分析. \n\n"
        "`chinese_title` 只放中文标题, 不要附加前缀、解释或换行. \n\n"
        f"{ANALYSIS_CONTENT_REQUIREMENTS}\n\n"
        "请基于以下论文信息与 PDF 文本完成结构化分析：\n\n"
        f"{paper_context}\n"
        "论文PDF内容:\n"
        f"{pdf_content}\n"
    )
    return [
        {"role": "system", "content": "你是一位偏微分方程与分析理论方向的研究助手. 请使用中文回复, 并严格遵守返回 schema. "},
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
        "请使用中文回答, 并以 Markdown 格式输出. \n\n"
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
        "格式要求：\n"
        "1. 标题必须按以上层级输出. \n"
        "2. 不要把章节标题加粗. \n"
        "3. 章节内容使用自然段, 不要列表. \n"
        "4. 行内公式使用 $...$, 行间公式使用 $$...$$, 不要使用 \\[...\\]. \n\n"
        f"{ANALYSIS_FALLBACK_REQUIREMENTS}\n\n"
        "请分析以下论文：\n\n"
        f"{context}\n"
        "论文PDF内容:\n"
        f"{pdf_content}\n"
    )
    return [
        {"role": "system", "content": "你是一位偏微分方程与分析理论方向的研究助手. 请使用中文回复. "},
        {"role": "user", "content": prompt},
    ]


def _get_token_encoder(model_name=None):
    if tiktoken is None:
        return None

    candidates = []
    normalized_model = str(model_name or "").strip()
    if normalized_model:
        candidates.append(normalized_model)
        if "/" in normalized_model:
            candidates.append(normalized_model.rsplit("/", 1)[-1])

    for candidate in candidates:
        try:
            return tiktoken.encoding_for_model(candidate)
        except Exception:
            continue

    for encoding_name in ("o200k_base", "cl100k_base"):
        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception:
            continue
    return None


def _estimate_text_tokens(text, model_name=None):
    content = str(text or "")
    if not content:
        return 0

    encoder = _get_token_encoder(model_name=model_name)
    if encoder is not None:
        try:
            return len(encoder.encode(content))
        except Exception:
            pass

    return max(1, len(content) // 4)


def _estimate_message_tokens(messages, model_name=None):
    total = 0
    for message in messages or []:
        role = ""
        content = ""
        if isinstance(message, dict):
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
        else:
            role = str(getattr(message, "role", "") or "")
            content = str(getattr(message, "content", "") or "")
        total += _estimate_text_tokens(role, model_name=model_name)
        total += _estimate_text_tokens(content, model_name=model_name)
        total += 4
    return total


def _count_extracted_pdf_pages(text):
    if not text:
        return 0
    return len(re.findall(r"^=== 第\d+页 ===$", str(text), flags=re.MULTILINE))


def _finalize_analysis_meta(response_state, structured_validated, structured_fallback, from_cache=False, structured_error=""):
    meta = dict(response_state or {})
    meta["analysis_schema_version"] = ANALYSIS_SCHEMA_VERSION
    meta["structured_output_validated"] = bool(structured_validated)
    meta["structured_output_fallback"] = bool(structured_fallback)
    meta["from_cache"] = bool(from_cache)
    meta.setdefault("estimated_prompt_tokens", None)
    meta.setdefault("pdf_text_length", None)
    meta.setdefault("pdf_text_pages", None)
    meta.setdefault("cleanup_requested", False)
    meta.setdefault("cleanup_attempted", False)
    meta.setdefault("cleanup_applied", False)
    meta.setdefault("cleanup_provider", "")
    meta.setdefault("cleanup_effective_model", "")
    meta.setdefault("cleanup_thinking_requested", False)
    meta.setdefault("cleanup_thinking_applied", False)
    meta.setdefault("cleanup_budget", None)
    meta.setdefault("cleanup_effort", None)
    meta.setdefault("cleanup_fallback_used", False)
    meta.setdefault("cleanup_reasoning_content_present", False)
    meta.setdefault("cleanup_structured_validated", False)
    meta.setdefault("cleanup_validation_error", "")
    if structured_error:
        meta["structured_error"] = structured_error
    return meta


def _prepare_cached_analysis(request_state, cached_payload):
    analysis_text, cached_meta = cached_payload
    if cached_meta:
        meta = dict(cached_meta)
        meta.setdefault("estimated_prompt_tokens", None)
        meta.setdefault("pdf_text_length", None)
        meta.setdefault("pdf_text_pages", None)
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
        "请严格按照给定的结构化 schema 返回分类结果. \n\n"
        f"{CLASSIFICATION_CONTENT_REQUIREMENTS}\n\n"
        "你需要判断论文与我关注主题的相关性, 并返回：\n"
        "1. `priority`: 只能是 0、1、2. 0 表示不相关, 1 表示重点关注, 2 表示了解领域. \n"
        "2. `reason`: 给出简短原因. priority 为 1 或 2 时尽量控制在 20 字左右. \n\n"
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
        {"role": "system", "content": "你是一位偏微分方程与分析理论方向的学术论文分类专家. 请严格遵守返回 schema. "},
        {"role": "user", "content": prompt},
    ]


def _build_classification_fallback_prompt(paper, abstract):
    author_names = [author.name for author in paper.authors]
    return f"""
        {CLASSIFICATION_CONTENT_REQUIREMENTS}

        论文标题: {paper.title}
        作者: {', '.join(author_names)}
        摘要: {abstract}
        类别: {', '.join(paper.categories)}

        我关注以下研究主题：

        重点关注领域（优先级1）：
        {chr(10).join([f"- {topic}" for topic in PRIORITY_TOPICS])}

        了解领域（优先级2）：
        {chr(10).join([f"- {topic}" for topic in SECONDARY_TOPICS])}

        请判断这篇论文是否与上述主题相关, 并指定优先级. 

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
            logger.warning("结构化分类失败, 将回退到普通文本模式: %s", str(structured_error))
            result = ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "你是一位偏微分方程与分析理论方向的学术论文分类专家. 请严格按照要求的格式回答. "},
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
            logger.info("论文不符合主题要求, 跳过: %s", paper.title)
            reason = reason or "不符合主题要求"

        cache_classification(arxiv_id, priority, reason)
        return priority, reason
    except Exception as e:
        logger.error("检查主题相关性失败 %s: %s", paper.title, str(e))
        return 2, f"检查出错, 默认处理: {str(e)}"


def analyze_paper(pdf_path, paper, max_pages=10, use_cache=True, thinking_mode=None, include_prompt_estimate=False):
    arxiv_id = paper.get_short_id()

    request_state = {
        **ai_client.get_analysis_request_config(thinking_mode=thinking_mode),
        **get_analysis_cleanup_request_config(),
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
    }
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
        estimated_prompt_tokens = None
        if include_prompt_estimate:
            estimated_prompt_tokens = _estimate_message_tokens(structured_messages, model_name=effective_model)
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
            analysis_meta = _finalize_analysis_meta(
                {**response_state, **request_state},
                structured_validated=True,
                structured_fallback=False,
            )
            analysis_blocks = structured_result
            normalized = render_structured_analysis_markdown(analysis_blocks)
        except Exception as structured_error:
            logger.warning("结构化分析失败, 将回退到普通文本模式: %s", str(structured_error))
            fallback_messages = _build_fallback_analysis_messages(pdf_content, paper=paper)
            analysis, usage, response_state = ai_client.chat_completion_with_usage(
                messages=fallback_messages,
                thinking_mode=False,
                return_response_state=True,
            )
            normalized = normalize_analysis_markdown(analysis, extract_analysis_title(analysis, paper.title))
            analysis_meta = _finalize_analysis_meta(
                {
                    **response_state,
                    **request_state,
                    "thinking_requested": False,
                    "thinking_applied": False,
                    "thinking_budget": None,
                    "thinking_effort": None,
                    "structured_output_mode": "prompt_fallback",
                },
                structured_validated=False,
                structured_fallback=True,
                structured_error=str(structured_error),
            )
            analysis_blocks = _structured_analysis_from_markdown(normalized, paper.title)

        cleaned_blocks, cleanup_usage, cleanup_meta = _apply_analysis_cleanup(
            analysis_blocks,
            paper=paper,
            source_name="arxiv_paper",
        )
        if cleanup_meta.get("cleanup_applied"):
            normalized = render_structured_analysis_markdown(cleaned_blocks)
        usage = _merge_usage(usage, cleanup_usage)
        analysis_meta.update(cleanup_meta)
        if include_prompt_estimate:
            analysis_meta["estimated_prompt_tokens"] = estimated_prompt_tokens
            analysis_meta["pdf_text_length"] = len(pdf_content)
            analysis_meta["pdf_text_pages"] = _count_extracted_pdf_pages(pdf_content)

        logger.info("论文分析完成: %s", paper.title)
        logger.info(
            "分析请求配置: provider=%s, model=%s, thinking=%s, fallback=%s, reasoning=%s, structured=%s, cleanup=%s",
            analysis_meta.get("provider"),
            analysis_meta.get("effective_model"),
            analysis_meta.get("thinking_applied"),
            analysis_meta.get("fallback_used"),
            analysis_meta.get("reasoning_content_present"),
            analysis_meta.get("structured_output_validated"),
            analysis_meta.get("cleanup_applied"),
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


def analyze_pdf_only(pdf_path, max_pages=10, title: str = None, use_cache=True, thinking_mode=None, include_prompt_estimate=False):
    from pathlib import Path

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error("PDF 文件不存在: %s", pdf_path)
        return f"**错误**: PDF 文件不存在: {pdf_path}", {}, {}

    request_state = {
        **ai_client.get_analysis_request_config(thinking_mode=thinking_mode),
        **get_analysis_cleanup_request_config(),
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
    }
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
        estimated_prompt_tokens = None
        if include_prompt_estimate:
            estimated_prompt_tokens = _estimate_message_tokens(structured_messages, model_name=effective_model)
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
            analysis_meta = _finalize_analysis_meta(
                {**response_state, **request_state},
                structured_validated=True,
                structured_fallback=False,
            )
            analysis_blocks = structured_result
            normalized = render_structured_analysis_markdown(analysis_blocks)
        except Exception as structured_error:
            logger.warning("结构化 PDF 分析失败, 将回退到普通文本模式: %s", str(structured_error))
            fallback_messages = _build_fallback_analysis_messages(pdf_content, title=title)
            analysis, usage, response_state = ai_client.chat_completion_with_usage(
                messages=fallback_messages,
                thinking_mode=False,
                return_response_state=True,
            )
            normalized = normalize_analysis_markdown(analysis, extract_analysis_title(analysis, title))
            analysis_meta = _finalize_analysis_meta(
                {
                    **response_state,
                    **request_state,
                    "thinking_requested": False,
                    "thinking_applied": False,
                    "thinking_budget": None,
                    "thinking_effort": None,
                    "structured_output_mode": "prompt_fallback",
                },
                structured_validated=False,
                structured_fallback=True,
                structured_error=str(structured_error),
            )
            analysis_blocks = _structured_analysis_from_markdown(normalized, title)

        cleaned_blocks, cleanup_usage, cleanup_meta = _apply_analysis_cleanup(
            analysis_blocks,
            title=title,
            source_name=f"local_pdf:{pdf_path.name}",
        )
        if cleanup_meta.get("cleanup_applied"):
            normalized = render_structured_analysis_markdown(cleaned_blocks)
        usage = _merge_usage(usage, cleanup_usage)
        analysis_meta.update(cleanup_meta)
        if include_prompt_estimate:
            analysis_meta["estimated_prompt_tokens"] = estimated_prompt_tokens
            analysis_meta["pdf_text_length"] = len(pdf_content)
            analysis_meta["pdf_text_pages"] = _count_extracted_pdf_pages(pdf_content)

        logger.info("PDF 分析完成: %s", pdf_path.name)
        logger.info(
            "分析请求配置: provider=%s, model=%s, thinking=%s, fallback=%s, reasoning=%s, structured=%s, cleanup=%s",
            analysis_meta.get("provider"),
            analysis_meta.get("effective_model"),
            analysis_meta.get("thinking_applied"),
            analysis_meta.get("fallback_used"),
            analysis_meta.get("reasoning_content_present"),
            analysis_meta.get("structured_output_validated"),
            analysis_meta.get("cleanup_applied"),
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

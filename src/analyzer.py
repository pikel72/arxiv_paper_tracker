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
    ANALYSIS_REQUEST_TIMEOUT,
    PRIORITY_TOPICS,
    SECONDARY_TOPICS,
    get_ai_client,
    get_analysis_cleanup_client,
    get_analysis_cleanup_request_config,
)

logger = logging.getLogger(__name__)

# 提示词的篇幅与排版要求变更后隔离旧缓存，避免直接复用此前的简短报告。
ANALYSIS_SCHEMA_VERSION = "paper_analysis_v3_readable_longform"
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
        description="充分展开的 Markdown 背景导读, 用多个自然段依次解释研究对象、方程、符号、问题背景与研究目标, 重要公式单列. 读者有 PDE 基础但不熟悉本文领域, 不要压缩成一段摘要. "
    )
    main_results: str = Field(
        description="充分展开的 Markdown 主要结果, 每个主定理或推论用独立引用块和加粗名称呈现, 分开写假设与结论, 重要公式单列, 块后用自然段解释意义. 保留原文编号及关键条件, 不要把多个定理挤在一段里. "
    )
    methods_and_tools: str = Field(
        description="充分展开的 Markdown 方法导读, 用四级小标题分别介绍核心分析学工具和解决难题的技巧, 每种方法独立分项并解释基本思想、本文用途及与其他步骤的联系. 给读者足够铺垫, 不要只列术语或压缩成一个技术段落. "
    )
    comparison_with_previous_work: str = Field(
        description="充分展开的 Markdown 文献比较, 按比较维度分项, 分别解释前人做到了什么、本文改变了什么以及这一变化的意义和限制, 每项有完整说明, 优先使用论文明确提到的工作. "
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
        description="简短分类原因. priority 为 1 或 2 时尽量控制在 20 字左右. "
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
            self.reason = self.reason[:40].rstrip("，、；;,. ")
        return self


# 两种输出路径共用导读要求，避免结构化字段或普通文本回退把长文再次压成摘要。
ANALYSIS_CONTENT_REQUIREMENTS = r"""
写作目标与优先顺序：
请写一篇篇幅充分、排版清楚、容易跟着读的长篇中文论文导读. 读者有偏微分方程与分析理论基础, 但不熟悉本文的具体领域. 读完应能了解文章研究什么、主要得到什么结果、用了哪些方法, 并决定是否精读原文.
第一优先是充分展开的篇幅, 第二是清晰的排版层次, 接着是研究内容与方法的易懂程度. 全文通常以 6000–8000 个中文汉字为目标, 不计公式源码, 内容丰富时可以更长. 不要把四节各压缩成一个段落, 也不要把长公式或术语数量当作文字解释的替代. 背景铺垫、概念说明、公式后的解释和必要的换一种说法都值得保留. 篇幅用于帮助理解, 不用于编造材料中没有的结论或反复赞扬贡献.

各节如何展开：
1. `research_background`: 约 2000 字左右. 从研究对象和现象讲起, 逐步引入方程、区域、边界条件、未知量与主要参数, 用独立公式展示模型, 紧接着解释符号和含义. 然后交代已有认识、问题的困难和本文目标. 分成多个自然段, 每段围绕一个话题, 可以用四级小标题组织. 不要默认读者已熟悉专门术语, 也不要开头一段就塞进全部背景和贡献.
2. `main_results`: 充分展开各个主要结果, 通常约 1500–2000 字. 先用一段话说明结果的整体图景, 再分别给出主定理、命题或推论. 每个结果必须用独立 Markdown 引用块, 块首加粗名称及原文编号, 假设分条、结论另起段, 重要公式单列. 块后再用自然段解释“这个结果意味着什么”, 说明其中值得注意的条件、尺度或增长率. 不要把多个定理接连写进同一普通段落. 原文没有编号时写“主要结果”, 不要自造编号.
3. `methods_and_tools`: 约 2000 字左右, 给足解释空间. 分为“#### a) 核心分析学工具”和“#### b) 技术性难题的解决技巧”. 先给出整体证明思路, 再把材料中出现的各个重要方法分别展开. 每项用加粗的方法名称或困难名称开头, 接着用完整句子解释基本思想、为何需要它、在本文中承担什么任务; 必要时再给代表性公式. 几种不同工具要分项介绍, 一项较长时继续分段. 可以解释 KAM、不动点、能量法等工具的基本作用, 不要求读者先懂它们; 但要联系本文, 不要只列名字. 方法介绍以理解大致路线为目标, 不必复现全部证明, 也不要把几个关键方法挤在一个长段里.
4. `comparison_with_previous_work`: 约 2000 字左右. 按材料支持的比较维度分项, 如研究对象、几何设定、假设条件、结果范围和方法. 每项先讲前人做到了什么, 再讲本文改变了什么、这一变化为何有意义, 必要时说明限制. 优先使用原文明确提到的作者或工作. 不要只给一串作者姓名或反复说“首次”“突破”. 原文比较有限时, 解释已知差别即可, 不为满足篇幅虚构文献结论.

排版要求：
- 四个正文部分内部都可以使用 Markdown, 不要因为要返回 JSON 字段就省略段落、加粗、小标题、列表或定理引用块. 字段中不重复四个主章节标题, 次级标题使用 ####. 普通文本输出则保留指定的四个 ### 主章节标题.
- 自然段之间留空行. 用 **加粗短语** 突出关键对象、结果和方法, 不要整段加粗. 叙述配合列表, 避免整节只有一个段落或每项只有一句标签.
- 行内公式用 $...$, 美元符号内侧不要留空格; 重要方程、主要结论和较长估计用独立的 $$ 块. $$ 独占一行, 公式单独成行, 公式块前后留空行. 不用 \[...\] 或 LaTeX theorem 环境; 用标准 LaTeX 命令, 公式前后保留文字解释.
- 定理引用块中的每一行都加 >, 包括空行和公式行. 以下仅示范排版, 方括号内容须替换为本文内容, 实际结果与解释应充分展开, 不要照抄占位文字：

> **定理 [原文编号]**
>
> 设 [研究对象与条件]. 假设：
>
> 1. [第一项关键假设].
> 2. [另一项关键假设, 如有].
>
> 则 [主要结论], 并满足：
>
> $$
> [原文的代表性结论公式]
> $$

[引用块之后, 用独立自然段解释结论的意义, 帮助读者理解条件和公式. 下一个结果另起一个引用块.]

内容边界：
基于论文信息和 PDF 摘录介绍内容. 摘录不够支持的具体结论或证明步骤, 简短说明不能确认, 继续充分解释已有内容. 不要编造定理、公式或文献; 区分作者证明的结果与启发式解释. 用中文写作, 人名和必要术语可保留英文, 标点使用半角形式, 数学公式和英文术语周围适当留空格.
提交前检查：四节是否都得到充分展开? 定理是否独立呈现? 方法是否分项解释? 公式是否单列且前后有说明? 如果只写成几段压缩摘要, 请先展开再返回.
""".strip()

ANALYSIS_CLEANUP_REQUIREMENTS = """
清洗要求：
1. 你是学术文本清洗助手, 不是重新分析论文的助手. 你只能整理现有内容, 不能新增事实判断、不能补充原文未提供的数学结论.
2. 输入会分成两部分：论文元数据与分析 blocks. 你必须 block in, block out 地返回同样的五个字段, 不得遗漏.
3. 不要改变结论强度、定理适用条件、函数空间、参数范围、误差阶、增长率、时间尺度、参考文献编号、变量名与公式含义.
4. 允许做的事情仅包括：修复乱码、修复错误转义、修复 Markdown 友好性、重新分段、在 block 内保留或整理分点、删除逐字机械重复、让论述更清楚. 保留原文篇幅、背景铺垫、术语说明和解释性复述, 不要概括、缩写或把多个自然段合并成摘要.
5. 像 \\boldsymbol, \\nabla, \\theta, \\lesssim, \\infty, \\partial_t, \\mathrm, \\mathbb 等 LaTeX 命令必须保留并修复, 不能被破坏.
6. 如果 block 中混入了字面量 \\n、\\t、\\r、控制字符或错误的反斜杠转义, 请你自行改正, 不要把这些坏格式原样保留下来.
7. 如果使用行间公式, 必须输出为真正的 Markdown 块公式格式, 即 $$ 独占一行、公式内容单独成行、结尾 $$ 独占一行; 不要输出 $$\\nE(w) 这类字面量转义. 定理引用块中的公式行和空行仍须保留 > 前缀.
8. 不要把“### 1.”这类主章节标题写回字段内容; 字段中只放该 section 的正文. 允许保留块内的小标题、编号分点和多个自然段.
9. 输出应继续面向偏微分方程与分析理论研究者, 语言保持学术、克制、可核对, 不要改成科普或宣传口吻.
10. 保留独立的定理与推论引用块、加粗名称、四级小标题、列表和公式后的说明. 排版整理应让原有长文更容易阅读, 不要把这些层次压平成连续段落.
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
    if not cleanup_request.get("cleanup_requested") or get_analysis_cleanup_client() is None:
        return analysis_blocks, {}, cleanup_meta

    cleanup_meta["cleanup_attempted"] = True
    total_cleanup_usage = {}
    current_blocks = analysis_blocks
    validation_feedback = ""

    for attempt in range(1, CLEANUP_MAX_ATTEMPTS + 1):
        try:
            cleaned_blocks, cleanup_usage, cleanup_state = get_analysis_cleanup_client().structured_chat_completion_with_usage(
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
        "请严格按照给定的结构化 schema 返回长篇论文导读, 四个正文字符串内使用充分分段的 Markdown. \n\n"
        "`chinese_title` 只放中文标题, 不要附加前缀、解释或换行. \n\n"
        f"{ANALYSIS_CONTENT_REQUIREMENTS}\n\n"
        "请基于以下论文信息与 PDF 文本完成结构化分析：\n\n"
        f"{paper_context}\n"
        "论文PDF内容:\n"
        f"{pdf_content}\n"
    )
    return [
        {"role": "system", "content": "你是一位善于讲解偏微分方程与分析理论论文的研究助手. 请写篇幅充分、排版清晰的中文长篇导读, 帮助不熟悉本文领域的读者理解内容和大致方法. 严格遵守返回 schema, 每个正文字段内保留完整的 Markdown 段落、定理块和小标题. "},
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
        "[用多个自然段展开研究对象、概念、方程和背景]\n\n"
        "### 2. 主要定理或主要结果\n"
        "[各个定理分别使用独立引用块, 假设与结论分开, 块后解释意义]\n\n"
        "### 3. 研究方法、关键技术和核心工具\n"
        "[用四级小标题区分核心工具和难题技巧, 每种方法分项展开解释]\n\n"
        "### 4. 与之前工作的比较\n"
        "[按比较维度分项, 每项充分解释前人工作、本文变化和意义]\n\n"
        "格式要求：\n"
        "1. 标题必须按以上层级输出. \n"
        "2. 不要把章节标题加粗. \n"
        "3. 章节内容应充分展开；可按论证层次使用自然段、小标题或有序分点, 不要把多个技术环节压缩成一个概括性段落. \n"
        "4. 行内公式使用 $...$, 行间公式使用 $$...$$, 不要使用 \\[...\\]. \n\n"
        # 回退只改变输出格式，不降低篇幅、数学细节或前人工作比较等质量要求。
        f"{ANALYSIS_CONTENT_REQUIREMENTS}\n\n"
        "请分析以下论文：\n\n"
        f"{context}\n"
        "论文PDF内容:\n"
        f"{pdf_content}\n"
    )
    return [
        {"role": "system", "content": "你是一位善于讲解偏微分方程与分析理论论文的研究助手. 请写篇幅充分、排版清晰的中文长篇导读, 帮助不熟悉本文领域的读者理解内容和大致方法. 保留独立定理块、分项方法介绍和充分的文字解释. "},
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
        {"role": "system", "content": "你是一位专业的学术论文分类专家. 请严格遵守返回 schema. "},
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
            structured, _ = get_ai_client().structured_chat_completion_with_usage(
                messages=_build_classification_messages(paper, abstract),
                response_model=StructuredTopicClassification,
                json_schema_prompt=True,
            )
            priority = structured.priority
            reason = structured.reason
            logger.info("主题相关性检查结果(结构化): priority=%s, reason=%s", priority, reason)
        except Exception as structured_error:
            logger.warning("结构化分类失败, 将回退到普通文本模式: %s", str(structured_error))
            result = get_ai_client().chat_completion(
                messages=[
                    {"role": "system", "content": "你是一位专业的学术论文分类专家. 请严格按照要求的格式回答. "},
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


def _run_analysis_pipeline(
    pdf_path,
    cache_id,
    display_name,
    paper=None,
    title=None,
    max_pages=10,
    use_cache=True,
    thinking_mode=None,
    include_prompt_estimate=False,
    source_name="analysis",
):
    request_state = {
        **get_ai_client().get_analysis_request_config(thinking_mode=thinking_mode),
        **get_analysis_cleanup_request_config(),
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
    }
    cache_key = build_analysis_cache_key(cache_id, request_state)
    effective_model = request_state.get("effective_model")

    if use_cache:
        cached = get_cached_analysis(cache_key)
        if cached is not None:
            logger.info("[缓存命中] 分析结果: %s", display_name)
            return _prepare_cached_analysis(request_state, cached)

    try:
        pdf_content = extract_pdf_text(str(pdf_path), max_pages=max_pages)

        fallback_title = title
        if paper is not None:
            structured_messages = _build_structured_analysis_messages(pdf_content, paper=paper)
            fallback_title = paper.title
        else:
            if not title:
                title = Path(pdf_path).stem.replace("_", " ").replace("-", " ")
                fallback_title = title
            structured_messages = _build_structured_analysis_messages(pdf_content, title=title)

        estimated_prompt_tokens = None
        if include_prompt_estimate:
            estimated_prompt_tokens = _estimate_message_tokens(structured_messages, model_name=effective_model)
        effective_thinking = request_state.get("thinking_applied")
        mode_str = " (深度思考模式)" if effective_thinking else ""
        logger.info("正在分析%s: %s", mode_str, display_name)

        try:
            structured_result, usage, response_state = get_ai_client().structured_chat_completion_with_usage(
                messages=structured_messages,
                response_model=StructuredPaperAnalysis,
                thinking_mode=thinking_mode,
                return_response_state=True,
                timeout=ANALYSIS_REQUEST_TIMEOUT,
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
            if paper is not None:
                fallback_messages = _build_fallback_analysis_messages(pdf_content, paper=paper)
            else:
                fallback_messages = _build_fallback_analysis_messages(pdf_content, title=title)
            analysis, usage, response_state = get_ai_client().chat_completion_with_usage(
                messages=fallback_messages,
                thinking_mode=False,
                return_response_state=True,
                timeout=ANALYSIS_REQUEST_TIMEOUT,
            )
            normalized = normalize_analysis_markdown(analysis, extract_analysis_title(analysis, fallback_title))
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
            analysis_blocks = _structured_analysis_from_markdown(normalized, fallback_title)

        cleaned_blocks, cleanup_usage, cleanup_meta = _apply_analysis_cleanup(
            analysis_blocks,
            paper=paper,
            title=title,
            source_name=source_name,
        )
        if cleanup_meta.get("cleanup_applied"):
            normalized = render_structured_analysis_markdown(cleaned_blocks)
        usage = _merge_usage(usage, cleanup_usage)
        analysis_meta.update(cleanup_meta)
        if include_prompt_estimate:
            analysis_meta["estimated_prompt_tokens"] = estimated_prompt_tokens
            analysis_meta["pdf_text_length"] = len(pdf_content)
            analysis_meta["pdf_text_pages"] = _count_extracted_pdf_pages(pdf_content)

        logger.info("分析完成: %s", display_name)
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
            final_cache_key = build_analysis_cache_key(cache_id, analysis_meta)
            cache_analysis(final_cache_key, normalized, analysis_meta)
        return normalized, usage, analysis_meta
    except Exception as e:
        logger.error("分析失败 %s (%s): %s", display_name, effective_model, str(e))
        return f"**分析出错**: {str(e)}", {}, {}


def analyze_paper(pdf_path, paper, max_pages=10, use_cache=True, thinking_mode=None, include_prompt_estimate=False):
    return _run_analysis_pipeline(
        pdf_path,
        cache_id=paper.get_short_id(),
        display_name=paper.title,
        paper=paper,
        max_pages=max_pages,
        use_cache=use_cache,
        thinking_mode=thinking_mode,
        include_prompt_estimate=include_prompt_estimate,
        source_name="arxiv_paper",
    )


def analyze_pdf_only(pdf_path, max_pages=10, title: str = None, use_cache=True, thinking_mode=None, include_prompt_estimate=False):
    from pathlib import Path

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error("PDF 文件不存在: %s", pdf_path)
        return f"**错误**: PDF 文件不存在: {pdf_path}", {}, {}

    return _run_analysis_pipeline(
        pdf_path,
        cache_id=pdf_path.stem,
        display_name=pdf_path.name,
        title=title,
        max_pages=max_pages,
        use_cache=use_cache,
        thinking_mode=thinking_mode,
        include_prompt_estimate=include_prompt_estimate,
        source_name=f"local_pdf:{pdf_path.name}",
    )

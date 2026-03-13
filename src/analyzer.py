# analyzer.py - 分析论文模块

import logging
import pdfplumber
import re

from config import ai_client, PRIORITY_TOPICS, SECONDARY_TOPICS
from cache import (
    get_cached_classification, cache_classification,
    get_cached_analysis, cache_analysis
)

logger = logging.getLogger(__name__)

SECTION_SPECS = [
    ("研究对象和背景", ["研究对象和背景", "研究对象与背景", "背景与研究对象", "研究背景", "背景"]),
    ("主要定理或主要结果", ["主要定理或主要结果", "主要结果", "主要定理", "核心结果", "关键结果"]),
    ("研究方法、关键技术和核心工具", ["研究方法、关键技术和核心工具", "研究方法与关键技术", "方法与工具", "研究方法", "方法", "技术路线"]),
    ("与之前工作的比较", ["与之前工作的比较", "与已有工作比较", "与先前工作比较", "与相关工作比较", "对比已有工作", "相关工作比较", "对比"]),
]

def _extract_sections(raw_text: str):
    text = (raw_text or "").replace("\r\n", "\n")
    lines = text.split("\n")
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    headings = []
    for idx, line in enumerate(lines):
        line_clean = re.sub(r"^[#\s>*-]+", "", line)
        line_clean = re.sub(r"^\d+\s*[.\、]\s*", "", line_clean)
        line_clean = line_clean.replace("**", "").replace("__", "")
        line_clean = re.sub(r"[:：]\s*$", "", line_clean).strip()
        if not line_clean:
            continue
        for canonical, aliases in SECTION_SPECS:
            if any(alias in line_clean for alias in aliases):
                headings.append(
                    {
                        "canonical": canonical,
                        "start": offsets[idx] + len(line) + 1,
                        "line_index": idx,
                    }
                )
                break

    # 只保留每个章节首次出现的位置
    seen = set()
    unique_headings = []
    for h in sorted(headings, key=lambda x: x["start"]):
        if h["canonical"] in seen:
            continue
        seen.add(h["canonical"])
        unique_headings.append(h)

    sections = {canonical: "" for canonical, _ in SECTION_SPECS}
    for i, h in enumerate(unique_headings):
        end = unique_headings[i + 1]["start"] if i + 1 < len(unique_headings) else len(text)
        content = text[h["start"]:end].strip()
        sections[h["canonical"]] = content

    return sections

def _extract_zh_title(raw_text: str, fallback: str):
    text = (raw_text or "").replace("\r\n", "\n")
    match = re.search(r"中文标题\s*[:：]\s*(.+)", text)
    if match:
        title = match.group(1).strip()
        if title:
            return title
    return fallback

def normalize_analysis_markdown(raw_text: str, zh_title: str):
    sections = _extract_sections(raw_text)

    def section_or_placeholder(key: str):
        content = (sections.get(key) or "").strip()
        return content if content else "（模型未给出相关内容）"

    return (
        f"# {zh_title}\n\n"
        "## 详细分析\n\n"
        "### 1. 研究对象和背景\n"
        f"{section_or_placeholder('研究对象和背景')}\n\n"
        "### 2. 主要定理或主要结果\n"
        f"{section_or_placeholder('主要定理或主要结果')}\n\n"
        "### 3. 研究方法、关键技术和核心工具\n"
        f"{section_or_placeholder('研究方法、关键技术和核心工具')}\n\n"
        "### 4. 与之前工作的比较\n"
        f"{section_or_placeholder('与之前工作的比较')}\n"
    )

def extract_pdf_text(pdf_path, max_pages=10):
    """从PDF文件中提取文本内容"""
    try:
        text_content = ""
        with pdfplumber.open(pdf_path) as pdf:
            # 限制页数以避免过长的内容
            if max_pages is None:
                pages_to_read = len(pdf.pages)
            else:
                pages_to_read = min(len(pdf.pages), max_pages)
            
            for i in range(pages_to_read):
                page = pdf.pages[i]
                page_text = page.extract_text()
                if page_text:
                    text_content += f"\n=== 第{i+1}页 ===\n{page_text}\n"
        
        logger.info(f"成功从PDF提取文本，共{pages_to_read}页")
        return text_content
    except Exception as e:
        logger.error(f"PDF文本提取失败 {pdf_path}: {str(e)}")
        return f"PDF文本提取失败: {str(e)}"

def check_topic_relevance(paper):
    """使用AI判断论文是否符合指定主题，并返回优先级"""
    arxiv_id = paper.get_short_id()
    
    # 检查缓存
    cached = get_cached_classification(arxiv_id)
    if cached is not None:
        priority, reason = cached
        logger.info(f"[缓存命中] 分类结果: {paper.title} -> 优先级{priority}")
        return priority, reason
    
    try:
        # 从Author对象中提取作者名
        author_names = [author.name for author in paper.authors]
        
        # 获取论文摘要
        abstract = paper.summary if hasattr(paper, 'summary') else "无摘要"
        
        prompt = f"""
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
        
        logger.info(f"正在检查主题相关性: {paper.title}")
        result = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一位专业的学术论文分类专家。请严格按照要求的格式回答。"},
                {"role": "user", "content": prompt},
            ]
        )
        logger.info(f"主题相关性检查结果: {result}")
        
        # 判断优先级
        if result.startswith("优先级1"):
            reason = result.replace("优先级1", "").strip(" -")
            logger.info(f"论文符合重点关注主题: {paper.title} - {reason}")
            priority, reason = 1, reason
        elif result.startswith("优先级2"):
            reason = result.replace("优先级2", "").strip(" -")
            logger.info(f"论文符合了解主题: {paper.title} - {reason}")
            priority, reason = 2, reason
        else:
            logger.info(f"论文不符合主题要求，跳过: {paper.title}")
            priority, reason = 0, "不符合主题要求"
        
        # 保存到缓存
        cache_classification(arxiv_id, priority, reason)
        return priority, reason
            
    except Exception as e:
        logger.error(f"检查主题相关性失败 {paper.title}: {str(e)}")
        # 出错时默认为优先级2，避免遗漏
        return 2, f"检查出错，默认处理: {str(e)}"

def analyze_paper(pdf_path, paper, max_pages=10, use_cache=True):
    """分析论文内容，支持多种AI分析后端"""
    arxiv_id = paper.get_short_id()
    
    if use_cache:
        cached = get_cached_analysis(arxiv_id)
        if cached is not None:
            logger.info(f"[缓存命中] 分析结果: {paper.title}")
            return cached
    
    try:
        # 从Author对象中提取作者名
        author_names = [author.name for author in paper.authors]

        # 提取PDF文本内容
        pdf_content = extract_pdf_text(pdf_path, max_pages=max_pages)

        # 获取高质量中文标题翻译
        from translator import translate_abstract_with_deepseek
        zh_title_raw = translate_abstract_with_deepseek(paper, translate_title_only=True, use_cache=use_cache)
        
        # 提取纯中文标题用于日志
        zh_title_clean = paper.title
        if "**中文标题**:" in zh_title_raw:
            for line in zh_title_raw.split('\n'):
                if line.startswith("**中文标题**:"):
                    zh_title_clean = line.replace("**中文标题**:", "").strip()
                    break

        prompt = fr"""
【重要】请使用中文回答，并以Markdown格式输出。

## 标题层级结构（必须严格遵循）

# 中文标题

## 详细分析

### 1. 研究对象和背景
[内容...]

### 2. 主要定理或主要结果
[内容...]

### 3. 研究方法、关键技术和核心工具
[内容...]

### 4. 与之前工作的比较
[内容...]

## 具体要求

1. **标题层级**：必须使用上述精确的标题结构，每个章节必须以 "### 1."、"### 2."、"### 3."、"### 4." 开头，不能改变数字顺序，不能省略数字
2. **禁止加粗标题**：章节标题中不要使用 **加粗** 标记
3. **公式格式**：
   - 行内公式用 $...$（注意公式内部无空格，如 $E=mc^2$）
   - 行间公式用 $$...$$，且公式前后各空一行
   - 禁止使用 \[...\] 包裹公式
4. **自然段格式**：每个章节内的内容用自然段叙述，不要用列表
5. **中文标题**：请在开头单独输出一行作为中文标题

请开始分析论文：

论文标题: {paper.title}
作者: {', '.join(author_names)}
类别: {', '.join(paper.categories)}
发布时间: {paper.published}

论文摘要: {paper.summary}

论文PDF内容:
{pdf_content}

请严格按照上述标题结构输出分析内容。
"""

        logger.info(f"正在分析论文: {zh_title_clean}")
        analysis = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复。"},
                {"role": "user", "content": prompt},
            ]
        )
        logger.info(f"论文分析完成: {paper.title}")
        
        normalized = normalize_analysis_markdown(analysis, zh_title_clean)
        if use_cache:
            cache_analysis(arxiv_id, normalized)
        return normalized
    except Exception as e:
        logger.error(f"分析论文失败 {paper.title}: {str(e)}")
        return f"**论文分析出错**: {str(e)}"


def analyze_pdf_only(pdf_path, max_pages=10, title: str = None, use_cache=True):
    """
    纯 PDF 分析函数，不依赖 arXiv 元数据
    
    Args:
        pdf_path: PDF 文件路径
        max_pages: 最大提取页数，None 表示全部
        title: 可选的论文标题，如果不提供则从 PDF 文件名推断
    
    Returns:
        分析结果字符串
    """
    from pathlib import Path
    
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.error(f"PDF 文件不存在: {pdf_path}")
        return f"**错误**: PDF 文件不存在: {pdf_path}"
    
    if use_cache:
        cache_key = pdf_path.stem
        cached = get_cached_analysis(cache_key)
        if cached is not None:
            logger.info(f"[缓存命中] 分析结果: {pdf_path.name}")
            return cached
    
    try:
        # 提取 PDF 文本内容
        pdf_content = extract_pdf_text(str(pdf_path), max_pages=max_pages)
        
        # 如果没有提供标题，从文件名推断
        if not title:
            title = pdf_path.stem.replace('_', ' ').replace('-', ' ')
        
        prompt = fr"""
【重要】请使用中文回答，并以Markdown格式输出。

## 标题层级结构（必须严格遵循）

# 中文标题

## 详细分析

### 1. 研究对象和背景
[内容...]

### 2. 主要定理或主要结果
[内容...]

### 3. 研究方法、关键技术和核心工具
[内容...]

### 4. 与之前工作的比较
[内容...]

## 具体要求

1. **标题层级**：必须使用上述精确的标题结构，每个章节必须以 "### 1."、"### 2."、"### 3."、"### 4." 开头，不能改变数字顺序，不能省略数字
2. **禁止加粗标题**：章节标题中不要使用 **加粗** 标记
3. **公式格式**：
   - 行内公式用 $...$（注意公式内部无空格，如 $E=mc^2$）
   - 行间公式用 $$...$$，且公式前后各空一行
   - 禁止使用 \[...\] 包裹公式
4. **自然段格式**：每个章节内的内容用自然段叙述，不要用列表
5. **基本信息**：请先输出基本信息（中文标题、英文标题、作者），格式如下：
   - **中文标题**: [翻译的标题]
   - **英文标题**: [原文标题]
   - **作者**: [作者列表]

请开始分析论文PDF：

论文PDF内容:
{pdf_content}

请严格按照上述标题结构输出分析内容。
"""

        logger.info(f"正在分析 PDF: {pdf_path.name}")
        analysis = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复。"},
                {"role": "user", "content": prompt},
            ]
        )
        logger.info(f"PDF 分析完成: {pdf_path.name}")
        
        zh_title = _extract_zh_title(analysis, title)
        normalized = normalize_analysis_markdown(analysis, zh_title)
        if use_cache:
            cache_analysis(cache_key, normalized)
        return normalized
        
    except Exception as e:
        logger.error(f"分析 PDF 失败 {pdf_path}: {str(e)}")
        return f"**PDF 分析出错**: {str(e)}"

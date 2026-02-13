# analyzer.py - 分析论文模块

import logging
import pdfplumber

from config import ai_client, PRIORITY_TOPICS, SECONDARY_TOPICS
from cache import (
    get_cached_classification, cache_classification,
    get_cached_analysis, cache_analysis
)

logger = logging.getLogger(__name__)

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
【重要】请使用中文回答，并以Markdown格式 (包含数学公式)，分自然段格式输出。请严格注意：所有行内公式请用 $...$ 包裹, 注意公式$...$内部前后不要有空格, 以免影响渲染, 行间公式使用 $$...$$, 并在公式前后空一行. 保证公式能被Markdown正确渲染。将你认为重要的词语加粗表示.
请在开头单独输出一行：{zh_title_raw}

论文标题: {paper.title}
作者: {', '.join(author_names)}
类别: {', '.join(paper.categories)}
发布时间: {paper.published}

论文摘要: {paper.summary}

论文PDF内容:
{pdf_content}

请基于上述论文的摘要和PDF内容进行分析，并提供：
1. 研究对象和背景 (约2000字): 给出论文描述的方程或系统, 如果在Introduction的部分给出了方程组的数学公式, 请一并给出 (用行间公式表示); 如果文章研究的是某一种现象的验证, 请描述现象。如果PDE研究的区域, 边值条件或函数空间有特殊之处, 请一并说明。
2. 主要定理或主要结果 : 给出文章证明的主要定理（Theorem X.X 或 Proposition X.X）, 包括假设条件和结论。
3. 研究方法、关键技术和核心工具 (约4000字):
a) 描述证明中使用的核心分析学工具（例如：不动点定理、紧性原理、变分方法、Strichartz 估计、特定类型的能量估计）; b) 描述论文中解决技术性难题（如非线性项或奇异性）时采用的主要技巧。
4. 与之前工作的比较 (约4000字):
a) 描述文章声称做出的突破 or 改进。这种改进主要体现在放宽了先前工作的哪些假设条件（例如：对初始数据正则性要求的降低、维度的推广等）？或者论文获得的结果（如解的正则性、存在性、唯一性或稳定性）比现有结果强在哪里？

重要: 再次提醒, 由于内容需要符合mathjax的渲染要求, 请严格注意：所有行内公式请用单美元符号 $...$; 同样, 不要使用 \[...\] 包裹行间公式, 请使用 $$...$$ 包裹行间公式, 并在公式前后空一行. 此外, 所有小标题中不要再用加粗标记, 请直接使用普通文字.

        """

        logger.info(f"正在分析论文: {zh_title_clean}")
        analysis = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复。"},
                {"role": "user", "content": prompt},
            ]
        )
        logger.info(f"论文分析完成: {paper.title}")
        
        if use_cache:
            cache_analysis(arxiv_id, analysis)
        return analysis
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
【重要】请使用中文回答，并以Markdown格式 (包含数学公式)，分自然段格式输出。请严格注意：所有行内公式请用 $...$ 包裹, 注意公式$...$内部前后不要有空格, 以免影响渲染, 行间公式使用 $$...$$, 并在公式前后空一行. 保证公式能被Markdown正确渲染。将你认为重要的词语加粗表示.

论文PDF内容:
{pdf_content}

请基于上述论文的PDF内容进行分析，并提供：

0. 首先，请从PDF内容中提取论文的基本信息，格式如下：
**中文标题**: [从PDF中识别并翻译的论文标题]
**英文标题**: [从PDF中识别的原始英文标题]
**作者**: [从PDF中识别的作者列表]

1. 研究对象和背景 (约2000字): 给出论文描述的方程或系统, 如果在Introduction的部分给出了方程组的数学公式, 请一并给出 (用行间公式表示); 如果文章研究的是某一种现象的验证, 请描述现象。如果PDE研究的区域, 边值条件或函数空间有特殊之处, 请一并说明。

2. 主要定理或主要结果: 给出文章证明的主要定理（Theorem X.X 或 Proposition X.X）, 包括假设条件和结论。

3. 研究方法、关键技术和核心工具 (约4000字):
a) 描述证明中使用的核心分析学工具（例如：不动点定理、紧性原理、变分方法、Strichartz 估计、特定类型的能量估计）; 
b) 描述论文中解决技术性难题（如非线性项或奇异性）时采用的主要技巧。

4. 与之前工作的比较 (约4000字):
a) 描述文章声称做出的突破或改进。这种改进主要体现在放宽了先前工作的哪些假设条件（例如：对初始数据正则性要求的降低、维度的推广等）？或者论文获得的结果（如解的正则性、存在性、唯一性或稳定性）比现有结果强在哪里？

重要: 再次提醒, 由于内容需要符合mathjax的渲染要求, 请严格注意：所有行内公式请用单美元符号 $...$; 同样, 不要使用 \[...\] 包裹行间公式, 请使用 $$...$$ 包裹行间公式, 并在公式前后空一行. 此外, 所有小标题中不要再用加粗标记, 请直接使用普通文字.
        """

        logger.info(f"正在分析 PDF: {pdf_path.name}")
        analysis = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复。"},
                {"role": "user", "content": prompt},
            ]
        )
        logger.info(f"PDF 分析完成: {pdf_path.name}")
        
        if use_cache:
            cache_analysis(cache_key, analysis)
        return analysis
        
    except Exception as e:
        logger.error(f"分析 PDF 失败 {pdf_path}: {str(e)}")
        return f"**PDF 分析出错**: {str(e)}"

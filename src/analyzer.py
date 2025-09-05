# analyzer.py - 分析论文模块

import logging
import pdfplumber

from config import ai_client, PRIORITY_TOPICS, SECONDARY_TOPICS

logger = logging.getLogger(__name__)

def extract_pdf_text(pdf_path, max_pages=5):
    """从PDF文件中提取文本内容"""
    try:
        text_content = ""
        with pdfplumber.open(pdf_path) as pdf:
            # 限制页数以避免过长的内容
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
            return 1, reason
        elif result.startswith("优先级2"):
            reason = result.replace("优先级2", "").strip(" -")
            logger.info(f"论文符合了解主题: {paper.title} - {reason}")
            return 2, reason
        else:
            logger.info(f"论文不符合主题要求，跳过: {paper.title}")
            return 0, "不符合主题要求"
            
    except Exception as e:
        logger.error(f"检查主题相关性失败 {paper.title}: {str(e)}")
        # 出错时默认为优先级2，避免遗漏
        return 2, f"检查出错，默认处理: {str(e)}"

def analyze_paper_with_deepseek(pdf_path, paper):
    """使用DeepSeek API分析论文（使用OpenAI 0.28.0兼容格式）"""
    try:
        # 从Author对象中提取作者名
        author_names = [author.name for author in paper.authors]
        
        # 提取PDF文本内容
        pdf_content = extract_pdf_text(pdf_path)
        
        prompt = f"""
        论文标题: {paper.title}
        作者: {', '.join(author_names)}
        类别: {', '.join(paper.categories)}
        发布时间: {paper.published}
        
        论文摘要: {paper.summary}
        
        论文PDF内容（前20页）:
        {pdf_content}
        
        请基于上述论文的摘要和PDF内容进行分析，并提供：
        1. 研究对象和背景: 给出论文描述的方程或系统, 如果在Introduction的部分给出了方程组的数学公式, 请一并给出 (用行间公式表示); 如果文章研究的是某一种现象的验证, 请描述现象.
        2. 主要定理或主要结果: 给出文章证明的主要定理.
        3. 研究方法, 具体采用的技术, 工具
        4. 与之前工作的比较: 文章是否声称做出了什么突破或改进? 如果有，请描述.
        
        请使用中文回答，并以Markdown格式 (包含数学公式), 分自然段格式输出。
        """
        
        logger.info(f"正在分析论文: {paper.title}")
        analysis = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一位专门总结和分析学术论文的研究助手。请使用中文回复。"},
                {"role": "user", "content": prompt},
            ]
        )
        
        logger.info(f"论文分析完成: {paper.title}")
        return analysis
    except Exception as e:
        logger.error(f"分析论文失败 {paper.title}: {str(e)}")
        return f"**论文分析出错**: {str(e)}"

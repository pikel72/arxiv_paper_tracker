# translator.py - 翻译摘要模块

import logging

from config import ai_client

logger = logging.getLogger(__name__)

def translate_abstract_with_deepseek(paper, translate_title_only=False):
    """使用DeepSeek API翻译论文摘要"""
    try:
        # 从Author对象中提取作者名

        author_names = [author.name for author in paper.authors]
        
        if translate_title_only:
            prompt = f"""
            请将以下英文标题翻译成中文，保持学术性和准确性：
            
            论文标题: {paper.title}
            
            请提供：
            1. 标题的中文翻译
            
            格式：
            **中文标题**: [翻译后的标题]
            """
            
            logger.info(f"正在翻译标题: {paper.title}")
        else:
            prompt = f"""
            请将以下英文摘要翻译成中文，保持学术性和准确性：
            
            论文标题: {paper.title}
            摘要: {paper.summary}
            
            请提供：
            1. 标题的中文翻译
            2. 摘要的中文翻译（保持原文的学术表达风格）
            
            格式：
            **中文标题**: [翻译后的标题]
            
            **摘要翻译**: [翻译后的摘要]
            """
            
            logger.info(f"正在翻译摘要: {paper.title}")
        
        translation = ai_client.chat_completion(
            messages=[
                {"role": "system", "content": "你是一位专业的学术翻译专家，擅长数学和物理领域的翻译。"},
                {"role": "user", "content": prompt},
            ]
        )
        if translate_title_only:
            logger.info(f"标题翻译完成: {paper.title}")
        else:
            logger.info(f"摘要翻译完成: {paper.title}")
        return translation
    except Exception as e:
        if translate_title_only:
            logger.error(f"翻译标题失败 {paper.title}: {str(e)}")
        else:
            logger.error(f"翻译摘要失败 {paper.title}: {str(e)}")
        return f"**翻译出错**: {str(e)}"

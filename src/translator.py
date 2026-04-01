# translator.py - 翻译摘要模块

import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import ai_client
from cache import get_cached_translation, cache_translation

logger = logging.getLogger(__name__)


class StructuredTitleTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chinese_title: str = Field(description="论文标题的中文翻译，只返回标题文本本身。")

    @field_validator("chinese_title", mode="before")
    @classmethod
    def normalize_title(cls, value):
        text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
        if not text:
            raise ValueError("中文标题不能为空")
        return text


class StructuredAbstractTranslation(StructuredTitleTranslation):
    abstract_translation: str = Field(description="论文摘要的完整中文翻译，保持原文的学术语气和信息。")

    @field_validator("abstract_translation", mode="before")
    @classmethod
    def normalize_abstract(cls, value):
        text = str(value or "").replace("\r\n", "\n").strip()
        if not text:
            raise ValueError("摘要翻译不能为空")
        return text


def _render_title_translation(result: StructuredTitleTranslation):
    return f"**中文标题**: {result.chinese_title}"


def _render_abstract_translation(result: StructuredAbstractTranslation):
    return (
        f"**中文标题**: {result.chinese_title}\n\n"
        f"**摘要翻译**: {result.abstract_translation}"
    )


def _build_translation_messages(paper, translate_title_only=False):
    if translate_title_only:
        prompt = (
            "请严格按照给定的结构化 schema 返回翻译结果。\n\n"
            "请将以下英文论文标题翻译成中文，保持学术性、准确性和简洁性。\n\n"
            f"论文标题: {paper.title}\n"
        )
    else:
        prompt = (
            "请严格按照给定的结构化 schema 返回翻译结果。\n\n"
            "请将以下英文论文标题和摘要翻译成中文，保持学术性和准确性，尽量保留原文术语与论证语气。\n\n"
            f"论文标题: {paper.title}\n"
            f"摘要: {paper.summary}\n"
        )
    return [
        {"role": "system", "content": "你是一位专业的学术翻译专家，擅长数学和物理领域的翻译。请严格遵守返回 schema。"},
        {"role": "user", "content": prompt},
    ]


def _build_translation_fallback_prompt(paper, translate_title_only=False):
    if translate_title_only:
        return f"""
            请将以下英文标题翻译成中文，保持学术性和准确性：
            
            论文标题: {paper.title}
            
            请提供：
            1. 标题的中文翻译
            
            格式：
            **中文标题**: [翻译后的标题]
            """
    return f"""
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


def translate_abstract_with_deepseek(paper, translate_title_only=False, use_cache=True):
    """使用DeepSeek API翻译论文摘要"""
    arxiv_id = paper.get_short_id()

    if use_cache:
        cached = get_cached_translation(arxiv_id, title_only=translate_title_only)
        if cached is not None:
            cache_type = "标题" if translate_title_only else "摘要"
            logger.info(f"[缓存命中] {cache_type}翻译: {paper.title}")
            return cached

    try:
        if translate_title_only:
            logger.info(f"正在翻译标题: {paper.title}")
        else:
            logger.info(f"正在翻译摘要: {paper.title}")

        try:
            messages = _build_translation_messages(paper, translate_title_only=translate_title_only)
            if translate_title_only:
                structured = ai_client.structured_chat_completion_with_usage(
                    messages=messages,
                    response_model=StructuredTitleTranslation,
                )[0]
                translation = _render_title_translation(structured)
            else:
                structured = ai_client.structured_chat_completion_with_usage(
                    messages=messages,
                    response_model=StructuredAbstractTranslation,
                )[0]
                translation = _render_abstract_translation(structured)
        except Exception as structured_error:
            logger.warning("结构化翻译失败，将回退到普通文本模式: %s", str(structured_error))
            prompt = _build_translation_fallback_prompt(paper, translate_title_only=translate_title_only)
            translation = ai_client.chat_completion(
                messages=[
                    {"role": "system", "content": "你是一位专业的学术翻译专家，擅长数学和物理领域的翻译。"},
                    {"role": "user", "content": prompt},
                ]
            )

        # 提取翻译后的标题用于日志
        translated_title = ""
        if "**中文标题**:" in translation:
            for line in translation.split('\n'):
                if line.startswith("**中文标题**:"):
                    translated_title = line.replace("**中文标题**:", "").strip()
                    break
        
        log_title = translated_title if translated_title else paper.title
        
        if translate_title_only:
            logger.info(f"标题翻译完成: {log_title}")
        else:
            logger.info(f"摘要翻译完成: {log_title}")
        
        if use_cache:
            cache_translation(arxiv_id, translation, title_only=translate_title_only)
        return translation
    except Exception as e:
        if translate_title_only:
            logger.error(f"翻译标题失败 {paper.title}: {str(e)}")
        else:
            logger.error(f"翻译摘要失败 {paper.title}: {str(e)}")
        return f"**翻译出错**: {str(e)}"

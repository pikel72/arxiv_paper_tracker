# translator.py - 翻译摘要模块

import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import ai_client
from cache import get_cached_translation, cache_translation

logger = logging.getLogger(__name__)

TRANSLATION_TITLE_REQUIREMENTS = """
翻译要求：
1. 翻译对象默认面向偏微分方程与分析理论研究者，而不是面向泛科普读者。
2. 标题翻译要学术、准确、克制，优先使用本领域常见术语，不要写成解释性副标题，也不要为了“顺口”改写定理强度。
3. 原文中的数学对象、方程名、模型名、性质名、方法名要尽量使用稳定译法；拿不准时宁可直译，也不要擅自意译发挥。
4. 不要遗漏限定词，如 global, local, quantitative, asymptotic, sharp, generic, axisymmetric, without swirl, critical, supercritical, conditional 等。
5. existence、uniqueness、regularity、well-posedness、blow-up、scattering、decay、stability、instability、asymptotics、vanishing viscosity 等术语要准确保留其理论含义，不要弱化。
6. 数学符号、变量名、公式、定理编号、范数记号、函数空间记号应原样保留。
7. 只返回标题本身，不要附加注释、解释或评价。
""".strip()

TRANSLATION_ABSTRACT_REQUIREMENTS = """
翻译要求：
1. 摘要翻译必须忠实于原文信息，不要擅自压缩掉假设、范围、否定词、比较对象、数量级、结论强度和适用条件。
2. 作者“证明了什么”要明确译出，不要把 proved, established, showed, validated 等强结论弱化成“讨论了”“研究了”。
3. 若原文涉及主要定理、先验估计、函数空间、误差阶、增长率、缩放、稳定性/不稳定性、爆破/散射等内容，应尽量完整保留，不要翻成空泛综述。
4. 关键术语、方程名、模型名、技术名、函数空间、范数、缩放、误差阶、增长率、公式和符号要尽量保留；如 $L^p$, $H^s$, Sobolev, Besov, Strichartz, Carleman, bootstrap, compactness 等通常不应被模糊化。
5. 如果原文句子很长，可以拆成更自然的中文句子，但不要改变逻辑关系，不要把条件和结论翻串，也不要把 conjecture、heuristic、formal、conditional 说成严格定理。
6. 语气保持学术摘要风格，避免口语化、宣传化，也不要额外加入解释、评论或推测。
""".strip()


class StructuredTitleTranslation(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chinese_title: str = Field(description="面向偏微分方程与分析理论读者的中文标题翻译, 只返回标题文本本身。")

    @field_validator("chinese_title", mode="before")
    @classmethod
    def normalize_title(cls, value):
        text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
        if not text:
            raise ValueError("中文标题不能为空")
        return text


class StructuredAbstractTranslation(StructuredTitleTranslation):
    abstract_translation: str = Field(
        description="论文摘要的完整中文翻译, 保持原文的学术语气和信息, 尽量保留假设、结论强度、函数空间、公式与术语。"
    )

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
            f"{TRANSLATION_TITLE_REQUIREMENTS}\n\n"
            "请将以下英文论文标题翻译成中文。\n\n"
            f"论文标题: {paper.title}\n"
        )
    else:
        prompt = (
            "请严格按照给定的结构化 schema 返回翻译结果。\n\n"
            f"{TRANSLATION_TITLE_REQUIREMENTS}\n\n"
            f"{TRANSLATION_ABSTRACT_REQUIREMENTS}\n\n"
            "请将以下英文论文标题和摘要翻译成中文。\n\n"
            f"论文标题: {paper.title}\n"
            f"摘要: {paper.summary}\n"
        )
    return [
        {"role": "system", "content": "你是一位偏微分方程与分析理论方向的学术翻译专家. 请严格遵守返回 schema. "},
        {"role": "user", "content": prompt},
    ]


def _build_translation_fallback_prompt(paper, translate_title_only=False):
    if translate_title_only:
        return f"""
            {TRANSLATION_TITLE_REQUIREMENTS}

            请将以下英文标题翻译成中文：
            
            论文标题: {paper.title}
            
            请提供：
            1. 标题的中文翻译
            
            格式：
            **中文标题**: [翻译后的标题]
            """
    return f"""
            {TRANSLATION_TITLE_REQUIREMENTS}

            {TRANSLATION_ABSTRACT_REQUIREMENTS}

            请将以下英文摘要翻译成中文：
            
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
                    {"role": "system", "content": "你是一位偏微分方程与分析理论方向的学术翻译专家. "},
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

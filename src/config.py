# config.py - 配置文件

import ast
import logging
import os
import re
from pathlib import Path

import instructor
from dotenv import load_dotenv
from litellm import completion

load_dotenv()

logger = logging.getLogger(__name__)


def _get_optional_int(name):
    value = os.getenv(name)
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        logger.warning("环境变量 %s 不是有效整数，将忽略: %s", name, value)
        return None


def _get_bool_env(name, default="off"):
    value = os.getenv(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _get_optional_bool_env(name):
    value = os.getenv(name)
    if value in (None, ""):
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    logger.warning("环境变量 %s 不是有效布尔值，将忽略: %s", name, value)
    return None


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GLM_API_KEY = os.getenv("GLM_API_KEY")
QWEN_API_KEY = os.getenv("QWEN_API_KEY")
DOUBAO_API_KEY = os.getenv("DOUBAO_API_KEY")
DOUBAO_API_BASE = os.getenv("DOUBAO_API_BASE")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
KIMI_API_BASE = os.getenv("KIMI_API_BASE")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY")
NVIDIA_NIM_API_KEY = os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NVIDIA_API_KEY")
NVIDIA_NIM_API_BASE = os.getenv("NVIDIA_NIM_API_BASE") or os.getenv("NVIDIA_API_BASE")
CUSTOM_API_BASE = os.getenv("CUSTOM_API_BASE")
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "qwen")
AI_MODEL = os.getenv("AI_MODEL", "qwen-turbo")
ANALYSIS_THINKING_MODE = _get_optional_bool_env("ANALYSIS_THINKING_MODE")
ANALYSIS_THINKING_MODEL = os.getenv("ANALYSIS_THINKING_MODEL")
ANALYSIS_THINKING_BUDGET = _get_optional_int("ANALYSIS_THINKING_BUDGET")
ANALYSIS_THINKING_EFFORT = os.getenv("ANALYSIS_THINKING_EFFORT")
ANALYSIS_CLEANUP_ENABLED = _get_bool_env("ANALYSIS_CLEANUP_ENABLED", "off")
ANALYSIS_CLEANUP_PROVIDER = os.getenv("ANALYSIS_CLEANUP_PROVIDER") or AI_PROVIDER
ANALYSIS_CLEANUP_MODEL = os.getenv("ANALYSIS_CLEANUP_MODEL") or AI_MODEL
ANALYSIS_CLEANUP_THINKING_MODE = _get_bool_env("ANALYSIS_CLEANUP_THINKING_MODE", "off")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = [email.strip() for email in os.getenv("EMAIL_TO", "").split(",") if email.strip()]

PAPERS_DIR = Path("./papers")
RESULTS_DIR = Path("./results")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
LOG_FILE = os.getenv("LOG_FILE", "arxiv_tracker.log")
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", "5242880"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))

CATEGORIES = [cat.strip() for cat in os.getenv("ARXIV_CATEGORIES", "math.AP").split(",") if cat.strip()]
MAX_PAPERS = int(os.getenv("MAX_PAPERS", "50"))
SEARCH_DAYS = int(os.getenv("SEARCH_DAYS", "3"))

default_priority_topics = [
    "流体力学中偏微分方程的数学理论",
    "Navier-Stokes方程",
    "Euler方程",
    "Prandtl方程",
    "湍流",
    "涡度",
]

default_secondary_topics = [
    "色散偏微分方程的数学理论",
    "双曲偏微分方程的数学理论",
    "调和分析",
    "极大算子",
    "椭圆偏微分方程",
    "抛物偏微分方程",
]

PRIORITY_TOPICS = os.getenv("PRIORITY_TOPICS", "|".join(default_priority_topics)).split("|")
SECONDARY_TOPICS = os.getenv("SECONDARY_TOPICS", "|".join(default_secondary_topics)).split("|")

PRIORITY_ANALYSIS_DELAY = int(os.getenv("PRIORITY_ANALYSIS_DELAY", "3"))
SECONDARY_ANALYSIS_DELAY = int(os.getenv("SECONDARY_ANALYSIS_DELAY", "2"))
MAX_THREADS = int(os.getenv("MAX_THREADS", "5"))

EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "ArXiv论文分析报告")

STRUCTURED_MODE_MAP = {
    "json": instructor.Mode.JSON,
    "tools": instructor.Mode.TOOLS,
    "tools_strict": instructor.Mode.TOOLS_STRICT,
}

PROVIDER_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": DEEPSEEK_API_KEY,
        "thinking_support": "model",
        "default_thinking_model": "deepseek-reasoner",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": OPENAI_API_KEY,
        "thinking_support": "model",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "api_key": GLM_API_KEY,
        "thinking_support": "model",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": QWEN_API_KEY,
        "thinking_support": "enable_thinking",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "doubao": {
        "base_url": DOUBAO_API_BASE or "https://ark.cn-beijing.volces.com/api/v3",
        "api_key": DOUBAO_API_KEY,
        "thinking_support": "model",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "kimi": {
        "base_url": KIMI_API_BASE or "https://api.moonshot.cn/v1",
        "api_key": KIMI_API_KEY,
        "thinking_support": "model",
        "default_thinking_model": "kimi-k2-thinking",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "thinking_support": "reasoning",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": SILICONFLOW_API_KEY,
        "thinking_support": "model",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "nvidia_nim": {
        "base_url": NVIDIA_NIM_API_BASE or "https://integrate.api.nvidia.com/v1",
        "api_key": NVIDIA_NIM_API_KEY,
        "thinking_support": "model",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
    "custom": {
        "base_url": CUSTOM_API_BASE,
        "api_key": CUSTOM_API_KEY,
        "thinking_support": "model",
        "structured_mode": "json",
        "litellm_provider": "openai",
    },
}

PROVIDER_API_KEY_HINTS = {
    "deepseek": ["DEEPSEEK_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "glm": ["GLM_API_KEY"],
    "qwen": ["QWEN_API_KEY"],
    "doubao": ["DOUBAO_API_KEY"],
    "kimi": ["KIMI_API_KEY"],
    "openrouter": ["OPENROUTER_API_KEY"],
    "siliconflow": ["SILICONFLOW_API_KEY"],
    "nvidia_nim": ["NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"],
    "custom": ["CUSTOM_API_KEY"],
}


def _read_attr_or_key(obj, name, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _coerce_text_block(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            text = _read_attr_or_key(item, "text")
            if text:
                parts.append(str(text))
                continue
            content = _read_attr_or_key(item, "content")
            if content:
                parts.append(str(content))
                continue
            parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return str(value)


class AIClient:
    def __init__(self, provider=None, model=None):
        requested_provider = provider or AI_PROVIDER
        requested_model = model or AI_MODEL

        self.provider = requested_provider
        self.model = requested_model

        if self.provider not in PROVIDER_CONFIG:
            raise ValueError(f"不支持的AI提供商: {self.provider}")

        self.provider_config = PROVIDER_CONFIG[self.provider]
        self._validate_provider_credentials()
        self.thinking_support = self.provider_config["thinking_support"]
        self.completion_fn = completion

    def _looks_like_prefixed_route_model(self, model_name):
        normalized = str(model_name or "").strip().lower()
        if not normalized or "/" not in normalized:
            return False
        prefixed_route_prefixes = (
            "qwen/",
            "openai/",
            "anthropic/",
            "google/",
            "mistralai/",
            "deepseek/",
            "meta/",
            "meta-llama/",
            "x-ai/",
            "moonshotai/",
            "nvidia/",
        )
        return normalized.startswith(prefixed_route_prefixes)

    def _validate_provider_credentials(self):
        api_key = self.provider_config.get("api_key")
        if isinstance(api_key, str) and api_key.strip():
            return

        hint_names = PROVIDER_API_KEY_HINTS.get(self.provider, [])
        hint_message = " / ".join(hint_names) if hint_names else "对应 API_KEY"
        error_message = f"AI 提供商 {self.provider} 缺少 API Key，请配置环境变量: {hint_message}"

        if self.provider == "qwen" and self._looks_like_prefixed_route_model(self.model):
            error_message += (
                "；检测到模型名使用前缀路由格式（例如 qwen/...）。"
                "这通常不是 DashScope 直连模型名。"
                "请显式选择服务商："
                "AI_PROVIDER=nvidia_nim 并配置 NVIDIA_NIM_API_KEY 或 NVIDIA_API_KEY，"
                "或 AI_PROVIDER=openrouter 并配置 OPENROUTER_API_KEY，"
                "或将 AI_MODEL 改为 qwen-plus 等 DashScope 模型并配置 QWEN_API_KEY。"
            )

        raise ValueError(error_message)

    def chat_completion(self, messages, thinking_mode=False, **kwargs):
        content, _, _ = self._do_chat_completion(messages, thinking_mode=thinking_mode, **kwargs)
        return content

    def chat_completion_with_usage(self, messages, thinking_mode=False, return_response_state=False, **kwargs):
        content, usage, response_state = self._do_chat_completion(messages, thinking_mode=thinking_mode, **kwargs)
        if return_response_state:
            return content, usage, response_state
        return content, usage

    def structured_chat_completion_with_usage(
        self,
        messages,
        response_model,
        thinking_mode=False,
        return_response_state=False,
        **kwargs,
    ):
        result, usage, response_state = self._do_chat_completion(
            messages,
            thinking_mode=thinking_mode,
            response_model=response_model,
            structured=True,
            **kwargs,
        )
        if return_response_state:
            return result, usage, response_state
        return result, usage

    def _looks_like_thinking_model(self, model_name):
        if not model_name:
            return False
        normalized = model_name.lower()
        if normalized.startswith(("o1", "o3", "o4")):
            return True
        markers = ("reasoner", "reasoning", "thinking", "r1", "qwq")
        return any(marker in normalized for marker in markers)

    def get_analysis_request_config(self, thinking_mode=False):
        if thinking_mode is None:
            thinking_mode = ANALYSIS_THINKING_MODE

        config = {
            "provider": self.provider,
            "effective_model": self.model,
            "thinking_requested": bool(thinking_mode),
            "thinking_applied": False,
            "thinking_support": self.thinking_support,
            "thinking_budget": None,
            "thinking_effort": None,
            "extra_body": {},
            "reasoning": None,
            "litellm_provider": self.provider_config.get("litellm_provider", "openai"),
            "structured_mode": self.provider_config.get("structured_mode", "json"),
        }

        if not thinking_mode:
            return config

        thinking_model = ANALYSIS_THINKING_MODEL
        default_thinking_model = self.provider_config.get("default_thinking_model")

        if self.thinking_support == "enable_thinking":
            config["thinking_applied"] = True
            config["effective_model"] = thinking_model or self.model
            if not thinking_model or thinking_model == self.model:
                config["extra_body"]["enable_thinking"] = True
                if ANALYSIS_THINKING_BUDGET is not None:
                    config["extra_body"]["thinking_budget"] = ANALYSIS_THINKING_BUDGET
            elif ANALYSIS_THINKING_BUDGET is not None:
                config["extra_body"]["thinking_budget"] = ANALYSIS_THINKING_BUDGET
            config["thinking_budget"] = ANALYSIS_THINKING_BUDGET
            return config

        if self.thinking_support == "reasoning":
            config["thinking_applied"] = True
            config["effective_model"] = thinking_model or self.model
            reasoning = {"enabled": True}
            if ANALYSIS_THINKING_EFFORT:
                reasoning["effort"] = ANALYSIS_THINKING_EFFORT
                config["thinking_effort"] = ANALYSIS_THINKING_EFFORT
            if ANALYSIS_THINKING_BUDGET is not None:
                reasoning["max_tokens"] = ANALYSIS_THINKING_BUDGET
                config["thinking_budget"] = ANALYSIS_THINKING_BUDGET
            config["reasoning"] = reasoning
            return config

        if self.thinking_support == "model":
            effective_model = thinking_model or default_thinking_model
            if not effective_model and self._looks_like_thinking_model(self.model):
                effective_model = self.model
            if effective_model:
                config["thinking_applied"] = True
                config["effective_model"] = effective_model
            return config

        return config

    def _create_kwargs(self, messages, request_config, kwargs):
        create_kwargs = {
            "model": request_config["effective_model"],
            "messages": messages,
            "api_key": self.provider_config["api_key"],
            "api_base": self.provider_config["base_url"],
            "base_url": self.provider_config["base_url"],
            "custom_llm_provider": request_config["litellm_provider"],
            **kwargs,
        }
        if request_config["extra_body"]:
            create_kwargs["extra_body"] = request_config["extra_body"]
        if request_config["reasoning"]:
            create_kwargs["reasoning"] = request_config["reasoning"]
        return create_kwargs

    def _is_thinking_unsupported_error(self, error_message):
        normalized = (error_message or "").lower()
        if "json_invalid" in normalized or "validation error for structuredpaperanalysis" in normalized:
            return False
        keywords = [
            "unsupported",
            "not support",
            "does not support",
            "unknown parameter",
            "unrecognized request argument",
            "invalid parameter",
            "invalid_request_error",
            "enable_thinking",
            "model not found",
            "no such model",
        ]
        return any(keyword in normalized for keyword in keywords)

    def _usage_to_dict(self, usage):
        if not usage:
            return {}
        prompt_tokens = _read_attr_or_key(usage, "prompt_tokens", 0) or 0
        completion_tokens = _read_attr_or_key(usage, "completion_tokens", 0) or 0
        total_tokens = _read_attr_or_key(usage, "total_tokens", 0) or 0
        usage_dict = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        reasoning_tokens = _read_attr_or_key(_read_attr_or_key(usage, "completion_tokens_details"), "reasoning_tokens")
        if reasoning_tokens is not None:
            usage_dict["reasoning_tokens"] = reasoning_tokens
        return usage_dict

    def _extract_reasoning_content(self, response):
        choices = _read_attr_or_key(response, "choices", []) or []
        if not choices:
            return ""
        message = _read_attr_or_key(choices[0], "message")
        reasoning_content = _read_attr_or_key(message, "reasoning_content")
        return _coerce_text_block(reasoning_content).strip()

    def _extract_content_and_usage(self, response):
        choices = _read_attr_or_key(response, "choices", []) or []
        if not choices:
            return "", {}
        message = _read_attr_or_key(choices[0], "message")
        content = _coerce_text_block(_read_attr_or_key(message, "content")).strip()
        usage = self._usage_to_dict(_read_attr_or_key(response, "usage"))
        return content, usage

    def _normalize_json_candidate(self, text):
        candidate = (text or "").strip()
        if not candidate:
            return ""
        if candidate.startswith("```"):
            fence_match = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.S)
            if fence_match:
                candidate = fence_match.group(1).strip()
        if candidate[:1] in "{[":
            return candidate
        match = re.search(r"(\{.*\}|\[.*\])", candidate, re.S)
        if match:
            return match.group(1).strip()
        return ""

    def _parse_structured_response(self, response_model, response):
        choices = _read_attr_or_key(response, "choices", []) or []
        if not choices:
            raise ValueError("结构化响应为空")
        message = _read_attr_or_key(choices[0], "message")
        content = _coerce_text_block(_read_attr_or_key(message, "content")).strip()
        reasoning_content = _coerce_text_block(_read_attr_or_key(message, "reasoning_content")).strip()
        candidates = []
        normalized_content = self._normalize_json_candidate(content)
        if normalized_content:
            candidates.append(normalized_content)
        normalized_reasoning = self._normalize_json_candidate(reasoning_content)
        if normalized_reasoning and normalized_reasoning not in candidates:
            candidates.append(normalized_reasoning)
        if not candidates:
            raise ValueError("结构化响应中没有可解析的 JSON 内容")

        last_error = None
        for candidate in candidates:
            try:
                return response_model.model_validate_json(candidate)
            except Exception as e:
                last_error = e
        if last_error is not None:
            raise last_error
        raise ValueError("结构化响应解析失败")

    def _build_synthetic_response_state(
        self,
        request_config,
        fallback_used=False,
        fallback_reason=None,
        reasoning_content_present=False,
    ):
        return {
            "provider": request_config["provider"],
            "effective_model": request_config["effective_model"],
            "thinking_requested": request_config["thinking_requested"],
            "thinking_applied": request_config["thinking_applied"],
            "thinking_budget": request_config["thinking_budget"],
            "thinking_effort": request_config["thinking_effort"],
            "fallback_used": bool(fallback_used),
            "fallback_reason": fallback_reason or "",
            "reasoning_content_present": bool(reasoning_content_present),
            "reasoning_content_length": 0,
            "structured_output_mode": request_config.get("structured_mode"),
        }

    def _extract_structured_candidate_from_error_message(self, error_message):
        text = error_message or ""
        for field_name in ("content", "reasoning_content"):
            pattern = rf"{field_name}='((?:\\\\.|[^'])*)'"
            for match in re.finditer(pattern, text, re.S):
                encoded = match.group(1)
                try:
                    value = ast.literal_eval("'" + encoded + "'")
                except Exception:
                    value = encoded
                candidate = self._normalize_json_candidate(value)
                if candidate:
                    return candidate, field_name == "reasoning_content"
        return "", False

    def _recover_structured_result_from_error_message(
        self,
        response_model,
        request_config,
        error_message,
        fallback_used=False,
        fallback_reason=None,
    ):
        candidate, from_reasoning = self._extract_structured_candidate_from_error_message(error_message)
        if not candidate:
            raise ValueError("异常信息中没有可恢复的结构化 JSON")
        result = response_model.model_validate_json(candidate)
        response_state = self._build_synthetic_response_state(
            request_config,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
            reasoning_content_present=from_reasoning,
        )
        return result, {}, response_state

    def _recover_structured_result_from_raw(
        self,
        create_kwargs,
        response_model,
        request_config,
        fallback_used=False,
        fallback_reason=None,
    ):
        response = self.completion_fn(**create_kwargs)
        result = self._parse_structured_response(response_model, response)
        usage = self._usage_to_dict(_read_attr_or_key(response, "usage"))
        response_state = self._build_response_state(
            request_config,
            response,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )
        return result, usage, response_state

    def _build_response_state(self, request_config, response, fallback_used=False, fallback_reason=None):
        reasoning_content = self._extract_reasoning_content(response)
        returned_model = _read_attr_or_key(response, "model")
        return {
            "provider": request_config["provider"],
            "effective_model": returned_model or request_config["effective_model"],
            "thinking_requested": request_config["thinking_requested"],
            "thinking_applied": request_config["thinking_applied"],
            "thinking_budget": request_config["thinking_budget"],
            "thinking_effort": request_config["thinking_effort"],
            "fallback_used": bool(fallback_used),
            "fallback_reason": fallback_reason or "",
            "reasoning_content_present": bool(reasoning_content),
            "reasoning_content_length": len(reasoning_content),
            "structured_output_mode": request_config.get("structured_mode"),
        }

    def _get_structured_client(self, request_config):
        structured_mode = request_config.get("structured_mode", "json")
        mode = STRUCTURED_MODE_MAP.get(structured_mode, instructor.Mode.JSON)
        return instructor.from_litellm(self.completion_fn, mode=mode)

    def _do_chat_completion(self, messages, thinking_mode=False, response_model=None, structured=False, **kwargs):
        import random
        import time

        max_retries = 3
        backoff_factor = 2
        base_kwargs = dict(kwargs)
        requested_config = self.get_analysis_request_config(thinking_mode=thinking_mode)

        if thinking_mode and not requested_config["thinking_applied"]:
            logger.warning("提供商 %s/%s 当前没有可用的思考模式能力，将使用普通模式", self.provider, self.model)

        request_sequence = [requested_config]
        if requested_config["thinking_applied"]:
            request_sequence.append(self.get_analysis_request_config(thinking_mode=False))

        fallback_reason = ""
        for index, request_config in enumerate(request_sequence):
            for attempt in range(max_retries):
                try:
                    create_kwargs = self._create_kwargs(messages, request_config, base_kwargs)
                    if structured:
                        structured_client = self._get_structured_client(request_config)
                        result, raw_response = structured_client.create_with_completion(
                            response_model=response_model,
                            max_retries=2,
                            **create_kwargs,
                        )
                        usage = self._usage_to_dict(_read_attr_or_key(raw_response, "usage"))
                        response_state = self._build_response_state(
                            request_config,
                            raw_response,
                            fallback_used=index > 0,
                            fallback_reason=fallback_reason,
                        )
                        return result, usage, response_state

                    response = self.completion_fn(**create_kwargs)
                    content, usage = self._extract_content_and_usage(response)
                    response_state = self._build_response_state(
                        request_config,
                        response,
                        fallback_used=index > 0,
                        fallback_reason=fallback_reason,
                    )
                    return content, usage, response_state
                except Exception as e:
                    error_msg = str(e).lower()
                    is_rate_limit = any(keyword in error_msg for keyword in ["rate limit", "too many requests", "429"])
                    is_thinking_fallback = (
                        index == 0
                        and request_config["thinking_applied"]
                        and self._is_thinking_unsupported_error(str(e))
                    )

                    if structured and response_model is not None and not is_rate_limit and not is_thinking_fallback:
                        try:
                            recovered_result, recovered_usage, recovered_state = self._recover_structured_result_from_error_message(
                                response_model,
                                request_config,
                                str(e),
                                fallback_used=index > 0,
                                fallback_reason=fallback_reason,
                            )
                            logger.warning(
                                "结构化解析失败后，已从异常信息恢复 JSON 结果: provider=%s, model=%s, error=%s",
                                self.provider,
                                request_config["effective_model"],
                                str(e),
                            )
                            return recovered_result, recovered_usage, recovered_state
                        except Exception:
                            pass

                        try:
                            recovered_result, recovered_usage, recovered_state = self._recover_structured_result_from_raw(
                                create_kwargs,
                                response_model,
                                request_config,
                                fallback_used=index > 0,
                                fallback_reason=fallback_reason,
                            )
                            logger.warning(
                                "结构化解析失败后，已通过原始响应恢复 JSON 结果: provider=%s, model=%s, error=%s",
                                self.provider,
                                request_config["effective_model"],
                                str(e),
                            )
                            return recovered_result, recovered_usage, recovered_state
                        except Exception as recovery_error:
                            logger.warning(
                                "结构化解析失败后的原始响应恢复也失败: provider=%s, model=%s, error=%s",
                                self.provider,
                                request_config["effective_model"],
                                str(recovery_error),
                            )
                            raise e

                    if is_thinking_fallback:
                        fallback_reason = str(e)
                        logger.warning(
                            "提供商 %s/%s 不支持当前思考模式配置，将回退到普通模式: %s",
                            self.provider,
                            request_config["effective_model"],
                            str(e),
                        )
                        break

                    if attempt < max_retries - 1:
                        wait_time = (backoff_factor ** attempt) + random.uniform(0, 1)
                        if is_rate_limit:
                            wait_time += 5
                        logger.warning(
                            "AI API调用失败 (尝试 %s/%s): %s。将在 %.1fs 后重试...",
                            attempt + 1,
                            max_retries,
                            str(e),
                            wait_time,
                        )
                        time.sleep(wait_time)
                    else:
                        raise Exception(f"AI API调用在 {max_retries} 次尝试后仍然失败 ({self.provider}): {str(e)}")


ai_client = AIClient(AI_PROVIDER, AI_MODEL)
analysis_cleanup_client = None
if ANALYSIS_CLEANUP_ENABLED:
    try:
        analysis_cleanup_client = AIClient(ANALYSIS_CLEANUP_PROVIDER, ANALYSIS_CLEANUP_MODEL)
    except Exception as e:
        logger.warning("分析 cleanup 客户端初始化失败，将禁用 cleanup: %s", str(e))


def get_analysis_cleanup_request_config():
    config = {
        "cleanup_requested": bool(ANALYSIS_CLEANUP_ENABLED and analysis_cleanup_client is not None),
        "cleanup_attempted": False,
        "cleanup_applied": False,
        "cleanup_provider": "",
        "cleanup_effective_model": "",
        "cleanup_thinking_requested": bool(ANALYSIS_CLEANUP_THINKING_MODE),
        "cleanup_thinking_applied": False,
        "cleanup_budget": None,
        "cleanup_effort": None,
        "cleanup_fallback_used": False,
        "cleanup_reasoning_content_present": False,
        "cleanup_structured_validated": False,
    }
    if not config["cleanup_requested"]:
        return config

    request_config = analysis_cleanup_client.get_analysis_request_config(thinking_mode=ANALYSIS_CLEANUP_THINKING_MODE)
    config.update(
        {
            "cleanup_provider": request_config["provider"],
            "cleanup_effective_model": request_config["effective_model"],
            "cleanup_thinking_requested": request_config["thinking_requested"],
            "cleanup_thinking_applied": request_config["thinking_applied"],
            "cleanup_budget": request_config["thinking_budget"],
            "cleanup_effort": request_config["thinking_effort"],
        }
    )
    return config

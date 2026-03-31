# config.py - 配置文件

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

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
CUSTOM_API_BASE = os.getenv("CUSTOM_API_BASE")
CUSTOM_API_KEY = os.getenv("CUSTOM_API_KEY")
AI_PROVIDER = os.getenv("AI_PROVIDER", "qwen")
AI_MODEL = os.getenv("AI_MODEL", "qwen-turbo")
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
    "涡度"
]

default_secondary_topics = [
    "色散偏微分方程的数学理论",
    "双曲偏微分方程的数学理论", 
    "调和分析",
    "极大算子",
    "椭圆偏微分方程",
    "抛物偏微分方程"
]

PRIORITY_TOPICS = os.getenv("PRIORITY_TOPICS", "|".join(default_priority_topics)).split("|")
SECONDARY_TOPICS = os.getenv("SECONDARY_TOPICS", "|".join(default_secondary_topics)).split("|")

PRIORITY_ANALYSIS_DELAY = int(os.getenv("PRIORITY_ANALYSIS_DELAY", "3"))
SECONDARY_ANALYSIS_DELAY = int(os.getenv("SECONDARY_ANALYSIS_DELAY", "2"))
MAX_THREADS = int(os.getenv("MAX_THREADS", "5"))

EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "ArXiv论文分析报告")

PROVIDER_CONFIG = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": DEEPSEEK_API_KEY,
        "thinking_support": "native",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "api_key": OPENAI_API_KEY,
        "thinking_support": "native",
    },
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/paas/v4/",
        "api_key": GLM_API_KEY,
        "thinking_support": "none",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": QWEN_API_KEY,
        "thinking_support": "enable_thinking",
    },
    "doubao": {
        "base_url": DOUBAO_API_BASE or "https://ark.cn-beijing.volces.com/api/v3",
        "api_key": DOUBAO_API_KEY,
        "thinking_support": "none",
    },
    "kimi": {
        "base_url": KIMI_API_BASE or "https://api.moonshot.cn/v1",
        "api_key": KIMI_API_KEY,
        "thinking_support": "native",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": OPENROUTER_API_KEY,
        "thinking_support": "none",
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": SILICONFLOW_API_KEY,
        "thinking_support": "none",
    },
    "custom": {
        "base_url": CUSTOM_API_BASE,
        "api_key": CUSTOM_API_KEY,
        "thinking_support": "none",
    },
}


class AIClient:
    """通用AI客户端，支持多个AI提供商和 thinking mode"""
    
    def __init__(self, provider=None, model=None):
        from openai import OpenAI
        
        self.provider = provider or AI_PROVIDER
        self.model = model or AI_MODEL
        
        if self.provider not in PROVIDER_CONFIG:
            raise ValueError(f"不支持的AI提供商: {self.provider}")
        
        config = PROVIDER_CONFIG[self.provider]
        self.thinking_support = config["thinking_support"]
        
        self.client = OpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
        )
    
    def chat_completion(self, messages, thinking_mode=False, **kwargs):
        """统一的聊天完成接口，包含失败重试机制"""
        content, _ = self._do_chat_completion(messages, thinking_mode=thinking_mode, **kwargs)
        return content
    
    def chat_completion_with_usage(self, messages, thinking_mode=False, **kwargs):
        """统一的聊天完成接口，返回内容和用量统计"""
        return self._do_chat_completion(messages, thinking_mode=thinking_mode, **kwargs)
    
    def _do_chat_completion(self, messages, thinking_mode=False, **kwargs):
        """内部实现：统一的聊天完成接口，包含失败重试机制"""
        import time
        import random
        
        max_retries = 3
        backoff_factor = 2
        
        extra_body = kwargs.pop("extra_body", None) or {}
        
        if thinking_mode and self.thinking_support == "enable_thinking":
            extra_body["enable_thinking"] = True
            logger.info(f"启用 thinking mode (enable_thinking=True) for {self.provider}")
        elif thinking_mode and self.thinking_support == "native":
            logger.info(f"启用 thinking mode (native) for {self.provider}/{self.model}")
        elif thinking_mode:
            logger.warning(f"提供商 {self.provider} 不支持 thinking mode，将使用普通模式")
        
        for attempt in range(max_retries):
            try:
                create_kwargs = {
                    "model": self.model,
                    "messages": messages,
                    **kwargs
                }
                if extra_body:
                    create_kwargs["extra_body"] = extra_body
                
                response = self.client.chat.completions.create(**create_kwargs)
                
                content = response.choices[0].message.content
                usage = {}
                if response.usage:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens or 0,
                        "completion_tokens": response.usage.completion_tokens or 0,
                        "total_tokens": response.usage.total_tokens or 0,
                    }
                return content, usage
            except Exception as e:
                error_msg = str(e).lower()
                is_rate_limit = any(keyword in error_msg for keyword in ["rate limit", "too many requests", "429"])
                
                if attempt < max_retries - 1:
                    wait_time = (backoff_factor ** attempt) + random.uniform(0, 1)
                    if is_rate_limit:
                        wait_time += 5
                    
                    logger.warning(f"AI API调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}。将在 {wait_time:.1f}s 后重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"AI API调用在 {max_retries} 次尝试后仍然失败 ({self.provider}): {str(e)}")


ai_client = AIClient(AI_PROVIDER, AI_MODEL)

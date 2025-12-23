# config.py - 配置文件

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置
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
# AI模型配置
AI_PROVIDER = os.getenv("AI_PROVIDER", "qwen")  # 支持: deepseek, openai, glm, custom, openrouter, siliconflow
AI_MODEL = os.getenv("AI_MODEL", "qwen-turbo")  # 模型名称
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")
# 支持多个收件人邮箱，用逗号分隔
EMAIL_TO = [email.strip() for email in os.getenv("EMAIL_TO", "").split(",") if email.strip()]

PAPERS_DIR = Path("./papers")
RESULTS_DIR = Path("./results")

# 从环境变量读取配置，如果没有则使用默认值
CATEGORIES = [cat.strip() for cat in os.getenv("ARXIV_CATEGORIES", "math.AP").split(",") if cat.strip()]
MAX_PAPERS = int(os.getenv("MAX_PAPERS", "50"))
SEARCH_DAYS = int(os.getenv("SEARCH_DAYS", "3"))

# 主题过滤列表从环境变量读取
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

# 从环境变量读取主题列表，使用 | 分隔
PRIORITY_TOPICS = os.getenv("PRIORITY_TOPICS", "|".join(default_priority_topics)).split("|")
SECONDARY_TOPICS = os.getenv("SECONDARY_TOPICS", "|".join(default_secondary_topics)).split("|")

# API调用延时配置
PRIORITY_ANALYSIS_DELAY = int(os.getenv("PRIORITY_ANALYSIS_DELAY", "3"))  # 重点论文分析延时（秒）
SECONDARY_ANALYSIS_DELAY = int(os.getenv("SECONDARY_ANALYSIS_DELAY", "2"))  # 摘要翻译延时（秒）
MAX_THREADS = int(os.getenv("MAX_THREADS", "5"))  # 最大线程数

# 邮件配置
EMAIL_SUBJECT_PREFIX = os.getenv("EMAIL_SUBJECT_PREFIX", "ArXiv论文分析报告")


class AIClient:
    """通用AI客户端，支持多个AI提供商"""
    
    def __init__(self, provider=None, model=None):
        self.provider = provider or AI_PROVIDER
        self.model = model or AI_MODEL
        
        if self.provider == "deepseek":
            import openai
            openai.api_key = DEEPSEEK_API_KEY
            openai.api_base = "https://api.deepseek.com/v1"
            self.client = openai
        elif self.provider == "openai":
            import openai
            openai.api_key = OPENAI_API_KEY
            openai.api_base = "https://api.openai.com/v1"
            self.client = openai
        elif self.provider == "glm":
            import openai
            openai.api_key = GLM_API_KEY
            openai.api_base = "https://open.bigmodel.cn/api/paas/v4/"
            self.client = openai
        elif self.provider == "qwen":
            import openai
            openai.api_key = QWEN_API_KEY
            openai.api_base = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            self.client = openai
        elif self.provider == "doubao":
            import openai
            openai.api_key = DOUBAO_API_KEY
            openai.api_base = DOUBAO_API_BASE or "https://ark.cn-beijing.volces.com/api/v3"
            self.client = openai
        elif self.provider == "kimi":
            import openai
            openai.api_key = KIMI_API_KEY
            openai.api_base = KIMI_API_BASE or "https://api.moonshot.cn/v1"
            self.client = openai
        elif self.provider == "openrouter":
            import openai
            openai.api_key = OPENROUTER_API_KEY
            openai.api_base = "https://openrouter.ai/api/v1"
            self.client = openai
        elif self.provider == "siliconflow":
            import openai
            openai.api_key = SILICONFLOW_API_KEY
            openai.api_base = "https://api.siliconflow.cn/v1"
            self.client = openai
        elif self.provider == "custom":
            import openai
            openai.api_key = CUSTOM_API_KEY
            openai.api_base = CUSTOM_API_BASE
            self.client = openai
        else:
            raise ValueError(f"不支持的AI提供商: {self.provider}")
    
    def chat_completion(self, messages, **kwargs):
        """统一的聊天完成接口，包含失败重试机制"""
        import time
        import random
        
        max_retries = 3
        backoff_factor = 2
        
        for attempt in range(max_retries):
            try:
                response = self.client.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    **kwargs
                )
                return response.choices[0].message.content
            except Exception as e:
                error_msg = str(e).lower()
                # 检查是否是频率限制错误
                is_rate_limit = any(keyword in error_msg for keyword in ["rate limit", "too many requests", "429"])
                
                if attempt < max_retries - 1:
                    wait_time = (backoff_factor ** attempt) + random.uniform(0, 1)
                    if is_rate_limit:
                        wait_time += 5  # 频率限制时额外多等一会儿
                    
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"AI API调用失败 (尝试 {attempt + 1}/{max_retries}): {str(e)}。将在 {wait_time:.1f}s 后重试...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"AI API调用在 {max_retries} 次尝试后仍然失败 ({self.provider}): {str(e)}")


# 创建全局AI客户端实例
ai_client = AIClient(AI_PROVIDER, AI_MODEL)

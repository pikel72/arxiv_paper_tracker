#!/usr/bin/env python3
# 测试多AI模型支持

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

def test_ai_providers():
    """测试不同AI提供商的配置"""
    from config import AIClient

    providers = [
        ("deepseek", "deepseek-chat"),
        ("openai", "gpt-4"),
        ("glm", "glm-4"),
        ("qwen", "qwen-turbo")
    ]

    for provider, model in providers:
        try:
            client = AIClient(provider, model)
            print(f"✅ {provider}: {model} - 配置成功")
        except Exception as e:
            print(f"❌ {provider}: {model} - 配置失败: {e}")

if __name__ == "__main__":
    test_ai_providers()

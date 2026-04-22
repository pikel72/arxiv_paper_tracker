#!/usr/bin/env python3
# 测试多AI模型支持

import os
import sys
from contextlib import ExitStack
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_ai_providers():
    """测试不同AI提供商的配置"""
    from config import AIClient, PROVIDER_CONFIG

    providers = [
        ("deepseek", "deepseek-chat"),
        ("openai", "gpt-4"),
        ("glm", "glm-4"),
        ("qwen", "qwen-turbo"),
        ("nvidia_nim", "meta/llama-3.1-8b-instruct"),
    ]

    failures = []
    with ExitStack() as stack:
        for provider, _ in providers:
            stack.enter_context(patch.dict(PROVIDER_CONFIG[provider], {"api_key": "test-api-key"}, clear=False))

        for provider, model in providers:
            try:
                AIClient(provider, model)
            except Exception as e:
                failures.append((provider, model, str(e)))

    assert not failures


if __name__ == "__main__":
    test_ai_providers()

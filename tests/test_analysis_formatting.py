#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from analyzer import extract_analysis_title, render_analysis_body


def test_extract_and_render_old_heading_style():
    sample = """### 详细分析

# 具有传输噪声的Navier-Stokes方程在两板间的各向异性无粘性极限分析

## 详细分析

### 1. 研究对象和背景
背景内容

### 2. 主要定理或主要结果
结果内容

### 3. 研究方法、关键技术和核心工具
方法内容

### 4. 与之前工作的比较
比较内容
"""

    assert extract_analysis_title(sample, "fallback") == "具有传输噪声的Navier-Stokes方程在两板间的各向异性无粘性极限分析"
    rendered = render_analysis_body(sample)
    assert "### 1. 研究对象和背景" in rendered
    assert "背景内容" in rendered
    assert "### 4. 与之前工作的比较" in rendered


def test_extract_and_render_plain_title_style():
    sample = """### 详细分析

二维Euler方程中的普适小尺度产生

## 详细分析

### 1. 研究对象和背景
背景内容

### 2. 主要定理或主要结果
结果内容
"""

    assert extract_analysis_title(sample, "fallback") == "二维Euler方程中的普适小尺度产生"
    rendered = render_analysis_body(sample)
    assert rendered.startswith("### 1. 研究对象和背景")
    assert "### 3. 研究方法、关键技术和核心工具" in rendered
    assert "（模型未给出相关内容）" in rendered


if __name__ == "__main__":
    test_extract_and_render_old_heading_style()
    test_extract_and_render_plain_title_style()
    print("analysis formatting tests passed")

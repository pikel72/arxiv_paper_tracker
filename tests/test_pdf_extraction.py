#!/usr/bin/env python3
# 测试PDF文本提取功能

import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_pdf_extraction():
    """测试PDF文本提取功能"""
    from analyzer import extract_pdf_text
    
    # 查找papers目录下的PDF文件
    papers_dir = Path(__file__).parent.parent / "papers"
    if not papers_dir.exists():
        print("papers目录不存在，创建目录")
        papers_dir.mkdir(exist_ok=True)
        print("请先运行主程序下载一些PDF文件进行测试")
        return

    pdf_files = list(papers_dir.glob("*.pdf"))
    if not pdf_files:
        print("papers目录中没有PDF文件，请先运行主程序下载一些PDF文件")
        return

    # 测试第一个PDF文件
    test_pdf = pdf_files[0]
    print(f"测试PDF文件: {test_pdf}")

    try:
        text_content = extract_pdf_text(str(test_pdf), max_pages=5)
        print("✅ PDF文本提取成功!")
        print(f"提取的文本长度: {len(text_content)} 字符")
        print("文本预览（前500字符）:")
        print("-" * 50)
        print(text_content[:500])
        print("-" * 50)
    except Exception as e:
        print(f"❌ PDF文本提取失败: {e}")


if __name__ == "__main__":
    test_pdf_extraction()

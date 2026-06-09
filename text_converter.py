#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本转换模块
============

提供繁体字转简体字的转换功能
"""

import logging

try:
    import zhconv
    ZHCONV_AVAILABLE = True
    logging.info("zhconv库已加载，繁简转换功能可用")
except ImportError:
    ZHCONV_AVAILABLE = False
    logging.warning("zhconv库未安装，繁简转换功能不可用")

def convert_traditional_to_simplified(text: str) -> str:
    """
    将繁体中文转换为简体中文

    Args:
        text: 待转换的文本

    Returns:
        转换后的简体中文文本
    """
    if not text or not isinstance(text, str):
        return text

    if not ZHCONV_AVAILABLE:
        logging.debug("zhconv不可用，跳过繁简转换")
        return text

    try:
        # 使用zhconv进行繁体转简体
        simplified_text = zhconv.convert(text, 'zh-cn')

        # 记录转换情况（仅当有实际转换时）
        if simplified_text != text:
            logging.debug(f"繁简转换: {text[:30]}... -> {simplified_text[:30]}...")

        return simplified_text

    except Exception as e:
        logging.error(f"繁简转换失败: {e}")
        return text  # 转换失败时返回原文本

def test_conversion():
    """测试转换功能"""
    test_cases = [
        "快的更新來了本集標題對不起爸爸波妮的眼淚",
        "與大熊的拳頭,回憶繼續,不過這次是波尼在房間中看完",
        "大熊的記憶之後,都回憶。波咪在得知了全部的真相之後",
        "便回了小女孩的母样然后铺向了被家庞客波尼对被叫",
        "家庞客的誤會終於解開了接著,被家庞客拿出了雄服"
    ]

    print("=" * 60)
    print("繁简转换测试")
    print("=" * 60)

    for i, text in enumerate(test_cases, 1):
        simplified = convert_traditional_to_simplified(text)
        print(f"测试 {i}:")
        print(f"  原文: {text}")
        print(f"  转换: {simplified}")
        print(f"  是否转换: {'是' if text != simplified else '否'}")
        print("-" * 40)

if __name__ == "__main__":
    test_conversion()
# -*- coding: utf-8 -*-
"""风格提示词选择器（Style Prompt Selector）。

给「图片风格转换」这类工作流提供一个下拉选择框：
风格库放在 ComfyUI 根目录的 styles/ 文件夹里，一条风格 = 一个 .txt 文件。

WEB_DIRECTORY 让 web/ 下的 js 被前端加载（把选中风格的提示词自动填进文本框）。
"""

from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

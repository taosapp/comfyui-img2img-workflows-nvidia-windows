# -*- coding: utf-8 -*-
"""风格库读写 + 风格提示词选择器节点。

风格库位置：ComfyUI 根目录下的 styles/ 文件夹（可用环境变量 COMFYUI_STYLE_DIR 覆盖）
    文件名（去掉「01-」这类序号前缀）= 下拉框里显示的风格名
    文件内容                          = 该风格的提示词
例如： styles/01-水彩画.txt 、 styles/02-简笔画.txt

数字前缀只用来排序，不会出现在选择框里；文件名以 _ 或 . 开头的文件会被忽略
（所以可以放 _说明.txt）。

风格文件内容支持注释，读取时自动剔除（2026-09-28 新增）：
    行首（允许空白）的 # 或 // 整行忽略；/* ... */ 块注释跨行剔除。
    行中间的 # 不算注释（避免误伤 #ff0000 这类色值）。
    想临时停用某段提示词：把它单独放一行，行首加 # 即可。

风格文件支持负向提示词段（2026-09-29 新增）：
    文件里写一行 ---负向--- （或 ---NEGATIVE---），其后的内容作为该风格的
    负向提示词，从节点第二个输出送出；之前的所有内容仍是正向提示词。
    没写分隔符的文件，负向输出为空串。
"""

import logging
import os
import re

LOG = logging.getLogger("style-prompt")


def _comfy_root():
    # <root>/custom_nodes/comfyui-style-prompt/nodes.py  ->  <root>
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(here))


STYLE_DIR = os.environ.get("COMFYUI_STYLE_DIR") or os.path.join(_comfy_root(), "styles")
STYLE_EXTS = (".txt", ".md", ".prompt")
_ORDER_PREFIX = re.compile(r"^\s*\d+\s*[-_.、)）．\s]*\s*")
_ILLEGAL = re.compile(r'[\\/:*?"<>|\r\n\t]+')


def display_name(stem):
    """文件名去掉序号前缀 = 风格名。"""
    return _ORDER_PREFIX.sub("", stem).strip() or stem


def library_files():
    """返回风格库里的文件名（已排序、已过滤）。"""
    try:
        names = sorted(os.listdir(STYLE_DIR))
    except OSError:
        return []
    out = []
    for fn in names:
        stem, ext = os.path.splitext(fn)
        if ext.lower() not in STYLE_EXTS or fn.startswith((".", "_")):
            continue
        out.append(fn)
    return out


def strip_comments(text):
    """去掉风格文件里的注释（读取风格库时统一执行）。

    支持：
      - 整行注释：行首（允许空白）的 # 或 //
      - 块注释：/* ... */（可跨行，与 ComfyUI 前端动态提示词的注释语法一致）
    注意：行中间的 # 不算注释（避免误伤 #ff0000 这类色值），
    想临时停用某段提示词，把它单独放在一行、行首加 # 即可。
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    kept = [ln for ln in text.splitlines() if not re.match(r"^\s*(?:#|//)", ln)]
    return "\n".join(ln.strip() for ln in kept if ln.strip()).strip()


_NEG_SEP = re.compile(r"^\s*-{2,}\s*(?:负向|negative)\s*-{2,}\s*$", re.IGNORECASE)


def split_negative(text):
    """按 ---负向--- 分隔符把风格文本拆成 (正向, 负向)，各自剔除注释。"""
    pos, neg = [], []
    target = pos
    for ln in text.splitlines():
        if _NEG_SEP.match(ln):
            target = neg
            continue
        target.append(ln)
    return strip_comments("\n".join(pos)), strip_comments("\n".join(neg))


def load_styles():
    """读取整份风格库，返回 {风格名: (正向, 负向)}（顺序 = 文件名排序）。"""
    styles = {}
    for fn in library_files():
        path = os.path.join(STYLE_DIR, fn)
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            LOG.warning("[style-prompt] 读取失败 %s：%s", fn, exc)
            continue
        pos, neg = split_negative(text)
        if not pos and not neg:
            continue
        name = display_name(os.path.splitext(fn)[0])
        if name in styles:  # 重名时退回完整文件名，避免互相覆盖
            name = os.path.splitext(fn)[0]
        while name in styles:
            name += " "
        styles[name] = (pos, neg)
    return styles


def library_stamp():
    """风格库指纹：任何文件变动都会让 ComfyUI 重新执行节点（否则会命中缓存）。"""
    parts = []
    for fn in library_files():
        path = os.path.join(STYLE_DIR, fn)
        try:
            parts.append("%s:%d:%d" % (fn, os.path.getsize(path), int(os.path.getmtime(path))))
        except OSError:
            pass
    return "%d|%s" % (len(parts), ",".join(parts))


class StylePromptSelector:
    """下拉选风格 → 输出该风格的正向/负向提示词；文本框非空时以文本框为准（只覆盖正向）。"""

    @classmethod
    def INPUT_TYPES(cls):
        names = list(load_styles()) or ["(风格库为空)"]
        return {
            "required": {
                "style": (names, {"tooltip": "风格库 = ComfyUI\\styles 里的 *.txt，文件名即风格名"}),
                "prompt": ("STRING", {
                    "multiline": True,
                    "dynamicPrompts": False,
                    "default": "",
                    "tooltip": "留空 = 直接用该风格文件里的原文；在这里改动只影响本次运行，不会写回风格库",
                }),
            }
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "negative")
    FUNCTION = "select"
    CATEGORY = "style"

    def select(self, style, prompt):
        styles = load_styles()
        lib_pos, lib_neg = styles.get(style, ("", ""))
        text = (prompt or "").strip()
        if text:
            if text == lib_pos:
                LOG.info("[style-prompt] 风格「%s」→ 使用节点内文本（与库原文一致，%d 字符）", style, len(text))
            else:
                LOG.info("[style-prompt] 风格「%s」→ 节点内文本覆盖了库正向原文（%d 字符，库原文 %d 字符）",
                         style, len(text), len(lib_pos))
            pos = text
        else:
            pos = lib_pos
            if not pos and styles:
                fallback = next(iter(styles))
                LOG.warning("[style-prompt] 风格「%s」不在库里，改用「%s」", style, fallback)
                style = fallback
                pos, lib_neg = styles[fallback]
            if pos:
                LOG.info("[style-prompt] 风格「%s」→ 库内原文（%d 字符）：%s ...",
                         style, len(pos), pos[:60])
            else:
                LOG.warning("[style-prompt] 风格库为空：%s", STYLE_DIR)
        if lib_neg:
            LOG.info("[style-prompt] 风格「%s」→ 负向词（%d 字符）", style, len(lib_neg))
        return (pos, lib_neg)

    @classmethod
    def IS_CHANGED(cls, style, prompt):
        return "%s|%s|%s" % (library_stamp(), style, prompt)


class StylePromptSave:
    """把提示词写回风格库（默认不写，只透传；把 enabled 打开才落盘）。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "enabled": ("BOOLEAN", {"default": False, "label_on": "写入风格库",
                                        "label_off": "只透传不写"}),
                "style_name": ("STRING", {"default": "", "tooltip": "写入/覆盖的风格名；库里已有同名文件就覆盖它"}),
                "prompt": ("STRING", {"multiline": True, "default": "", "dynamicPrompts": False}),
            },
            "optional": {
                "text": ("STRING", {"forceInput": True, "tooltip": "接了上游就用上游的文本（例如选择器的输出）"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "save"
    CATEGORY = "style"
    OUTPUT_NODE = True

    def save(self, enabled, style_name, prompt, text=None):
        value = text if text is not None else prompt
        value = value or ""
        if not enabled:
            LOG.info("[style-prompt] 存库节点未启用，透传（%d 字符）", len(value))
            return (value,)
        name = (style_name or "").strip()
        if not name:
            LOG.warning("[style-prompt] 未填风格名，跳过写入")
            return (value,)
        try:
            path = self._write(name, value)
            LOG.info("[style-prompt] 已写入风格库：%s", path)
        except OSError as exc:
            LOG.error("[style-prompt] 写入风格库失败：%s", exc)
        return (value,)

    @staticmethod
    def _write(name, text):
        os.makedirs(STYLE_DIR, exist_ok=True)
        target = None
        for fn in library_files():
            if display_name(os.path.splitext(fn)[0]) == name:
                target = os.path.join(STYLE_DIR, fn)
                break
        if target is None:
            prefix = 0
            for fn in library_files():
                m = re.match(r"^\s*(\d+)", fn)
                if m:
                    prefix = max(prefix, int(m.group(1)))
            target = os.path.join(STYLE_DIR, "%02d-%s.txt" % (prefix + 1, _ILLEGAL.sub("_", name)))
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(text.strip() + "\n")
        return target


NODE_CLASS_MAPPINGS = {
    "StylePromptSelector": StylePromptSelector,
    "StylePromptSave": StylePromptSave,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "StylePromptSelector": "风格提示词选择器（下拉）",
    "StylePromptSave": "风格提示词存回库",
}


def _styles_route(request):
    from aiohttp import web
    styles = load_styles()
    return web.json_response({
        "styles": {k: v[0] for k, v in styles.items()},
        "negatives": {k: v[1] for k, v in styles.items()},
        "dir": STYLE_DIR,
    })


def _register_routes():
    """把风格库暴露给前端 js（拉取提示词用来自动填充文本框）。"""
    try:
        from server import PromptServer
        inst = getattr(PromptServer, "instance", None)
        if inst is None:
            return
        inst.routes.get("/style_prompt/styles")(_styles_route)
        LOG.info("[style-prompt] 风格库已就绪：%s（%d 条）", STYLE_DIR, len(library_files()))
    except Exception as exc:  # 单独 import 本模块做测试时不带 server 也能用
        LOG.debug("[style-prompt] 未注册 HTTP 路由：%s", exc)


_register_routes()

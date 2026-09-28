// 风格提示词选择器（前端辅助）
// 作用：选中某个风格时，自动把该风格的提示词填进节点下面的文本框，方便直接查看和微调。
// 说明：这只是「省事」用的 —— 就算这段 js 没加载，节点照样能用（文本框留空 = 用风格库原文）。
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_CLASS = "StylePromptSelector";
const ROUTE = "/style_prompt/styles";

let LIB = null; // 缓存风格库 { 风格名: 提示词 }

async function library(force) {
  if (LIB && !force) return LIB;
  try {
    const res = await api.fetchApi(ROUTE, { cache: "no-store" });
    LIB = await res.json();
  } catch (err) {
    console.warn("[style-prompt] 读取风格库失败", err);
    LIB = { styles: {} };
  }
  return LIB;
}

function writeWidget(widget, text) {
  if (!widget) return;
  widget.value = text;
  // 多行文本在界面上是 DOM 控件，要连底层元素一起改，否则框里看不到变化
  if (widget.inputEl) widget.inputEl.value = text;
  else if (widget.element && "value" in widget.element) widget.element.value = text;
}

app.registerExtension({
  name: "comfyui.styleprompt.selector",
  async nodeCreated(node) {
    const cls = node.comfyClass || node.type;
    if (cls !== NODE_CLASS) return;

    const styleW = node.widgets?.find((w) => w.name === "style");
    const promptW = node.widgets?.find((w) => w.name === "prompt");
    if (!styleW || !promptW) return;

    // force=true：换风格时用新风格原文覆盖文本框
    // force=false：只在文本框为空时填充（保留工作流里已保存的文本）
    const sync = async (force) => {
      const lib = await library(false);
      const text = (lib.styles || {})[styleW.value];
      if (typeof text !== "string" || !text) return;
      if (force || !String(promptW.value ?? "").trim()) {
        writeWidget(promptW, text);
        node.setDirtyCanvas?.(true, true);
      }
    };

    // 换风格：覆盖文本框
    const originalCallback = styleW.callback;
    styleW.callback = function (value, ...rest) {
      const out = originalCallback ? originalCallback.call(this, value, ...rest) : undefined;
      sync(true);
      return out;
    };

    // 打开工作流：控件值恢复完后再回填（nodeCreated 早于 configure，所以必须挂这里）
    const originalOnConfigure = node.onConfigure;
    node.onConfigure = function (...args) {
      const out = typeof originalOnConfigure === "function" ? originalOnConfigure.apply(this, args) : undefined;
      sync(false);
      return out;
    };

    // 右键菜单：一键拉回风格库原文（新增 / 改名风格文件后，下拉选项要刷新页面才更新）
    const originalMenu = node.getExtraMenuOptions;
    node.getExtraMenuOptions = function () {
      const options = arguments[1];
      if (typeof originalMenu === "function") originalMenu.apply(this, arguments);
      if (Array.isArray(options)) {
        options.push({
          content: "重新载入风格库原文",
          callback: async () => {
            LIB = null;
            await sync(true);
          },
        });
      }
    };

    await sync(false);
  },
});

#!/usr/bin/env bash
# ComfyUI 启动脚本（macOS / Linux）
#
# 与 Windows 的 start_comfyui.bat 等价，但：
#   · 路径全部自动推导，不写死用户名和盘符（拷到任何目录都能跑）
#   · Apple Silicon 自动设 PYTORCH_ENABLE_MPS_FALLBACK，避免 MPS 不支持的算子直接崩
#   · 不加 --lowvram（MPS 下统一内存，这个参数是反效果）
#
# 用法：
#   chmod +x start_comfyui_mac.sh     # 从 Windows 拷过来后要补执行位
#   ./start_comfyui_mac.sh            # 启动
#   ./start_comfyui_mac.sh --lowvram  # 想自己加参数就往后接
#   ./start_comfyui_mac.sh --cpu      # 只验证节点、不加载模型（排查用）

set -e
cd "$(dirname "$0")"

# ---- 1. 找解释器：优先项目自带的虚拟环境，其次系统 python3 ----
PY=""
for cand in "venv/bin/python" ".venv/bin/python" "env/bin/python"; do
    if [ -x "$cand" ]; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    PY="$(command -v python3 || command -v python || true)"
fi
if [ -z "$PY" ]; then
    echo "[x] 找不到 python。请先：python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# ---- 2. 环境变量 ----
# 国内网络走 HF 镜像（想用官方源就 HF_ENDPOINT=https://huggingface.co ./start_comfyui_mac.sh）
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
# Apple Silicon：让 MPS 不支持的算子回落到 CPU，而不是直接报错
if [ "$(uname -s)" = "Darwin" ]; then
    export PYTORCH_ENABLE_MPS_FALLBACK=1
fi
# 本机代理常把 127.0.0.1 也劫持走，访问本地服务时记得绕开
export NO_PROXY="${NO_PROXY:-127.0.0.1,localhost}"

# ---- 3. 打印环境摘要 ----
echo "============================================"
echo "  ComfyUI 启动（macOS / Linux）"
echo "============================================"
echo "  目录   : $(pwd)"
echo "  解释器 : $PY"
"$PY" - <<'EOF' || true
import platform, sys
print("  Python :", sys.version.split()[0], "|", platform.system(), platform.machine())
try:
    import torch
    line = "  torch  : %s" % torch.__version__
    if hasattr(torch.backends, "mps"):
        line += " | MPS 可用: %s" % torch.backends.mps.is_available()
    if torch.cuda.is_available():
        line += " | CUDA: %s (%s)" % (torch.version.cuda, torch.cuda.get_device_name(0))
    print(line)
except Exception as exc:
    print("  [!] torch 导入失败：%r" % (exc,))
    print("      先确认装好了依赖：source venv/bin/activate && pip install -r requirements.txt")
EOF
echo "  地址   : http://127.0.0.1:8188"
echo "  Ctrl+C 停止"
echo

# ---- 4. 启动 ----
exec "$PY" main.py "$@"

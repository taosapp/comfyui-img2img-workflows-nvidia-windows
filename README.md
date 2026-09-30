# ComfyUI 图生图工作流集（NVIDIA / Windows）

一套在 **NVIDIA 消费级显卡（8-12GB 显存）+ Windows** 上实测可用的 ComfyUI 图片工作流，
围绕 **Qwen-Image-2.1（GGUF 量化）图生图** 构建，包含：

| 工作流 | 用途 | 速度（RTX 3060 12GB 实测） |
|---|---|---|
| `workflows/图片风格转换.json` | 通用图生图风格转换，下拉框切换风格库（水彩/简笔画/高清增强等） | 约 4-6 分钟/张（1152×864） |
| `workflows/抠图.json` | 透明底抠图（BiRefNet 专用分割模型，不改像素） | 约 3 秒/张 |
| `workflows/产品图层拆分.json` | 产品海报拆成 主体/文字/背景 三层（SAM3 文本提示分割） | 约 1 分钟/张 |
| `workflows/文生图.json` | Qwen-Image-2.1 文生图（GGUF + KV 缓存加速） | 待实测 |
| `workflows/分层文生图.json` | Qwen-Image-Layered 一次生成分层图（文字直接生成多层，LatentCut 切层输出） | 待实测 |

配套一个自建小节点包 `custom_nodes/comfyui-style-prompt/`（风格库下拉选择器 + 存回节点 + 背景填充节点），
以及一份 ComfyUI-GGUF 补丁（见 `patches/`）。

> 全部内容在 RTX 3060 12GB + 32GB 内存、Windows、`--lowvram` 启动下实测通过；
> 8GB 显存 / 16GB 内存的机器也能跑图片工作流（见下方「硬件要求」）。

## 工作流简介

### 图片风格转换
`LoadImage → 风格选择器(下拉) → TextEncodeQwenImage21 → KSampler → VAEDecode → SaveImage`，
中间串了一个 `QwenImage21Cache`（KV 缓存，同样提示词连续出图时可省 40% 时间，勿删）。

风格 = `styles/` 目录下一个 `.txt` 文件，文件名（去掉序号）就是下拉框里的名字。
**新增风格只要丢一个 txt 进去、浏览器 F5 即可**；改内容直接重新 Queue。
风格文件支持 `#` 注释（详见 `styles/_说明.txt`）。

### 抠图
核心节点 `LoadBackgroundRemovalModel + RemoveBackground`（BiRefNet，Swin-L 版），
输出与输入同尺寸的透明 PNG。注意链路中必须过一次 `InvertMask`
（`JoinImageWithAlpha` 内部做 `alpha = 1 - mask`），`GrowMask` 放在反相前用于去白边。

### 产品图层拆分
一张产品海报 → **主体 / 文字 / 背景三层**，用 SAM3 的文本提示分割
（`smartphone:2`、`text:30` 这类 `词:实例数` 语法，模型放 `models/checkpoints/`，用
`CheckpointLoaderSimple` 加载）。关键掩膜运算：**文字掩膜 − 主体外扩 = 纯文字**
（机身印字不会被误检）；背景层由自建节点 `BackgroundFillSmooth` 补全
（逐行水平插值延续结构 + 轻扩散 + 匹配噪点），**不跑生图大模型**，
被产品重新合成回去时中心区本就会被盖住，边界延续才是质量关键。

## 安装

1. 安装 [ComfyUI](https://github.com/comfyanonymous/ComfyUI)（本仓库工作流基于 0.37.0 实测）；
2. 安装第三方节点 [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF)：
   ```bash
   git clone https://github.com/city96/ComfyUI-GGUF custom_nodes/ComfyUI-GGUF
   pip install -r custom_nodes/ComfyUI-GGUF/requirements.txt
   ```
3. **给 ComfyUI-GGUF 打补丁**（重要）：
   `qwen-image-2.1-Q5_K_M.gguf` 没有架构元数据，加载器只能从张量名反推架构，
   原版 ComfyUI-GGUF 不认识它、会报 `Unknown model architecture!`。
   打法见 `patches/README.md`（基线：city96/ComfyUI-GGUF @ `6ea2651e`）；
4. 把 `custom_nodes/comfyui-style-prompt/` 拷进你的 `custom_nodes/`，重启 ComfyUI；
5. 把 `workflows/`、`styles/` 放到 ComfyUI 根目录同名文件夹下；
6. 按下表下载模型（**模型不随仓库分发，请自行获取**）。

## 模型清单（图片工作流部分）

| 文件 | 大小 | 放置目录 | 来源 |
|---|---|---|---|
| `qwen-image-2.1-Q5_K_M.gguf` | 4.9 GB | `models/diffusion_models/` | [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1) 官方权重的 GGUF 量化版（[Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1)、unsloth 等社区仓库有量化版） |
| `qwen3vl_8b_int8_convrot.safetensors` | 8.7 GB | `models/text_encoders/` | 基于 [Qwen/Qwen3-VL-8B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct) 的 int8 convrot 量化版（ComfyUI 社区量化）；也可用官方 BF16 |
| `qwen_image_2.1_vae_bf16.safetensors` | 0.63 GB | `models/vae/` | [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1) |
| `birefnet.safetensors`（仅抠图用） | 0.42 GB | `models/background_removal/` | [Comfy-Org/BiRefNet](https://huggingface.co/Comfy-Org/BiRefNet)（MIT） |
| `sam3.1_multiplex_fp16.safetensors`（仅图层拆分用） | 1.7 GB | `models/checkpoints/` | [Comfy-Org/sam3.1](https://huggingface.co/Comfy-Org/sam3.1) |

- 合计约 **14.7 GB**；国内网络可用 [hf-mirror.com](https://hf-mirror.com) 镜像下载；
- **文件名必须一字不差**：工作流按文件名找模型；
- 各模型许可证不同（Qwen 系列为 Apache-2.0 / Qwen Research，请自行确认你的用途是否合规）。

## 硬件要求（实测）

| 配置 | 结论 |
|---|---|
| RTX 3060 12GB + 32GB 内存 | 全部工作流实测可用，启动参数 `--lowvram` |
| RTX 4060 8GB + 16GB 内存 | 图片工作流可跑：8GB 显存需更多内存换入换出（更慢），**16GB 内存必须把页面文件设到 24-32GB（SSD）**，预计比 12GB 卡慢 1.5-3 倍 |

启动示例（Windows）：

```bat
python main.py --lowvram --preview-method auto
```

## 目录结构

```
├── workflows/                      # 五个工作流（浏览器直接打开）
├── styles/                         # 风格库：一个 txt = 一种风格，支持 # 注释
├── custom_nodes/comfyui-style-prompt/   # 自建节点：风格下拉选择器 + 存回节点
└── patches/                        # ComfyUI-GGUF 的 Qwen-Image 架构补丁
```

## 免责声明

本项目只包含工作流与代码，不含任何模型权重与图片素材。模型的使用请遵守各自许可证；
生成内容（尤其是人物风格化）请遵守当地法律法规，不要用于伪造他人身份等用途。

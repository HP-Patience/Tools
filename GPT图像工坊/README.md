# GPT 图像工坊

一个轻量的本地 AI 绘图 Web 工具：输入 Prompt，选择模型和生成数量，即可通过兼容 OpenAI Images API 的服务生成图片，并自动保存到本地 `output/` 目录。

## 功能特点

- FastAPI + 原生前端，启动简单。
- 支持配置兼容 OpenAI API 的图片生成接口地址和 API Key。
- 支持模型列表拉取、单张/多张图片生成。
- 支持上传图片并调用图片编辑接口生成修改结果。
- 支持在本地标注工作台里对图片画框、画圈、画箭头、手绘和添加文字说明，再合成 PNG 回填到主页编辑图片。
- 生成结果会保存为图片文件，便于后续整理和复用。

## 目录结构

```text
.
├── app.py              # FastAPI Web 服务
├── image_gen.py        # OpenAI 兼容图片生成客户端
├── static/index.html   # 前端页面
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量示例
└── test_requests.py    # 接口测试脚本
```

## 快速开始

```bash
cd GPT图像工坊
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

编辑 `.env`，填入你的接口地址和 API Key：

```env
IMAGE_API_BASE_URL="https://example.com/v1"
IMAGE_API_KEY="你的 API Key"
```

启动服务：

```bash
python app.py
```

浏览器打开：

```text
http://127.0.0.1:8000
```

也可以在页面顶部的配置区直接保存 API 地址和 API Key。

## 图片编辑

在提示词下方上传一张 PNG/JPEG/WEBP 图片，填写编辑要求后点击“按上图编辑”。“生成新图”是纯文字生成，不会读取已选择的图片；只有“按上图编辑”会调用上游 `/images/edits` 并把图片作为 multipart `image` 字段上传，结果同样保存到本地 `output/`。

## 图片标注工作台

选择本地图片后，页面会立即显示预览。点击预览、生成结果图或编辑结果图，可以打开图片工作台。在工作台里可以用矩形、圆形、箭头、画笔和文字对图片进行标注，并在右侧为每个标注填写说明。

点击工作台里的“保存”时，前端会把标注直接合成为一张 PNG，并把主页的“编辑图片”预览替换成这张标注图；标注说明会追加到 Prompt 中。随后手动点击主页“按上图编辑”才会提交给本地 `/api/edit`。后端仍然只向上游图片编辑接口发送 `model`、`prompt` 和 `image`，以兼容 ChatGPT 账号反向代理类上游。AI 返回结果会保存为 `output/edited_*.png`。

## 注意事项

- `.env`、`output/`、运行日志和虚拟环境不会提交到仓库。
- 如果使用自签名证书的内部服务，当前客户端默认关闭了 TLS 校验；如需用于公网或生产环境，建议改为启用证书校验。
- 对 ChatGPT 账号反向代理类上游，GPT Image 2 请求默认只发送 `model` 和 `prompt`；多图通过后端循环单张请求实现。
- `grok-imagine-image` 当前在前端限制为每次 1 张。

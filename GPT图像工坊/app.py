"""图片生成 Web 服务 - FastAPI"""
from __future__ import annotations

import base64
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import requests
from dotenv import set_key
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import image_gen

app = FastAPI(title="Prompt → Image")
BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
OUTPUT_DIR.mkdir(exist_ok=True)
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


class GenRequest(BaseModel):
    prompt: str
    model: str = "gpt-image-2"
    n: int = 1


class ImageItem(BaseModel):
    b64: str
    data_url: str
    file_path: str
    file_url: str


class GenResponse(BaseModel):
    b64: str
    data_url: str
    images: List[ImageItem]
    model: str
    annotated_image: Optional[ImageItem] = None


class ApiConfig(BaseModel):
    base_url: str
    api_key: str


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config", response_model=ApiConfig)
def get_api_config():
    return image_gen.get_config()


@app.put("/api/config", response_model=ApiConfig)
def save_api_config(config: ApiConfig):
    base_url = config.base_url.strip().rstrip("/")
    api_key = config.api_key.strip()
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(400, "API 地址必须是有效的 http 或 https URL")
    if not api_key:
        raise HTTPException(400, "API Key 不能为空")

    image_gen.ENV_FILE.touch(exist_ok=True)
    set_key(str(image_gen.ENV_FILE), "IMAGE_API_BASE_URL", base_url)
    set_key(str(image_gen.ENV_FILE), "IMAGE_API_KEY", api_key)
    os.environ["IMAGE_API_BASE_URL"] = base_url
    os.environ["IMAGE_API_KEY"] = api_key
    return {"base_url": base_url, "api_key": api_key}


@app.get("/api/models")
def models():
    try:
        return {"models": image_gen.list_models()}
    except Exception as e:
        raise HTTPException(502, f"无法获取模型列表: {e}")


def _image_format(raw: bytes) -> tuple[str, str]:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpg", "image/jpeg"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "webp", "image/webp"
    raise ValueError("上游返回了不支持的图片格式")


def _save_b64_images(b64_list: list[str], prefix: str) -> list[ImageItem]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    images = []
    for index, b64 in enumerate(b64_list, start=1):
        raw = base64.b64decode(b64, validate=True)
        extension, mime_type = _image_format(raw)
        filename = f"{prefix}_{timestamp}_{index}.{extension}"
        output_path = OUTPUT_DIR / filename
        output_path.write_bytes(raw)
        images.append(ImageItem(
            b64=b64,
            data_url=f"data:{mime_type};base64,{b64}",
            file_path=f"output/{filename}",
            file_url=f"/output/{filename}",
        ))
    return images


def _save_raw_image(raw: bytes, prefix: str) -> ImageItem:
    extension, mime_type = _image_format(raw)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}_{timestamp}.{extension}"
    output_path = OUTPUT_DIR / filename
    output_path.write_bytes(raw)
    b64 = base64.b64encode(raw).decode("ascii")
    return ImageItem(
        b64=b64,
        data_url=f"data:{mime_type};base64,{b64}",
        file_path=f"output/{filename}",
        file_url=f"/output/{filename}",
    )


@app.post("/api/generate", response_model=GenResponse)
def generate(req: GenRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "prompt 不能为空")
    if not 1 <= req.n <= 4:
        raise HTTPException(400, "n 必须在 1 到 4 之间")
    try:
        b64_list = image_gen.generate_images_b64(
            prompt=req.prompt,
            model=req.model,
            n=req.n,
        )
    except requests.Timeout:
        raise HTTPException(504, "生成超时（>180s），请重试")
    except requests.HTTPError as e:
        raise HTTPException(502, f"上游错误: {e.response.text[:200]}")
    except Exception as e:
        raise HTTPException(500, f"内部错误: {e}")

    images = _save_b64_images(b64_list, "generated")
    first = images[0]
    return GenResponse(
        b64=first.b64,
        data_url=first.data_url,
        images=images,
        model=req.model,
    )


@app.post("/api/edit", response_model=GenResponse)
async def edit_image(
    prompt: str = Form(...),
    model: str = Form("gpt-image-2"),
    n: int = Form(1),
    save_annotated: bool = Form(False),
    image: UploadFile = File(...),
):
    if not prompt.strip():
        raise HTTPException(400, "prompt 不能为空")
    if not 1 <= n <= 4:
        raise HTTPException(400, "n 必须在 1 到 4 之间")
    content_type = image.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(400, "请上传图片文件")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(400, "上传图片不能为空")
    if len(image_bytes) > 20 * 1024 * 1024:
        raise HTTPException(400, "上传图片不能超过 20MB")

    annotated_image = None
    if save_annotated:
        try:
            annotated_image = _save_raw_image(image_bytes, "annotated")
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, f"保存标注图失败: {e}")

    try:
        b64_list = image_gen.edit_images_b64(
            image_bytes=image_bytes,
            filename=image.filename or "input.png",
            content_type=content_type,
            prompt=prompt,
            model=model,
            n=n,
        )
    except requests.Timeout:
        raise HTTPException(504, "编辑超时（>180s），请重试")
    except requests.HTTPError as e:
        raise HTTPException(502, f"上游错误: {e.response.text[:200]}")
    except Exception as e:
        raise HTTPException(500, f"内部错误: {e}")

    images = _save_b64_images(b64_list, "edited")
    first = images[0]
    return GenResponse(
        b64=first.b64,
        data_url=first.data_url,
        images=images,
        model=model,
        annotated_image=annotated_image,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

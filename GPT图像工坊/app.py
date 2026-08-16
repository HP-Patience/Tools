"""图片生成 Web 服务 - FastAPI"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime
from io import BytesIO
from math import ceil
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

import requests
from dotenv import set_key
from PIL import Image, ImageOps
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
LANCZOS = getattr(getattr(Image, "Resampling", Image), "LANCZOS")


class GenRequest(BaseModel):
    prompt: str
    model: str = "gpt-image-2"
    n: int = 1


class ImageItem(BaseModel):
    b64: str
    data_url: str
    file_path: str
    file_url: str
    metadata_path: Optional[str] = None
    metadata_url: Optional[str] = None


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


def _metadata_paths_for_image(image: ImageItem) -> tuple[Path, str, str]:
    image_path = OUTPUT_DIR / Path(image.file_path).name
    metadata_path = image_path.with_suffix(".json")
    metadata_filename = metadata_path.name
    return metadata_path, f"output/{metadata_filename}", f"/output/{metadata_filename}"


def _save_image_metadata(image: ImageItem, metadata: Optional[dict]) -> None:
    if not metadata:
        return
    metadata_path, metadata_file_path, metadata_file_url = _metadata_paths_for_image(image)
    payload = {
        **metadata,
        "image_file_path": image.file_path,
        "image_file_url": image.file_url,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    image.metadata_path = metadata_file_path
    image.metadata_url = metadata_file_url


def _save_b64_images(b64_list: list[str], prefix: str, metadata: Optional[dict] = None) -> list[ImageItem]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    images = []
    total = len(b64_list)
    for index, b64 in enumerate(b64_list, start=1):
        raw = base64.b64decode(b64, validate=True)
        extension, mime_type = _image_format(raw)
        filename = f"{prefix}_{timestamp}_{index}.{extension}"
        output_path = OUTPUT_DIR / filename
        output_path.write_bytes(raw)
        image = ImageItem(
            b64=b64,
            data_url=f"data:{mime_type};base64,{b64}",
            file_path=f"output/{filename}",
            file_url=f"/output/{filename}",
        )
        per_image_metadata = None
        if metadata:
            per_image_metadata = {
                **metadata,
                "result_index": index,
                "result_count": total,
            }
        _save_image_metadata(image, per_image_metadata)
        images.append(image)
    return images

def _save_raw_image(raw: bytes, prefix: str, metadata: Optional[dict] = None) -> ImageItem:
    extension, mime_type = _image_format(raw)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}_{timestamp}.{extension}"
    output_path = OUTPUT_DIR / filename
    output_path.write_bytes(raw)
    b64 = base64.b64encode(raw).decode("ascii")
    image = ImageItem(
        b64=b64,
        data_url=f"data:{mime_type};base64,{b64}",
        file_path=f"output/{filename}",
        file_url=f"/output/{filename}",
    )
    _save_image_metadata(image, metadata)
    return image


def _fit_rgb_image(raw: bytes, max_side: int) -> Image.Image:
    try:
        image = Image.open(BytesIO(raw))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_side, max_side), LANCZOS)
        if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
            canvas = Image.new("RGB", image.size, "white")
            canvas.paste(image.convert("RGBA"), mask=image.convert("RGBA").getchannel("A"))
            return canvas
        return image.convert("RGB")
    except Exception as e:
        raise ValueError(f"无法读取上传图片: {e}") from e


def _jpeg_bytes_under_limit(image: Image.Image, max_bytes: int) -> bytes:
    for quality in (88, 82, 76, 70, 64):
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
        data = buf.getvalue()
        if len(data) <= max_bytes:
            return data

    reduced = image.copy()
    while True:
        width, height = reduced.size
        if max(width, height) <= 768:
            buf = BytesIO()
            reduced.save(buf, format="JPEG", quality=60, optimize=True, progressive=True)
            return buf.getvalue()
        reduced = reduced.resize((max(1, int(width * 0.85)), max(1, int(height * 0.85))), LANCZOS)
        buf = BytesIO()
        reduced.save(buf, format="JPEG", quality=70, optimize=True, progressive=True)
        data = buf.getvalue()
        if len(data) <= max_bytes:
            return data


def _compose_reference_sheet(image_files: list[tuple[bytes, str, str]]) -> tuple[bytes, str, str]:
    """把多张参考图合成一张轻量参考板，兼容只支持单图/请求体较小的上游。"""
    count = len(image_files)
    if count < 2:
        raise ValueError("合成参考板至少需要两张图")

    # 2 张用左右排列；3/4 张用 2 列网格。限制单格尺寸，避免 CPA/反代报“请求内容过大”。
    columns = 2
    rows = ceil(count / columns)
    tile = 896 if count <= 2 else 768
    gap = 20
    padding = 20
    thumbs = [_fit_rgb_image(raw, tile) for raw, _, _ in image_files]
    canvas = Image.new(
        "RGB",
        (columns * tile + (columns - 1) * gap + padding * 2, rows * tile + (rows - 1) * gap + padding * 2),
        "white",
    )

    for index, thumb in enumerate(thumbs):
        col = index % columns
        row = index // columns
        x0 = padding + col * (tile + gap) + (tile - thumb.width) // 2
        y0 = padding + row * (tile + gap) + (tile - thumb.height) // 2
        canvas.paste(thumb, (x0, y0))

    data = _jpeg_bytes_under_limit(canvas, max_bytes=12 * 1024 * 1024)
    return data, "reference_sheet.jpg", "image/jpeg"


def _augment_prompt_for_reference_sheet(prompt: str, count: int) -> str:
    if count == 2:
        layout = "左侧是参考图 1，右侧是参考图 2。"
    else:
        layout = f"参考板中共有 {count} 张图，按从左到右、从上到下的顺序编号。"
    return (
        f"{prompt.strip()}\n\n"
        "补充说明：上传的参考图是一张由多张参考图拼成的白底参考板。"
        f"{layout}"
        "请只使用参考图中的人物、风格、构图、颜色等信息进行创作；"
        "不要把白底参考板、拼接边距、分隔空白或编号结构画进最终结果。"
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

    images = _save_b64_images(b64_list, "generated", {
        "kind": "generated",
        "prompt": req.prompt,
        "model": req.model,
        "requested_count": req.n,
    })
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
    image: List[UploadFile] = File(...),
):
    if not prompt.strip():
        raise HTTPException(400, "prompt 不能为空")
    if not 1 <= n <= 4:
        raise HTTPException(400, "n 必须在 1 到 4 之间")
    if not image:
        raise HTTPException(400, "请上传图片文件")
    if len(image) > 4:
        raise HTTPException(400, "参考图最多支持 4 张")

    image_files: list[tuple[bytes, str, str]] = []
    total_bytes = 0
    for index, upload in enumerate(image, start=1):
        content_type = upload.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(400, f"第 {index} 个文件不是图片")

        image_bytes = await upload.read()
        if not image_bytes:
            raise HTTPException(400, f"第 {index} 个图片为空")
        if len(image_bytes) > 20 * 1024 * 1024:
            raise HTTPException(400, f"第 {index} 个图片不能超过 20MB")
        total_bytes += len(image_bytes)
        if total_bytes > 60 * 1024 * 1024:
            raise HTTPException(400, "参考图总大小不能超过 60MB")

        image_files.append((
            image_bytes,
            upload.filename or f"input_{index}.png",
            content_type,
        ))

    annotated_image = None
    if save_annotated:
        if len(image_files) != 1:
            raise HTTPException(400, "保存标注图时只能提交一张图片")
        try:
            annotated_image = _save_raw_image(image_files[0][0], "annotated", {
                "kind": "annotated_input",
                "prompt": prompt,
                "model": model,
                "requested_count": n,
            })
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, f"保存标注图失败: {e}")

    upstream_prompt = prompt
    try:
        if len(image_files) == 1:
            b64_list = image_gen.edit_images_multi_b64(
                image_files=image_files,
                prompt=upstream_prompt,
                model=model,
                n=n,
            )
        else:
            sheet_bytes, sheet_filename, sheet_content_type = _compose_reference_sheet(image_files)
            upstream_prompt = _augment_prompt_for_reference_sheet(prompt, len(image_files))
            b64_list = image_gen.edit_images_b64(
                image_bytes=sheet_bytes,
                filename=sheet_filename,
                content_type=sheet_content_type,
                prompt=upstream_prompt,
                model=model,
                n=n,
            )
    except requests.Timeout:
        raise HTTPException(504, "编辑超时（>180s），请重试")
    except requests.HTTPError as e:
        raise HTTPException(502, f"上游错误: {e.response.text[:200]}")
    except Exception as e:
        raise HTTPException(500, f"内部错误: {e}")

    images = _save_b64_images(b64_list, "edited", {
        "kind": "edited",
        "prompt": prompt,
        "upstream_prompt": upstream_prompt,
        "model": model,
        "requested_count": n,
        "reference_image_count": len(image_files),
        "saved_annotated_input": bool(annotated_image),
        "annotated_image_path": annotated_image.file_path if annotated_image else None,
    })
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

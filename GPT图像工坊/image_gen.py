"""OpenAI 兼容图片生成客户端（可作为模块导入）。"""
from __future__ import annotations

import os
from pathlib import Path

import requests
import urllib3
from dotenv import load_dotenv

ENV_FILE = Path(__file__).with_name(".env")
DEFAULT_BASE_URL = "https://dss.josiny.com:2053/v1"
load_dotenv(ENV_FILE)

# 该服务使用自签名证书，禁用校验。仅限内部使用。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
_VERIFY = False
# 避免系统代理设置触发 urllib3 的 TLS-in-TLS bug
_NO_PROXY = {"http": None, "https": None}


def get_config() -> dict[str, str]:
    """返回当前进程使用的 API 配置。"""
    return {
        "base_url": os.getenv("IMAGE_API_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/"),
        "api_key": os.getenv("IMAGE_API_KEY", "").strip(),
    }


def _request_config() -> tuple[str, dict[str, str]]:
    config = get_config()
    if not config["api_key"]:
        raise RuntimeError("尚未配置 IMAGE_API_KEY，请先在页面中保存 API 配置")
    return config["base_url"], {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }


def generate_images_b64(
    prompt: str,
    model: str = "gpt-image-2",
    n: int = 1,
    timeout: int = 180,
) -> list[str]:
    """生成图片，返回 base64 字符串列表（不含 data: 前缀）。"""
    base_url, headers = _request_config()
    images = []
    while len(images) < n:
        remaining = n - len(images)
        # This project may point at a ChatGPT-account reverse proxy rather than
        # the official OpenAI Images API. Such proxies often reject optional
        # image parameters like size/quality/output_format/background and may
        # also reject n. For GPT Image 2, keep the upstream payload minimal and
        # loop locally to support Count > 1.
        payload = {"model": model, "prompt": prompt}
        if model != "gpt-image-2":
            payload["n"] = remaining
        if model == "grok-imagine-image":
            payload["response_format"] = "b64_json"
        r = requests.post(
            f"{base_url}/images/generations",
            headers=headers,
            json=payload,
            timeout=timeout,
            verify=_VERIFY,
            proxies=_NO_PROXY,
        )
        r.raise_for_status()
        batch = [item["b64_json"] for item in r.json().get("data", []) if "b64_json" in item]
        if not batch:
            raise RuntimeError(f"上游返回无 b64_json: {r.text[:300]}")
        images.extend(batch)
    return images[:n]


def generate_image_b64(
    prompt: str,
    model: str = "gpt-image-2",
    n: int = 1,
    timeout: int = 180,
) -> str:
    """生成图片，返回 base64 字符串（不含 data: 前缀）。"""
    return generate_images_b64(prompt, model, n, timeout)[0]



def edit_images_multi_b64(
    image_files: list[tuple[bytes, str, str]],
    prompt: str,
    model: str = "gpt-image-2",
    n: int = 1,
    timeout: int = 180,
) -> list[str]:
    """编辑图片，返回 base64 字符串列表（不含 data: 前缀）。

    ``image_files`` 中每一项为 ``(bytes, filename, content_type)``。多张
    参考图会以 multipart ``image[]`` 字段直接发给上游，用来验证
    CPA/反代是否支持真正多图编辑；Count > 1 仍在本地循环调用。
    """
    if not image_files:
        raise ValueError("至少需要一张参考图")

    base_url, headers = _request_config()
    # Let requests set the multipart boundary itself; Content-Type from
    # _request_config() is JSON-specific and would break multipart uploads.
    headers = {"Authorization": headers["Authorization"]}
    images = []
    while len(images) < n:
        upstream_image_field = "image[]" if len(image_files) > 1 else "image"
        files = [
            (upstream_image_field, (filename or f"input_{index}.png", raw, content_type or "application/octet-stream"))
            for index, (raw, filename, content_type) in enumerate(image_files, start=1)
        ]
        data = {
            "model": model,
            "prompt": prompt,
        }
        r = requests.post(
            f"{base_url}/images/edits",
            headers=headers,
            data=data,
            files=files,
            timeout=timeout,
            verify=_VERIFY,
            proxies=_NO_PROXY,
        )
        r.raise_for_status()
        batch = [item["b64_json"] for item in r.json().get("data", []) if "b64_json" in item]
        if not batch:
            raise RuntimeError(f"上游返回无 b64_json: {r.text[:300]}")
        images.extend(batch)
    return images[:n]


def edit_images_b64(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    prompt: str,
    model: str = "gpt-image-2",
    n: int = 1,
    timeout: int = 180,
) -> list[str]:
    """编辑单张图片，返回 base64 字符串列表（不含 data: 前缀）。"""
    return edit_images_multi_b64(
        image_files=[(image_bytes, filename, content_type)],
        prompt=prompt,
        model=model,
        n=n,
        timeout=timeout,
    )

def list_models() -> list[str]:
    base_url, headers = _request_config()
    r = requests.get(
        f"{base_url}/models",
        headers=headers,
        timeout=30,
        verify=_VERIFY,
        proxies=_NO_PROXY,
    )
    r.raise_for_status()
    return [m["id"] for m in r.json()["data"]]

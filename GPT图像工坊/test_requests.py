"""OpenAI 兼容接口测试 - dss.josiny.com:2053
纯 requests 实现，不依赖 openai SDK。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import requests

import image_gen

_CONFIG = image_gen.get_config()
BASE_URL = _CONFIG["base_url"]
API_KEY = _CONFIG["api_key"]
if not API_KEY:
    raise RuntimeError("尚未配置 IMAGE_API_KEY，请先在页面中保存 API 配置")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


def _post(path: str, payload: dict, timeout: int = 60) -> dict:
    r = requests.post(f"{BASE_URL}{path}", headers=HEADERS,
                      json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ---------- 1. 列出模型 ----------
def list_models() -> list[str]:
    return [m["id"] for m in requests.get(
        f"{BASE_URL}/models", headers=HEADERS, timeout=30
    ).json()["data"]]


# ---------- 2. 聊天补全 ----------
def chat(model: str, prompt: str, max_tokens: int = 200) -> str:
    data = _post("/chat/completions", {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    })
    return data["choices"][0]["message"]["content"]


# ---------- 3. 图像生成 ----------
def generate_image(
    model: str,
    prompt: str,
    save_path: str | Path,
    n: int = 1,
    timeout: int = 180,
) -> Path | list[Path]:
    """绘图通常较慢，默认超时 180s。"""
    b64_items = []
    while len(b64_items) < n:
        remaining = n - len(b64_items)
        payload = {"model": model, "prompt": prompt}
        if model != "gpt-image-2":
            payload["n"] = remaining
        data = _post("/images/generations", payload, timeout=timeout)
        batch = [item["b64_json"] for item in data.get("data", []) if "b64_json" in item]
        if not batch:
            raise RuntimeError(f"上游返回无 b64_json: {data}")
        b64_items.extend(batch)

    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if len(b64_items) == 1:
        save_path.write_bytes(base64.b64decode(b64_items[0]))
        return save_path

    paths = []
    for index, b64 in enumerate(b64_items, start=1):
        numbered_path = save_path.with_name(f"{save_path.stem}_{index}{save_path.suffix}")
        numbered_path.write_bytes(base64.b64decode(b64))
        paths.append(numbered_path)
    return paths


# ---------- 4. 流式聊天 ----------
def chat_stream(model: str, prompt: str) -> None:
    with requests.post(
        f"{BASE_URL}/chat/completions",
        headers=HEADERS,
        json={"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True},
        stream=True,
        timeout=60,
    ) as r:
        for line in r.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            payload = line[6:]
            if payload == b"[DONE]":
                break
            chunk = json.loads(payload)
            delta = chunk["choices"][0]["delta"].get("content", "")
            if delta:
                print(delta, end="", flush=True)
    print()


# ---------- demo ----------
if __name__ == "__main__":
    print("=== Models ===")
    for m in list_models():
        print(" -", m)

    print("\n=== Chat (gpt-5.4-mini) ===")
    print(chat("gpt-5.4-mini", "用一句话介绍你自己", max_tokens=100))

    print("\n=== Image (gpt-image-1.5) ===")
    out = generate_image(
        model="gpt-image-1.5",
        prompt="A cute cat sitting on a windowsill, watercolor style",
        save_path="output/cat.png",
        n=2,
    )
    print("saved ->", out)

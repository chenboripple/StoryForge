"""Reusable image generation helpers with provider-specific adapters."""

from __future__ import annotations

import base64
import json
import os
import math
import subprocess
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
import uuid
from urllib import error as urlerror
from urllib import request as urlrequest


IMAGE_RESOLUTION_PRESETS = {
    "360p": 360,
    "540p": 540,
    "720p": 720,
    "1080p": 1080,
    "2k": 1440,
    "4k": 2160,
}

IMAGE_ASPECT_RATIOS = {
    "16:9": (16, 9),
    "16:10": (16, 10),
    "21:9": (21, 9),
    "9:16": (9, 16),
    "9:19.5": (9, 19.5),
    "4:3": (4, 3),
    "1:1": (1, 1),
    "3:2": (3, 2),
    "3:4": (3, 4),
    "2:3": (2, 3),
    "5:4": (5, 4),
    "4:5": (4, 5),
}


def generate_image_from_model_config(
    model_cfg: Dict[str, Any],
    prompt: str,
    download_dir: Optional[str] = None,
) -> Tuple[Optional[Dict[str, str]], str]:
    provider = str(model_cfg.get("provider") or "").strip().lower()
    if provider == "qwen-image":
        return _generate_qwen_image(model_cfg, prompt, download_dir=download_dir)
    return _generate_openai_compatible_image(model_cfg, prompt, download_dir=download_dir)


def _generate_qwen_image(
    model_cfg: Dict[str, Any],
    prompt: str,
    download_dir: Optional[str] = None,
) -> Tuple[Optional[Dict[str, str]], str]:
    model = str(model_cfg.get("model") or "qwen-image-2.0").strip()
    api_key = str(model_cfg.get("api_key") or "").strip()
    endpoint = str(
        model_cfg.get("image_endpoint")
        or model_cfg.get("base_url")
        or "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
    ).strip()
    image_size = _normalize_qwen_image_size(
        str(model_cfg.get("image_size") or "1024*1024").strip().replace("x", "*")
    )
    timeout = int(model_cfg.get("timeout") or 90)

    if not api_key:
        return None, "qwen-image provider missing api_key"

    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]
        },
        "parameters": {"size": image_size},
    }

    status_code, body, curl_error = _post_json_with_curl(
        endpoint=endpoint,
        api_key=api_key,
        payload=payload,
        timeout=timeout,
    )
    if curl_error:
        return None, curl_error
    if status_code < 200 or status_code >= 300:
        return None, f"http {status_code}: {body[:300]}"

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None, "invalid json response"

    image_url = _extract_qwen_image_url(data)
    if not image_url:
        return None, "qwen response missing output image url"

    local_path, download_error = download_image(image_url, output_dir=download_dir)
    if download_error:
        return None, download_error

    return {
        "url": image_url,
        "thumb_url": image_url,
        "provider": "qwen-image",
        "model": model,
        "local_path": local_path or "",
        "size": image_size,
        "aspect_ratio": str(model_cfg.get("aspect_ratio") or "16:9"),
        "image_preset": str(model_cfg.get("image_preset") or "720p"),
    }, ""


def _generate_openai_compatible_image(
    model_cfg: Dict[str, Any],
    prompt: str,
    download_dir: Optional[str] = None,
) -> Tuple[Optional[Dict[str, str]], str]:
    model = str(model_cfg.get("model") or "").strip()
    api_key = str(model_cfg.get("api_key") or "").strip()
    base_url = str(model_cfg.get("base_url") or "").strip().rstrip("/")
    if not (model and api_key and base_url):
        return None, "image model missing api_key/base_url/model"

    cfg_extra = model_cfg.get("extra") if isinstance(model_cfg.get("extra"), dict) else {}
    image_size = str(
        model_cfg.get("image_size")
        or cfg_extra.get("image_size")
        or "1024x1024"
    ).strip()
    response_format = str(
        model_cfg.get("response_format")
        or cfg_extra.get("response_format")
        or "url"
    ).strip()
    endpoint_cfg = str(
        model_cfg.get("image_endpoint")
        or cfg_extra.get("image_endpoint")
        or "/images/generations"
    ).strip()

    endpoint = endpoint_cfg if endpoint_cfg.startswith("http") else f"{base_url}/{endpoint_cfg.lstrip('/')}"
    payload = {
        "model": model,
        "prompt": prompt,
        "size": image_size,
        "response_format": response_format,
    }

    req = urlrequest.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=int(model_cfg.get("timeout") or 90)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
    except urlerror.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            err_body = ""
        return None, f"http {e.code}: {err_body or e.reason}"
    except urlerror.URLError as e:
        return None, f"network error: {e.reason}"
    except TimeoutError:
        return None, "request timeout"
    except json.JSONDecodeError:
        return None, "invalid json response"

    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        return None, "response has no data items"

    first = items[0] if isinstance(items[0], dict) else {}
    url = str(first.get("url") or "").strip()
    if not url:
        b64 = str(first.get("b64_json") or "").strip()
        if not b64:
            return None, "response missing url/b64_json"
        try:
            base64.b64decode(b64, validate=True)
        except Exception:
            return None, "invalid base64 image payload"
        url = f"data:image/png;base64,{b64}"

    local_path, download_error = download_image(url, output_dir=download_dir)
    if download_error:
        return None, download_error

    return {
        "url": url,
        "thumb_url": url,
        "provider": str(model_cfg.get("provider") or "configured-image-provider"),
        "model": model,
        "local_path": local_path or "",
        "size": image_size,
        "aspect_ratio": str(model_cfg.get("aspect_ratio") or "16:9"),
        "image_preset": str(model_cfg.get("image_preset") or "720p"),
    }, ""


def download_image(url: str, output_dir: Optional[str] = None) -> Tuple[Optional[str], str]:
    target_dir = os.path.abspath(output_dir or os.getcwd())
    os.makedirs(target_dir, exist_ok=True)
    filename = f"generated_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid.uuid4().hex[:8]}.png"
    file_path = os.path.join(target_dir, filename)

    if url.startswith("data:image/"):
        comma = url.find(",")
        if comma == -1:
            return None, "invalid data url"
        raw = url[comma + 1 :]
        try:
            decoded = base64.b64decode(raw)
        except Exception:
            return None, "invalid base64 image payload"
        with open(file_path, "wb") as f:
            f.write(decoded)
        return file_path, ""

    cmd = ["curl", "-sSL", "-o", file_path, url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return None, (proc.stderr or proc.stdout or "curl download failed").strip()
    return file_path, ""


def _post_json_with_curl(
    endpoint: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout: int,
) -> Tuple[int, str, str]:
    cmd = [
        "curl",
        "-sS",
        "-m",
        str(timeout),
        "-X",
        "POST",
        endpoint,
        "-H",
        f"Authorization: Bearer {api_key}",
        "-H",
        "Content-Type: application/json",
        "-d",
        json.dumps(payload, ensure_ascii=False),
        "-w",
        "\n%{http_code}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return 0, "", (proc.stderr or proc.stdout or "curl request failed").strip()

    body, _, status_text = proc.stdout.rpartition("\n")
    try:
        status_code = int(status_text.strip())
    except ValueError:
        return 0, proc.stdout, "unable to parse curl http status"
    return status_code, body, ""


def _extract_qwen_image_url(data: Dict[str, Any]) -> str:
    output = data.get("output") if isinstance(data, dict) else None
    choices = output.get("choices") if isinstance(output, dict) else None
    if not isinstance(choices, list):
        return ""

    for choice in choices:
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            image = str(item.get("image") or "").strip()
            if image:
                return image
    return ""


def _normalize_qwen_image_size(size: str) -> str:
    parts = size.lower().replace("x", "*").split("*", 1)
    if len(parts) != 2:
        return size
    try:
        width = int(parts[0])
        height = int(parts[1])
    except ValueError:
        return size

    if width <= 0 or height <= 0:
        return size

    max_pixels = 4194304
    pixels = width * height
    if pixels <= max_pixels:
        return f"{width}*{height}"

    scale = math.sqrt(max_pixels / float(pixels))
    new_width = max(64, int(width * scale))
    new_height = max(64, int(height * scale))
    return f"{new_width}*{new_height}"


def resolve_image_size(
    provider: str,
    requested_size: str = "",
    image_preset: str = "720p",
    aspect_ratio: str = "16:9",
) -> str:
    normalized_provider = (provider or "").strip().lower()
    separator = "*" if normalized_provider == "qwen-image" else "x"

    preset_value = IMAGE_RESOLUTION_PRESETS.get((image_preset or "720p").lower(), 720)
    ratio = IMAGE_ASPECT_RATIOS.get(aspect_ratio or "16:9", (16, 9))
    ratio_w, ratio_h = float(ratio[0]), float(ratio[1])

    if ratio_w >= ratio_h:
        height = preset_value
        width = int(round(height * ratio_w / ratio_h))
    else:
        width = preset_value
        height = int(round(width * ratio_h / ratio_w))

    # requested_size 作为“最大尺寸上限”处理（不是默认尺寸）。
    # 例：4096x4096 表示宽高都不能超过 4096。
    if requested_size and requested_size.strip():
        raw = requested_size.strip().lower().replace("*", "x")
        parts = raw.split("x", 1)
        if len(parts) == 2:
            try:
                max_w = int(parts[0])
                max_h = int(parts[1])
                if max_w > 0 and max_h > 0 and (width > max_w or height > max_h):
                    scale = min(max_w / float(width), max_h / float(height))
                    width = max(64, int(round(width * scale)))
                    height = max(64, int(round(height * scale)))
            except ValueError:
                # 非法上限格式时忽略，回退到按 preset/ratio 的计算值。
                pass

    return f"{width}{separator}{height}"
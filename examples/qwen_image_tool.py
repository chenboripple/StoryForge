"""CLI tool for direct qwen-image generation and download."""

from __future__ import annotations

import argparse
import os
import sys

from core.image_generation import generate_image_from_model_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and download images with qwen-image provider")
    parser.add_argument("prompt", nargs="+", help="Image description prompt")
    parser.add_argument("--model", default="qwen-image-2.0", help="Model id")
    parser.add_argument("--size", default="1024*1024", help="Image size, e.g. 1024*1024")
    parser.add_argument("--api-key", default=os.getenv("TOKEN_PLAN_AUTH_TOKEN") or os.getenv("ANTHROPIC_AUTH_TOKEN") or "")
    parser.add_argument("--endpoint", default="https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation")
    parser.add_argument("--output-dir", default=os.getcwd())
    args = parser.parse_args()

    model_cfg = {
        "provider": "qwen-image",
        "model": args.model,
        "api_key": args.api_key,
        "image_endpoint": args.endpoint,
        "image_size": args.size,
        "timeout": 120,
    }
    result, error = generate_image_from_model_config(model_cfg, " ".join(args.prompt), download_dir=args.output_dir)
    if error:
        print(error, file=sys.stderr)
        return 1

    print(result.get("local_path") or "")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = SKILL_DIR / "config.json"

OPENAI_COMPATIBLE = "openai_compatible"
GEMINI_NATIVE = "gemini_native"

TRANSPORT_OPENAI_IMAGE_GENERATION = "openai_image_generation"
TRANSPORT_OPENAI_CHAT_COMPLETIONS = "openai_chat_completions"
TRANSPORT_GEMINI_NATIVE = "gemini_native"

PRESETS = {
    "openai-chat": {
        "target": "gpt-image-2",
        "provider": OPENAI_COMPATIBLE,
        "transport": TRANSPORT_OPENAI_CHAT_COMPLETIONS,
        "url": "https://api.openai.com/v1/chat/completions",
        "api_model": "gpt-image-2",
    },
    "openai-image": {
        "target": "gpt-image-2",
        "provider": OPENAI_COMPATIBLE,
        "transport": TRANSPORT_OPENAI_IMAGE_GENERATION,
        "url": "https://api.openai.com/v1/images/generations",
        "api_model": "gpt-image-2",
    },
    "gemini-native": {
        "target": "gemini-3-pro-preview",
        "provider": GEMINI_NATIVE,
        "transport": TRANSPORT_GEMINI_NATIVE,
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent",
        "api_model": "gemini-3-pro-preview",
    },
}


def prompt_if_missing(value: str | None, label: str, *, secret: bool = False) -> str:
    if value:
        return value
    if secret:
        value = getpass.getpass(f"{label}: ").strip()
    else:
        value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} is required.")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create ai-scientific-draw config.json from an API key and target settings."
    )
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="openai-chat",
        help="Target template to start from. Default: openai-chat.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key. If omitted, the script prompts securely.",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Target name in config.json, such as gpt-image-2.",
    )
    parser.add_argument(
        "--api-model",
        default=None,
        help="Provider model name. Defaults to the preset model.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="API endpoint URL. Defaults to the preset URL.",
    )
    parser.add_argument(
        "--provider",
        choices=[OPENAI_COMPATIBLE, GEMINI_NATIVE],
        default=None,
        help="Provider type. Defaults to the preset provider.",
    )
    parser.add_argument(
        "--transport",
        choices=[
            TRANSPORT_OPENAI_IMAGE_GENERATION,
            TRANSPORT_OPENAI_CHAT_COMPLETIONS,
            TRANSPORT_GEMINI_NATIVE,
        ],
        default=None,
        help="Request/response protocol. Defaults to the preset transport.",
    )
    parser.add_argument(
        "--default-target",
        default=None,
        help="defaults.target value. Defaults to --target.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Request timeout in seconds. Default: 180.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output config path. Default: ai-scientific-draw/config.json.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output if it already exists.",
    )
    return parser


def validate_target(provider: str, transport: str, url: str, api_key: str) -> None:
    if not url:
        raise ValueError("URL is required.")
    if not api_key:
        raise ValueError("API key is required.")
    if provider == OPENAI_COMPATIBLE and transport not in {
        TRANSPORT_OPENAI_IMAGE_GENERATION,
        TRANSPORT_OPENAI_CHAT_COMPLETIONS,
    }:
        raise ValueError(
            f"{OPENAI_COMPATIBLE} requires transport "
            f"{TRANSPORT_OPENAI_IMAGE_GENERATION} or {TRANSPORT_OPENAI_CHAT_COMPLETIONS}."
        )
    if provider == GEMINI_NATIVE and transport != TRANSPORT_GEMINI_NATIVE:
        raise ValueError(f"{GEMINI_NATIVE} requires transport {TRANSPORT_GEMINI_NATIVE}.")


def make_config(args: argparse.Namespace) -> dict[str, object]:
    preset = PRESETS[args.preset]
    api_key = prompt_if_missing(args.api_key, "API key", secret=True)

    target = args.target or preset["target"]
    provider = args.provider or preset["provider"]
    transport = args.transport or preset["transport"]
    url = args.url or preset["url"]
    api_model = args.api_model or preset["api_model"]
    default_target = args.default_target or target

    validate_target(provider, transport, url, api_key)

    return {
        "defaults": {
            "target": default_target,
            "timeout": args.timeout,
            OPENAI_COMPATIBLE: {
                "size": "1024x1024",
                "quality": "medium",
                "output_format": "png",
            },
            GEMINI_NATIVE: {
                "aspect_ratio": "16:9",
                "image_size": "2K",
            },
        },
        "targets": {
            target: {
                "provider": provider,
                "transport": transport,
                "url": url,
                "api_key": api_key,
                "api_model": api_model,
            }
        },
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = Path.cwd() / output

    if output.exists() and not args.force:
        print(
            f"Error: {output} already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 1

    try:
        config = make_config(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

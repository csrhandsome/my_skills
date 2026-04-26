from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config.json"
DEFAULT_OUTPUT = REPO_ROOT / "img" / "generated.png"
DEFAULT_TIMEOUT = 180.0

OPENAI_COMPATIBLE = "openai_compatible"
GEMINI_NATIVE = "gemini_native"

TRANSPORT_OPENAI_IMAGE_GENERATION = "openai_image_generation"
TRANSPORT_OPENAI_CHAT_COMPLETIONS = "openai_chat_completions"
TRANSPORT_GEMINI_NATIVE = "gemini_native"

OPENAI_DEFAULTS = {
    "size": "1024x1024",
    "quality": "medium",
    "output_format": "png",
}
GEMINI_DEFAULTS = {
    "aspect_ratio": "16:9",
    "image_size": "2K",
}
GEMINI_DEFAULT_RESPONSE_MODALITIES = ["IMAGE"]

MARKDOWN_IMAGE_URL_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
PLAIN_URL_RE = re.compile(r"https?://[^\s)]+")


def parse_config(config_path: Path) -> dict[str, object]:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Config must be a JSON object: {config_path}")

    if "targets" in raw:
        return parse_targets_config(raw)

    return parse_legacy_config(raw)


def parse_targets_config(raw: dict[str, object]) -> dict[str, object]:
    defaults_raw = raw.get("defaults")
    targets_raw = raw.get("targets")
    if not isinstance(defaults_raw, dict):
        raise ValueError("Config key 'defaults' must be a JSON object.")
    if not isinstance(targets_raw, dict) or not targets_raw:
        raise ValueError("Config key 'targets' must be a non-empty JSON object.")

    targets = {
        target_name: normalize_target_config(target_name, target_raw)
        for target_name, target_raw in targets_raw.items()
    }
    default_target = str(defaults_raw.get("target") or next(iter(targets)))
    if default_target not in targets:
        raise ValueError("Config key 'defaults.target' must exist in 'targets'.")

    return {
        "defaults": normalize_defaults(defaults_raw, default_target),
        "targets": targets,
    }


def parse_legacy_config(raw: dict[str, object]) -> dict[str, object]:
    api_key = raw.get("api_key")
    if not api_key:
        raise ValueError("Missing required config key: api_key")

    models_raw = raw.get("models")
    if not isinstance(models_raw, dict) or not models_raw:
        raise ValueError("Config key 'models' must be a non-empty JSON object.")

    targets: dict[str, dict[str, object]] = {}
    for model_name, model_raw in models_raw.items():
        if not isinstance(model_name, str):
            raise ValueError("All model names in 'models' must be strings.")
        if not isinstance(model_raw, dict):
            raise ValueError(f"Config for model '{model_name}' must be a JSON object.")

        target_raw = dict(model_raw)
        target_raw["api_key"] = str(api_key)
        target_raw.setdefault("api_model", model_name)
        targets[model_name] = normalize_target_config(model_name, target_raw)

    default_target = str(raw.get("default_model") or next(iter(targets)))
    if default_target not in targets:
        raise ValueError("Config key 'default_model' must exist in 'models'.")

    return {
        "defaults": normalize_defaults({}, default_target),
        "targets": targets,
    }


def normalize_defaults(defaults_raw: dict[str, object], default_target: str) -> dict[str, object]:
    timeout_raw = defaults_raw.get("timeout", DEFAULT_TIMEOUT)
    try:
        timeout = float(timeout_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Config key 'defaults.timeout' must be numeric.") from exc
    if timeout <= 0:
        raise ValueError("Config key 'defaults.timeout' must be positive.")

    return {
        "target": default_target,
        "timeout": timeout,
        OPENAI_COMPATIBLE: merge_defaults(
            OPENAI_DEFAULTS,
            defaults_raw.get(OPENAI_COMPATIBLE),
            OPENAI_COMPATIBLE,
        ),
        GEMINI_NATIVE: merge_defaults(
            GEMINI_DEFAULTS,
            defaults_raw.get(GEMINI_NATIVE),
            GEMINI_NATIVE,
        ),
    }


def merge_defaults(
    base_defaults: dict[str, str],
    overrides_raw: object,
    section_name: str,
) -> dict[str, str]:
    if overrides_raw is None:
        return dict(base_defaults)
    if not isinstance(overrides_raw, dict):
        raise ValueError(f"Config key 'defaults.{section_name}' must be a JSON object.")

    merged = dict(base_defaults)
    for key, value in overrides_raw.items():
        if not isinstance(key, str):
            raise ValueError(f"Config key 'defaults.{section_name}' must use string keys.")
        if value is None:
            continue
        merged[key] = str(value)
    return merged


def normalize_target_config(target_name: str, target_raw: object) -> dict[str, object]:
    if not isinstance(target_name, str):
        raise ValueError("All target names in 'targets' must be strings.")
    if not isinstance(target_raw, dict):
        raise ValueError(f"Config for target '{target_name}' must be a JSON object.")

    provider = str(target_raw.get("provider") or "")
    url = str(target_raw.get("url") or "")
    api_key = str(target_raw.get("api_key") or "")
    api_model = str(target_raw.get("api_model") or target_name)
    transport = str(target_raw.get("transport") or infer_transport(provider, url))

    if provider not in {OPENAI_COMPATIBLE, GEMINI_NATIVE}:
        raise ValueError(
            f"Target '{target_name}' must set provider to "
            f"'{OPENAI_COMPATIBLE}' or '{GEMINI_NATIVE}'."
        )
    if not url:
        raise ValueError(f"Target '{target_name}' is missing 'url'.")
    if not api_key:
        raise ValueError(f"Target '{target_name}' is missing 'api_key'.")

    if provider == OPENAI_COMPATIBLE and transport not in {
        TRANSPORT_OPENAI_IMAGE_GENERATION,
        TRANSPORT_OPENAI_CHAT_COMPLETIONS,
    }:
        raise ValueError(
            f"Target '{target_name}' must use transport "
            f"'{TRANSPORT_OPENAI_IMAGE_GENERATION}' or "
            f"'{TRANSPORT_OPENAI_CHAT_COMPLETIONS}'."
        )
    if provider == GEMINI_NATIVE and transport != TRANSPORT_GEMINI_NATIVE:
        raise ValueError(
            f"Target '{target_name}' must use transport '{TRANSPORT_GEMINI_NATIVE}'."
        )

    return {
        "provider": provider,
        "transport": transport,
        "url": url,
        "api_key": api_key,
        "api_model": api_model,
    }


def infer_transport(provider: str, url: str) -> str:
    if provider == OPENAI_COMPATIBLE:
        if url.endswith("/chat/completions"):
            return TRANSPORT_OPENAI_CHAT_COMPLETIONS
        return TRANSPORT_OPENAI_IMAGE_GENERATION
    if provider == GEMINI_NATIVE:
        return TRANSPORT_GEMINI_NATIVE
    return ""


def extract_error_message(payload: object) -> str:
    if isinstance(payload, dict):
        for key in ("message", "msg", "detail"):
            value = payload.get(key)
            if value:
                return str(value)

        error = payload.get("error")
        if isinstance(error, dict):
            for key in ("message", "detail", "code", "status"):
                value = error.get(key)
                if value:
                    return str(value)
        elif error:
            return str(error)

        return json.dumps(payload, ensure_ascii=False)

    return str(payload)


def raise_for_api_error(payload: object, http_status: int | None = None) -> None:
    if isinstance(payload, dict):
        status_code = payload.get("status_code")
        if status_code not in (None, 200):
            raise RuntimeError(
                f"API returned status_code={status_code}: {extract_error_message(payload)}"
            )
        if "error" in payload and payload["error"]:
            raise RuntimeError(extract_error_message(payload))

    if http_status is not None and http_status >= 400:
        raise RuntimeError(f"HTTP {http_status}: {extract_error_message(payload)}")


def post_json(
    *,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> dict[str, object]:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)

    try:
        response_payload = response.json()
    except requests.JSONDecodeError:
        response_payload = {"message": response.text}

    raise_for_api_error(response_payload, response.status_code)
    if response.status_code != 200:
        raise RuntimeError(
            f"HTTP {response.status_code}: {extract_error_message(response_payload)}"
        )
    if not isinstance(response_payload, dict):
        raise RuntimeError("API response is not a JSON object.")

    return response_payload


def save_openai_image(image_data: object, output_path: Path, timeout: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(image_data, dict):
        b64_payload = image_data.get("b64_json")
        image_url = image_data.get("url")
    else:
        b64_payload = getattr(image_data, "b64_json", None)
        image_url = getattr(image_data, "url", None)

    if b64_payload:
        output_path.write_bytes(base64.b64decode(str(b64_payload)))
        return

    if image_url:
        response = requests.get(str(image_url), timeout=timeout)
        response.raise_for_status()
        output_path.write_bytes(response.content)
        return

    raise RuntimeError("Image response did not contain b64_json or url.")


def save_gemini_image(payload: dict[str, object], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise RuntimeError("Gemini response is missing candidates.")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            inline_data = part.get("inlineData") or part.get("inline_data")
            if not isinstance(inline_data, dict):
                continue
            data = inline_data.get("data")
            if data:
                output_path.write_bytes(base64.b64decode(str(data)))
                return

    raise RuntimeError("Gemini response did not contain inline image data.")


def generate_openai_image_generation(
    *,
    target_config: dict[str, object],
    prompt: str,
    size: str,
    quality: str,
    output_format: str,
    timeout: float,
) -> dict[str, object]:
    url = target_config["url"]
    api_key = target_config["api_key"]
    api_model = target_config["api_model"]
    if not isinstance(url, str) or not isinstance(api_key, str) or not isinstance(api_model, str):
        raise ValueError("OpenAI image-generation target config is invalid.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": api_model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "output_format": output_format,
    }
    return post_json(url=url, headers=headers, payload=payload, timeout=timeout)


def generate_openai_chat_completion_image(
    *,
    target_config: dict[str, object],
    prompt: str,
    timeout: float,
) -> dict[str, object]:
    url = target_config["url"]
    api_key = target_config["api_key"]
    api_model = target_config["api_model"]
    if not isinstance(url, str) or not isinstance(api_key, str) or not isinstance(api_model, str):
        raise ValueError("OpenAI chat-completions target config is invalid.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": api_model,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
    }
    return post_json(url=url, headers=headers, payload=payload, timeout=timeout)


def generate_gemini_native_image(
    *,
    target_config: dict[str, object],
    prompt: str,
    aspect_ratio: str,
    image_size: str,
    timeout: float,
) -> dict[str, object]:
    url = target_config["url"]
    api_key = target_config["api_key"]
    api_model = target_config["api_model"]
    if not isinstance(url, str) or not isinstance(api_key, str) or not isinstance(api_model, str):
        raise ValueError("Gemini target config is invalid.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "model": api_model,
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseModalities": GEMINI_DEFAULT_RESPONSE_MODALITIES,
            "imageConfig": {
                "aspectRatio": aspect_ratio,
                "image_size": image_size,
            },
        },
    }
    return post_json(url=url, headers=headers, payload=payload, timeout=timeout)


def extract_openai_generation_images(payload: dict[str, object]) -> list[dict[str, str]]:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("OpenAI image-generation response is empty.")

    images: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        image_payload = normalize_image_entry(item)
        if image_payload is not None:
            images.append(image_payload)

    if not images:
        raise RuntimeError("OpenAI image-generation response did not contain an image.")
    return images


def extract_chat_completion_images(payload: dict[str, object]) -> list[dict[str, str]]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("Chat completions response is missing choices.")

    images: list[dict[str, str]] = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        images.extend(extract_images_from_message(message))

    if not images:
        raise RuntimeError(
            "Chat completions response did not contain an image URL or b64 payload."
        )
    return dedupe_images(images)


def extract_images_from_message(message: dict[str, object]) -> list[dict[str, str]]:
    images: list[dict[str, str]] = []

    message_images = message.get("images")
    if isinstance(message_images, list):
        for entry in message_images:
            image_payload = normalize_image_entry(entry)
            if image_payload is not None:
                images.append(image_payload)

    for text_fragment in iter_text_fragments(message.get("content")):
        for url in extract_image_urls(text_fragment):
            images.append({"url": url})

    return images


def normalize_image_entry(entry: object) -> dict[str, str] | None:
    if not isinstance(entry, dict):
        return None

    b64_payload = entry.get("b64_json")
    if b64_payload:
        return {"b64_json": str(b64_payload)}

    image_url = entry.get("url")
    if image_url:
        return {"url": str(image_url)}

    return None


def iter_text_fragments(content: object) -> list[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []

    fragments: list[str] = []
    for item in content:
        if isinstance(item, str):
            fragments.append(item)
            continue
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str):
            fragments.append(text)
            continue
        nested_content = item.get("content")
        if isinstance(nested_content, str):
            fragments.append(nested_content)
    return fragments


def extract_image_urls(text: str) -> list[str]:
    urls = MARKDOWN_IMAGE_URL_RE.findall(text)
    if not urls:
        urls = PLAIN_URL_RE.findall(text)

    unique_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        unique_urls.append(url)
    return unique_urls


def dedupe_images(images: list[dict[str, str]]) -> list[dict[str, str]]:
    unique_images: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for image in images:
        if "b64_json" in image:
            key = ("b64_json", image["b64_json"])
        else:
            key = ("url", image["url"])
        if key in seen:
            continue
        seen.add(key)
        unique_images.append(image)
    return unique_images


def build_parser(target_names: list[str], default_target: str, default_timeout: float) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an image with configured targets."
    )
    parser.add_argument("prompt", nargs="?", help="Prompt used for image generation.")
    parser.add_argument(
        "--target",
        "--model",
        dest="target",
        default=default_target,
        choices=target_names,
        help="Configured target from ai_draw_skills/config.json. '--model' is kept as a compatibility alias.",
    )
    parser.add_argument(
        "--list-targets",
        action="store_true",
        help="Print configured targets and exit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output file path. Relative paths are resolved from ai_draw_skills/.",
    )
    parser.add_argument(
        "--size",
        default=None,
        help="OpenAI-compatible image size override, such as 1024x1024.",
    )
    parser.add_argument(
        "--quality",
        default=None,
        help="OpenAI-compatible quality override, such as low, medium, or high.",
    )
    parser.add_argument(
        "--output-format",
        default=None,
        help="OpenAI-compatible output format override, such as png or jpeg.",
    )
    parser.add_argument(
        "--aspect-ratio",
        default=None,
        help="Gemini image aspect ratio override, such as 16:9.",
    )
    parser.add_argument(
        "--image-size",
        default=None,
        help="Gemini image size override, such as 2K.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help=f"Request timeout in seconds. Default: {default_timeout:g}.",
    )
    return parser


def print_targets(targets: dict[str, dict[str, object]], default_target: str) -> None:
    for target_name, target_config in targets.items():
        provider = target_config["provider"]
        transport = target_config["transport"]
        api_model = target_config["api_model"]
        default_marker = " (default)" if target_name == default_target else ""
        print(
            f"{target_name}{default_marker}: provider={provider}, "
            f"transport={transport}, api_model={api_model}"
        )


def main() -> int:
    config = parse_config(CONFIG_PATH)
    defaults = config["defaults"]
    targets = config["targets"]
    if not isinstance(defaults, dict):
        raise ValueError("Config defaults are invalid.")
    if not isinstance(targets, dict):
        raise ValueError("Config targets are invalid.")

    default_target = defaults["target"]
    default_timeout = defaults["timeout"]
    if not isinstance(default_target, str):
        raise ValueError("Config key 'defaults.target' must be a string.")
    if not isinstance(default_timeout, float):
        raise ValueError("Config key 'defaults.timeout' must be numeric.")

    parser = build_parser(list(targets.keys()), default_target, default_timeout)
    args = parser.parse_args()

    if args.list_targets:
        print_targets(targets, default_target)
        return 0
    if not args.prompt:
        parser.error("the following arguments are required: prompt")

    target_config = targets.get(args.target)
    if not isinstance(target_config, dict):
        raise ValueError(f"Target config not found: {args.target}")

    provider = target_config.get("provider")
    transport = target_config.get("transport")
    if not isinstance(provider, str):
        raise ValueError(f"Target '{args.target}' is missing provider.")
    if not isinstance(transport, str):
        raise ValueError(f"Target '{args.target}' is missing transport.")

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = REPO_ROOT / output_path

    if provider == OPENAI_COMPATIBLE:
        provider_defaults = defaults.get(OPENAI_COMPATIBLE)
        if not isinstance(provider_defaults, dict):
            raise ValueError(f"Config key 'defaults.{OPENAI_COMPATIBLE}' is invalid.")

        size = args.size or provider_defaults["size"]
        quality = args.quality or provider_defaults["quality"]
        output_format = args.output_format or provider_defaults["output_format"]

        if transport == TRANSPORT_OPENAI_IMAGE_GENERATION:
            response = generate_openai_image_generation(
                target_config=target_config,
                prompt=args.prompt,
                size=size,
                quality=quality,
                output_format=output_format,
                timeout=args.timeout,
            )
            images = extract_openai_generation_images(response)
            save_openai_image(images[0], output_path, args.timeout)
            print(output_path)
            return 0

        if transport == TRANSPORT_OPENAI_CHAT_COMPLETIONS:
            response = generate_openai_chat_completion_image(
                target_config=target_config,
                prompt=args.prompt,
                timeout=args.timeout,
            )
            images = extract_chat_completion_images(response)
            save_openai_image(images[0], output_path, args.timeout)
            print(output_path)
            return 0

    if provider == GEMINI_NATIVE and transport == TRANSPORT_GEMINI_NATIVE:
        provider_defaults = defaults.get(GEMINI_NATIVE)
        if not isinstance(provider_defaults, dict):
            raise ValueError(f"Config key 'defaults.{GEMINI_NATIVE}' is invalid.")

        aspect_ratio = args.aspect_ratio or provider_defaults["aspect_ratio"]
        image_size = args.image_size or provider_defaults["image_size"]
        response = generate_gemini_native_image(
            target_config=target_config,
            prompt=args.prompt,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
            timeout=args.timeout,
        )
        save_gemini_image(response, output_path)
        print(output_path)
        return 0

    raise ValueError(
        f"Unsupported target configuration for '{args.target}': "
        f"provider={provider}, transport={transport}"
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)

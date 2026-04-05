#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from chat_client.core.api_utils import get_ollama_model_capabilities, get_provider_models


def _load_default_provider() -> dict:
    try:
        import data.config as config
    except Exception:
        return {}

    providers = getattr(config, "PROVIDERS", {})
    if not isinstance(providers, dict):
        return {}
    provider = providers.get("ollama", {})
    return provider if isinstance(provider, dict) else {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print Ollama capability detection for one or more models.",
    )
    parser.add_argument(
        "models",
        nargs="*",
        help="Model names to inspect. If omitted, uses models discovered from the Ollama provider.",
    )
    parser.add_argument(
        "--base-url",
        default="",
        help="Override the Ollama OpenAI-compatible base URL, e.g. http://localhost:11434/v1",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Override the Ollama API key. Defaults to the configured provider value.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of aligned text.",
    )
    return parser.parse_args()


def _resolve_provider(args: argparse.Namespace) -> dict:
    provider = dict(_load_default_provider())
    if args.base_url:
        provider["base_url"] = args.base_url
    if args.api_key:
        provider["api_key"] = args.api_key
    return provider


def _resolve_models(args: argparse.Namespace, provider: dict) -> list[str]:
    if args.models:
        return list(args.models)
    if not provider:
        return []
    return get_provider_models(provider)


def main() -> int:
    args = _parse_args()
    provider = _resolve_provider(args)
    models = _resolve_models(args, provider)

    if not provider.get("base_url"):
        print("Missing Ollama provider base_url. Configure data.config PROVIDERS['ollama'] or pass --base-url.", file=sys.stderr)
        return 2

    if not models:
        print("No models provided and no Ollama models were discovered.", file=sys.stderr)
        return 2

    results = {model: get_ollama_model_capabilities(provider, model) for model in models}

    if args.json:
        print(json.dumps(results, indent=2, sort_keys=True))
        return 0

    for model in models:
        capabilities = results[model]
        print(
            f"{model:<32} "
            f"images={'yes' if capabilities.get('supports_images') else 'no':<3} "
            f"tools={'yes' if capabilities.get('supports_tools') else 'no':<3} "
            f"thinking={'yes' if capabilities.get('supports_thinking') else 'no':<3}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

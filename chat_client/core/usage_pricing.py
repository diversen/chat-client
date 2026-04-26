from decimal import Decimal, ROUND_HALF_UP
from typing import Any


ZERO_DECIMAL = Decimal("0")
MICRO_UNIT = Decimal("1000000")
MONEY_QUANTIZE = Decimal("0.00000001")


def _coerce_int(value: Any) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 0
    return max(normalized, 0)


def _coerce_decimal_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "0"
    try:
        decimal_value = Decimal(text)
    except Exception:
        return "0"
    if decimal_value < ZERO_DECIMAL:
        return "0"
    return format(decimal_value.normalize(), "f")


def _read_attr_or_key(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _resolve_pricing_entry(entries: Any, model_name: str) -> dict[str, Any]:
    if not isinstance(entries, dict):
        return {}
    exact = entries.get(model_name)
    if isinstance(exact, dict):
        return exact
    wildcard = entries.get("*")
    if isinstance(wildcard, dict):
        return wildcard
    return {}


def resolve_model_pricing(pricing_config: Any, provider_name: str, model_name: str) -> dict[str, str]:
    if not isinstance(pricing_config, dict):
        return {
            "input_per_million": "0",
            "cached_input_per_million": "0",
            "output_per_million": "0",
            "currency": "USD",
        }

    provider_entries = _resolve_pricing_entry(pricing_config, provider_name)
    model_entries = _resolve_pricing_entry(provider_entries, model_name)

    if not model_entries and provider_name:
        wildcard_provider_entries = _resolve_pricing_entry(pricing_config, "*")
        model_entries = _resolve_pricing_entry(wildcard_provider_entries, model_name)

    currency = str(model_entries.get("currency", "USD") or "USD").strip() or "USD"
    return {
        "input_per_million": _coerce_decimal_text(model_entries.get("input_per_million")),
        "cached_input_per_million": _coerce_decimal_text(model_entries.get("cached_input_per_million")),
        "output_per_million": _coerce_decimal_text(model_entries.get("output_per_million")),
        "currency": currency,
    }


def compute_usage_cost(
    *,
    input_tokens: Any,
    cached_input_tokens: Any,
    output_tokens: Any,
    input_per_million: Any,
    cached_input_per_million: Any,
    output_per_million: Any,
) -> str:
    input_token_count = _coerce_int(input_tokens)
    cached_input_token_count = min(_coerce_int(cached_input_tokens), input_token_count)
    output_token_count = _coerce_int(output_tokens)
    uncached_input_token_count = max(input_token_count - cached_input_token_count, 0)

    try:
        input_rate = Decimal(str(input_per_million or "0"))
        cached_input_rate = Decimal(str(cached_input_per_million or "0"))
        output_rate = Decimal(str(output_per_million or "0"))
    except Exception:
        return "0"

    total = (
        (Decimal(uncached_input_token_count) / MICRO_UNIT) * input_rate
        + (Decimal(cached_input_token_count) / MICRO_UNIT) * cached_input_rate
        + (Decimal(output_token_count) / MICRO_UNIT) * output_rate
    )
    if total <= ZERO_DECIMAL:
        return "0"
    return format(total.quantize(MONEY_QUANTIZE, rounding=ROUND_HALF_UP), "f")


def normalize_chat_usage(value: Any) -> dict[str, Any]:
    usage = _read_attr_or_key(value, "usage", {})
    if not usage:
        return {
            "request_id": str(_read_attr_or_key(value, "id", "") or ""),
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "usage_source": "missing",
        }

    prompt_tokens = _coerce_int(_read_attr_or_key(usage, "prompt_tokens"))
    completion_tokens = _coerce_int(_read_attr_or_key(usage, "completion_tokens"))
    total_tokens = _coerce_int(_read_attr_or_key(usage, "total_tokens"))
    prompt_tokens_details = _read_attr_or_key(usage, "prompt_tokens_details", {})
    completion_tokens_details = _read_attr_or_key(usage, "completion_tokens_details", {})
    cached_tokens = _coerce_int(_read_attr_or_key(prompt_tokens_details, "cached_tokens"))
    reasoning_tokens = _coerce_int(_read_attr_or_key(completion_tokens_details, "reasoning_tokens"))

    return {
        "request_id": str(_read_attr_or_key(value, "id", "") or ""),
        "input_tokens": prompt_tokens,
        "cached_input_tokens": min(cached_tokens, prompt_tokens),
        "output_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "usage_source": "provider",
    }


def normalize_usage_payload(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "request_id": "",
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "usage_source": "missing",
        }

    usage = value.get("usage", {})
    if not isinstance(usage, dict):
        return {
            "request_id": str(value.get("id", "") or ""),
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
            "usage_source": "missing",
        }

    prompt_tokens = _coerce_int(usage.get("prompt_tokens"))
    completion_tokens = _coerce_int(usage.get("completion_tokens"))
    total_tokens = _coerce_int(usage.get("total_tokens"))
    prompt_tokens_details = usage.get("prompt_tokens_details", {})
    completion_tokens_details = usage.get("completion_tokens_details", {})
    cached_tokens = _coerce_int(prompt_tokens_details.get("cached_tokens") if isinstance(prompt_tokens_details, dict) else 0)
    reasoning_tokens = _coerce_int(
        completion_tokens_details.get("reasoning_tokens") if isinstance(completion_tokens_details, dict) else 0
    )

    return {
        "request_id": str(value.get("id", "") or ""),
        "input_tokens": prompt_tokens,
        "cached_input_tokens": min(cached_tokens, prompt_tokens),
        "output_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "usage_source": "provider",
    }

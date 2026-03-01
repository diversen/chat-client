import json
import os
from typing import Any

import httpx


GOOGLE_SEARCH_API_URL = "https://www.googleapis.com/customsearch/v1"


def _resolve_google_search_credentials() -> tuple[str, str]:
    api_key = os.getenv("GOOGLE_SEARCH_API_KEY", "").strip()
    cx = os.getenv("GOOGLE_SEARCH_CX", "").strip()
    return api_key, cx


def google_search(query: str, num_results: int = 5) -> str:
    """
    Search Google via Custom Search JSON API and return compact JSON results.
    """
    query = str(query or "").strip()
    if not query:
        return json.dumps({"error": "Missing required parameter: query"}, ensure_ascii=True)

    api_key, cx = _resolve_google_search_credentials()
    if not api_key or not cx:
        return json.dumps(
            {
                "error": (
                    "Google Search tool is not configured. "
                    "Set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_CX environment variables."
                )
            },
            ensure_ascii=True,
        )

    try:
        count = int(num_results)
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(count, 10))

    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": count,
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.get(GOOGLE_SEARCH_API_URL, params=params)
            response.raise_for_status()
            payload: Any = response.json()
    except httpx.TimeoutException:
        return json.dumps({"error": "Google Search request timed out"}, ensure_ascii=True)
    except httpx.HTTPStatusError as error:
        status_code = error.response.status_code
        detail = ""
        try:
            error_payload = error.response.json()
            detail = str(error_payload.get("error", {}).get("message", "")).strip()
        except Exception:
            detail = ""
        message = f"Google Search request failed with status {status_code}"
        if detail:
            message = f"{message}: {detail}"
        return json.dumps({"error": message}, ensure_ascii=True)
    except httpx.HTTPError:
        return json.dumps({"error": "Google Search request failed"}, ensure_ascii=True)
    except ValueError:
        return json.dumps({"error": "Google Search returned invalid JSON"}, ensure_ascii=True)

    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []

    results = []
    for item in items:
        if not isinstance(item, dict):
            continue
        results.append(
            {
                "title": str(item.get("title", "")),
                "link": str(item.get("link", "")),
                "snippet": str(item.get("snippet", "")),
            }
        )

    output = {
        "query": query,
        "result_count": len(results),
        "results": results,
    }
    return json.dumps(output, ensure_ascii=True)

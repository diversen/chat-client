import json
import re
from html import unescape
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

WIKIPEDIA_API_TIMEOUT_SECONDS = 20
WIKIPEDIA_USER_AGENT = "chat-client/0.1"


def _resolve_language(language: str | None) -> str:
    if not language:
        return "en"

    normalized = language.strip().lower()
    if not normalized:
        return "en"

    allowed = set("abcdefghijklmnopqrstuvwxyz-")
    if any(char not in allowed for char in normalized):
        raise ValueError("language must be a valid Wikipedia language code, e.g. 'en'.")

    return normalized


def _request_wikipedia_api(language: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"https://{language}.wikipedia.org/w/api.php?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": WIKIPEDIA_USER_AGENT})

    try:
        with urlopen(request, timeout=WIKIPEDIA_API_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise ValueError(f"Wikipedia request failed with HTTP {error.code}.") from error
    except URLError as error:
        raise ValueError(f"Wikipedia request failed: {error.reason}.") from error
    except json.JSONDecodeError as error:
        raise ValueError("Wikipedia response was not valid JSON.") from error

    if not isinstance(payload, dict):
        raise ValueError("Wikipedia response was not a JSON object.")
    return payload


def _clean_search_snippet(snippet: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(snippet or ""))
    return unescape(text)


def get_wikipedia_pages_json(title: str, language: str = "en") -> str:
    """
    Fetch plain-text article content from Wikipedia and return the query.pages JSON payload.
    """
    title = str(title or "").strip()
    if not title:
        raise ValueError("title is required and must be a non-empty string.")

    resolved_language = _resolve_language(language)
    payload = _request_wikipedia_api(
        resolved_language,
        {
            "action": "query",
            "prop": "extracts",
            "titles": title,
            "explaintext": "1",
            "redirects": "1",
            "format": "json",
            "formatversion": "2",
        },
    )

    query = payload.get("query", {})
    pages = query.get("pages") if isinstance(query, dict) else None
    if not isinstance(pages, list):
        raise ValueError("Wikipedia response did not include a valid query.pages payload.")

    return json.dumps(pages, ensure_ascii=False)


def search_wikipedia(query: str, language: str = "en", limit: int = 5) -> str:
    """
    Search Wikipedia article titles and return compact JSON results.
    """
    query = str(query or "").strip()
    if not query:
        raise ValueError("query is required and must be a non-empty string.")

    try:
        result_limit = int(limit)
    except (TypeError, ValueError):
        result_limit = 5
    result_limit = max(1, min(result_limit, 10))

    resolved_language = _resolve_language(language)
    payload = _request_wikipedia_api(
        resolved_language,
        {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": result_limit,
            "format": "json",
            "formatversion": "2",
        },
    )

    query_payload = payload.get("query", {})
    search_results = query_payload.get("search") if isinstance(query_payload, dict) else None
    if not isinstance(search_results, list):
        raise ValueError("Wikipedia response did not include a valid query.search payload.")

    results: list[dict[str, Any]] = []
    for item in search_results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", ""))
        pageid = item.get("pageid")
        result: dict[str, Any] = {
            "title": title,
            "snippet": _clean_search_snippet(item.get("snippet")),
        }
        if isinstance(pageid, int):
            result["pageid"] = pageid
        results.append(result)

    return json.dumps(
        {
            "query": query,
            "language": resolved_language,
            "result_count": len(results),
            "results": results,
        },
        ensure_ascii=False,
    )

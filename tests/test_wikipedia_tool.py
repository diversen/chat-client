import io
import json
from urllib.error import HTTPError, URLError
from unittest.mock import patch

import pytest

from chat_client.tools.wikipedia_tool import get_wikipedia_pages_json, search_wikipedia


class _WikipediaResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()
        return False


def _json_response(payload):
    return _WikipediaResponse(json.dumps(payload).encode("utf-8"))


def test_get_wikipedia_pages_json_returns_pages_payload():
    payload = {
        "query": {
            "pages": [
                {
                    "pageid": 9228,
                    "title": "Earth",
                    "extract": "Earth is the third planet from the Sun.",
                }
            ]
        }
    }

    with patch("chat_client.tools.wikipedia_tool.urlopen", return_value=_json_response(payload)) as urlopen_mock:
        result = get_wikipedia_pages_json(" Earth ")

    assert json.loads(result) == payload["query"]["pages"]
    request = urlopen_mock.call_args.args[0]
    assert request.full_url.startswith("https://en.wikipedia.org/w/api.php?")
    assert "titles=Earth" in request.full_url
    assert request.headers["User-agent"] == "chat-client/0.1"


def test_get_wikipedia_pages_json_supports_language_code():
    payload = {"query": {"pages": [{"title": "Jorden", "extract": "Jorden er..."}]}}

    with patch("chat_client.tools.wikipedia_tool.urlopen", return_value=_json_response(payload)) as urlopen_mock:
        get_wikipedia_pages_json("Jorden", language="DA")

    assert urlopen_mock.call_args.args[0].full_url.startswith("https://da.wikipedia.org/w/api.php?")


def test_search_wikipedia_returns_compact_results():
    payload = {
        "query": {
            "search": [
                {
                    "pageid": 9228,
                    "title": "Earth",
                    "snippet": '<span class="searchmatch">Earth</span> is a planet.',
                }
            ]
        }
    }

    with patch("chat_client.tools.wikipedia_tool.urlopen", return_value=_json_response(payload)) as urlopen_mock:
        result = search_wikipedia("earth", limit=50)

    assert json.loads(result) == {
        "query": "earth",
        "language": "en",
        "result_count": 1,
        "results": [{"title": "Earth", "snippet": "Earth is a planet.", "pageid": 9228}],
    }
    request_url = urlopen_mock.call_args.args[0].full_url
    assert "list=search" in request_url
    assert "srlimit=10" in request_url


@pytest.mark.parametrize(
    ("callable_", "kwargs", "message"),
    [
        (get_wikipedia_pages_json, {"title": ""}, "title is required"),
        (search_wikipedia, {"query": ""}, "query is required"),
        (get_wikipedia_pages_json, {"title": "Earth", "language": "en/evil"}, "language must be"),
    ],
)
def test_wikipedia_tools_validate_inputs(callable_, kwargs, message):
    with pytest.raises(ValueError, match=message):
        callable_(**kwargs)


def test_wikipedia_tool_reports_http_error():
    error = HTTPError(url="https://en.wikipedia.org/w/api.php", code=503, msg="Service Unavailable", hdrs=None, fp=None)

    with patch("chat_client.tools.wikipedia_tool.urlopen", side_effect=error):
        with pytest.raises(ValueError, match="HTTP 503"):
            get_wikipedia_pages_json("Earth")


def test_wikipedia_tool_reports_url_error():
    with patch("chat_client.tools.wikipedia_tool.urlopen", side_effect=URLError("network down")):
        with pytest.raises(ValueError, match="network down"):
            search_wikipedia("Earth")

import sys
import types
from pathlib import Path
import asyncio

import pytest
import httpx


def _install_test_config() -> None:
    data_dir = Path(__file__).resolve().parent / ".test-data"
    data_dir.mkdir(exist_ok=True)

    config_module = types.ModuleType("data.config")
    config_module.LOG_LEVEL = "INFO"
    config_module.RELOAD = False
    config_module.DATA_DIR = "tests/.test-data"
    config_module.DATABASE = Path("tests/.test-data/test.db")
    config_module.HOSTNAME_WITH_SCHEME = "https://test.invalid"
    config_module.SITE_NAME = "test.invalid"
    config_module.SESSION_SECRET_KEY = "test-secret-key"
    config_module.SESSION_COOKIE = "chat_client_test_session"
    config_module.SESSION_HTTPS_ONLY = False
    config_module.REQUEST_MAX_SIZE = 10 * 1024 * 1024
    config_module.USE_KATEX = False
    config_module.DEFAULT_MODEL = "test-model"
    config_module.PROVIDERS = {"test-provider": {"base_url": "http://test", "api_key": "test"}}
    config_module.MODELS = {"test-model": "test-provider"}
    config_module.VISION_MODELS = []
    config_module.SYSTEM_MESSAGE_MODELS = []
    config_module.TOOL_REGISTRY = {}
    config_module.LOCAL_TOOL_DEFINITIONS = []
    config_module.TOOL_MODELS = []
    config_module.TOOL_CALLS_COLLAPSED_BY_DEFAULT = True
    config_module.MCP_SERVER_URL = ""
    config_module.MCP_AUTH_TOKEN = ""
    config_module.MCP_TIMEOUT_SECONDS = 5.0
    config_module.MCP_TOOLS_CACHE_SECONDS = 0.0
    config_module.PYTHON_TOOL_DOCKER_IMAGE = "secure-python"

    class ConfigSMTP:
        HOST = "smtp.example.com"
        PORT = 587
        USERNAME = "test-user"
        PASSWORD = "test-password"
        DEFAULT_FROM = "Chat <test@example.com>"

    config_module.ConfigSMTP = ConfigSMTP

    def _missing_attr(name: str):
        raise AttributeError(f"Test config missing attribute: {name}")

    config_module.__getattr__ = _missing_attr

    data_package = sys.modules.setdefault("data", types.ModuleType("data"))
    data_package.__path__ = [str(Path(__file__).resolve().parent.parent / "data")]
    data_package.config = config_module
    sys.modules["data.config"] = config_module


_install_test_config()

collect_ignore = [
    "test_runner.py",
    "test_stream.py",
]


@pytest.fixture
def app():
    from chat_client.main import app

    return app


class SyncASGITestClient:
    def __init__(self, app, base_url: str = "http://testserver"):
        self.app = app
        self.base_url = base_url
        self.cookies = httpx.Cookies()

    async def _request(self, method: str, url: str, **kwargs):
        follow_redirects = kwargs.pop("follow_redirects", False)
        request_cookies = kwargs.pop("cookies", None)
        transport = httpx.ASGITransport(app=self.app)
        merged_cookies = httpx.Cookies(self.cookies)
        if request_cookies:
            for key, value in request_cookies.items():
                merged_cookies.set(key, value)

        async with httpx.AsyncClient(
            transport=transport,
            base_url=self.base_url,
            follow_redirects=follow_redirects,
            cookies=merged_cookies,
        ) as client:
            response = await client.request(method, url, **kwargs)
            self.cookies.update(client.cookies)
            return response

    def request(self, method: str, url: str, **kwargs):
        return asyncio.run(self._request(method, url, **kwargs))

    def get(self, url: str, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self.request("POST", url, **kwargs)

    def close(self):
        return None


@pytest.fixture
def client(app):
    test_client = SyncASGITestClient(app)
    yield test_client
    test_client.close()


@pytest.fixture(autouse=True)
def stub_common_context(monkeypatch):
    async def fake_get_context(request, variables):
        base = {
            "request": request,
            "logged_in": False,
            "user_id": False,
            "profile": {},
            "version": "test-version",
            "use_katex": False,
            "prompts": [],
            "flash_messages": [],
        }
        return {**base, **variables}

    async def fake_list_prompts(user_id):
        return []

    async def fake_get_profile(user_id):
        return {}

    monkeypatch.setattr("chat_client.core.base_context.get_context", fake_get_context)
    monkeypatch.setattr("chat_client.endpoints.user_endpoints.get_context", fake_get_context)
    monkeypatch.setattr("chat_client.endpoints.prompt_endpoints.get_context", fake_get_context)
    monkeypatch.setattr("chat_client.repositories.prompt_repository.list_prompts", fake_list_prompts)
    monkeypatch.setattr("chat_client.repositories.user_repository.get_profile", fake_get_profile)

import asyncio
import logging
from types import SimpleNamespace

from chat_client.core import chat_service


class DummyOpenAIError(Exception):
    def __init__(self, message: str, body=None, response=None):
        super().__init__(message)
        self.body = body
        self.response = response


class DummyResponse:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


def test_map_openai_error_message_for_image_modality_string():
    error = DummyOpenAIError("Image input modality is not enabled for models/gemma-3n-e4b-it")
    assert chat_service.map_openai_error_message(error) == chat_service.IMAGE_MODALITY_ERROR_MESSAGE


def test_map_openai_error_message_for_image_modality_in_body():
    error = DummyOpenAIError(
        "Error code: 400",
        body=[{"error": {"message": "Image input modality is not enabled for model"}}],
    )
    assert chat_service.map_openai_error_message(error) == chat_service.IMAGE_MODALITY_ERROR_MESSAGE


def test_map_openai_error_message_defaults_to_generic_message():
    error = DummyOpenAIError("Some unrelated provider error")
    assert chat_service.map_openai_error_message(error) == chat_service.GENERIC_OPENAI_ERROR_MESSAGE


def test_map_openai_error_message_for_image_modality_in_response_json():
    error = DummyOpenAIError(
        "Error code: 400",
        response=DummyResponse({"error": {"message": "Image input modality is not enabled"}}),
    )
    assert chat_service.map_openai_error_message(error) == chat_service.IMAGE_MODALITY_ERROR_MESSAGE


class DummyRequest:
    def __init__(self, disconnected_after_calls: int = 999):
        self.calls = 0
        self.disconnected_after_calls = disconnected_after_calls

    async def is_disconnected(self):
        self.calls += 1
        return self.calls >= self.disconnected_after_calls


class DummyStream:
    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    def __iter__(self):
        return iter(self._chunks)

    def close(self):
        self.closed = True


def _chunk(content: str, finish_reason=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=None),
                finish_reason=finish_reason,
            )
        ],
        model_dump=lambda: {"choices": [{"delta": {"content": content}}]},
    )


def test_chat_response_stream_closes_provider_stream_when_client_disconnects():
    stream = DummyStream([_chunk("hello"), _chunk("world")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: stream)))
    request = DummyRequest(disconnected_after_calls=1)

    async def _get_profile(_user_id):
        return {"system_message": ""}

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
            logged_in=1,
            get_profile=_get_profile,
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())
    assert chunks == []
    assert stream.closed is True


def test_chat_response_stream_closes_provider_stream_after_normal_completion():
    stream = DummyStream([_chunk("hello", finish_reason="stop")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: stream)))
    request = DummyRequest(disconnected_after_calls=999)

    async def _get_profile(_user_id):
        return {"system_message": ""}

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
            logged_in=1,
            get_profile=_get_profile,
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())
    assert len(chunks) == 1
    assert "hello" in chunks[0]
    assert stream.closed is True

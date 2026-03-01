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


def _chunk(content: str | None = "", finish_reason=None, tool_calls=None):
    delta_payload = {}
    if content is not None:
        delta_payload["content"] = content
    if tool_calls is not None:
        serialized_tool_calls = []
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            serialized_tool_calls.append(
                {
                    "index": getattr(tool_call, "index", None),
                    "id": getattr(tool_call, "id", None),
                    "type": getattr(tool_call, "type", None),
                    "function": {
                        "name": getattr(function, "name", None),
                        "arguments": getattr(function, "arguments", None),
                    },
                }
            )
        delta_payload["tool_calls"] = serialized_tool_calls
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
                finish_reason=finish_reason,
            )
        ],
        model_dump=lambda: {"choices": [{"delta": delta_payload}]},
    )


def test_chat_response_stream_closes_provider_stream_when_client_disconnects():
    stream = DummyStream([_chunk("hello"), _chunk("world")])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: stream)))
    request = DummyRequest(disconnected_after_calls=1)

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
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

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hi"}],
            model="test-model",
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


def test_chat_response_stream_uses_streaming_tool_loop():
    first_stream = DummyStream(
        [
            _chunk(
                None,
                tool_calls=[
                    SimpleNamespace(
                        index=0,
                        id="call_utc",
                        type="function",
                        function=SimpleNamespace(name="get_locale_date_time", arguments='{"timezone":"UTC"}'),
                    ),
                    SimpleNamespace(
                        index=1,
                        id="call_ny",
                        type="function",
                        function=SimpleNamespace(
                            name="get_locale_date_time",
                            arguments='{"timezone":"America/New_York"}',
                        ),
                    ),
                ],
            ),
            _chunk("", finish_reason="tool_calls"),
        ]
    )
    final_stream = DummyStream([_chunk("comparison", finish_reason="stop")])
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return first_stream if len(create_calls) == 1 else final_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)
    executed_calls = []

    def _tool_executor(tool_call):
        executed_calls.append(tool_call)
        timezone = chat_service.parse_tool_arguments(tool_call, logging.getLogger("test")).get("timezone", "")
        return f"time for {timezone}"

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "compare times"}],
            model="tool-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=["tool-model"],
            tools_loader=lambda: [{"type": "function", "function": {"name": "get_locale_date_time"}}],
            tool_executor=_tool_executor,
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 2
    assert create_calls[0]["stream"] is True
    assert "tools" in create_calls[0]
    assert create_calls[1]["stream"] is True
    assert "tools" in create_calls[1]
    assert len(executed_calls) == 2
    assert chat_service.parse_tool_arguments(executed_calls[0], logging.getLogger("test")) == {"timezone": "UTC"}
    assert chat_service.parse_tool_arguments(executed_calls[1], logging.getLogger("test")) == {"timezone": "America/New_York"}
    second_call_messages = create_calls[1]["messages"]
    assert second_call_messages[1]["role"] == "assistant"
    assert len(second_call_messages[1]["tool_calls"]) == 2
    assert second_call_messages[2]["tool_call_id"] == "call_utc"
    assert second_call_messages[3]["tool_call_id"] == "call_ny"
    assert any('"tool_call"' in chunk for chunk in chunks)
    assert any("comparison" in chunk for chunk in chunks)
    assert first_stream.closed is True
    assert final_stream.closed is True


def test_chat_response_stream_tools_model_without_tool_calls_streams_on_first_call():
    final_stream = DummyStream([_chunk("streamed final", finish_reason="stop")])
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return final_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hello"}],
            model="tool-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=["tool-model"],
            tools_loader=lambda: [{"type": "function", "function": {"name": "get_locale_date_time"}}],
            tool_executor=lambda _tool_call: "",
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 1
    assert create_calls[0]["stream"] is True
    assert "tools" in create_calls[0]
    assert len(chunks) == 1
    assert "streamed final" in chunks[0]
    assert final_stream.closed is True

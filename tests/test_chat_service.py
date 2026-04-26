import asyncio
import threading
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


def test_normalize_reasoning_effort_accepts_supported_values():
    assert chat_service.normalize_reasoning_effort("LOW") == "low"
    assert chat_service.normalize_reasoning_effort("medium") == "medium"
    assert chat_service.normalize_reasoning_effort("high") == "high"
    assert chat_service.normalize_reasoning_effort("none") == ""
    assert chat_service.normalize_reasoning_effort("none", allow_none=True) == "none"
    assert chat_service.normalize_reasoning_effort("") == ""


def test_normalize_reasoning_effort_for_provider_allows_none_only_for_ollama():
    assert chat_service.normalize_reasoning_effort_for_provider("none", "ollama") == "none"
    assert chat_service.normalize_reasoning_effort_for_provider("none", "openai") == ""


def test_build_chat_completion_create_kwargs_shapes_provider_options():
    create_kwargs = chat_service.build_chat_completion_create_kwargs(
        model="qwen3:latest",
        messages=[{"role": "user", "content": "hello"}],
        provider_name="ollama",
        reasoning_effort="none",
        include_usage_in_stream=True,
        tool_definitions=[{"type": "function", "function": {"name": "noop"}}],
    )

    assert create_kwargs == {
        "model": "qwen3:latest",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": True,
        "reasoning_effort": "none",
        "stream_options": {"include_usage": True},
        "tools": [{"type": "function", "function": {"name": "noop"}}],
    }


def test_summarize_messages_for_log_includes_attachment_paths():
    summary = chat_service.summarize_messages_for_log(
        [
            {
                "role": "user",
                "content": "Read these files",
                "attachments": [
                    {"attachment_id": 1, "name": "notes.txt"},
                    {"attachment_id": 2, "name": "report.csv"},
                ],
            }
        ]
    )

    assert summary["attachment_count"] == 2
    assert summary["attachment_paths"] == ["/mnt/data/notes.txt", "/mnt/data/report.csv"]


def test_summarize_last_user_message_for_log_includes_attached_file_path_note():
    summary = chat_service.summarize_last_user_message_for_log(
        [
            {"role": "system", "content": "You are helpful."},
            {
                "role": "user",
                "content": ("Please inspect the file.\n\nAttached files available to tools:\n- /mnt/data/0059_cipher.txt"),
            },
        ]
    )

    assert "/mnt/data/0059_cipher.txt" in summary["last_user_message_full"]


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


def _chunk(content: str | None = "", finish_reason=None, tool_calls=None, reasoning: str | None = None, usage=None, chunk_id="chunk-id"):
    delta_payload = {}
    if content is not None:
        delta_payload["content"] = content
    if reasoning is not None:
        delta_payload["reasoning"] = reasoning
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
    choices = []
    if content is not None or tool_calls is not None or reasoning is not None or finish_reason is not None:
        choices.append(
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls, reasoning=reasoning),
                finish_reason=finish_reason,
            )
        )
    payload = {"id": chunk_id, "choices": [{"delta": delta_payload}] if choices else []}
    if usage is not None:
        payload["usage"] = usage
    return SimpleNamespace(
        id=chunk_id,
        choices=choices,
        usage=usage,
        model_dump=lambda: payload,
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


def test_chat_response_stream_persists_provider_usage_per_round():
    stream = DummyStream(
        [
            _chunk("hello", finish_reason="stop", chunk_id="cmpl-1"),
            _chunk(
                None,
                usage={
                    "prompt_tokens": 1200,
                    "completion_tokens": 45,
                    "total_tokens": 1245,
                    "prompt_tokens_details": {"cached_tokens": 1000},
                    "completion_tokens_details": {"reasoning_tokens": 7},
                },
                chunk_id="cmpl-1",
            ),
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: stream)))
    request = DummyRequest(disconnected_after_calls=999)
    persisted_usage = []

    async def _persist_usage_event(**usage_data):
        persisted_usage.append(usage_data)

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
            turn_id="turn-usage",
            provider_name="openai",
            include_usage_in_stream=True,
            persist_usage_event=_persist_usage_event,
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())
    assert len(chunks) == 2
    assert persisted_usage == [
        {
            "turn_id": "turn-usage",
            "round_index": 1,
            "provider": "openai",
            "model": "test-model",
            "call_type": "chat",
            "request_id": "cmpl-1",
            "input_tokens": 1200,
            "cached_input_tokens": 1000,
            "output_tokens": 45,
            "total_tokens": 1245,
            "reasoning_tokens": 7,
            "usage_source": "provider",
        }
    ]


def test_chat_response_stream_ignores_tool_calls_for_non_tool_models():
    stream = DummyStream(
        [
            _chunk(
                None,
                tool_calls=[
                    SimpleNamespace(
                        index=0,
                        id="call_ignored",
                        type="function",
                        function=SimpleNamespace(name="python_hardened", arguments='{"code":"print(1)"}'),
                    )
                ],
            ),
            _chunk("", finish_reason="tool_calls"),
        ]
    )
    create_calls = []
    executed_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    def _tool_executor(tool_call):
        executed_calls.append(tool_call)
        return "should not run"

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "use python_hardened"}],
            model="plain-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=["tool-model"],
            tools_loader=lambda: [{"type": "function", "function": {"name": "python_hardened"}}],
            tool_executor=_tool_executor,
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 1
    assert "tools" not in create_calls[0]
    assert executed_calls == []
    assert any('"tool_calls"' in chunk for chunk in chunks)
    assert not any('"tool_status"' in chunk for chunk in chunks)
    assert stream.closed is True


def test_parse_tool_arguments_raises_on_invalid_json():
    tool_call = {"function": {"name": "python_hardened", "arguments": '{"code": "print(1)"'}}

    try:
        chat_service.parse_tool_arguments(tool_call, logging.getLogger("test"))
        assert False, "Expected ToolArgumentsError"
    except chat_service.ToolArgumentsError as error:
        assert str(error) == 'Tool "python_hardened" was called with invalid JSON arguments.'


def test_parse_tool_arguments_requires_json_object():
    tool_call = {"function": {"name": "python_hardened", "arguments": '["print(1)"]'}}

    try:
        chat_service.parse_tool_arguments(tool_call, logging.getLogger("test"))
        assert False, "Expected ToolArgumentsError"
    except chat_service.ToolArgumentsError as error:
        assert str(error) == 'Tool "python_hardened" requires JSON object arguments.'


def test_validate_tool_arguments_checks_required_unexpected_and_type():
    schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
        },
        "required": ["code"],
        "additionalProperties": False,
    }

    try:
        chat_service.validate_tool_arguments({}, schema, "python_hardened")
        assert False, "Expected required argument failure"
    except chat_service.ToolArgumentsError as error:
        assert str(error) == 'Tool "python_hardened" requires argument "code".'

    try:
        chat_service.validate_tool_arguments({"code": 1}, schema, "python_hardened")
        assert False, "Expected type validation failure"
    except chat_service.ToolArgumentsError as error:
        assert str(error) == 'Tool "python_hardened" requires argument "code" of type string.'

    try:
        chat_service.validate_tool_arguments({"code": "print(1)", "x": 1}, schema, "python_hardened")
        assert False, "Expected unexpected argument failure"
    except chat_service.ToolArgumentsError as error:
        assert str(error) == 'Tool "python_hardened" received unexpected arguments: "x".'


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


def test_chat_response_stream_passes_reasoning_effort_for_openai_provider():
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
            model="test-model",
            reasoning_effort="high",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            provider_name="openai",
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 1
    assert create_calls[0]["reasoning_effort"] == "high"
    assert "streamed final" in chunks[0]
    assert final_stream.closed is True


def test_chat_response_stream_passes_reasoning_effort_for_ollama_provider():
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
            model="test-model",
            reasoning_effort="high",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            provider_name="ollama",
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 1
    assert create_calls[0]["reasoning_effort"] == "high"
    assert "streamed final" in chunks[0]
    assert final_stream.closed is True


def test_chat_response_stream_passes_none_reasoning_effort_for_ollama_provider():
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
            model="test-model",
            reasoning_effort="none",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            provider_name="ollama",
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 1
    assert create_calls[0]["reasoning_effort"] == "none"
    assert "streamed final" in chunks[0]
    assert final_stream.closed is True


def test_chat_response_stream_retries_once_for_reasoning_only_incomplete_stream():
    first_stream = DummyStream([_chunk("", reasoning="Thinking")])
    second_stream = DummyStream([_chunk("final answer", finish_reason="stop")])
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return first_stream if len(create_calls) == 1 else second_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hello"}],
            model="test-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            empty_answer_retry_count=1,
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 2
    assert any('"reasoning": "Thinking"' in chunk for chunk in chunks)
    assert any("final answer" in chunk for chunk in chunks)
    assert not any(chat_service.INCOMPLETE_STREAM_ERROR_MESSAGE in chunk for chunk in chunks)
    assert first_stream.closed is True
    assert second_stream.closed is True


def test_chat_response_stream_returns_error_after_second_reasoning_only_incomplete_stream():
    first_stream = DummyStream([_chunk("", reasoning="Thinking")])
    second_stream = DummyStream([_chunk("", reasoning="Still thinking")])
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return first_stream if len(create_calls) == 1 else second_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hello"}],
            model="test-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            empty_answer_retry_count=1,
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 2
    assert any(chat_service.INCOMPLETE_STREAM_ERROR_MESSAGE in chunk for chunk in chunks)
    assert first_stream.closed is True
    assert second_stream.closed is True


def test_chat_response_stream_retries_empty_stopped_answer_when_enabled():
    first_stream = DummyStream([_chunk("", reasoning="Thinking", finish_reason="stop")])
    second_stream = DummyStream([_chunk("final answer", finish_reason="stop")])
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return first_stream if len(create_calls) == 1 else second_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hello"}],
            model="test-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=[],
            tools_loader=lambda: [],
            tool_executor=lambda _tool_call: "",
            empty_answer_retry_count=1,
            retry_on_empty_answer_stop=True,
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 2
    assert any('"reasoning": "Thinking"' in chunk for chunk in chunks)
    assert any("final answer" in chunk for chunk in chunks)
    assert first_stream.closed is True
    assert second_stream.closed is True


def test_chat_response_stream_does_not_retry_empty_stopped_answer_by_default():
    stream = DummyStream([_chunk("", reasoning="Thinking", finish_reason="stop")])
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "hello"}],
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

    assert len(create_calls) == 1
    assert any('"reasoning": "Thinking"' in chunk for chunk in chunks)
    assert stream.closed is True


def test_chat_response_stream_respects_configured_max_chat_loop_rounds():
    first_stream = DummyStream(
        [
            _chunk(
                None,
                tool_calls=[
                    SimpleNamespace(
                        index=0,
                        id="call_once",
                        type="function",
                        function=SimpleNamespace(name="python_hardened", arguments='{"code":"print(1)"}'),
                    )
                ],
            ),
            _chunk("", finish_reason="tool_calls"),
        ]
    )
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return first_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "use python_hardened"}],
            model="tool-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=["tool-model"],
            tools_loader=lambda: [{"type": "function", "function": {"name": "python_hardened"}}],
            tool_executor=lambda _tool_call: "1",
            max_chat_loop_rounds=1,
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 1
    assert any("Tool loop exceeded maximum rounds" in chunk for chunk in chunks)
    assert first_stream.closed is True


def test_chat_response_stream_keeps_tool_execution_errors_inside_chat():
    first_stream = DummyStream(
        [
            _chunk(
                None,
                tool_calls=[
                    SimpleNamespace(
                        index=0,
                        id="call_bad_tool",
                        type="function",
                        function=SimpleNamespace(name="stateful_python", arguments='{"code":"print(1)"}'),
                    )
                ],
            ),
            _chunk("", finish_reason="tool_calls"),
        ]
    )
    final_stream = DummyStream([_chunk("fallback answer", finish_reason="stop")])
    create_calls = []

    def _create(**kwargs):
        create_calls.append(kwargs)
        return first_stream if len(create_calls) == 1 else final_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    def _tool_executor(_tool_call):
        raise chat_service.ToolNotFoundError('Tool "stateful_python" does not exist.')

    async def _run():
        chunks = []
        async for chunk in chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "use the tool"}],
            model="tool-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=["tool-model"],
            tools_loader=lambda: [{"type": "function", "function": {"name": "python_hardened"}}],
            tool_executor=_tool_executor,
            logger=logging.getLogger("test"),
        ):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_run())

    assert len(create_calls) == 2
    assert any('"error_text": "Tool \\"stateful_python\\" does not exist."' in chunk for chunk in chunks)
    assert any('"tool_call_id": "call_bad_tool"' in chunk for chunk in chunks)
    assert any("fallback answer" in chunk for chunk in chunks)
    second_call_messages = create_calls[1]["messages"]
    assert second_call_messages[1]["role"] == "assistant"
    assert second_call_messages[2] == {
        "role": "tool",
        "tool_call_id": "call_bad_tool",
        "content": 'Tool "stateful_python" does not exist.',
    }
    assert first_stream.closed is True
    assert final_stream.closed is True


def test_chat_response_stream_yields_tool_status_before_blocking_sync_tool_completes():
    first_stream = DummyStream(
        [
            _chunk(
                None,
                tool_calls=[
                    SimpleNamespace(
                        index=0,
                        id="call_sleep",
                        type="function",
                        function=SimpleNamespace(name="python_relaxed", arguments='{"code":"import time; time.sleep(10)"}'),
                    )
                ],
            ),
            _chunk("", finish_reason="tool_calls"),
        ]
    )
    final_stream = DummyStream([_chunk("done", finish_reason="stop")])
    create_calls = []
    release_tool = threading.Event()

    def _create(**kwargs):
        create_calls.append(kwargs)
        return first_stream if len(create_calls) == 1 else final_stream

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=_create)))
    request = DummyRequest(disconnected_after_calls=999)

    def _tool_executor(_tool_call):
        release_tool.wait(timeout=1.0)
        return "slept"

    async def _run():
        stream = chat_service.chat_response_stream(
            request,
            messages=[{"role": "user", "content": "sleep"}],
            model="tool-model",
            openai_client_cls=lambda **_: client,
            provider_info_resolver=lambda _model: {},
            tool_models=["tool-model"],
            tools_loader=lambda: [{"type": "function", "function": {"name": "python_relaxed"}}],
            tool_executor=_tool_executor,
            logger=logging.getLogger("test"),
        )

        streamed_tool_call_chunk = await asyncio.wait_for(anext(stream), timeout=0.2)
        streamed_finish_chunk = await asyncio.wait_for(anext(stream), timeout=0.2)
        first_chunk = await asyncio.wait_for(anext(stream), timeout=0.2)
        release_tool.set()
        remaining_chunks = []
        async for chunk in stream:
            remaining_chunks.append(chunk)
        return streamed_tool_call_chunk, streamed_finish_chunk, first_chunk, remaining_chunks

    streamed_tool_call_chunk, streamed_finish_chunk, first_chunk, remaining_chunks = asyncio.run(_run())

    assert '"tool_calls"' in streamed_tool_call_chunk
    assert '"content": ""' in streamed_finish_chunk
    assert '"tool_status"' in first_chunk
    assert '"phase": "start"' in first_chunk
    assert '"tool_name": "python_relaxed"' in first_chunk
    assert any('"tool_call_id": "call_sleep"' in chunk for chunk in remaining_chunks)
    assert any("done" in chunk for chunk in remaining_chunks)
    assert first_stream.closed is True
    assert final_stream.closed is True

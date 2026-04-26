from chat_client.core import exceptions_validation
from chat_client.core.attachments import make_image_attachment_ref
from chat_client.repositories import attachment_repository
from chat_client.repositories import image_repository

from chat_client.models import (
    Dialog,
    Message,
    Image,
    MessageImage,
    Attachment,
    MessageAttachment,
    ToolCallEvent,
    AssistantTurnEvent,
    LlmUsageEvent,
)
from chat_client.database.db_session import async_session
import uuid
import logging
import json
from decimal import Decimal
from sqlalchemy import select, func, update, delete, exists, or_

logger: logging.Logger = logging.getLogger(__name__)

DIALOGS_PER_PAGE = 20


async def _touch_dialog_in_session(session, user_id: int, dialog_id: str) -> None:
    await session.execute(
        update(Dialog)
        .where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        .values(updated=func.current_timestamp())
    )


async def _next_dialog_sequence_index(session, user_id: int, dialog_id: str) -> int:
    return await _next_dialog_sequence_index_in_session(session, user_id, dialog_id)


async def _next_dialog_sequence_index_in_session(session, user_id: int, dialog_id: str) -> int:
    message_max_stmt = select(func.max(Message.sequence_index)).where(
        Message.dialog_id == dialog_id,
        Message.user_id == user_id,
    )
    tool_max_stmt = select(func.max(ToolCallEvent.sequence_index)).where(
        ToolCallEvent.dialog_id == dialog_id,
        ToolCallEvent.user_id == user_id,
    )
    assistant_turn_max_stmt = select(func.max(AssistantTurnEvent.sequence_index)).where(
        AssistantTurnEvent.dialog_id == dialog_id,
        AssistantTurnEvent.user_id == user_id,
    )
    message_max_result = await session.execute(message_max_stmt)
    tool_max_result = await session.execute(tool_max_stmt)
    assistant_turn_max_result = await session.execute(assistant_turn_max_stmt)
    message_max = message_max_result.scalar_one_or_none()
    tool_max = tool_max_result.scalar_one_or_none()
    assistant_turn_max = assistant_turn_max_result.scalar_one_or_none()
    max_sequence = max(int(message_max or 0), int(tool_max or 0), int(assistant_turn_max or 0))
    return max_sequence + 1


async def create_dialog(user_id: int, title: str):

    async with async_session() as session:
        dialog_id = str(uuid.uuid4())
        new_dialog = Dialog(
            dialog_id=dialog_id,
            user_id=user_id,
            title=title,
        )
        session.add(new_dialog)
        await session.commit()

        return dialog_id


async def update_dialog_title(user_id: int, dialog_id: str, title: str):

    normalized_title = str(title).strip()
    if not normalized_title:
        raise exceptions_validation.UserValidate("Dialog title cannot be empty")

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise exceptions_validation.UserValidate("Dialog not found or not owned by user")

        dialog.title = normalized_title
        dialog.updated = func.current_timestamp()
        await session.commit()

        return {
            "dialog_id": str(dialog.dialog_id),
            "title": dialog.title,
        }


async def create_message(
    user_id: int,
    dialog_id: str,
    role: str,
    content: str,
    images: list[dict[str, str | int]] | None = None,
    attachments: list[dict[str, str | int]] | None = None,
):

    async with async_session() as session:
        sequence_index = await _next_dialog_sequence_index(session, user_id, dialog_id)
        new_message = Message(
            role=role,
            content=content,
            dialog_id=dialog_id,
            user_id=user_id,
            sequence_index=sequence_index,
        )
        session.add(new_message)
        await session.flush()
        message_id = new_message.message_id
        if message_id is None:
            raise RuntimeError("Failed to create message id")

        for image in images or []:
            attachment_id = image.get("attachment_id")
            try:
                normalized_attachment_id = int(attachment_id)
            except (TypeError, ValueError):
                normalized_attachment_id = 0

            if normalized_attachment_id > 0:
                attachment_stmt = select(Attachment).where(
                    Attachment.attachment_id == normalized_attachment_id,
                    Attachment.user_id == user_id,
                )
                attachment_result = await session.execute(attachment_stmt)
                existing_attachment = attachment_result.scalar_one_or_none()
                if existing_attachment is None:
                    continue

                new_image = Image(data_url=make_image_attachment_ref(normalized_attachment_id))
                session.add(new_image)
                await session.flush()
                image_id = new_image.image_id
                if image_id is None:
                    continue
                session.add(
                    MessageImage(
                        message_id=message_id,
                        image_id=image_id,
                    )
                )
                continue

            data_url = str(image.get("data_url", "")).strip()
            if not data_url.startswith("data:image/"):
                continue

            new_image = Image(data_url=data_url)
            session.add(new_image)
            await session.flush()
            image_id = new_image.image_id
            if image_id is None:
                continue
            session.add(
                MessageImage(
                    message_id=message_id,
                    image_id=image_id,
                )
            )

        for attachment in attachments or []:
            attachment_id = attachment.get("attachment_id")
            if attachment_id is None:
                continue
            try:
                normalized_attachment_id = int(attachment_id)
            except (TypeError, ValueError):
                continue

            attachment_stmt = select(Attachment).where(
                Attachment.attachment_id == normalized_attachment_id,
                Attachment.user_id == user_id,
            )
            attachment_result = await session.execute(attachment_stmt)
            existing_attachment = attachment_result.scalar_one_or_none()
            if existing_attachment is None:
                continue

            session.add(
                MessageAttachment(
                    message_id=message_id,
                    attachment_id=normalized_attachment_id,
                )
            )

        await _touch_dialog_in_session(session, user_id, dialog_id)
        await session.commit()
        await session.refresh(new_message)

        return new_message.message_id


async def get_dialog(user_id: int, dialog_id: str):

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise exceptions_validation.UserValidate("Dialog not found or not owned by user")

        assert dialog.created is not None

        return {
            "dialog_id": str(dialog.dialog_id),
            "title": dialog.title,
            "created": dialog.created.isoformat(),
        }


async def get_messages(user_id: int, dialog_id: str):

    async with async_session() as session:
        stmt = (
            select(Message)
            .where(Message.dialog_id == dialog_id, Message.user_id == user_id, Message.active == 1)
            .order_by(Message.sequence_index.asc(), Message.message_id.asc())
            .limit(1000)
        )
        result = await session.execute(stmt)
        messages = result.scalars().all()

        message_ids = [m.message_id for m in messages if m.message_id is not None]
        images_by_message: dict[int, list[dict[str, str]]] = {}
        attachments_by_message: dict[int, list[dict[str, str | int]]] = {}
        if message_ids:
            images_by_message = await image_repository.load_message_images(
                session,
                message_ids=message_ids,
            )
            attachments_by_message = await attachment_repository.load_message_attachments(
                session,
                message_ids=message_ids,
            )

        combined_rows: list[tuple] = []
        for m in messages:
            assert m.created is not None
            message_id = m.message_id
            if message_id is None:
                continue
            if m.role not in {"user", "system"}:
                continue
            combined_rows.append(
                (
                    int(m.sequence_index),
                    {
                        "message_id": str(message_id),
                        "role": m.role,
                        "content": m.content,
                        "images": images_by_message.get(message_id, []),
                        "attachments": attachments_by_message.get(message_id, []),
                        "created": m.created.isoformat(),
                    },
                )
            )

        assistant_turn_stmt = (
            select(AssistantTurnEvent)
            .where(AssistantTurnEvent.dialog_id == dialog_id, AssistantTurnEvent.user_id == user_id)
            .order_by(
                AssistantTurnEvent.sequence_index.asc(),
                AssistantTurnEvent.assistant_turn_event_id.asc(),
            )
        )
        assistant_turn_result = await session.execute(assistant_turn_stmt)
        assistant_turn_events = assistant_turn_result.scalars().all()

        turns_by_id: dict[str, dict] = {}
        ordered_turn_ids: list[str] = []
        for event in assistant_turn_events:
            assert event.created is not None
            turn_id = str(event.turn_id or "").strip()
            if not turn_id:
                continue
            if turn_id not in turns_by_id:
                turns_by_id[turn_id] = {
                    "message_id": None,
                    "role": "assistant_turn",
                    "turn_id": turn_id,
                    "events": [],
                    "created": event.created.isoformat(),
                    "_sequence_index": int(event.sequence_index),
                }
                ordered_turn_ids.append(turn_id)
            turns_by_id[turn_id]["events"].append(
                {
                    "event_type": event.event_type,
                    "reasoning_text": event.reasoning_text,
                    "content_text": event.content_text,
                    "tool_call_id": event.tool_call_id,
                    "tool_name": event.tool_name,
                    "arguments_json": event.arguments_json,
                    "result_text": event.result_text,
                    "error_text": event.error_text,
                }
            )

        for turn_id in ordered_turn_ids:
            turn = turns_by_id[turn_id]
            combined_rows.append((int(turn.pop("_sequence_index")), turn))

        combined_rows.sort(key=lambda row: row[0])
        return [row[1] for row in combined_rows]


async def create_assistant_turn_events(
    user_id: int,
    dialog_id: str,
    turn_id: str,
    events: list[dict],
):
    normalized_turn_id = str(turn_id).strip()
    if not normalized_turn_id:
        raise exceptions_validation.UserValidate("turn_id is required")
    if not events:
        return

    async with async_session() as session:
        next_sequence_index = await _next_dialog_sequence_index_in_session(session, user_id, dialog_id)
        for event in events:
            event_type = str(event.get("event_type", "")).strip()
            if event_type not in {"assistant_segment", "tool_call"}:
                continue
            assistant_turn_event = AssistantTurnEvent(
                user_id=user_id,
                dialog_id=dialog_id,
                turn_id=normalized_turn_id,
                sequence_index=next_sequence_index,
                event_type=event_type,
                reasoning_text=str(event.get("reasoning_text", "")),
                content_text=str(event.get("content_text", "")),
                tool_call_id=str(event.get("tool_call_id", "")),
                tool_name=str(event.get("tool_name", "")),
                arguments_json=str(event.get("arguments_json", "{}")),
                result_text=str(event.get("result_text", "")),
                error_text=str(event.get("error_text", "")),
            )
            session.add(assistant_turn_event)
            next_sequence_index += 1
        await _touch_dialog_in_session(session, user_id, dialog_id)
        await session.commit()


async def create_tool_call_event(
    user_id: int,
    dialog_id: str,
    tool_call_id: str,
    tool_name: str,
    arguments: dict,
    result_text: str = "",
    error_text: str = "",
):
    async with async_session() as session:
        sequence_index = await _next_dialog_sequence_index(session, user_id, dialog_id)
        event = ToolCallEvent(
            user_id=user_id,
            dialog_id=dialog_id,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            sequence_index=sequence_index,
            arguments_json=json.dumps(arguments),
            result_text=result_text,
            error_text=error_text,
        )
        session.add(event)
        await _touch_dialog_in_session(session, user_id, dialog_id)
        await session.commit()


async def create_llm_usage_event(
    user_id: int,
    dialog_id: str,
    *,
    turn_id: str = "",
    round_index: int = 0,
    provider: str = "",
    model: str = "",
    call_type: str = "chat",
    request_id: str = "",
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    reasoning_tokens: int = 0,
    input_price_per_million: str = "0",
    cached_input_price_per_million: str = "0",
    output_price_per_million: str = "0",
    currency: str = "USD",
    cost_amount: str = "0",
    usage_source: str = "missing",
):
    async with async_session() as session:
        dialog_title = ""
        if dialog_id:
            dialog_result = await session.execute(
                select(Dialog.title).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
            )
            dialog_title = str(dialog_result.scalar_one_or_none() or "")

        event = LlmUsageEvent(
            user_id=user_id,
            dialog_id=dialog_id,
            dialog_title=dialog_title,
            turn_id=str(turn_id or ""),
            round_index=max(int(round_index or 0), 0),
            provider=str(provider or ""),
            model=str(model or ""),
            call_type=str(call_type or "chat"),
            request_id=str(request_id or ""),
            input_tokens=max(int(input_tokens or 0), 0),
            cached_input_tokens=max(int(cached_input_tokens or 0), 0),
            output_tokens=max(int(output_tokens or 0), 0),
            total_tokens=max(int(total_tokens or 0), 0),
            reasoning_tokens=max(int(reasoning_tokens or 0), 0),
            input_price_per_million=str(input_price_per_million or "0"),
            cached_input_price_per_million=str(cached_input_price_per_million or "0"),
            output_price_per_million=str(output_price_per_million or "0"),
            currency=str(currency or "USD"),
            cost_amount=str(cost_amount or "0"),
            usage_source=str(usage_source or "missing"),
        )
        session.add(event)
        await _touch_dialog_in_session(session, user_id, dialog_id)
        await session.commit()


async def get_dialog_usage_totals(user_id: int, dialog_id: str) -> dict[str, str | int]:
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(LlmUsageEvent).where(LlmUsageEvent.user_id == user_id, LlmUsageEvent.dialog_id == dialog_id)
                )
            )
            .scalars()
            .all()
        )

    total_cost = Decimal("0")
    currency = "USD"
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    reasoning_tokens = 0
    request_count = 0

    for row in rows:
        request_count += 1
        input_tokens += int(row.input_tokens or 0)
        cached_input_tokens += int(row.cached_input_tokens or 0)
        output_tokens += int(row.output_tokens or 0)
        total_tokens += int(row.total_tokens or 0)
        reasoning_tokens += int(row.reasoning_tokens or 0)
        currency = str(row.currency or currency)
        try:
            total_cost += Decimal(str(row.cost_amount or "0"))
        except Exception:
            pass

    return {
        "request_count": request_count,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "currency": currency,
        "cost_amount": format(total_cost, "f"),
    }


async def list_dialog_usage_events(user_id: int, dialog_id: str) -> list[dict[str, str | int]]:
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(LlmUsageEvent)
                    .where(LlmUsageEvent.user_id == user_id, LlmUsageEvent.dialog_id == dialog_id)
                    .order_by(LlmUsageEvent.created.asc(), LlmUsageEvent.llm_usage_event_id.asc())
                )
            )
            .scalars()
            .all()
        )

    events: list[dict[str, str | int]] = []
    for row in rows:
        created = row.created.isoformat() if row.created is not None else ""
        events.append(
            {
                "turn_id": str(row.turn_id or ""),
                "dialog_title": str(row.dialog_title or ""),
                "round_index": int(row.round_index or 0),
                "provider": str(row.provider or ""),
                "model": str(row.model or ""),
                "call_type": str(row.call_type or ""),
                "request_id": str(row.request_id or ""),
                "input_tokens": int(row.input_tokens or 0),
                "cached_input_tokens": int(row.cached_input_tokens or 0),
                "output_tokens": int(row.output_tokens or 0),
                "total_tokens": int(row.total_tokens or 0),
                "reasoning_tokens": int(row.reasoning_tokens or 0),
                "input_price_per_million": str(row.input_price_per_million or "0"),
                "cached_input_price_per_million": str(row.cached_input_price_per_million or "0"),
                "output_price_per_million": str(row.output_price_per_million or "0"),
                "currency": str(row.currency or "USD"),
                "cost_amount": str(row.cost_amount or "0"),
                "usage_source": str(row.usage_source or "missing"),
                "created": created,
            }
        )
    return events


async def get_dialog_usage_by_turn(user_id: int, dialog_id: str) -> list[dict[str, str | int]]:
    events = await list_dialog_usage_events(user_id, dialog_id)
    turns_by_id: dict[str, dict[str, str | int]] = {}
    turn_order: list[str] = []

    for event in events:
        turn_id = str(event.get("turn_id", "") or "")
        if not turn_id:
            continue
        if turn_id not in turns_by_id:
            turns_by_id[turn_id] = {
                "turn_id": turn_id,
                "request_count": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
                "currency": str(event.get("currency", "USD") or "USD"),
                "cost_amount": "0",
                "first_created": str(event.get("created", "") or ""),
            }
            turn_order.append(turn_id)

        turn = turns_by_id[turn_id]
        turn["request_count"] = int(turn["request_count"]) + 1
        turn["input_tokens"] = int(turn["input_tokens"]) + int(event.get("input_tokens", 0))
        turn["cached_input_tokens"] = int(turn["cached_input_tokens"]) + int(event.get("cached_input_tokens", 0))
        turn["output_tokens"] = int(turn["output_tokens"]) + int(event.get("output_tokens", 0))
        turn["total_tokens"] = int(turn["total_tokens"]) + int(event.get("total_tokens", 0))
        turn["reasoning_tokens"] = int(turn["reasoning_tokens"]) + int(event.get("reasoning_tokens", 0))
        turn["currency"] = str(event.get("currency", "USD") or "USD")
        try:
            total_cost = Decimal(str(turn.get("cost_amount", "0"))) + Decimal(str(event.get("cost_amount", "0")))
            turn["cost_amount"] = format(total_cost, "f")
        except Exception:
            pass

    return [turns_by_id[turn_id] for turn_id in turn_order]


async def get_user_usage_totals(user_id: int) -> dict[str, str | int]:
    async with async_session() as session:
        rows = (
            (
                await session.execute(
                    select(LlmUsageEvent).where(LlmUsageEvent.user_id == user_id).order_by(LlmUsageEvent.created.asc())
                )
            )
            .scalars()
            .all()
        )

    total_cost = Decimal("0")
    currency = "USD"
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    total_tokens = 0
    reasoning_tokens = 0
    request_count = 0

    for row in rows:
        request_count += 1
        input_tokens += int(row.input_tokens or 0)
        cached_input_tokens += int(row.cached_input_tokens or 0)
        output_tokens += int(row.output_tokens or 0)
        total_tokens += int(row.total_tokens or 0)
        reasoning_tokens += int(row.reasoning_tokens or 0)
        currency = str(row.currency or currency)
        try:
            total_cost += Decimal(str(row.cost_amount or "0"))
        except Exception:
            pass

    return {
        "request_count": request_count,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "reasoning_tokens": reasoning_tokens,
        "currency": currency,
        "cost_amount": format(total_cost, "f"),
    }


async def list_user_usage_by_dialog(user_id: int) -> list[dict[str, str | int]]:
    async with async_session() as session:
        usage_rows = (
            (
                await session.execute(
                    select(LlmUsageEvent)
                    .where(LlmUsageEvent.user_id == user_id)
                    .order_by(LlmUsageEvent.created.asc(), LlmUsageEvent.llm_usage_event_id.asc())
                )
            )
            .scalars()
            .all()
        )
    dialogs_by_id: dict[str, dict[str, str | int]] = {}
    dialog_order: list[str] = []

    for row in usage_rows:
        dialog_id = str(row.dialog_id or "")
        if not dialog_id:
            continue
        if dialog_id not in dialogs_by_id:
            dialogs_by_id[dialog_id] = {
                "dialog_id": dialog_id,
                "title": str(row.dialog_title or ""),
                "request_count": 0,
                "input_tokens": 0,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "reasoning_tokens": 0,
                "currency": str(row.currency or "USD"),
                "cost_amount": "0",
                "first_created": row.created.isoformat() if row.created is not None else "",
                "last_created": row.created.isoformat() if row.created is not None else "",
            }
            dialog_order.append(dialog_id)

        dialog = dialogs_by_id[dialog_id]
        dialog["request_count"] = int(dialog["request_count"]) + 1
        dialog["input_tokens"] = int(dialog["input_tokens"]) + int(row.input_tokens or 0)
        dialog["cached_input_tokens"] = int(dialog["cached_input_tokens"]) + int(row.cached_input_tokens or 0)
        dialog["output_tokens"] = int(dialog["output_tokens"]) + int(row.output_tokens or 0)
        dialog["total_tokens"] = int(dialog["total_tokens"]) + int(row.total_tokens or 0)
        dialog["reasoning_tokens"] = int(dialog["reasoning_tokens"]) + int(row.reasoning_tokens or 0)
        dialog["currency"] = str(row.currency or "USD")
        if row.created is not None:
            dialog["last_created"] = row.created.isoformat()
        try:
            total_cost = Decimal(str(dialog.get("cost_amount", "0"))) + Decimal(str(row.cost_amount or "0"))
            dialog["cost_amount"] = format(total_cost, "f")
        except Exception:
            pass

    ordered_dialogs = [dialogs_by_id[dialog_id] for dialog_id in dialog_order]
    ordered_dialogs.sort(key=lambda item: (str(item.get("last_created", "")), str(item.get("dialog_id", ""))), reverse=True)
    return ordered_dialogs


async def get_user_usage_by_dialog_info(user_id: int, current_page: int = 1) -> dict[str, list[dict[str, str | int]] | bool]:
    dialogs = await list_user_usage_by_dialog(user_id)
    start_index = max(current_page - 1, 0) * DIALOGS_PER_PAGE
    end_index = start_index + DIALOGS_PER_PAGE
    return {
        "dialogs": dialogs[start_index:end_index],
        "has_next": end_index < len(dialogs),
    }


async def delete_dialog(user_id: int, dialog_id: str):

    async with async_session() as session:
        stmt = select(Dialog).where(Dialog.dialog_id == dialog_id, Dialog.user_id == user_id)
        result = await session.execute(stmt)
        dialog = result.scalar_one_or_none()

        if not dialog:
            raise exceptions_validation.UserValidate("Dialog is not connected to user. You can't delete it")

        await session.delete(dialog)
        await session.commit()


async def get_dialogs_info(user_id: int, current_page: int = 1, query: str = ""):

    async with async_session() as session:
        query = str(query).strip()

        filters = [Dialog.user_id == user_id]
        if query:
            pattern = f"%{query}%"
            message_match_exists = exists(
                select(1).where(
                    Message.dialog_id == Dialog.dialog_id,
                    Message.user_id == user_id,
                    Message.active == 1,
                    Message.content.ilike(pattern),
                )
            )
            filters.append(
                or_(
                    Dialog.title.ilike(pattern),
                    message_match_exists,
                )
            )

        # Fetch dialogs for the current page
        stmt = (
            select(Dialog)
            .where(*filters)
            .order_by(Dialog.updated.desc(), Dialog.dialog_id.desc())
            .limit(DIALOGS_PER_PAGE)
            .offset((current_page - 1) * DIALOGS_PER_PAGE)
        )
        result = await session.execute(stmt)
        dialogs = result.scalars().all()

        # Count total number of dialogs
        count_stmt = select(func.count()).select_from(Dialog).where(*filters)
        count_result = await session.execute(count_stmt)
        num_dialogs = count_result.scalar_one()

        has_prev = current_page > 1
        has_next = num_dialogs > current_page * DIALOGS_PER_PAGE
        prev_page = current_page - 1 if has_prev else 0
        next_page = current_page + 1 if has_next else 0

        logger.warning(f"Dialogs for user {user_id}: {len(dialogs)} found on page {current_page} (query={query!r})")

        dialogs_list = []
        for d in dialogs:
            assert d.created is not None  # helps both Mypy and sanity
            assert d.updated is not None
            dialogs_list.append(
                {
                    "dialog_id": str(d.dialog_id),
                    "title": d.title,
                    "created": d.created.isoformat(),
                    "updated": d.updated.isoformat(),
                }
            )

        return {
            "current_page": current_page,
            "per_page": DIALOGS_PER_PAGE,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_page": prev_page,
            "next_page": next_page,
            "dialogs": dialogs_list,
            "num_dialogs": num_dialogs,
        }


async def update_message(user_id: int, message_id: int, new_content: str):
    """
    Update a message and deactivate newer messages in the same dialog
    """
    new_content = str(new_content).strip()

    if not new_content:
        raise exceptions_validation.UserValidate("Message content cannot be empty")

    async with async_session() as session:
        # First, get the message to update and verify ownership
        stmt = select(Message).where(Message.message_id == message_id, Message.user_id == user_id)
        result = await session.execute(stmt)
        message = result.scalar_one_or_none()

        if not message:
            raise exceptions_validation.UserValidate("Message not found or not owned by user")

        earlier_user_message_exists_stmt = select(
            exists().where(
                Message.dialog_id == message.dialog_id,
                Message.user_id == user_id,
                Message.role == "user",
                Message.active == 1,
                Message.sequence_index < message.sequence_index,
            )
        )
        earlier_user_message_exists = bool((await session.execute(earlier_user_message_exists_stmt)).scalar())
        was_first_user_message = message.role == "user" and not earlier_user_message_exists

        # Update the message content
        message.content = new_content

        # Deactivate all messages in the same dialog that were created after this message
        deactivate_stmt = (
            update(Message)
            .where(
                Message.dialog_id == message.dialog_id,
                Message.sequence_index > message.sequence_index,
                Message.user_id == user_id,
            )
            .values(active=0)
        )
        await session.execute(deactivate_stmt)

        # Remove tool call events that belong to turns after the edited message.
        delete_tool_events_stmt = delete(ToolCallEvent).where(
            ToolCallEvent.dialog_id == message.dialog_id,
            ToolCallEvent.user_id == user_id,
            ToolCallEvent.sequence_index > message.sequence_index,
        )
        await session.execute(delete_tool_events_stmt)

        delete_assistant_turn_events_stmt = delete(AssistantTurnEvent).where(
            AssistantTurnEvent.dialog_id == message.dialog_id,
            AssistantTurnEvent.user_id == user_id,
            AssistantTurnEvent.sequence_index > message.sequence_index,
        )
        await session.execute(delete_assistant_turn_events_stmt)

        await _touch_dialog_in_session(session, user_id, str(message.dialog_id))
        await session.commit()

        return {
            "message_id": message_id,
            "dialog_id": str(message.dialog_id),
            "content": new_content,
            "updated": True,
            "was_first_user_message": was_first_user_message,
        }

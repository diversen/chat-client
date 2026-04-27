from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Mapping

from chat_client.core import exceptions_validation


@dataclass(frozen=True)
class UsageDateRange:
    start_date: str
    end_date: str
    start_datetime: datetime | None
    end_datetime_exclusive: datetime | None


def _parse_optional_date(raw_value: str, field_name: str) -> date | None:
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise exceptions_validation.JSONError(f"Invalid {field_name} parameter", status_code=400) from exc


def parse_usage_date_range(query_params: Mapping[str, str]) -> UsageDateRange:
    start = _parse_optional_date(str(query_params.get("start_date", "")), "start_date")
    end = _parse_optional_date(str(query_params.get("end_date", "")), "end_date")

    if start is not None and end is not None and start > end:
        raise exceptions_validation.JSONError("start_date must be on or before end_date", status_code=400)

    return UsageDateRange(
        start_date=start.isoformat() if start is not None else "",
        end_date=end.isoformat() if end is not None else "",
        start_datetime=datetime.combine(start, time.min) if start is not None else None,
        end_datetime_exclusive=datetime.combine(end + timedelta(days=1), time.min) if end is not None else None,
    )

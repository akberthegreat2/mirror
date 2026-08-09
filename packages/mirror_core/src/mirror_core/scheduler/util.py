"""Internal scheduling helpers: datetime coercion and cron evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _next_cron_time(expression: str, *, after: datetime) -> datetime | None:
    """Return the next time for a tiny cron subset.

    The implementation intentionally supports the practical subset used by the
    repository tests: ``*`` and ``*/N`` minute expressions with optional
    six-field second precision.
    """

    parts = expression.split()
    if len(parts) not in {5, 6}:
        return None
    if len(parts) == 5:
        second_field = "0"
        minute_field, hour_field, day_field, month_field, weekday_field = parts
    else:
        (
            second_field,
            minute_field,
            hour_field,
            day_field,
            month_field,
            weekday_field,
        ) = parts

    if (
        hour_field != "*"
        or day_field != "*"
        or month_field != "*"
        or weekday_field != "*"
    ):
        return None

    after = _coerce_datetime(after).replace(microsecond=0)
    start = after + timedelta(seconds=1)

    def _parse_field(field: str, upper: int) -> list[int] | None:
        if field == "*":
            return list(range(upper))
        if field.startswith("*/"):
            try:
                step = int(field[2:])
            except ValueError:
                return None
            if step <= 0:
                return None
            return list(range(0, upper, step))
        try:
            value = int(field)
        except ValueError:
            return None
        if 0 <= value < upper:
            return [value]
        return None

    minute_candidates = _parse_field(minute_field, 60)
    second_candidates = _parse_field(second_field, 60)
    if minute_candidates is None or second_candidates is None:
        return None

    for day_offset in range(366):
        day = (start + timedelta(days=day_offset)).date()
        hour_start = start.hour if day_offset == 0 else 0
        for hour in range(hour_start, 24):
            for minute in minute_candidates:
                if day_offset == 0 and hour == start.hour and minute < start.minute:
                    continue
                for second in second_candidates:
                    if (
                        day_offset == 0
                        and hour == start.hour
                        and minute == start.minute
                        and second < start.second
                    ):
                        continue
                    candidate = datetime(
                        day.year,
                        day.month,
                        day.day,
                        hour,
                        minute,
                        second,
                        tzinfo=start.tzinfo,
                    )
                    if candidate > after:
                        return candidate
    return None

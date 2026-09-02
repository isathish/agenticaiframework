"""Cron expression parser — stdlib-only.

Supports the standard 5-field syntax (``min hour dom month dow``), an
optional leading seconds field (6 fields), ``@hourly``-style aliases,
lists, ranges, steps, month / weekday names and ``?``/``L`` for day
fields in their common meanings (``L`` = last day of month).

    >>> Cron("*/15 9-17 * * mon-fri").next_after(datetime(2026, 1, 5, 9, 0))
    datetime.datetime(2026, 1, 5, 9, 15)
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import FrozenSet, Optional

_ALIASES = {
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
    "@monthly": "0 0 1 * *",
    "@weekly": "0 0 * * 0",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@hourly": "0 * * * *",
    "@minutely": "* * * * *",
}
_MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_abbr) if m}
_DOWS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


class CronError(ValueError):
    pass


def _parse_field(text: str, lo: int, hi: int, names: Optional[dict] = None, *, dow: bool = False) -> FrozenSet[int]:
    values = set()
    for part in text.split(","):
        part = part.strip().lower()
        if not part:
            raise CronError("empty cron field element")
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            try:
                step = int(step_s)
            except ValueError as exc:
                raise CronError(f"invalid step {step_s!r}") from exc
            if step <= 0:
                raise CronError("step must be positive")
        if part in ("*", "?"):
            start, end = lo, hi
        elif "-" in part:
            a, b = part.split("-", 1)
            start, end = _atom(a, names, dow), _atom(b, names, dow)
        else:
            start = _atom(part, names, dow)
            end = hi if step > 1 else start
        if dow:
            start, end = start % 7, end % 7
        if start > end:
            # wrap-around ranges like fri-mon or 22-2
            values.update(range(start, hi + 1, step))
            values.update(range(lo, end + 1, step))
        else:
            values.update(range(start, end + 1, step))
    bad = [v for v in values if v < lo or v > hi]
    if bad:
        raise CronError(f"value {bad[0]} out of range {lo}-{hi}")
    return frozenset(values)


def _atom(token: str, names: Optional[dict], dow: bool) -> int:
    if names and token[:3] in names and not token.isdigit():
        return names[token[:3]]
    try:
        v = int(token)
    except ValueError as exc:
        raise CronError(f"invalid cron token {token!r}") from exc
    if dow and v == 7:
        return 0
    return v


class Cron:
    def __init__(self, expression: str) -> None:
        expr = expression.strip()
        expr = _ALIASES.get(expr.lower(), expr)
        fields = expr.split()
        if len(fields) == 5:
            fields = ["0"] + fields
        if len(fields) != 6:
            raise CronError(f"expected 5 or 6 fields, got {len(fields)}: {expression!r}")
        sec, minute, hour, dom, month, dow = fields
        self.expression = expression
        self.seconds = _parse_field(sec, 0, 59)
        self.minutes = _parse_field(minute, 0, 59)
        self.hours = _parse_field(hour, 0, 23)
        self.last_dom = dom.strip().lower() == "l"
        self.days = frozenset(range(1, 32)) if self.last_dom else _parse_field(dom, 1, 31)
        self.months = _parse_field(month, 1, 12, _MONTHS)
        self.weekdays = _parse_field(dow, 0, 6, _DOWS, dow=True)
        self._dom_star = dom.strip() in ("*", "?")
        self._dow_star = dow.strip() in ("*", "?")

    # -- matching -----------------------------------------------------------

    def _day_matches(self, dt: datetime) -> bool:
        dom_ok = dt.day in self.days
        if self.last_dom:
            dom_ok = dt.day == calendar.monthrange(dt.year, dt.month)[1]
        dow_ok = (dt.weekday() + 1) % 7 in self.weekdays  # convert Mon=0 -> Sun=0
        # Vixie cron: if both restricted, either may match.
        if not self._dom_star and not self._dow_star:
            return dom_ok or dow_ok
        return dom_ok and dow_ok

    def matches(self, dt: datetime) -> bool:
        return (
            dt.second in self.seconds
            and dt.minute in self.minutes
            and dt.hour in self.hours
            and dt.month in self.months
            and self._day_matches(dt)
        )

    def next_after(self, start: Optional[datetime] = None, *, inclusive: bool = False) -> datetime:
        """Next matching time strictly after ``start`` (or at it when ``inclusive``)."""
        dt = (start or datetime.now()).replace(microsecond=0)
        if not inclusive:
            dt += timedelta(seconds=1)
        # Search field-by-field, skipping whole units that cannot match.
        for _ in range(366 * 24 * 60 * 2):
            if dt.month not in self.months:
                year = dt.year + (dt.month // 12)
                month = dt.month % 12 + 1
                dt = dt.replace(year=year, month=month, day=1, hour=0, minute=0, second=0)
                continue
            if not self._day_matches(dt):
                dt = (dt + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                continue
            if dt.hour not in self.hours:
                dt = (dt + timedelta(hours=1)).replace(minute=0, second=0)
                continue
            if dt.minute not in self.minutes:
                dt = (dt + timedelta(minutes=1)).replace(second=0)
                continue
            if dt.second not in self.seconds:
                dt += timedelta(seconds=1)
                continue
            return dt
        raise CronError(f"no matching time found for {self.expression!r}")

    def previous_before(self, end: Optional[datetime] = None) -> datetime:
        """Most recent matching time strictly before ``end`` (minute resolution)."""
        dt = (end or datetime.now()).replace(microsecond=0) - timedelta(seconds=1)
        for _ in range(366 * 24 * 60 * 2):
            if self.matches(dt):
                return dt
            dt -= timedelta(seconds=1) if len(self.seconds) < 60 else timedelta(minutes=1)
            if len(self.seconds) == 60:
                dt = dt.replace(second=0)
        raise CronError(f"no matching time found for {self.expression!r}")

    def is_due(self, last_run: Optional[datetime], now: Optional[datetime] = None) -> bool:
        """True when a scheduled tick lies in ``(last_run, now]``."""
        now = now or datetime.now()
        if last_run is None:
            return True
        return self.next_after(last_run) <= now

    def __repr__(self) -> str:
        return f"Cron({self.expression!r})"


__all__ = ["Cron", "CronError"]

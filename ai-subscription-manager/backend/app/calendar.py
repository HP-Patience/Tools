import calendar
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Hong_Kong")


def today():
    return datetime.now(TZ).date()


def add_term(start: date, count: int, unit: str) -> date:
    if not isinstance(count, int) or count <= 0 or count > 10000:
        raise ValueError("期限数量应为 1 至 10000")
    if unit in ("day", "week"):
        return start + timedelta(days=count * (7 if unit == "week" else 1))
    if unit not in ("month", "year"):
        raise ValueError("期限单位无效")
    months = start.year * 12 + start.month - 1 + count * (12 if unit == "year" else 1)
    year, month = divmod(months, 12)
    return date(year, month + 1, min(start.day, calendar.monthrange(year, month + 1)[1]))


def service_status(service, day=None):
    day = day or today()
    if service.ended_at:
        return "ended"
    if service.started_on > day:
        return "upcoming"
    if not service.expires_on:
        return "no_expiry"
    if service.expires_on < day:
        return "overdue"
    if service.expires_on == day:
        return "today"
    return "active"

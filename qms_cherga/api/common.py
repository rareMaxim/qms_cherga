"""
Common utilities for QMS API.
"""
import frappe
from frappe import _
from frappe.utils import get_time, now_datetime, get_system_timezone, get_date_str
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import List, Tuple
from datetime import time

from qms_cherga.utils.logger import get_logger

logger = get_logger(__name__)


def office_room(office_id: str) -> str:
    """
    Генерує ім'я кімнати для WebSocket на основі ID офісу.

    Args:
        office_id: ID офісу

    Returns:
        Назва WebSocket кімнати
    """
    return f'qms_office:{office_id}'


def is_office_open(schedule_name: str, timezone: str) -> bool:
    """
    Перевіряє, чи відкритий офіс зараз згідно з графіком, враховуючи винятки,
    часову зону офісу та можливість кількох робочих інтервалів на день.

    Args:
        schedule_name: Назва (ID) документу QMS Schedule
        timezone: Рядок з назвою часової зони у форматі IANA (напр., 'Europe/Kyiv')

    Returns:
        True, якщо офіс відкритий, False - якщо закритий або сталася помилка
    """
    if not schedule_name:
        logger.error("Schedule name not provided for is_office_open check")
        return False

    office_tz = None
    try:
        if timezone:
            office_tz = ZoneInfo(timezone)
        else:
            system_tz_str = get_system_timezone()
            office_tz = ZoneInfo(system_tz_str)
            logger.warning(
                f"Office timezone not provided for schedule '{schedule_name}'. "
                f"Falling back to system timezone '{system_tz_str}'."
            )
    except ZoneInfoNotFoundError:
        system_tz_str = get_system_timezone()
        office_tz = ZoneInfo(system_tz_str)
        logger.error(
            f"Invalid timezone '{timezone}' provided for schedule '{schedule_name}'. "
            f"Falling back to system timezone '{system_tz_str}'."
        )
    except Exception as e:
        system_tz_str = get_system_timezone()
        office_tz = ZoneInfo(system_tz_str)
        logger.error(
            f"Error processing timezone '{timezone}' for schedule '{schedule_name}'. "
            f"Falling back to system timezone '{system_tz_str}'. Error: {e}"
        )

    try:
        now_local_dt = now_datetime().astimezone(office_tz)

        current_date_str = now_local_dt.strftime('%Y-%m-%d')
        current_day_name = now_local_dt.strftime('%A')
        current_time_obj = get_time(now_local_dt.strftime('%H:%M:%S'))

        # Перевірка Винятків
        exceptions = frappe.get_all(
            "QMS Schedule Exception Child",
            filters={
                "parenttype": "QMS Schedule",
                "parent": schedule_name,
                "exception_date": current_date_str
            },
            fields=["is_workday", "start_time", "end_time"],
        )

        if exceptions:
            is_explicitly_non_workday = any(not exc.is_workday for exc in exceptions)
            if is_explicitly_non_workday:
                return False

            for exception in exceptions:
                if exception.is_workday and exception.start_time and exception.end_time:
                    start_time_exc = get_time(exception.start_time)
                    end_time_exc = get_time(exception.end_time)
                    if start_time_exc <= current_time_obj < end_time_exc:
                        return True  # Відкрито за винятком

            # Якщо були робочі винятки, але час не підійшов - закрито
            if any(exc.is_workday for exc in exceptions):
                return False

        # Перевірка Правил
        all_rules = frappe.get_all(
            "QMS Schedule Rule Child",
            filters={
                "parent": schedule_name,
                "parenttype": "QMS Schedule",
                "day_of_week": current_day_name
            },
            fields=["start_time", "end_time"]
        )

        if not all_rules:
            return False  # Немає правил на цей день

        for rule in all_rules:
            start_time_rule = get_time(rule.start_time)
            end_time_rule = get_time(rule.end_time)
            if start_time_rule <= current_time_obj < end_time_rule:
                return True  # Відкрито за правилом

        return False  # Жоден інтервал не підійшов

    except Exception as e:
        now_local_dt_str = now_local_dt.isoformat() if 'now_local_dt' in locals() else 'N/A'
        logger.error(
            f"Error during schedule check for schedule '{schedule_name}' "
            f"with timezone '{timezone}'. Current local time check: {now_local_dt_str}. "
            f"Error: {e}",
            exc_info=True
        )
        frappe.log_error(frappe.get_traceback(), "Schedule Check Runtime Error")
        return False


def get_working_intervals_for_date(
    schedule_name: str,
    target_date,
    timezone_str: str
) -> List[Tuple[time, time]]:
    """
    Допоміжна функція для отримання робочих інтервалів на задану дату.

    Args:
        schedule_name: Назва графіку роботи
        target_date: Дата для перевірки
        timezone_str: Часова зона

    Returns:
        Список кортежів (start_time, end_time) з робочими інтервалами
    """
    logger.info(
        f"Getting working intervals for schedule '{schedule_name}', "
        f"date '{target_date}', timezone '{timezone_str}'"
    )

    target_date_str = get_date_str(target_date)
    day_name = target_date.strftime('%A')
    intervals = []

    try:
        # 1. Перевірка винятків
        exceptions = frappe.get_all(
            "QMS Schedule Exception Child",
            filters={
                "parent": schedule_name,
                "parenttype": "QMS Schedule",
                "exception_date": target_date_str
            },
            fields=["is_workday", "start_time", "end_time"],
            order_by="start_time"
        )

        logger.info(f"Found {len(exceptions)} exceptions for date {target_date_str}")

        has_exception = bool(exceptions)
        is_explicitly_non_workday = any(not exc.is_workday for exc in exceptions)

        if is_explicitly_non_workday:
            logger.info("Date marked as non-workday by exception")
            return []

        if has_exception:
            for exc in exceptions:
                if exc.is_workday and exc.start_time and exc.end_time:
                    try:
                        start = get_time(exc.start_time)
                        end = get_time(exc.end_time)
                        if start < end:
                            intervals.append((start, end))
                            logger.info(f"Added exception interval: {start} - {end}")
                        else:
                            logger.warning(
                                f"Invalid exception interval (start >= end): "
                                f"{exc.start_time} - {exc.end_time}"
                            )
                    except (TypeError, ValueError) as e:
                        logger.error(
                            f"Could not parse time from exception: "
                            f"Start='{exc.start_time}', End='{exc.end_time}'. Error: {e}"
                        )

            return intervals

        # 2. Перевірка правил (якщо не було винятків)
        logger.info(f"No relevant exceptions. Checking rules for {day_name}")

        rules = frappe.get_all(
            "QMS Schedule Rule Child",
            filters={
                "parent": schedule_name,
                "parenttype": "QMS Schedule",
                "day_of_week": day_name
            },
            fields=["start_time", "end_time"],
            order_by="start_time"
        )

        logger.info(f"Found {len(rules)} rules for {day_name}")

        for rule in rules:
            try:
                start = get_time(rule.start_time)
                end = get_time(rule.end_time)
                if start < end:
                    intervals.append((start, end))
                    logger.info(f"Added rule interval: {start} - {end}")
                else:
                    logger.warning(
                        f"Invalid rule interval (start >= end): "
                        f"{rule.start_time} - {rule.end_time}"
                    )
            except (TypeError, ValueError) as e:
                logger.error(
                    f"Could not parse time from rule: "
                    f"Start='{rule.start_time}', End='{rule.end_time}'. Error: {e}"
                )

        return intervals

    except Exception as e:
        logger.error(
            f"Error getting working intervals for {schedule_name} "
            f"on {target_date_str}: {e}",
            exc_info=True
        )
        frappe.log_error(frappe.get_traceback(), "Schedule Interval Error")
        return []

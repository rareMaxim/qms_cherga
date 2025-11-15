"""
Structured logging utilities for QMS system.
"""
import logging
import json
from typing import Any, Dict
from frappe.utils import now_datetime


# Створюємо logger для QMS
qms_logger = logging.getLogger("qms_cherga")


class StructuredFormatter(logging.Formatter):
    """
    Форматер для структурованих логів у JSON форматі.
    """
    def format(self, record):
        log_data = {
            "timestamp": now_datetime().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Додаємо додаткові поля якщо є
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        # Додаємо exception якщо є
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


def get_logger(name: str = "qms_cherga") -> logging.Logger:
    """
    Отримує logger з налаштуванням.

    Args:
        name: Назва logger'а

    Returns:
        Налаштований logger
    """
    logger = logging.getLogger(name)

    # Якщо logger вже налаштований, повертаємо його
    if logger.handlers:
        return logger

    # Налаштовуємо logger
    logger.setLevel(logging.INFO)

    # Створюємо handler
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    # Використовуємо structured formatter
    formatter = StructuredFormatter()
    handler.setFormatter(formatter)

    # Додаємо handler до logger
    logger.addHandler(handler)

    return logger


def log_api_call(func_name: str, **kwargs):
    """
    Логує виклик API функції.

    Args:
        func_name: Назва функції
        **kwargs: Додаткові дані для логування
    """
    logger = get_logger()

    # Створюємо LogRecord з додатковими даними
    extra_data = {
        "event_type": "api_call",
        "function": func_name,
        **kwargs
    }

    logger.info(f"API call: {func_name}", extra={"extra_data": extra_data})


def log_ticket_event(event_type: str, ticket_name: str, ticket_number: str = None, **kwargs):
    """
    Логує події пов'язані з талонами.

    Args:
        event_type: Тип події (created, called, started, completed, etc.)
        ticket_name: ID талона
        ticket_number: Номер талона для відображення
        **kwargs: Додаткові дані
    """
    logger = get_logger()

    extra_data = {
        "event_type": "ticket_event",
        "ticket_event": event_type,
        "ticket_name": ticket_name,
        "ticket_number": ticket_number,
        **kwargs
    }

    logger.info(f"Ticket {event_type}: {ticket_number or ticket_name}", extra={"extra_data": extra_data})


def log_error(error_type: str, message: str, **kwargs):
    """
    Логує помилки.

    Args:
        error_type: Тип помилки
        message: Повідомлення про помилку
        **kwargs: Додаткові дані
    """
    logger = get_logger()

    extra_data = {
        "event_type": "error",
        "error_type": error_type,
        **kwargs
    }

    logger.error(message, extra={"extra_data": extra_data})


def log_performance(func_name: str, duration_ms: float, **kwargs):
    """
    Логує метрики продуктивності.

    Args:
        func_name: Назва функції
        duration_ms: Тривалість виконання в мілісекундах
        **kwargs: Додаткові метрики
    """
    logger = get_logger()

    extra_data = {
        "event_type": "performance",
        "function": func_name,
        "duration_ms": duration_ms,
        **kwargs
    }

    logger.info(f"Performance: {func_name} took {duration_ms:.2f}ms", extra={"extra_data": extra_data})

"""
Rate limiting utilities for QMS API endpoints.
"""
import frappe
from functools import wraps
from frappe import _
from frappe.utils import now_datetime, get_datetime
from datetime import timedelta


def rate_limit(max_requests: int = 10, window_seconds: int = 60, key_func=None):
    """
    Декоратор для обмеження частоти викликів API.

    Args:
        max_requests: Максимальна кількість запитів
        window_seconds: Часове вікно в секундах
        key_func: Функція для генерації ключа (за замовчуванням - IP адреса)
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Генеруємо ключ для rate limiting
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                # За замовчуванням використовуємо IP адресу
                key = frappe.local.request_ip or "unknown"

            # Ім'я функції для ідентифікації
            func_name = fn.__name__
            cache_key = f"rate_limit:{func_name}:{key}"

            # Отримуємо поточний час
            current_time = now_datetime()

            # Отримуємо історію запитів з кешу
            try:
                request_history = frappe.cache().get(cache_key) or []
            except Exception:
                request_history = []

            # Видаляємо старі записи (за межами вікна)
            cutoff_time = current_time - timedelta(seconds=window_seconds)
            request_history = [
                req_time for req_time in request_history
                if get_datetime(req_time) > cutoff_time
            ]

            # Перевіряємо ліміт
            if len(request_history) >= max_requests:
                from qms_cherga.utils.response import error_response
                frappe.local.response.http_status_code = 429
                return error_response(
                    _("Rate limit exceeded. Please try again later."),
                    error_code="RATE_LIMIT_EXCEEDED",
                    http_status_code=429
                )

            # Додаємо поточний запит
            request_history.append(str(current_time))

            # Зберігаємо в кеш
            try:
                frappe.cache().set(cache_key, request_history, expires_in_sec=window_seconds + 10)
            except Exception:
                pass  # Не блокуємо запит якщо кеш недоступний

            # Викликаємо оригінальну функцію
            return fn(*args, **kwargs)

        return wrapper
    return decorator


def clear_rate_limit(func_name: str, key: str = None):
    """
    Очищає rate limit для конкретної функції та ключа.

    Args:
        func_name: Назва функції
        key: Ключ (IP або інший ідентифікатор)
    """
    if key is None:
        key = frappe.local.request_ip or "unknown"

    cache_key = f"rate_limit:{func_name}:{key}"
    try:
        frappe.cache().delete(cache_key)
    except Exception:
        pass

"""
Caching utilities for QMS system.
"""
import frappe
from functools import wraps
from typing import Any, Callable, Optional
import hashlib
import json


def make_cache_key(*args, **kwargs) -> str:
    """
    Генерує ключ кешу на основі аргументів.

    Args:
        *args: Позиційні аргументи
        **kwargs: Іменовані аргументи

    Returns:
        Хеш-ключ для кешу
    """
    # Створюємо строку з аргументів
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
    key_string = ":".join(key_parts)

    # Створюємо хеш
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(ttl: int = 300, key_prefix: str = "qms"):
    """
    Декоратор для кешування результатів функції.

    Args:
        ttl: Time to live в секундах (за замовчуванням 5 хвилин)
        key_prefix: Префікс для ключа кешу

    Example:
        @cached(ttl=600, key_prefix="office_info")
        def get_office_info(office_id):
            return frappe.get_doc("QMS Office", office_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Генеруємо ключ кешу
            func_name = func.__name__
            args_key = make_cache_key(*args, **kwargs)
            cache_key = f"{key_prefix}:{func_name}:{args_key}"

            # Перевіряємо чи є значення в кеші
            try:
                cached_value = frappe.cache().get(cache_key)
                if cached_value is not None:
                    return cached_value
            except Exception:
                pass  # Якщо кеш недоступний, виконуємо функцію

            # Викликаємо функцію
            result = func(*args, **kwargs)

            # Зберігаємо в кеш
            try:
                frappe.cache().set(cache_key, result, expires_in_sec=ttl)
            except Exception:
                pass  # Не блокуємо виконання якщо кеш недоступний

            return result

        # Додаємо метод для очищення кешу
        def clear_cache(*args, **kwargs):
            func_name = func.__name__
            if args or kwargs:
                # Очищаємо конкретний ключ
                args_key = make_cache_key(*args, **kwargs)
                cache_key = f"{key_prefix}:{func_name}:{args_key}"
                try:
                    frappe.cache().delete(cache_key)
                except Exception:
                    pass
            else:
                # Очищаємо всі ключі з префіксом
                try:
                    frappe.cache().delete_keys(f"{key_prefix}:{func_name}:*")
                except Exception:
                    pass

        wrapper.clear_cache = clear_cache
        return wrapper

    return decorator


def invalidate_cache(key_pattern: str):
    """
    Інвалідує кеш за патерном ключа.

    Args:
        key_pattern: Патерн ключа (наприклад, "qms:office_info:*")
    """
    try:
        frappe.cache().delete_keys(key_pattern)
    except Exception:
        pass


def get_cached(key: str) -> Optional[Any]:
    """
    Отримує значення з кешу.

    Args:
        key: Ключ кешу

    Returns:
        Значення з кешу або None
    """
    try:
        return frappe.cache().get(key)
    except Exception:
        return None


def set_cached(key: str, value: Any, ttl: int = 300):
    """
    Зберігає значення в кеш.

    Args:
        key: Ключ кешу
        value: Значення для збереження
        ttl: Time to live в секундах
    """
    try:
        frappe.cache().set(key, value, expires_in_sec=ttl)
    except Exception:
        pass


def delete_cached(key: str):
    """
    Видаляє значення з кешу.

    Args:
        key: Ключ кешу
    """
    try:
        frappe.cache().delete(key)
    except Exception:
        pass


# Спеціалізовані функції для QMS кешування

def cache_office_info(office_id: str, data: dict, ttl: int = 3600):
    """
    Кешує інформацію про офіс (TTL: 1 година).
    """
    set_cached(f"qms:office_info:{office_id}", data, ttl=ttl)


def get_cached_office_info(office_id: str) -> Optional[dict]:
    """
    Отримує закешовану інформацію про офіс.
    """
    return get_cached(f"qms:office_info:{office_id}")


def invalidate_office_cache(office_id: str = None):
    """
    Інвалідує кеш офісу.
    """
    if office_id:
        invalidate_cache(f"qms:office_info:{office_id}")
        invalidate_cache(f"qms:kiosk_services:{office_id}")
    else:
        invalidate_cache("qms:office_info:*")
        invalidate_cache("qms:kiosk_services:*")


def cache_kiosk_services(office_id: str, data: dict, ttl: int = 600):
    """
    Кешує список сервісів для кіоску (TTL: 10 хвилин).
    """
    set_cached(f"qms:kiosk_services:{office_id}", data, ttl=ttl)


def get_cached_kiosk_services(office_id: str) -> Optional[dict]:
    """
    Отримує закешований список сервісів для кіоску.
    """
    return get_cached(f"qms:kiosk_services:{office_id}")


def invalidate_service_cache(service_id: str = None):
    """
    Інвалідує кеш сервісів.
    """
    if service_id:
        # Інвалідуємо всі кіоски, бо не знаємо в яких офісах цей сервіс
        invalidate_cache("qms:kiosk_services:*")
    else:
        invalidate_cache("qms:kiosk_services:*")

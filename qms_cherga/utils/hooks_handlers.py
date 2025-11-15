"""
Event handlers for QMS DocTypes to invalidate cache.
"""
import frappe
from qms_cherga.utils.cache import invalidate_office_cache, invalidate_service_cache


def on_office_update(doc, method):
    """
    Інвалідує кеш офісу при його оновленні.

    Args:
        doc: QMS Office document
        method: Метод Frappe (on_update, after_insert, etc.)
    """
    invalidate_office_cache(doc.name)
    frappe.logger().info(f"Cache invalidated for office: {doc.name}")


def on_service_update(doc, method):
    """
    Інвалідує кеш сервісів при оновленні.

    Args:
        doc: QMS Service document
        method: Метод Frappe
    """
    invalidate_service_cache(doc.name)
    frappe.logger().info(f"Cache invalidated for service: {doc.name}")


def on_office_service_assignment_update(doc, method):
    """
    Інвалідує кеш офісу при зміні призначень сервісів.

    Args:
        doc: QMS Office Service Assignment (child table)
        method: Метод Frappe
    """
    # doc.parent містить назву офісу
    if hasattr(doc, 'parent'):
        invalidate_office_cache(doc.parent)
        frappe.logger().info(f"Cache invalidated for office assignments: {doc.parent}")


def on_service_category_update(doc, method):
    """
    Інвалідує кеш всіх сервісів при зміні категорії.

    Args:
        doc: QMS Service Category document
        method: Метод Frappe
    """
    # Інвалідуємо всі сервіси, бо категорія могла змінитися
    invalidate_service_cache()
    frappe.logger().info(f"Cache invalidated for category update: {doc.name}")

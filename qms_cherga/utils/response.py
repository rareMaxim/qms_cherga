
import frappe


def _build_response(status, message=None, data=None, error_code=None, details=None, http_status_code=200):
    """Внутрішня функція для побудови стандартної структури відповіді."""
    response = {"status": status}
    if message:
        # _() використовується для можливості перекладу повідомлень
        response["message"] = frappe._(message)
    if data is not None:  # Дозволяємо передавати порожні словники/списки
        response["data"] = data
    if error_code:
        response["error_code"] = error_code
    # Включаємо деталі тільки в режимі розробника для безпеки
    if details and frappe.conf.get("developer_mode"):
        response["details"] = str(details)  # Перетворюємо на рядок для JSON

    # Встановлюємо HTTP статус відповіді
    frappe.response.status_code = http_status_code
    return response


def success_response(data=None, message=None):
    """Повертає стандартну успішну відповідь (HTTP 200)."""
    return _build_response("success", message=message, data=data, http_status_code=200)


def error_response(message, error_code=None, details=None, http_status_code=400):
    """Повертає стандартну відповідь про помилку (HTTP 400 за замовчуванням)."""
    # Логуємо помилку на бекенді для діагностики
    frappe.log_error(
        message=f"API Error: {message} (Code: {error_code})", title="QMS API Error")
    if details:
        frappe.log_error(message=str(details), title="QMS API Error Details")
    return _build_response("error", message=message, error_code=error_code, details=details, http_status_code=http_status_code)


def info_response(message, data=None):
    """Повертає стандартну інформаційну відповідь (HTTP 200)."""
    return _build_response("info", message=message, data=data, http_status_code=200)

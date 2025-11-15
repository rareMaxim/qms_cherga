"""
Kiosk API endpoints for QMS system.
"""
import frappe
from frappe import _
from frappe.utils import now

from qms_cherga.utils.response import error_response, info_response, success_response
from qms_cherga.utils.rate_limiter import rate_limit
from qms_cherga.utils.cache import get_cached_office_info, cache_office_info, get_cached_kiosk_services, cache_kiosk_services
from qms_cherga.utils.logger import log_api_call, log_ticket_event, log_error
from qms_cherga.api.common import is_office_open


@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=60, window_seconds=60)  # 60 запитів на хвилину
def get_office_info(office: str):
    """
    Отримує інформацію про офіс.

    Args:
        office: ID офісу

    Returns:
        Інформація про офіс (назва, часова зона, адреса, телефон)
    """
    log_api_call("get_office_info", office=office)

    if not office:
        return error_response(_("Office ID is required."), http_status_code=400)

    try:
        # Перевіряємо кеш
        cached_data = get_cached_office_info(office)
        if cached_data:
            log_api_call("get_office_info", office=office, cache_hit=True)
            return success_response(data=cached_data)

        # Отримуємо з БД
        office_data = frappe.db.get_value(
            "QMS Office",
            office,
            ["office_name", "timezone", "address", "contact_phone"],
            as_dict=True
        )

        if not office_data:
            return error_response(
                _("Office '{0}' not found.").format(office),
                http_status_code=404
            )

        # Кешуємо результат на 1 годину
        cache_office_info(office, office_data, ttl=3600)

        return success_response(data=office_data)

    except Exception as e:
        log_error("get_office_info_error", str(e), office=office)
        frappe.log_error(frappe.get_traceback(), f"Get Office Info API Error for Office {office}")
        return error_response(
            _("An unexpected error occurred while fetching office information."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=60, window_seconds=60)  # 60 запитів на хвилину
def get_kiosk_services(office: str):
    """
    Отримує список послуг для кіоску з кешуванням.

    Args:
        office: ID офісу

    Returns:
        Список послуг, згрупованих за категоріями
    """
    log_api_call("get_kiosk_services", office=office)

    try:
        if not office:
            return error_response(_("Office ID is required."), http_status_code=400)

        if not frappe.db.exists("QMS Office", office):
            return error_response(_("Office '{0}' not found.").format(office), http_status_code=404)

        # Перевіряємо кеш
        cached_data = get_cached_kiosk_services(office)
        if cached_data:
            log_api_call("get_kiosk_services", office=office, cache_hit=True)
            # Перевіряємо чи офіс відкритий (це не кешуємо, бо змінюється часто)
            office_doc = frappe.get_cached_doc("QMS Office", office)
            schedule_name = office_doc.schedule or frappe.db.get_value(
                "QMS Organization", office_doc.organization, "default_schedule"
            )
            if schedule_name and not is_office_open(schedule_name, office_doc.timezone):
                return info_response(
                    _("Office '{0}' is currently closed.").format(office_doc.office_name),
                    data={"status": "closed", "categories": [], "services_no_category": []}
                )
            return success_response(data=cached_data)

        # Перевірка графіка роботи
        office_doc = frappe.get_cached_doc("QMS Office", office)
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule"
        )

        office_is_open = False
        closed_message = _("Working schedule not configured.")

        if schedule_name:
            office_is_open = is_office_open(schedule_name, office_doc.timezone)
            if not office_is_open:
                closed_message = _("Office '{0}' is currently closed.").format(office_doc.office_name)
        else:
            closed_message = _("Working schedule not configured for office '{0}'.").format(
                office_doc.office_name
            )
            office_is_open = False

        if not office_is_open:
            return info_response(
                message=closed_message,
                data={"status": "closed", "categories": [], "services_no_category": []}
            )

        # Отримуємо впорядковані призначення послуг для офісу
        assignments = frappe.get_all(
            "QMS Office Service Assignment",
            filters={"parent": office, "is_active_in_office": 1},
            fields=["service"],
            order_by="idx asc"
        )

        if not assignments:
            result_data = {"categories": [], "services_no_category": []}
            cache_kiosk_services(office, result_data, ttl=600)
            return success_response(data=result_data)

        ordered_service_ids = [a.service for a in assignments]

        # Отримуємо деталі тільки активних та доступних для кіоску послуг
        services_details = frappe.get_all(
            "QMS Service",
            filters={
                "name": ["in", ordered_service_ids],
                "enabled": 1,
                "live_queue_enabled": 1
            },
            fields=["name", "service_name", "category", "icon"]
        )

        active_services_map = {s.name: s for s in services_details}

        # Отримуємо та сортуємо категорії
        category_ids = list(set(s.category for s in services_details if s.category))
        categories_map = {}
        sorted_cat_ids = []

        if category_ids:
            categories_data = frappe.get_all(
                "QMS Service Category",
                filters={"name": ["in", category_ids]},
                fields=["name", "category_name", "display_order"],
                order_by="display_order asc, category_name asc"
            )
            sorted_cat_ids = [cat.name for cat in categories_data]
            categories_map = {
                cat.name: {"label": cat.category_name, "services": []}
                for cat in categories_data
            }

        # Розподіляємо послуги за категоріями
        services_no_category_ordered = []
        temp_categories_services = {cat_id: [] for cat_id in sorted_cat_ids}

        for service_id in ordered_service_ids:
            if service_id in active_services_map:
                service_info = active_services_map[service_id]
                service_data = {
                    "id": service_info.name,
                    "label": service_info.service_name,
                    "icon": service_info.icon or ""
                }

                if service_info.category and service_info.category in temp_categories_services:
                    temp_categories_services[service_info.category].append(service_data)
                else:
                    services_no_category_ordered.append(service_data)

        # Формуємо фінальний список категорій
        final_categories_list = []
        for cat_id in sorted_cat_ids:
            if temp_categories_services[cat_id]:
                final_categories_list.append({
                    "label": categories_map[cat_id]["label"],
                    "services": temp_categories_services[cat_id]
                })

        result_data = {
            "categories": final_categories_list,
            "services_no_category": services_no_category_ordered
        }

        # Кешуємо результат на 10 хвилин
        cache_kiosk_services(office, result_data, ttl=600)

        return success_response(data=result_data)

    except Exception as e:
        log_error("get_kiosk_services_error", str(e), office=office)
        frappe.log_error(frappe.get_traceback(), f"Get Kiosk Services API Error for Office {office}")
        return error_response(
            _("An unexpected error occurred while fetching kiosk services."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=30, window_seconds=60)  # 30 запитів на хвилину (більш обмежено для створення)
def create_live_queue_ticket(service: str, office: str, visitor_phone: str = None):
    """
    API Endpoint для створення нового талону QMS Ticket з Кіоску.

    Args:
        service: ID сервісу
        office: ID офісу
        visitor_phone: Номер телефону відвідувача (опціонально)

    Returns:
        Деталі створеного талону
    """
    log_api_call("create_live_queue_ticket", service=service, office=office)

    try:
        # --- Базова валідація вхідних даних ---
        if not service or not office:
            return error_response(
                _("Service or Office not specified."),
                error_code="MISSING_PARAMS",
                http_status_code=400
            )

        # Перевірка існування записів
        if not frappe.db.exists("QMS Service", service):
            return error_response(
                _("Service '{0}' not found.").format(service),
                error_code="INVALID_SERVICE",
                http_status_code=404
            )

        if not frappe.db.exists("QMS Office", office):
            return error_response(
                _("Office '{0}' not found.").format(office),
                error_code="INVALID_OFFICE",
                http_status_code=404
            )

        # --- Додаткові перевірки ---
        service_doc = frappe.get_cached_doc("QMS Service", service)
        if not service_doc.enabled:
            return error_response(
                _("Service '{0}' is currently inactive.").format(service_doc.service_name),
                error_code="SERVICE_INACTIVE",
                http_status_code=400
            )

        if not service_doc.live_queue_enabled:
            return error_response(
                _("Service '{0}' is not available for live queue.").format(service_doc.service_name),
                error_code="SERVICE_NO_LIVE_QUEUE",
                http_status_code=400
            )

        is_service_in_office = frappe.db.exists("QMS Office Service Assignment", {
            "parent": office,
            "service": service,
            "is_active_in_office": 1
        })

        if not is_service_in_office:
            office_name = frappe.db.get_value("QMS Office", office, "office_name")
            return error_response(
                _("Service '{0}' is not available in office '{1}'.").format(
                    service_doc.service_name, office_name
                ),
                error_code="SERVICE_NOT_IN_OFFICE",
                http_status_code=400
            )

        office_doc = frappe.get_cached_doc("QMS Office", office)
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule"
        )

        if schedule_name:
            if not is_office_open(schedule_name, office_doc.timezone):
                return info_response(
                    _("Office '{0}' is currently closed.").format(office_doc.office_name),
                    data={"office_status": "closed"}
                )
        else:
            return error_response(
                _("Working schedule not configured for office '{0}'.").format(office_doc.office_name),
                error_code="NO_SCHEDULE",
                http_status_code=500
            )

        # --- Валідація номеру телефону ---
        if visitor_phone:
            if not visitor_phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
                log_error("invalid_phone_format", f"Invalid phone format: {visitor_phone}")
                visitor_phone = None

        # --- Створення документу QMS Ticket ---
        new_ticket = frappe.new_doc("QMS Ticket")
        new_ticket.office = office
        new_ticket.service = service
        new_ticket.status = "Waiting"
        new_ticket.issue_time = now()
        if visitor_phone:
            new_ticket.visitor_phone = visitor_phone

        new_ticket.insert(ignore_permissions=True)
        frappe.db.commit()

        # Логуємо створення талону
        log_ticket_event(
            "created",
            new_ticket.name,
            new_ticket.ticket_number,
            office=office,
            service=service
        )

        # --- Успішна відповідь ---
        return success_response(
            message=_("Ticket created successfully."),
            data={
                "ticket_name": new_ticket.name,
                "ticket_number": new_ticket.ticket_number,
                "office": new_ticket.office,
                "service": new_ticket.service
            }
        )

    except frappe.exceptions.ValidationError as e:
        frappe.db.rollback()
        log_error("ticket_validation_error", str(e), service=service, office=office)
        return error_response(str(e), error_code="VALIDATION_ERROR", http_status_code=400)

    except Exception as e:
        frappe.db.rollback()
        log_error("ticket_creation_error", str(e), service=service, office=office)
        frappe.log_error(frappe.get_traceback(), "QMS Ticket Creation API Error")
        return error_response(
            message=_("Failed to create ticket due to an internal error."),
            details=str(e),
            http_status_code=500
        )

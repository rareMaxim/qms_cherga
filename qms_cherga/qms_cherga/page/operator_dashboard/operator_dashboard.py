import frappe
from frappe import _  # Імпортуємо функцію перекладу
from frappe.utils import get_fullname, today, now_datetime, time_diff_in_seconds, flt, get_datetime

from qms_cherga.utils.response import success_response, error_response, info_response


@frappe.whitelist()
def get_initial_data():
    """
    Отримує початкові дані для Дашбоарду Оператора (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            # 401 Unauthorized
            # Повідомлення Frappe за замовчуванням вже перекладається
            return error_response(_("Authentication required."), http_status_code=401)

        operator_info = {}
        current_ticket_details = None
        available_service_points_list = []

        # Знаходимо запис Оператора (використовуємо get_doc для перевірки існування)
        try:
            operator_doc = frappe.get_doc(
                "QMS Operator", {"user": current_user})
            if not operator_doc.is_active:
                # 403 Forbidden - оператор існує, але не активний
                return error_response(
                    message=_("Operator record for user {0} is not active.").format(
                        current_user),
                    error_code="OPERATOR_INACTIVE",
                    http_status_code=403)
        except frappe.DoesNotExistError:
            # 404 Not Found
            return error_response(message=_("QMS Operator record not found for user {0}.").format(current_user),
                                  http_status_code=404)

        office_id = operator_doc.default_office
        office_name_full = _("Not Specified")  # Перекладено
        if office_id:
            try:
                office_doc_data = frappe.db.get_value(
                    "QMS Office", office_id, ["office_name", "name"], as_dict=True)
                if office_doc_data:
                    office_name_full = office_doc_data.office_name or office_doc_data.name  # Fallback на ID
                    # Отримуємо точки обслуговування
                    available_service_points = frappe.get_all(
                        "QMS Service Point",
                        filters={"office": office_id, "is_active": 1},
                        fields=["name", "point_name"],
                        order_by="point_name asc"
                    )
                    available_service_points_list = [
                        {"value": p.name, "label": p.point_name} for p in available_service_points]
                else:
                    # Офіс, вказаний у оператора, не знайдено - помилка конфігурації
                    frappe.log_warning(
                        f"Office '{office_id}' linked to operator '{operator_doc.name}' not found.", "Operator Config Warning")
                    office_name_full = _("Error: Office '{0}' not found").format(
                        office_id)  # Перекладено

            except Exception as e:
                # Логуємо помилку отримання даних офісу/точок
                frappe.log_error(
                    f"Error fetching office/service point details for office {office_id}: {e}", "Initial Data Error")
                office_name_full = _(
                    "Error loading office data")  # Перекладено

        operator_info = {
            "qms_operator_name": operator_doc.name,
            "full_name": operator_doc.full_name or get_fullname(current_user),
            "default_office_id": office_id,
            "default_office_name": office_name_full,
            # Потребує кращої логіки, перекладено
            "current_status": _("Available")
        }

        # Шукаємо поточний активний талон
        active_ticket = frappe.get_all(
            "QMS Ticket",
            filters={"operator": current_user,
                     "status": ["in", ["Serving", "Called"]]},
            fields=["name", "ticket_number", "service", "service_point", "status",
                    "visitor_phone", "call_time", "start_service_time", "office"],
            order_by="modified desc",
            limit=1
        )

        if active_ticket:
            ticket_data = active_ticket[0]
            service_name = frappe.db.get_value(
                "QMS Service", ticket_data.service, "service_name") if ticket_data.service else _("N/A")  # Перекладено
            service_point_name = frappe.db.get_value(
                "QMS Service Point", ticket_data.service_point, "point_name") if ticket_data.service_point else _("N/A")  # Перекладено

            current_ticket_details = ticket_data.copy()
            current_ticket_details["service_name"] = service_name
            current_ticket_details["service_point_name"] = service_point_name

        # Успішна відповідь
        return success_response(data={
            "operator_info": operator_info,
            "current_ticket": current_ticket_details,  # Може бути None
            "available_service_points": available_service_points_list
        })

    except Exception as e:
        # Обробка неочікуваних помилок
        frappe.log_error(frappe.get_traceback(), "Get Initial Data API Error")
        return error_response(
            # Перекладено
            message=_(
                "An unexpected error occurred while fetching initial data."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist()
def get_queue_stats(office: str):
    """
    Отримує базову статистику черги (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    if not office:
        # 400 Bad Request
        # Перекладено
        return error_response(_("Office ID is required."), http_status_code=400)

    try:
        if not frappe.db.exists("QMS Office", office):
            # 404 Not Found
            # Перекладено
            return error_response(_("Office '{0}' not found.").format(office), http_status_code=404)

        waiting_count = frappe.db.count(
            "QMS Ticket", {"status": "Waiting", "office": office})
        served_count = frappe.db.count("QMS Ticket", {
            "status": "Completed",
            "office": office,
            "modified": [">=", today() + " 00:00:00"]
        })

        return success_response(data={
            "waiting": waiting_count,
            "served_today": served_count
        })
    except Exception as e:
        frappe.log_error(frappe.get_traceback(),
                         f"Get Queue Stats Error for Office {office}")
        # 500 Internal Server Error
        return error_response(
            # Перекладено
            message=_(
                "An unexpected error occurred while fetching queue statistics."),
            details=str(e),
            http_status_code=500
        )

# Допоміжна функція для отримання та валідації талону


def _get_validated_ticket(ticket_name: str, expected_statuses: list = None):
    """Gets ticket doc, checks existence and operator match."""
    current_user = frappe.session.user
    if current_user == "Guest":
        # Викидаємо виняток, який буде зловлено зовнішньою функцією
        raise frappe.AuthenticationError(
            _("Authentication required."))  # Перекладено

    try:
        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)
    except frappe.DoesNotExistError:
        # Викидаємо виняток
        # Повідомлення Frappe має перекладатися
        raise frappe.DoesNotExistError(
            _("Ticket {0} not found.").format(ticket_name))  # Перекладено

    if ticket_doc.operator != current_user:
        # Викидаємо виняток
        raise frappe.PermissionError(
            _("Cannot modify a ticket assigned to another operator."))  # Перекладено

    if expected_statuses and ticket_doc.status not in expected_statuses:
        # Викидаємо виняток
        raise frappe.ValidationError(
            _("Invalid ticket status '{0}'. Expected one of: {1}.").format(ticket_doc.status, expected_statuses))  # Перекладено

    return ticket_doc


@frappe.whitelist()
def start_serving_ticket(ticket_name: str):
    """
    Розпочинає обслуговування талону (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        # Отримуємо та валідуємо талон
        ticket_doc = _get_validated_ticket(
            ticket_name, expected_statuses=["Called"])

        # Оновлення документа
        ticket_doc.status = "Serving"
        ticket_doc.start_service_time = now_datetime()
        ticket_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Отримуємо додаткові дані для відповіді
        service_name = frappe.db.get_value(
            "QMS Service", ticket_doc.service, "service_name") if ticket_doc.service else _("N/A")  # Перекладено
        service_point_name = frappe.db.get_value(
            "QMS Service Point", ticket_doc.service_point, "point_name") if ticket_doc.service_point else _("N/A")  # Перекладено

        ticket_info = ticket_doc.as_dict()
        ticket_info["service_name"] = service_name
        ticket_info["service_point_name"] = service_point_name

        return success_response(
            message=_("Started serving ticket {0}.").format(
                ticket_doc.ticket_number),  # Перекладено
            data={"ticket_info": ticket_info}
        )

    # Обробляємо специфічні помилки валідації
    except frappe.AuthenticationError as e:
        return error_response(str(e), http_status_code=401)
    except frappe.DoesNotExistError as e:
        return error_response(str(e), http_status_code=404)
    except frappe.PermissionError as e:
        return error_response(str(e), http_status_code=403)
    except frappe.ValidationError as e:
        # 409 Conflict або 400 Bad Request
        return error_response(str(e), error_code="INVALID_STATUS", http_status_code=409)
    except Exception as e:
        # Загальні помилки
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(),
                         "Start Serving Ticket API Error")
        return error_response(
            # Перекладено
            message=_("An unexpected error occurred while starting service."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist()
def finish_service_ticket(ticket_name: str):
    """
    Завершує обслуговування талону (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        ticket_doc = _get_validated_ticket(
            ticket_name, expected_statuses=["Serving"])

        completion_time = now_datetime()
        ticket_doc.status = "Completed"
        ticket_doc.completion_time = completion_time

        if ticket_doc.start_service_time:
            service_duration_seconds = time_diff_in_seconds(
                completion_time, ticket_doc.start_service_time)
            ticket_doc.actual_service_time_mins = round(
                flt(service_duration_seconds) / 60.0, 2)
        else:
            ticket_doc.actual_service_time_mins = 0

        ticket_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Перекладено
        return success_response(message=_("Service for ticket {0} completed.").format(ticket_doc.ticket_number))

    except frappe.AuthenticationError as e:
        return error_response(str(e), http_status_code=401)
    except frappe.DoesNotExistError as e:
        return error_response(str(e), http_status_code=404)
    except frappe.PermissionError as e:
        return error_response(str(e), http_status_code=403)
    except frappe.ValidationError as e:
        return error_response(str(e), error_code="INVALID_STATUS", http_status_code=409)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(),
                         "Finish Service Ticket API Error")
        # Перекладено
        return error_response(_("An unexpected error occurred while finishing service."), details=str(e), http_status_code=500)


@frappe.whitelist()
def mark_no_show(ticket_name: str):
    """
    Відмічає талон як "Не з'явився" (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        # Дозволяємо відмітку якщо статус Called або Serving
        ticket_doc = _get_validated_ticket(
            ticket_name, expected_statuses=["Called", "Serving"])

        ticket_doc.status = "NoShow"
        # Можна очистити інші поля за потреби
        # ticket_doc.start_service_time = None
        # ticket_doc.completion_time = None
        # ticket_doc.actual_service_time_mins = None
        ticket_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Перекладено
        return success_response(message=_("Ticket {0} marked as 'No Show'.").format(ticket_doc.ticket_number))

    except frappe.AuthenticationError as e:
        return error_response(str(e), http_status_code=401)
    except frappe.DoesNotExistError as e:
        return error_response(str(e), http_status_code=404)
    except frappe.PermissionError as e:
        return error_response(str(e), http_status_code=403)
    except frappe.ValidationError as e:
        return error_response(str(e), error_code="INVALID_STATUS", http_status_code=409)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Mark No Show API Error")
        # Перекладено
        return error_response(_("An unexpected error occurred while marking as 'No Show'."), details=str(e), http_status_code=500)


@frappe.whitelist()
def hold_ticket(ticket_name: str):
    """
    Відкладає талон (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        # Відкласти можна лише талон, що обслуговується
        ticket_doc = _get_validated_ticket(
            ticket_name, expected_statuses=["Serving"])

        ticket_doc.status = "Postponed"
        # Можна додати логіку збереження часу відкладення
        ticket_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Перекладено
        return success_response(message=_("Ticket {0} postponed.").format(ticket_doc.ticket_number))

    except frappe.AuthenticationError as e:
        return error_response(str(e), http_status_code=401)
    except frappe.DoesNotExistError as e:
        return error_response(str(e), http_status_code=404)
    except frappe.PermissionError as e:
        return error_response(str(e), http_status_code=403)
    except frappe.ValidationError as e:
        return error_response(str(e), error_code="INVALID_STATUS", http_status_code=409)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Hold Ticket API Error")
        # Перекладено
        return error_response(_("An unexpected error occurred while postponing the ticket."), details=str(e), http_status_code=500)


@frappe.whitelist()
def get_my_held_tickets():
    """
    Отримує список відкладених талонів поточного оператора (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            # Гості не мають відкладених талонів, повертаємо успіх з порожніми даними
            return success_response(data={"held_tickets": []})

        held_tickets_data = frappe.get_all(
            "QMS Ticket",
            filters={"operator": current_user, "status": "Postponed"},
            fields=["name", "ticket_number", "service"],
            order_by="modified desc"
        )

        result_list = []
        if held_tickets_data:
            service_ids = list(
                set(t.service for t in held_tickets_data if t.service))
            service_names_map = {}
            if service_ids:
                services = frappe.get_all("QMS Service", filters={
                                          "name": ["in", service_ids]}, fields=["name", "service_name"])
                service_names_map = {s.name: s.service_name for s in services}

            for ticket in held_tickets_data:
                ticket_dict = ticket.copy()
                # Змінено: додано _() для N/A
                ticket_dict["service_name"] = service_names_map.get(
                    ticket.service, ticket.service or _("N/A"))
                result_list.append(ticket_dict)

        return success_response(data={"held_tickets": result_list})

    except Exception as e:
        frappe.log_error(frappe.get_traceback(),
                         "Get My Held Tickets API Error")
        # Перекладено
        return error_response(_("An unexpected error occurred while fetching held tickets."), details=str(e), http_status_code=500)


@frappe.whitelist()
def recall_ticket(ticket_name: str):
    """
    Повертає відкладений талон до роботи (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        # Використовуємо _get_validated_ticket для перевірок
        ticket_doc = _get_validated_ticket(
            ticket_name, expected_statuses=["Postponed"])

        # --- Отримуємо назви для відповіді ---
        service_name = frappe.db.get_value(
            "QMS Service", ticket_doc.service, "service_name") if ticket_doc.service else _("N/A")  # Перекладено
        service_point_name = frappe.db.get_value(
            "QMS Service Point", ticket_doc.service_point, "point_name") if ticket_doc.service_point else _("Not Assigned")  # Перекладено

        # --- Оновлення Полів Документа ---
        ticket_doc.status = "Called"  # Ставимо статус "Викликано"
        ticket_doc.call_time = now_datetime()  # Новий час "виклику"
        # Очищаємо попередні дані обслуговування
        ticket_doc.start_service_time = None
        ticket_doc.completion_time = None
        ticket_doc.actual_service_time_mins = None
        # Можливо, скинути service_point, якщо логіка вимагає перепризначення точки
        # ticket_doc.service_point = None

        ticket_doc.save(ignore_permissions=True)
        ticket_doc.reload()  # Оновити дані після збереження
        frappe.db.commit()

        # --- Формуємо відповідь з назвами ---
        ticket_info = ticket_doc.as_dict()
        ticket_info["service_name"] = service_name
        ticket_info["service_point_name"] = service_point_name

        # --- Успішна відповідь API ---
        return success_response(
            message=_("Ticket {0} recalled successfully.").format(
                ticket_doc.ticket_number),  # Перекладено
            data={"ticket_info": ticket_info}
        )

    except frappe.AuthenticationError as e:
        return error_response(str(e), http_status_code=401)
    except frappe.DoesNotExistError as e:
        return error_response(str(e), http_status_code=404)
    except frappe.PermissionError as e:
        return error_response(str(e), http_status_code=403)
    except frappe.ValidationError as e:
        return error_response(str(e), error_code="INVALID_STATUS", http_status_code=409)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Recall Ticket API Error")
        # Перекладено
        return error_response(_("An unexpected error occurred while recalling the ticket."), details=str(e), http_status_code=500)

"""
Operator Dashboard API endpoints for QMS system.
"""
import frappe
from frappe import _
from frappe.utils import now_datetime, today

from qms_cherga.utils.response import error_response, info_response, success_response
from qms_cherga.utils.logger import log_api_call, log_ticket_event, log_error


@frappe.whitelist()
def get_operator_dashboard_data():
    """
    Отримує всі початкові дані для панелі керування оператора.

    Returns:
        Інформація про оператора, точки обслуговування, активний талон, статистику
    """
    user = frappe.session.user
    log_api_call("get_operator_dashboard_data", user=user)

    if user == "Guest":
        return error_response(_("Authentication required."), http_status_code=401)

    try:
        operator = frappe.get_doc("QMS Operator", {"user": user, "is_active": 1})
    except frappe.DoesNotExistError:
        return error_response(
            _("Active QMS Operator record not found for user {0}.").format(user),
            error_code="OPERATOR_NOT_FOUND",
            http_status_code=404
        )

    try:
        office_id = operator.default_office

        # Інформація про оператора та його офіс
        operator_info = {
            "name": operator.name,
            "full_name": operator.full_name,
            "user": operator.user,
            "office": office_id,
            "office_name": frappe.db.get_value("QMS Office", office_id, "office_name")
        }

        # Доступні оператору точки обслуговування (Service Points)
        service_points = frappe.get_all(
            "QMS Service Point",
            filters={"office": office_id, "is_active": 1},
            fields=["name", "point_name"],
            order_by="point_name"
        )

        # Поточний активний талон оператора (якщо є)
        active_ticket = frappe.get_all(
            "QMS Ticket",
            filters={"operator": user, "status": ["in", ["Called", "Serving"]]},
            fields=[
                "name", "ticket_number", "service", "status",
                "issue_time", "call_time", "start_service_time",
                "visitor_name", "visitor_phone"
            ],
            limit=1
        )

        active_ticket_doc = None
        if active_ticket:
            active_ticket_doc = active_ticket[0]
            active_ticket_doc['service_name'] = frappe.db.get_value(
                "QMS Service", active_ticket_doc.service, "service_name"
            )

        # ОТРИМАННЯ СТАТИСТИКИ ТА ВІДКЛАДЕНИХ ТАЛОНІВ
        live_data = get_live_data(office=office_id, as_dict=True)

        return success_response(data={
            "operator_info": operator_info,
            "service_points": service_points,
            "active_ticket": active_ticket_doc,
            "queue_stats": live_data.get("stats"),
            "postponed_tickets": live_data.get("postponed_tickets")
        })

    except Exception as e:
        log_error("operator_dashboard_data_error", str(e), user=user)
        frappe.log_error(frappe.get_traceback(), "Get Operator Dashboard Data API Error")
        return error_response(
            _("An unexpected error occurred while fetching initial data."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist()
def get_live_data(office: str, as_dict: bool = False):
    """
    Отримує "живі" дані для панелі оператора: статистику та відкладені талони.

    Args:
        office: ID офісу
        as_dict: Повертати як словник (для внутрішнього використання)

    Returns:
        Статистика черги та список відкладених талонів
    """
    log_api_call("get_live_data", office=office)

    if not frappe.db.exists("QMS Office", office):
        response = error_response(_("Office not found"), http_status_code=404)
        return response if not as_dict else {}

    try:
        # Статистика черги для офісу
        stats = {
            "waiting": frappe.db.count("QMS Ticket", {"office": office, "status": "Waiting"}),
            "serving": frappe.db.count("QMS Ticket", {"office": office, "status": "Serving"}),
            "finished_today": frappe.db.count("QMS Ticket", {
                "office": office,
                "status": ["in", ["Completed", "NoShow"]],
                "completion_time": [">=", today()]
            })
        }

        # Список відкладених талонів
        postponed_tickets = frappe.get_all(
            "QMS Ticket",
            filters={"office": office, "status": "Postponed"},
            fields=["name", "ticket_number", "service"],
            order_by="modified desc"
        )

        for ticket in postponed_tickets:
            ticket['service_name'] = frappe.db.get_value(
                "QMS Service", ticket.service, "service_name"
            )

        data_to_return = {
            "stats": stats,
            "postponed_tickets": postponed_tickets
        }

        return success_response(data=data_to_return) if not as_dict else data_to_return

    except Exception as e:
        log_error("get_live_data_error", str(e), office=office)
        frappe.log_error(frappe.get_traceback(), f"Get Live Data API Error for Office {office}")
        response = error_response(
            _("An unexpected error occurred while fetching live data."),
            details=str(e),
            http_status_code=500
        )
        return response if not as_dict else {}


@frappe.whitelist()
def call_next_visitor(service_point_name: str):
    """
    Викликає наступного відвідувача з черги з використанням pessimistic locking.

    Args:
        service_point_name: ID точки обслуговування

    Returns:
        Інформація про викликаний талон
    """
    current_user = frappe.session.user
    log_api_call("call_next_visitor", user=current_user, service_point=service_point_name)

    try:
        if current_user == "Guest":
            return error_response(_("Authentication required."), http_status_code=401)

        # Перевірка, чи є у оператора вже активний талон
        active_ticket = frappe.db.exists("QMS Ticket", {
            "operator": current_user,
            "status": ["in", ["Called", "Serving"]]
        })

        if active_ticket:
            return error_response(
                _("You already have an active ticket. Please finish or postpone the current one before calling a new visitor."),
                error_code="ACTIVE_TICKET_EXISTS",
                http_status_code=409
            )

        operator_doc = frappe.get_doc("QMS Operator", {"user": current_user, "is_active": 1})
        operator_skills = [skill.service for skill in operator_doc.get("operator_skills", [])]

        if not operator_skills:
            return error_response(
                _("Operator {0} has no skills assigned.").format(current_user),
                error_code="NO_SKILLS",
                http_status_code=400
            )

        service_point_data = frappe.db.get_value(
            "QMS Service Point",
            service_point_name,
            ["office", "point_name"],
            as_dict=True
        )

        if not service_point_data:
            return error_response(
                _("Service point with ID '{0}' not found.").format(service_point_name),
                http_status_code=404
            )

        office_id = service_point_data.office
        actual_service_point_display_name = service_point_data.point_name

        if not office_id:
            return error_response(
                _("Could not determine Office for service point '{0}'.").format(
                    actual_service_point_display_name
                ),
                http_status_code=500
            )

        # ВИПРАВЛЕННЯ RACE CONDITION: Використовуємо SELECT FOR UPDATE
        # Це забезпечує pessimistic locking - інші транзакції чекатимуть
        frappe.db.begin()

        # SQL запит з FOR UPDATE для блокування рядка
        waiting_tickets_query = """
            SELECT name
            FROM `tabQMS Ticket`
            WHERE office = %(office)s
            AND status = 'Waiting'
            AND service IN %(skills)s
            ORDER BY priority DESC, creation ASC
            LIMIT 1
            FOR UPDATE
        """

        waiting_tickets = frappe.db.sql(
            waiting_tickets_query,
            {"office": office_id, "skills": operator_skills},
            as_dict=True
        )

        if not waiting_tickets:
            frappe.db.rollback()
            return info_response(
                _("No tickets found in queue for calling."),
                data={"ticket_info": None}
            )

        next_ticket_name = waiting_tickets[0].name

        # Отримуємо та оновлюємо документ
        ticket_doc = frappe.get_doc("QMS Ticket", next_ticket_name)

        # Перевіряємо ще раз статус (double-check після lock)
        if ticket_doc.status != "Waiting":
            frappe.db.rollback()
            return info_response(
                _("The ticket was already called by another operator."),
                data={"ticket_info": None}
            )

        # Оновлюємо талон
        ticket_doc.status = "Called"
        ticket_doc.call_time = now_datetime()
        ticket_doc.operator = current_user
        ticket_doc.service_point = service_point_name

        ticket_doc.save(ignore_permissions=True)
        frappe.db.commit()

        # Логуємо виклик талону
        log_ticket_event(
            "called",
            ticket_doc.name,
            ticket_doc.ticket_number,
            operator=current_user,
            service_point=service_point_name
        )

        return success_response(
            message=_("Ticket {0} called to point {1}.").format(
                ticket_doc.ticket_number, actual_service_point_display_name
            ),
            data={"ticket_info": ticket_doc.as_dict()}
        )

    except frappe.DoesNotExistError as e:
        frappe.db.rollback()
        log_error("call_next_visitor_not_found", str(e), user=current_user)
        doc_type_name = str(e).split("'")[1] if "'" in str(e) else _("Document")
        return error_response(
            _("{0} not found.").format(doc_type_name),
            details=frappe.get_traceback(),
            http_status_code=404
        )

    except frappe.PermissionError as e:
        frappe.db.rollback()
        log_error("call_next_visitor_permission", str(e), user=current_user)
        return error_response(
            _("Permission denied."),
            details=frappe.get_traceback(),
            http_status_code=403
        )

    except Exception as e:
        frappe.db.rollback()
        log_error("call_next_visitor_error", str(e), user=current_user)
        frappe.log_error(frappe.get_traceback(), "Call Next Visitor API Error")
        return error_response(
            message=_("An unexpected error occurred while calling the next visitor."),
            details=str(e),
            http_status_code=500
        )


def _update_ticket_status(ticket_name, target_status, user, extra_data=None):
    """
    Внутрішня функція для зміни статусу талону.

    Args:
        ticket_name: ID талону
        target_status: Цільовий статус
        user: Користувач який виконує операцію
        extra_data: Додаткові дані для оновлення

    Returns:
        Оновлений талон або повідомлення про помилку
    """
    try:
        ticket = frappe.get_doc("QMS Ticket", ticket_name)

        if ticket.status not in ["Called", "Serving", "Postponed"]:
            # Дозвіл на виклик з очікування
            if not (target_status == "Called" and ticket.status == "Waiting"):
                return error_response(
                    _("Ticket {0} is not in a state that can be modified by the operator.").format(
                        ticket.ticket_number
                    ),
                    error_code="INVALID_TICKET_STATE",
                    http_status_code=400
                )

        ticket.status = target_status
        if extra_data:
            ticket.update(extra_data)

        ticket.save(ignore_permissions=True)
        frappe.db.commit()

        # Логуємо зміну статусу
        log_ticket_event(
            target_status.lower(),
            ticket.name,
            ticket.ticket_number,
            operator=user
        )

        return success_response(data=ticket.as_dict())

    except frappe.DoesNotExistError:
        return error_response(
            _("Ticket {0} not found.").format(ticket_name),
            http_status_code=404
        )

    except Exception as e:
        frappe.db.rollback()
        log_error("update_ticket_status_error", str(e), ticket=ticket_name, status=target_status)
        frappe.log_error(
            frappe.get_traceback(),
            f"Update Ticket Status API Error for {ticket_name}"
        )
        return error_response(
            _("An unexpected error occurred while updating the ticket."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist()
def start_service(ticket_name: str):
    """
    Переводить талон у статус 'Serving'.

    Args:
        ticket_name: ID талону

    Returns:
        Оновлений талон
    """
    log_api_call("start_service", ticket=ticket_name)
    return _update_ticket_status(
        ticket_name,
        "Serving",
        frappe.session.user,
        {"start_service_time": now_datetime()}
    )


@frappe.whitelist()
def finish_service(ticket_name: str):
    """
    Переводить талон у статус 'Completed'.

    Args:
        ticket_name: ID талону

    Returns:
        Оновлений талон
    """
    log_api_call("finish_service", ticket=ticket_name)
    return _update_ticket_status(
        ticket_name,
        "Completed",
        frappe.session.user,
        {"completion_time": now_datetime()}
    )


@frappe.whitelist()
def mark_as_no_show(ticket_name: str):
    """
    Переводить талон у статус 'NoShow'.

    Args:
        ticket_name: ID талону

    Returns:
        Оновлений талон
    """
    log_api_call("mark_as_no_show", ticket=ticket_name)
    return _update_ticket_status(
        ticket_name,
        "NoShow",
        frappe.session.user,
        {"completion_time": now_datetime()}
    )


@frappe.whitelist()
def postpone_ticket(ticket_name: str):
    """
    Переводить талон у статус 'Postponed'.

    Args:
        ticket_name: ID талону

    Returns:
        Оновлений талон
    """
    log_api_call("postpone_ticket", ticket=ticket_name)
    return _update_ticket_status(ticket_name, "Postponed", frappe.session.user)


@frappe.whitelist()
def recall_ticket(ticket_name: str, service_point: str):
    """
    Повторно викликає відкладений талон.

    Args:
        ticket_name: ID талону
        service_point: ID точки обслуговування

    Returns:
        Оновлений талон
    """
    log_api_call("recall_ticket", ticket=ticket_name, service_point=service_point)

    if not service_point:
        return error_response(
            _("Service point is required to recall a ticket."),
            http_status_code=400
        )

    return _update_ticket_status(
        ticket_name,
        "Called",
        frappe.session.user,
        {
            "call_time": now_datetime(),
            "service_point": service_point,
            "operator": frappe.session.user
        }
    )

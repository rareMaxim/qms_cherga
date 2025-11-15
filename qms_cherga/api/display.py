"""
Display Board API endpoints for QMS system.
"""
import frappe
from frappe import _
from frappe.utils import get_datetime, cint, today, now

from qms_cherga.utils.response import error_response, info_response, success_response
from qms_cherga.utils.rate_limiter import rate_limit
from qms_cherga.utils.logger import log_api_call, log_error
from qms_cherga.api.common import is_office_open


@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=120, window_seconds=60)  # 120 запитів на хвилину (часті оновлення)
def ping_display_board(office_id: str, client_timestamp: str):
    """
    Heartbeat для display board.

    Args:
        office_id: ID офісу
        client_timestamp: Часова мітка клієнта

    Returns:
        Підтвердження через WebSocket
    """
    log_api_call("ping_display_board", office_id=office_id)

    if not office_id:
        return error_response(_("Office ID is required for ping."), http_status_code=400)

    try:
        message_to_send = {
            'status': 'ok',
            'office_id': office_id,
            'server_time': now(),
            'client_timestamp_received': client_timestamp
        }

        frappe.publish_realtime(
            event='display_board_pong_ack',
            message=message_to_send,
            after_commit=True
        )

        return success_response(message="Pong will be sent via WebSocket.")

    except Exception as e:
        log_error("ping_error", str(e), office_id=office_id)
        frappe.log_error(
            f"Failed to publish pong for office {office_id}: {e}",
            "QMS Ping Error"
        )
        return error_response(
            message=_("Ping received, but pong dispatch via WebSocket failed."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=60, window_seconds=60)  # 60 запитів на хвилину
def get_display_data(office: str, limit_called: int = 3, limit_waiting: int = 20):
    """
    Отримує дані для публічного дисплея черги.

    Args:
        office: ID офісу
        limit_called: Ліміт викликаних талонів для відображення
        limit_waiting: Ліміт талонів в очікуванні для відображення

    Returns:
        Дані для display board (викликані та очікують талони, статус офісу)
    """
    log_api_call("get_display_data", office=office, limit_called=limit_called, limit_waiting=limit_waiting)

    try:
        limit_called = cint(limit_called)
        limit_waiting = cint(limit_waiting)

        if not office:
            return error_response(_("Office ID is required."), http_status_code=400)

        if not frappe.db.exists("QMS Office", office):
            return error_response(_("Office '{0}' not found.").format(office), http_status_code=404)

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

        # Отримуємо інформаційне повідомлення
        info_message_text = office_doc.display_message_text or None

        if not office_is_open:
            return info_response(
                message=closed_message,
                data={
                    "office_status": "closed",
                    "last_called": [],
                    "waiting": [],
                    "info_message": info_message_text
                }
            )

        # --- Отримуємо останні викликані/обслужені ---
        last_called = []
        potential_called = frappe.get_all(
            "QMS Ticket",
            filters={
                "office": office,
                "status": "Called",
                "call_time": [">=", today() + " 00:00:00"]
            },
            fields=["name", "ticket_number", "service_point", "call_time"],
            order_by="call_time desc",
            limit_page_length=limit_called
        )

        # Отримуємо назви точок одним запитом
        point_ids = list(set(t.service_point for t in potential_called if t.service_point))
        point_names_map = {}

        if point_ids:
            points = frappe.get_all(
                "QMS Service Point",
                filters={"name": ["in", point_ids]},
                fields=["name", "point_name"]
            )
            point_names_map = {p.name: p.point_name for p in points}

        for ticket in potential_called:
            short_ticket_number = ticket.ticket_number.split('-')[-1] if ticket.ticket_number and '-' in ticket.ticket_number else ticket.ticket_number
            call_time_dt = get_datetime(ticket.call_time) if ticket.call_time else None
            last_called.append({
                "ticket": short_ticket_number or ticket.name,
                "window": point_names_map.get(ticket.service_point, "N/A"),
                "time": call_time_dt.strftime("%H:%M") if call_time_dt else "--:--"
            })

        # --- Отримуємо наступних у черзі ---
        waiting_tickets = []
        waiting_raw = frappe.get_all(
            "QMS Ticket",
            filters={"office": office, "status": "Waiting"},
            fields=["name", "ticket_number", "service"],
            order_by="priority desc, creation asc",
            limit_page_length=limit_waiting
        )

        # Отримуємо назви послуг одним запитом
        service_ids_waiting = list(set(row.service for row in waiting_raw if row.service))
        service_names_map_waiting = {}

        if service_ids_waiting:
            services = frappe.get_all(
                "QMS Service",
                filters={"name": ["in", service_ids_waiting]},
                fields=["name", "service_name"]
            )
            service_names_map_waiting = {s.name: s.service_name for s in services}

        for row in waiting_raw:
            short_ticket_number = row.ticket_number.split('-')[-1] if row.ticket_number and '-' in row.ticket_number else row.ticket_number
            waiting_tickets.append({
                "ticket": short_ticket_number or row.name,
                "service": service_names_map_waiting.get(row.service, _("Service not specified")),
                "service_id": row.service
            })

        # Успішна відповідь для відкритого офісу
        return success_response(data={
            "office_status": "open",
            "last_called": last_called,
            "waiting": waiting_tickets,
            "info_message": info_message_text
        })

    except Exception as e:
        log_error("get_display_data_error", str(e), office=office)
        frappe.log_error(frappe.get_traceback(), f"Get Display Data API Error for Office {office}")
        return error_response(
            message=_("An unexpected error occurred while fetching display data."),
            details=str(e),
            http_status_code=500
        )

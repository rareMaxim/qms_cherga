"""
QMS Cherga API Module

Модульна структура API для системи управління чергами.
"""

# Імпортуємо всі публічні функції для зворотної сумісності
from qms_cherga.api.common import office_room, is_office_open, get_working_intervals_for_date
from qms_cherga.api.kiosk import get_kiosk_services, create_live_queue_ticket, get_office_info
from qms_cherga.api.display import get_display_data, ping_display_board
from qms_cherga.api.operator import (
    get_operator_dashboard_data,
    get_live_data,
    call_next_visitor,
    start_service,
    finish_service,
    mark_as_no_show,
    postpone_ticket,
    recall_ticket
)
from qms_cherga.api.appointments import (
    get_available_appointment_slots,
    create_appointment_ticket
)

__all__ = [
    # Common utilities
    "office_room",
    "is_office_open",
    "get_working_intervals_for_date",

    # Kiosk API
    "get_kiosk_services",
    "create_live_queue_ticket",
    "get_office_info",

    # Display Board API
    "get_display_data",
    "ping_display_board",

    # Operator API
    "get_operator_dashboard_data",
    "get_live_data",
    "call_next_visitor",
    "start_service",
    "finish_service",
    "mark_as_no_show",
    "postpone_ticket",
    "recall_ticket",

    # Appointments API
    "get_available_appointment_slots",
    "create_appointment_ticket",
]

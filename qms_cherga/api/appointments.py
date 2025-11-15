"""
Appointments API endpoints for QMS system.
"""
import frappe
from frappe import _
from frappe.utils import get_datetime, get_system_timezone, get_date_str, now
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime, timedelta

from qms_cherga.utils.response import error_response, info_response, success_response
from qms_cherga.utils.rate_limiter import rate_limit
from qms_cherga.utils.logger import log_api_call, log_ticket_event, log_error
from qms_cherga.api.common import get_working_intervals_for_date

# Обмеження на кількість слотів в одному робочому інтервалі
MAX_SLOT_ITERATIONS_PER_INTERVAL = 1000


@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=30, window_seconds=60)  # 30 запитів на хвилину
def get_available_appointment_slots(service: str, office: str, date: str):
    """
    Отримує список доступних часових слотів для попереднього запису.

    Args:
        service: ID сервісу
        office: ID офісу
        date: Дата в форматі YYYY-MM-DD

    Returns:
        Список доступних слотів для запису
    """
    log_api_call("get_available_appointment_slots", service=service, office=office, date=date)

    try:
        # --- Валідація ---
        if not service or not office or not date:
            return error_response(
                _("Service, Office, and Date are required."),
                error_code="MISSING_PARAMS",
                http_status_code=400
            )

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

        # Валідація дати
        try:
            target_date = datetime.fromisoformat(date).date()
        except ValueError:
            return error_response(
                _("Invalid date format provided. Use YYYY-MM-DD."),
                error_code="INVALID_DATE_FORMAT",
                http_status_code=400
            )

        # Перевірка часової зони та дати відносно поточної
        office_doc = frappe.get_cached_doc("QMS Office", office)
        office_tz_str = office_doc.timezone or get_system_timezone()

        try:
            office_tz = ZoneInfo(office_tz_str)
            now_in_office_tz = datetime.now(office_tz).date()

            if target_date < now_in_office_tz:
                return info_response(
                    _("Cannot book appointments for past dates."),
                    data={"slots": [], "is_available": False}
                )
        except ZoneInfoNotFoundError:
            return error_response(
                _("Invalid office timezone configured: {0}").format(office_tz_str),
                error_code="INVALID_TIMEZONE",
                http_status_code=500
            )

        # --- Отримання налаштувань ---
        service_doc = frappe.get_cached_doc("QMS Service", service)
        avg_duration_mins = service_doc.avg_duration_mins or 15
        slot_duration = timedelta(minutes=avg_duration_mins)

        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule"
        )

        if not schedule_name:
            return error_response(
                _("Working schedule not configured for office '{0}'.").format(office_doc.office_name),
                error_code="NO_SCHEDULE",
                http_status_code=500
            )

        # --- Визначення робочих інтервалів на задану дату ---
        working_intervals = get_working_intervals_for_date(schedule_name, target_date, office_tz_str)

        if not working_intervals:
            return info_response(
                _("Office is closed on {0}.").format(get_date_str(target_date)),
                data={"slots": [], "is_available": False}
            )

        # --- Отримання існуючих записів ---
        existing_appointments = frappe.get_all(
            "QMS Ticket",
            filters={
                "office": office,
                "service": service,
                "is_appointment": 1,
                "status": ["!=", "Cancelled"],
                "appointment_datetime": ["between", (f"{date} 00:00:00", f"{date} 23:59:59")]
            },
            fields=["appointment_datetime"]
        )

        booked_slots = {
            get_datetime(appt.appointment_datetime).astimezone(office_tz).time()
            for appt in existing_appointments if appt.appointment_datetime
        }

        # --- Генерація доступних слотів ---
        available_slots = []
        now_time_office = datetime.now(office_tz).time()

        for start_work, end_work in working_intervals:
            current_slot_time = start_work
            iteration_count = 0

            while current_slot_time < end_work:
                iteration_count += 1

                # Перевірка на перевищення ліміту ітерацій
                if iteration_count > MAX_SLOT_ITERATIONS_PER_INTERVAL:
                    log_error(
                        "slot_generation_limit_exceeded",
                        f"Exceeded MAX_SLOT_ITERATIONS_PER_INTERVAL ({MAX_SLOT_ITERATIONS_PER_INTERVAL})",
                        service=service,
                        office=office,
                        date=date
                    )
                    break

                # Перевірка, чи слот не зайнятий та не в минулому
                is_booked = current_slot_time in booked_slots
                is_past = target_date == now_in_office_tz and current_slot_time < now_time_office

                if not is_booked and not is_past:
                    slot_dt_naive = datetime.combine(target_date, current_slot_time)
                    slot_dt_aware = slot_dt_naive.replace(tzinfo=office_tz)
                    available_slots.append({
                        "time": current_slot_time.strftime("%H:%M"),
                        "datetime": slot_dt_aware.strftime("%Y-%m-%d %H:%M:%S")
                    })

                # Перехід до наступного слоту
                current_dt_naive = datetime.combine(target_date, current_slot_time)

                if slot_duration.total_seconds() <= 0:
                    log_error(
                        "invalid_slot_duration",
                        f"Slot duration is zero or negative: {slot_duration}",
                        service=service
                    )
                    break

                next_dt_naive = current_dt_naive + slot_duration
                current_slot_time = next_dt_naive.time()

        return success_response(data={
            "slots": available_slots,
            "is_available": bool(available_slots)
        })

    except Exception as e:
        log_error("get_available_slots_error", str(e), service=service, office=office, date=date)
        frappe.log_error(frappe.get_traceback(), "Get Available Slots API Error")
        return error_response(
            _("An unexpected error occurred while fetching available slots."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=20, window_seconds=60)  # 20 запитів на хвилину
def create_appointment_ticket(
    service: str,
    office: str,
    appointment_datetime: str,
    visitor_phone: str = None
):
    """
    Створює талон попереднього запису на вказаний час.

    Args:
        service: ID сервісу
        office: ID офісу
        appointment_datetime: Дата та час запису (YYYY-MM-DD HH:MM:SS)
        visitor_phone: Номер телефону відвідувача (опціонально)

    Returns:
        Деталі створеного талону
    """
    log_api_call(
        "create_appointment_ticket",
        service=service,
        office=office,
        appointment_datetime=appointment_datetime
    )

    try:
        # --- Валідація вхідних даних ---
        if not service or not office or not appointment_datetime:
            return error_response(
                _("Service, Office, and Appointment Datetime are required."),
                error_code="MISSING_PARAMS",
                http_status_code=400
            )

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

        # Валідація та конвертація дати/часу
        try:
            appt_dt_naive = datetime.strptime(appointment_datetime, '%Y-%m-%d %H:%M:%S')
            office_doc = frappe.get_cached_doc("QMS Office", office)
            office_tz_str = office_doc.timezone or get_system_timezone()
            office_tz = ZoneInfo(office_tz_str)

            # Робимо aware в часовій зоні офісу
            appt_dt_aware = appt_dt_naive.replace(tzinfo=office_tz)

            # Переводимо в UTC для збереження в Frappe
            appt_dt_utc = appt_dt_aware.astimezone(ZoneInfo("UTC"))
            target_date_str = appt_dt_aware.strftime('%Y-%m-%d')
            target_time = appt_dt_aware.time()

        except (ValueError, TypeError):
            return error_response(
                _("Invalid appointment datetime format. Use 'YYYY-MM-DD HH:MM:SS'."),
                error_code="INVALID_DATETIME_FORMAT",
                http_status_code=400
            )
        except ZoneInfoNotFoundError:
            return error_response(
                _("Invalid office timezone configured: {0}").format(office_tz_str),
                error_code="INVALID_TIMEZONE",
                http_status_code=500
            )

        # --- Перевірка доступності слоту ---
        # Використовуємо транзакцію для уникнення race condition
        frappe.db.begin()

        slot_taken = frappe.db.exists("QMS Ticket", {
            "office": office,
            "service": service,
            "is_appointment": 1,
            "status": ["!=", "Cancelled"],
            "appointment_datetime": appt_dt_utc
        })

        if slot_taken:
            frappe.db.rollback()
            return error_response(
                _("The selected time slot ({0}) is no longer available. Please choose another time.").format(
                    target_time.strftime("%H:%M")
                ),
                error_code="SLOT_TAKEN",
                http_status_code=409
            )

        # Додаткова перевірка: чи відкритий офіс у цей час?
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule"
        )

        if schedule_name:
            working_intervals = get_working_intervals_for_date(
                schedule_name, appt_dt_aware.date(), office_tz_str
            )
            is_within_working_hours = any(
                start <= target_time < end for start, end in working_intervals
            )

            if not is_within_working_hours:
                frappe.db.rollback()
                return error_response(
                    _("The selected time slot ({0}) is outside of office working hours for {1}.").format(
                        target_time.strftime("%H:%M"), target_date_str
                    ),
                    error_code="OUTSIDE_WORKING_HOURS",
                    http_status_code=400
                )
        else:
            frappe.db.rollback()
            return error_response(
                _("Working schedule not configured for office '{0}'.").format(office_doc.office_name),
                error_code="NO_SCHEDULE",
                http_status_code=500
            )

        # --- Створення талону ---
        new_ticket = frappe.new_doc("QMS Ticket")
        new_ticket.office = office
        new_ticket.service = service
        new_ticket.status = "Waiting"
        new_ticket.is_appointment = 1
        new_ticket.appointment_datetime = appt_dt_utc
        new_ticket.issue_time = now()

        if visitor_phone:
            new_ticket.visitor_phone = visitor_phone

        new_ticket.insert(ignore_permissions=True)
        frappe.db.commit()

        # Логуємо створення запису
        log_ticket_event(
            "appointment_created",
            new_ticket.name,
            new_ticket.ticket_number,
            office=office,
            service=service,
            appointment_datetime=appointment_datetime
        )

        # --- Успішна відповідь ---
        return success_response(
            message=_("Appointment booked successfully for {0} at {1}.").format(
                get_date_str(appt_dt_aware.date()),
                target_time.strftime("%H:%M")
            ),
            data={
                "ticket_name": new_ticket.name,
                "ticket_number": new_ticket.ticket_number,
                "office": new_ticket.office,
                "service": new_ticket.service,
                "appointment_datetime_display": appt_dt_aware.strftime("%Y-%m-%d %H:%M"),
                "is_appointment": True
            }
        )

    except Exception as e:
        frappe.db.rollback()
        log_error(
            "create_appointment_error",
            str(e),
            service=service,
            office=office,
            appointment_datetime=appointment_datetime
        )
        frappe.log_error(frappe.get_traceback(), "Create Appointment Ticket API Error")
        return error_response(
            _("An unexpected error occurred while booking the appointment."),
            details=str(e),
            http_status_code=500
        )

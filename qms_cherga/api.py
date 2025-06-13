import frappe
from frappe import _
from frappe.utils import get_datetime, get_system_timezone, get_time, now_datetime, cint, today, now
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime

from qms_cherga.utils.response import error_response, info_response, success_response

# Додайте ці імпорти на початку файлу api.py, якщо їх немає
from frappe.utils import (
    get_datetime, get_system_timezone, get_time, now_datetime, cint, today, now, get_date_str
)
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import timedelta, datetime


def office_room(office_id: str):
    """
    Генерує ім'я кімнати для WebSocket на основі ID офісу.
    """
    return f'qms_office:{office_id}'


@frappe.whitelist()
def get_operator_dashboard_data():
    """
    Отримує всі початкові дані для панелі керування оператора.
    """
    user = frappe.session.user
    if user == "Guest":
        return error_response(_("Authentication required."), http_status_code=401)

    try:
        operator = frappe.get_doc(
            "QMS Operator", {"user": user, "is_active": 1})
    except frappe.DoesNotExistError:
        return error_response(_("Active QMS Operator record not found for user {0}.").format(user), error_code="OPERATOR_NOT_FOUND", http_status_code=404)

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
        service_points = frappe.get_all("QMS Service Point",
                                        filters={"office": office_id,
                                                 "is_active": 1},
                                        fields=["name", "point_name"],
                                        order_by="point_name"
                                        )

        # Поточний активний талон оператора (якщо є)
        active_ticket = frappe.get_all("QMS Ticket",
                                       filters={"operator": user, "status": [
                                           "in", ["Called", "Serving"]]},
                                       fields=["name", "ticket_number", "service", "status",
                                               "issue_time", "call_time", "start_service_time"],
                                       limit=1
                                       )
        active_ticket_doc = None
        if active_ticket:
            active_ticket_doc = active_ticket[0]
            active_ticket_doc['service_name'] = frappe.db.get_value(
                "QMS Service", active_ticket_doc.service, "service_name")

        # ОТРИМАННЯ СТАТИСТИКИ ТА ВІДКЛАДЕНИХ ТАЛОНІВ
        live_data = get_live_data(office=office_id, as_dict=True)

        return success_response(data={
            "operator_info": operator_info,
            "service_points": service_points,
            "active_ticket": active_ticket_doc,
            "queue_stats": live_data.get("stats"),  # <-- НОВІ ДАНІ
            # <-- НОВІ ДАНІ
            "postponed_tickets": live_data.get("postponed_tickets")
        })

    except Exception as e:
        frappe.log_error(frappe.get_traceback(),
                         "Get Operator Dashboard Data API Error")
        return error_response(_("An unexpected error occurred while fetching initial data."), details=str(e), http_status_code=500)


@frappe.whitelist()
def get_live_data(office: str, as_dict: bool = False):
    """
    Отримує "живі" дані для панелі оператора: статистику та відкладені талони.
    """
    if not frappe.db.exists("QMS Office", office):
        response = error_response(_("Office not found"), http_status_code=404)
        return response if not as_dict else {}

    try:
        # Статистика черги для офісу
        stats = {
            "waiting": frappe.db.count("QMS Ticket", {"office": office, "status": "Waiting", "creation": [">=", today()]}),
            "serving": frappe.db.count("QMS Ticket", {"office": office, "status": "Serving", "creation": [">=", today()]}),
            "finished_today": frappe.db.count("QMS Ticket", {"office": office, "status": ["in", ["Completed", "NoShow"]], "creation": [">=", today()]})
        }

        # Список відкладених талонів
        postponed_tickets = frappe.get_all("QMS Ticket",
                                           filters={"office": office,
                                                    "status": "Postponed"},
                                           fields=[
                                               "name", "ticket_number", "service"],
                                           order_by="modified desc"
                                           )
        for ticket in postponed_tickets:
            ticket['service_name'] = frappe.db.get_value(
                "QMS Service", ticket.service, "service_name")

        data_to_return = {
            "stats": stats,
            "postponed_tickets": postponed_tickets
        }

        return success_response(data=data_to_return) if not as_dict else data_to_return

    except Exception as e:
        frappe.log_error(frappe.get_traceback(),
                         f"Get Live Data API Error for Office {office}")
        response = error_response(
            _("An unexpected error occurred while fetching live data."), details=str(e), http_status_code=500)
        return response if not as_dict else {}


def _update_ticket_status(ticket_name, target_status, user, extra_data=None):
    """Внутрішня функція для зміни статусу талону."""
    try:
        ticket = frappe.get_doc("QMS Ticket", ticket_name)

        if ticket.status not in ["Called", "Serving", "Postponed"]:
            # Дозвіл на виклик з очікування
            if not (target_status == "Called" and ticket.status == "Waiting"):
                return error_response(_("Ticket {0} is not in a state that can be modified by the operator.").format(ticket.ticket_number), error_code="INVALID_TICKET_STATE", http_status_code=400)

        ticket.status = target_status
        if extra_data:
            ticket.update(extra_data)

        ticket.save(ignore_permissions=True)
        frappe.db.commit()
        return success_response(data=ticket.as_dict())

    except frappe.DoesNotExistError:
        return error_response(_("Ticket {0} not found.").format(ticket_name), http_status_code=404)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(),
                         f"Update Ticket Status API Error for {ticket_name}")
        return error_response(_("An unexpected error occurred while updating the ticket."), details=str(e), http_status_code=500)


@frappe.whitelist()
def start_service(ticket_name: str):
    """Переводить талон у статус 'Serving'."""
    return _update_ticket_status(ticket_name, "Serving", frappe.session.user, {"start_service_time": now_datetime()})


@frappe.whitelist()
def finish_service(ticket_name: str):
    """Переводить талон у статус 'Completed'."""
    return _update_ticket_status(ticket_name, "Completed", frappe.session.user, {"completion_time": now_datetime()})


@frappe.whitelist()
def mark_as_no_show(ticket_name: str):
    """Переводить талон у статус 'NoShow'."""
    return _update_ticket_status(ticket_name, "NoShow", frappe.session.user, {"completion_time": now_datetime()})


@frappe.whitelist()
def postpone_ticket(ticket_name: str):
    """Переводить талон у статус 'Postponed'."""
    return _update_ticket_status(ticket_name, "Postponed", frappe.session.user)


@frappe.whitelist()
def recall_ticket(ticket_name: str, service_point: str):
    """Повторно викликає відкладений талон."""
    if not service_point:
        return error_response(_("Service point is required to recall a ticket."), http_status_code=400)

    # Перевіримо чи точка обслуговування вільна
    # Цю логіку можна зробити складнішою (наприклад, перевіряти чи оператор вільний)
    # але поки що для простоти припускаємо, що оператор сам контролює цей процес.

    return _update_ticket_status(ticket_name, "Called", frappe.session.user, {
        "call_time": now_datetime(),
        "service_point": service_point,
        "operator": frappe.session.user
    })


@frappe.whitelist(allow_guest=True)
def ping_display_board(office_id: str, client_timestamp: str):
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
        frappe.log_error(
            f"Failed to publish pong for office {office_id}: {e}", "QMS Ping Error")
        return error_response(message=_("Ping received, but pong dispatch via WebSocket failed."), details=str(e), http_status_code=500)


@frappe.whitelist(allow_guest=True)
def get_office_info(office: str):
    if not office:
        return error_response(_("Office ID is required."), http_status_code=400)
    try:
        office_data = frappe.db.get_value("QMS Office", office, [
                                          "office_name", "timezone", "address", "contact_phone"], as_dict=True)
        if not office_data:
            return error_response(_("Office '{0}' not found.").format(office), http_status_code=404)
        return success_response(data=office_data)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(),
                         f"Get Office Info API Error for Office {office}")
        return error_response(_("An unexpected error occurred while fetching office information."), details=str(e), http_status_code=500)

    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(),
                         title=f"Get Office Info API Error for Office {office}")
        # 500 Internal Server Error
        return error_response(
            message=_(
                "An unexpected error occurred while fetching office information."),
            details=str(e),  # Деталі будуть доступні тільки в developer_mode
            http_status_code=500
        )


@frappe.whitelist(allow_guest=True)
def get_available_appointment_slots(service: str, office: str, date: str):
    """
    Отримує список доступних часових слотів для попереднього запису.
    (З доданими print для діагностики)
    """
    # Додаємо ліміт ітерацій для циклу while, щоб запобігти нескінченному виконанню
    # Обмеження на кількість слотів в одному робочому інтервалі
    MAX_SLOT_ITERATIONS_PER_INTERVAL = 1000
    try:
        # --- Валідація ---
        if not service or not office or not date:
            print("DEBUG: Validation failed: Missing parameters.")
            return error_response(_("Service, Office, and Date are required."), error_code="MISSING_PARAMS", http_status_code=400)

        if not frappe.db.exists("QMS Service", service):
            print(f"DEBUG: Validation failed: Service '{service}' not found.")
            return error_response(_("Service '{0}' not found.").format(service), error_code="INVALID_SERVICE", http_status_code=404)
        if not frappe.db.exists("QMS Office", office):
            print(f"DEBUG: Validation failed: Office '{office}' not found.")
            return error_response(_("Office '{0}' not found.").format(office), error_code="INVALID_OFFICE", http_status_code=404)

        # Валідація дати
        try:
            # Використовуємо datetime.fromisoformat для стандарту YYYY-MM-DD
            target_date = datetime.fromisoformat(date).date()
            print(f"DEBUG: Parsed target_date: {target_date}")
        except ValueError:
            print(f"DEBUG: Validation failed: Invalid date format '{date}'.")
            return error_response(_("Invalid date format provided. Use YYYY-MM-DD."), error_code="INVALID_DATE_FORMAT", http_status_code=400)

        # Перевірка часової зони та дати відносно поточної
        office_doc = frappe.get_cached_doc("QMS Office", office)
        office_tz_str = office_doc.timezone or get_system_timezone()
        print(f"DEBUG: Office timezone string: '{office_tz_str}'")
        try:
            office_tz = ZoneInfo(office_tz_str)
            now_in_office_tz = datetime.now(office_tz).date()
            print(
                f"DEBUG: Current date in office timezone ({office_tz_str}): {now_in_office_tz}")
            if target_date < now_in_office_tz:
                print("DEBUG: Target date is in the past.")
                return info_response(_("Cannot book appointments for past dates."), data={"slots": [], "is_available": False})
        except ZoneInfoNotFoundError:
            print(
                f"DEBUG: Validation failed: Invalid timezone '{office_tz_str}'.")
            return error_response(_("Invalid office timezone configured: {0}").format(office_tz_str), error_code="INVALID_TIMEZONE", http_status_code=500)

        print("DEBUG: Initial validation passed.")

        # --- Отримання налаштувань ---
        service_doc = frappe.get_cached_doc("QMS Service", service)
        avg_duration_mins = service_doc.avg_duration_mins or 15
        slot_duration = timedelta(minutes=avg_duration_mins)
        print(
            f"DEBUG: Service '{service}' found. Slot duration: {avg_duration_mins} mins.")

        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule")
        if not schedule_name:
            print(
                f"DEBUG: Configuration error: No schedule found for office '{office}'.")
            return error_response(_("Working schedule not configured for office '{0}'.").format(office_doc.office_name), error_code="NO_SCHEDULE", http_status_code=500)
        print(f"DEBUG: Using schedule '{schedule_name}'.")

        # --- Визначення робочих інтервалів на задану дату ---
        print(
            f"DEBUG: Calling get_working_intervals_for_date for date: {target_date}, schedule: {schedule_name}")
        working_intervals = get_working_intervals_for_date(
            schedule_name, target_date, office_tz_str)
        print(f"DEBUG: Received working_intervals: {working_intervals}")

        if not working_intervals:
            print("DEBUG: No working intervals found for the date. Returning closed.")
            return info_response(_("Office is closed on {0}.").format(get_date_str(target_date)), data={"slots": [], "is_available": False})

        # --- Отримання існуючих записів ---
        print("DEBUG: Fetching existing appointments...")
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
        booked_slots = {get_datetime(appt.appointment_datetime).astimezone(office_tz).time()  # Конвертуємо в зону офісу перед отриманням часу
                        for appt in existing_appointments if appt.appointment_datetime}
        print(
            f"DEBUG: Found {len(existing_appointments)} existing appointments. Booked time slots (in office TZ): {booked_slots}")

        # --- Генерація доступних слотів ---
        available_slots = []
        now_time_office = datetime.now(office_tz).time()
        print(f"DEBUG: Current time in office timezone: {now_time_office}")
        print(f"DEBUG: Starting slot generation loop...")

        interval_index = 0
        for start_work, end_work in working_intervals:
            interval_index += 1
            print(
                f"DEBUG: Processing interval #{interval_index}: Start={start_work}, End={end_work}")
            current_slot_time = start_work
            iteration_count = 0  # Лічильник для циклу while

            while current_slot_time < end_work:
                iteration_count += 1
                # Перевірка на перевищення ліміту ітерацій
                if iteration_count > MAX_SLOT_ITERATIONS_PER_INTERVAL:
                    print(
                        f"DEBUG: ERROR - Exceeded MAX_SLOT_ITERATIONS_PER_INTERVAL ({MAX_SLOT_ITERATIONS_PER_INTERVAL}) for interval {interval_index}. Breaking loop.")
                    # Можна повернути помилку або просто зупинити генерацію для цього інтервалу
                    # return error_response("Slot generation limit exceeded.", http_status_code=500)
                    break  # Виходимо з циклу while для цього інтервалу

                # Виводимо кожну N-у ітерацію або якщо є потенційна проблема
                if iteration_count % 50 == 0 or iteration_count > MAX_SLOT_ITERATIONS_PER_INTERVAL - 5:
                    print(
                        f"DEBUG: Interval #{interval_index}, Iteration #{iteration_count}: current_slot_time={current_slot_time}, end_work={end_work}")

                # Перевірка, чи слот не зайнятий
                is_booked = current_slot_time in booked_slots
                # Перевірка, чи слот не в минулому
                is_past = target_date == now_in_office_tz and current_slot_time < now_time_office

                if not is_booked and not is_past:
                    # Додаємо слот
                    slot_dt_naive = datetime.combine(
                        target_date, current_slot_time)
                    slot_dt_aware = slot_dt_naive.replace(tzinfo=office_tz)
                    available_slots.append({
                        "time": current_slot_time.strftime("%H:%M"),
                        "datetime": slot_dt_aware.strftime("%Y-%m-%d %H:%M:%S")
                    })
                    # print(f"DEBUG: Added slot: {current_slot_time.strftime('%H:%M')}")
                # else:
                    # print(f"DEBUG: Skipped slot: {current_slot_time.strftime('%H:%M')} (Booked: {is_booked}, Past: {is_past})")

                # --- Перехід до наступного слоту ---
                # Важливо: Використовуємо datetime для додавання timedelta
                current_dt_naive = datetime.combine(
                    target_date, current_slot_time)
                # Перевірка на нульову тривалість, щоб уникнути нескінченного циклу
                if slot_duration.total_seconds() <= 0:
                    print(
                        f"DEBUG: ERROR - Slot duration is zero or negative ({slot_duration}). Breaking loop.")
                    break  # Виходимо з циклу while

                next_dt_naive = current_dt_naive + slot_duration

                # Перевірка, чи не виходимо за межі робочого дня після додавання тривалості
                # Якщо кінець наступного слоту виходить за межі end_work, то цей слот вже не підходить
                # (Це може бути оптимізовано, щоб не генерувати останній, якщо він не поміщається)
                # if next_dt_naive.time() > end_work:
                # print(f"DEBUG: Next slot end time {next_dt_naive.time()} exceeds interval end {end_work}. Stopping interval.")
                # break # Зупиняємо для цього інтервалу

                current_slot_time = next_dt_naive.time()

            print(
                f"DEBUG: Finished processing interval #{interval_index} after {iteration_count} iterations.")

        print(
            f"DEBUG: Slot generation finished. Found {len(available_slots)} available slots.")
        print(f"DEBUG: Returning success response.")
        return success_response(data={"slots": available_slots, "is_available": bool(available_slots)})

    except Exception as e:
        print(
            f"DEBUG: Exception caught in get_available_appointment_slots: {type(e).__name__} - {e}")
        frappe.log_error(frappe.get_traceback(),
                         "Get Available Slots API Error (with debug)")
        return error_response(_("An unexpected error occurred while fetching available slots."), details=str(e), http_status_code=500)


def get_working_intervals_for_date(schedule_name, target_date, timezone_str):
    """
    Допоміжна функція для отримання робочих інтервалів.
    (З доданими print для діагностики)
    """
    print(f"--- DEBUG (helper): Entering get_working_intervals_for_date ---")
    target_date_str = get_date_str(target_date)
    day_name = target_date.strftime('%A')
    print(
        f"DEBUG (helper): schedule='{schedule_name}', target_date='{target_date_str}', day_name='{day_name}', timezone='{timezone_str}'")
    intervals = []

    try:
        # 1. Перевірка винятків
        print("DEBUG (helper): Checking for exceptions...")
        exceptions = frappe.get_all(
            "QMS Schedule Exception Child",
            filters={"parent": schedule_name, "parenttype": "QMS Schedule",
                     "exception_date": target_date_str},
            fields=["is_workday", "start_time", "end_time"],
            order_by="start_time"
        )
        print(
            f"DEBUG (helper): Found {len(exceptions)} exceptions for the date.")

        has_exception = bool(exceptions)
        is_explicitly_non_workday = any(
            not exc.is_workday for exc in exceptions)

        if is_explicitly_non_workday:
            print(
                "DEBUG (helper): Exception marks this as a non-workday. Returning empty intervals.")
            return []

        if has_exception:
            print("DEBUG (helper): Processing exceptions...")
            for exc in exceptions:
                if exc.is_workday and exc.start_time and exc.end_time:
                    try:
                        start = get_time(exc.start_time)
                        end = get_time(exc.end_time)
                        if start < end:
                            intervals.append((start, end))
                            print(
                                f"DEBUG (helper): Added interval from exception: {start} - {end}")
                        else:
                            print(
                                f"DEBUG (helper): WARNING - Invalid exception interval skipped (start >= end): {exc.start_time} - {exc.end_time}")
                    except (TypeError, ValueError):
                        print(
                            f"DEBUG (helper): ERROR - Could not parse time from exception: Start='{exc.start_time}', End='{exc.end_time}'")

            print(
                f"DEBUG (helper): Returning intervals based SOLELY on exceptions: {intervals}")
            return intervals

        # 2. Перевірка правил (якщо не було винятків)
        print(
            f"DEBUG (helper): No relevant exceptions found. Checking rules for day: {day_name}...")
        rules = frappe.get_all(
            "QMS Schedule Rule Child",
            filters={"parent": schedule_name,
                     "parenttype": "QMS Schedule", "day_of_week": day_name},
            fields=["start_time", "end_time"],
            order_by="start_time"
        )
        print(f"DEBUG (helper): Found {len(rules)} rules for the day.")

        for rule in rules:
            try:
                start = get_time(rule.start_time)
                end = get_time(rule.end_time)
                if start < end:
                    intervals.append((start, end))
                    print(
                        f"DEBUG (helper): Added interval from rule: {start} - {end}")
                else:
                    print(
                        f"DEBUG (helper): WARNING - Invalid rule interval skipped (start >= end): {rule.start_time} - {rule.end_time}")
            except (TypeError, ValueError):
                print(
                    f"DEBUG (helper): ERROR - Could not parse time from rule: Start='{rule.start_time}', End='{rule.end_time}'")

        print(
            f"DEBUG (helper): Returning intervals based on rules: {intervals}")
        return intervals

    except Exception as e:
        print(f"DEBUG (helper): Exception caught: {type(e).__name__} - {e}")
        frappe.log_error(
            f"Error getting working intervals for {schedule_name} on {target_date_str}: {e}", "Schedule Interval Error (with debug)")
        return []


@frappe.whitelist(allow_guest=True)
def create_appointment_ticket(service: str, office: str, appointment_datetime: str, visitor_phone: str = None):
    """
    Створює талон попереднього запису на вказаний час.
    """
    try:
        # --- Валідація вхідних даних ---
        if not service or not office or not appointment_datetime:
            return error_response(_("Service, Office, and Appointment Datetime are required."), error_code="MISSING_PARAMS", http_status_code=400)

        if not frappe.db.exists("QMS Service", service):
            return error_response(_("Service '{0}' not found.").format(service), error_code="INVALID_SERVICE", http_status_code=404)
        if not frappe.db.exists("QMS Office", office):
            return error_response(_("Office '{0}' not found.").format(office), error_code="INVALID_OFFICE", http_status_code=404)

        # Валідація та конвертація дати/часу
        try:
            # Очікуємо datetime рядок у форматі "YYYY-MM-DD HH:MM:SS" з часовою зоною офісу
            appt_dt_naive = datetime.strptime(
                appointment_datetime, '%Y-%m-%d %H:%M:%S')
            office_doc = frappe.get_cached_doc("QMS Office", office)
            office_tz_str = office_doc.timezone or get_system_timezone()
            office_tz = ZoneInfo(office_tz_str)
            appt_dt_aware = office_tz.localize(appt_dt_naive)  # Робимо aware
            # Переводимо в UTC для збереження в Frappe (стандартна практика)
            appt_dt_utc = appt_dt_aware.astimezone(ZoneInfo("UTC"))
            target_date_str = appt_dt_aware.strftime('%Y-%m-%d')
            target_time = appt_dt_aware.time()

        except (ValueError, TypeError):
            return error_response(_("Invalid appointment datetime format. Use 'YYYY-MM-DD HH:MM:SS'."), error_code="INVALID_DATETIME_FORMAT", http_status_code=400)
        except ZoneInfoNotFoundError:
            return error_response(_("Invalid office timezone configured: {0}").format(office_tz_str), error_code="INVALID_TIMEZONE", http_status_code=500)

        # --- Перевірка доступності слоту (Дуже важливо!) ---
        # Проста перевірка, чи вже існує запис на цей час (може бути недостатньою при високому навантаженні)
        # В ідеалі потрібен механізм блокування слоту.
        slot_taken = frappe.db.exists("QMS Ticket", {
            "office": office,
            "service": service,
            "is_appointment": 1,
            "status": ["!=", "Cancelled"],
            "appointment_datetime": appt_dt_utc  # Порівнюємо з UTC
        })
        if slot_taken:
            # 409 Conflict
            return error_response(_("The selected time slot ({0}) is no longer available. Please choose another time.").format(target_time.strftime("%H:%M")), error_code="SLOT_TAKEN", http_status_code=409)

        # Додаткова перевірка: чи відкритий офіс у цей час?
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule")
        if schedule_name:
            working_intervals = get_working_intervals_for_date(
                schedule_name, appt_dt_aware.date(), office_tz_str)
            is_within_working_hours = any(
                start <= target_time < end for start, end in working_intervals)
            if not is_within_working_hours:
                return error_response(_("The selected time slot ({0}) is outside of office working hours for {1}.").format(target_time.strftime("%H:%M"), target_date_str), error_code="OUTSIDE_WORKING_HOURS", http_status_code=400)
        else:
            # Якщо немає графіка, але ми дійшли сюди, це помилка конфігурації
            return error_response(_("Working schedule not configured for office '{0}'.").format(office_doc.office_name), error_code="NO_SCHEDULE", http_status_code=500)

        # --- Створення талону ---
        new_ticket = frappe.new_doc("QMS Ticket")
        new_ticket.office = office
        new_ticket.service = service
        new_ticket.status = "Waiting"  # Або "Scheduled", якщо додасте такий статус
        new_ticket.is_appointment = 1
        new_ticket.appointment_datetime = appt_dt_utc  # Зберігаємо в UTC
        new_ticket.issue_time = now()  # Час створення запису
        if visitor_phone:
            # TODO: Додати валідацію формату телефону
            new_ticket.visitor_phone = visitor_phone

        # autoname згенерує ім'я та номер
        new_ticket.insert(ignore_permissions=True)
        frappe.db.commit()

        # --- Успішна відповідь ---
        return success_response(
            message=_("Appointment booked successfully for {0} at {1}.").format(
                get_date_str(appt_dt_aware.date()
                             ), target_time.strftime("%H:%M")
            ),
            data={
                "ticket_name": new_ticket.name,
                "ticket_number": new_ticket.ticket_number,
                "office": new_ticket.office,
                "service": new_ticket.service,
                # Для відображення користувачу
                "appointment_datetime_display": appt_dt_aware.strftime("%Y-%m-%d %H:%M"),
                "is_appointment": True
            }
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(),
                         "Create Appointment Ticket API Error")
        return error_response(_("An unexpected error occurred while booking the appointment."), details=str(e), http_status_code=500)

# --- Функція перевірки робочого часу ---
# Ця функція сама не повертає стандартизовану відповідь,
# її результат обробляється викликаючими функціями.


def is_office_open(schedule_name: str, timezone: str):
    """
    Перевіряє, чи відкритий офіс зараз згідно з графіком, враховуючи винятки,
    часову зону офісу та можливість кількох робочих інтервалів на день.

    :param schedule_name: Назва (ID) документу QMS Schedule.
    :param timezone: Рядок з назвою часової зони у форматі IANA (напр., 'Europe/Kyiv').
    :return: True, якщо офіс відкритий, False - якщо закритий або сталася помилка.
    """
    if not schedule_name:
        frappe.log_error(
            "Schedule name not provided for is_office_open check.", "Schedule Check Error")
        return False

    office_tz = None
    try:
        if timezone:
            office_tz = ZoneInfo(timezone)
        else:
            system_tz_str = get_system_timezone()
            office_tz = ZoneInfo(system_tz_str)
            frappe.log_warning(
                f"Office timezone not provided for schedule '{schedule_name}'. Falling back to system timezone '{system_tz_str}'.", "Schedule Check Info")
    except ZoneInfoNotFoundError:
        system_tz_str = get_system_timezone()
        office_tz = ZoneInfo(system_tz_str)
        frappe.log_error(
            message=f"Invalid timezone '{timezone}' provided for schedule '{schedule_name}'. Falling back to system timezone '{system_tz_str}'.", title="Schedule Check Error")
    except Exception as e:
        system_tz_str = get_system_timezone()
        office_tz = ZoneInfo(system_tz_str)
        frappe.log_error(
            message=f"Error processing timezone '{timezone}' for schedule '{schedule_name}'. Falling back to system timezone '{system_tz_str}'. Error: {e}", title="Schedule Check Error")

    try:
        # now_local_dt = datetime.now(office_tz) # Використовуємо frappe.utils.now_datetime()
        now_local_dt = now_datetime().astimezone(office_tz)

        current_date_str = now_local_dt.strftime('%Y-%m-%d')
        current_day_name = now_local_dt.strftime('%A')
        current_time_obj = get_time(now_local_dt.strftime('%H:%M:%S'))

        # Перевірка Винятків
        exceptions = frappe.get_all(
            "QMS Schedule Exception Child",
            filters={"parenttype": "QMS Schedule",
                     "parent": schedule_name, "exception_date": current_date_str},
            fields=["is_workday", "start_time", "end_time"],
        )

        if exceptions:
            is_explicitly_non_workday = any(
                not exc.is_workday for exc in exceptions)
            if is_explicitly_non_workday:
                return False

            found_working_interval_in_exception = False
            for exception in exceptions:
                if exception.is_workday and exception.start_time and exception.end_time:
                    start_time_exc = get_time(exception.start_time)
                    end_time_exc = get_time(exception.end_time)
                    if start_time_exc <= current_time_obj < end_time_exc:
                        return True  # Відкрито за винятком

            # Якщо були робочі винятки, але час не підійшов - закрито
            if any(exc.is_workday for exc in exceptions):
                return False

        # Перевірка Правил
        all_rules = frappe.get_all(
            "QMS Schedule Rule Child",
            filters={"parent": schedule_name, "parenttype": "QMS Schedule",
                     "day_of_week": current_day_name},
            fields=["start_time", "end_time"]
        )

        if not all_rules:
            return False  # Немає правил на цей день

        for rule in all_rules:
            start_time_rule = get_time(rule.start_time)
            end_time_rule = get_time(rule.end_time)
            if start_time_rule <= current_time_obj < end_time_rule:
                return True  # Відкрито за правилом

        return False  # Жоден інтервал не підійшов

    except Exception as e:
        now_local_dt_str = now_local_dt.isoformat() if 'now_local_dt' in locals() else 'N/A'
        frappe.log_error(
            f"Error during schedule check for schedule '{schedule_name}' with timezone '{timezone}'. Current local time check: {now_local_dt_str}. Error: {e}\n{frappe.get_traceback()}",
            "Schedule Check Runtime Error"
        )
        return False


# --- API Ендпоінти ---

@frappe.whitelist(allow_guest=True)
def create_live_queue_ticket(service: str, office: str, visitor_phone: str = None):
    """
    API Endpoint для створення нового талону QMS Ticket з Кіоску (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        # --- Базова валідація вхідних даних ---
        if not service or not office:
            return error_response(_("Service or Office not specified."), error_code="MISSING_PARAMS", http_status_code=400)

        # Перевірка існування записів
        if not frappe.db.exists("QMS Service", service):
            return error_response(_("Service '{0}' not found.").format(service), error_code="INVALID_SERVICE", http_status_code=404)
        if not frappe.db.exists("QMS Office", office):
            return error_response(_("Office '{0}' not found.").format(office), error_code="INVALID_OFFICE", http_status_code=404)

        # --- Додаткові перевірки ---
        service_doc = frappe.get_cached_doc("QMS Service", service)
        if not service_doc.enabled:
            return error_response(_("Service '{0}' is currently inactive.").format(service_doc.service_name), error_code="SERVICE_INACTIVE", http_status_code=400)
        if not service_doc.live_queue_enabled:
            return error_response(_("Service '{0}' is not available for live queue.").format(service_doc.service_name), error_code="SERVICE_NO_LIVE_QUEUE", http_status_code=400)

        is_service_in_office = frappe.db.exists("QMS Office Service Assignment", {
                                                "parent": office, "service": service, "is_active_in_office": 1})
        if not is_service_in_office:
            office_name = frappe.db.get_value(
                "QMS Office", office, "office_name")
            return error_response(_("Service '{0}' is not available in office '{1}'.").format(service_doc.service_name, office_name), error_code="SERVICE_NOT_IN_OFFICE", http_status_code=400)

        office_doc = frappe.get_cached_doc("QMS Office", office)
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule")

        if schedule_name:
            if not is_office_open(schedule_name, office_doc.timezone):
                # Використовуємо info_response, бо це не помилка системи, а стан офісу
                # Повертаємо 200 OK, але з інформаційним статусом
                return info_response(_("Office '{0}' is currently closed.").format(office_doc.office_name), data={"office_status": "closed"})
        else:
            # Якщо немає графіка, це помилка конфігурації
            # 500 бо це проблема налаштування сервера
            return error_response(_("Working schedule not configured for office '{0}'.").format(office_doc.office_name), error_code="NO_SCHEDULE", http_status_code=500)

        # --- Валідація номеру телефону ---
        if visitor_phone:
            # Простіша перевірка
            if not visitor_phone.replace("+", "").replace("-", "").replace(" ", "").isdigit():
                frappe.log_warning(
                    f"Invalid phone format '{visitor_phone}' provided. Ignoring.", "Ticket Creation Warning")
                visitor_phone = None

        # --- Створення документу QMS Ticket ---
        new_ticket = frappe.new_doc("QMS Ticket")
        new_ticket.office = office
        new_ticket.service = service
        new_ticket.status = "Waiting"
        # Використовуємо now() для консистентності
        new_ticket.issue_time = frappe.utils.now()
        if visitor_phone:
            new_ticket.visitor_phone = visitor_phone

        # Метод autoname має встановити name та ticket_number

        new_ticket.insert(ignore_permissions=True)
        frappe.db.commit()

        # --- Успішна відповідь ---
        return success_response(
            message=_("Ticket created successfully."),
            data={
                "ticket_name": new_ticket.name,  # Унікальний ID документа
                "ticket_number": new_ticket.ticket_number,  # Номер для відображення
                "office": new_ticket.office,
                "service": new_ticket.service
            }
        )

    except frappe.exceptions.ValidationError as e:
        # Обробка помилок валідації Frappe
        frappe.db.rollback()
        # Повідомлення з ValidationError вже може бути перекладене
        return error_response(str(e), error_code="VALIDATION_ERROR", http_status_code=400)
    except Exception as e:
        # Обробка інших неочікуваних помилок
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(),
                         "QMS Ticket Creation API Error")
        # Повертаємо загальну помилку сервера
        return error_response(
            message=_("Failed to create ticket due to an internal error."),
            details=str(e),  # Деталі тільки в режимі розробника
            http_status_code=500
        )


@frappe.whitelist()
def call_next_visitor(service_point_name: str):
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            return error_response(_("Authentication required."), http_status_code=401)

        operator_doc = frappe.get_doc(
            "QMS Operator", {"user": current_user, "is_active": 1})
        operator_skills = [
            skill.service for skill in operator_doc.get("operator_skills", [])]
        if not operator_skills:
            return error_response(_("Operator {0} has no skills assigned.").format(current_user), error_code="NO_SKILLS", http_status_code=400)

        service_point_data = frappe.db.get_value("QMS Service Point", service_point_name, [
                                                 "office", "point_name"], as_dict=True)
        if not service_point_data:
            return error_response(_("Service point with ID '{0}' not found.").format(service_point_name), http_status_code=404)

        office_id = service_point_data.office
        actual_service_point_display_name = service_point_data.point_name

        if not office_id:
            return error_response(_("Could not determine Office for service point '{0}'.").format(actual_service_point_display_name), http_status_code=500)

        waiting_tickets = frappe.get_list(
            "QMS Ticket",
            filters={"office": office_id, "status": "Waiting",
                     "service": ["in", operator_skills]},
            fields=["name"],
            order_by="priority desc, creation asc",
            limit_page_length=1
        )

        if not waiting_tickets:
            return info_response(_("No tickets found in queue for calling."), data={"ticket_info": None})

        next_ticket_name = waiting_tickets[0].name
        ticket_doc = frappe.get_doc("QMS Ticket", next_ticket_name)

        # Просто оновлюємо поля і зберігаємо. Хук on_update в QMSTicket зробить решту.
        ticket_doc.status = "Called"
        ticket_doc.call_time = now_datetime()
        ticket_doc.operator = current_user
        ticket_doc.service_point = service_point_name

        # Можливо, зберегти service_name та service_point_name напряму в документі талону
        # для легшого доступу в get_realtime_data, якщо вони не оновлюються часто.
        # ticket_doc.service_name = frappe.db.get_value("QMS Service", ticket_doc.service, "service_name")
        # ticket_doc.service_point_name = actual_service_point_display_name

        ticket_doc.save(ignore_permissions=True)  # Це викличе on_update
        frappe.db.commit()

        return success_response(
            message=_("Ticket {0} called to point {1}.").format(
                ticket_doc.ticket_number, actual_service_point_display_name),
            # Повертаємо дані, які також пішли по WS
            data={"ticket_info": ticket_doc}
        )
    # ... (обробка винятків як раніше) ...
    except frappe.DoesNotExistError as e:
        frappe.db.rollback()
        doc_type_name = str(e).split(
            "'")[1] if "'" in str(e) else _("Document")
        return error_response(_("{0} not found.").format(doc_type_name), details=frappe.get_traceback(), http_status_code=404)
    except frappe.PermissionError as e:
        frappe.db.rollback()
        return error_response(_("Permission denied."), details=frappe.get_traceback(), http_status_code=403)
    except Exception as e:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Call Next Visitor API Error")
        return error_response(
            message=_(
                "An unexpected error occurred while calling the next visitor."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist(allow_guest=True)
def get_display_data(office: str, limit_called: int = 3, limit_waiting: int = 20):
    """
    Отримує дані для публічного дисплея черги (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
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
            "QMS Organization", office_doc.organization, "default_schedule")

        office_is_open = False
        # Змінено: ініціалізація перекладним рядком
        closed_message = _("Working schedule not configured.")

        if schedule_name:
            office_is_open = is_office_open(schedule_name, office_doc.timezone)
            if not office_is_open:
                closed_message = _("Office '{0}' is currently closed.").format(
                    office_doc.office_name)
        else:
            closed_message = _("Working schedule not configured for office '{0}'.").format(
                office_doc.office_name)
            office_is_open = False

        # Отримуємо інформаційне повідомлення
        info_message_text = office_doc.display_message_text or None

        if not office_is_open:
            # Використовуємо info_response для стану "закрито"
            return info_response(
                message=closed_message,
                data={
                    "office_status": "closed",
                    "last_called": [],
                    "waiting": [],
                    "info_message": info_message_text  # Передаємо повідомлення і тут
                }
            )

        # --- Отримуємо останні викликані/обслужені ---
        last_called = []
        potential_called = frappe.get_all(
            "QMS Ticket",
            filters={
                "office": office,
                # Показуємо тільки ті, що зараз викликані
                "status": "Called",
                # Обмежуємо сьогоднішнім днем для продуктивності
                # Фільтр за часом виклику
                "call_time": [">=", today() + " 00:00:00"] if frappe.db.db_type == 'mariadb' else [">=", datetime.combine(get_datetime(today()).date(), datetime.min.time())]
            },
            fields=["name", "ticket_number", "service_point", "call_time"],
            # Сортуємо за часом виклику, найновіші зверху
            order_by="call_time desc",
            limit_page_length=limit_called  # Беремо тільки потрібну кількість
        )

        # Отримуємо назви точок одним запитом
        point_ids = list(
            set(t.service_point for t in potential_called if t.service_point))
        point_names_map = {}
        if point_ids:
            points = frappe.get_all("QMS Service Point", filters={
                                    "name": ["in", point_ids]}, fields=["name", "point_name"])
            point_names_map = {p.name: p.point_name for p in points}

        for ticket in potential_called:
            short_ticket_number = ticket.ticket_number.split(
                '-')[-1] if ticket.ticket_number and '-' in ticket.ticket_number else ticket.ticket_number
            call_time_dt = get_datetime(
                ticket.call_time) if ticket.call_time else None
            last_called.append({
                "ticket": short_ticket_number or ticket.name,
                "window": point_names_map.get(ticket.service_point, "N/A"),
                "time": call_time_dt.strftime("%H:%M") if call_time_dt else "--:--"
            })

        # --- Отримуємо наступних у черзі ---
        waiting_tickets = []
        # TODO: Додати логіку обробки талонів по запису (is_appointment, appointment_datetime), якщо реалізовано
        waiting_raw = frappe.get_all(
            "QMS Ticket",
            filters={"office": office, "status": "Waiting"},
            fields=["name", "ticket_number", "service"],
            order_by="priority desc, creation asc",
            limit_page_length=limit_waiting
        )

        # Отримуємо назви послуг одним запитом
        service_ids_waiting = list(
            set(row.service for row in waiting_raw if row.service))
        service_names_map_waiting = {}
        if service_ids_waiting:
            services = frappe.get_all("QMS Service", filters={
                                      "name": ["in", service_ids_waiting]}, fields=["name", "service_name"])
            service_names_map_waiting = {
                s.name: s.service_name for s in services}

        for row in waiting_raw:
            short_ticket_number = row.ticket_number.split(
                '-')[-1] if row.ticket_number and '-' in row.ticket_number else row.ticket_number
            waiting_tickets.append({
                "ticket": short_ticket_number or row.name,
                # Переклад тут
                "service": service_names_map_waiting.get(row.service, _("Service not specified")),
                "service_id": row.service  # Додаємо ID для можливої стилізації на фронтенді
            })

        # Успішна відповідь для відкритого офісу
        return success_response(data={
            "office_status": "open",
            "last_called": last_called,
            "waiting": waiting_tickets,
            "info_message": info_message_text  # Передаємо повідомлення
        })

    except Exception as e:
        # Обробка неочікуваних помилок
        frappe.log_error(frappe.get_traceback(),
                         f"Get Display Data API Error for Office {office}")
        return error_response(
            message=_(
                "An unexpected error occurred while fetching display data."),
            details=str(e),
            http_status_code=500
        )


@frappe.whitelist(allow_guest=True)
def get_kiosk_services(office: str):
    """
    Отримує список послуг для кіоску (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        if not office:
            return error_response(_("Office ID is required."), http_status_code=400)
        if not frappe.db.exists("QMS Office", office):
            return error_response(_("Office '{0}' not found.").format(office), http_status_code=404)

        # Перевірка графіка роботи
        office_doc = frappe.get_cached_doc("QMS Office", office)
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule")

        office_is_open = False
        # Змінено: ініціалізація перекладним рядком
        closed_message = _("Working schedule not configured.")

        if schedule_name:
            office_is_open = is_office_open(schedule_name, office_doc.timezone)
            if not office_is_open:
                closed_message = _("Office '{0}' is currently closed.").format(
                    office_doc.office_name)
        else:
            closed_message = _("Working schedule not configured for office '{0}'.").format(
                office_doc.office_name)
            office_is_open = False

        if not office_is_open:
            # Використовуємо info_response для стану "закрито"
            return info_response(
                message=closed_message,
                data={"status": "closed", "categories": [],
                      "services_no_category": []}
            )

        # Отримуємо впорядковані призначення послуг для офісу
        assignments = frappe.get_all(
            "QMS Office Service Assignment",
            filters={"parent": office, "is_active_in_office": 1},
            fields=["service"],
            order_by="idx asc"  # Важливо для порядку на кіоску
        )
        if not assignments:
            # Успіх, але дані порожні
            return success_response(data={"categories": [], "services_no_category": []})

        ordered_service_ids = [a.service for a in assignments]

        # Отримуємо деталі тільки активних та доступних для кіоску послуг
        services_details = frappe.get_all(
            "QMS Service",
            filters={
                "name": ["in", ordered_service_ids],
                "enabled": 1,  # Послуга має бути активна
                "live_queue_enabled": 1  # Послуга має бути доступна для живої черги
            },
            # Додаємо іконку
            fields=["name", "service_name", "category", "icon"]
        )
        # Створюємо словник для швидкого доступу
        active_services_map = {s.name: s for s in services_details}

        # Отримуємо та сортуємо категорії
        category_ids = list(
            set(s.category for s in services_details if s.category))
        categories_map = {}
        sorted_cat_ids = []
        if category_ids:
            categories_data = frappe.get_all(
                "QMS Service Category",
                filters={"name": ["in", category_ids]},
                fields=["name", "category_name", "display_order"],
                order_by="display_order asc, category_name asc"  # Сортування категорій
            )
            sorted_cat_ids = [cat.name for cat in categories_data]
            categories_map = {cat.name: {
                "label": cat.category_name, "services": []} for cat in categories_data}

        # Розподіляємо послуги за категоріями згідно з порядком assignments
        services_no_category_ordered = []
        # Створюємо тимчасовий словник для накопичення послуг у категоріях
        temp_categories_services = {cat_id: [] for cat_id in sorted_cat_ids}

        for service_id in ordered_service_ids:
            # Перевіряємо, чи послуга активна і доступна для кіоску
            if service_id in active_services_map:
                service_info = active_services_map[service_id]
                service_data = {
                    "id": service_info.name,
                    "label": service_info.service_name,
                    "icon": service_info.icon or ""  # Повертаємо іконку або порожній рядок
                }

                if service_info.category and service_info.category in temp_categories_services:
                    temp_categories_services[service_info.category].append(
                        service_data)
                else:
                    services_no_category_ordered.append(service_data)

        # Формуємо фінальний список категорій з послугами (тільки не порожні)
        final_categories_list = []
        for cat_id in sorted_cat_ids:
            # Додаємо категорію, тільки якщо в ній є послуги
            if temp_categories_services[cat_id]:
                final_categories_list.append({
                    "label": categories_map[cat_id]["label"],
                    "services": temp_categories_services[cat_id]
                })

        # Успішна відповідь з даними
        return success_response(data={
            "categories": final_categories_list,
            "services_no_category": services_no_category_ordered
        })

    except Exception as e:
        # Обробка неочікуваних помилок
        frappe.log_error(frappe.get_traceback(),
                         f"Get Kiosk Services API Error for Office {office}")
        return error_response(
            message=_(
                "An unexpected error occurred while fetching kiosk services."),
            details=str(e),
            http_status_code=500
        )

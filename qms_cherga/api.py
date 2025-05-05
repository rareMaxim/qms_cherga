# qms_cherga/api.py

import frappe
from frappe import _  # Імпорт для перекладів
from frappe.utils import get_datetime, get_system_timezone, get_time, now_datetime, cint, today, now
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime

from qms_cherga.utils.response import error_response, info_response, success_response


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
            return error_response("Service or Office not specified.", error_code="MISSING_PARAMS", http_status_code=400)

        # Перевірка існування записів
        if not frappe.db.exists("QMS Service", service):
            return error_response(f"Service '{service}' not found.", error_code="INVALID_SERVICE", http_status_code=404)
        if not frappe.db.exists("QMS Office", office):
            return error_response(f"Office '{office}' not found.", error_code="INVALID_OFFICE", http_status_code=404)

        # --- Додаткові перевірки ---
        service_doc = frappe.get_cached_doc("QMS Service", service)
        if not service_doc.enabled:
            return error_response(f"Service '{service_doc.service_name}' is currently inactive.", error_code="SERVICE_INACTIVE", http_status_code=400)
        if not service_doc.live_queue_enabled:
            return error_response(f"Service '{service_doc.service_name}' is not available for live queue.", error_code="SERVICE_NO_LIVE_QUEUE", http_status_code=400)

        is_service_in_office = frappe.db.exists("QMS Office Service Assignment", {
                                                "parent": office, "service": service, "is_active_in_office": 1})
        if not is_service_in_office:
            office_name = frappe.db.get_value(
                "QMS Office", office, "office_name")
            return error_response(f"Service '{service_doc.service_name}' is not available in office '{office_name}'.", error_code="SERVICE_NOT_IN_OFFICE", http_status_code=400)

        office_doc = frappe.get_cached_doc("QMS Office", office)
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule")

        if schedule_name:
            if not is_office_open(schedule_name, office_doc.timezone):
                # Використовуємо info_response, бо це не помилка системи, а стан офісу
                # Повертаємо 200 OK, але з інформаційним статусом
                return info_response(f"Office '{office_doc.office_name}' is currently closed.", data={"office_status": "closed"})
        else:
            # Якщо немає графіка, це помилка конфігурації
            # 500 бо це проблема налаштування сервера
            return error_response(f"Working schedule not configured for office '{office_doc.office_name}'.", error_code="NO_SCHEDULE", http_status_code=500)

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
            message="Ticket created successfully.",
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
        return error_response(str(e), error_code="VALIDATION_ERROR", http_status_code=400)
    except Exception as e:
        # Обробка інших неочікуваних помилок
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(),
                         "QMS Ticket Creation API Error")
        # Повертаємо загальну помилку сервера
        return error_response(
            message="Failed to create ticket due to an internal error.",
            details=str(e),  # Деталі тільки в режимі розробника
            http_status_code=500
        )


@frappe.whitelist()
def call_next_visitor(service_point_name: str):  # service_point_name - це ID
    """
    Викликає наступного відвідувача (Оновлена версія).
    Повертає стандартизовану відповідь.
    """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            # 401 Unauthorized
            return error_response("Authentication required.", http_status_code=401)

        # --- Отримуємо дані Оператора та Навички ---
        try:
            operator_doc = frappe.get_doc(
                "QMS Operator", {"user": current_user, "is_active": 1})
        except frappe.DoesNotExistError:
            # 404 Not Found
            return error_response(f"Active QMS Operator record not found for user {current_user}.", http_status_code=404)

        operator_skills = [
            skill.service for skill in operator_doc.get("operator_skills", [])]
        if not operator_skills:
            # 400 Bad Request або 409 Conflict - оператор не може працювати
            return error_response(f"Operator {current_user} has no skills assigned.", error_code="NO_SKILLS", http_status_code=400)

        # --- Отримуємо дані Точки Обслуговування та Офісу ---
        service_point_data = frappe.db.get_value("QMS Service Point", service_point_name, [
                                                 "office", "point_name"], as_dict=True)
        if not service_point_data:
            # 404 Not Found
            return error_response(f"Service point with ID '{service_point_name}' not found.", http_status_code=404)

        office_id = service_point_data.office
        actual_service_point_display_name = service_point_data.point_name  # "Людська" назва

        if not office_id:
            # 500 Internal Server Error - проблема конфігурації
            return error_response(f"Could not determine Office for service point '{actual_service_point_display_name}'.", http_status_code=500)

        # --- Пошук Наступного Талону ---
        # TODO: Додати логіку обробки талонів по запису (is_appointment, appointment_datetime), якщо реалізовано
        waiting_tickets = frappe.get_list(
            "QMS Ticket",
            filters={
                "office": office_id,
                "status": "Waiting",
                "service": ["in", operator_skills]
            },
            fields=["name"],
            # Спочатку пріоритет, потім час створення
            order_by="priority desc, creation asc",
            limit_page_length=1
        )

        if not waiting_tickets:
            # Це інформаційна відповідь, а не помилка
            # Повертаємо порожні дані
            return info_response("No tickets found in queue for calling.", data={"ticket_info": None})

        # --- Оновлення Знайденого Талону ---
        next_ticket_name = waiting_tickets[0].name
        ticket_doc = frappe.get_doc("QMS Ticket", next_ticket_name)

        service_name = frappe.db.get_value(
            "QMS Service", ticket_doc.service, "service_name") if ticket_doc.service else "Unknown Service"

        ticket_doc.status = "Called"
        ticket_doc.call_time = now_datetime()
        ticket_doc.operator = current_user
        ticket_doc.service_point = service_point_name  # Зберігаємо ID точки

        ticket_doc.save(ignore_permissions=True)
        ticket_doc.reload()  # Оновити дані після збереження
        frappe.db.commit()

        # --- Формуємо дані для відповіді ---
        ticket_data_for_response = {
            "name": ticket_doc.name,
            "ticket_number": ticket_doc.ticket_number,
            "service": ticket_doc.service,
            "service_name": service_name,
            "service_point": ticket_doc.service_point,  # ID
            "service_point_name": actual_service_point_display_name,  # Назва
            "status": ticket_doc.status,
            "visitor_phone": ticket_doc.visitor_phone,
            "call_time": ticket_doc.call_time,
            "start_service_time": ticket_doc.start_service_time,
            "office": ticket_doc.office,
            "operator": ticket_doc.operator,
            # Додайте інші поля за потреби
        }

        # --- Успішна відповідь ---
        # Надсилаємо подію WebSocket для оновлення табло
        # Потрібно додати цю логіку, якщо використовується WebSocket
        # frappe.publish_realtime(event='qms_ticket_called', message=ticket_data_for_response, room=f'office_{office_id}')

        return success_response(
            message=f"Ticket {ticket_doc.ticket_number} called to point {actual_service_point_display_name}.",
            data={"ticket_info": ticket_data_for_response}
        )

    except frappe.exceptions.DoesNotExistError as e:
        # Обробка, якщо документ не знайдено під час get_doc або get_value
        frappe.db.rollback()
        doc_type_name = str(e).split("'")[1] if "'" in str(e) else "Document"
        return error_response(f"{doc_type_name} not found.", details=frappe.get_traceback(), http_status_code=404)
    except frappe.exceptions.PermissionError as e:
        # Обробка помилок доступу
        frappe.db.rollback()
        return error_response("Permission denied.", details=frappe.get_traceback(), http_status_code=403)
    except Exception as e:
        # Обробка інших неочікуваних помилок
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Call Next Visitor API Error")
        return error_response(
            message="An unexpected error occurred while calling the next visitor.",
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
            return error_response("Office ID is required.", http_status_code=400)

        if not frappe.db.exists("QMS Office", office):
            return error_response(f"Office '{office}' not found.", http_status_code=404)

        # Перевірка графіка роботи
        office_doc = frappe.get_cached_doc("QMS Office", office)
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule")

        office_is_open = False
        closed_message = "Working schedule not configured."

        if schedule_name:
            office_is_open = is_office_open(schedule_name, office_doc.timezone)
            if not office_is_open:
                closed_message = f"Office '{office_doc.office_name}' is currently closed."
        else:
            closed_message = f"Working schedule not configured for office '{office_doc.office_name}'."
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
                "service": service_names_map_waiting.get(row.service, "Service not specified"),
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
            message="An unexpected error occurred while fetching display data.",
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
            return error_response("Office ID is required.", http_status_code=400)
        if not frappe.db.exists("QMS Office", office):
            return error_response(f"Office '{office}' not found.", http_status_code=404)

        # Перевірка графіка роботи
        office_doc = frappe.get_cached_doc("QMS Office", office)
        schedule_name = office_doc.schedule or frappe.db.get_value(
            "QMS Organization", office_doc.organization, "default_schedule")

        office_is_open = False
        closed_message = "Working schedule not configured."

        if schedule_name:
            office_is_open = is_office_open(schedule_name, office_doc.timezone)
            if not office_is_open:
                closed_message = f"Office '{office_doc.office_name}' is currently closed."
        else:
            closed_message = f"Working schedule not configured for office '{office_doc.office_name}'."
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
            message="An unexpected error occurred while fetching kiosk services.",
            details=str(e),
            http_status_code=500
        )

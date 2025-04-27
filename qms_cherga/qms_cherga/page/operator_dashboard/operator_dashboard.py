# qms_cherga/qms_cherga/page/operator_dashboard/operator_dashboard.py
import frappe
from frappe.utils import get_fullname, today, now_datetime, time_diff_in_seconds, flt


@frappe.whitelist()
def get_initial_data():
    """
    Отримує початкові дані для Дашбоарду Оператора при його завантаженні.
    Включає інформацію про оператора (вкл. назву офісу),
    поточний активний талон (вкл. назву послуги та точки),
    та список доступних точок (вкл. назви).
    """
    current_user = frappe.session.user
    if current_user == "Guest":
        # Повертаємо помилку або структуру з позначкою помилки
        return {"error": "User not logged in", "operator_info": None, "current_ticket": None, "available_service_points": []}

    operator_info = {}
    current_ticket_details = None
    available_service_points_list = []  # Змінено назву для ясності

    # Знаходимо запис Оператора
    operator_data = frappe.db.get_value(
        "QMS Operator",
        {"user": current_user, "is_active": 1},
        ["name", "full_name", "default_office"],  # Отримуємо ID офісу
        as_dict=True
    )

    # Якщо Оператор знайдений та активний
    if operator_data:
        office_id = operator_data.default_office
        office_name_full = "Не вказано"
        # Якщо у оператора вказано офіс за замовчуванням
        if office_id:
            # Отримуємо назву офісу
            office_name_full = frappe.db.get_value(
                "QMS Office", office_id, "office_name"
            ) or office_id  # Fallback на ID, якщо назва порожня

            # Отримуємо точки обслуговування для цього офісу
            available_service_points = frappe.get_all(
                "QMS Service Point",
                filters={"office": office_id, "is_active": 1},
                fields=["name", "point_name"],  # name - ID, point_name - назва
                order_by="point_name asc"
            )
            # Перетворюємо у формат { value: 'ID', label: 'Назва' } для селектора JS
            available_service_points_list = [
                {"value": p.name, "label": p.point_name} for p in available_service_points]
        else:
            # Якщо офіс не вказано у оператора, список точок буде порожнім
            available_service_points_list = []

        # Формуємо інформацію про оператора
        operator_info = {
            "qms_operator_name": operator_data.name,
            "full_name": operator_data.full_name or get_fullname(current_user),
            "default_office_id": office_id,  # ID офісу
            "default_office_name": office_name_full,  # Назва офісу
            "current_status": "Available"  # TODO: Покращити логіку статусу оператора
        }

        # Шукаємо поточний активний талон цього оператора
        active_ticket = frappe.get_all(
            "QMS Ticket",
            filters={"operator": current_user,
                     "status": ["in", ["Serving", "Called"]]},
            # Додаємо service та service_point для отримання їхніх назв
            fields=["name", "ticket_number", "service", "service_point", "status", "visitor_phone",
                    "call_time", "start_service_time", "office"],
            order_by="modified desc",
            limit=1
        )

        # Якщо активний талон знайдено, доповнюємо його назвами
        if active_ticket:
            ticket_data = active_ticket[0]
            service_name = "N/A"
            if ticket_data.service:
                service_name = frappe.db.get_value(
                    "QMS Service", ticket_data.service, "service_name") or service_name

            service_point_name = "N/A"
            if ticket_data.service_point:
                service_point_name = frappe.db.get_value(
                    "QMS Service Point", ticket_data.service_point, "point_name") or service_point_name

            current_ticket_details = ticket_data.copy()  # Копіюємо дані
            current_ticket_details["service_name"] = service_name
            current_ticket_details["service_point_name"] = service_point_name

    else:
        # Якщо запис оператора не знайдено або він неактивний
        # Повертаємо помилку (або порожні дані, залежно від бажаної поведінки)
        # Важливо, щоб JS обробляв цей випадок
        return {
            "error": "Active QMS Operator record not found for the current user.",
            "operator_info": None,  # Явно вказуємо, що даних немає
            "current_ticket": None,
            "available_service_points": []
        }
        # Або можна генерувати Frappe Exception:
        # frappe.throw("Не знайдено активний запис Оператора для вашого користувача.", title="Помилка Налаштувань")

    # Повертаємо зібрані дані
    return {
        "operator_info": operator_info,
        "current_ticket": current_ticket_details,
        "available_service_points": available_service_points_list  # Список для селектора JS
    }


@frappe.whitelist()
def get_queue_stats(office: str):
    """
    Отримує базову статистику черги для вказаного ID офісу.
    """
    # Перевірка, чи передано ID офісу
    if not office:
        return {"waiting": "?", "served_today": "?"}

    try:
        # Рахуємо талони зі статусом 'Waiting' для цього офісу
        waiting_count = frappe.db.count(
            "QMS Ticket", {"status": "Waiting", "office": office})

        # Рахуємо талони, завершені сьогодні для цього офісу
        served_count = frappe.db.count("QMS Ticket", {
                                       "status": "Completed",
                                       "office": office,
                                       # Порівнюємо дату модифікації з початком сьогоднішнього дня
                                       "modified": [">=", today() + " 00:00:00"]
                                       })
        return {"waiting": waiting_count, "served_today": served_count}
    except Exception as e:
        # Логуємо помилку та повертаємо індикатори помилки
        frappe.log_error(frappe.get_traceback(),
                         f"Get Queue Stats Error for Office {office}")
        return {"waiting": "Err", "served_today": "Err"}


@frappe.whitelist()
def start_serving_ticket(ticket_name: str):
    """
    Змінює статус талону на 'Serving', фіксує час початку.
    Повертає оновлену інформацію про талон.
    """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            frappe.throw("Потрібна авторизація.")

        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)

        # Валідація
        if ticket_doc.operator != current_user:
            frappe.throw("Це не ваш талон.")
        if ticket_doc.status != "Called":
            frappe.throw(
                f"Невірний статус талону '{ticket_doc.status}'. Очікується 'Called'.")

        # Оновлення документа
        ticket_doc.status = "Serving"
        ticket_doc.start_service_time = now_datetime()
        ticket_doc.save()  # Може викликати 'validate' та 'before_save' хуки, якщо вони є
        frappe.db.commit()

        # Отримуємо назви для повноти відповіді (опціонально, але корисно для UI)
        service_name = frappe.db.get_value(
            "QMS Service", ticket_doc.service, "service_name") if ticket_doc.service else "N/A"
        service_point_name = frappe.db.get_value(
            "QMS Service Point", ticket_doc.service_point, "point_name") if ticket_doc.service_point else "N/A"

        ticket_info = ticket_doc.as_dict()
        ticket_info["service_name"] = service_name
        ticket_info["service_point_name"] = service_point_name

        # Сповіщення через real-time
        frappe.publish_realtime(
            event="qms_ticket_updated",
            message=ticket_info,  # Надсилаємо оновлені дані
            room=f"qms_office_{ticket_doc.office}"
        )

        # Успішна відповідь
        return {
            "status": "success",
            "message": f"Розпочато обслуговування талону {ticket_doc.ticket_number}.",
            "ticket_info": ticket_info  # Повертаємо оновлені дані
        }
    except Exception as e:
        frappe.log_error(frappe.get_traceback(),
                         "Start Serving Ticket API Error")
        frappe.db.rollback()
        # Повертаємо помилку у зрозумілому форматі
        return {"status": "error", "message": f"Помилка при старті обслуговування: {e}"}


@frappe.whitelist()
def finish_service_ticket(ticket_name: str):
    """
    Змінює статус талону на 'Completed', фіксує час завершення та тривалість.
    """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            frappe.throw("Потрібна авторизація.")

        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)

        # Валідація
        if ticket_doc.operator != current_user:
            frappe.throw("Це не ваш талон.")
        if ticket_doc.status != "Serving":
            frappe.throw(
                f"Невірний статус талону '{ticket_doc.status}'. Очікується 'Serving'.")

        # Оновлення документа
        completion_time = now_datetime()
        ticket_doc.status = "Completed"
        ticket_doc.completion_time = completion_time

        # Розрахунок тривалості обслуговування
        if ticket_doc.start_service_time:
            service_duration_seconds = time_diff_in_seconds(
                completion_time, ticket_doc.start_service_time
            )
            # Зберігаємо в хвилинах з двома знаками після коми
            ticket_doc.actual_service_time_mins = round(
                flt(service_duration_seconds) / 60.0, 2)
        else:
            # Якщо час початку не було зафіксовано
            ticket_doc.actual_service_time_mins = 0

        ticket_doc.save()
        frappe.db.commit()

        # Сповіщення (можна надсилати менше даних, лише статус)
        frappe.publish_realtime(
            event="qms_ticket_updated",
            message={'name': ticket_doc.name, 'status': ticket_doc.status,
                     'office': ticket_doc.office, 'ticket_number': ticket_doc.ticket_number},
            room=f"qms_office_{ticket_doc.office}"
        )
        # Сповіщення про оновлення статистики
        frappe.publish_realtime(
            event="qms_stats_updated",
            message={'office': ticket_doc.office},
            room=f"qms_office_{ticket_doc.office}"
        )

        return {"status": "success", "message": f"Обслуговування талону {ticket_doc.ticket_number} завершено."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(),
                         "Finish Service Ticket API Error")
        frappe.db.rollback()
        return {"status": "error", "message": f"Помилка при завершенні обслуговування: {e}"}


@frappe.whitelist()
def mark_no_show(ticket_name: str):
    """ Змінює статус талону на 'NoShow'. """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            frappe.throw("Потрібна авторизація.")

        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)

        # Валідація
        if ticket_doc.operator != current_user:
            frappe.throw("Це не ваш талон.")
        # Дозволяємо відмітити як NoShow якщо статус Called або Serving
        if ticket_doc.status not in ["Called", "Serving"]:
            frappe.throw(
                f"Невірний Статус '{ticket_doc.status}' (очікується 'Called' або 'Serving')")

        # Оновлення
        ticket_doc.status = "NoShow"
        # Можна додати логіку для очищення часу обслуговування, якщо потрібно
        # ticket_doc.start_service_time = None
        # ticket_doc.completion_time = None
        # ticket_doc.actual_service_time_mins = None
        ticket_doc.save()
        frappe.db.commit()

        # Сповіщення
        frappe.publish_realtime(
            event="qms_ticket_updated",
            message={'name': ticket_doc.name, 'status': ticket_doc.status,
                     'office': ticket_doc.office, 'ticket_number': ticket_doc.ticket_number},
            room=f"qms_office_{ticket_doc.office}"
        )
        # Оновлення статистики
        frappe.publish_realtime(
            event="qms_stats_updated",
            message={'office': ticket_doc.office},
            room=f"qms_office_{ticket_doc.office}"
        )

        return {"status": "success", "message": f"Талон {ticket_doc.ticket_number} відмічено як 'Не з\\'явився'."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Mark No Show API Error")
        frappe.db.rollback()
        return {"status": "error", "message": f"Помилка при відмітці 'Не з\\'явився': {e}"}


@frappe.whitelist()
def hold_ticket(ticket_name: str):
    """ Змінює статус талону на 'Postponed' (Відкладено). """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            frappe.throw("Потрібна авторизація.")

        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)

        # Валідація
        if ticket_doc.operator != current_user:
            frappe.throw("Це не ваш талон.")
        # Відкласти можна лише талон, що обслуговується
        if ticket_doc.status != "Serving":
            frappe.throw(
                f"Невірний Статус '{ticket_doc.status}' (очікується 'Serving').")

        # Оновлення
        ticket_doc.status = "Postponed"
        # Можна зберігати час відкладення або додаткову інформацію, якщо потрібно
        ticket_doc.save()
        frappe.db.commit()

        # Сповіщення
        frappe.publish_realtime(
            event="qms_ticket_updated",
            message={'name': ticket_doc.name, 'status': ticket_doc.status,
                     'office': ticket_doc.office, 'ticket_number': ticket_doc.ticket_number},
            room=f"qms_office_{ticket_doc.office}"
        )
        # Оновлення статистики (кількість Serving зменшилась)
        frappe.publish_realtime(
            event="qms_stats_updated",
            message={'office': ticket_doc.office},
            room=f"qms_office_{ticket_doc.office}"
        )

        return {"status": "success", "message": f"Талон {ticket_doc.ticket_number} відкладено."}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Hold Ticket API Error")
        frappe.db.rollback()
        return {"status": "error", "message": f"Помилка при відкладанні талону: {e}"}


@frappe.whitelist()
def get_my_held_tickets():
    """
    Отримує список талонів, відкладених поточним оператором ('Postponed').
    Включає назву послуги.
    """
    current_user = frappe.session.user
    if current_user == "Guest":
        return []  # Гості не мають відкладених талонів

    # Отримуємо ID талонів та ID послуг
    held_tickets_data = frappe.get_all(
        "QMS Ticket",
        filters={
            "operator": current_user,
            "status": "Postponed"
        },
        fields=["name", "ticket_number", "service"],  # Отримуємо ID послуги
        order_by="modified desc"  # Показуємо останні відкладені зверху
    )

    if not held_tickets_data:
        return []  # Повертаємо порожній список, якщо немає відкладених

    # Отримуємо назви послуг для знайдених талонів
    service_ids = [t.service for t in held_tickets_data if t.service]
    service_names_map = {}
    if service_ids:
        # Використовуємо set для унікальних ID
        services = frappe.get_all("QMS Service", filters={
                                  "name": ["in", list(set(service_ids))]}, fields=["name", "service_name"])
        service_names_map = {s.name: s.service_name for s in services}

    # Формуємо результат, додаючи назву послуги до кожного талону
    result_list = []
    for ticket in held_tickets_data:
        ticket_dict = ticket.copy()
        # Додаємо service_name, використовуючи map. Якщо назви немає, використовуємо ID або "N/A"
        ticket_dict["service_name"] = service_names_map.get(
            ticket.service, ticket.service or "N/A")
        result_list.append(ticket_dict)

    return result_list


@frappe.whitelist()
def recall_ticket(ticket_name: str):
    """
    Повертає відкладений талон ('Postponed') в роботу, встановлюючи статус 'Called'.
    Повертає оновлену інформацію про талон з назвами.
    """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            frappe.throw("Потрібна авторизація.")

        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)

        # --- Валідація ---
        if not ticket_doc:
            frappe.throw(f"Талон {ticket_name} не знайдено.")
        # Перевіряємо, чи цей оператор відклав талон
        if ticket_doc.operator != current_user:
            frappe.throw(
                "Ви не можете повернути талон, відкладений іншим оператором.")
        if ticket_doc.status != "Postponed":
            frappe.throw(
                f"Статус талону '{ticket_doc.status}'. Очікується 'Postponed'.")

        # --- Отримуємо назви для відповіді ---
        service_name = frappe.db.get_value(
            "QMS Service", ticket_doc.service, "service_name") if ticket_doc.service else "N/A"
        # Точка обслуговування може бути вже неактуальною або не призначеною при поверненні
        service_point_name = frappe.db.get_value(
            "QMS Service Point", ticket_doc.service_point, "point_name") if ticket_doc.service_point else "Не призначено"

        # --- Оновлення Полів Документа ---
        ticket_doc.status = "Called"  # Повертаємо в стан "Викликано"
        # Фіксуємо новий час "виклику" (повернення)
        ticket_doc.call_time = now_datetime()
        # Очищаємо попередні часи обслуговування та, можливо, точку
        # ticket_doc.service_point = None # Залежить від бізнес-логіки, чи скидати точку
        ticket_doc.start_service_time = None
        ticket_doc.completion_time = None
        ticket_doc.actual_service_time_mins = None

        # --- Збереження та Commit ---
        ticket_doc.save()
        frappe.db.commit()

        # --- Формуємо відповідь з назвами ---
        ticket_info = ticket_doc.as_dict()  # Отримуємо всі поля документа
        ticket_info["service_name"] = service_name
        # Навіть якщо "Не призначено"
        ticket_info["service_point_name"] = service_point_name

        # --- Публікація Realtime Подій ---
        # Оновлення статусу талону
        frappe.publish_realtime(
            event="qms_ticket_updated",
            message=ticket_info,  # Надсилаємо повну інформацію
            room=f"qms_office_{ticket_doc.office}"
        )
        # Оновлення статистики (кількість Called збільшилась)
        frappe.publish_realtime(
            event="qms_stats_updated",
            message={'office': ticket_doc.office},
            room=f"qms_office_{ticket_doc.office}"
        )

        # --- Успішна відповідь API ---
        return {
            "status": "success",
            "message": f"Талон {ticket_doc.ticket_number} повернуто до роботи.",
            "ticket_info": ticket_info  # Повертаємо оновлені дані з назвами
        }

    except Exception as e:
        # Обробка помилок
        frappe.log_error(frappe.get_traceback(), "Recall Ticket API Error")
        frappe.db.rollback()
        return {"status": "error", "message": f"Помилка під час повернення талону: {e}"}

# !!! ВАЖЛИВО: Функція call_next_visitor() була перенесена до api.py !!!
# Якщо вона все ще є у вашому файлі operator_dashboard.py, її потрібно видалити звідси.

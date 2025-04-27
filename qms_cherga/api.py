# qms_cherga/api.py

# Для встановлення поточного часу
from datetime import datetime
from frappe.utils import get_datetime, get_time, now_datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Імпорт з zoneinfo
import frappe

# Допоміжна функція для перевірки графіка (потрібно додати цей код в api.py або в інший утилітарний файл)
# УВАГА: Ця функція є спрощеним прикладом. Повноцінна реалізація має враховувати
# часові пояси, винятки (QMS Schedule Exception Child) та може бути складнішою.


def is_office_open(schedule_name: str, timezone: str):  # timezone тут ігнорується!
    """
    Перевіряє, чи відкритий офіс зараз згідно з графіком, враховуючи винятки.
    УВАГА: Ця версія ІГНОРУЄ параметр 'timezone' і використовує СИСТЕМНИЙ ЧАС сервера Frappe.
    Працюватиме коректно тільки якщо часова зона офісу = системна зона сервера.
    """
    if not schedule_name:
        frappe.log_error("Schedule name not provided.", "Schedule Check Info")
        return False

    try:
        # --- Отримання поточного часу та дати в СИСТЕМНІЙ зоні Frappe ---
        now_system_dt = now_datetime()  # Це вже об'єкт datetime в системній зоні
        current_date_str = now_system_dt.strftime('%Y-%m-%d')
        current_day_name = now_system_dt.strftime('%A')
        current_time_obj = get_time(now_system_dt.strftime('%H:%M:%S'))

        # Попередження, якщо зона офісу не співпадає з системною (опціонально)
        system_tz = frappe.utils.get_system_timezone()
        if timezone and timezone != system_tz:
            frappe.log_error(
                f"Schedule check for office timezone '{timezone}' is using system time '{system_tz}' instead.", "Schedule Check Warning")

        # --- Перевірка Винятків (логіка без змін, але порівняння з системним часом) ---
        exception = frappe.db.get_value(
            "QMS Schedule Exception Child",
            filters={"parenttype": "QMS Schedule",
                     "parent": schedule_name, "exception_date": current_date_str},
            fieldname=["is_workday", "start_time", "end_time"], as_dict=True
        )
        if exception:
            if not exception.is_workday:
                return False
            if exception.start_time and exception.end_time:
                # Порівнюємо системний час з часом винятку
                return get_time(exception.start_time) <= current_time_obj < get_time(exception.end_time)
            return False

        # --- Перевірка стандартних правил (логіка без змін, але порівняння з системним часом) ---
        rules = frappe.get_all("QMS Schedule Rule Child",
                               filters={"parent": schedule_name,
                                        "parenttype": "QMS Schedule"},
                               fields=["day_of_week", "start_time", "end_time"])
        rules_dict = {rule.day_of_week: rule for rule in rules}
        if current_day_name in rules_dict:
            rule = rules_dict[current_day_name]
            # Порівнюємо системний час з часом правила
            return get_time(rule.start_time) <= current_time_obj < get_time(rule.end_time)
        return False

    except Exception as e:
        frappe.log_error(
            f"Error checking schedule '{schedule_name}' (system time) for timezone '{timezone}': {e}", "Schedule Check Error")
        return False


# `@frappe.whitelist()` робить функцію доступною через HTTP API.
# `allow_guest=True` дозволяє викликати цей метод неавторизованим користувачам (що необхідно для кіоску).


@frappe.whitelist(allow_guest=True)
def create_live_queue_ticket(service: str, office: str, visitor_phone: str = None):
    """
    API Endpoint для створення нового талону QMS Ticket з Кіоску.

    :param service: Назва (ID) обраної послуги QMS Service.
    :param office: Назва (ID) офісу QMS Office, до якого відноситься кіоск.
    :param visitor_phone: Опціональний номер телефону відвідувача.
    :return: Словник з деталями талону або повідомленням про помилку.
    """
    # --- Базова валідація вхідних даних ---
    if not service or not office:
        # Викидаємо помилку, якщо не передано обов'язкові параметри
        frappe.throw("Не вказано Послугу або Офіс.",
                     title="Відсутня Інформація")

    # Перевіряємо, чи існують такі записи в базі даних
    if not frappe.db.exists("QMS Service", service):
        frappe.throw(f"Послуга '{service}' не знайдена.", title="Невірні Дані")
    if not frappe.db.exists("QMS Office", office):
        frappe.throw(f"Офіс '{office}' не знайдений.", title="Невірні Дані")

    # --- Додаткові перевірки (Рекомендовано додати пізніше) ---

    # TODO: Перевірити, чи активна послуга (`QMS Service`.enabled == 1)?
    # TODO: Перевірити, чи доступна послуга в цьому офісі (чи є відповідний запис у `QMS Office`.available_services)?
    # TODO: Перевірити, чи доступна послуга для живої черги (`QMS Service`.live_queue_enabled == 1)?
    # TODO: Перевірити, чи офіс зараз працює згідно з графіком (`QMS Schedule`)?
 # --- Додаткові перевірки ---

    # 1. Перевірка, чи активна послуга (`QMS Service`.enabled == 1)?
    service_doc = frappe.get_cached_doc("QMS Service", service)
    if not service_doc.enabled:
        frappe.throw(
            f"Послуга '{service_doc.service_name}' наразі неактивна.", title="Послуга Неактивна")

    # 2. Перевірка, чи доступна послуга для живої черги (`QMS Service`.live_queue_enabled == 1)?
    if not service_doc.live_queue_enabled:
        frappe.throw(
            f"Послуга '{service_doc.service_name}' недоступна для живої черги.", title="Послуга Недоступна")

    # 3. Перевірка, чи доступна послуга в цьому офісі (чи є відповідний запис у `QMS Office`.available_services)?
    is_service_in_office = frappe.db.exists(
        "QMS Office Service Assignment",
        {"parent": office, "service": service, "is_active_in_office": 1}
    )
    if not is_service_in_office:
        office_name = frappe.db.get_value("QMS Office", office, "office_name")
        frappe.throw(f"Послуга '{service_doc.service_name}' недоступна в офісі '{office_name}'.",
                     title="Послуга Недоступна в Офісі")

    # 4. Перевірка, чи офіс зараз працює згідно з графіком (`QMS Schedule`)?
    #    (Це базова перевірка, повна логіка з урахуванням винятків може бути складнішою)
    office_doc = frappe.get_cached_doc("QMS Office", office)
    schedule_name = office_doc.schedule or frappe.db.get_value(
        "QMS Organization", office_doc.organization, "default_schedule")

    if schedule_name:
        # Логіку перевірки графіка краще винести в окрему функцію
        if not is_office_open(schedule_name, office_doc.timezone):
            frappe.throw(
                f"Офіс '{office_doc.office_name}' наразі зачинений.", title="Офіс Зачинено")
    else:
        # Якщо графік не вказано ні для офісу, ні для організації, можливо, дозволити завжди? Або видати помилку?
        frappe.throw(
            f"Для офісу '{office_doc.office_name}' не налаштовано графік роботи.", title="Графік Не Налаштовано")

    # --- Валідація номеру телефону (приклад простої перевірки) ---
    if visitor_phone:
        # TODO: Додати більш надійну валідацію формату номеру телефону
        # Наприклад, за допомогою регулярних виразів або зовнішньої бібліотеки
        if not visitor_phone.replace("+", "").replace("-", "").isdigit():
            frappe.msgprint(
                f"Номер телефону '{visitor_phone}' має невірний формат.", title="Попередження", indicator="orange")
            # Не кидаємо помилку, але попереджаємо і, можливо, не зберігаємо
            # visitor_phone = None # Очистити, якщо не валідний?
    try:
        # --- Створення документу QMS Ticket ---
        new_ticket = frappe.new_doc("QMS Ticket")
        new_ticket.office = office
        new_ticket.service = service
        new_ticket.status = "Waiting"  # Статус за замовчуванням
        # Використовуємо frappe.utils.now(), що повертає рядок у форматі БД
        new_ticket.issue_time = frappe.utils.now()  # Час створення талону

        # Додаємо телефон, якщо він переданий
        if visitor_phone:
            # TODO: Додати валідацію формату номеру телефону?
            new_ticket.visitor_phone = visitor_phone

        # Метод `autoname` в qms_ticket.py автоматично встановить `name` та `ticket_number`
        # Якщо autoname не спрацьовує або не визначений, потрібно генерувати `name` тут.

        # --- Збереження в базі даних ---
        # `ignore_permissions=True` дозволяє гостьовому користувачу (кіоску) створювати документ.
        # ВАЖЛИВО: Переконайтесь, що валідація вище (TODO) достатньо надійна,
        # щоб запобігти створенню небажаних талонів.
        new_ticket.insert(ignore_permissions=True)

        # Застосовуємо зміни в базі даних
        frappe.db.commit()

        # --- Успішна відповідь ---
        # Повертаємо інформацію про створений талон на фронтенд (кіоск)
        return {
            "status": "success",
            "message": "Ticket created successfully",
            # Унікальний ID запису (напр., CNAP1-0001), встановлюється через autoname
            "ticket_name": new_ticket.name,
            # Поле для відображення (дублює name, також встановлюється через autoname)
            "ticket_number": new_ticket.ticket_number,
            "office": new_ticket.office,
            "service": new_ticket.service
            # Можна додати інші поля за потреби
        }

    except Exception as e:
        # Обробка можливих помилок під час створення
        frappe.log_error(reference_doctype="QMS Ticket",
                         title="QMS Ticket Creation Error",
                         message=f"Error creating ticket: {str(e)}")
        # Відкочуємо транзакцію у разі помилки
        frappe.db.rollback()
        # Повертаємо помилку на фронтенд
        # Не варто показувати деталі системної помилки на публічному кіоску
        return {
            "status": "error",
            "message": "Не вдалося створити талон. Спробуйте пізніше або зверніться до адміністратора."
            # "error_details": str(e) # Можна розкоментувати для налагодження
        }


@frappe.whitelist()  # Доступно тільки для авторизованих користувачів
def call_next_visitor(service_point_name: str):
    """
    Знаходить наступний талон у черзі (Waiting) для вказаної точки обслуговування (за її ID),
    враховуючи пріоритет, час створення та навички поточного оператора.
    Змінює статус знайденого талону на 'Called'.
    Повертає деталі викликаного талону, включаючи назви послуги та точки.

    :param service_point_name: Назва (ID) точки обслуговування QMS Service Point, з якої йде виклик.
    :return: Словник з деталями викликаного талону або повідомлення про статус.
    """
    try:
        current_user = frappe.session.user
        if current_user == "Guest":
            frappe.throw("Ви повинні увійти в систему, щоб викликати відвідувачів.",
                         title="Потрібна Авторизація")

        # --- Отримуємо дані Оператора та його Навички ---
        operator_doc_name = frappe.db.get_value(
            "QMS Operator", {"user": current_user, "is_active": 1}, "name")
        if not operator_doc_name:
            frappe.throw(
                f"Активний запис Оператора Черги для користувача {current_user} не знайдено.", title="Оператора не знайдено")

        operator_doc = frappe.get_doc("QMS Operator", operator_doc_name)
        operator_skills = [
            skill.service for skill in operator_doc.operator_skills]
        if not operator_skills:
            frappe.throw(
                f"Оператору {current_user} не призначено жодних навичок (послуг).", title="Відсутні Навички")

        # --- Отримуємо дані Точки Обслуговування та Офісу ---
        # Отримуємо ID офісу та "людську" назву точки
        service_point_doc = frappe.db.get_value("QMS Service Point", service_point_name, [
                                                "office", "point_name"], as_dict=True)  # service_point_name тут - це ID
        if not service_point_doc:
            frappe.throw(
                f"Точку обслуговування з ID '{service_point_name}' не знайдено.", title="Невірна Точка Обслуговування")

        office_id = service_point_doc.office
        actual_service_point_name = service_point_doc.point_name  # "Людська" назва точки

        if not office_id:
            frappe.throw(
                f"Не вдалося визначити Офіс для точки обслуговування '{actual_service_point_name}' (ID: {service_point_name}).", title="Помилка Конфігурації")

        # --- Пошук Наступного Талону ---
        # Шукаємо талони зі статусом 'Waiting' для цього офісу,
        # де послуга входить до списку навичок оператора.
        waiting_tickets = frappe.get_list(
            "QMS Ticket",
            filters={
                "office": office_id,
                "status": "Waiting",
                "service": ["in", operator_skills]
            },
            fields=["name"],  # Нам потрібне лише ім'я (ID) талону
            # Спочатку вищий пріоритет, потім найстаріший
            order_by="priority desc, creation asc",
            limit_page_length=1  # Беремо лише один
        )

        if not waiting_tickets:
            # Якщо талонів, що відповідають критеріям, немає
            return {"status": "info", "message": "Немає талонів у черзі для виклику."}

        # --- Оновлення Знайденого Талону ---
        next_ticket_name = waiting_tickets[0].name
        ticket_doc = frappe.get_doc("QMS Ticket", next_ticket_name)

        # Отримуємо назву послуги
        service_id = ticket_doc.service
        service_name = frappe.db.get_value(
            "QMS Service", service_id, "service_name") if service_id else "Невідома послуга"

        # Оновлюємо поля талону
        ticket_doc.status = "Called"          # Змінюємо статус
        ticket_doc.call_time = now_datetime()  # Фіксуємо час виклику
        ticket_doc.operator = current_user    # Записуємо, який оператор викликав
        # Записуємо ID точки, з якої викликали
        ticket_doc.service_point = service_point_name

        ticket_doc.save()  # Зберігаємо зміни
        frappe.db.commit()  # Застосовуємо транзакцію

        # --- Сповіщення через Real-time ---
        frappe.publish_realtime(
            event="qms_ticket_called",
            message={
                'ticket_number': ticket_doc.ticket_number,  # Повний номер талону
                'service_point_name': actual_service_point_name,  # "Людська" назва точки
                'office': office_id,  # ID офісу для фільтрації подій
                'service_name': service_name,  # Назва послуги
                # Додаємо оператора, який викликав (може бути корисно)
                'operator': current_user
                # Можна додати інші поля за потреби
            },
            # Кімната для підписки (за ID офісу)
            room=f"qms_office_{office_id}"
        )

        # --- Успішна відповідь API ---
        return {
            "status": "success",
            "message": f"Талон {ticket_doc.ticket_number} викликано на точку {actual_service_point_name}.",
            "ticket_info": {  # Повертаємо детальну інформацію для дашборду оператора
                "name": ticket_doc.name,
                "ticket_number": ticket_doc.ticket_number,
                "service": ticket_doc.service,  # ID послуги
                "service_name": service_name,  # Назва послуги
                "service_point": ticket_doc.service_point,  # ID точки
                "service_point_name": actual_service_point_name,  # Назва точки
                "status": ticket_doc.status,
                "visitor_phone": ticket_doc.visitor_phone,
                "call_time": ticket_doc.call_time,
                "start_service_time": ticket_doc.start_service_time,
                "office": ticket_doc.office  # ID офісу
                # Додайте інші поля з ticket_doc за потреби
            }
        }

    except Exception as e:
        # Обробка помилок
        frappe.log_error(frappe.get_traceback(), "Call Next Visitor API Error")
        frappe.db.rollback()
        # Формуємо відповідь про помилку
        return {
            "status": "error",
            "message": f"Помилка під час виклику наступного талону: {e}"
        }

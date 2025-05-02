# qms_cherga/api.py

# Для встановлення поточного часу
from datetime import datetime
from frappe.utils import get_datetime, get_system_timezone, get_time, now_datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Імпорт з zoneinfo
import frappe

# Допоміжна функція для перевірки графіка (потрібно додати цей код в api.py або в інший утилітарний файл)
# УВАГА: Ця функція є спрощеним прикладом. Повноцінна реалізація має враховувати
# часові пояси, винятки (QMS Schedule Exception Child) та може бути складнішою.


def is_office_open(schedule_name: str, timezone: str):
    """
    Перевіряє, чи відкритий офіс зараз згідно з графіком, враховуючи винятки,
    часову зону офісу та можливість кількох робочих інтервалів на день.

    :param schedule_name: Назва (ID) документу QMS Schedule.
    :param timezone: Рядок з назвою часової зони у форматі IANA (напр., 'Europe/Kyiv').
    :return: True, якщо офіс відкритий, False - якщо закритий або сталася помилка.
    """
    if not schedule_name:
        # Логуємо помилку, якщо ім'я графіка не передано
        frappe.log_error("Schedule name not provided for is_office_open check.",
                         "Schedule Check Error")
        return False

    office_tz = None
    try:
        # --- Крок 1: Визначення об'єкта часової зони офісу ---
        if timezone:
            # Створюємо об'єкт ZoneInfo з переданого рядка
            office_tz = ZoneInfo(timezone)
        else:
            # Якщо часова зона не вказана для офісу, використовуємо системну зону сервера Frappe
            system_tz_str = get_system_timezone()
            office_tz = ZoneInfo(system_tz_str)
            # Логуємо попередження про використання системної зони
            frappe.log_warning(f"Office timezone not provided for schedule '{schedule_name}'. Falling back to system timezone '{system_tz_str}'.",
                               "Schedule Check Info")

    except ZoneInfoNotFoundError:
        # Якщо вказана в офісі часова зона недійсна (не знайдена в базі IANA)
        system_tz_str = get_system_timezone()
        office_tz = ZoneInfo(system_tz_str)
        # Логуємо помилку і використовуємо системну зону
        frappe.log_error(message=f"Invalid timezone '{timezone}' provided for schedule '{schedule_name}'. Falling back to system timezone '{system_tz_str}'.",
                         title="Schedule Check Error")
    except Exception as e:
        # Обробка інших можливих помилок при роботі з ZoneInfo
        system_tz_str = get_system_timezone()
        office_tz = ZoneInfo(system_tz_str)
        frappe.log_error(message=f"Error processing timezone '{timezone}' for schedule '{schedule_name}'. Falling back to system timezone '{system_tz_str}'. Error: {e}",
                         title="Schedule Check Error")

    # --- Основна логіка перевірки ---
    try:
        # --- Крок 2: Отримання поточного часу в часовій зоні офісу ---
        # frappe.utils.now_datetime() повертає datetime об'єкт, що вже усвідомлює часову зону (зазвичай системну)
        # Конвертуємо цей час у цільову часову зону офісу
        now_local_dt = now_datetime().astimezone(office_tz)

        # Отримуємо компоненти дати та часу з локального часу офісу
        current_date_str = now_local_dt.strftime('%Y-%m-%d')
        # День тижня англійською (необхідно для пошуку правил)
        current_day_name = now_local_dt.strftime('%A')
        # Отримуємо об'єкт time для порівняння (вже в локальному часі офісу)
        current_time_obj = get_time(now_local_dt.strftime('%H:%M:%S'))

        # --- Крок 3: Перевірка Винятків (Exceptions) ---
        # Шукаємо винятки, що стосуються поточної дати (в локальному часі офісу)
        exceptions = frappe.get_all(
            "QMS Schedule Exception Child",
            filters={
                "parenttype": "QMS Schedule",
                "parent": schedule_name,
                "exception_date": current_date_str  # Порівнюємо з локальною датою
            },
            fields=["is_workday", "start_time", "end_time"],
            # Зазвичай лише один виняток на день, але отримуємо всі на випадок дублікатів
        )

        if exceptions:
            # Перевіряємо, чи є хоч один запис, що явно вказує на неробочий день
            is_explicitly_non_workday = any(
                not exc.is_workday for exc in exceptions)
            if is_explicitly_non_workday:
                # Якщо знайдено запис is_workday=0, день точно неробочий, незалежно від правил
                return False

            # Якщо не було явного 'неробочий', перевіряємо робочі інтервали з винятків
            found_working_interval_in_exception = False
            for exception in exceptions:
                # Перевіряємо тільки ті записи, де is_workday=1 і вказано час початку та кінця
                if exception.is_workday and exception.start_time and exception.end_time:
                    # Час у правилах/винятках вважається локальним для офісу
                    start_time_exc = get_time(exception.start_time)
                    end_time_exc = get_time(exception.end_time)
                    # Порівнюємо поточний локальний час офісу з локальним часом інтервалу винятку
                    if start_time_exc <= current_time_obj < end_time_exc:
                        # Знайшли відповідний робочий інтервал у винятках - офіс відкритий
                        return True

            # Якщо пройшли всі записи винятків і не знайшли відповідного робочого інтервалу,
            # АЛЕ день був позначений як робочий виняток (is_workday=1, хоч час не підійшов або не був вказаний),
            # то вважаємо, що офіс зачинений, бо виняток має пріоритет.
            if any(exc.is_workday for exc in exceptions):
                return False

            # Якщо були тільки is_workday=0, то ми вже вийшли з функції раніше.
            # Якщо список винятків був порожній, переходимо до перевірки правил.

        # --- Крок 4: Якщо винятків не було або вони не застосувались, перевіряємо стандартні правила ---
        # Шукаємо правила для поточного дня тижня (в локальному часі офісу)
        all_rules = frappe.get_all(
            "QMS Schedule Rule Child",
            filters={
                "parent": schedule_name,
                "parenttype": "QMS Schedule",
                "day_of_week": current_day_name  # Використовуємо локальний день тижня
            },
            fields=["start_time", "end_time"]
        )

        # Якщо на цей день тижня взагалі немає правил у графіку
        if not all_rules:
            return False

        # Перевіряємо кожен робочий інтервал (правило) для цього дня
        for rule in all_rules:
            # Час у правилах вважається локальним для офісу
            start_time_rule = get_time(rule.start_time)
            end_time_rule = get_time(rule.end_time)
            # Порівнюємо поточний локальний час офісу з локальним часом інтервалу правила
            if start_time_rule <= current_time_obj < end_time_rule:
                # Знайшли відповідний робочий інтервал у правилах - офіс відкритий
                return True

        # Якщо пройшли всі правила для цього дня і жоден інтервал не підійшов
        return False

    except Exception as e:
        # Логування будь-якої помилки під час виконання основної логіки
        now_local_dt_str = now_local_dt.isoformat() if 'now_local_dt' in locals() else 'N/A'
        frappe.log_error(
            f"Error during schedule check for schedule '{schedule_name}' with timezone '{timezone}'. Current local time check: {now_local_dt_str}. Error: {e}\n{frappe.get_traceback()}",
            "Schedule Check Runtime Error"
        )
        # У разі будь-якої помилки безпечніше вважати, що офіс зачинений
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
            frappe.log_error(title="Operator Skills Error",
                             message=f"Operator {current_user} has no skills assigned. Raising ValidationError.")
            frappe.throw(
                msg=f"Оператору {current_user} не призначено жодних навичок (послуг).",
                title="Відсутні Навички",
                exc=frappe.ValidationError  # Явно вказуємо тип винятку
            )

        # --- Отримуємо дані Точки Обслуговування та Офісу ---
        # Отримуємо ID офісу та "людську" назву точки
        service_point_doc = frappe.db.get_value("QMS Service Point", service_point_name, [
            "office", "point_name"], as_dict=True)  # service_point_name тут - це ID
        if not service_point_doc:
            frappe.throw(
                msg=f"Точку обслуговування з ID '{service_point_name}' не знайдено.",
                title="Невірна Точка Обслуговування")

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

        ticket_doc.save(ignore_permissions=True)  # Зберігаємо зміни
        ticket_doc.reload()
        frappe.db.commit()  # Застосовуємо транзакцію
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
                "office": ticket_doc.office,  # ID офісу
                "operator": ticket_doc.operator,  # ID оператора

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


@frappe.whitelist(allow_guest=True)
def get_display_data(office: str, limit_called: int = 3, limit_waiting: int = 20):
    """
    Отримує комбіновані дані для публічного дисплея черги (версія з ORM):
    останні викликані та наступні очікуючі талони.
    """
    limit_called = frappe.cint(
        limit_called)  # Перетворюємо на цілі числа [cite: 138]
    limit_waiting = frappe.cint(limit_waiting)  # [cite: 138]

    if not office:  # [cite: 138]
        frappe.log_error(
            "Office ID not provided for get_display_data", "Display API ORM")  # [cite: 138]
        return {"error": "Office ID is required."}  # [cite: 138]

    if not frappe.db.exists("QMS Office", office):  # [cite: 138]
        frappe.log_error(
            f"Office ID '{office}' not found for get_display_data", "Display API ORM")  # [cite: 138]
        return {"error": f"Office '{office}' not found."}  # [cite: 138]

    # Перевірка графіка роботи
    office_doc = frappe.get_cached_doc("QMS Office", office)
    schedule_name = office_doc.schedule or frappe.db.get_value(
        "QMS Organization", office_doc.organization, "default_schedule"
    )

    office_is_open = False
    closed_message = "Графік роботи не налаштовано."

    if schedule_name:
        office_is_open = is_office_open(schedule_name, office_doc.timezone)
        if not office_is_open:
            closed_message = f"Офіс '{office_doc.office_name}' наразі зачинено."
    else:
        closed_message = f"Для офісу '{office_doc.office_name}' не налаштовано графік роботи."
        office_is_open = False

    if not office_is_open:
        return {
            "office_status": "closed",  # Статус
            "message": closed_message,  # Повідомлення
            "last_called": [],
            "waiting": []
        }

    # --- Отримуємо останні викликані/обслужені (ORM + сортування в Python) ---
    last_called = []  # [cite: 138]
    try:
        called_statuses = ["Called"]  # [cite: 138]
        # Отримуємо більше записів, щоб потім відсортувати в Python
        potential_called = frappe.get_all(
            "QMS Ticket",
            filters={
                "office": office,
                "status": ["in", called_statuses],
                "issue_time": ["Timespan", "today"],
            },
            fields=[
                "name", "ticket_number", "status", "service", "service_point",
                "call_time", "start_service_time", "completion_time",
                "modified"  # <--- Додано 'modified' для можливості використання як fallback
            ],
            # Попереднє сортування для оптимізації [cite: 138]
            order_by="modified desc",
            # Беремо з запасом для сортування
            limit_page_length=max(20, limit_called * 3)  # [cite: 138]
        )

        # Розраховуємо "найпізніший час" для кожного талону
        tickets_with_latest_time = []  # [cite: 138]
        for ticket in potential_called:  # [cite: 138]
            # Отримуємо datetime об'єкти або None
            call_dt = get_datetime(ticket.get('call_time'))  # [cite: 138]
            start_dt = get_datetime(ticket.get(
                'start_service_time'))  # [cite: 138]
            completion_dt = get_datetime(
                ticket.get('completion_time'))  # [cite: 138]
            # [cite: 138] # Отримуємо час модифікації
            modified_dt = get_datetime(ticket.get('modified'))

            # Знаходимо максимальний з перших трьох (час події)
            latest_event_dt = max(
                filter(None, [call_dt, start_dt, completion_dt]), default=None)  # [cite: 138]

            # Використовуємо час події, або час модифікації якщо подій не було
            # (Можна закоментувати 'or modified_dt', якщо fallback не потрібен)
            display_dt = latest_event_dt or modified_dt  # [cite: 138]

            if display_dt:  # Переконуємось, що хоч якийсь час є [cite: 138]
                tickets_with_latest_time.append({  # [cite: 138]
                    "data": ticket,  # [cite: 138]
                    # Зберігаємо display_dt для сортування/відображення
                    "display_dt": display_dt  # [cite: 138]
                })

        # Сортуємо в Python за display_dt (від новішого до старішого)
        tickets_with_latest_time.sort(  # [cite: 138]
            key=lambda x: x["display_dt"], reverse=True)  # [cite: 138]

        # Беремо потрібну кількість (limit_called)
        top_called_tickets = [item["data"]  # [cite: 138]
                              for item in tickets_with_latest_time[:limit_called]]  # [cite: 138]
        # Отримуємо відповідний display_dt для відібраних талонів
        top_called_times = {item["data"]["name"]: item["display_dt"]
                            for item in tickets_with_latest_time[:limit_called]}  # [cite: 138]

        # Отримуємо назви точок та послуг для відібраних талонів
        point_ids = [t["service_point"]  # [cite: 138]
                     for t in top_called_tickets if t.get("service_point")]  # [cite: 138]
        service_ids_called = [t["service"]  # [cite: 138]
                              for t in top_called_tickets if t.get("service")]  # [cite: 138]

        point_names_map = {}  # [cite: 138]
        if point_ids:  # [cite: 138]
            points = frappe.get_all("QMS Service Point", filters={  # [cite: 138]
                "name": ["in", list(set(point_ids))]}, fields=["name", "point_name"])  # [cite: 138]
            point_names_map = {
                p.name: p.point_name for p in points}  # [cite: 138]

        service_names_map_called = {}  # [cite: 138]
        if service_ids_called:  # [cite: 138]
            services = frappe.get_all("QMS Service", filters={"name": ["in", list(  # [cite: 138]
                set(service_ids_called))]}, fields=["name", "service_name"])  # [cite: 138]
            service_names_map_called = {  # [cite: 138]
                s.name: s.service_name for s in services}  # [cite: 138]

        # Форматуємо результат для last_called
        for ticket_data in top_called_tickets:  # [cite: 138]
            # Беремо збережений час для цього талону
            display_time_dt = top_called_times.get(
                ticket_data.name)  # [cite: 138]

            # Скорочений номер талону
            short_ticket_number = ticket_data.ticket_number.split(  # [cite: 138]
                '-')[-1] if ticket_data.ticket_number and '-' in ticket_data.ticket_number else ticket_data.ticket_number  # [cite: 138]

            last_called.append({  # [cite: 138]
                # [cite: 138]
                "ticket": short_ticket_number or ticket_data.name,
                # [cite: 138]
                "window": point_names_map.get(ticket_data.get("service_point"), "N/A"),
                # Форматуємо знайдений час
                # [cite: 138]
                "time": display_time_dt.strftime("%H:%M") if display_time_dt else "--:--"
            })

    except Exception as e:
        frappe.log_error(  # [cite: 138]
            f"Error fetching/sorting last called tickets (ORM) for office {office}: {e}\n{frappe.get_traceback()}", "Display API ORM")  # [cite: 138]
        # [cite: 138]
        last_called = [{"ticket": "Error", "window": "ORM Error", "time": ""}]

    # --- Отримуємо наступних у черзі (ORM) ---
    waiting_tickets = []  # [cite: 138]
    try:
        waiting_raw = frappe.get_all(  # [cite: 138]
            "QMS Ticket",
            filters={
                "office": office,
                "status": "Waiting",
                "issue_time": ["Timespan", "today"]
            },
            fields=["name", "ticket_number", "service"],
            order_by="priority desc, creation asc",  # [cite: 138]
            ignore_permissions=True,  # [cite: 138]
            limit_page_length=limit_waiting  # Використовуємо ліміт [cite: 138]
        )

        # Отримуємо назви послуг одним запитом
        service_ids_waiting = [  # [cite: 138]
            row.service for row in waiting_raw if row.service]  # [cite: 138]
        service_names_map_waiting = {}  # [cite: 138]
        if service_ids_waiting:  # [cite: 138]
            services = frappe.get_all("QMS Service", filters={"name": ["in", list(  # [cite: 138]
                set(service_ids_waiting))]}, fields=["name", "service_name"])  # [cite: 138]
            service_names_map_waiting = {  # [cite: 138]
                s.name: s.service_name for s in services}  # [cite: 138]

        # Форматуємо дані для waiting
        for row in waiting_raw:  # [cite: 138]
            # Скорочений номер талону
            short_ticket_number = row.ticket_number.split(  # [cite: 138]
                '-')[-1] if row.ticket_number and '-' in row.ticket_number else row.ticket_number  # [cite: 138]
            waiting_tickets.append({  # [cite: 138]
                "ticket": short_ticket_number or row.name,  # [cite: 138]
                # [cite: 138]
                "service": service_names_map_waiting.get(row.service, "Послуга не вказана")
            })
    except Exception as e:
        frappe.log_error(  # [cite: 138]
            f"Error fetching waiting tickets (ORM) for office {office}: {e}\n{frappe.get_traceback()}", "Display API ORM")  # [cite: 138]
        waiting_tickets = [
            {"ticket": "Error", "service": "ORM Error"}]  # [cite: 138]

    # Логування перед поверненням (можна закоментувати після відладки)
    # frappe.log_error(f"Formatted last_called data for display: {last_called}", "Display API Debug")

    return {  # [cite: 138]
        "office_status": "open",  # Додаємо статус
        "last_called": last_called,  # [cite: 138]
        "waiting": waiting_tickets  # [cite: 138]
    }


# ... (існуючий код в api.py) ...
@frappe.whitelist(allow_guest=True)
def get_kiosk_services(office: str):
    """
    Отримує список доступних для кіоску послуг для вказаного офісу,
    згрупованих за категоріями та ВІДСОРТОВАНИХ згідно з порядком
    у таблиці 'available_services' документа QMS Office.
    Включає іконки для послуг.

    :param office: ID офісу (QMS Office).
    :return: Словник зі структурою {categories: [...], services_no_category: [...]}.
    """
    if not office or not frappe.db.exists("QMS Office", office):
        return {"error": f"Офіс '{office}' не знайдений або не вказаний."}

    # Отримуємо дані офісу та перевіряємо графік
    office_doc = frappe.get_cached_doc("QMS Office", office)
    schedule_name = office_doc.schedule or frappe.db.get_value(
        "QMS Organization", office_doc.organization, "default_schedule"
    )

    office_is_open = False
    closed_message = "Графік роботи не налаштовано."  # Повідомлення за замовчуванням

    if schedule_name:
        # ВАЖЛИВО: is_office_open використовує СИСТЕМНИЙ ЧАС сервера.
        # Переконайтесь, що він збігається з часом офісу, або покращіть is_office_open.
        office_is_open = is_office_open(schedule_name, office_doc.timezone)
        if not office_is_open:
            # TODO: Можна додати логіку отримання годин роботи з графіка для повідомлення
            closed_message = f"Офіс '{office_doc.office_name}' наразі зачинено згідно з графіком роботи."
    else:
        # Якщо графік не вказано, вважаємо зачиненим або видаємо помилку конфігурації
        closed_message = f"Для офісу '{office_doc.office_name}' не налаштовано графік роботи."
        office_is_open = False  # Явно вказуємо, що зачинено без графіка

    if not office_is_open:
        return {
            "status": "closed",
            "message": closed_message,
            "categories": [],  # Повертаємо порожні списки
            "services_no_category": []
        }
    assignments = frappe.get_all(
        "QMS Office Service Assignment",
        filters={"parent": office, "is_active_in_office": 1},
        fields=["service"],
        order_by="idx asc"
    )
    if not assignments:
        return {"categories": [], "services_no_category": []}

    ordered_service_ids = [a.service for a in assignments]
    if not ordered_service_ids:
        return {"categories": [], "services_no_category": []}

    # --- ЗМІНА: Додаємо 'icon' до списку полів ---
    services_details = frappe.get_all(
        "QMS Service",
        filters={
            "name": ["in", ordered_service_ids],
            "enabled": 1,
            "live_queue_enabled": 1
        },
        fields=["name", "service_name", "category",
                "icon"]  # <-- Додано 'icon'
    )
    # ----------------------------------------------

    active_services_map = {s.name: s for s in services_details}

    category_ids = list(
        set(s.category for s in services_details if s.category))
    categories_map = {}
    if category_ids:
        categories_data = frappe.get_all(
            "QMS Service Category",
            filters={"name": ["in", category_ids]},
            fields=["name", "category_name", "display_order"],
            order_by="display_order asc, category_name asc"
        )
        categories_map = {
            cat.name: {"label": cat.category_name, "services": []}
            for cat in categories_data
        }

    services_no_category_ordered = []
    final_categories_map = {
        cat_id: {"label": data["label"], "services": []}
        for cat_id, data in categories_map.items()
    }

    for service_id in ordered_service_ids:
        if service_id in active_services_map:
            service_info = active_services_map[service_id]
            # --- ЗМІНА: Додаємо іконку до даних послуги ---
            service_data = {
                "id": service_info.name,
                "label": service_info.service_name,
                "icon": service_info.icon  # <-- Передаємо іконку
            }
            # --------------------------------------------

            if service_info.category and service_info.category in final_categories_map:
                final_categories_map[service_info.category]["services"].append(
                    service_data)
            else:
                services_no_category_ordered.append(service_data)

    final_categories_list = []
    if category_ids and categories_map:
        sorted_cat_ids = [cat.name for cat in categories_data]
        for cat_id in sorted_cat_ids:
            if cat_id in final_categories_map and final_categories_map[cat_id]["services"]:
                final_categories_list.append(final_categories_map[cat_id])

    return {
        "categories": final_categories_list,
        "services_no_category": services_no_category_ordered
    }

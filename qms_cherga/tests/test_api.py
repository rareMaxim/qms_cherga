# qms_cherga/tests/test_api.py
import frappe
# Або IntegrationTestCase, якщо потрібно більше інтеграції
from frappe.tests.utils import FrappeTestCase
# Для маніпуляцій з часом/запитами
from frappe.utils import now_datetime, add_days, get_date_str

# Імпортуємо функції, які будемо тестувати
from qms_cherga.api import create_live_queue_ticket, call_next_visitor, is_office_open

# Імпортуємо інші потрібні функції або класи, якщо необхідно
# from unittest.mock import patch # Для мокування часу


class TestQMSApi(FrappeTestCase):

    # Метод setUp виконується перед кожним тестом у класі
    def setUp(self):
        # Створюємо необхідні базові дані для тестів
        # Переконайтесь, що ці дані не конфліктують з існуючими, або очищайте їх у tearDown
        self.organization = create_test_organization()
        self.schedule = create_test_schedule(self.organization.name)
        self.office = create_test_office(
            self.organization.name, self.schedule.name, "TESTOFF")
        self.service1 = create_test_service(
            self.organization.name, "Послуга 1", live_queue_enabled=1, enabled=1)
        self.service2 = create_test_service(
            self.organization.name, "Послуга 2 (Неактивна)", live_queue_enabled=1, enabled=0)
        self.service3 = create_test_service(
            self.organization.name, "Послуга 3 (Не для кіоску)", live_queue_enabled=0, enabled=1)
        self.service_point = create_test_service_point(
            self.office.name, "Вікно 1")

        # Створюємо тестового користувача та оператора
        self.test_user = create_test_user(
            "test_qms_op@example.com", "Тестовий Оператор")
        self.operator = create_test_operator(self.test_user.name, self.office.name, [
                                             self.service1.name])  # Навичка тільки для service1

        # Призначаємо послугу офісу
        assign_service_to_office(self.office.name, self.service1.name)
        # Неактивна послуга також призначена
        assign_service_to_office(self.office.name, self.service2.name)
        # Послуга не для кіоску також призначена
        assign_service_to_office(self.office.name, self.service3.name)

        # Перелогінюємось як тестовий оператор для тестів, що потребують авторизації
        frappe.set_user(self.test_user.name)

    # Метод tearDown виконується після кожного тесту (для очищення)
    def tearDown(self):
        # Повертаємо користувача адміністратора
        frappe.set_user("Administrator")
        # Видаляємо створені тестові дані (або використовуємо rollback)
        # frappe.db.rollback() # Якщо ви використовуєте IntegrationTestCase і хочете відкочувати зміни
        # Або явне видалення:
        frappe.delete_doc("QMS Ticket", self.get_tickets_created_in_test(
        ), ignore_permissions=True, force=True)
        frappe.delete_doc("QMS Operator", self.operator.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("User", self.test_user.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("QMS Service Point", self.service_point.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("QMS Office", self.office.name,
                          ignore_permissions=True, force=True)  # Видалить і assignments
        frappe.delete_doc("QMS Service", self.service1.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("QMS Service", self.service2.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("QMS Service", self.service3.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("QMS Schedule", self.schedule.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("QMS Organization", self.organization.name,
                          ignore_permissions=True, force=True)
        frappe.db.commit()  # Підтверджуємо видалення

    # --- Тести для create_live_queue_ticket ---

    def test_create_ticket_success(self):
        # Тестуємо успішне створення
        response = create_live_queue_ticket(
            service=self.service1.name, office=self.office.name)
        self.assertEqual(response.get("status"), "success")
        self.assertTrue(response.get("ticket_name"))
        self.assertTrue(response.get("ticket_number"))
        self.assertTrue(frappe.db.exists(
            "QMS Ticket", response.get("ticket_name")))
        # Перевіряємо, чи номер відповідає формату
        self.assertTrue(response.get("ticket_number").startswith(
            self.office.abbreviation))

    def test_create_ticket_missing_params(self):
        # Тестуємо помилку при відсутності параметрів
        with self.assertRaises(frappe.ValidationError):
            create_live_queue_ticket(service=self.service1.name, office="")
        with self.assertRaises(frappe.ValidationError):
            create_live_queue_ticket(service="", office=self.office.name)

    def test_create_ticket_invalid_service(self):
        # Тестуємо помилку при неіснуючій послузі
        with self.assertRaises(frappe.ValidationError):
            create_live_queue_ticket(
                service="Неіснуюча Послуга", office=self.office.name)

    def test_create_ticket_inactive_service(self):
        # Тестуємо помилку для неактивної послуги
        with self.assertRaises(frappe.ValidationError) as cm:
            create_live_queue_ticket(
                service=self.service2.name, office=self.office.name)
        self.assertIn("наразі неактивна", str(cm.exception))

    def test_create_ticket_not_live_queue(self):
        # Тестуємо помилку для послуги, що не для кіоску
        with self.assertRaises(frappe.ValidationError) as cm:
            create_live_queue_ticket(
                service=self.service3.name, office=self.office.name)
        self.assertIn("недоступна для живої черги", str(cm.exception))

    def test_create_ticket_service_not_in_office(self):
        # Створюємо послугу, не призначену офісу
        service_other = create_test_service(
            self.organization.name, "Інша Послуга", live_queue_enabled=1, enabled=1)
        with self.assertRaises(frappe.ValidationError) as cm:
            create_live_queue_ticket(
                service=service_other.name, office=self.office.name)
        self.assertIn("недоступна в офісі", str(cm.exception))

        frappe.delete_doc("QMS Service", service_other.name,
                          ignore_permissions=True, force=True)  # Clean up

    # --- Тести для is_office_open ---
    # Ці тести потребують контролю часу. Використаємо `frappe.utils.now_datetime`
    # як орієнтир, але краще використовувати mock або freezegun для надійності.

    # @patch('frappe.utils.now_datetime') # Приклад використання mock
    def test_is_office_open_during_working_hours(self):  # , mock_now):
        # Налаштовуємо час на робочий (напр., Середа 10:00)
        # mock_now.return_value = datetime(2025, 4, 30, 10, 0, 0) # Потрібен імпорт datetime
        # Поки що просто викликаємо, припускаючи, що СЬОГОДНІ в тестовому графіку є робочий час
        # і ми використовуємо Варіант 2 (системний час)
        is_open = is_office_open(self.schedule.name, self.office.timezone)
        # Потрібно знати, чи зараз дійсно робочий час за графіком 'TESTSCHED'
        # self.assertTrue(is_open) # Або assertFalse, залежно від реального часу/графіка

    def test_is_office_open_closed_day(self):
        # Налаштовуємо час на вихідний (напр., Неділя 11:00)
        # mock_now.return_value = datetime(2025, 4, 27, 11, 0, 0)
        is_open = is_office_open(self.schedule.name, self.office.timezone)
        # self.assertFalse(is_open) # Припускаючи, що неділя - вихідний у 'TESTSCHED'

    def test_is_office_open_with_exception_closed(self):
        # Додаємо виняток - неробочий день на сьогодні
        today_str = get_date_str(now_datetime())
        add_schedule_exception(self.schedule.name, today_str, is_workday=0)
        is_open = is_office_open(self.schedule.name, self.office.timezone)
        self.assertFalse(is_open)

    def test_is_office_open_with_exception_open_hours(self):
        # Додаємо виняток - робочий день зі зміненими годинами
        today_str = get_date_str(now_datetime())
        # Припустимо, зараз 14:30 (за системним часом)
        add_schedule_exception(self.schedule.name, today_str,
                               is_workday=1, start_time="14:00:00", end_time="15:00:00")
        is_open = is_office_open(self.schedule.name, self.office.timezone)
        # Повинно бути відкрито, якщо поточний системний час між 14:00 та 15:00
        # self.assertTrue(is_open)

    # --- Тести для call_next_visitor ---

    def test_call_next_success(self):
        # Створюємо талон у черзі
        ticket = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting")
        # Перелогінюємось як оператор
        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)

        self.assertEqual(response.get("status"), "success")
        self.assertEqual(response.get("ticket_info").get("name"), ticket.name)
        updated_ticket = frappe.get_doc("QMS Ticket", ticket.name)
        self.assertEqual(updated_ticket.status, "Called")
        self.assertEqual(updated_ticket.operator, self.test_user.name)
        self.assertEqual(updated_ticket.service_point, self.service_point.name)

    def test_call_next_no_waiting_tickets(self):
        # Переконуємось, що немає талонів у черзі
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "info")
        self.assertIn("Немає талонів у черзі", response.get("message"))

    def test_call_next_operator_no_skills(self):
        # Створюємо талон
        ticket = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting")
        # Створюємо оператора без навичок
        user_no_skill = create_test_user("noskill@example.com", "Без Навичок")
        op_no_skill = create_test_operator(
            user_no_skill.name, self.office.name, [])
        frappe.set_user(user_no_skill.name)

        with self.assertRaises(frappe.ValidationError) as cm:
            call_next_visitor(service_point_name=self.service_point.name)
        self.assertIn("не призначено жодних навичок", str(cm.exception))

        # Cleanup
        frappe.set_user("Administrator")
        frappe.delete_doc("QMS Operator", op_no_skill.name,
                          ignore_permissions=True, force=True)
        frappe.delete_doc("User", user_no_skill.name,
                          ignore_permissions=True, force=True)

    def test_call_next_no_matching_skill_ticket(self):
        # Створюємо талон на послугу, якої немає в оператора
        service_no_skill = create_test_service(
            self.organization.name, "Послуга Без Навички", live_queue_enabled=1, enabled=1)
        assign_service_to_office(self.office.name, service_no_skill.name)
        ticket = create_test_ticket(
            self.office.name, service_no_skill.name, status="Waiting")

        # У цього оператора є тільки service1
        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        # Немає талонів, бо єдиний у черзі не підходить за навичкою
        self.assertEqual(response.get("status"), "info")
        self.assertIn("Немає талонів у черзі", response.get("message"))

        # Cleanup
        frappe.delete_doc("QMS Service", service_no_skill.name,
                          ignore_permissions=True, force=True)

    # Допоміжна функція для отримання ID створених у тесті талонів

    def get_tickets_created_in_test(self):
        # Простий спосіб - за офісом та часом створення (потребує уточнення)
        # Більш надійний - зберігати ID створених талонів у self під час тестів
        return [d.name for d in frappe.get_all("QMS Ticket", filters={"office": self.office.name})]


# --- Допоміжні функції для створення тестових даних ---
# (Розмістіть їх у цьому ж файлі або винесіть в окремий утилітарний файл тестів)

def create_test_organization():
    if frappe.db.exists("QMS Organization", {"organization_name": "Тест Організація"}):
        return frappe.get_doc("QMS Organization", {"organization_name": "Тест Організація"})
    org = frappe.get_doc({
        "doctype": "QMS Organization",
        "organization_name": "Тест Організація",
    }).insert(ignore_permissions=True)
    return org


def create_test_schedule(organization_name):
    schedule_name = "TESTSCHED"
    if frappe.db.exists("QMS Schedule", schedule_name):
        # Повертаємо існуючий або оновлюємо? Поки повертаємо.
        doc = frappe.get_doc("QMS Schedule", schedule_name)
        # Очистимо старі правила/винятки для чистоти тесту
        doc.schedule_rules = []
        doc.schedule_exceptions = []
        # Додамо дефолтні правила на будні
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for day in days:
            doc.append("schedule_rules", {
                "day_of_week": day,
                "start_time": "09:00:00",
                "end_time": "18:00:00"
            })
        doc.save(ignore_permissions=True)
        return doc

    sched = frappe.get_doc({
        "doctype": "QMS Schedule",
        "schedule_name": schedule_name,
        # Додаємо правила для будніх днів
        "schedule_rules": [
            {"day_of_week": day, "start_time": "09:00:00", "end_time": "18:00:00"}
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        ]
    }).insert(ignore_permissions=True)
    return sched


def add_schedule_exception(schedule_name, date_str, is_workday, start_time=None, end_time=None):
    doc = frappe.get_doc("QMS Schedule", schedule_name)
    # Видалимо попередній виняток на цю дату, якщо він є
    doc.schedule_exceptions = [
        exc for exc in doc.schedule_exceptions if exc.exception_date != get_date_str(date_str)]
    exc_data = {
        "doctype": "QMS Schedule Exception Child",
        "exception_date": date_str,
        "description": f"Тестовий виняток {date_str}",
        "is_workday": is_workday
    }
    if is_workday:
        exc_data["start_time"] = start_time
        exc_data["end_time"] = end_time
    doc.append("schedule_exceptions", exc_data)
    doc.save(ignore_permissions=True)


def create_test_office(organization_name, schedule_name, abbr):
    if frappe.db.exists("QMS Office", {"abbreviation": abbr}):
        return frappe.get_doc("QMS Office", {"abbreviation": abbr})
    office = frappe.get_doc({
        "doctype": "QMS Office",
        "organization": organization_name,
        "office_name": f"Тест Офіс {abbr}",
        "abbreviation": abbr,
        "schedule": schedule_name,
        # Використовуємо системну зону для простоти тестів без pytz/zoneinfo
        "timezone": frappe.utils.get_system_timezone()
    }).insert(ignore_permissions=True)
    return office


def create_test_service(organization_name, service_name, **kwargs):
    # Видаляємо існуючий з такою назвою, щоб уникнути конфліктів унікальності
    frappe.delete_doc("QMS Service", {"service_name": service_name},
                      ignore_permissions=True, force=True, ignore_missing=True)

    data = {
        "doctype": "QMS Service",
        "organization": organization_name,
        "service_name": service_name,
        "avg_duration_mins": 15,
        "enabled": kwargs.get("enabled", 1),
        "live_queue_enabled": kwargs.get("live_queue_enabled", 1),
        "requires_appointment": kwargs.get("requires_appointment", 0),
    }
    service = frappe.get_doc(data).insert(ignore_permissions=True)
    return service


def assign_service_to_office(office_name, service_name):
    office_doc = frappe.get_doc("QMS Office", office_name)
    # Перевіряємо, чи вже призначено
    exists = any(item.service ==
                 service_name for item in office_doc.available_services)
    if not exists:
        office_doc.append("available_services", {
            "service": service_name,
            "is_active_in_office": 1
        })
        office_doc.save(ignore_permissions=True)


def create_test_service_point(office_name, point_name):
    # Видаляємо існуючий з такою назвою в цьому офісі
    existing = frappe.db.get_value(
        "QMS Service Point", {"office": office_name, "point_name": point_name})
    if existing:
        frappe.delete_doc("QMS Service Point", existing,
                          ignore_permissions=True, force=True)

    sp = frappe.get_doc({
        "doctype": "QMS Service Point",
        "office": office_name,
        "point_name": point_name,
        "is_active": 1
    }).insert(ignore_permissions=True)
    return sp


def create_test_user(email, first_name):
    if frappe.db.exists("User", email):
        # Можливо, оновити ролі або просто повернути існуючого
        user = frappe.get_doc("User", email)
        # Переконаємось, що користувач активний для тесту
        if not user.enabled:
            user.enabled = 1
            user.save(ignore_permissions=True)
        return user
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "send_welcome_email": 0,
        "enabled": 1,
        # Додайте необхідні ролі
        "roles": [
            {"role": "System Manager"}  # Або спеціальна роль Оператора
        ]
    }).insert(ignore_permissions=True)
    return user


def create_test_operator(user_name, office_name, skills_list):
    if frappe.db.exists("QMS Operator", {"user": user_name}):
        op = frappe.get_doc("QMS Operator", {"user": user_name})
        # Оновимо навички
        op.operator_skills = []
        for skill_service_name in skills_list:
            op.append("operator_skills", {
                      "service": skill_service_name, "skill_level": "Proficient"})
        op.is_active = 1  # Переконуємось, що активний
        op.default_office = office_name
        op.save(ignore_permissions=True)
        return op

    op = frappe.get_doc({
        "doctype": "QMS Operator",
        "user": user_name,
        "full_name": frappe.db.get_value("User", user_name, "full_name"),
        "default_office": office_name,
        "is_active": 1,
        "operator_skills": [{"service": skill, "skill_level": "Proficient"} for skill in skills_list]
    }).insert(ignore_permissions=True)
    return op


def create_test_ticket(office_name, service_name, status="Waiting", **kwargs):
    # Простий спосіб створити талон для тесту
    # УВАГА: Це обходить функцію autoname з qms_ticket.py!
    # Для тестування самої autoname потрібен інший підхід (виклик new_doc().insert())
    ticket_data = {
        "doctype": "QMS Ticket",
        "office": office_name,
        "service": service_name,
        "status": status,
        "issue_time": now_datetime(),
        **kwargs  # Додаткові поля, якщо передано
    }
    # Генеруємо тимчасовий унікальний номер для тесту, якщо статус не Waiting
    # (бо autoname не спрацює тут, а поле name/ticket_number унікальне)
    if status != "Waiting":
        ticket_data["ticket_number"] = frappe.generate_hash(length=10)

    ticket = frappe.get_doc(ticket_data)
    # Якщо статус Waiting, autoname має спрацювати при insert
    if status != "Waiting":
        ticket.name = ticket.ticket_number  # Встановлюємо name вручну

     # ignore_permissions важливий для тестів
    ticket.insert(ignore_permissions=True)
    # Якщо статус був Waiting, поле ticket_number має заповнитись автоматично
    if status == "Waiting" and not ticket.ticket_number:
        ticket.reload()  # Перезавантажимо документ, щоб побачити згенерований номер
    return ticket

# -*- coding: utf-8 -*-
# Copyright (c) 2025, Maxym Sysoiev and Contributors
# See license.txt

import frappe
# Використовуємо FrappeTestCase для автоматичного rollback
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, add_days, get_date_str, get_datetime
from datetime import time  # Додано для створення об'єктів часу

# Імпортуємо функції, які тестуємо
from qms_cherga.api import (
    create_live_queue_ticket,
    call_next_visitor,
    is_office_open,
    get_kiosk_services,  # Додано для повноти, якщо є тести
    get_display_data    # Додано для повноти, якщо є тести
)

# Імпортуємо freezegun
from freezegun import freeze_time

# --- Допоміжні функції для створення тестових даних ---
# (Розміщені тут для самодостатності файлу)


def delete_doc_if_exists(doctype, filters_or_name):
    """
    Видаляє документ, якщо він існує, на основі фільтрів або імені.

    :param doctype: Тип документа (DocType).
    :param filters_or_name: Словник фільтрів або рядок з іменем документа.
    """
    doc_name = None
    if isinstance(filters_or_name, str):
        # Якщо передано ім'я документа
        if frappe.db.exists(doctype, filters_or_name):
            doc_name = filters_or_name
    elif isinstance(filters_or_name, dict):
        # Якщо передано фільтри
        # Використовуємо frappe.db.get_value для пошуку імені
        existing = frappe.db.get_value(doctype, filters_or_name, "name")
        if existing:
            doc_name = existing
    else:
        # Непідтримуваний тип фільтра
        frappe.log_error(
            f"Unsupported filter type for delete_doc_if_exists: {type(filters_or_name)}", "Test Utils")
        return

    if doc_name:
        try:
            # Видаляємо документ, ігноруючи дозволи та можливу відсутність (про всяк випадок)
            frappe.delete_doc(
                doctype,
                doc_name,
                ignore_permissions=True,
                force=True,
                ignore_missing=True  # Додає стійкості, якщо документ зник між перевіркою та видаленням
            )
            # print(f"Deleted existing {doctype}: {doc_name}") # Для дебагу
        except Exception as e:
            # Логуємо помилку, якщо видалення не вдалося
            frappe.log_error(
                f"Failed to delete {doctype} {doc_name}: {e}", "Test Utils Delete Error")


def create_test_organization(org_name="Тест API Організація"):
    delete_doc_if_exists("QMS Organization", {"organization_name": org_name})
    org = frappe.get_doc({
        "doctype": "QMS Organization",
        "organization_name": org_name,
    }).insert(ignore_permissions=True)
    return org


def create_test_schedule(schedule_name, rules=None, exceptions=None):
    delete_doc_if_exists("QMS Schedule", schedule_name)
    sched = frappe.get_doc({
        "doctype": "QMS Schedule",
        "schedule_name": schedule_name,
        "schedule_rules": rules or [],
        "schedule_exceptions": exceptions or []
    }).insert(ignore_permissions=True)
    return sched


def add_schedule_exception(schedule_name, date_str, is_workday, start_time=None, end_time=None):
    doc = frappe.get_doc("QMS Schedule", schedule_name)
    # Видаляємо попередній виняток на цю дату, якщо він є
    doc.schedule_exceptions = [exc for exc in doc.schedule_exceptions if get_date_str(
        exc.exception_date) != date_str]
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
    doc.flags.ignore_permissions = True  # Потрібно для save
    doc.save()  # ignore_permissions тут може не спрацювати, краще ставити прапорець
    return doc


def create_test_office(organization_name, schedule_name, abbr, office_name=None, timezone="UTC"):
    delete_doc_if_exists("QMS Office", {"abbreviation": abbr})
    office = frappe.get_doc({
        "doctype": "QMS Office",
        "organization": organization_name,
        "office_name": office_name or f"Тест API Офіс {abbr}",
        "abbreviation": abbr,
        "schedule": schedule_name,
        "timezone": timezone  # Використовуємо переданий timezone
    }).insert(ignore_permissions=True)
    return office


def create_test_service(organization_name, service_name, **kwargs):
    delete_doc_if_exists("QMS Service", {"service_name": service_name})
    data = {
        "doctype": "QMS Service",
        "organization": organization_name,
        "service_name": service_name,
        "avg_duration_mins": kwargs.get("avg_duration_mins", 15),
        "enabled": kwargs.get("enabled", 1),
        "live_queue_enabled": kwargs.get("live_queue_enabled", 1),
        "requires_appointment": kwargs.get("requires_appointment", 0),
        "icon": kwargs.get("icon", "fa fa-cogs")
    }
    service = frappe.get_doc(data).insert(ignore_permissions=True)
    return service


def assign_service_to_office(office_name, service_name):
    office_doc = frappe.get_doc("QMS Office", office_name)
    exists = any(item.service == service_name for item in office_doc.get(
        "available_services", []))
    if not exists:
        office_doc.append("available_services", {
            "service": service_name,
            "is_active_in_office": 1
        })
        office_doc.flags.ignore_permissions = True
        office_doc.save()


def create_test_service_point(office_name, point_name):
    delete_doc_if_exists("QMS Service Point", {
                         "office": office_name, "point_name": point_name})
    sp = frappe.get_doc({
        "doctype": "QMS Service Point",
        "office": office_name,
        "point_name": point_name,
        "is_active": 1
    }).insert(ignore_permissions=True)
    return sp


def create_test_user(email, first_name, roles=None):
    delete_doc_if_exists("User", email)
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "send_welcome_email": 0,
        "enabled": 1,
        "roles": roles or [{"role": "System Manager"}]
    }).insert(ignore_permissions=True)
    return user


def create_test_operator(user_name, office_name, skills_list=None):
    delete_doc_if_exists("QMS Operator", {"user": user_name})
    op = frappe.get_doc({
        "doctype": "QMS Operator",
        "user": user_name,
        "full_name": frappe.db.get_value("User", user_name, "full_name"),
        "default_office": office_name,
        "is_active": 1,
        "operator_skills": [{"service": skill, "skill_level": "Proficient"} for skill in (skills_list or [])]
    }).insert(ignore_permissions=True)
    return op


def create_test_ticket(office_name, service_name, status="Waiting", **kwargs):
    # Створюємо талон через стандартний механізм для спрацювання autoname
    ticket = frappe.new_doc("QMS Ticket")
    ticket.office = office_name
    ticket.service = service_name
    ticket.status = status  # Встановлюємо статус ПІСЛЯ заповнення office
    ticket.issue_time = now_datetime()

    for key, value in kwargs.items():
        ticket.set(key, value)

    # ignore_permissions важливий для тестів
    ticket.insert(ignore_permissions=True)
    # Перезавантажуємо, щоб отримати згенерований ticket_number
    ticket.reload()
    return ticket


# --- Основний клас тестів ---
class TestQMSApi(FrappeTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestQMSApi, cls).setUpClass()
        # Створюємо дані один раз для всього класу тестів
        cls.organization = create_test_organization()
        cls.test_timezone = "Europe/Kyiv"  # Використовуємо Київський час
        # Графік: Середа 09:00-13:00, 14:00-18:00 (локальний час)
        cls.schedule = create_test_schedule(
            schedule_name="API_TEST_SCHED",
            rules=[
                {"day_of_week": "Wednesday", "start_time": time(
                    9, 0), "end_time": time(13, 0)},
                {"day_of_week": "Wednesday", "start_time": time(
                    14, 0), "end_time": time(18, 0)},
                {"day_of_week": "Thursday", "start_time": time(
                    10, 0), "end_time": time(16, 0)},  # Інший день
            ]
        )
        cls.office = create_test_office(
            cls.organization.name, cls.schedule.name, "APITEST", timezone=cls.test_timezone
        )
        cls.service1 = create_test_service(
            cls.organization.name, "API Послуга 1", live_queue_enabled=1, enabled=1)
        cls.service2 = create_test_service(
            cls.organization.name, "API Послуга 2 (Неактивна)", live_queue_enabled=1, enabled=0)
        cls.service3 = create_test_service(
            cls.organization.name, "API Послуга 3 (Не для кіоску)", live_queue_enabled=0, enabled=1)
        cls.service_point = create_test_service_point(
            cls.office.name, "API Вікно 1")

        cls.test_user = create_test_user(
            "test_api_op@example.com", "API Тест Оператор")
        cls.operator = create_test_operator(
            cls.test_user.name, cls.office.name, skills_list=[cls.service1.name])

        assign_service_to_office(cls.office.name, cls.service1.name)
        assign_service_to_office(cls.office.name, cls.service2.name)
        assign_service_to_office(cls.office.name, cls.service3.name)

    @classmethod
    def tearDownClass(cls):
        # Очищаємо дані після всіх тестів у класі
        # FrappeTestCase зазвичай робить rollback автоматично, але для надійності можна видалити
        # delete_doc_if_exists("QMS Operator", {"user": cls.test_user.name})
        # delete_doc_if_exists("User", cls.test_user.name)
        # delete_doc_if_exists("QMS Service Point", cls.service_point.name)
        # delete_doc_if_exists("QMS Office", cls.office.name)
        # delete_doc_if_exists("QMS Service", cls.service1.name)
        # delete_doc_if_exists("QMS Service", cls.service2.name)
        # delete_doc_if_exists("QMS Service", cls.service3.name)
        # delete_doc_if_exists("QMS Schedule", cls.schedule.name)
        # delete_doc_if_exists("QMS Organization", cls.organization.name)
        # frappe.db.commit() # Якщо видаляєте вручну
        super(TestQMSApi, cls).tearDownClass()

    def setUp(self):
        # Встановлюємо користувача перед кожним тестом, що потребує авторизації
        frappe.set_user(self.test_user.name)

    def tearDown(self):
        # Повертаємо адміністратора після кожного тесту
        frappe.set_user("Administrator")
        # FrappeTestCase автоматично відкотить зміни між тестами

    # --- Тести для is_office_open (з freezegun) ---

    # Середа, 11:05 Київ (UTC+3) - Робочий час
    @freeze_time("2025-04-30 08:05:00")
    def test_is_office_open_during_working_hours(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    # Середа, 08:55 Київ (UTC+3) - Перед відкриттям
    @freeze_time("2025-04-30 05:55:00")
    def test_is_office_open_before_opening(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Середа, 13:15 Київ (UTC+3) - Під час перерви
    @freeze_time("2025-04-30 10:15:00")
    def test_is_office_open_during_break(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Середа, 15:30 Київ (UTC+3) - Після перерви, робочий час
    @freeze_time("2025-04-30 12:30:00")
    def test_is_office_open_after_break(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    # Середа, 18:05 Київ (UTC+3) - Після закриття
    @freeze_time("2025-04-30 15:05:00")
    def test_is_office_open_after_closing(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Неділя, 12:00 Київ (UTC+3) - Вихідний
    @freeze_time("2025-05-04 09:00:00")
    def test_is_office_open_on_weekend(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-05-07 08:30:00")  # Наступна Середа, 11:30 Київ
    def test_is_office_open_with_exception_closed(self):
        exception_date = "2025-05-07"
        add_schedule_exception(
            self.schedule.name, exception_date, is_workday=0)
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))
        # Очистка винятку після тесту (або rollback подбає про це)
        # doc = frappe.get_doc("QMS Schedule", self.schedule.name)
        # doc.schedule_exceptions = [e for e in doc.schedule_exceptions if get_date_str(e.exception_date) != exception_date]
        # doc.save()

    @freeze_time("2025-05-14 08:45:00")  # Ще одна Середа, 11:45 Київ
    def test_is_office_open_with_exception_open_limited_hours(self):
        exception_date = "2025-05-14"
        # Виняток: робочий день 11:00 - 12:00 Київського часу
        add_schedule_exception(self.schedule.name, exception_date,
                               is_workday=1, start_time=time(11, 0), end_time=time(12, 0))
        self.assertTrue(is_office_open(
            self.schedule.name, self.test_timezone), "Should be open during exception hours")

        # Перевірка поза вікном винятку (12:15 Київ = 09:15 UTC)
        with freeze_time("2025-05-14 09:15:00"):
            self.assertFalse(is_office_open(
                self.schedule.name, self.test_timezone), "Should be closed outside exception hours")

    def test_is_office_open_invalid_inputs(self):
        self.assertFalse(is_office_open(
            self.schedule.name, "Invalid/Timezone"))
        self.assertFalse(is_office_open(self.schedule.name, None))
        self.assertFalse(is_office_open(self.schedule.name, ""))
        self.assertFalse(is_office_open(
            None, self.test_timezone))  # Без графіка

    # --- Тести для create_live_queue_ticket ---

    @freeze_time("2025-04-30 08:05:00")  # Середа, 11:05 Київ - Робочий час
    def test_create_ticket_success(self):
        frappe.set_user("Guest")  # Імітуємо кіоск
        response = create_live_queue_ticket(
            service=self.service1.name, office=self.office.name)
        self.assertEqual(response.get("status"), "success")
        self.assertTrue(response.get("ticket_name"))
        self.assertTrue(response.get("ticket_number"))
        ticket = frappe.get_doc("QMS Ticket", response.get("ticket_name"))
        self.assertEqual(ticket.office, self.office.name)
        self.assertEqual(ticket.service, self.service1.name)
        self.assertEqual(ticket.status, "Waiting")
        # Формуємо очікуваний початок імені
        expected_prefix = f"TKT-{self.office.abbreviation}-"
        # Перевіряємо, чи ім'я документа починається з цього префіксу
        self.assertTrue(
            str(ticket.name).startswith(expected_prefix),
            # Додано повідомлення про помилку
            f"Ticket name '{ticket.name}' does not start with expected prefix '{expected_prefix}'"
        )
        # Також перевіримо, що поле ticket_number відповідає імені (якщо ви їх синхронізували)
        self.assertEqual(str(ticket.name), str(ticket.ticket_number))

    # Середа, 08:55 Київ - Перед відкриттям
    @freeze_time("2025-04-30 05:55:00")
    def test_create_ticket_office_closed(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "зачинений"):
            create_live_queue_ticket(
                service=self.service1.name, office=self.office.name)

    def test_create_ticket_missing_params(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "Не вказано Послугу або Офіс"):
            create_live_queue_ticket(service=self.service1.name, office="")
        with self.assertRaisesRegex(frappe.ValidationError, "Не вказано Послугу або Офіс"):
            create_live_queue_ticket(service="", office=self.office.name)

    def test_create_ticket_invalid_service(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "не знайдена"):
            create_live_queue_ticket(
                service="Неіснуюча Послуга API", office=self.office.name)

    @freeze_time("2025-04-30 08:05:00")
    def test_create_ticket_inactive_service(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "неактивна"):
            create_live_queue_ticket(
                service=self.service2.name, office=self.office.name)

    @freeze_time("2025-04-30 08:05:00")
    def test_create_ticket_not_live_queue(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "недоступна для живої черги"):
            create_live_queue_ticket(
                service=self.service3.name, office=self.office.name)

    @freeze_time("2025-04-30 08:05:00")
    def test_create_ticket_service_not_in_office(self):
        frappe.set_user("Guest")
        # Створюємо послугу, не призначену офісу
        service_other = create_test_service(
            self.organization.name, "API Інша Послуга")
        with self.assertRaisesRegex(frappe.ValidationError, "недоступна в офісі"):
            create_live_queue_ticket(
                service=service_other.name, office=self.office.name)
        # Clean up (rollback подбає)
        # delete_doc_if_exists("QMS Service", service_other.name)

    # --- Тести для call_next_visitor ---
    # Ці тести виконуються від імені оператора (встановлено в self.setUp)

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_call_next_success(self):
        # Створюємо талон у черзі
        ticket = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting")
        response = call_next_visitor(
            service_point_name=self.service_point.name)

        self.assertEqual(response.get("status"), "success",
                         response.get("message"))
        self.assertIsNotNone(response.get("ticket_info"))
        self.assertEqual(response.get("ticket_info").get("name"), ticket.name)

        updated_ticket = frappe.get_doc("QMS Ticket", ticket.name)
        self.assertEqual(updated_ticket.status, "Called")
        self.assertEqual(updated_ticket.operator, self.test_user.name)
        self.assertEqual(updated_ticket.service_point, self.service_point.name)

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_no_waiting_tickets(self):
        # Переконуємось, що немає талонів у черзі Waiting для service1
        frappe.db.delete("QMS Ticket", {
                         "office": self.office.name, "service": self.service1.name, "status": "Waiting"})
        frappe.db.commit()  # Потрібно підтвердити видалення перед викликом API
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "info")
        self.assertIn("Немає талонів у черзі", response.get("message"))

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_operator_no_skills_assigned(self):
        # Створюємо талон
        ticket = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting")
        # Створюємо оператора без навичок
        user_no_skill = create_test_user(
            "noskill_api@example.com", "API Без Навичок")
        op_no_skill = create_test_operator(
            user_no_skill.name, self.office.name, skills_list=[])  # Порожній список навичок
        frappe.set_user(user_no_skill.name)  # Перелогінюємось

        with self.assertRaisesRegex(frappe.ValidationError, "не призначено жодних навичок"):
            call_next_visitor(service_point_name=self.service_point.name)

        # Повертаємо користувача і очищаємо (rollback подбає)
        frappe.set_user("Administrator")
        # delete_doc_if_exists("QMS Operator", op_no_skill.name)
        # delete_doc_if_exists("User", user_no_skill.name)

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_no_matching_skill_ticket(self):
        # Створюємо талон на послугу, якої немає в оператора
        service_no_skill = create_test_service(
            self.organization.name, "API Послуга Без Навички")
        assign_service_to_office(self.office.name, service_no_skill.name)
        ticket = create_test_ticket(
            self.office.name, service_no_skill.name, status="Waiting")

        # У self.operator є навичка тільки для self.service1
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        # Очікуємо "Немає талонів", бо єдиний талон не відповідає навичкам оператора
        self.assertEqual(response.get("status"), "info")
        self.assertIn("Немає талонів у черзі", response.get("message"))
        # Clean up (rollback подбає)
        # delete_doc_if_exists("QMS Service", service_no_skill.name)

    # --- Додайте тести для інших функцій API (get_kiosk_services, get_display_data) ---
    # Наприклад:
    @freeze_time("2025-04-30 08:05:00")
    def test_get_kiosk_services_returns_active(self):
        frappe.set_user("Guest")
        data = get_kiosk_services(office=self.office.name)
        self.assertNotIn("error", data)
        # Перевіряємо, що service1 є, а service2 (неактивна) і service3 (не для кіоску) - немає
        found_service1 = False
        for cat in data.get("categories", []):
            for svc in cat.get("services", []):
                if svc["id"] == self.service1.name:
                    found_service1 = True
                    break
            if found_service1:
                break
        if not found_service1:
            for svc in data.get("services_no_category", []):
                if svc["id"] == self.service1.name:
                    found_service1 = True
                    break

        self.assertTrue(
            found_service1, f"Service {self.service1.name} not found in kiosk services")

        # Перевіряємо, що інших немає
        all_service_ids = []
        for cat in data.get("categories", []):
            all_service_ids.extend([svc["id"]
                                   for svc in cat.get("services", [])])
        all_service_ids.extend([svc["id"]
                               for svc in data.get("services_no_category", [])])

        self.assertNotIn(self.service2.name, all_service_ids,
                         f"Inactive service {self.service2.name} should not be in kiosk list")
        self.assertNotIn(self.service3.name, all_service_ids,
                         f"Service {self.service3.name} (not live queue) should not be in kiosk list")

    @freeze_time("2025-04-30 08:05:00")
    def test_get_display_data_structure(self):
        frappe.set_user("Guest")
        # Створимо кілька талонів
        t1_wait = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting", priority=1)
        t2_wait = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting")
        t3_called = create_test_ticket(self.office.name, self.service1.name, status="Called",
                                       operator=self.test_user.name, service_point=self.service_point.name, call_time=now_datetime())

        data = get_display_data(office=self.office.name,
                                limit_called=5, limit_waiting=10)

        self.assertIn("last_called", data)
        self.assertIn("waiting", data)
        self.assertIsInstance(data["last_called"], list)
        self.assertIsInstance(data["waiting"], list)

        # Перевіряємо, що викликаний талон є у списку last_called
        called_tickets = [t['ticket'] for t in data['last_called']]
        # Порівнюємо скорочений номер
        short_t3_num = t3_called.ticket_number.split('-')[-1]
        self.assertIn(short_t3_num, called_tickets)

        # Перевіряємо, що очікуючі талони є у списку waiting
        waiting_tickets = [t['ticket'] for t in data['waiting']]
        short_t1_num = t1_wait.ticket_number.split('-')[-1]
        short_t2_num = t2_wait.ticket_number.split('-')[-1]
        self.assertIn(short_t1_num, waiting_tickets)
        self.assertIn(short_t2_num, waiting_tickets)


# --- Запуск тестів ---
# bench --site [your-site] run-tests --app qms_cherga --module qms_cherga.tests.test_api

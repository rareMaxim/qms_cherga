# -*- coding: utf-8 -*-
# Copyright (c) 2025, Maxym Sysoiev and Contributors
# See license.txt

import uuid
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, add_days, get_date_str, get_datetime
from datetime import time
from freezegun import freeze_time

# Імпортуємо функції, які тестуємо
from qms_cherga.api import (
    create_live_queue_ticket,
    call_next_visitor,
    is_office_open,
    get_kiosk_services,
    get_display_data
)

# --- Допоміжні функції для створення тестових даних (Крок 1: Прибрано delete_doc_if_exists) ---

# Функція для безпечного видалення документів (використовується в tearDownClass)


def safe_delete_doc(doctype, name):
    try:
        frappe.delete_doc(
            doctype,
            name,
            ignore_permissions=True,
            force=True,
            ignore_missing=True  # Додає стійкості
        )
    except Exception as e:
        # Логуємо помилку, якщо видалення не вдалося
        frappe.log_error(
            f"Failed to delete {doctype} {name} during teardown: {e}", "Test Cleanup Error")


def create_test_organization(org_name="Тест API Організація"):
    # Видалення тут більше не потрібне, якщо викликається тільки з setUpClass
    # delete_doc_if_exists("QMS Organization", {"organization_name": org_name})
    org = frappe.get_doc({
        "doctype": "QMS Organization",
        "organization_name": org_name,
    }).insert(ignore_permissions=True)
    return org


def create_test_schedule(schedule_name, rules=None, exceptions=None):
    # delete_doc_if_exists("QMS Schedule", schedule_name) # Видалення не потрібне
    sched = frappe.get_doc({
        "doctype": "QMS Schedule",
        "schedule_name": schedule_name,
        "schedule_rules": rules or [],
        "schedule_exceptions": exceptions or []
    }).insert(ignore_permissions=True)
    return sched


def add_schedule_exception(schedule_name, date_str, is_workday, start_time=None, end_time=None):
    # Ця функція модифікує існуючий документ, rollback має подбати про це
    doc = frappe.get_doc("QMS Schedule", schedule_name)
    # Перезаписуємо винятки коректно
    current_exceptions = doc.get("schedule_exceptions", [])
    new_exceptions = [exc for exc in current_exceptions if get_date_str(
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
    new_exceptions.append(exc_data)
    # Використовуємо set для оновлення таблиці
    doc.set("schedule_exceptions", new_exceptions)
    doc.flags.ignore_permissions = True
    doc.save()
    return doc


def create_test_office(organization_name, schedule_name, abbr, office_name=None, timezone="UTC"):
    # delete_doc_if_exists("QMS Office", {"abbreviation": abbr}) # Видалення не потрібне
    office = frappe.get_doc({
        "doctype": "QMS Office",
        "organization": organization_name,
        "office_name": office_name or f"Тест API Офіс {abbr}",
        "abbreviation": abbr,
        "schedule": schedule_name,
        "timezone": timezone
    }).insert(ignore_permissions=True)
    return office


def create_test_service(organization_name, service_name, **kwargs):
    # delete_doc_if_exists("QMS Service", {"service_name": service_name}) # Видалення не потрібне
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
    # Ця функція модифікує існуючий документ, rollback має подбати про це
    office_doc = frappe.get_doc("QMS Office", office_name)
    # Використовуємо get для безпечного доступу
    current_services = office_doc.get("available_services", [])
    exists = any(item.service == service_name for item in current_services)
    if not exists:
        office_doc.append("available_services", {
            "service": service_name,
            "is_active_in_office": 1
        })
        office_doc.flags.ignore_permissions = True
        office_doc.save()


def create_test_service_point(office_name, point_name):
    # delete_doc_if_exists("QMS Service Point", {"office": office_name, "point_name": point_name}) # Видалення не потрібне
    sp = frappe.get_doc({
        "doctype": "QMS Service Point",
        "office": office_name,
        "point_name": point_name,
        "is_active": 1
    }).insert(ignore_permissions=True)
    return sp


def create_test_user(email, first_name, roles=None):
    # delete_doc_if_exists("User", email) # Видалення не потрібне
    user = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
        "send_welcome_email": 0,
        "enabled": 1,
        "roles": roles or [{"role": "System Manager"}]  # Або інша базова роль
    }).insert(ignore_permissions=True)
    return user


def create_test_operator(user_name, office_name, skills_list=None):
    # delete_doc_if_exists("QMS Operator", {"user": user_name}) # Видалення не потрібне
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
    # Rollback подбає про видалення талонів, створених у тестах
    ticket = frappe.new_doc("QMS Ticket")
    ticket.office = office_name
    ticket.service = service_name
    ticket.status = status
    ticket.issue_time = now_datetime()
    for key, value in kwargs.items():
        ticket.set(key, value)
    ticket.insert(ignore_permissions=True)
    ticket.reload()  # Щоб отримати згенеровані поля, як name
    return ticket

# --- Основний клас тестів ---


class TestQMSApi(FrappeTestCase):

    # Зберігаємо імена створених у setUpClass записів для очищення
    created_docs = []

    @classmethod
    def setUpClass(cls):
        super(TestQMSApi, cls).setUpClass()
        # Створюємо дані один раз для всього класу тестів
        # Використовуємо try...finally для гарантованого додавання до списку на видалення
        try:
            cls.organization = create_test_organization()
            cls.created_docs.append(
                ("QMS Organization", cls.organization.name))

            cls.test_timezone = "Europe/Kyiv"
            cls.schedule = create_test_schedule(
                schedule_name="API_TEST_SCHED",
                rules=[
                    {"day_of_week": "Wednesday", "start_time": time(
                        9, 0), "end_time": time(13, 0)},
                    {"day_of_week": "Wednesday", "start_time": time(
                        14, 0), "end_time": time(18, 0)},
                    {"day_of_week": "Thursday", "start_time": time(
                        10, 0), "end_time": time(16, 0)},
                ]
            )
            cls.created_docs.append(("QMS Schedule", cls.schedule.name))

            cls.office = create_test_office(
                cls.organization.name, cls.schedule.name, "APITEST", timezone=cls.test_timezone
            )
            # Використовуємо name (який = abbreviation)
            cls.created_docs.append(("QMS Office", cls.office.name))

            cls.service1 = create_test_service(
                cls.organization.name, "API Послуга 1", live_queue_enabled=1, enabled=1)
            cls.created_docs.append(("QMS Service", cls.service1.name))
            cls.service2 = create_test_service(
                cls.organization.name, "API Послуга 2 (Неактивна)", live_queue_enabled=1, enabled=0)
            cls.created_docs.append(("QMS Service", cls.service2.name))
            cls.service3 = create_test_service(
                cls.organization.name, "API Послуга 3 (Не для кіоску)", live_queue_enabled=0, enabled=1)
            cls.created_docs.append(("QMS Service", cls.service3.name))

            cls.service_point = create_test_service_point(
                cls.office.name, "API Вікно 1")
            cls.created_docs.append(
                ("QMS Service Point", cls.service_point.name))

            cls.test_user = create_test_user(
                "test_api_op@example.com", "API Тест Оператор")
            # Користувача теж треба видаляти
            cls.created_docs.append(("User", cls.test_user.name))

            cls.operator = create_test_operator(
                cls.test_user.name, cls.office.name, skills_list=[cls.service1.name])
            cls.created_docs.append(("QMS Operator", cls.operator.name))

            assign_service_to_office(cls.office.name, cls.service1.name)
            assign_service_to_office(cls.office.name, cls.service2.name)
            assign_service_to_office(cls.office.name, cls.service3.name)

            # Важливо: commit потрібен після setUpClass, щоб дані були доступні для всіх тестів
            frappe.db.commit()

        except Exception:
            # Якщо щось пішло не так під час сетапу, намагаємось очистити вже створене
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        # Явно видаляємо всі документи, створені в setUpClass, у зворотному порядку
        # Використовуємо збережений список cls.created_docs
        if hasattr(cls, 'created_docs'):
            for doctype, name in reversed(cls.created_docs):
                safe_delete_doc(doctype, name)
            cls.created_docs = []  # Очищуємо список

        frappe.db.commit()  # Застосовуємо видалення
        super(TestQMSApi, cls).tearDownClass()

    def setUp(self):
        # Встановлюємо користувача перед кожним тестом
        frappe.set_user(self.test_user.name)
        # Rollback подбає про очищення даних, створених *всередині* тесту

    def tearDown(self):
        # Повертаємо адміністратора після кожного тесту
        frappe.set_user("Administrator")
        # Не потрібно нічого видаляти тут, rollback зробить свою справу

    # --- Тести для is_office_open (з freezegun) ---

    # Середа, 11:05 Київ (UTC+3) - Робочий час
    @freeze_time("2025-04-30 08:05:00")  # 11:05 Kyiv = 08:05 UTC
    def test_is_office_open_during_working_hours(self):
        # УВАГА: Цей тест залежить від коректності реалізації is_office_open з часовими зонами
        # Поточна реалізація в api.py може ігнорувати timezone.
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    # Середа, 08:55 Київ (UTC+3) - Перед відкриттям
    @freeze_time("2025-04-30 05:55:00")  # 08:55 Kyiv = 05:55 UTC
    def test_is_office_open_before_opening(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Середа, 13:15 Київ (UTC+3) - Під час перерви
    @freeze_time("2025-04-30 10:15:00")  # 13:15 Kyiv = 10:15 UTC
    def test_is_office_open_during_break(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Середа, 15:30 Київ (UTC+3) - Після перерви, робочий час
    @freeze_time("2025-04-30 12:30:00")  # 15:30 Kyiv = 12:30 UTC
    def test_is_office_open_after_break(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    # Середа, 18:05 Київ (UTC+3) - Після закриття
    @freeze_time("2025-04-30 15:05:00")  # 18:05 Kyiv = 15:05 UTC
    def test_is_office_open_after_closing(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Неділя, 12:00 Київ (UTC+3) - Вихідний
    @freeze_time("2025-05-04 09:00:00")  # 12:00 Kyiv = 09:00 UTC
    def test_is_office_open_on_weekend(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Тест на точний час відкриття (09:00 Київ) - Має бути відкрито
    @freeze_time("2025-04-30 06:00:00")  # 09:00 Kyiv = 06:00 UTC
    def test_is_office_open_at_opening_time(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    # Тест на точний час закриття (18:00 Київ) - Має бути ЗАКРИТО (бо < end_time)
    @freeze_time("2025-04-30 15:00:00")  # 18:00 Kyiv = 15:00 UTC
    def test_is_office_open_at_closing_time(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Тест на точний час початку перерви (13:00 Київ) - Має бути ЗАКРИТО
    @freeze_time("2025-04-30 10:00:00")  # 13:00 Kyiv = 10:00 UTC
    def test_is_office_open_at_break_start_time(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    # Тест на точний час кінця перерви (14:00 Київ) - Має бути ВІДКРИТО
    @freeze_time("2025-04-30 11:00:00")  # 14:00 Kyiv = 11:00 UTC
    def test_is_office_open_at_break_end_time(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    @freeze_time("2025-05-07 08:30:00")  # Наступна Середа, 11:30 Київ
    def test_is_office_open_with_exception_closed(self):
        exception_date = "2025-05-07"
        # Додаємо виняток всередині тесту, rollback його видалить
        add_schedule_exception(
            self.schedule.name, exception_date, is_workday=0)
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-05-14 08:45:00")  # Ще одна Середа, 11:45 Київ
    def test_is_office_open_with_exception_open_limited_hours(self):
        exception_date = "2025-05-14"
        add_schedule_exception(self.schedule.name, exception_date,
                               is_workday=1, start_time=time(11, 0), end_time=time(12, 0))  # 11:00-12:00 Kyiv
        # Перевірка часу всередині винятку (11:45 Київ = 08:45 UTC)
        self.assertTrue(is_office_open(
            self.schedule.name, self.test_timezone), "Should be open during exception hours")

        # Перевірка поза вікном винятку (12:15 Київ = 09:15 UTC)
        with freeze_time("2025-05-14 09:15:00"):
            self.assertFalse(is_office_open(
                self.schedule.name, self.test_timezone), "Should be closed outside exception hours")

    def test_is_office_open_invalid_inputs(self):
        # Перевіряємо, що функція коректно обробляє невалідну часову зону
        # Поточна реалізація поверне False через fallback на системний час і можливу помилку zoneinfo
        # Якщо реалізація буде покращена, цей тест може потребувати оновлення.
        self.assertFalse(is_office_open(
            self.schedule.name, "Invalid/Timezone"))
        self.assertFalse(is_office_open(self.schedule.name, None))
        self.assertFalse(is_office_open(self.schedule.name, ""))
        self.assertFalse(is_office_open(
            None, self.test_timezone))  # Без графіка

    # --- Тести для create_live_queue_ticket ---

    @freeze_time("2025-04-30 08:05:00")  # Робочий час (11:05 Київ)
    def test_create_ticket_success(self):
        initial_counter = frappe.db.get_value("QMS Daily Counter", {
                                              "office": self.office.name, "date": get_date_str(now_datetime())}, "last_number") or 0

        frappe.set_user("Guest")  # Імітуємо кіоск
        response = create_live_queue_ticket(
            service=self.service1.name, office=self.office.name)
        self.assertEqual(response.get("status"), "success")
        self.assertTrue(response.get("ticket_name"))
        # Перевіряємо наявність номера для відображення
        self.assertTrue(response.get("ticket_number"))

        # Перевіряємо створений документ
        ticket = frappe.get_doc("QMS Ticket", response.get("ticket_name"))
        self.assertEqual(ticket.office, self.office.name)
        self.assertEqual(ticket.service, self.service1.name)
        self.assertEqual(ticket.status, "Waiting")

        # Перевірка формату імені та номера
        expected_prefix = f"TIKET-{self.office.abbreviation}-{get_date_str(now_datetime()).replace('-', '')}-"
        self.assertTrue(ticket.name.startswith(expected_prefix))
        expected_number_str = str(initial_counter + 1).zfill(4)
        self.assertTrue(ticket.name.endswith(f"-{expected_number_str}"))
        # Перевіряємо, що поле ticket_number містить лише номер лічильника
        self.assertEqual(ticket.ticket_number, expected_number_str)

        # Перевіряємо лічильник (опціонально, але корисно)
        final_counter = frappe.db.get_value("QMS Daily Counter", {
                                            "office": self.office.name, "date": get_date_str(now_datetime())}, "last_number")
        self.assertEqual(final_counter, initial_counter + 1)

    @freeze_time("2025-04-30 05:55:00")  # Перед відкриттям (08:55 Київ)
    def test_create_ticket_office_closed(self):
        frappe.set_user("Guest")
        # Враховуємо можливі варіанти написання
        with self.assertRaisesRegex(frappe.ValidationError, "(з|З)ачинений"):
            create_live_queue_ticket(
                service=self.service1.name, office=self.office.name)

    def test_create_ticket_missing_params(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "(Н|н)е вказано (П|п)ослугу або (О|о)фіс"):
            create_live_queue_ticket(service=self.service1.name, office="")
        with self.assertRaisesRegex(frappe.ValidationError, "(Н|н)е вказано (П|п)ослугу або (О|о)фіс"):
            create_live_queue_ticket(service="", office=self.office.name)

    def test_create_ticket_invalid_service_or_office(self):
        frappe.set_user("Guest")
        # Неіснуюча послуга
        with self.assertRaisesRegex(frappe.ValidationError, "(П|п)ослуга.*не знайдена"):
            create_live_queue_ticket(
                service="Неіснуюча Послуга API", office=self.office.name)
        # Неіснуючий офіс
        with self.assertRaisesRegex(frappe.ValidationError, "(О|о)фіс.*не знайдений"):
            create_live_queue_ticket(
                service=self.service1.name, office="НЕІСНУЮЧИЙ_ОФІС")

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_create_ticket_inactive_service(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "(Н|н)еактивна"):
            create_live_queue_ticket(
                service=self.service2.name, office=self.office.name)

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_create_ticket_not_live_queue(self):
        frappe.set_user("Guest")
        with self.assertRaisesRegex(frappe.ValidationError, "(Н|н)едоступна для живої черги"):
            create_live_queue_ticket(
                service=self.service3.name, office=self.office.name)

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_create_ticket_service_not_in_office(self):
        frappe.set_user("Guest")
        # === УНІКАЛЬНІСТЬ: Додаємо суфікс до назви послуги ===
        unique_suffix = uuid.uuid4().hex[:6]
        service_name = f"API Інша Послуга-{unique_suffix}"
        # =====================================================
        # Створюємо послугу, не призначену офісу (rollback її видалить)
        service_other = create_test_service(
            self.organization.name, service_name)  # Використовуємо унікальне ім'я
        with self.assertRaisesRegex(frappe.ValidationError, "(Н|н)едоступна в офісі"):
            create_live_queue_ticket(
                service=service_other.name, office=self.office.name)
        # Rollback видалить service_other автоматично

    # --- Тести для call_next_visitor ---
    # Ці тести виконуються від імені оператора (встановлено в self.setUp)

    def test_call_next_success(self):
        # === ІЗОЛЯЦІЯ: Видаляємо інші Waiting талони цього оператора ===
        frappe.db.delete("QMS Ticket", {
            "office": self.office.name,
            "status": "Waiting",
            # Видаляємо тільки ті, що оператор може викликати
            "service": ["in", [self.service1.name]]
        })
        # ==============================================================

        # Створюємо талон у черзі
        ticket = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting")
        call_time_before = now_datetime()
        response = call_next_visitor(
            service_point_name=self.service_point.name)

        self.assertEqual(response.get("status"), "success",
                         response.get("message", "No message"))
        self.assertIsNotNone(response.get("ticket_info"))
        returned_info = response.get("ticket_info")
        self.assertEqual(returned_info.get("name"), ticket.name)
        self.assertEqual(returned_info.get("status"), "Called")
        # === ВИПРАВЛЕННЯ: Перевіряємо поле operator у повернутому словнику ===
        self.assertEqual(returned_info.get("operator"), self.test_user.name)
        # ===================================================================
        self.assertEqual(returned_info.get(
            "service_point"), self.service_point.name)
        self.assertEqual(returned_info.get("service_point_name"),
                         self.service_point.point_name)  # Перевіряємо назву точки

        # Перевіряємо дані напряму в БД
        updated_ticket = frappe.get_doc("QMS Ticket", ticket.name)
        self.assertEqual(updated_ticket.status, "Called")
        # Перевіряємо, що оператор записався в БД
        self.assertEqual(updated_ticket.operator, self.test_user.name)
        self.assertEqual(updated_ticket.service_point, self.service_point.name)
        self.assertIsNotNone(updated_ticket.call_time)
        self.assertGreaterEqual(get_datetime(
            updated_ticket.call_time), call_time_before)

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_no_waiting_tickets_scenario(self):
        # === ІЗОЛЯЦІЯ: Переконуємось, що немає талонів ===
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        # ===============================================

        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "info")
        self.assertIn("Немає талонів у черзі", response.get("message", ""))

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_operator_no_skills_assigned_scenario(self):
        # === ІЗОЛЯЦІЯ: Видаляємо інші Waiting талони ===
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        # ===============================================
        unique_suffix = uuid.uuid4().hex[:6]
        user_email = f"noskill_api_{unique_suffix}@example.com"
        user_no_skill = create_test_user(
            user_email, f"API Без Навичок {unique_suffix}")
        op_no_skill = create_test_operator(
            user_no_skill.name, self.office.name, skills_list=[])  # Явно порожній список
        frappe.set_user(user_no_skill.name)

        # === ВИПРАВЛЕННЯ ОЧІКУВАННЯ: Очікуємо статус 'error' та відповідне повідомлення ===
        # Викликаємо функцію
        response = call_next_visitor(
            service_point_name=self.service_point.name)

        # Перевіряємо, що статус 'error'
        self.assertEqual(response.get("status"), "error")
        # Перевіряємо, що повідомлення містить текст помилки про відсутність навичок
        self.assertIn("не призначено жодних навичок",
                      response.get("message", ""))
        # ==========================================================================

        frappe.set_user("Administrator")

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_no_matching_skill_ticket_scenario(self):
        frappe.db.delete("QMS Ticket", {
            "office": self.office.name,
            "status": "Waiting",
            "service": ["in", [self.service1.name]]
        })
        # === УНІКАЛЬНІСТЬ: Додаємо суфікс до назви послуги ===
        unique_suffix = uuid.uuid4().hex[:6]
        service_name = f"API Послуга Без Навички-{unique_suffix}"
        # =====================================================
        service_no_skill = create_test_service(
            self.organization.name, service_name)
        assign_service_to_office(self.office.name, service_no_skill.name)
        ticket = create_test_ticket(
            self.office.name, service_no_skill.name, status="Waiting")

        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "info")
        self.assertIn("Немає талонів у черзі", response.get("message", ""))

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_prioritization(self):
        # Створюємо два талони: один з вищим пріоритетом, але створений пізніше
        t_normal = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting", priority=0)
        # Заморожуємо час на секунду пізніше для другого талону
        with freeze_time("2025-04-30 08:05:01"):
            t_priority = create_test_ticket(
                self.office.name, self.service1.name, status="Waiting", priority=5)

        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "success")
        # Перевіряємо, що викликано саме пріоритетний талон
        self.assertEqual(response.get(
            "ticket_info").get("name"), t_priority.name)

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_fifo_same_priority(self):
        # Створюємо два талони з однаковим пріоритетом
        t_first = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting", priority=0)
        with freeze_time("2025-04-30 08:05:01"):
            t_second = create_test_ticket(
                self.office.name, self.service1.name, status="Waiting", priority=0)

        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "success")
        # Перевіряємо, що викликано перший створений талон
        self.assertEqual(response.get("ticket_info").get("name"), t_first.name)

    # --- Тести для get_kiosk_services ---
    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_get_kiosk_services_returns_active_and_ordered(self):
        frappe.set_user("Guest")
        # Модифікуємо порядок сервісів в офісі для тесту сортування
        office_doc = frappe.get_doc("QMS Office", self.office.name)
        # Створюємо новий список з бажаним порядком (наприклад, service3, потім service1)
        # Важливо: додаємо лише ті сервіси, які мають бути видимі в кіоску
        new_assignments = [
            # service3 не має бути видимий (live_queue_enabled=0)
            {"service": self.service1.name, "is_active_in_office": 1},
            # service2 не має бути видимий (enabled=0)
        ]
        office_doc.set("available_services", new_assignments)
        office_doc.save(ignore_permissions=True)

        data = get_kiosk_services(office=self.office.name)
        self.assertNotIn("error", data)
        # Перевіряємо статус "open"
        self.assertEqual(data.get("status", "open"), "open")

        all_visible_services = data.get("services_no_category", [])
        for cat in data.get("categories", []):
            all_visible_services.extend(cat.get("services", []))

        # Перевіряємо, що service1 є
        service1_data = next(
            (s for s in all_visible_services if s["id"] == self.service1.name), None)
        self.assertIsNotNone(service1_data)
        self.assertEqual(service1_data.get("label"),
                         self.service1.service_name)
        self.assertEqual(service1_data.get("icon"),
                         self.service1.icon)  # Перевіряємо іконку

        # Перевіряємо, що service2 і service3 відсутні
        self.assertIsNone(
            next((s for s in all_visible_services if s["id"] == self.service2.name), None))
        self.assertIsNone(
            next((s for s in all_visible_services if s["id"] == self.service3.name), None))

        # Перевірка порядку (якщо сервіси без категорій)
        if data.get("services_no_category"):
            # У нашому випадку лише service1
            self.assertEqual(len(data["services_no_category"]), 1)
            self.assertEqual(data["services_no_category"]
                             [0]["id"], self.service1.name)

    @freeze_time("2025-04-30 05:55:00")  # Перед відкриттям
    def test_get_kiosk_services_office_closed(self):
        frappe.set_user("Guest")
        data = get_kiosk_services(office=self.office.name)
        self.assertEqual(data.get("status"), "closed")
        self.assertIn("зачинено", data.get("message", ""))
        self.assertEqual(len(data.get("categories", [])), 0)
        self.assertEqual(len(data.get("services_no_category", [])), 0)

    # --- Тести для get_display_data ---

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_get_display_data_structure_and_order(self):
        # === ІЗОЛЯЦІЯ: Видаляємо ВСІ талони для цього офісу перед тестом ===
        frappe.db.delete("QMS Ticket", {"office": self.office.name})
        # ====================================================================
        frappe.set_user("Guest")
        # Створюємо талони для тестування списків та сортування
        t_wait_prio1_earlier = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting", priority=1)  # -0001
        with freeze_time("2025-04-30 08:05:01"):
            t_wait_prio0_later = create_test_ticket(
                self.office.name, self.service1.name, status="Waiting", priority=0)  # -0002
        with freeze_time("2025-04-30 08:05:02"):
            # Цей буде викликаний останнім
            t_called_latest = create_test_ticket(self.office.name, self.service1.name, status="Called",  # -0003
                                                 operator=self.test_user.name, service_point=self.service_point.name, call_time=now_datetime())
        with freeze_time("2025-04-30 08:05:03"):
            # Цей буде завершений ще пізніше, але статус не "Called"
            t_completed = create_test_ticket(self.office.name, self.service1.name, status="Completed",  # -0004
                                             operator=self.test_user.name, service_point=self.service_point.name,
                                             call_time=get_datetime(
                                                 "2025-04-30 08:04:00"),  # Викликаний раніше
                                             completion_time=now_datetime())  # Завершений останнім
        # Цей буде викликаний раніше
        t_called_earlier = create_test_ticket(self.office.name, self.service3.name, status="Called",  # -0005 (Інша послуга)
                                              operator=self.test_user.name, service_point=self.service_point.name, call_time=get_datetime("2025-04-30 08:04:30"))

        data = get_display_data(office=self.office.name,
                                limit_called=3, limit_waiting=10)

        self.assertEqual(data.get("office_status"), "open")
        self.assertIn("last_called", data)
        self.assertIn("waiting", data)
        self.assertIsInstance(data["last_called"], list)
        self.assertIsInstance(data["waiting"], list)

        # Перевірка last_called (має бути t_called_latest (0003), потім t_called_earlier (0005))
        # Статус Completed (0004) не має показуватись у 'Called'
        called_tickets = data['last_called']
        # Має бути 2 викликаних
        self.assertEqual(len(called_tickets), 2,
                         f"Expected 2 called tickets, got {len(called_tickets)}: {called_tickets}")
        # Скорочені номери для порівняння
        short_num_latest = t_called_latest.ticket_number  # Тут вже є тільки номер
        short_num_earlier = t_called_earlier.ticket_number  # Тут вже є тільки номер

        # Перевіряємо, що перший у списку - найостанніший викликаний
        self.assertEqual(called_tickets[0]['ticket'], short_num_latest)
        self.assertEqual(
            called_tickets[0]['window'], self.service_point.point_name)
        # Перевіряємо другий
        # === ВИПРАВЛЕННЯ: Порівнюємо з 'short_num_earlier' ===
        self.assertEqual(called_tickets[1]['ticket'], short_num_earlier)
        # ===================================================
        self.assertEqual(
            called_tickets[1]['window'], self.service_point.point_name)

        # Перевірка waiting (має бути t_wait_prio1_earlier (0001), потім t_wait_prio0_later (0002))
        waiting_tickets = data['waiting']
        self.assertEqual(len(waiting_tickets), 2)  # Має бути рівно 2 очікуючих
        # Скорочені номери
        short_num_prio1 = t_wait_prio1_earlier.ticket_number
        short_num_prio0 = t_wait_prio0_later.ticket_number

        # Перевіряємо порядок
        self.assertEqual(waiting_tickets[0]['ticket'], short_num_prio1)
        # Перевірка назви послуги
        self.assertEqual(
            waiting_tickets[0]['service'], self.service1.service_name)
        self.assertEqual(waiting_tickets[1]['ticket'], short_num_prio0)
        self.assertEqual(
            waiting_tickets[1]['service'], self.service1.service_name)

    @freeze_time("2025-04-30 05:55:00")  # Перед відкриттям
    def test_get_display_data_office_closed(self):
        frappe.set_user("Guest")
        data = get_display_data(office=self.office.name,
                                limit_called=3, limit_waiting=10)
        self.assertEqual(data.get("office_status"), "closed")
        self.assertIn("зачинено", data.get("message", ""))
        self.assertEqual(len(data.get("last_called", [])), 0)
        self.assertEqual(len(data.get("waiting", [])), 0)


# --- Запуск тестів ---
# bench --site [your-site] run-tests --app qms_cherga --module qms_cherga.tests.test_api

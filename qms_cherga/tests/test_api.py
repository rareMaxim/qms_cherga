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
    is_office_open,  # Ця функція не повертає стандартний словник, тести залишаються
    get_kiosk_services,
    get_display_data
)


def safe_delete_doc(doctype, name):
    try:
        frappe.delete_doc(doctype,
                          name,
                          ignore_permissions=True,
                          force=True,
                          ignore_missing=True)
    except Exception as e:
        frappe.log_error(
            f"Failed to delete {doctype} {name} during teardown: {e}", "Test Cleanup Error")


def create_test_organization(org_name="Тест API Організація"):
    org = frappe.get_doc({"doctype": "QMS Organization",
                         "organization_name": org_name, }).insert(ignore_permissions=True)
    return org


def create_test_schedule(schedule_name, rules=None, exceptions=None):
    sched = frappe.get_doc({"doctype": "QMS Schedule",
                            "schedule_name": schedule_name,
                            "schedule_rules": rules or [],
                            "schedule_exceptions": exceptions or []}).insert(ignore_permissions=True)
    return sched


def add_schedule_exception(schedule_name, date_str, is_workday, start_time=None, end_time=None):
    doc = frappe.get_doc("QMS Schedule", schedule_name)
    current_exceptions = doc.get("schedule_exceptions", [])
    new_exceptions = [exc for exc in current_exceptions if get_date_str(
        exc.exception_date) != date_str]
    exc_data = {"doctype": "QMS Schedule Exception Child", "exception_date": date_str,
                "description": f"Тестовий виняток {date_str}", "is_workday": is_workday}
    if is_workday:
        exc_data["start_time"] = start_time
        exc_data["end_time"] = end_time
        new_exceptions.append(exc_data)
        doc.set("schedule_exceptions", new_exceptions)
        doc.flags.ignore_permissions = True
        doc.save()
        return doc


def create_test_office(organization_name, schedule_name, abbr, office_name=None, timezone="UTC"):
    office = frappe.get_doc({"doctype": "QMS Office",
                             "organization": organization_name,
                             "office_name": office_name or f"Тест API Офіс {abbr}",
                             "abbreviation": abbr,
                             "schedule": schedule_name, "timezone": timezone}).insert(ignore_permissions=True)
    return office


def create_test_service(organization_name, service_name, **kwargs):
    data = {"doctype": "QMS Service",
            "organization": organization_name,
            "service_name": service_name,
            "avg_duration_mins": kwargs.get("avg_duration_mins", 15),
            "enabled": kwargs.get("enabled", 1),
            "live_queue_enabled": kwargs.get("live_queue_enabled", 1),
            "requires_appointment": kwargs.get("requires_appointment", 0),
            "icon": kwargs.get("icon", "fa fa-cogs")}
    service = frappe.get_doc(data).insert(ignore_permissions=True)
    return service


def assign_service_to_office(office_name, service_name):
    office_doc = frappe.get_doc("QMS Office", office_name)
    current_services = office_doc.get("available_services", [])
    exists = any(item.service == service_name for item in current_services)
    if not exists:
        office_doc.append("available_services", {
                          "service": service_name, "is_active_in_office": 1})
        office_doc.flags.ignore_permissions = True
        office_doc.save()


def create_test_service_point(office_name, point_name):
    sp = frappe.get_doc({"doctype": "QMS Service Point", "office": office_name,
                        "point_name": point_name, "is_active": 1}).insert(ignore_permissions=True)
    return sp


def create_test_user(email, first_name, roles=None):
    user = frappe.get_doc({"doctype": "User", "email": email, "first_name": first_name, "send_welcome_email": 0,
                          "enabled": 1, "roles": roles or [{"role": "System Manager"}]}).insert(ignore_permissions=True)
    return user


def create_test_operator(user_name, office_name, skills_list=None):
    op = frappe.get_doc({"doctype": "QMS Operator", "user": user_name, "full_name": frappe.db.get_value("User", user_name, "full_name"), "default_office": office_name,
                        "is_active": 1, "operator_skills": [{"service": skill, "skill_level": "Proficient"} for skill in (skills_list or [])]}).insert(ignore_permissions=True)
    return op


def create_test_ticket(office_name, service_name, status="Waiting", **kwargs):
    ticket = frappe.new_doc("QMS Ticket")
    ticket.office = office_name
    ticket.service = service_name
    ticket.status = status
    ticket.issue_time = now_datetime()
    for key, value in kwargs.items():
        ticket.set(key, value)
        ticket.insert(ignore_permissions=True)
        ticket.reload()
        return ticket

# --- Основний клас тестів ---


class TestQMSApi(FrappeTestCase):
    created_docs = []

    @classmethod
    def setUpClass(cls):
        super(TestQMSApi, cls).setUpClass()
        try:
            cls.organization = create_test_organization()
            cls.created_docs.append(
                ("QMS Organization", cls.organization.name))
            cls.test_timezone = "Europe/Kyiv"
            cls.schedule = create_test_schedule(
                schedule_name="API_TEST_SCHED",
                rules=[{"day_of_week": "Wednesday", "start_time": time(9, 0), "end_time": time(13, 0)},
                       {"day_of_week": "Wednesday", "start_time": time(
                           14, 0), "end_time": time(18, 0)},
                       {"day_of_week": "Thursday", "start_time": time(10, 0), "end_time": time(16, 0)},])
            cls.created_docs.append(("QMS Schedule", cls.schedule.name))
            cls.office = create_test_office(
                cls.organization.name, cls.schedule.name, "APITEST", timezone=cls.test_timezone)
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
            cls.created_docs.append(("User", cls.test_user.name))
            cls.operator = create_test_operator(
                cls.test_user.name, cls.office.name, skills_list=[cls.service1.name])
            cls.created_docs.append(("QMS Operator", cls.operator.name))
            assign_service_to_office(cls.office.name, cls.service1.name)
            assign_service_to_office(cls.office.name, cls.service2.name)
            assign_service_to_office(cls.office.name, cls.service3.name)
            frappe.db.commit()
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'created_docs'):
            for doctype, name in reversed(cls.created_docs):
                safe_delete_doc(doctype, name)
            cls.created_docs = []
        frappe.db.commit()
        super(TestQMSApi, cls).tearDownClass()

    def setUp(self):
        frappe.set_user(self.test_user.name)

    def tearDown(self):
        frappe.set_user("Administrator")

    @freeze_time("2025-04-30 08:05:00")
    def test_is_office_open_during_working_hours(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 05:55:00")
    def test_is_office_open_before_opening(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 10:15:00")
    def test_is_office_open_during_break(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 12:30:00")
    def test_is_office_open_after_break(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 15:05:00")
    def test_is_office_open_after_closing(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-05-04 09:00:00")
    def test_is_office_open_on_weekend(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 06:00:00")
    def test_is_office_open_at_opening_time(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 15:00:00")
    def test_is_office_open_at_closing_time(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 10:00:00")
    def test_is_office_open_at_break_start_time(self):
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-04-30 11:00:00")
    def test_is_office_open_at_break_end_time(self):
        self.assertTrue(is_office_open(self.schedule.name, self.test_timezone))

    @freeze_time("2025-05-07 08:30:00")
    def test_is_office_open_with_exception_closed(self):
        exception_date = "2025-05-07"
        add_schedule_exception(
            self.schedule.name, exception_date, is_workday=0)
        self.assertFalse(is_office_open(
            self.schedule.name, self.test_timezone))

    @freeze_time("2025-05-14 08:45:00")
    def test_is_office_open_with_exception_open_limited_hours(self):
        exception_date = "2025-05-14"
        add_schedule_exception(self.schedule.name, exception_date,
                               is_workday=1, start_time=time(11, 0), end_time=time(12, 0))
        self.assertTrue(is_office_open(
            self.schedule.name, self.test_timezone), "Should be open during exception hours")
        with freeze_time("2025-05-14 09:15:00"):
            self.assertFalse(is_office_open(
                self.schedule.name, self.test_timezone), "Should be closed outside exception hours")

    def test_is_office_open_invalid_inputs(self):
        self.assertFalse(is_office_open(
            self.schedule.name, "Invalid/Timezone"))
        self.assertFalse(is_office_open(self.schedule.name, None))
        self.assertFalse(is_office_open(self.schedule.name, ""))
        self.assertFalse(is_office_open(None, self.test_timezone))

    @freeze_time("2025-04-30 08:05:00")  # Робочий час (11:05 Київ)
    def test_create_ticket_success(self):
        initial_counter = frappe.db.get_value("QMS Daily Counter", {
                                              "office": self.office.name, "date": get_date_str(now_datetime())}, "last_number") or 0

        frappe.set_user("Guest")  # Імітуємо кіоск
        response = create_live_queue_ticket(
            service=self.service1.name, office=self.office.name)

        # Перевіряємо НОВИЙ формат відповіді
        self.assertEqual(response.get("status"), "success")
        self.assertIn("data", response)
        ticket_data = response.get("data", {})
        self.assertTrue(ticket_data.get("ticket_name"))
        self.assertTrue(ticket_data.get("ticket_number"))
        self.assertEqual(ticket_data.get("office"), self.office.name)
        self.assertEqual(ticket_data.get("service"), self.service1.name)

        # Перевіряємо створений документ (залишається так само)
        ticket = frappe.get_doc("QMS Ticket", ticket_data.get("ticket_name"))
        self.assertEqual(ticket.office, self.office.name)
        self.assertEqual(ticket.service, self.service1.name)
        self.assertEqual(ticket.status, "Waiting")

        # Перевірка формату імені та номера (залишається так само)
        expected_prefix = f"TIKET-{self.office.abbreviation}-{get_date_str(now_datetime()).replace('-', '')}-"
        self.assertTrue(ticket.name.startswith(expected_prefix))
        expected_number_str = str(initial_counter + 1).zfill(4)
        self.assertTrue(ticket.name.endswith(f"-{expected_number_str}"))
        self.assertEqual(ticket.ticket_number, expected_number_str)

        # Перевіряємо лічильник (залишається так само)
        final_counter = frappe.db.get_value("QMS Daily Counter", {
                                            "office": self.office.name, "date": get_date_str(now_datetime())}, "last_number")
        self.assertEqual(final_counter, initial_counter + 1)

    @freeze_time("2025-04-30 05:55:00")  # Перед відкриттям (08:55 Київ)
    def test_create_ticket_office_closed(self):
        frappe.set_user("Guest")
        # Тепер перевіряємо повернутий словник, а не виняток
        response = create_live_queue_ticket(
            service=self.service1.name, office=self.office.name)
        self.assertEqual(response.get("status"), "info")  # Очікуємо 'info'
        # Перевіряємо повідомлення
        self.assertIn("closed", response.get("message", "").lower())
        self.assertEqual(response.get("data", {}).get(
            "office_status"), "closed")  # Перевіряємо статус в даних

    def test_create_ticket_missing_params(self):
        frappe.set_user("Guest")
        # Перевіряємо повернутий словник помилки
        response = create_live_queue_ticket(
            service=self.service1.name, office="")
        self.assertEqual(response.get("status"), "error")
        self.assertEqual(response.get("error_code"), "MISSING_PARAMS")

        response = create_live_queue_ticket(
            service="", office=self.office.name)
        self.assertEqual(response.get("status"), "error")
        self.assertEqual(response.get("error_code"), "MISSING_PARAMS")

    def test_create_ticket_invalid_service_or_office(self):
        frappe.set_user("Guest")
        # Неіснуюча послуга
        response = create_live_queue_ticket(
            service="Неіснуюча Послуга API", office=self.office.name)
        self.assertEqual(response.get("status"), "error")
        self.assertEqual(response.get("error_code"), "INVALID_SERVICE")

        # Неіснуючий офіс
        response = create_live_queue_ticket(
            service=self.service1.name, office="НЕІСНУЮЧИЙ_ОФІС")
        self.assertEqual(response.get("status"), "error")
        self.assertEqual(response.get("error_code"), "INVALID_OFFICE")

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_create_ticket_inactive_service(self):
        frappe.set_user("Guest")
        response = create_live_queue_ticket(
            service=self.service2.name, office=self.office.name)
        self.assertEqual(response.get("status"), "error")
        self.assertEqual(response.get("error_code"), "SERVICE_INACTIVE")

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_create_ticket_not_live_queue(self):
        frappe.set_user("Guest")
        response = create_live_queue_ticket(
            service=self.service3.name, office=self.office.name)
        self.assertEqual(response.get("status"), "error")
        self.assertEqual(response.get("error_code"), "SERVICE_NO_LIVE_QUEUE")

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_create_ticket_service_not_in_office(self):
        frappe.set_user("Guest")
        unique_suffix = uuid.uuid4().hex[:6]
        service_name = f"API Інша Послуга-{unique_suffix}"
        service_other = create_test_service(
            self.organization.name, service_name)
        # Важливо: Додаємо service_other до списку на видалення, бо він створюється всередині тесту
        self.addCleanup(safe_delete_doc, "QMS Service", service_other.name)

        response = create_live_queue_ticket(
            service=service_other.name, office=self.office.name)
        self.assertEqual(response.get("status"), "error")
        self.assertEqual(response.get("error_code"), "SERVICE_NOT_IN_OFFICE")

    # --- Тести для call_next_visitor (ОНОВЛЕНО) ---

    def test_call_next_success(self):
        # Ізоляція
        frappe.db.delete("QMS Ticket", {
                         "office": self.office.name, "status": "Waiting", "service": ["in", [self.service1.name]]})
        ticket = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting")
        call_time_before = now_datetime()
        # Встановлюємо користувача-оператора
        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)

        # Перевіряємо НОВИЙ формат відповіді
        self.assertEqual(response.get("status"), "success",
                         response.get("message", "No message"))
        self.assertIn("data", response)
        self.assertIsNotNone(response.get("data", {}).get("ticket_info"))

        returned_info = response.get("data", {}).get("ticket_info", {})
        self.assertEqual(returned_info.get("name"), ticket.name)
        self.assertEqual(returned_info.get("status"), "Called")
        self.assertEqual(returned_info.get("operator"),
                         self.test_user.name)  # Перевіряємо оператора
        self.assertEqual(returned_info.get("service_point"),
                         self.service_point.name)  # Перевіряємо ID точки
        self.assertEqual(returned_info.get("service_point_name"),
                         self.service_point.point_name)  # Перевіряємо назву точки

        # Перевіряємо дані напряму в БД (без змін)
        updated_ticket = frappe.get_doc("QMS Ticket", ticket.name)
        self.assertEqual(updated_ticket.status, "Called")
        self.assertEqual(updated_ticket.operator, self.test_user.name)
        self.assertEqual(updated_ticket.service_point, self.service_point.name)
        self.assertIsNotNone(updated_ticket.call_time)
        self.assertGreaterEqual(get_datetime(
            updated_ticket.call_time), call_time_before)

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_no_waiting_tickets_scenario(self):
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        # Перевіряємо НОВИЙ формат відповіді
        self.assertEqual(response.get("status"), "info")  # Очікуємо 'info'
        self.assertIn("No tickets found", response.get("message", ""))
        # Перевіряємо, що даних талону немає
        self.assertIsNone(response.get("data", {}).get("ticket_info"))

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_operator_no_skills_assigned_scenario(self):
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        unique_suffix = uuid.uuid4().hex[:6]
        user_email = f"noskill_api_{unique_suffix}@example.com"
        user_no_skill = create_test_user(
            user_email, f"API Без Навичок {unique_suffix}")
        # Додаємо користувача на видалення
        self.addCleanup(safe_delete_doc, "User", user_no_skill.name)
        op_no_skill = create_test_operator(
            user_no_skill.name, self.office.name, skills_list=[])
        # Додаємо оператора на видалення
        self.addCleanup(safe_delete_doc, "QMS Operator", op_no_skill.name)

        frappe.set_user(user_no_skill.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        frappe.set_user("Administrator")  # Повертаємо адміна

        # Перевіряємо НОВИЙ формат відповіді
        self.assertEqual(response.get("status"), "error")  # Очікуємо 'error'
        self.assertEqual(response.get("error_code"), "NO_SKILLS")
        self.assertIn("no skills assigned", response.get("message", ""))

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_no_matching_skill_ticket_scenario(self):
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        unique_suffix = uuid.uuid4().hex[:6]
        service_name = f"API Послуга Без Навички-{unique_suffix}"
        service_no_skill = create_test_service(
            self.organization.name, service_name)
        self.addCleanup(safe_delete_doc, "QMS Service", service_no_skill.name)
        assign_service_to_office(self.office.name, service_no_skill.name)
        ticket = create_test_ticket(
            self.office.name, service_no_skill.name, status="Waiting")
        self.addCleanup(safe_delete_doc, "QMS Ticket", ticket.name)

        # У цього юзера немає навички service_no_skill
        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)

        # Перевіряємо НОВИЙ формат відповіді
        # Немає підходящих талонів
        self.assertEqual(response.get("status"), "info")
        self.assertIn("No tickets found", response.get("message", ""))

    # Тести на пріоритезацію/FIFO залишаються схожими, але перевіряють дані в response['data']['ticket_info']
    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_prioritization(self):
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        t_normal = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting", priority=0)
        self.addCleanup(safe_delete_doc, "QMS Ticket", t_normal.name)
        with freeze_time("2025-04-30 08:05:01"):
            t_priority = create_test_ticket(
                self.office.name, self.service1.name, status="Waiting", priority=5)
            self.addCleanup(safe_delete_doc, "QMS Ticket", t_priority.name)

        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "success")
        self.assertEqual(response.get("data", {}).get(
            "ticket_info", {}).get("name"), t_priority.name)

    @freeze_time("2025-04-30 08:05:00")
    def test_call_next_fifo_same_priority(self):
        frappe.db.delete(
            "QMS Ticket", {"office": self.office.name, "status": "Waiting"})
        t_first = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting", priority=0)
        self.addCleanup(safe_delete_doc, "QMS Ticket", t_first.name)
        with freeze_time("2025-04-30 08:05:01"):
            t_second = create_test_ticket(
                self.office.name, self.service1.name, status="Waiting", priority=0)
            self.addCleanup(safe_delete_doc, "QMS Ticket", t_second.name)

        frappe.set_user(self.test_user.name)
        response = call_next_visitor(
            service_point_name=self.service_point.name)
        self.assertEqual(response.get("status"), "success")
        self.assertEqual(response.get("data", {}).get(
            "ticket_info", {}).get("name"), t_first.name)

    # --- Тести для get_kiosk_services (ОНОВЛЕНО) ---

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_get_kiosk_services_returns_active_and_ordered(self):
        frappe.set_user("Guest")
        office_doc = frappe.get_doc("QMS Office", self.office.name)
        # new_assignments = [ # Тільки service1 має бути видимий
        #     {"service": self.service1.name, "is_active_in_office": 1},
        # ]
        # office_doc.set("available_services", new_assignments)
        # office_doc.save(ignore_permissions=True)
        # frappe.db.commit() # Зберегти зміни перед викликом API

        response = get_kiosk_services(office=self.office.name)

        # Перевіряємо НОВИЙ формат
        self.assertEqual(response.get("status"), "success")
        self.assertIn("data", response)
        kiosk_data = response.get("data", {})

        # Отримуємо всі видимі послуги з категорій та без
        all_visible_services = kiosk_data.get("services_no_category", [])
        for cat in kiosk_data.get("categories", []):
            all_visible_services.extend(cat.get("services", []))

        # Перевіряємо, що service1 є
        service1_data = next(
            (s for s in all_visible_services if s["id"] == self.service1.name), None)
        self.assertIsNotNone(service1_data)
        self.assertEqual(service1_data.get("label"),
                         self.service1.service_name)
        self.assertEqual(service1_data.get("icon"), self.service1.icon)

        # Перевіряємо, що service2 і service3 відсутні
        self.assertIsNone(
            next((s for s in all_visible_services if s["id"] == self.service2.name), None))
        self.assertIsNone(
            next((s for s in all_visible_services if s["id"] == self.service3.name), None))

        # Перевірка порядку (у цьому випадку має бути тільки service1 без категорії)
        self.assertEqual(len(kiosk_data.get("services_no_category", [])), 1)
        self.assertEqual(
            kiosk_data["services_no_category"][0]["id"], self.service1.name)
        # Категорій бути не повинно
        self.assertEqual(len(kiosk_data.get("categories", [])), 0)

    @freeze_time("2025-04-30 05:55:00")  # Перед відкриттям
    def test_get_kiosk_services_office_closed(self):
        frappe.set_user("Guest")
        response = get_kiosk_services(office=self.office.name)
        # Перевіряємо НОВИЙ формат
        self.assertEqual(response.get("status"), "info")  # Очікуємо 'info'
        self.assertIn("closed", response.get("message", "").lower())
        kiosk_data = response.get("data", {})
        # Перевіряємо статус в даних
        self.assertEqual(kiosk_data.get("status"), "closed")
        self.assertEqual(len(kiosk_data.get("categories", [])), 0)
        self.assertEqual(len(kiosk_data.get("services_no_category", [])), 0)

    # --- Тести для get_display_data (ОНОВЛЕНО) ---

    @freeze_time("2025-04-30 08:05:00")  # Робочий час
    def test_get_display_data_structure_and_order(self):
        frappe.db.delete("QMS Ticket", {"office": self.office.name})
        frappe.set_user("Guest")  # Табло - гостьовий доступ

        # Створюємо талони
        t_wait_prio1_earlier = create_test_ticket(
            self.office.name, self.service1.name, status="Waiting", priority=1)
        self.addCleanup(safe_delete_doc, "QMS Ticket",
                        t_wait_prio1_earlier.name)
        with freeze_time("2025-04-30 08:05:01"):
            t_wait_prio0_later = create_test_ticket(
                self.office.name, self.service1.name, status="Waiting", priority=0)
            self.addCleanup(safe_delete_doc, "QMS Ticket",
                            t_wait_prio0_later.name)
        t_called_earlier_time = get_datetime("2025-04-30 08:04:30")
        t_called_earlier = create_test_ticket(self.office.name, self.service3.name, status="Called",
                                              operator=self.test_user.name, service_point=self.service_point.name, call_time=t_called_earlier_time)
        self.addCleanup(safe_delete_doc, "QMS Ticket", t_called_earlier.name)
        with freeze_time("2025-04-30 08:05:02"):
            t_called_latest_time = now_datetime()
            t_called_latest = create_test_ticket(self.office.name, self.service1.name, status="Called",
                                                 operator=self.test_user.name, service_point=self.service_point.name, call_time=t_called_latest_time)
            self.addCleanup(safe_delete_doc, "QMS Ticket",
                            t_called_latest.name)
        with freeze_time("2025-04-30 08:05:03"):
            t_completed = create_test_ticket(self.office.name, self.service1.name, status="Completed", operator=self.test_user.name,
                                             service_point=self.service_point.name, call_time=get_datetime("2025-04-30 08:04:00"), completion_time=now_datetime())
            self.addCleanup(safe_delete_doc, "QMS Ticket", t_completed.name)

        response = get_display_data(
            office=self.office.name, limit_called=3, limit_waiting=10)

        # Перевіряємо НОВИЙ формат
        self.assertEqual(response.get("status"), "success")
        self.assertIn("data", response)
        display_data = response.get("data", {})

        self.assertEqual(display_data.get("office_status"), "open")
        self.assertIn("last_called", display_data)
        self.assertIn("waiting", display_data)
        self.assertIsInstance(display_data.get("last_called"), list)
        self.assertIsInstance(display_data.get("waiting"), list)

        # Перевірка last_called (має бути t_called_latest, потім t_called_earlier)
        called_tickets = display_data['last_called']
        self.assertEqual(len(called_tickets), 2,
                         f"Expected 2 called tickets, got {len(called_tickets)}: {called_tickets}")
        short_num_latest = t_called_latest.ticket_number
        short_num_earlier = t_called_earlier.ticket_number

        self.assertEqual(called_tickets[0]['ticket'], short_num_latest)
        self.assertEqual(
            called_tickets[0]['window'], self.service_point.point_name)
        self.assertEqual(called_tickets[1]['ticket'], short_num_earlier)
        self.assertEqual(
            called_tickets[1]['window'], self.service_point.point_name)

        # Перевірка waiting (має бути t_wait_prio1_earlier, потім t_wait_prio0_later)
        waiting_tickets = display_data['waiting']
        self.assertEqual(len(waiting_tickets), 2)
        short_num_prio1 = t_wait_prio1_earlier.ticket_number
        short_num_prio0 = t_wait_prio0_later.ticket_number

        self.assertEqual(waiting_tickets[0]['ticket'], short_num_prio1)
        self.assertEqual(
            waiting_tickets[0]['service'], self.service1.service_name)
        self.assertEqual(waiting_tickets[1]['ticket'], short_num_prio0)
        self.assertEqual(
            waiting_tickets[1]['service'], self.service1.service_name)

    @freeze_time("2025-04-30 05:55:00")  # Перед відкриттям
    def test_get_display_data_office_closed(self):
        frappe.set_user("Guest")
        response = get_display_data(
            office=self.office.name, limit_called=3, limit_waiting=10)
        self.assertEqual(response.get("status"), "info")  # Очікуємо 'info'
        self.assertIn("closed", response.get("message", "").lower())
        display_data = response.get("data", {})
        self.assertEqual(display_data.get("office_status"), "closed")
        self.assertEqual(len(display_data.get("last_called", [])), 0)
        self.assertEqual(len(display_data.get("waiting", [])), 0)

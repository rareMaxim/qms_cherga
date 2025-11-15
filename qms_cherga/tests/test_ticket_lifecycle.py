"""
Integration tests for ticket lifecycle.
"""
import unittest
import frappe
from frappe.utils import now_datetime
from qms_cherga.api.kiosk import create_live_queue_ticket
from qms_cherga.api.operator import call_next_visitor, start_service, finish_service, mark_as_no_show, postpone_ticket


class TestTicketLifecycle(unittest.TestCase):
    """Integration tests for complete ticket lifecycle"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        frappe.set_user("Administrator")

        # Створюємо тестову організацію
        if not frappe.db.exists("QMS Organization", "TEST-ORG"):
            org = frappe.get_doc({
                "doctype": "QMS Organization",
                "organization_name": "Test Organization"
            })
            org.insert(ignore_permissions=True)

        # Створюємо тестовий графік роботи
        if not frappe.db.exists("QMS Schedule", "TEST-SCHEDULE"):
            schedule = frappe.get_doc({
                "doctype": "QMS Schedule",
                "schedule_name": "TEST-SCHEDULE"
            })
            # Додаємо правило для всіх днів
            for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                schedule.append("schedule_rules", {
                    "day_of_week": day,
                    "start_time": "08:00:00",
                    "end_time": "18:00:00"
                })
            schedule.insert(ignore_permissions=True)

        # Створюємо тестовий офіс
        if not frappe.db.exists("QMS Office", "TEST-LIFECYCLE"):
            office = frappe.get_doc({
                "doctype": "QMS Office",
                "abbreviation": "TEST-LIFECYCLE",
                "office_name": "Test Lifecycle Office",
                "organization": "TEST-ORG",
                "schedule": "TEST-SCHEDULE",
                "timezone": "Europe/Kyiv"
            })
            office.insert(ignore_permissions=True)

        # Створюємо тестовий сервіс
        if not frappe.db.exists("QMS Service", "TEST-SERVICE-LC"):
            service = frappe.get_doc({
                "doctype": "QMS Service",
                "service_name": "Test Service Lifecycle",
                "organization": "TEST-ORG",
                "enabled": 1,
                "live_queue_enabled": 1,
                "avg_duration_mins": 15
            })
            service.insert(ignore_permissions=True)

        # Додаємо сервіс до офісу
        office_doc = frappe.get_doc("QMS Office", "TEST-LIFECYCLE")
        if not any(a.service == "TEST-SERVICE-LC" for a in office_doc.get("available_services", [])):
            office_doc.append("available_services", {
                "service": "TEST-SERVICE-LC",
                "is_active_in_office": 1
            })
            office_doc.save(ignore_permissions=True)

        # Створюємо точку обслуговування
        if not frappe.db.exists("QMS Service Point", "TEST-POINT-LC"):
            point = frappe.get_doc({
                "doctype": "QMS Service Point",
                "point_name": "Test Point Lifecycle",
                "office": "TEST-LIFECYCLE",
                "is_active": 1
            })
            point.insert(ignore_permissions=True)

        # Створюємо оператора
        if not frappe.db.exists("User", "test.operator@qms.local"):
            user = frappe.get_doc({
                "doctype": "User",
                "email": "test.operator@qms.local",
                "first_name": "Test",
                "last_name": "Operator",
                "send_welcome_email": 0
            })
            user.insert(ignore_permissions=True)

        if not frappe.db.exists("QMS Operator", {"user": "test.operator@qms.local"}):
            operator = frappe.get_doc({
                "doctype": "QMS Operator",
                "user": "test.operator@qms.local",
                "full_name": "Test Operator",
                "default_office": "TEST-LIFECYCLE",
                "is_active": 1
            })
            operator.append("operator_skills", {
                "service": "TEST-SERVICE-LC"
            })
            operator.insert(ignore_permissions=True)

        frappe.db.commit()

    def test_complete_ticket_lifecycle(self):
        """Test complete ticket lifecycle: create -> call -> start -> finish"""

        # 1. Створюємо талон через кіоск
        create_response = create_live_queue_ticket(
            service="TEST-SERVICE-LC",
            office="TEST-LIFECYCLE",
            visitor_phone="+380501234567"
        )

        self.assertTrue(create_response.get("success"), "Ticket creation should succeed")
        ticket_name = create_response["data"]["ticket_name"]
        ticket_number = create_response["data"]["ticket_number"]

        self.assertIsNotNone(ticket_name)
        self.assertIsNotNone(ticket_number)

        # Перевіряємо що талон створено зі статусом "Waiting"
        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)
        self.assertEqual(ticket_doc.status, "Waiting")

        # 2. Оператор викликає талон
        frappe.set_user("test.operator@qms.local")

        call_response = call_next_visitor("TEST-POINT-LC")

        self.assertTrue(call_response.get("success"), "Call next visitor should succeed")

        # Перевіряємо статус після виклику
        ticket_doc.reload()
        self.assertEqual(ticket_doc.status, "Called")
        self.assertIsNotNone(ticket_doc.call_time)
        self.assertEqual(ticket_doc.operator, "test.operator@qms.local")

        # 3. Оператор починає обслуговування
        start_response = start_service(ticket_name)

        self.assertTrue(start_response.get("success"), "Start service should succeed")

        # Перевіряємо статус
        ticket_doc.reload()
        self.assertEqual(ticket_doc.status, "Serving")
        self.assertIsNotNone(ticket_doc.start_service_time)

        # 4. Оператор завершує обслуговування
        finish_response = finish_service(ticket_name)

        self.assertTrue(finish_response.get("success"), "Finish service should succeed")

        # Перевіряємо фінальний статус
        ticket_doc.reload()
        self.assertEqual(ticket_doc.status, "Completed")
        self.assertIsNotNone(ticket_doc.completion_time)

    def test_ticket_postpone_and_recall(self):
        """Test postponing and recalling a ticket"""

        frappe.set_user("Administrator")

        # Створюємо талон
        create_response = create_live_queue_ticket(
            service="TEST-SERVICE-LC",
            office="TEST-LIFECYCLE"
        )

        ticket_name = create_response["data"]["ticket_name"]

        # Оператор викликає талон
        frappe.set_user("test.operator@qms.local")
        call_next_visitor("TEST-POINT-LC")

        # Відкладаємо талон
        postpone_response = postpone_ticket(ticket_name)

        self.assertTrue(postpone_response.get("success"))

        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)
        self.assertEqual(ticket_doc.status, "Postponed")

        # TODO: Додати recall_ticket test коли буде реалізовано

    def test_ticket_no_show(self):
        """Test marking ticket as no-show"""

        frappe.set_user("Administrator")

        # Створюємо талон
        create_response = create_live_queue_ticket(
            service="TEST-SERVICE-LC",
            office="TEST-LIFECYCLE"
        )

        ticket_name = create_response["data"]["ticket_name"]

        # Оператор викликає талон
        frappe.set_user("test.operator@qms.local")
        call_next_visitor("TEST-POINT-LC")

        # Позначаємо як no-show
        no_show_response = mark_as_no_show(ticket_name)

        self.assertTrue(no_show_response.get("success"))

        ticket_doc = frappe.get_doc("QMS Ticket", ticket_name)
        self.assertEqual(ticket_doc.status, "NoShow")
        self.assertIsNotNone(ticket_doc.completion_time)

    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        frappe.set_user("Administrator")

        # Видаляємо тестові талони
        tickets = frappe.get_all("QMS Ticket", filters={"office": "TEST-LIFECYCLE"}, pluck="name")
        for ticket in tickets:
            frappe.delete_doc("QMS Ticket", ticket, force=True)

        # Видаляємо тестові дані
        if frappe.db.exists("QMS Service Point", "TEST-POINT-LC"):
            frappe.delete_doc("QMS Service Point", "TEST-POINT-LC", force=True)

        if frappe.db.exists("QMS Operator", {"user": "test.operator@qms.local"}):
            operator = frappe.get_all("QMS Operator", filters={"user": "test.operator@qms.local"}, pluck="name")
            if operator:
                frappe.delete_doc("QMS Operator", operator[0], force=True)

        if frappe.db.exists("User", "test.operator@qms.local"):
            frappe.delete_doc("User", "test.operator@qms.local", force=True)

        if frappe.db.exists("QMS Office", "TEST-LIFECYCLE"):
            frappe.delete_doc("QMS Office", "TEST-LIFECYCLE", force=True)

        if frappe.db.exists("QMS Service", "TEST-SERVICE-LC"):
            frappe.delete_doc("QMS Service", "TEST-SERVICE-LC", force=True)

        if frappe.db.exists("QMS Schedule", "TEST-SCHEDULE"):
            frappe.delete_doc("QMS Schedule", "TEST-SCHEDULE", force=True)

        if frappe.db.exists("QMS Organization", "TEST-ORG"):
            frappe.delete_doc("QMS Organization", "TEST-ORG", force=True)

        frappe.db.commit()


def run_tests():
    """Run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()

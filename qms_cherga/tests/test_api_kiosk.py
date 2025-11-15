"""
Unit tests for Kiosk API endpoints.
"""
import unittest
import frappe
from qms_cherga.api.kiosk import get_office_info, get_kiosk_services, create_live_queue_ticket


class TestKioskAPI(unittest.TestCase):
    """Test cases for Kiosk API endpoints"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        frappe.set_user("Administrator")

    def test_get_office_info_success(self):
        """Test get_office_info with valid office ID"""
        # Створюємо тестовий офіс
        if not frappe.db.exists("QMS Office", "TEST-OFFICE-001"):
            office = frappe.get_doc({
                "doctype": "QMS Office",
                "abbreviation": "TEST-OFFICE-001",
                "office_name": "Test Office",
                "timezone": "Europe/Kyiv"
            })
            office.insert(ignore_permissions=True)
            frappe.db.commit()

        # Викликаємо API
        response = get_office_info("TEST-OFFICE-001")

        # Перевіряємо результат
        self.assertTrue(response.get("success"))
        self.assertIn("data", response)
        self.assertEqual(response["data"]["office_name"], "Test Office")

    def test_get_office_info_not_found(self):
        """Test get_office_info with non-existent office"""
        response = get_office_info("NONEXISTENT-OFFICE")

        self.assertFalse(response.get("success"))
        self.assertEqual(response.get("http_status_code"), 404)

    def test_get_office_info_missing_param(self):
        """Test get_office_info without office parameter"""
        response = get_office_info("")

        self.assertFalse(response.get("success"))
        self.assertEqual(response.get("http_status_code"), 400)

    def test_get_kiosk_services_success(self):
        """Test get_kiosk_services with valid office"""
        # Створюємо тестовий офіс якщо не існує
        if not frappe.db.exists("QMS Office", "TEST-OFFICE-001"):
            office = frappe.get_doc({
                "doctype": "QMS Office",
                "abbreviation": "TEST-OFFICE-001",
                "office_name": "Test Office",
                "timezone": "Europe/Kyiv"
            })
            office.insert(ignore_permissions=True)
            frappe.db.commit()

        response = get_kiosk_services("TEST-OFFICE-001")

        self.assertTrue(response.get("success"))
        self.assertIn("data", response)
        self.assertIn("categories", response["data"])
        self.assertIn("services_no_category", response["data"])

    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        # Видаляємо тестові дані
        if frappe.db.exists("QMS Office", "TEST-OFFICE-001"):
            frappe.delete_doc("QMS Office", "TEST-OFFICE-001", force=True)
            frappe.db.commit()


def run_tests():
    """Run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()

"""
Unit tests for Operator API endpoints.
"""
import unittest
import frappe
from qms_cherga.api.operator import get_live_data, start_service, finish_service


class TestOperatorAPI(unittest.TestCase):
    """Test cases for Operator API endpoints"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        frappe.set_user("Administrator")

        # Створюємо тестовий офіс
        if not frappe.db.exists("QMS Office", "TEST-OFFICE-OPS"):
            office = frappe.get_doc({
                "doctype": "QMS Office",
                "abbreviation": "TEST-OFFICE-OPS",
                "office_name": "Test Office for Operators",
                "timezone": "Europe/Kyiv"
            })
            office.insert(ignore_permissions=True)
            frappe.db.commit()

    def test_get_live_data_success(self):
        """Test get_live_data with valid office"""
        response = get_live_data("TEST-OFFICE-OPS", as_dict=True)

        self.assertIn("stats", response)
        self.assertIn("postponed_tickets", response)
        self.assertIn("waiting", response["stats"])
        self.assertIn("serving", response["stats"])
        self.assertIn("finished_today", response["stats"])

    def test_get_live_data_not_found(self):
        """Test get_live_data with non-existent office"""
        response = get_live_data("NONEXISTENT-OFFICE", as_dict=False)

        self.assertFalse(response.get("success"))

    def test_start_service_missing_ticket(self):
        """Test start_service with non-existent ticket"""
        response = start_service("NONEXISTENT-TICKET")

        self.assertFalse(response.get("success"))
        self.assertEqual(response.get("http_status_code"), 404)

    def test_finish_service_missing_ticket(self):
        """Test finish_service with non-existent ticket"""
        response = finish_service("NONEXISTENT-TICKET")

        self.assertFalse(response.get("success"))
        self.assertEqual(response.get("http_status_code"), 404)

    @classmethod
    def tearDownClass(cls):
        """Clean up test data"""
        if frappe.db.exists("QMS Office", "TEST-OFFICE-OPS"):
            frappe.delete_doc("QMS Office", "TEST-OFFICE-OPS", force=True)
            frappe.db.commit()


def run_tests():
    """Run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()

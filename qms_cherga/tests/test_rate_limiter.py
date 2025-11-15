"""
Unit tests for rate limiting.
"""
import unittest
import frappe
import time
from qms_cherga.utils.rate_limiter import rate_limit, clear_rate_limit


class TestRateLimiter(unittest.TestCase):
    """Test cases for rate limiting"""

    def setUp(self):
        """Set up test fixtures"""
        frappe.local.request_ip = "127.0.0.1"

    def test_rate_limit_decorator(self):
        """Test rate limit decorator"""

        @rate_limit(max_requests=3, window_seconds=2)
        def test_function():
            return {"success": True, "message": "OK"}

        # Перші 3 запити мають пройти
        for i in range(3):
            result = test_function()
            self.assertTrue(result.get("success"), f"Request {i+1} should succeed")

        # 4-й запит має бути заблокований
        result = test_function()
        self.assertFalse(result.get("success"), "4th request should be rate limited")
        self.assertEqual(result.get("error_code"), "RATE_LIMIT_EXCEEDED")

        # Чекаємо закінчення вікна
        time.sleep(2.1)

        # Тепер запит має пройти
        result = test_function()
        self.assertTrue(result.get("success"), "Request after window should succeed")

    def test_clear_rate_limit(self):
        """Test clearing rate limit"""

        @rate_limit(max_requests=2, window_seconds=60)
        def test_function():
            return {"success": True}

        # Виконуємо 2 запити
        test_function()
        test_function()

        # 3-й запит має бути заблокований
        result = test_function()
        self.assertFalse(result.get("success"))

        # Очищаємо rate limit
        clear_rate_limit("test_function", "127.0.0.1")

        # Тепер запит має пройти
        result = test_function()
        self.assertTrue(result.get("success"))


def run_tests():
    """Run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()

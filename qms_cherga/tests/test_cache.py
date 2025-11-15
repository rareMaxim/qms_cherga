"""
Unit tests for caching utilities.
"""
import unittest
import frappe
from qms_cherga.utils.cache import (
    get_cached_office_info,
    cache_office_info,
    invalidate_office_cache,
    get_cached_kiosk_services,
    cache_kiosk_services
)


class TestCache(unittest.TestCase):
    """Test cases for caching utilities"""

    def setUp(self):
        """Set up test fixtures"""
        # Очищаємо кеш перед кожним тестом
        invalidate_office_cache()

    def test_cache_and_get_office_info(self):
        """Test caching and retrieving office info"""
        test_data = {
            "office_name": "Test Office",
            "timezone": "Europe/Kyiv"
        }

        # Кешуємо дані
        cache_office_info("TEST-001", test_data, ttl=10)

        # Отримуємо з кешу
        cached_data = get_cached_office_info("TEST-001")

        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data["office_name"], "Test Office")
        self.assertEqual(cached_data["timezone"], "Europe/Kyiv")

    def test_invalidate_office_cache(self):
        """Test cache invalidation"""
        test_data = {"office_name": "Test Office"}

        # Кешуємо дані
        cache_office_info("TEST-001", test_data, ttl=10)

        # Перевіряємо що дані в кеші
        self.assertIsNotNone(get_cached_office_info("TEST-001"))

        # Інвалідуємо кеш
        invalidate_office_cache("TEST-001")

        # Перевіряємо що кеш очищено
        self.assertIsNone(get_cached_office_info("TEST-001"))

    def test_cache_kiosk_services(self):
        """Test caching kiosk services"""
        test_data = {
            "categories": [],
            "services_no_category": [
                {"id": "SRV-001", "label": "Test Service"}
            ]
        }

        # Кешуємо дані
        cache_kiosk_services("TEST-001", test_data, ttl=10)

        # Отримуємо з кешу
        cached_data = get_cached_kiosk_services("TEST-001")

        self.assertIsNotNone(cached_data)
        self.assertEqual(len(cached_data["services_no_category"]), 1)
        self.assertEqual(cached_data["services_no_category"][0]["id"], "SRV-001")


def run_tests():
    """Run all tests"""
    unittest.main()


if __name__ == "__main__":
    run_tests()

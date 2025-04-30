# Copyright (c) 2025, Maxym Sysoiev and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class QMSOperator(Document):
    # Метод для отримання послуг (може бути і поза класом, але з @frappe.whitelist())
    @frappe.whitelist()
    def get_services_for_office(self, office_id):
        """
        Отримує список ID активних послуг для вказаного офісу.
        Викликається з клієнтського скрипта.
        """
        if not office_id:
            frappe.throw("Не вказано ID офісу.")

        if not frappe.db.exists("QMS Office", office_id):
            frappe.throw(f"Офіс з ID '{office_id}' не знайдено.")

        # Отримуємо список ID послуг з таблиці QMS Office Service Assignment
        service_assignments = frappe.get_all(
            "QMS Office Service Assignment",
            filters={
                # Фільтр за батьківським документом (Офіс)
                "parent": office_id,
                "parenttype": "QMS Office",  # Явно вказуємо тип батьківського документа
                "is_active_in_office": 1    # Тільки активні призначення
            },
            fields=["service"]  # Отримуємо тільки поле 'service' (ID послуги)
        )

        # Повертаємо список ID послуг
        service_ids = [d.service for d in service_assignments]
        return service_ids

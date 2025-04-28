# Copyright (c) 2025, Maxym Sysoiev and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class QMSWebsocketTest(Document):
    # Цей метод викликається після збереження документа (і створення, і оновлення)
    def on_update(self):
        frappe.publish_realtime(
            event='websocket_test_updated',  # Унікальна назва події
            message={
                'docname': self.name,
                'message': f"Документ '{self.name}' було оновлено!"
            },
            # Фільтр для клієнта (необов'язково, але корисно)
            doctype=self.doctype,
            docname=self.name,   # Фільтр для клієнта - тільки для цього документа
            after_commit=True    # Важливо! Надіслати після завершення транзакції БД
        )
        # Для відладки
        frappe.msgprint(f"Подію WebSocket надіслано для {self.name}")

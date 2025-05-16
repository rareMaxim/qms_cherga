# qms_ticket.py

import time
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today, cint, get_date_str


class QMSTicket(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        actual_service_time_mins: DF.Int
        actual_wait_time_mins: DF.Int
        appointment_datetime: DF.Datetime | None
        appointment_source: DF.Data | None
        call_time: DF.Datetime | None
        completion_time: DF.Datetime | None
        estimated_wait_time_mins: DF.Int
        is_appointment: DF.Check
        issue_time: DF.Datetime | None
        office: DF.Link
        operator: DF.Link | None
        priority: DF.Int
        service: DF.Link
        service_point: DF.Link | None
        start_service_time: DF.Datetime | None
        status: DF.Literal["Scheduled", "Waiting", "Called",
                           "Serving", "Completed", "NoShow", "Cancelled", "Postponed"]
        target_operator: DF.Link | None
        ticket_number: DF.Data | None
        visitor_email: DF.Data | None
        visitor_name: DF.Data | None
        visitor_phone: DF.Data | None
    # end: auto-generated types

    def on_update(self):
        """Викликається після кожного збереження документу (існуючого або нового після after_insert)."""

        frappe.logger("qms_realtime").debug(
            f"QMSTicket {self.name} on_update triggered. Status: {self.status}")
        event_name_to_publish = 'qms_ticket_updated_doc'
        event_type_in_payload = 'qms_ticket_updated_doc'  # Тип всередині даних
        # Визначаємо, чи це була специфічна зміна статусу, яку треба обробити окремо
        if self._doc_before_save:  # Перевіряємо, чи це оновлення, а не перше збереження
            old_status = self._doc_before_save.get("status")
            new_status = self.status
            if new_status != old_status:
                event_type_in_payload = new_status
        else:
            event_type_in_payload = self.status
        self.publish_event(event_name_to_publish, event_type_in_payload)

        # Додатково, якщо відбулась зміна статусу, можна надіслати подію про оновлення статистики
        if self._doc_before_save and self._doc_before_save.get("status") != self.status:
            self.publish_stats_update()

    def after_insert(self):
        # """Викликається тільки після першого збереження нового документу."""
        # frappe.logger("qms_realtime").debug(
        #     f"QMSTicket {self.name} after_insert triggered. Status: {self.status}")

        # # Типова подія для нового талону з кіоску або створеного вручну зі статусом Waiting
        # if self.status == "Waiting":
        #     self.publish_event(event_name_for_socket='qms_ticket_created',
        #                        event_type_in_payload='qms_new_ticket_in_queue')
        # # Якщо талон створюється одразу зі статусом "Called" (наприклад, при ручному створенні оператором)
        # elif self.status == "Called":
        #     self.publish_event(event_name_for_socket='qms_ticket_called',
        #                        event_type_in_payload='qms_ticket_called')
        # # Для інших статусів при створенні (менш імовірно, але для повноти)
        # else:
        #     self.publish_event(event_name_for_socket='qms_ticket_updated_doc',
        #                        event_type_in_payload='qms_ticket_updated_doc')

        # self.publish_stats_update()  # Оновлюємо статистику при створенні будь-якого талону
        pass

    def publish_stats_update(self):
        """Надсилає подію про необхідність оновлення статистики."""
        if not self.office:
            return

        stats_message = {
            "type": "qms_stats_update_needed",  # Спеціальний тип для статистики
            "office": self.office,
            "operator": self.operator,  # Якщо статистика залежить від оператора
            # Можна додати інші дані, які допоможуть фронтенду зрозуміти, що саме оновити
        }
        room = office_room(self.office)

        frappe.logger("qms_realtime").info(
            f"QMSTicket {self.name}: Publishing event 'qms_stats_updated' to room '{room}' for stats refresh.")

        frappe.publish_realtime(
            event='qms_stats_updated',  # Загальна подія для оновлення статистики
            message=stats_message,
            # room=room,
            after_commit=True
        )

    # --- Налаштування DocType ---
    # У визначенні DocType 'QMS Ticket' (через UI або qms_ticket.json):
    # 1. Встановіть властивість 'Autoname' на 'method'.
    #    (Або 'python:autoname', якщо ви хочете вказати ім'я методу явно).
    # 2. Приберіть інші правила Autoname ('naming_series', 'prompt', 'field:...' тощо).

    def autoname(self):
        """
        Цей метод автоматично викликається Frappe для встановлення
        первинного ключа документа (self.name), якщо Autoname='method'.
        Він виконується *перед* before_insert.
        """
        # 1. Перевірка наявності офісу
        if not self.office:
            frappe.throw(
                "Необхідно вказати 'Office' для генерації імені талону")

        # 2. Отримання поточної дати
        current_date_str = today()  # Формат: YYYY-MM-DD

        # 3. Отримання наступного номера послідовності
        try:
            # Передаємо дату для консистентності
            next_num = self.get_next_ticket_sequence_orm(current_date_str)
        except Exception as e:
            # Логуємо помилку і перериваємо процес, якщо лічильник недоступний
            frappe.log_error(frappe.get_traceback(),
                             "QMSTicket Autoname Counter Fetch Error")
            frappe.throw(
                f"Не вдалося отримати лічильник для автоматичного іменування: {e}")

        # 4. Форматування лічильника (наприклад, 4 цифри)
        counter_str = str(next_num).zfill(4)

        # 5. Форматування дати (наприклад, YYYYMMDD)
        date_str_formatted = current_date_str.replace("-", "")

        # 6. Отримання абревіатури (ABBR) з поля 'office'
        abbr = self.office

        # 7. Створення фінального імені: TIKET-OFFICE ABBR-Date-COunter
        # Налаштуйте префікс та роздільники відповідно до ваших вимог
        generated_name = f"TIKET-{abbr}-{date_str_formatted}-{counter_str}"

        # 8. Присвоєння згенерованого імені полю self.name
        self.name = generated_name

        # --- Опціонально: Встановлення поля ticket_number ---
        # Якщо ви хочете, щоб поле ticket_number також встановлювалось тут
        # (це може бути логічніше, ніж у before_insert)
        if not self.ticket_number:
            self.ticket_number = counter_str
            # Або якщо потрібне числове значення:
            # self.ticket_number = next_num

    def before_insert(self):
        # Метод autoname вже встановив self.name.
        # Цей метод тепер можна використовувати для іншої логіки,
        # яка має виконатися після autoname, але перед першим збереженням.
        # Наприклад, валідації, встановлення інших полів тощо.

        # Якщо ви НЕ встановили self.ticket_number у методі autoname,
        # це можна зробити тут, хоча це менш чисто.
        # Наприклад, витягнувши лічильник з self.name (але краще встановити в autoname).
        #
        # if not self.ticket_number and self.name:
        #     try:
        #         self.ticket_number = self.name.split('-')[-1]
        #     except Exception:
        #         pass # Обробка помилки, якщо формат імені несподіваний

        # Наразі метод може бути порожнім, якщо інша логіка не потрібна
        if not self.issue_time:
            self.issue_time = now_datetime()
        # Якщо статус не встановлено, за замовчуванням "Waiting"
        if not self.status:
            self.status = "Waiting"

    # Метод get_next_ticket_sequence_orm залишається без змін (як у попередньому варіанті)
    def get_next_ticket_sequence_orm(self, current_date_str):
        """
        Отримує наступний номер послідовності з 'QMS Daily Counter'.
        (Код ідентичний попередньому)
        """
        if not self.office:
            frappe.throw("Не вказано 'Office' для генерації послідовності")

        counter_doc_name = f"{self.office}-{current_date_str}"
        new_number = 0
        max_attempts = 5  # Кількість спроб

        for attempt in range(max_attempts):
            counter_doc = None
            try:
                # Use exists for check
                if frappe.db.exists("QMS Daily Counter", counter_doc_name):
                    # Use get_doc for loading
                    counter_doc = frappe.get_doc(
                        "QMS Daily Counter", counter_doc_name)
                    # Re-read from DB before incrementing
                    counter_doc.load_from_db()
                    new_number = cint(counter_doc.last_number) + 1  # Use cint
                    counter_doc.last_number = new_number
                else:
                    # Create new counter document
                    new_number = 1
                    counter_doc = frappe.new_doc("QMS Daily Counter")
                    counter_doc.name = counter_doc_name  # Set name explicitly
                    counter_doc.office = self.office
                    counter_doc.date = current_date_str
                    counter_doc.last_number = new_number

                # Save the counter doc
                counter_doc.flags.ignore_permissions = True
                counter_doc.save(ignore_version=True)
                frappe.db.commit()  # Commit immediately

                # If save successful, return the number
                return new_number

            except frappe.DuplicateEntryError:
                frappe.db.rollback()
                frappe.log_warning(
                    f"Attempt {attempt + 1}: Duplicate entry error for {counter_doc_name}. Retrying.", "QMSTicket ORM Counter")

            except Exception as e:
                frappe.db.rollback()
                frappe.log_error(frappe.get_traceback(
                ), f"QMS Ticket Counter Error (ORM Attempt {attempt + 1})")
                # Перекидаємо помилку, щоб її зловили у методі autoname
                raise frappe._(
                    "Не вдалося оновити лічильник талонів: {0}").format(e)

            # Wait before retrying
            time.sleep(0.1 + (0.1 * attempt))  # Progressive delay

        # If loop finishes without returning
        frappe.db.rollback()
        # Перекидаємо помилку, щоб її зловили у методі autoname
        raise _(
            f"Не вдалося отримати унікальний номер талону для офісу {self.office} ({current_date_str}) після {max_attempts} спроб (ORM метод). Можливе високе навантаження."
        )

    def _get_common_realtime_data_fields(self):
        """Збирає загальні поля для WebSocket повідомлень."""
        service_name = self.get(
            "service_name")  # Спробувати отримати, якщо поле додано в doc
        if not service_name and self.service:
            service_name = frappe.db.get_value(
                "QMS Service", self.service, "service_name")

        # Спробувати отримати, якщо поле додано в doc
        service_point_name = self.get("service_point_name")
        if not service_point_name and self.service_point:
            service_point_name = frappe.db.get_value(
                "QMS Service Point", self.service_point, "point_name")

        # Подумайте, чи потрібен service_point_number і як його отримати, якщо він відрізняється від point_name
        service_point_number = self.get(
            "service_point_number")  # або інша логіка отримання

        return {
            "name": self.name,
            "ticket_id": self.name,  # Часто дублюється для зручності фронтенда
            "ticket_number": self.ticket_number,
            "office": self.office,
            "status": self.status,
            "service": self.service,
            "service_name": service_name or frappe._("Unknown Service"),
            "service_point": self.service_point,
            "service_point_name": service_point_name or (_("N/A") if self.status == "Called" or self.status == "Serving" else None),
            "service_point_number": service_point_number,  # Може бути None
            "operator": self.operator,
            "call_time": str(self.call_time) if self.call_time else None,
            "start_service_time": str(self.start_service_time) if self.start_service_time else None,
            "completion_time": str(self.completion_time) if self.completion_time else None,
            # Час останньої модифікації як основний час події
            "timestamp": str(self.modified),
            "visitor_phone": self.visitor_phone,
            # Додайте інші поля, які потрібні для ВСІХ типів подій табло
        }

    def publish_event(self, event_name_for_socket: str, event_type_in_payload: str):
        """Універсальний метод для публікації подій талону."""
        if not self.office:
            frappe.logger("qms_realtime").warning(
                f"QMSTicket {self.name}: Office not set. Cannot publish event '{event_name_for_socket}'.")
            return

        message_payload = self._get_common_realtime_data_fields()
        # Ключове поле для фронтенда
        message_payload["type"] = event_type_in_payload

        room = office_room(self.office)

        frappe.logger("qms_realtime").info(
            f"QMSTicket {self.name}: Publishing event '{event_name_for_socket}' to room '{room}' with payload: {message_payload}")

        frappe.publish_realtime(
            event=event_name_for_socket,
            message=message_payload,
            # room=room,
            after_commit=True
        )


def office_room(office_id: str):
    """
    Генерує ім'я кімнати для WebSocket на основі ID офісу.
    """
    return f'qms_office:{office_id}'

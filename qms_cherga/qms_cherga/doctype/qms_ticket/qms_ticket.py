# Copyright (c) 2025, Maxym Sysoiev and contributors
# For license information, please see license.txt

import time  # Для невеликої затримки при повторі
from frappe.utils import today, cint, now_datetime, get_date_str
import time
import frappe
from frappe.model.document import Document
from frappe.utils import today, cint  # cint for safe integer conversion


class QMSTicket(Document):
    def before_insert(self):
        # Встановлюємо номер талону перед першим збереженням
        # Перевіряємо, можливо він вже встановлений (малоймовірно)
        if not self.ticket_number:
            next_num = self.get_next_ticket_sequence()
            print(f"Next ticket number: {next_num}")
            # Записуємо тільки номер послідовності
            self.ticket_number = str(next_num).zfill(4)


class QMSTicket(Document):
    # Переконайтесь, що методу autoname(self) НЕМАЄ

    def before_insert(self):
        # Встановлюємо номер талону перед першим збереженням
        if not self.ticket_number:  # Перевірка, чи поле ще не заповнене
            next_num = self.get_next_ticket_sequence_orm()  # Викликаємо ORM версію
            self.ticket_number = str(next_num).zfill(4)

    def get_next_ticket_sequence_orm(self):
        """
        Отримує наступний номер послідовності з QMS Daily Counter,
        використовуючи Frappe ORM та цикл повторних спроб.
        УВАГА: Менш надійно при високому навантаженні, ніж SQL FOR UPDATE.
        """
        if not self.office:
            frappe.throw(
                "Office is required to generate Ticket Number Sequence")

        current_date_str = today()
        counter_doc_name = f"{self.office}-{current_date_str}"
        new_number = 0
        max_attempts = 5  # Максимальна кількість спроб

        for attempt in range(max_attempts):
            counter_doc = None
            try:
                if frappe.db.exists("QMS Daily Counter", counter_doc_name, debug=True):
                    print(f"Counter {counter_doc_name} exists.")
                    # Завантажуємо існуючий лічильник
                    counter_doc = frappe.get_doc(
                        "QMS Daily Counter", counter_doc_name)
                    # Перечитуємо з бази, щоб отримати найсвіжіше значення
                    # (хоча це не гарантує відсутності змін між load і save)
                    counter_doc.load_from_db()
                    new_number = counter_doc.last_number + 1
                    counter_doc.last_number = new_number
                    # Логування (можна прибрати пізніше)
                    # frappe.log_error(
                    #     f"Attempt {attempt+1}: Updating counter {counter_doc_name} from {new_number-1} to {new_number}", "QMSTicket ORM Counter")

                else:
                    # Створюємо новий лічильник
                    print(
                        f"Counter {counter_doc_name} does not exist. Creating new.")
                    new_number = 1
                    counter_doc = frappe.new_doc("QMS Daily Counter")
                    counter_doc.name = counter_doc_name
                    counter_doc.office = self.office
                    counter_doc.date = current_date_str
                    counter_doc.last_number = new_number
                    # Логування (можна прибрати пізніше)
                    frappe.log_error(
                        f"Attempt {attempt+1}: Creating counter {counter_doc_name} with value {new_number}", "QMSTicket ORM Counter")

                # Зберігаємо лічильник
                counter_doc.flags.ignore_permissions = True
                counter_doc.save()  # Тут може виникнути DuplicateEntryError при створенні

                # Якщо збереження пройшло успішно, повертаємо номер
                return new_number

            except frappe.DuplicateEntryError:
                # Колізія при створенні лічильника (insert). Інший процес встиг.
                # Просто переходимо до наступної спроби, яка має завантажити вже створений документ.
                frappe.log_warning(
                    f"Attempt {attempt + 1}: Duplicate entry error for {counter_doc_name}. Retrying.", "QMSTicket ORM Counter")
            except Exception as e:
                # Інша помилка
                frappe.log_error(frappe.get_traceback(
                ), f"QMS Ticket Autoname Counter Error (ORM Attempt {attempt + 1})")
                frappe.throw(
                    "Не вдалося згенерувати номер талону через помилку лічильника.")

            # Невелика затримка перед наступною спробою
            time.sleep(0.1 * (attempt + 1))

        # Якщо всі спроби не вдалися
        frappe.throw(
            f"Failed to get unique ticket sequence for office {self.office} after {max_attempts} attempts (ORM method).", title="Counter Error")
